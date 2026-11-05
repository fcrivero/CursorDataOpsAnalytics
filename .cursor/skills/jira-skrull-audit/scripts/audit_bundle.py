"""Load sorted SKRULL audit check results from reports/*.json (after live fetch)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from skrull_epic_suggest import suggest_epics

from generate_report import (
    REPORTS,
    check4_eligible,
    load_check,
    load_check_file,
    load_epics,
    sort_key,
)


@dataclass
class AuditBundle:
    fetched_at: str
    scanned: int
    c1_scanned: int
    c3_scanned: int
    c1_issues: list[dict]
    c2_issues: list[dict]
    c3_issues: list[dict]
    c4_issues: list[dict]
    c5_issues: list[dict]
    epics: list[dict]

    def epic_suggestions(self, issue: dict, limit: int = 3) -> list[tuple[str, str, float]]:
        return suggest_epics(
            issue.get("summary") or "",
            issue.get("description"),
            self.epics,
            limit=limit,
        )


def gather_audit_bundle() -> AuditBundle:
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    scanned_path = REPORTS / "population.json"
    scanned = (
        len(json.loads(scanned_path.read_text(encoding="utf-8"))["issues"])
        if scanned_path.exists()
        else 0
    )

    c1_file = load_check_file("assignee")
    c1_issues = sorted(c1_file["issues"], key=sort_key)
    c1_scanned = c1_file.get("scope_total") or scanned

    c3_file = load_check_file("points")
    c3_issues = sorted(c3_file["issues"], key=sort_key)
    c3_scanned = c3_file.get("scope_total") or scanned

    return AuditBundle(
        fetched_at=fetched_at,
        scanned=scanned,
        c1_scanned=c1_scanned,
        c3_scanned=c3_scanned,
        c1_issues=c1_issues,
        c2_issues=sorted(load_check("epic"), key=sort_key),
        c3_issues=c3_issues,
        c4_issues=sorted(
            [i for i in load_check("open_week") if check4_eligible(i)],
            key=sort_key,
        ),
        c5_issues=sorted(load_check("blocked"), key=sort_key),
        epics=load_epics(),
    )


def default_excel_filename(when: datetime | None = None) -> str:
    dt = when or datetime.now(timezone.utc)
    return f"{dt.strftime('%m%d%y')}-SKRULL AUDIT.xlsx"
