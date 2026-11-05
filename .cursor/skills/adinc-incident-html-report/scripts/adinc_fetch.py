"""Fetch ADINC issues from Jira REST API."""
from __future__ import annotations

import json
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

from adinc_credentials import JIRA_BASE, basic_auth
from adinc_lifecycle_metrics import (
    COMPLETION_DATE,
    END_DATE,
    START_DATE_PICK,
    compute_metrics,
    metrics_from_jira_fields,
)

NOTES_FIELD = "customfield_10253"

SEARCH_FIELDS = [
    "summary",
    "status",
    "resolution",
    "priority",
    "created",
    "updated",
    "resolutiondate",
    "description",
    NOTES_FIELD,
    START_DATE_PICK,
    COMPLETION_DATE,
    END_DATE,
]


def adf_to_text(node) -> str:
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
                    return f"[{href}|{text or href}]"
        return text
    if kind == "hardBreak":
        return "\n"
    if kind == "paragraph":
        return adf_to_text(node.get("content")) + "\n"
    return adf_to_text(node.get("content"))


def field_to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return adf_to_text(value).strip()
    return str(value)


def normalize_issue(raw: dict) -> dict:
    f = raw.get("fields") or {}
    status = f.get("status") or {}
    priority_field = f.get("priority")
    if isinstance(priority_field, dict):
        priority = priority_field.get("name") or ""
    else:
        priority = str(priority_field or "")

    issue = {
        "key": raw.get("key", ""),
        "summary": f.get("summary") or "",
        "status": status.get("name") if isinstance(status, dict) else str(status or ""),
        "priority": priority,
        "created": f.get("created") or "",
        "updated": f.get("updated") or "",
        "description": field_to_text(f.get("description")),
        "notes": field_to_text(f.get(NOTES_FIELD)),
        "resolutiondate": f.get("resolutiondate") or "",
    }
    issue.update(metrics_from_jira_fields(f))
    issue.update(compute_metrics(issue))
    return issue


def jira_search(jql: str, auth_header: str, *, max_results: int = 100) -> list[dict]:
    issues: list[dict] = []
    page_token: str | None = None
    field_list = ",".join(SEARCH_FIELDS)
    while True:
        params = [
            f"jql={quote(jql)}",
            f"maxResults={max_results}",
            f"fields={quote(field_list)}",
        ]
        if page_token:
            params.append(f"nextPageToken={quote(page_token)}")
        url = f"{JIRA_BASE}/rest/api/3/search/jql?{'&'.join(params)}"
        req = Request(
            url,
            headers={"Authorization": f"Basic {auth_header}", "Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Jira search failed ({e.code}): {detail[:500]}") from e
        batch = data.get("issues", [])
        issues.extend(normalize_issue(i) for i in batch)
        page_token = data.get("nextPageToken")
        if not page_token or not batch:
            break
    return issues
