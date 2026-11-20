#!/usr/bin/env python3
"""Fast PagerDuty fetch for Data Ops incident analysis.

Usage:
  python pd_incident_fetch.py 5794432
  python pd_incident_fetch.py 5794432 --similar-days 90 --max-pages 3

Never uses GET /incidents?incident_number= (invalid). Always GET /incidents/{pd#}.
Similar-incident search: default 30d / 3 pages for same-job (Step 5a) — never unbounded pagination.
By default searches **High Urgency** (`P7OFL7L`) only; pass `--include-low` to add `P3CUKVY` (matches skill default scope).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

DEFAULT_SERVICE_IDS = ["P7OFL7L"]
ALL_DATAOPS_SERVICE_IDS = ["P7OFL7L", "P3CUKVY"]
RUNBOOK_RE = re.compile(
    r"\[Link to Job Runbooks\]\(\s*(https?://[^)\s]+)\s*\)", re.I
)
JOB_TITLE_RE = re.compile(r"job_name:([A-Za-z0-9_.]+)")
JOB_BODY_RE = re.compile(r"^Job:\s*(.+)$", re.M)
RUN_TITLE_RE = re.compile(r"@databricks_job_run_id:(\d+)")
RUN_BODY_RE = re.compile(r"^Run:\s*(\d+)$", re.M)


def get_auth() -> str:
    cfg_path = os.path.expanduser("~/.cursor/mcp.json")
    with open(cfg_path, encoding="utf-8") as f:
        cfg = json.load(f)
    servers = cfg.get("mcpServers", {})
    for name in ("pagerduty-mcp-manual", "pagerduty"):
        if name in servers:
            hdr = servers[name].get("headers", {})
            candidate = hdr.get("Authorization")
            if candidate and "$" not in candidate:
                return (
                    candidate
                    if candidate.startswith("Token")
                    else f"Token {candidate}"
                )
    for name, v in servers.items():
        if "pagerduty" in name.lower():
            hdr = v.get("headers", {})
            candidate = hdr.get("Authorization")
            if candidate and "$" not in candidate:
                return (
                    candidate
                    if candidate.startswith("Token")
                    else f"Token {candidate}"
                )
    sys.exit("error: no pagerduty token in ~/.cursor/mcp.json")


def api(auth: str, path: str) -> dict:
    req = urllib.request.Request(
        f"https://api.pagerduty.com{path}",
        headers={
            "Authorization": auth,
            "Accept": "application/vnd.pagerduty+json;version=2",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def extract_job_run(title: str, alert_body: str | None) -> tuple[str | None, str | None]:
    job = None
    run_id = None
    if title:
        m = JOB_TITLE_RE.search(title)
        if m:
            job = m.group(1)
        m = RUN_TITLE_RE.search(title)
        if m:
            run_id = m.group(1)
    if alert_body:
        if not job:
            m = JOB_BODY_RE.search(alert_body)
            if m:
                job = m.group(1).strip()
        if not run_id:
            m = RUN_BODY_RE.search(alert_body)
            if m:
                run_id = m.group(1)
    return job, run_id


def extract_runbook(alert_body: str | None) -> str | None:
    if not alert_body:
        return None
    m = RUNBOOK_RE.search(alert_body)
    return m.group(1).strip() if m else None


def extract_responder(inc: dict, log_entries: list) -> dict[str, str | None]:
    """Current assignee or last ack/assign from timeline (assignments clear on resolve)."""
    for a in inc.get("assignments") or []:
        name = (a.get("assignee") or {}).get("summary")
        if name:
            return {"name": name, "source": "assignments"}
    ordered = sorted(
        log_entries,
        key=lambda e: e.get("created_at") or "",
        reverse=True,
    )
    for entry in ordered:
        typ = entry.get("type")
        agent = (entry.get("agent") or {}).get("summary")
        if typ == "acknowledge_log_entry" and agent:
            return {"name": agent, "source": "acknowledged"}
        if typ == "assign_log_entry":
            assignees = entry.get("assignees") or []
            if assignees and assignees[0].get("summary"):
                return {"name": assignees[0]["summary"], "source": "assigned"}
            if agent and (entry.get("agent") or {}).get("type") == "user_reference":
                return {"name": agent, "source": "assigned"}
    return {"name": None, "source": None}


def alert_body_text(alerts: list) -> str | None:
    for alert in alerts:
        body = alert.get("body") or {}
        details = body.get("details") or {}
        text = details.get("body")
        if text:
            return text
        cef = body.get("cef_details") or {}
        cef_details = cef.get("details") or {}
        text = cef_details.get("body")
        if text:
            return text
    return None


def fetch_similar(
    auth: str,
    *,
    current_pd: str,
    title: str,
    job: str | None,
    since: str,
    until: str,
    max_pages: int,
    service_ids: list[str],
) -> list[dict]:
    matches: list[dict] = []
    offset = 0
    for _ in range(max_pages):
        qs = (
            f"?service_ids[]={'&service_ids[]='.join(service_ids)}"
            f"&since={since}&until={until}&limit=100&offset={offset}"
            f"&sort_by=created_at:desc"
        )
        data = api(auth, f"/incidents{qs}")
        batch = data.get("incidents", [])
        if not batch:
            break
        for inc in batch:
            if str(inc.get("incident_number")) == str(current_pd):
                continue
            t = inc.get("title") or ""
            if title and t == title:
                matches.append({"match": "same_title", **inc})
            elif job and (job in t or job in (inc.get("summary") or "")):
                matches.append({"match": "same_job", **inc})
        if len(matches) >= 15:
            break
        if not data.get("more", False):
            break
        offset += len(batch)
    return matches[:15]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fast PD incident fetch for analysis")
    parser.add_argument("pd", help="PagerDuty incident number (e.g. 5794432)")
    parser.add_argument(
        "--similar-days",
        type=int,
        default=30,
        help="Lookback for similar incidents (default: 30)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Max list_incidents pages for similar search (default: 3 for Step 5a, max 5)",
    )
    parser.add_argument(
        "--include-low",
        action="store_true",
        help="Include Low Urgency service P3CUKVY in similar-incident search (default: High P7OFL7L only)",
    )
    args = parser.parse_args()
    max_pages = max(1, min(args.max_pages, 5))

    auth = get_auth()
    pd = str(args.pd).lstrip("#")

    try:
        inc = api(auth, f"/incidents/{pd}")["incident"]
    except urllib.error.HTTPError as e:
        sys.exit(f"error: GET /incidents/{pd} failed: {e.code} {e.reason}")

    uuid = inc["id"]
    if str(inc.get("incident_number")) != pd:
        sys.exit(
            f"error: identity mismatch — requested PD#{pd}, "
            f"got PD#{inc.get('incident_number')}"
        )

    with ThreadPoolExecutor(max_workers=3) as pool:
        notes_f = pool.submit(api, auth, f"/incidents/{uuid}/notes")
        alerts_f = pool.submit(api, auth, f"/incidents/{uuid}/alerts")
        logs_f = pool.submit(api, auth, f"/incidents/{uuid}/log_entries?limit=100")
        notes = notes_f.result().get("notes", [])
        alerts = alerts_f.result().get("alerts", [])
        log_entries = logs_f.result().get("log_entries", [])

    body = alert_body_text(alerts)
    job, run_id = extract_job_run(inc.get("title", ""), body)
    runbook_url = extract_runbook(body)

    until = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    since = (
        datetime.now(timezone.utc) - timedelta(days=args.similar_days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    sid = ALL_DATAOPS_SERVICE_IDS if args.include_low else DEFAULT_SERVICE_IDS
    similar = fetch_similar(
        auth,
        current_pd=pd,
        title=inc.get("title", ""),
        job=job,
        since=since,
        until=until,
        max_pages=max_pages,
        service_ids=sid,
    )

    assignee = extract_responder(inc, log_entries)

    out = {
        "incident": inc,
        "verified_uuid": uuid,
        "notes": notes,
        "alerts": alerts,
        "log_entries": log_entries,
        "parsed": {
            "job": job,
            "run_id": run_id,
            "runbook_url": runbook_url,
            "workspace": None,
            "assignee": assignee,
            "responder": assignee,
        },
        "similar": {
            "lookback_days": args.similar_days,
            "pages_fetched": max_pages,
            "service_ids": sid,
            "count": len(similar),
            "incidents": similar,
        },
    }
    if body:
        m = re.search(r"^Workspace:\s*(\S+)$", body, re.M)
        if m:
            out["parsed"]["workspace"] = m.group(1)

    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
