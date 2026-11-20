"""Confluence RCA fetch for MTTD (defect introduction §5)."""
from __future__ import annotations

import json
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from adinc_credentials import confluence_auth_header, confluence_base
from adinc_lifecycle_metrics import (
    compute_metrics,
    extract_confluence_page_id,
    parse_defect_introduction_from_storage_html,
)


def confluence_get_storage(page_id: str, auth_header: str) -> str:
    url = f"{confluence_base()}/wiki/rest/api/content/{page_id}?expand=body.storage"
    req = Request(
        url,
        headers={"Authorization": auth_header, "Accept": "application/json"},
    )
    try:
        with urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode())
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:300]
        raise RuntimeError(f"HTTP {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(str(exc.reason or exc)) from exc
    storage = (data.get("body") or {}).get("storage", {}).get("value")
    if not storage:
        raise RuntimeError("empty body.storage in Confluence response")
    return storage


def enrich_mttd(issue: dict, auth_header: str | None) -> dict:
    issue = dict(issue)
    issue["confluence_page_id"] = issue.get("confluence_page_id") or extract_confluence_page_id(
        issue.get("notes")
    )
    key = issue.get("key") or "?"
    page_id = issue.get("confluence_page_id")

    if not page_id:
        issue["mttd_enrichment"] = "no_confluence_link"
        issue.update(compute_metrics(issue))
        return issue
    if not auth_header:
        issue["mttd_enrichment"] = "no_confluence_auth"
        issue.update(compute_metrics(issue))
        return issue

    try:
        storage = confluence_get_storage(page_id, auth_header)
    except RuntimeError as exc:
        issue["mttd_enrichment"] = "confluence_error"
        issue["mttd_confluence_error"] = str(exc)
        print(f"Warning: {key}: Confluence page {page_id}: {exc}", file=sys.stderr)
        issue.update(compute_metrics(issue))
        return issue

    d = parse_defect_introduction_from_storage_html(storage)
    if d:
        issue["defect_introduction_date"] = d.isoformat()
        issue["mttd_enrichment"] = "ok"
    else:
        issue["mttd_enrichment"] = "no_defect_introduction_in_rca"
        print(
            f"Warning: {key}: Confluence page {page_id}: no parsable "
            "'Defect introduction time' in RCA body",
            file=sys.stderr,
        )
    issue.update(compute_metrics(issue))
    return issue