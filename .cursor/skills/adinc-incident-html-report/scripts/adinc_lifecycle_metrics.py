"""ADINC lifecycle metrics from Jira date fields and Confluence RCA (date-only math)."""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

START_DATE_PICK = "customfield_10489"
COMPLETION_DATE = "customfield_10566"
END_DATE = "customfield_10453"

CONFLUENCE_PAGE_RE = re.compile(
    r"pageId=(\d+)|/pages/(\d+)/|/pages/viewpage\.action\?pageId=(\d+)",
    re.I,
)


def parse_jira_date(value: str | None) -> date | None:
    if not value or not str(value).strip():
        return None
    s = str(value).strip()[:10]
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def parse_defect_introduction_from_storage_html(html: str) -> date | None:
    if not html:
        return None
    m = re.search(
        r"(?is)Defect introduction time</p></td>\s*<td[^>]*>\s*<p[^>]*>(.*?)</p>",
        html,
    )
    if not m:
        m = re.search(
            r"(?is)Defect introduction time[^<]*</[^>]+>\s*<[^>]+>\s*([^<]+)",
            html,
        )
    if not m:
        m = re.search(
            r"(?is)Defect introduction time\s*</p>\s*</th>\s*<td[^>]*>\s*<p[^>]*>(.*?)</p>",
            html,
        )
    if not m:
        return None
    text = re.sub(r"\s+", " ", m.group(1).strip())
    if not text or re.match(r"(?i)^unknown\b", text):
        return None
    dm = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if dm:
        return parse_jira_date(dm.group(1))
    dm = re.search(
        r"(\d{4}-\d{2}-\d{2})\s+\d{1,2}:\d{2}\s*(?:AM|PM)?",
        text,
        re.I,
    )
    if dm:
        return parse_jira_date(dm.group(1))
    return None


def page_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    for m in CONFLUENCE_PAGE_RE.finditer(url):
        for g in m.groups():
            if g:
                return g
    return None


def extract_confluence_page_id(notes: str | None) -> str | None:
    if not notes:
        return None
    return page_id_from_url(notes) or _first_page_id_in_text(notes)


def _first_page_id_in_text(text: str) -> str | None:
    for m in CONFLUENCE_PAGE_RE.finditer(text):
        for g in m.groups():
            if g:
                return g
    return None


def extract_confluence_page_id_from_adf(node: Any) -> str | None:
    """Resolve Confluence page id from Jira Notes ADF (inlineCard, blockCard, links)."""
    if node is None:
        return None
    if isinstance(node, list):
        for child in node:
            found = extract_confluence_page_id_from_adf(child)
            if found:
                return found
        return None
    if isinstance(node, str):
        return _first_page_id_in_text(node)
    if not isinstance(node, dict):
        return None

    attrs = node.get("attrs") or {}
    for key in ("url", "href"):
        found = page_id_from_url(str(attrs.get(key) or ""))
        if found:
            return found

    kind = node.get("type")
    if kind == "text":
        for mark in node.get("marks") or []:
            if mark.get("type") == "link":
                found = page_id_from_url((mark.get("attrs") or {}).get("href", ""))
                if found:
                    return found

    if kind in ("inlineCard", "blockCard", "embedCard"):
        for key in ("url", "href"):
            found = page_id_from_url(str(attrs.get(key) or ""))
            if found:
                return found

    return extract_confluence_page_id_from_adf(node.get("content"))


def resolve_confluence_page_id(notes_raw: Any, notes_text: str | None = None) -> str | None:
    if isinstance(notes_raw, dict):
        found = extract_confluence_page_id_from_adf(notes_raw)
        if found:
            return found
    if notes_text:
        found = extract_confluence_page_id(notes_text)
        if found:
            return found
    if isinstance(notes_raw, str):
        return extract_confluence_page_id(notes_raw)
    return None


def days_between(start: date | None, end: date | None) -> int | None:
    if not start or not end:
        return None
    delta = (end - start).days
    return delta if delta >= 0 else None


def compute_metrics(issue: dict[str, Any]) -> dict[str, Any]:
    """Return metric fields to merge onto an issue dict."""
    start = parse_jira_date(issue.get("start_date_pick"))
    completion = parse_jira_date(issue.get("completion_date"))
    # MTTR close = End Date (customfield_10453) only — never Jira resolutiondate (adinc-jira-dates.md).
    end = parse_jira_date(issue.get("end_date"))
    defect = parse_jira_date(issue.get("defect_introduction_date"))

    mttr = days_between(start, end)
    mttm = days_between(start, completion)
    mttd = days_between(defect, start) if defect and start else None

    return {
        "mttr_days": mttr,
        "mttm_days": mttm,
        "mttd_days": mttd,
    }


def metrics_from_jira_fields(fields: dict[str, Any]) -> dict[str, str | None]:
    return {
        "start_date_pick": fields.get(START_DATE_PICK),
        "completion_date": fields.get(COMPLETION_DATE),
        "end_date": fields.get(END_DATE),
    }
