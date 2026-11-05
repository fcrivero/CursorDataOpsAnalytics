#!/usr/bin/env python3
"""
ADINC weekly audit — always fetch tickets from Jira (no snapshot reuse), run all checks, email HTML report.

Usage:
  python run_weekly_audit.py              # audit + email (if SMTP configured)
  python run_weekly_audit.py --dry-run    # audit only, write report files locally
  python run_weekly_audit.py --no-email   # write reports, skip email

Environment (see .env.example):
  JIRA_SERVER, JIRA_TOKEN
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS
  EMAIL_FROM, EMAIL_TO (comma-separated)
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import smtplib
import ssl
import sys
from datetime import datetime, timezone
from difflib import get_close_matches
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

from adinc_field_allowlists import check_field_enums, explain_allowed_values_failure
from adinc_priority_check import (
    check_jira_priority,
    explain_priority_failure,
    format_inc_for_output,
    format_sla_missed_for_output,
    requires_p1,
)
from adinc_rca_open_check import check_rca_while_open, explain_rca_while_open, is_resolved_status
from adinc_title_format import audit_title_format, is_inc_number_na

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_OUTPUT_DIR = SCRIPT_DIR / "reports"

REQUIRED = [
    "INC_NUMBER", "TEAM", "PIPELINE", "DAG", "TASK",
    "SOURCE_SYSTEM", "ISSUE_CATEGORY", "EXTERNAL", "MISSED_SLA", "PD_ID",
]
REQUIRED_SET = set(REQUIRED)
NA_ALLOWED_FIELDS = {"INC_NUMBER", "DAG", "TASK", "PD_ID", "PIPELINE", "SOURCE_SYSTEM", "EXTERNAL", "MISSED_SLA"}
NOTES_FIELD = "customfield_10253"
OPEN_STATUSES = {"IN PROGRESS", "OPEN", "TO DO", "REOPENED", "BLOCKED"}
CLOSED_STATUSES = {"DONE", "CLOSED", "RESOLVED", "CANCELLED"}
EXCLUDED_RESOLUTIONS = {"CANCELLED"}

FIELD_LINE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$")


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def jira_base() -> str:
    return env("JIRA_SERVER", "https://deept.atlassian.net").rstrip("/")


def jira_browse(key: str) -> str:
    return f"{jira_base()}/browse/{key}"


def jira_request(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    token = env("JIRA_TOKEN")
    if not token:
        raise RuntimeError("JIRA_TOKEN is not set. Copy .env.example to .env and configure it.")

    url = urljoin(jira_base() + "/", path.lstrip("/"))
    body = json.dumps(payload).encode("utf-8")
    req = Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        },
        method="POST",
    )
    try:
        with urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jira API error {e.code}: {detail[:500]}") from e
    except URLError as e:
        raise RuntimeError(f"Jira connection failed: {e}") from e


def fetch_all_adinc_issues() -> list[dict[str, Any]]:
    jql = env("ADINC_JQL", "project = ADINC ORDER BY created DESC")
    fields = [
        "summary", "status", "resolution", "created", "updated", "description",
        NOTES_FIELD, "priority",
    ]  # resolution required for cancelled exclusion
    start_at = 0
    max_results = 100
    all_issues: list[dict[str, Any]] = []

    while True:
        data = jira_request(
            "/rest/api/2/search",
            {"jql": jql, "startAt": start_at, "maxResults": max_results, "fields": fields},
        )
        issues = data.get("issues", [])
        all_issues.extend(issues)
        total = data.get("total", len(all_issues))
        if start_at + len(issues) >= total or not issues:
            break
        start_at += len(issues)

    return all_issues


def parse_description(desc: str | None) -> tuple[dict[str, str], list[str]]:
    if not desc or not str(desc).strip():
        return {}, []
    text = str(desc).replace("\r\n", "\n").replace("\r", "\n")
    found: dict[str, str] = {}
    unparsed: list[str] = []
    for line in text.split("\n"):
        line_stripped = line.strip()
        if not line_stripped:
            continue
        m = FIELD_LINE_RE.match(line_stripped)
        if m:
            found[m.group(1).upper()] = m.group(2).strip()
        else:
            unparsed.append(line_stripped)
    return found, unparsed


def classify_value(field: str, val: str | None) -> str | None:
    if val is None or not val.strip():
        return "Blank"
    upper = val.strip().upper()
    if upper in ("NA", "N/A", "N.A.", "NONE") and field not in NA_ALLOWED_FIELDS:
        return "NA"
    if upper == "TBD":
        return "TBD"
    return None


def is_rca_missing(notes: str | None) -> tuple[bool, str]:
    from adinc_notes import is_rca_missing as _is_rca_missing
    return _is_rca_missing(notes)


def check_structure(desc: str, found: dict[str, str], unparsed: list[str]) -> tuple[bool, str]:
    parts: list[str] = []
    if not desc or not str(desc).strip():
        parts.append("Description is empty")
    missing = [f for f in REQUIRED if f not in found]
    if missing:
        parts.append("Missing: " + ", ".join(missing))
    misspelled: list[str] = []
    extra: list[str] = []
    for key in found:
        if key in REQUIRED_SET:
            continue
        close = get_close_matches(key, REQUIRED, n=1, cutoff=0.75)
        if close:
            misspelled.append(f"{key} (likely meant {close[0]})")
        else:
            extra.append(key)
    if misspelled:
        parts.append("Misspelled: " + "; ".join(misspelled))
    if extra:
        parts.append("Extra fields: " + ", ".join(extra))
    if unparsed:
        preview = " | ".join(unparsed[:2])
        if len(unparsed) > 2:
            preview += "..."
        parts.append("Unparsed content: " + preview)
    if not parts:
        return False, "All 10 required fields present and correctly named"
    return True, "; ".join(parts)


def check_invalid_values(found: dict[str, str]) -> tuple[bool, str]:
    findings: list[str] = []
    for field in REQUIRED:
        if field not in found:
            findings.append(f"{field}=Missing (field absent)")
            continue
        kind = classify_value(field, found[field])
        if kind:
            display = found[field] if found[field] else "(empty)"
            findings.append(f"{field}={kind} ({display})")
    if not findings:
        return False, "No invalid placeholder values"
    return True, "; ".join(findings)


def adf_to_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(n) for n in node)
    if not isinstance(node, dict):
        return str(node)

    kind = node.get("type")
    attrs = node.get("attrs") or {}

    if kind == "text":
        text = node.get("text", "")
        for mark in node.get("marks") or []:
            if mark.get("type") == "link":
                href = (mark.get("attrs") or {}).get("href", "")
                if href:
                    return f"[{href}|{text or href}|smart-link]"
        return text

    if kind in ("inlineCard", "blockCard", "embedCard"):
        url = attrs.get("url", "")
        if url:
            return f"[{url}|{url}|smart-link]"
        return ""

    if kind == "hardBreak":
        return "\n"
    if kind == "paragraph":
        return adf_to_text(node.get("content")) + "\n"
    return adf_to_text(node.get("content"))


def field_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return adf_to_text(value).strip()
    return str(value)


def normalize_issue(raw: dict[str, Any]) -> dict[str, Any]:
    fields = raw.get("fields") or {}
    status_obj = fields.get("status") or {}
    resolution_obj = fields.get("resolution") or {}
    return {
        "key": raw.get("key", ""),
        "summary": fields.get("summary") or "",
        "status": status_obj.get("name") or "",
        "resolution": resolution_obj.get("name") or "" if isinstance(resolution_obj, dict) else str(resolution_obj or ""),
        "created": (fields.get("created") or "")[:10],
        "updated": (fields.get("updated") or "")[:10],
        "description": field_to_text(fields.get("description")),
        "notes": field_to_text(fields.get(NOTES_FIELD)) or field_to_text(fields.get("notes")),
        "priority": (
            (fields.get("priority") or {}).get("name", "")
            if isinstance(fields.get("priority"), dict)
            else str(fields.get("priority") or "")
        ),
    }


def is_excluded(issue: dict[str, Any]) -> bool:
    resolution = str(issue.get("resolution") or "").strip().upper()
    if resolution in EXCLUDED_RESOLUTIONS:
        return True
    return str(issue.get("status") or "").strip().upper() == "CANCELLED"


def run_audit(issues: list[dict[str, Any]]) -> dict[str, Any]:
    structure_flagged: list[dict[str, str]] = []
    open_flagged: list[dict[str, str]] = []
    closed_invalid_flagged: list[dict[str, str]] = []
    rca_flagged: list[dict[str, str]] = []
    title_format_flagged: list[dict[str, str]] = []
    field_enums_flagged: list[dict[str, str]] = []
    priority_flagged: list[dict[str, str]] = []
    rca_while_open_flagged: list[dict[str, str]] = []
    title_format_scanned = 0
    priority_applicable = 0
    not_done_scanned = 0
    excluded_count = 0
    open_count = 0
    closed_count = 0

    for raw in issues:
        issue = normalize_issue(raw)
        if is_excluded(issue):
            excluded_count += 1
            continue
        desc = issue["description"]
        found, unparsed = parse_description(desc)
        status = issue["status"].upper()
        row = {
            "key": issue["key"],
            "url": jira_browse(issue["key"]),
            "summary": issue["summary"],
            "status": issue["status"],
            "created": issue["created"],
            "updated": issue["updated"],
        }

        flagged, comments = check_structure(desc, found, unparsed)
        if flagged:
            structure_flagged.append({**row, "audit_type": "Structure", "comments": comments})

        if is_inc_number_na(found):
            title_format_scanned += 1
            flagged, comments, suggested = audit_title_format(issue["summary"], found)
            if flagged:
                title_format_flagged.append({
                    **row,
                    "audit_type": "Title Format",
                    "comments": comments,
                    "suggested_title": suggested,
                    "current_summary": issue["summary"],
                })

        flagged, comments = check_field_enums(found)
        if flagged:
            field_enums_flagged.append({
                **row,
                "audit_type": "Allowed Values in Fields (Dropdowns)",
                "comments": comments,
                "plain_english": explain_allowed_values_failure(comments),
            })

        if requires_p1(found, issue.get("created"))[0]:
            priority_applicable += 1
            flagged, comments = check_jira_priority(
                found, issue.get("priority"), issue.get("created"),
            )
            if flagged:
                priority_flagged.append({
                    **row,
                    "audit_type": "Jira Priority",
                    "comments": comments,
                    "plain_english": explain_priority_failure(comments),
                    "jira_priority": issue.get("priority") or "",
                    "missed_sla": format_sla_missed_for_output(found.get("MISSED_SLA")),
                    "inc_display": format_inc_for_output(
                        found.get("INC_NUMBER"), issue.get("created"),
                    ),
                })

        if not is_resolved_status(issue["status"]):
            not_done_scanned += 1
            flagged, comments = check_rca_while_open(issue["status"], issue["notes"])
            if flagged:
                rca_while_open_flagged.append({
                    **row,
                    "audit_type": "RCA While Open",
                    "comments": comments,
                    "plain_english": explain_rca_while_open(comments),
                })

        if status in OPEN_STATUSES:
            open_count += 1
            flagged, comments = check_invalid_values(found)
            if flagged:
                open_flagged.append({**row, "audit_type": "Open Invalid Values", "comments": comments})
        elif status in CLOSED_STATUSES:
            closed_count += 1
            flagged, comments = check_invalid_values(found)
            if flagged:
                closed_invalid_flagged.append({**row, "audit_type": "Closed Invalid Values", "comments": comments})
            missing, comments = is_rca_missing(issue["notes"])
            if missing:
                rca_flagged.append({**row, "audit_type": "Missing RCA", "comments": comments})

    return {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "summary": {
            "total": len(issues),
            "audited": len(issues) - excluded_count,
            "excluded_cancelled": excluded_count,
            "open": open_count,
            "closed": closed_count,
            "structure": {"scanned": len(issues) - excluded_count, "flagged": len(structure_flagged)},
            "open_invalid": {"scanned": open_count, "flagged": len(open_flagged)},
            "closed_invalid": {"scanned": closed_count, "flagged": len(closed_invalid_flagged)},
            "rca": {"scanned": closed_count, "flagged": len(rca_flagged)},
            "title_format": {"scanned": title_format_scanned, "flagged": len(title_format_flagged)},
            "field_enums": {"scanned": len(issues) - excluded_count, "flagged": len(field_enums_flagged)},
            "jira_priority": {"scanned": priority_applicable, "flagged": len(priority_flagged)},
            "rca_while_open": {"scanned": not_done_scanned, "flagged": len(rca_while_open_flagged)},
        },
        "structure": structure_flagged,
        "open_invalid": open_flagged,
        "closed_invalid": closed_invalid_flagged,
        "rca": rca_flagged,
        "title_format": title_format_flagged,
        "field_enums": field_enums_flagged,
        "jira_priority": priority_flagged,
        "rca_while_open": rca_while_open_flagged,
    }


def html_table(rows: list[dict[str, str]], max_rows: int | None = None) -> str:
    if not rows:
        return "<p><em>No issues found.</em></p>"
    display = rows[:max_rows] if max_rows else rows
    out = [
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px;">',
        "<tr><th>Ticket</th><th>Summary</th><th>Status</th><th>Created</th><th>Updated</th><th>Comments</th></tr>",
    ]
    for r in display:
        out.append(
            "<tr>"
            f'<td><a href="{r["url"]}">{r["key"]}</a></td>'
            f'<td>{escape_html(r["summary"][:120])}</td>'
            f'<td>{escape_html(r["status"])}</td>'
            f'<td>{escape_html(r["created"])}</td>'
            f'<td>{escape_html(r["updated"])}</td>'
            f'<td>{escape_html(r["comments"])}</td>'
            "</tr>"
        )
    out.append("</table>")
    if max_rows and len(rows) > max_rows:
        out.append(f"<p><em>Showing {max_rows} of {len(rows)} — see CSV attachment for full list.</em></p>")
    return "\n".join(out)


def title_format_html_table(rows: list[dict[str, str]], max_rows: int | None = None) -> str:
    if not rows:
        return "<p><em>No issues found.</em></p>"
    display = rows[:max_rows] if max_rows else rows
    out = [
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px;">',
        "<tr><th>Ticket</th><th>Current title</th><th>Proposed title</th><th>Status</th><th>Comments</th></tr>",
    ]
    for r in display:
        out.append(
            "<tr>"
            f'<td><a href="{r["url"]}">{r["key"]}</a></td>'
            f'<td>{escape_html(r.get("current_summary", r.get("summary", ""))[:120])}</td>'
            f'<td>{escape_html(r.get("suggested_title", "")[:160])}</td>'
            f'<td>{escape_html(r["status"])}</td>'
            f'<td>{escape_html(r["comments"])}</td>'
            "</tr>"
        )
    out.append("</table>")
    if max_rows and len(rows) > max_rows:
        out.append(f"<p><em>Showing {max_rows} of {len(rows)} — see CSV attachment for full list.</em></p>")
    return "\n".join(out)


ALLOWED_VALUES_REFERENCE_HTML = """
<p>Four description fields must use approved dropdown values (same rules as ticket creation).</p>
<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px;">
<tr><th>Field</th><th>Rule</th><th>Example pass</th><th>Example fail</th></tr>
<tr><td>TEAM</td><td>Must be exactly ads-data-support</td><td>ads-data-support</td><td>ODS, blank</td></tr>
<tr><td>ISSUE_CATEGORY</td><td>Must match approved list (case-sensitive)</td><td>Data - DQ, AWS - Kinesis, AWS - S3</td><td>AWS - S3*, blank</td></tr>
<tr><td>SOURCE_SYSTEM</td><td>Approved list or NA / N/A</td><td>ODS - Metrics, 3P Vendor - Hightouch, NA</td><td>typo or invented vendor name</td></tr>
<tr><td>PIPELINE</td><td>Must match approved list</td><td>ADM - Targeting, NA</td><td>typo or invented value</td></tr>
</table>
"""


def jira_priority_html_table(rows: list[dict[str, str]], max_rows: int | None = None) -> str:
    if not rows:
        return "<p><em>No issues found.</em></p>"
    display = rows[:max_rows] if max_rows else rows
    out = [
        '<p>MISSED_SLA=Y always requires P1. Real INC_NUMBER requires P1 only for tickets created after 2026-05-30.</p>',
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px;">',
        "<tr><th>Ticket</th><th>INC (Customer Impacted)</th><th>SLA MISSED</th><th>Priority</th></tr>",
    ]
    for r in display:
        title = escape_html(r.get("summary", r["key"])[:160])
        out.append(
            "<tr>"
            f'<td><a href="{r["url"]}">{title}</a></td>'
            f'<td>{escape_html(r.get("inc_display", ""))}</td>'
            f'<td>{escape_html(r.get("missed_sla", ""))}</td>'
            f'<td>{escape_html(r.get("jira_priority", ""))}</td>'
            "</tr>"
        )
    out.append("</table>")
    if max_rows and len(rows) > max_rows:
        out.append(f"<p><em>Showing {max_rows} of {len(rows)} — see CSV attachment for full list.</em></p>")
    return "\n".join(out)


def allowed_values_html_table(rows: list[dict[str, str]], max_rows: int | None = None) -> str:
    out = [ALLOWED_VALUES_REFERENCE_HTML]
    if not rows:
        out.append("<p><em>No issues found.</em></p>")
        return "\n".join(out)
    display = rows[:max_rows] if max_rows else rows
    out.extend([
        '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;width:100%;font-size:13px;">',
        "<tr><th>Ticket</th><th>Status</th><th>What's wrong</th><th>Technical details</th></tr>",
    ])
    for r in display:
        out.append(
            "<tr>"
            f'<td><a href="{r["url"]}">{r["key"]}</a></td>'
            f'<td>{escape_html(r["status"])}</td>'
            f'<td>{escape_html(r.get("plain_english", r["comments"]))}</td>'
            f'<td>{escape_html(r["comments"])}</td>'
            "</tr>"
        )
    out.append("</table>")
    if max_rows and len(rows) > max_rows:
        out.append(f"<p><em>Showing {max_rows} of {len(rows)} — see CSV attachment for full list.</em></p>")
    return "\n".join(out)


def escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_html_report(audit: dict[str, Any]) -> str:
    s = audit["summary"]
    priority = {
        r["key"]
        for r in audit["structure"] + audit["open_invalid"] + audit["rca"] + audit["rca_while_open"] + audit["title_format"] + audit["field_enums"] + audit["jira_priority"]
    }

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>ADINC Weekly Audit</title></head>
<body style="font-family:Segoe UI,Arial,sans-serif;color:#222;max-width:1100px;margin:0 auto;padding:20px;">
  <h1>ADINC Weekly Audit Report</h1>
  <p>Generated: {escape_html(audit["generated_at"])}</p>

  <h2>Executive summary</h2>
  <table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;">
    <tr><th>Check</th><th>Scanned</th><th>Flagged</th></tr>
    <tr><td>Structure</td><td>{s["structure"]["scanned"]}</td><td>{s["structure"]["flagged"]}</td></tr>
    <tr><td>Open invalid values (TBD/NA/Blank)</td><td>{s["open_invalid"]["scanned"]}</td><td>{s["open_invalid"]["flagged"]}</td></tr>
    <tr><td>Closed invalid values (TBD/NA/Blank)</td><td>{s["closed_invalid"]["scanned"]}</td><td>{s["closed_invalid"]["flagged"]}</td></tr>
    <tr><td>Missing RCA in Notes</td><td>{s["rca"]["scanned"]}</td><td>{s["rca"]["flagged"]}</td></tr>
    <tr><td>Title format (INC_NUMBER=NA)</td><td>{s["title_format"]["scanned"]}</td><td>{s["title_format"]["flagged"]}</td></tr>
    <tr><td>Allowed values in fields (dropdowns)</td><td>{s["field_enums"]["scanned"]}</td><td>{s["field_enums"]["flagged"]}</td></tr>
    <tr><td>Jira Priority (P1 required)</td><td>{s["jira_priority"]["scanned"]}</td><td>{s["jira_priority"]["flagged"]}</td></tr>
    <tr><td>RCA in Notes while not Done/Closed</td><td>{s["rca_while_open"]["scanned"]}</td><td>{s["rca_while_open"]["flagged"]}</td></tr>
  </table>

  <p><strong>Total tickets:</strong> {s["total"]} &nbsp;|&nbsp;
     <strong>Open:</strong> {s["open"]} &nbsp;|&nbsp;
     <strong>Closed:</strong> {s["closed"]}</p>

  {"<p><strong>Priority tickets:</strong> " + ", ".join(sorted(priority)) + "</p>" if priority else ""}

  <h2>Check 1 — Structure issues ({s["structure"]["flagged"]})</h2>
  {html_table(audit["structure"])}

  <h2>Check 2 — Open tickets with invalid values ({s["open_invalid"]["flagged"]})</h2>
  {html_table(audit["open_invalid"])}

  <h2>Check 4 — Closed tickets missing RCA ({s["rca"]["flagged"]})</h2>
  {html_table(audit["rca"])}

  <h2>Check 5 — Title format / Summary, INC_NUMBER=NA ({s["title_format"]["flagged"]})</h2>
  {title_format_html_table(audit["title_format"])}

  <h2>Check 6 — Allowed Values in Fields (Dropdowns) ({s["field_enums"]["flagged"]})</h2>
  {allowed_values_html_table(audit["field_enums"], max_rows=50)}

  <h2>Check 7 — Jira Priority (P1 required) ({s["jira_priority"]["flagged"]})</h2>
  {jira_priority_html_table(audit["jira_priority"], max_rows=50)}

  <h2>Check 8 — RCA in Notes while not Done/Closed ({s["rca_while_open"]["flagged"]})</h2>
  {html_table(audit["rca_while_open"], max_rows=50)}

  <h2>Check 3 — Closed tickets with invalid values ({s["closed_invalid"]["flagged"]})</h2>
  {html_table(audit["closed_invalid"], max_rows=50)}

  <hr>
  <p style="font-size:12px;color:#666;">Automated by ADINC weekly audit script. Jira: {escape_html(jira_base())}/projects/ADINC</p>
</body>
</html>"""


def write_csv(audit: dict[str, Any], path: Path) -> None:
    all_rows: list[dict[str, str]] = []
    for section in ("structure", "open_invalid", "closed_invalid", "rca", "rca_while_open", "title_format", "field_enums", "jira_priority"):
        all_rows.extend(audit[section])

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "audit_type", "key", "url", "summary", "status", "created", "updated",
                "comments", "suggested_title", "current_summary", "plain_english",
                "jira_priority", "missed_sla", "inc_display",
            ],
        )
        writer.writeheader()
        for row in all_rows:
            writer.writerow({k: row.get(k, "") for k in writer.fieldnames})


def send_email(subject: str, html_body: str, attachments: list[tuple[str, bytes]]) -> None:
    smtp_host = env("SMTP_HOST")
    smtp_port = int(env("SMTP_PORT", "587") or "587")
    smtp_user = env("SMTP_USER")
    smtp_password = env("SMTP_PASSWORD")
    email_from = env("EMAIL_FROM")
    email_to = [x.strip() for x in env("EMAIL_TO").split(",") if x.strip()]

    if not all([smtp_host, email_from, email_to]):
        raise RuntimeError("Email not configured. Set SMTP_HOST, EMAIL_FROM, EMAIL_TO in .env")

    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = email_from
    msg["To"] = ", ".join(email_to)
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    for filename, content in attachments:
        part = MIMEApplication(content, Name=filename)
        part["Content-Disposition"] = f'attachment; filename="{filename}"'
        msg.attach(part)

    use_tls = env("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    with smtplib.SMTP(smtp_host, smtp_port, timeout=60) as server:
        if use_tls:
            server.starttls(context=ssl.create_default_context())
        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)
        server.sendmail(email_from, email_to, msg.as_string())


def main() -> int:
    parser = argparse.ArgumentParser(description="ADINC weekly audit and email report")
    parser.add_argument("--dry-run", action="store_true", help="Fetch and report locally; do not email")
    parser.add_argument("--no-email", action="store_true", help="Write report files only")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    load_dotenv(SCRIPT_DIR / ".env")

    print("Fetching ADINC tickets from Jira...")
    issues = fetch_all_adinc_issues()
    print(f"Fetched {len(issues)} tickets")

    audit = run_audit(issues)
    s = audit["summary"]

    print(f"Structure flagged: {s['structure']['flagged']}")
    print(f"Open invalid: {s['open_invalid']['flagged']}")
    print(f"Closed invalid: {s['closed_invalid']['flagged']}")
    print(f"Missing RCA: {s['rca']['flagged']}")
    print(f"Title format (INC_NUMBER=NA): {s['title_format']['flagged']} / {s['title_format']['scanned']} scanned")
    print(f"Allowed values: {s['field_enums']['flagged']} / {s['field_enums']['scanned']} scanned")
    print(f"Jira priority: {s['jira_priority']['flagged']} / {s['jira_priority']['scanned']} applicable")
    print(f"RCA while open: {s['rca_while_open']['flagged']} / {s['rca_while_open']['scanned']} not Done/Closed")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d")
    json_path = args.output_dir / f"adinc-audit-{stamp}.json"
    html_path = args.output_dir / f"adinc-audit-{stamp}.html"
    csv_path = args.output_dir / f"adinc-audit-{stamp}.csv"

    json_path.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    html_body = build_html_report(audit)
    html_path.write_text(html_body, encoding="utf-8")
    write_csv(audit, csv_path)
    print(f"Wrote {json_path}")
    print(f"Wrote {html_path}")
    print(f"Wrote {csv_path}")

    if args.dry_run or args.no_email:
        print("Email skipped (--dry-run or --no-email)")
        return 0

    subject = env(
        "EMAIL_SUBJECT",
        f"ADINC Weekly Audit — {s['structure']['flagged']} structure, "
        f"{s['open_invalid']['flagged']} open, {s['rca']['flagged']} missing RCA",
    )
    send_email(subject, html_body, [(csv_path.name, csv_path.read_bytes())])
    print(f"Email sent to: {env('EMAIL_TO')}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
