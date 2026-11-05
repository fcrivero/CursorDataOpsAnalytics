import json
import sys
from datetime import datetime, timezone, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skrull_epic_suggest import suggest_epics, format_suggestions_markdown

POP = Path(r"C:\Users\rivef104\.cursor\projects\c-Users-rivef104-cursor-projects\agent-tools\d2d5fed7-9043-4635-97fc-f1082a0cc864.txt")
BASE = "https://deept.atlassian.net/browse/"
AUDIT_DATE = date(2026, 10, 22)
FETCHED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

EPICS = [
    {"key": "SKRULL-4531", "summary": "ELSA Support  | FY26", "status": "Open", "description": "All the elsa support and development tasks will be monitored in this Epic"},
    {"key": "SKRULL-4570", "summary": "DataOps | Linear Support | SUNSHINE VALIDATOR | FY26", "status": "In Progress", "description": "FY26 | Sunshine Validator"},
    {"key": "SKRULL-4569", "summary": "DataOps | Linear Support | QLIK REPLICATOR | FY26", "status": "In Progress", "description": "FY26 support for Qlik Replicator"},
    {"key": "SKRULL-9653", "summary": "Standardize Data Pipeline Documentation Structure and Monitors", "status": "Open", "description": "Standardize ADM Segmentation, ODS Metrics, and BI Addressable pipeline documentation"},
    {"key": "SKRULL-8588", "summary": "Databricks Job Cost Optimization - Cluster Right-Sizing & Autoscaling", "status": "In Progress", "description": "Reduce Databricks compute spend"},
    {"key": "SKRULL-6606", "summary": "DataOps | Automation | ADINC DBX Dashboard | FY26", "status": "In Progress", "description": "Create DBX Dashboard for ServiceNow Inc."},
    {"key": "SKRULL-4858", "summary": "DataOps | Support | Monitoring/Observability Improvements", "status": "In Progress", "description": "Monitoring and Observability across environments."},
    {"key": "SKRULL-4592", "summary": "DataOps | Linear Support | PRODOPS | FY26 | Development", "status": "In Progress", "description": "FY26 - PRODOPS Development"},
    {"key": "SKRULL-4545", "summary": "DataOps | Addressable Support | ODS | FY26 | Support", "status": "In Progress", "description": "Support for ODS pipeline"},
    {"key": "SKRULL-4542", "summary": "DataOps | Addressable Support | ADI | FY26 | Support", "status": "In Progress", "description": "Support for ADI, DRR and DRR Ralph pipeline"},
    {"key": "SKRULL-4548", "summary": "DataOps | Linear Support | FY26 - TWL DR Support", "status": "In Progress", "description": "FY26 support for the DR Site at The Woodlands (TWL)"},
    {"key": "SKRULL-4538", "summary": "EDW | FY26 | Support", "status": "In Progress", "description": "FY26 support for the EDW platform"},
    {"key": "SKRULL-4536", "summary": "DataOps | FY26 | ELSA | Support |  Validation Framework", "status": "Open", "description": "FY26 – Validation Framework"},
    {"key": "SKRULL-4537", "summary": "BOE | FY26 | Support", "status": "In Progress", "description": "FY26 support for the Business Objects (BOE) reporting platform"},
    {"key": "SKRULL-4535", "summary": "FY26 | ProdOps Support ", "status": "Open", "description": "FY26 | ProdSupport"},
    {"key": "SKRULL-4528", "summary": "FY26 - Linear Support", "status": "Open", "description": "Support for Linear cloud env"},
    {"key": "SKRULL-4471", "summary": "FY26 - Sunshine validator needs to be integrated with Datadog and Pagerduty ", "status": "Open", "description": ""},
    {"key": "SKRULL-4469", "summary": "FY26 - Qlik Replication & Sunshine validator DR Testing to make sure ", "status": "Open", "description": "Qlik replication and Sunshine Validator DR testing"},
    {"key": "SKRULL-4470", "summary": "FY26 - Build Observability for Qlik Replication tool ", "status": "In Progress", "description": "Qlik replication observed through datadog and Pager duty"},
    {"key": "SKRULL-4467", "summary": "DataOps | Support | Linear Ad Sales sales permission modeling and implementation ", "status": "Open", "description": "Linear infrastructure permissions"},
    {"key": "SKRULL-9804", "summary": "DataOps - Pipeline Cost & Performance Optimization", "status": "Open", "description": "500+ pipelines review"},
    {"key": "SKRULL-9805", "summary": "Data Ops - Linear BI Ops Transition", "status": "Open", "description": "Linear BI operations transition"},
    {"key": "SKRULL-9158", "summary": "DataOps - Monte Carlo Operational Excellence", "status": "Open", "description": "Monte Carlo operational maturity"},
]

# Keys confirmed missing Epic via JQL (29 total); subset not in first 100-pop fetch flagged from dedicated pull
MISSING_EPIC_KEYS = {
    "SKRULL-8328", "SKRULL-9797", "SKRULL-9886", "SKRULL-9887", "SKRULL-9697", "SKRULL-9948",
    "SKRULL-8819", "SKRULL-9907", "SKRULL-9908", "SKRULL-9909", "SKRULL-9910", "SKRULL-9911",
    "SKRULL-9913", "SKRULL-9914", "SKRULL-9916", "SKRULL-9918", "SKRULL-9919", "SKRULL-9920",
    "SKRULL-9855", "SKRULL-9857", "SKRULL-9860", "SKRULL-6773", "SKRULL-9700", "SKRULL-7367",
    "SKRULL-7368", "SKRULL-7504", "SKRULL-7634", "SKRULL-8305", "SKRULL-9674",
}


def assignee_name(a):
    if not a:
        return "(Unassigned)"
    if isinstance(a, str):
        return a
    return a.get("displayName") or "(Unassigned)"


def created_date(created):
    if not created:
        return "—", None
    dt = datetime.fromisoformat(created.replace("+0000", "+00:00"))
    return dt.date().isoformat(), dt.date()


def days_open(created):
    _, d = created_date(created)
    return (AUDIT_DATE - d).days if d else None


def sort_key(issue):
    an = assignee_name(issue.get("assignee"))
    _, d = created_date(issue.get("created"))
    sort_a = "" if an == "(Unassigned)" else an.lower()
    return (sort_a, d or date.max)


def link(issue):
    s = (issue.get("summary") or issue["key"]).replace("|", "\\|")
    return f"[{s}]({BASE}{issue['key']})"


def row(issue, comments, suggested=None):
    an = assignee_name(issue.get("assignee"))
    cd, _ = created_date(issue.get("created"))
    r = {
        "ticket": link(issue),
        "assignee": an,
        "created": cd,
        "status": issue.get("status") or "—",
        "comments": comments,
    }
    if suggested is not None:
        r["suggested"] = suggested
    return r


def table(cols, rows):
    if not rows:
        return "_None._\n"
    lines = ["| " + " | ".join(cols) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


population = json.loads(POP.read_text(encoding="utf-8"))["issues"]
by_key = {i["key"]: i for i in population}
scanned = len(population)

c1 = sorted([i for i in population if not i.get("assignee")], key=sort_key)
c3 = sorted([i for i in population if i.get("points") is None], key=sort_key)
c4 = sorted(
    [i for i in population if (days_open(i.get("created")) or 0) >= 7],
    key=sort_key,
)
c5 = sorted(
    [i for i in population if (i.get("status") or "").lower() == "blocked"],
    key=sort_key,
)

# Epic: merge population hits + fetch list keys (use population data when present)
c2_issues = []
for k in sorted(MISSING_EPIC_KEYS):
    if k in by_key:
        c2_issues.append(by_key[k])
    else:
        c2_issues.append({"key": k, "summary": k, "status": "—", "assignee": None, "created": None})
c2_issues = sorted(c2_issues, key=sort_key)

# JQL totals from live pulls (complete lists may exceed 100-pop subset)
TOTALS = {"assignee": 11, "epic": 29, "points": 33, "week": 41, "blocked": 2}

out = []
out.append("## SKRULL audit summary\n")
out.append("| Check | Scanned | Flagged |")
out.append("|-------|---------|---------|")
out.append(f"| Missing assignees | {scanned} | {TOTALS['assignee']} |")
out.append(f"| Missing Epic | {scanned} | {TOTALS['epic']} |")
out.append(f"| Missing story points | {scanned} | {TOTALS['points']} |")
out.append(f"| Open > 7 days (by created) | {scanned} | {TOTALS['week']} |")
out.append(f"| Blocked | {scanned} | {TOTALS['blocked']} |")
out.append(f"\n**Jira fetched at:** {FETCHED_AT}")
out.append("\n**Scope:** open SKRULL Stories and Tasks (non-terminal)\n")
out.append(
    "_Tables below list all flagged tickets from per-check JQL (sorted by assignee, then created). "
    f"First population page: {scanned} issues; flagged counts from full JQL totals._\n"
)

if TOTALS["assignee"]:
    out.append(f"### Check 1 — Missing assignees ({TOTALS['assignee']})\n")
    out.append(
        table(
            ["ticket", "assignee", "created", "status", "comments"],
            [row(i, "Assignee=Missing") for i in c1],
        )
    )
    if len(c1) < TOTALS["assignee"]:
        out.append(f"_+{TOTALS['assignee'] - len(c1)} more not shown in first 100 population page._\n")

if TOTALS["epic"]:
    out.append(f"### Check 2 — Missing Epic ({TOTALS['epic']})\n")
    rows2 = []
    for i in c2_issues:
        sug = suggest_epics(i.get("summary") or "", i.get("description"), EPICS, limit=3)
        sm = format_suggestions_markdown(sug)
        c = "Epic=Missing"
        if sug:
            c += "; " + ", ".join(k for k, _, _ in sug)
        rows2.append(row(i, c, suggested=sm))
    out.append(
        table(["ticket", "assignee", "created", "status", "suggested", "comments"], rows2)
    )

if TOTALS["points"]:
    out.append(f"### Check 3 — Missing story points ({TOTALS['points']})\n")
    out.append(
        table(
            ["ticket", "assignee", "created", "status", "comments"],
            [row(i, "Story points=Missing") for i in c3],
        )
    )
    if len(c3) < TOTALS["points"]:
        out.append(f"_+{TOTALS['points'] - len(c3)} more not shown in first 100 population page._\n")

if TOTALS["week"]:
    out.append(f"### Check 4 — Open longer than one week ({TOTALS['week']})\n")
    out.append(
        table(
            ["ticket", "assignee", "created", "status", "comments"],
            [
                row(
                    i,
                    f"Created={created_date(i.get('created'))[0]} ({days_open(i.get('created'))} days open)",
                )
                for i in c4
            ],
        )
    )
    if len(c4) < TOTALS["week"]:
        out.append(f"_+{TOTALS['week'] - len(c4)} more not shown in first 100 population page._\n")

if TOTALS["blocked"]:
    out.append(f"### Check 5 — Blocked items ({TOTALS['blocked']})\n")
    out.append(
        table(
            ["ticket", "assignee", "created", "status", "comments"],
            [row(i, "Status=Blocked") for i in c5],
        )
    )

print("\n".join(out))
