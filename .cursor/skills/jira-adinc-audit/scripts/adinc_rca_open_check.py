"""Check 8 — RCA in Notes while ticket is not Done/Closed."""

from __future__ import annotations

from adinc_notes import is_rca_missing

RESOLVED_STATUSES = frozenset({"DONE", "CLOSED", "RESOLVED"})


def is_resolved_status(status: str | None) -> bool:
    return (status or "").strip().upper() in RESOLVED_STATUSES


def check_rca_while_open(status: str | None, notes: str | None) -> tuple[bool, str]:
    """
    Flag when General → Notes already contains substantive RCA but the ticket
    is not Done/Closed/Resolved (mirror of Check 4 scope).
    """
    if is_resolved_status(status):
        return False, "Ticket is Done/Closed/Resolved — not applicable"

    missing, _missing_comment = is_rca_missing(notes)
    if missing:
        return False, "Notes do not contain RCA yet"

    return True, (
        "Notes contain RCA but status is not Done/Closed — "
        "transition ticket when work is complete"
    )


def explain_rca_while_open(comments: str) -> str:
    if comments.startswith("Notes contain RCA"):
        return "RCA is documented in Notes but the ticket is still open — close or update status."
    return comments
