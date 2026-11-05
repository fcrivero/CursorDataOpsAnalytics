"""Write SKRULL audit Excel workbook (Fernando template layout) from reports/*.json."""
from __future__ import annotations

import os
import shutil
import sys
from datetime import date, datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import openpyxl
from openpyxl.worksheet.worksheet import Worksheet

from audit_bundle import AuditBundle, default_excel_filename, gather_audit_bundle
from generate_report import (
    REPORTS,
    assignee_name,
    created_date,
    days_open,
)
from skrull_epic_suggest import format_suggestions_plaintext

SKILL_ROOT = SCRIPT_DIR.parent
TEMPLATE = SKILL_ROOT / "assets" / "SKRULL-AUDIT-template.xlsx"
JIRA_BROWSE = "https://deept.atlassian.net/browse/"


def _clear_data_rows(ws: Worksheet) -> None:
    if ws.max_row > 1:
        ws.delete_rows(2, ws.max_row - 1)


def _write_ticket_cell(ws: Worksheet, row: int, issue: dict) -> None:
    summary = issue.get("summary") or issue["key"]
    cell = ws.cell(row=row, column=1, value=summary)
    cell.hyperlink = f"{JIRA_BROWSE}{issue['key']}"
    cell.style = "Hyperlink"


def _created_value(issue: dict) -> date | None:
    _, d = created_date(issue.get("created"))
    return d


def _fill_standard_row(ws: Worksheet, row: int, issue: dict) -> None:
    _write_ticket_cell(ws, row, issue)
    ws.cell(row=row, column=2, value=assignee_name(issue.get("assignee")))
    created = _created_value(issue)
    ws.cell(row=row, column=3, value=created)
    ws.cell(row=row, column=4, value=issue.get("status") or "")


def fill_workbook(wb: openpyxl.Workbook, bundle: AuditBundle) -> None:
    # Check 2 — Missing Epic
    ws2 = wb["Missing Epic"]
    _clear_data_rows(ws2)
    row = 2
    for issue in bundle.c2_issues:
        _fill_standard_row(ws2, row, issue)
        sug = format_suggestions_plaintext(bundle.epic_suggestions(issue))
        ws2.cell(row=row, column=5, value=sug)
        row += 1

    # Check 3 — Missing story points
    ws3 = wb["Missing story points"]
    _clear_data_rows(ws3)
    row = 2
    for issue in bundle.c3_issues:
        _fill_standard_row(ws3, row, issue)
        row += 1

    # Check 4 — Open more than 8 days
    ws4 = wb["Open more than 8 days"]
    _clear_data_rows(ws4)
    row = 2
    for issue in bundle.c4_issues:
        _fill_standard_row(ws4, row, issue)
        n = days_open(issue.get("created"))
        ws4.cell(row=row, column=5, value=n if n is not None else "")
        row += 1

    # Check 5 — Blocked items
    ws5 = wb["Blocked items"]
    _clear_data_rows(ws5)
    row = 2
    for issue in bundle.c5_issues:
        _fill_standard_row(ws5, row, issue)
        row += 1

    # Optional Check 1 sheet when flagged (not in default template)
    if bundle.c1_issues:
        title = "Missing assignees"
        if title in wb.sheetnames:
            ws1 = wb[title]
            _clear_data_rows(ws1)
        else:
            ws1 = wb.create_sheet(title, 0)
            ws1.append(["Ticket", "Assignee", "Created", "Status"])
        row = 2
        for issue in bundle.c1_issues:
            _fill_standard_row(ws1, row, issue)
            row += 1


def resolve_output_path(explicit: str | None = None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("SKRULL_AUDIT_XLSX_DIR", "").strip()
    base = Path(env) if env else REPORTS
    base.mkdir(parents=True, exist_ok=True)
    return base / default_excel_filename()


def generate_excel(
    output_path: Path | None = None,
    *,
    template_path: Path = TEMPLATE,
    bundle: AuditBundle | None = None,
) -> Path:
    bundle = bundle or gather_audit_bundle()
    out = resolve_output_path(str(output_path) if output_path else None)

    if not template_path.is_file():
        raise FileNotFoundError(f"Excel template not found: {template_path}")

    shutil.copy(template_path, out)
    wb = openpyxl.load_workbook(out)
    fill_workbook(wb, bundle)
    wb.save(out)
    wb.close()
    return out


def main() -> None:
    out_arg = sys.argv[1] if len(sys.argv) > 1 else None
    path = generate_excel(Path(out_arg) if out_arg else None)
    print(str(path))


if __name__ == "__main__":
    main()
