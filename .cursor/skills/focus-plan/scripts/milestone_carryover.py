#!/usr/bin/env python3
"""Milestone carryover with nested task-tree preservation for Confluence focus plans.

Confluence stores child tasks as a sibling ``<ac:task-list>`` immediately after the
parent ``<ac:task>`` (not inside ``<ac:task-body>``). When extracting or rebuilding
the milestones list, always use balanced tag matching — never ``find('</ac:task-list>')``
on the first match, or nested lists truncate and flatten the tree.
"""

from __future__ import annotations

import re
import uuid
from datetime import date
from typing import Any

MILESTONES_LIST_MARKER = '<ac:task-list ac:task-list-id="04923dc9f0c9">'


def find_task_list_close(html: str, open_start: int) -> int:
    """Return index *after* the closing ``</ac:task-list>`` for the list at *open_start*."""
    pos = html.find(">", open_start)
    if pos == -1:
        raise ValueError("malformed ac:task-list opening tag")
    pos += 1
    depth = 1
    while pos < len(html) and depth > 0:
        next_open = html.find("<ac:task-list", pos)
        next_close = html.find("</ac:task-list>", pos)
        if next_close == -1:
            raise ValueError("unclosed ac:task-list")
        if next_open != -1 and next_open < next_close:
            depth += 1
            pos = html.find(">", next_open) + 1
        else:
            depth -= 1
            if depth == 0:
                return next_close + len("</ac:task-list>")
            pos = next_close + len("</ac:task-list>")
    raise ValueError("unclosed ac:task-list")


def extract_milestones_bounds(body: str) -> tuple[int, int, str]:
    """Return (list_start, list_end, inner_html) for the milestones task-list."""
    start = body.find(MILESTONES_LIST_MARKER)
    if start == -1:
        raise ValueError("milestones task-list not found")
    end = find_task_list_close(body, start)
    inner = body[start + len(MILESTONES_LIST_MARKER) : end - len("</ac:task-list>")]
    return start, end, inner


def split_top_level_blocks(list_inner: str) -> list[str]:
    blocks: list[str] = []
    pos = 0
    while pos < len(list_inner):
        task_start = list_inner.find("<ac:task>", pos)
        list_start = list_inner.find("<ac:task-list", pos)
        if task_start == -1 and list_start == -1:
            break
        if list_start != -1 and (task_start == -1 or list_start < task_start):
            close = find_task_list_close(list_inner, list_start)
            blocks.append(list_inner[list_start:close])
            pos = close
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


def merge_task_with_following_list(blocks: list[str]) -> list[str]:
    """Merge ``<ac:task>`` + immediate sibling ``<ac:task-list>`` into one tree block."""
    merged: list[str] = []
    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b.startswith("<ac:task>") and i + 1 < len(blocks) and blocks[i + 1].startswith("<ac:task-list"):
            merged.append(b + blocks[i + 1])
            i += 2
        else:
            merged.append(b)
            i += 1
    return merged


def is_fully_complete_block(block: str) -> bool:
    """True when block has no incomplete tasks (safe to drop)."""
    return "incomplete" not in block


def block_plain_text(block: str) -> str:
    """Extract readable text from a milestone task block."""
    import html as html_mod

    m = re.search(r"<ac:task-body>(.*?)</ac:task-body>", block, re.S)
    if not m:
        return ""
    t = re.sub(r"<[^>]+>", " ", m.group(1))
    return html_mod.unescape(re.sub(r"\s+", " ", t)).strip()


def completed_block_texts_from_html(body: str) -> list[str]:
    """All fully-complete milestone tree texts from a plan (HTML-accurate).

    Use this instead of parser ``milestones_completed`` when daily-log items were
    appended after the main list — the parser may miss them.
    """
    _, _, inner = extract_milestones_bounds(body)
    blocks = merge_task_with_following_list(split_top_level_blocks(inner))
    texts: list[str] = []
    for block in blocks:
        if block.startswith("<ac:task>") and is_fully_complete_block(block):
            t = block_plain_text(block)
            if t:
                texts.append(t)
    return texts


def prune_complete_blocks(body: str) -> tuple[str, list[str]]:
    """Remove fully-complete milestone blocks; return (new_body, dropped labels)."""
    _, _, inner = extract_milestones_bounds(body)
    blocks = merge_task_with_following_list(split_top_level_blocks(inner))
    kept: list[str] = []
    dropped: list[str] = []

    for block in blocks:
        if block.startswith("<ac:task>") and is_fully_complete_block(block):
            t = block_plain_text(block)
            if t:
                dropped.append(t)
            continue
        kept.append(block)

    new_body = replace_milestones_task_list(body, "\n" + "\n".join(kept) + "\n")
    return new_body, dropped


def accomplishments_texts_from_html(body: str) -> list[str]:
    """Plain-text lines from the previous plan's Accomplishments last week section."""
    import html as html_mod

    from parse_focus_plan import strip_tags  # noqa: WPS433

    m = re.search(r"Accomplishments.*?<ol[^>]*>(.*?)</ol>", body, flags=re.S | re.I)
    if not m:
        return []
    texts: list[str] = []
    for li in re.findall(r"<li[^>]*>(.*?)</li>", m.group(1), flags=re.S):
        t = strip_tags(li)
        t = html_mod.unescape(re.sub(r"\s+", " ", t)).strip()
        if t and t.lower() != "none":
            texts.append(t)
    return texts


def matches_prior_completed(text: str, completed_texts: list[str]) -> bool:
    """True if *text* matches a completed milestone from the previous plan."""
    from confluence_links import BARE_TICKET_RE  # noqa: WPS433
    from parse_focus_plan import normalize_for_match, similar  # noqa: WPS433

    norm = normalize_for_match(text)
    text_tickets = {m.group(0).upper() for m in BARE_TICKET_RE.finditer(text)}
    for c in completed_texts:
        if text_tickets:
            c_tickets = {m.group(0).upper() for m in BARE_TICKET_RE.finditer(c)}
            if text_tickets & c_tickets:
                return True
    if len(norm) < 15:
        return False
    for c in completed_texts:
        cn = normalize_for_match(c)
        if norm == cn:
            return True
        # Substring match only when the shared span is substantial
        shorter, longer = (norm, cn) if len(norm) <= len(cn) else (cn, norm)
        if len(shorter) >= 25 and shorter in longer:
            return True
        # High-confidence similarity for long, distinctive lines only
        if len(norm) >= 45 and similar(text, c, threshold=0.88):
            return True
    return False


def matches_prior_done(text: str, prior_plan_body: str) -> bool:
    """True if *text* was already done on the previous plan (milestone or accomplishment)."""
    completed = completed_block_texts_from_html(prior_plan_body)
    accomplishments = accomplishments_texts_from_html(prior_plan_body)
    return matches_prior_completed(text, completed) or matches_prior_completed(text, accomplishments)


def remove_blocks_matching_completed(body: str, completed_texts: list[str]) -> tuple[str, list[str]]:
    """Drop milestone blocks whose text matches prior-plan completions (re-add guard)."""
    _, _, inner = extract_milestones_bounds(body)
    blocks = merge_task_with_following_list(split_top_level_blocks(inner))
    kept: list[str] = []
    dropped: list[str] = []

    for block in blocks:
        if block.startswith("<ac:task>"):
            # Never drop a tree that still has open subtasks — daily-log "done" lines
            # often refer to a follow-up umbrella, not every nested WFP item.
            if not is_fully_complete_block(block):
                kept.append(block)
                continue
            t = block_plain_text(block)
            if t and matches_prior_completed(t, completed_texts):
                dropped.append(t)
                continue
        kept.append(block)

    new_body = replace_milestones_task_list(body, "\n" + "\n".join(kept) + "\n")
    return new_body, dropped


def carryover_html_blocks(body: str) -> list[str]:
    """Return milestone tree blocks to carry: incomplete trees with nesting preserved."""
    _, _, inner = extract_milestones_bounds(body)
    blocks = merge_task_with_following_list(split_top_level_blocks(inner))
    return [b for b in blocks if b.startswith("<ac:task>") and not is_fully_complete_block(b)]


def filter_carried_blocks_by_daily_done(
    blocks: list[str],
    done_items: list[dict[str, Any]],
) -> tuple[list[str], list[str]]:
    """Drop a carried block only if the whole tree is complete AND it matches a done daily-log line.

    Never drop when ``is_fully_complete_block`` is false — open nested subtasks must always carry.
    """
    kept: list[str] = []
    dropped: list[str] = []
    for block in blocks:
        if not is_fully_complete_block(block):
            kept.append(block)
            continue
        text = block_plain_text(block)
        if text and any(matches_prior_completed(text, [d.get("text", "")]) for d in done_items):
            dropped.append(text)
            continue
        kept.append(block)
    return kept, dropped


def replace_milestones_task_list(body: str, new_inner: str) -> str:
    """Replace milestones list content while preserving the outer list wrapper."""
    start, end, _ = extract_milestones_bounds(body)
    return body[: start + len(MILESTONES_LIST_MARKER)] + new_inner + body[end - len("</ac:task-list>") : end] + body[end:]


def task_tree_to_html(task: dict[str, Any], use_raw: bool = True) -> str:
    """Serialize a parsed task tree using Confluence sibling-list nesting."""
    children = task.get("children") or []
    if use_raw and task.get("raw_xml"):
        parent = task["raw_xml"]
    else:
        parent = _single_task_xml(task)

    if not children:
        return parent

    child_parts: list[str] = []
    for child in children:
        # Children are leaves or subtrees; never double-wrap sibling lists
        if child.get("children"):
            child_parts.append(task_tree_to_html(child, use_raw=use_raw))
        elif use_raw and child.get("raw_xml"):
            child_parts.append(child["raw_xml"])
        else:
            child_parts.append(_single_task_xml(child))

    list_id = uuid.uuid4().hex[:12]
    sibling_list = f'<ac:task-list ac:task-list-id="{list_id}">{"".join(child_parts)}</ac:task-list>'
    return parent + sibling_list


def _single_task_xml(task: dict[str, Any]) -> str:
    import html as html_mod

    tid = abs(hash(task.get("text", ""))) % 9000 + 1000
    status = "complete" if task.get("complete") else "incomplete"
    tuuid = str(uuid.uuid4())
    body_inner = task.get("body_html") or html_mod.escape(task.get("text", ""))
    return (
        f"<ac:task>"
        f"<ac:task-id>{tid}</ac:task-id>"
        f"<ac:task-uuid>{tuuid}</ac:task-uuid>"
        f"<ac:task-status>{status}</ac:task-status>"
        f"<ac:task-body>{body_inner}</ac:task-body>"
        f"</ac:task>"
    )


def carryover_from_parsed(carried_tasks: list[dict[str, Any]]) -> str:
    """Build inner HTML for carried milestone trees from parser output."""
    return "\n".join(task_tree_to_html(t) for t in carried_tasks)


def rebuild_milestones_html(
    body: str,
    carried_blocks: list[str] | None = None,
    carried_tasks: list[dict[str, Any]] | None = None,
    new_task_xml_parts: list[str] | None = None,
    plan_monday: date | None = None,
) -> str:
    """Replace milestones section. Provide *carried_blocks* (raw HTML) OR *carried_tasks* (parsed)."""
    from confluence_dates import roll_carried_dates  # noqa: WPS433

    if carried_blocks is None and carried_tasks is not None:
        carried_blocks = [task_tree_to_html(t) for t in carried_tasks]
    if carried_blocks is None:
        carried_blocks = []

    parts = list(carried_blocks)
    if plan_monday:
        parts = [roll_carried_dates(b, plan_monday) for b in parts]
    if new_task_xml_parts:
        parts.extend(new_task_xml_parts)

    return replace_milestones_task_list(body, "\n" + "\n".join(parts) + "\n")
