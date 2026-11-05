"""Check 7 — Jira Priority must be P1 when MISSED_SLA=Y or INC_NUMBER is a real incident."""

from __future__ import annotations

NA_INC_VALUES = {"NA", "N/A", "N.A.", "NONE", "N/A."}
REQUIRED_PRIORITY = "P1"
# SNOW → Jira ADINC migration; INC_NUMBER→P1 applies only to tickets created after this date.
# Uses Jira `created` (import/native cohort), NOT Start DatePick — see adinc-jira-dates.md for open dates.
INC_P1_RULE_CUTOFF_DATE = "2026-05-30"


def is_real_inc_number(value: str | None) -> bool:
    if value is None or not str(value).strip():
        return False
    return str(value).strip().upper() not in NA_INC_VALUES


def is_missed_sla_y(found: dict[str, str]) -> bool:
    return (found.get("MISSED_SLA") or "").strip().upper() == "Y"


def normalize_jira_priority(priority: str | None) -> str:
    if priority is None:
        return ""
    if isinstance(priority, dict):
        return str(priority.get("name") or "").strip()
    return str(priority).strip()


def normalize_created_date(created: str | None) -> str:
    """Return YYYY-MM-DD from Jira created timestamp."""
    if not created:
        return ""
    return str(created).strip()[:10]


def inc_number_triggers_p1(created: str | None) -> bool:
    """
    Real INC_NUMBER requires P1 only for ADINC-native tickets created after the
    SNOW migration cutoff (strictly after 2026-05-30).
    """
    created_date = normalize_created_date(created)
    if not created_date:
        return False
    return created_date > INC_P1_RULE_CUTOFF_DATE


def requires_p1(found: dict[str, str], created: str | None = None) -> tuple[bool, list[str]]:
    triggers: list[str] = []
    if is_missed_sla_y(found):
        triggers.append("MISSED_SLA=Y")
    inc = (found.get("INC_NUMBER") or "").strip()
    if is_real_inc_number(inc) and inc_number_triggers_p1(created):
        triggers.append(f"INC_NUMBER={inc}")
    return bool(triggers), triggers


def check_jira_priority(
    found: dict[str, str],
    priority: str | None,
    created: str | None = None,
) -> tuple[bool, str]:
    """Return (flagged, comments). Uses description fields + Jira Priority field."""
    must_p1, triggers = requires_p1(found, created)
    if not must_p1:
        return False, "Priority rules not applicable"

    actual = normalize_jira_priority(priority) or "(empty)"
    if actual.upper() == REQUIRED_PRIORITY:
        return False, "Jira Priority=P1 (required)"

    trigger_text = "; ".join(triggers)
    return True, (
        f"Jira Priority must be {REQUIRED_PRIORITY} ({trigger_text}); "
        f"got {actual}"
    )


def explain_priority_failure(comments: str) -> str:
    if comments.startswith("Jira Priority must be P1"):
        return comments.replace("Jira Priority must be P1", "This ticket must be Jira Priority P1")
    return comments


def format_inc_for_output(inc_number: str | None, created: str | None = None) -> str:
    """Table cell: real ServiceNow INC includes (Customer Impacted) when P1 INC rule applies."""
    inc = (inc_number or "").strip()
    if not inc:
        return "—"
    if is_real_inc_number(inc):
        if inc_number_triggers_p1(created):
            return f"{inc} (Customer Impacted)"
        return f"{inc} (legacy SNOW migration — INC does not require P1)"
    return inc


def format_sla_missed_for_output(missed_sla: str | None) -> str:
    """Table cell: Y or N from description MISSED_SLA."""
    v = (missed_sla or "").strip().upper()
    if v in ("Y", "N"):
        return v
    return v if v else "—"
