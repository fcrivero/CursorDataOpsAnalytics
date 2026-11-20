"""Default SKRULL Fix Version and Affects Version for new **Epic** issues only (not Stories)."""
from __future__ import annotations

from datetime import date, datetime, timezone

# Update when fiscal-year Fix Version name changes (e.g. SKRULL.2028).
DEFAULT_FIX_VERSION = "SKRULL.2027"


def fiscal_quarter_affects_version(when: date | None = None) -> str:
    """
    Map a calendar date to SKRULL Affects Version {SKRULL.FY.Qn}.

    FY naming: Oct (calendar year Y) starts SKRULL.(Y+1).Q1 per project versions in Jira.
    """
    d = when or datetime.now(timezone.utc).date()
    m, y = d.month, d.year
    if m >= 10:
        fy = y + 1
        quarter = "Q1"
    elif m <= 3:
        fy = y
        quarter = "Q2"
    elif m <= 6:
        fy = y
        quarter = "Q3"
    else:
        fy = y
        quarter = "Q4"
    return f"SKRULL.{fy}.{quarter}"


def default_version_fields(
    when: date | None = None,
    *,
    fix_version: str | None = None,
    affects_version: str | None = None,
) -> dict:
    fix = fix_version or DEFAULT_FIX_VERSION
    affects = affects_version or fiscal_quarter_affects_version(when)
    return {
        "fixVersions": [{"name": fix}],
        "versions": [{"name": affects}],
    }


if __name__ == "__main__":
    dv = default_version_fields()
    print("fixVersions:", dv["fixVersions"][0]["name"])
    print("versions (Affects):", dv["versions"][0]["name"])