#!/usr/bin/env python3
"""Pre-publish guard: every incomplete milestone on the previous WFP must remain on the new WFP.

Catches accidental drops from daily-log fuzzy match, one-off patch scripts, or wrong dedup logic.
Exit 0 if OK, 1 if any prior incomplete task is missing from the new plan milestones section.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from parse_focus_plan import normalize_for_match, similar  # noqa: WPS433

from milestone_carryover import (  # noqa: WPS433
    block_plain_text,
    carryover_html_blocks,
    extract_milestones_bounds,
)


def _task_body_plain(chunk: str) -> str:
    import html as html_mod

    m = re.search(r"<ac:task-body>(.*?)</ac:task-body>", chunk, re.S)
    if not m:
        return ""
    t = re.sub(r"<[^>]+>", " ", m.group(1))
    return html_mod.unescape(re.sub(r"\s+", " ", t)).strip()


def _incomplete_task_texts_in_html_fragment(html: str) -> list[str]:
    """Incomplete task labels in a milestones inner fragment or merged tree block."""
    texts: list[str] = []
    for chunk in re.split(r"(?=<ac:task>)", html):
        if "<ac:task-status>incomplete</ac:task-status>" not in chunk:
            continue
        t = _task_body_plain(chunk)
        if t:
            texts.append(t)
    return texts


def _incomplete_task_texts_in_milestones(body: str) -> list[str]:
    """All plain-text labels for tasks still marked incomplete in milestones."""
    _, _, inner = extract_milestones_bounds(body)
    return _incomplete_task_texts_in_html_fragment(inner)


def _text_present(label: str, candidates: list[str], threshold: float = 0.88) -> bool:
    norm = normalize_for_match(label)
    if len(norm) < 8:
        return False
    for c in candidates:
        cn = normalize_for_match(c)
        if norm == cn:
            return True
        shorter, longer = (norm, cn) if len(norm) <= len(cn) else (cn, norm)
        if len(shorter) >= 20 and shorter in longer:
            return True
        if len(norm) >= 30 and similar(label, c, threshold=threshold):
            return True
    return False


MIN_CARRYOVER_LABEL_LEN = 12  # ignore link fragments / acronyms parsed as tasks


def validate_carryover(previous_body: str, new_body: str) -> list[str]:
    """Return human-readable errors; empty list means pass."""
    errors: list[str] = []
    prev_blocks = carryover_html_blocks(previous_body)
    new_incomplete = _incomplete_task_texts_in_milestones(new_body)

    for block in prev_blocks:
        parent = block_plain_text(block)
        for label in _incomplete_task_texts_in_html_fragment(block):
            if len(normalize_for_match(label)) < MIN_CARRYOVER_LABEL_LEN:
                continue
            if not _text_present(label, new_incomplete):
                hint = f" (parent: {parent[:60]}…)" if parent and label != parent else ""
                errors.append(f"Missing incomplete milestone from prior WFP: {label[:120]}{hint}")

    seen: set[str] = set()
    deduped: list[str] = []
    for e in errors:
        if e not in seen:
            deduped.append(e)
            seen.add(e)
    return deduped


def load_body(path: Path) -> str:
    raw = path.read_text(encoding="utf-8")
    if path.suffix == ".json":
        data = json.loads(raw)
        return data["body"]["storage"]["value"]
    return raw


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate WFP milestone carryover")
    parser.add_argument("--previous", required=True, type=Path, help="Prior WFP HTML or page JSON")
    parser.add_argument("--new", required=True, type=Path, help="New WFP HTML or page JSON")
    parser.add_argument("--json", action="store_true", help="Print JSON {ok, errors}")
    args = parser.parse_args()

    prev = load_body(args.previous)
    new = load_body(args.new)
    errors = validate_carryover(prev, new)

    if args.json:
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2, ensure_ascii=False))
    elif errors:
        print("WFP carryover validation FAILED:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
    else:
        print("WFP carryover validation OK")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
