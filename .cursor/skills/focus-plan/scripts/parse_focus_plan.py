#!/usr/bin/env python3
"""Parse Fernando Rivero focus plan Confluence storage HTML into structured JSON.

Usage:
  python parse_focus_plan.py --input page.json [--output out.json]

Input: JSON from confluence_get_page (must include body.storage.value) or raw HTML file.
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
import uuid
from datetime import date
from pathlib import Path
from typing import Any


def strip_tags(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    return html.unescape(re.sub(r"\s+", " ", s)).strip()


def _split_top_level_blocks(list_inner: str) -> list[str]:
    """Split task-list inner HTML into alternating top-level task and task-list blocks."""
    blocks: list[str] = []
    pos = 0
    while pos < len(list_inner):
        task_start = list_inner.find("<ac:task>", pos)
        list_start = list_inner.find("<ac:task-list", pos)
        if task_start == -1 and list_start == -1:
            break
        if list_start != -1 and (task_start == -1 or list_start < task_start):
            m = re.match(r"<ac:task-list[^>]*>.*?</ac:task-list>", list_inner[list_start:], flags=re.S)
            if m:
                blocks.append(m.group(0))
                pos = list_start + len(m.group(0))
                continue
        if task_start == -1:
            break
        depth = 1
        i = task_start + len("<ac:task>")
        while i < len(list_inner) and depth:
            if list_inner.startswith("<ac:task>", i):
                depth += 1
                i += len("<ac:task>")
            elif list_inner.startswith("</ac:task>", i):
                depth -= 1
                i += len("</ac:task>")
            else:
                i += 1
        blocks.append(list_inner[task_start:i])
        pos = i
    return blocks


def parse_task_lists(section_html: str) -> list[dict[str, Any]]:
    """Parse ac:task-list blocks; merge task + immediately following sibling task-list as parent/children."""
    tasks: list[dict[str, Any]] = []
    for m in re.finditer(
        r"<ac:task-list[^>]*>(.*?)</ac:task-list>", section_html, flags=re.S
    ):
        blocks = _split_top_level_blocks(m.group(1))
        i = 0
        while i < len(blocks):
            block = blocks[i]
            if block.startswith("<ac:task>"):
                task = _parse_task(block)
                # Confluence often places child lists as the next sibling block
                if i + 1 < len(blocks) and blocks[i + 1].startswith("<ac:task-list"):
                    sibling_children = parse_task_lists(blocks[i + 1])
                    task["children"] = task.get("children", []) + sibling_children
                    i += 1
                tasks.append(task)
            i += 1
    return tasks


def _parse_task(task_xml: str) -> dict[str, Any]:
    status_m = re.search(r"<ac:task-status>([^<]+)</ac:task-status>", task_xml)
    status = (status_m.group(1) if status_m else "incomplete").strip()
    body_m = re.search(r"<ac:task-body>(.*?)</ac:task-body>", task_xml, flags=re.S)
    body_raw = body_m.group(1) if body_m else ""
    nested_lists = re.findall(
        r"(<ac:task-list[^>]*>.*?</ac:task-list>)", body_raw, flags=re.S
    )
    body_text = strip_tags(re.sub(r"<ac:task-list[^>]*>.*?</ac:task-list>", "", body_raw, flags=re.S))
    children: list[dict[str, Any]] = []
    for nl in nested_lists:
        children.extend(parse_task_lists(nl))
    return {
        "text": body_text,
        "status": status,
        "complete": status == "complete",
        "children": children,
        "raw_xml": task_xml,
    }


def task_tree_incomplete(task: dict[str, Any]) -> bool:
    if not task.get("complete"):
        return True
    return any(task_tree_incomplete(c) for c in task.get("children", []))


def carryover_milestones(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tasks to carry: incomplete top-level, or parent+children if any incomplete in tree."""
    carried: list[dict[str, Any]] = []
    for t in tasks:
        if task_tree_incomplete(t):
            carried.append(t)
    return carried


def completed_milestones(tasks: list[dict[str, Any]], prefix: str = "") -> list[str]:
    """Flat list of completed task labels (for accomplishments)."""
    done: list[str] = []
    for t in tasks:
        label = f"{prefix}{t['text']}" if prefix else t["text"]
        if t.get("complete") and not t.get("children"):
            done.append(label)
        elif t.get("complete") and t.get("children"):
            # Parent complete with no incomplete descendants — count parent only if all children done
            if not task_tree_incomplete(t):
                done.append(label)
            else:
                done.extend(completed_milestones(t["children"], prefix=f"{label} → "))
        else:
            done.extend(completed_milestones(t.get("children", []), prefix=f"{label} → "))
    return [d for d in done if d.strip()]


def parse_table_rows(table_html: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    trs = re.findall(r"<tr[^>]*>(.*?)</tr>", table_html, flags=re.S)
    if not trs:
        return rows
    headers = [strip_tags(c) for c in re.findall(r"<t[hd][^>]*>(.*?)</t[hd]>", trs[0], flags=re.S)]
    for tr in trs[1:]:
        cells = [strip_tags(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", tr, flags=re.S)]
        if not cells:
            continue
        row = {headers[i]: cells[i] if i < len(cells) else "" for i in range(len(headers))}
        if any(v for v in row.values()):
            rows.append(row)
    return rows


def extract_section(body: str, heading_pattern: str) -> str:
    """Extract HTML between a heading and the next h3 or end of macro."""
    m = re.search(
        rf"<h3[^>]*>.*?{heading_pattern}.*?</h3>(.*?)(?=<h3|<p local-id|<p><br|<hr|</ac:rich-text-body>|$)",
        body,
        flags=re.S | re.I,
    )
    return m.group(1) if m else ""


def normalize_for_match(text: str) -> str:
    t = text.lower()
    t = re.sub(r"[^a-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def similar(a: str, b: str, threshold: float = 0.72) -> bool:
    """Simple token overlap similarity."""
    ta = set(normalize_for_match(a).split())
    tb = set(normalize_for_match(b).split())
    if not ta or not tb:
        return False
    overlap = len(ta & tb) / min(len(ta), len(tb))
    return overlap >= threshold or normalize_for_match(a) in normalize_for_match(b) or normalize_for_match(b) in normalize_for_match(a)


def task_to_xml(task: dict[str, Any], task_id: int | None = None, plan_monday: date | None = None) -> tuple[str, int]:
    """Serialize one task; nested children use Confluence sibling ``<ac:task-list>`` pattern."""
    from confluence_dates import format_task_body_inner  # noqa: WPS433

    tid = task_id or abs(hash(task.get("text", ""))) % 9000 + 1000
    status = "complete" if task.get("complete") else "incomplete"
    tuuid = str(uuid.uuid4())
    ref_monday = plan_monday or task.get("plan_monday")
    if isinstance(ref_monday, str):
        ref_monday = date.fromisoformat(ref_monday)
    if task.get("body_html"):
        body_inner = task["body_html"]
    elif task.get("raw") or task.get("raw_markdown"):
        from confluence_dates import format_task_body_inner  # noqa: WPS433

        source = task.get("raw") or task.get("raw_markdown") or task.get("text", "")
        body_inner = format_task_body_inner(source, plan_monday=ref_monday)
    else:
        body_inner = format_task_body_inner(task.get("text", ""), plan_monday=ref_monday)
    parent = (
        f"<ac:task>"
        f"<ac:task-id>{tid}</ac:task-id>"
        f"<ac:task-uuid>{tuuid}</ac:task-uuid>"
        f"<ac:task-status>{status}</ac:task-status>"
        f"<ac:task-body>{body_inner}</ac:task-body>"
        f"</ac:task>"
    )
    next_id = tid + 1
    children = task.get("children") or []
    if not children:
        return parent, next_id
    child_parts: list[str] = []
    for child in children:
        cx, next_id = task_to_xml(child, next_id, plan_monday=ref_monday)
        child_parts.append(cx)
    sibling_list = (
        f'<ac:task-list ac:task-list-id="{uuid.uuid4().hex[:12]}">{"".join(child_parts)}</ac:task-list>'
    )
    return parent + sibling_list, next_id


def milestones_to_xml(tasks: list[dict[str, Any]]) -> str:
    parts: list[str] = []
    tid = 1000
    for t in tasks:
        x, tid = task_to_xml(t, tid)
        parts.append(x)
    return f'<ac:task-list ac:task-list-id="{uuid.uuid4().hex[:12]}">{"".join(parts)}</ac:task-list>'


def parse_focus_plan_body(body_html: str) -> dict[str, Any]:
    main_focus_m = re.search(
        r'<ac:parameter ac:name="title">MAIN FOCUS</ac:parameter>.*?<ac:rich-text-body>(.*?)</ac:rich-text-body>',
        body_html,
        flags=re.S,
    )
    main = main_focus_m.group(1) if main_focus_m else body_html

    milestones_section = extract_section(main, r"Milestones/Deliverables/Goals")
    milestones = parse_task_lists(milestones_section)

    personal_section = extract_section(main, r"Personal Goals")
    personal_tables = re.findall(r"<table[^>]*>.*?</table>", personal_section, flags=re.S)
    personal_goals = parse_table_rows(personal_tables[0]) if personal_tables else []

    team_section = extract_section(main, r"Team Goals I")
    team_tables = re.findall(r"<table[^>]*>.*?</table>", team_section, flags=re.S)
    team_goals = parse_table_rows(team_tables[0]) if team_tables else []

    def grab_list(section_key: str) -> list[str]:
        sec = extract_section(main, section_key) or ""
        items = parse_task_lists(sec)
        if items:
            return [t["text"] for t in items if t["text"]]
        lis = re.findall(r"<li[^>]*>(.*?)</li>", sec, flags=re.S)
        return [strip_tags(x) for x in lis if strip_tags(x)]

    accomplishments_section = extract_section(main, r"Accomplishments")
    acc_ol = re.findall(r"<li[^>]*>(.*?)</li>", accomplishments_section, flags=re.S)
    accomplishments = [strip_tags(x) for x in acc_ol if strip_tags(x)]

    return {
        "milestones": milestones,
        "milestones_carryover": carryover_milestones(milestones),
        "milestones_completed": completed_milestones(milestones),
        "personal_goals": personal_goals,
        "team_goals": team_goals,
        "touchpoints": grab_list(r"Touch-Points|Interfaces"),
        "escalations": grab_list(r"Potential Problems|Escalations"),
        "non_project": grab_list(r"Non-Project"),
        "one_on_one": grab_list(r"1:1|Comments/Thoughts"),
        "accomplishments_existing": accomplishments,
    }


def load_input(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(raw)
        if "body" in data and "storage" in data.get("body", {}):
            return data["body"]["storage"]["value"]
        if "body" in data:
            return data["body"]
    return raw


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse focus plan Confluence storage HTML")
    ap.add_argument("--input", required=True, help="Page JSON or HTML file")
    ap.add_argument("--output", help="Write JSON to file (default stdout)")
    args = ap.parse_args()
    body = load_input(Path(args.input))
    result = parse_focus_plan_body(body)
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
