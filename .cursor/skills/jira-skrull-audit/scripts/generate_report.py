"""Generate SKRULL audit markdown from per-check Jira MCP JSON files."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from skrull_epic_suggest import format_suggestions_markdown, suggest_epics

REPORTS = Path(__file__).resolve().parent.parent / "reports"
BASE = "https://deept.atlassian.net/browse/"
# More than 8 calendar days open → Days Open column shows 9+
CHECK4_MIN_DAYS_OPEN = 9


def audit_date() -> date:
    return datetime.now(timezone.utc).date()


def load_check(name: str) -> list[dict]:
    path = REPORTS / f"check_{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["issues"]


def load_check_file(name: str) -> dict:
    path = REPORTS / f"check_{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def load_epics() -> list[dict]:
    path = REPORTS / "open_epics.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["issues"]


def assignee_name(a) -> str:
    if not a:
        return "(Unassigned)"
    if isinstance(a, str):
        return a
    return a.get("displayName") or "(Unassigned)"


def created_date(created: str | None) -> tuple[str, date | None]:
    if not created:
        return "—", None
    dt = datetime.fromisoformat(created.replace("+0000", "+00:00"))
    return dt.date().isoformat(), dt.date()


def days_open(created: str | None) -> int | None:
    _, d = created_date(created)
    return (audit_date() - d).days if d else None


def check4_eligible(issue: dict) -> bool:
    n = days_open(issue.get("created"))
    return n is not None and n >= CHECK4_MIN_DAYS_OPEN


def sort_key(issue: dict) -> tuple:
    an = assignee_name(issue.get("assignee"))
    _, d = created_date(issue.get("created"))
    return ("" if an == "(Unassigned)" else an.lower(), d or date.max)


def link(issue: dict) -> str:
    s = (issue.get("summary") or issue["key"]).replace("|", "\\|")
    return f"[{s}]({BASE}{issue['key']})"


def table(
    cols: list[str],
    rows: list[dict],
    headers: list[str] | None = None,
) -> str:
    if not rows:
        return "_None._\n"
    hdr = headers or cols
    lines = ["| " + " | ".join(hdr) + " |", "| " + " | ".join("---" for _ in cols) + " |"]
    for r in rows:
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    return "\n".join(lines) + "\n"


def render_check2_only(fetched_at: str, scanned: int, c2_issues: list[dict], epics: list[dict]) -> str:
    out: list[str] = []
    out.append(f"**Jira fetched at:** {fetched_at}")
    out.append(
        "\n**Scope:** open SKRULL Stories and Tasks missing Epic Link (`\"Epic Link\" is EMPTY AND parent is EMPTY`)\n"
    )
    if not c2_issues:
        out.append("### Check 2 — Missing Epic (0)\n\n_None._\n")
        return "\n".join(out)
    out.append(f"### Check 2 — Missing Epic ({len(c2_issues)})\n")
    rows2 = []
    for i in c2_issues:
        sug = suggest_epics(i.get("summary") or "", i.get("description"), epics, limit=3)
        rows2.append(
            {
                "ticket": link(i),
                "assignee": assignee_name(i.get("assignee")),
                "created": created_date(i.get("created"))[0],
                "status": i.get("status") or "—",
                "suggested": format_suggestions_markdown(sug),
            }
        )
    out.append(table(["ticket", "assignee", "created", "status", "suggested"], rows2))
    return "\n".join(out)


def render_check3_only(fetched_at: str, c3_issues: list[dict], c3_scanned: int) -> str:
    out: list[str] = []
    out.append(f"**Jira fetched at:** {fetched_at}")
    out.append(
        "\n**Scope:** open SKRULL **Stories** only (`issuetype = Story`; Tasks and Sub-tasks excluded)\n"
    )
    if not c3_issues:
        out.append("### Check 3 — Missing story points (0)\n\n_None._\n")
        return "\n".join(out)
    out.append(f"### Check 3 — Missing story points ({len(c3_issues)})\n")
    rows = [
        {
            "ticket": link(i),
            "assignee": assignee_name(i.get("assignee")),
            "created": created_date(i.get("created"))[0],
            "status": i.get("status") or "—",
        }
        for i in c3_issues
    ]
    out.append(
        table(
            ["ticket", "assignee", "created", "status"],
            rows,
            ["Ticket", "Assignee", "Created", "Status"],
        )
    )
    out.append(f"\n_Scanned {c3_scanned} open Stories._\n")
    return "\n".join(out)


def render_check4_only(fetched_at: str, c4_issues: list[dict]) -> str:
    out: list[str] = []
    out.append(f"**Jira fetched at:** {fetched_at}")
    out.append(
        f"\n**Scope:** open SKRULL Stories and Tasks open **more than 8 days** "
        f"(Days Open >= {CHECK4_MIN_DAYS_OPEN}; JQL `created <= -{CHECK4_MIN_DAYS_OPEN}d`)\n"
    )
    if not c4_issues:
        out.append("### Check 4 — Open more than 8 days (0)\n\n_None._\n")
        return "\n".join(out)
    out.append(f"### Check 4 — Open more than 8 days ({len(c4_issues)})\n")
    rows = []
    for i in c4_issues:
        n = days_open(i.get("created"))
        rows.append(
            {
                "ticket": link(i),
                "assignee": assignee_name(i.get("assignee")),
                "created": created_date(i.get("created"))[0],
                "status": i.get("status") or "—",
                "days_open": n if n is not None else "—",
            }
        )
    out.append(
        table(
            ["ticket", "assignee", "created", "status", "days_open"],
            rows,
            ["Ticket", "Assignee", "Created", "Status", "Days Open"],
        )
    )
    return "\n".join(out)


def main() -> None:
    from audit_bundle import gather_audit_bundle

    argv = [a for a in sys.argv[1:] if a != "--no-excel"]
    write_excel = "--no-excel" not in sys.argv[1:]

    bundle = gather_audit_bundle()
    fetched_at = bundle.fetched_at
    scanned = bundle.scanned
    c1_issues = bundle.c1_issues
    c1_scanned = bundle.c1_scanned
    c2_issues = bundle.c2_issues
    c3_issues = bundle.c3_issues
    c3_scanned = bundle.c3_scanned
    c4_issues = bundle.c4_issues
    c5_issues = bundle.c5_issues
    epics = bundle.epics

    if argv and argv[0] in ("check2", "epic"):
        print(render_check2_only(fetched_at, scanned, c2_issues, epics))
        return

    if argv and argv[0] in ("check3", "points"):
        print(render_check3_only(fetched_at, c3_issues, c3_scanned))
        return

    if argv and argv[0] in ("check4", "open_week"):
        print(render_check4_only(fetched_at, c4_issues))
        return

    out: list[str] = []
    out.append("## SKRULL audit summary\n")
    out.append("| Check | Scanned | Flagged |")
    out.append("|-------|---------|---------|")
    out.append(f"| Missing assignees | {c1_scanned} | {len(c1_issues)} |")
    out.append(f"| Missing Epic | {scanned} | {len(c2_issues)} |")
    out.append(f"| Missing story points | {c3_scanned} | {len(c3_issues)} |")
    out.append(f"| Open > 8 days (9+ by created) | {scanned} | {len(c4_issues)} |")
    out.append(f"| Blocked | {scanned} | {len(c5_issues)} |")
    out.append(f"\n**Jira fetched at:** {fetched_at}")
    out.append(
        "\n**Scope:** open SKRULL Stories and Tasks (`status not in Done, Closed, Resolved, Cancelled`)\n"
    )

    if c1_issues:
        out.append(f"### Check 1 — Missing assignees ({len(c1_issues)})\n")
        rows = [
            {
                "ticket": link(i),
                "assignee": assignee_name(i.get("assignee")),
                "created": created_date(i.get("created"))[0],
                "status": i.get("status") or "—",
            }
            for i in c1_issues
        ]
        out.append(table(["ticket", "assignee", "created", "status"], rows))

    if c2_issues:
        out.append(f"### Check 2 — Missing Epic ({len(c2_issues)})\n")
        rows2 = []
        for i in c2_issues:
            sug = suggest_epics(i.get("summary") or "", i.get("description"), epics, limit=3)
            rows2.append(
                {
                    "ticket": link(i),
                    "assignee": assignee_name(i.get("assignee")),
                    "created": created_date(i.get("created"))[0],
                    "status": i.get("status") or "—",
                    "suggested": format_suggestions_markdown(sug),
                }
            )
        out.append(table(["ticket", "assignee", "created", "status", "suggested"], rows2))

    if c3_issues:
        out.append(f"### Check 3 — Missing story points ({len(c3_issues)})\n")
        rows = [
            {
                "ticket": link(i),
                "assignee": assignee_name(i.get("assignee")),
                "created": created_date(i.get("created"))[0],
                "status": i.get("status") or "—",
            }
            for i in c3_issues
        ]
        out.append(table(["ticket", "assignee", "created", "status"], rows))

    if c4_issues:
        out.append(f"### Check 4 — Open more than 8 days ({len(c4_issues)})\n")
        rows = []
        for i in c4_issues:
            n = days_open(i.get("created"))
            rows.append(
                {
                    "ticket": link(i),
                    "assignee": assignee_name(i.get("assignee")),
                    "created": created_date(i.get("created"))[0],
                    "status": i.get("status") or "—",
                    "days_open": n if n is not None else "—",
                }
            )
        out.append(
            table(
                ["ticket", "assignee", "created", "status", "days_open"],
                rows,
                ["Ticket", "Assignee", "Created", "Status", "Days Open"],
            )
        )

    if c5_issues:
        out.append(f"### Check 5 — Blocked items ({len(c5_issues)})\n")
        rows = [
            {
                "ticket": link(i),
                "assignee": assignee_name(i.get("assignee")),
                "created": created_date(i.get("created"))[0],
                "status": i.get("status") or "—",
            }
            for i in c5_issues
        ]
        out.append(table(["ticket", "assignee", "created", "status"], rows))

    text = "\n".join(out)
    print(text)

    if write_excel and not argv:
        from generate_excel import generate_excel

        xlsx_path = generate_excel(bundle=bundle)
        print(f"\n**Excel audit:** `{xlsx_path}`")


if __name__ == "__main__":
    main()
