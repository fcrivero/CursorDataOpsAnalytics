"""ADINC Notes (RCA) helpers — synced with adinc-jira-notes.md."""
from __future__ import annotations

import re

_URL_RE = re.compile(r"https?://[^\s\]|]+", re.IGNORECASE)
_SMART_LINK_RE = re.compile(r"\[[^\]]+\|[^\]]+\|smart-link\]", re.IGNORECASE)


def is_rca_missing(notes: str | None) -> tuple[bool, str]:
    """Return (flagged, comment). Confluence/URL links in Notes count as valid RCA."""
    if notes is None:
        return True, "Notes=Missing RCA (live MCP returned null)"
    s = str(notes).strip()
    if not s:
        return True, "Notes=Missing RCA"
    u = s.upper()
    if u in ("#N/A", "N/A", "NA"):
        return True, "Notes=Placeholder (#N/A)"
    if u in ("RCA:", "RCA"):
        return True, "Notes=Missing RCA (label only)"

    body = re.sub(r"^RCA\s*:\s*", "", s, flags=re.IGNORECASE).strip()
    if not body or body.upper() in ("#N/A", "N/A", "NA"):
        return True, "Notes=Missing RCA (label only)"

    if _URL_RE.search(body) or _SMART_LINK_RE.search(body):
        return False, ""

    if len(body) >= 10:
        return False, ""

    return True, "Notes=Missing RCA (label only)"
