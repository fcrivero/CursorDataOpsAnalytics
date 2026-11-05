"""One-off audit report generator from saved Jira MCP JSON blobs."""
import json
import sys
from datetime import datetime, timezone, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skrull_epic_suggest import suggest_epics, format_suggestions_markdown

BASE = "https://deept.atlassian.net/browse/"
AUDIT_DATE = date(2026, 10, 22)
FETCHED_AT = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
AGENT = Path(r"C:\Users\rivef104\.cursor\projects\c-Users-rivef104-cursor-projects\agent-tools")


def load(name):
    return json.loads((AGENT / name).read_text(encoding="utf-8"))


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
    d = dt.date()
    return d.isoformat(), d


def days_open(created):
    _, d = created_date(created)
    if not d:
        return None
    return (AUDIT_DATE - d).days


def sort_rows(rows):
    def key(r):
        return (r["_assignee_sort"].lower(), r["_created_sort"] or date.max)

    return sorted(rows, key=key)


def link(issue):
    s = (issue.get("summary") or issue["key"]).replace("|", "\\|")
    return f"[{s}]({BASE}{issue['key']})"


def base_row(issue, comments):
    an = assignee_name(issue.get("assignee"))
    cd, d = created_date(issue.get("created"))
    return {
        "ticket": link(issue),
        "assignee": an,
        "created": cd,
        "status": issue.get("status") or "—",
        "comments": comments,
        "_assignee_sort": "(Unassigned)" if an == "(Unassigned)" else an,
        "_created_sort": d,
    }


def md_table(cols, rows):
    if not rows:
        return "_None._\n"
    hdr = "| " + " | ".join(cols) + " |"
    sep = "| " + " | ".join("---" for _ in cols) + " |"
    lines = [hdr, sep]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def main():
    population = load("d2d5fed7-9043-4635-97fc-f1082a0cc864.txt")["issues"]
    scanned = len(population)

    epics = load("epics.json") if (AGENT / "epics.json").exists() else []
    if not epics:
        epics = []  # filled below from inline

    # Inline epics from MCP (23 open)
    epics_data = json.loads(
        Path(__file__).resolve().parent.parent.joinpath("_epics_inline.json").read_text(encoding="utf-8")
    )
    epics = epics_data["issues"]

    assignee_issues = json.loads(
        Path(__file__).resolve().parent.parent.joinpath("_check_assignee.json").read_text(encoding="utf-8")
    )["issues"]
    points_issues = json.loads(
        Path(__file__).resolve().parent.parent.joinpath("_check_points.json").read_text(encoding="utf-8")
    )["issues"]
    week_issues = json.loads(
        Path(__file__).resolve().parent.parent.joinpath("_check_week.json").read_text(encoding="utf-8")
    )["issues"]
    blocked_issues = json.loads(
        Path(__file__).resolve().parent.parent.joinpath("_check_blocked.json").read_text(encoding="utf-8")
    )["issues"]
    epic_issues = json.loads(
        Path(__file__).resolve().parent.parent.joinpath("_check_epic.json").read_text(encoding="utf-8")
    )["issues"]

    c1 = sort_rows([base_row(i, "Assignee=Missing") for i in assignee_issues])
    c3 = sort_rows([base_row(i, "Story points=Missing") for i in points_issues])
    c4 = sort_rows(
        [
            base_row(i, f"Created={created_date(i.get('created'))[0]} ({days_open(i.get('created'))} days open)")
            for i in week_issues
            if days_open(i.get("created")) is not None and days_open(i.get("created")) >= 7
        ]
    )
    c5 = sort_rows([base_row(i, "Status=Blocked") for i in blocked_issues])

    c2 = []
    for i in epic_issues:
        sug = suggest_epics(i.get("summary") or "", i.get("description"), epics, limit=3)
        r = base_row(i, "Epic=Missing")
        r["suggested"] = format_suggestions_markdown(sug)
        if sug:
            r["comments"] += "; " + ", ".join(k for k, _, _ in sug)
        c2.append(r)
    c2 = sort_rows(c2)

    out = []
    out.append("## SKRULL audit summary\n")
    out.append("| Check | Scanned | Flagged |")
    out.append("|-------|---------|---------|")
    out.append(f"| Missing assignees | {scanned} | {len(c1)} |")
    out.append(f"| Missing Epic | {scanned} | {len(c2)} |")
    out.append(f"| Missing story points | {scanned} | {len(c3)} |")
    out.append(f"| Open > 7 days (by created) | {scanned} | {len(c4)} |")
    out.append(f"| Blocked | {scanned} | {len(c5)} |")
    out.append("")
    out.append(f"**Jira fetched at:** {FETCHED_AT}")
    out.append(
        "**Scope:** `project = SKRULL AND issuetype in (Story, Task) AND status not in (Done, Closed, Resolved, Cancelled)`"
    )
    out.append(
        "\n_Note: Population scan returned 100 issues (MCP page limit). Per-check JQL totals used for complete flagged lists where available._\n"
    )

    if c1:
        out.append(f"### Check 1 — Missing assignees ({len(c1)})\n")
        out.append(md_table(["ticket", "assignee", "created", "status", "comments"], c1))
    if c2:
        out.append(f"### Check 2 — Missing Epic ({len(c2)})\n")
        out.append(md_table(["ticket", "assignee", "created", "status", "suggested", "comments"], c2))
    if c3:
        out.append(f"### Check 3 — Missing story points ({len(c3)})\n")
        out.append(md_table(["ticket", "assignee", "created", "status", "comments"], c3))
    if c4:
        out.append(f"### Check 4 — Open longer than one week ({len(c4)})\n")
        out.append(md_table(["ticket", "assignee", "created", "status", "comments"], c4))
    if c5:
        out.append(f"### Check 5 — Blocked items ({len(c5)})\n")
        out.append(md_table(["ticket", "assignee", "created", "status", "comments"], c5))

    report = "\n".join(out)
    Path(__file__).resolve().parent.joinpath("_audit_report.md").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    main()
