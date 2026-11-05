"""Confluence RCA fetch for MTTD (defect introduction §5)."""
from __future__ import annotations

import json
from urllib.request import Request, urlopen

from adinc_credentials import CONFLUENCE_BASE
from adinc_lifecycle_metrics import (
    compute_metrics,
    extract_confluence_page_id,
    parse_defect_introduction_from_storage_html,
)


def confluence_get_storage(page_id: str, auth_header: str) -> str | None:
    url = f"{CONFLUENCE_BASE}/wiki/rest/api/content/{page_id}?expand=body.storage"
    req = Request(
        url,
        headers={"Authorization": f"Basic {auth_header}", "Accept": "application/json"},
    )
    with urlopen(req, timeout=90) as resp:
        data = json.loads(resp.read().decode())
    return (data.get("body") or {}).get("storage", {}).get("value")


def enrich_mttd(issue: dict, auth_header: str) -> dict:
    issue = dict(issue)
    issue["confluence_page_id"] = extract_confluence_page_id(issue.get("notes"))
    if not issue.get("confluence_page_id"):
        issue.update(compute_metrics(issue))
        return issue
    try:
        storage = confluence_get_storage(issue["confluence_page_id"], auth_header)
    except Exception:
        storage = None
    if storage:
        d = parse_defect_introduction_from_storage_html(storage)
        if d:
            issue["defect_introduction_date"] = d.isoformat()
    issue.update(compute_metrics(issue))
    return issue
