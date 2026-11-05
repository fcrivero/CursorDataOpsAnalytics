#!/usr/bin/env python3
"""Parse pending items from the latest Oncall activity log agent transcript.

Locates agent-transcripts containing ``Oncall log —`` or ``Open items`` /
``Pending items`` tables, extracts open follow-ups with links, and formats
compact milestone markdown (1–2 lines).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from confluence_links import plain_text_for_dedup

ONCALL_PARENT_TITLE = "Follow up with open Oncall items"

TRANSCRIPT_ROOT = Path(
    r"C:\Users\rivef104\.cursor\projects\c-Users-rivef104-cursor-projects\agent-transcripts"
)

CLOSED_MARKERS = (
    "none — **closed**",
    "none — closed",
    "no further action",
    "closed from your end",
)

SKIP_NEXT_ACTION = re.compile(
    r"^(none\s*[—-]\s*\*?\*?closed|no further action|closed from your end)",
    re.I,
)


@dataclass
class OncallItem:
    day: str
    name: str
    next_action: str
    links: list[dict[str, str]] = field(default_factory=list)
    raw_markdown: str = ""
    text: str = ""  # plain for dedup

    def to_dict(self) -> dict:
        return {
            "day": self.day,
            "name": self.name,
            "next_action": self.next_action,
            "links": self.links,
            "raw": self.raw_markdown,
            "text": self.text,
        }


def find_oncall_transcripts(root: Path) -> list[Path]:
    """Return transcript jsonl files that look like Oncall activity logs."""
    candidates: list[Path] = []
    if not root.exists():
        return candidates
    for p in root.rglob("*.jsonl"):
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:8000]
        except OSError:
            continue
        if "Oncall log" in head or "Pending items" in head or "Open items" in head:
            candidates.append(p)
    return sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True)


def _extract_assistant_texts(jsonl_path: Path) -> list[str]:
    texts: list[str] = []
    for line in jsonl_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("role") != "assistant":
            continue
        msg = obj.get("message", {})
        content = msg.get("content", [])
        if isinstance(content, str):
            texts.append(content)
            continue
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                texts.append(block.get("text", ""))
    return texts


def _latest_open_items_block(texts: list[str]) -> str | None:
    """Return the last assistant message that looks like an open-items snapshot."""
    patterns = (
        re.compile(r"## Open items\b", re.I),
        re.compile(r"## Pending items remaining", re.I),
        re.compile(r"## Pending items — full detail", re.I),
        re.compile(r"\*\*3 open in log\*\*", re.I),
    )
    for text in reversed(texts):
        if any(p.search(text) for p in patterns):
            return text
    # Fallback: last Oncall log snapshot with summary table
    for text in reversed(texts):
        if "| Day | Name | Next action |" in text and "Quick summary" in text:
            return text
    return None


def _parse_summary_table(block: str) -> list[tuple[str, str, str]]:
    """Parse | Day | Name | Next action | rows (optional 4th Live status column)."""
    rows: list[tuple[str, str, str]] = []
    in_table = False
    for line in block.splitlines():
        if re.match(r"^\|\s*Day\s*\|\s*Name\s*\|\s*Next action", line, re.I):
            in_table = True
            continue
        if not in_table:
            continue
        if not line.strip().startswith("|"):
            if rows:
                break
            continue
        if re.match(r"^\|\s*[-:]+\s*\|", line):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 3:
            continue
        day, name, nxt = cells[0], cells[1], cells[2]
        if day.lower() in ("day", "---"):
            continue
        rows.append((day, name, nxt))
    return rows


def _extract_links(text: str) -> list[dict[str, str]]:
    links: list[dict[str, str]] = []
    seen: set[str] = set()
    for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
        url = m.group(2)
        if url in seen:
            continue
        seen.add(url)
        links.append({"label": m.group(1), "url": url})
    return links


def _normalize_key(text: str) -> str:
    t = re.sub(r"\*\*|`|~~", "", text).lower()
    return re.sub(r"\s+", " ", t).strip()


def _parse_detail_sections(block: str) -> dict[str, str]:
    """Map ### section headings in an Open items block to their body text."""
    sections: dict[str, str] = {}
    for m in re.finditer(r"^### (.+)$", block, re.M):
        heading = m.group(1).strip()
        start = m.end()
        nxt = re.search(r"^---\s*$|^### ", block[start:], re.M)
        end = start + (nxt.start() if nxt else len(block) - start)
        sections[_normalize_key(heading)] = block[start:end]
    return sections


def _match_section(name: str, sections: dict[str, str]) -> str:
    """Find the best ### detail section for a summary-table *name*."""
    short = _short_title(name).lower()
    best_key = ""
    best_score = 0
    tokens = [t for t in re.split(r"[\s|—–\-/]+", short) if len(t) > 2]
    for key in sections:
        score = sum(1 for t in tokens if t in key)
        if "sne_identity" in short and "sne_identity" in key:
            score += 5
        if "ldb" in short and "ldb" in key and "delivery" in key:
            score += 5
        if "rptng" in short and ("rptng" in key or "user_suspended" in key):
            score += 5
        if score > best_score:
            best_score = score
            best_key = key
    return sections.get(best_key, "") if best_key else ""


def _find_item_detail_block(full_transcript: str, name: str, open_block: str = "") -> str:
    """Find the ### section for *name* (prefer sections inside *open_block*)."""
    if open_block:
        sec = _match_section(name, _parse_detail_sections(open_block))
        if sec:
            return sec
    tokens = [t for t in re.split(r"[\s\[\]|—–-]+", _short_title(name).lower()) if len(t) > 3]
    best = ""
    for m in re.finditer(r"### (.+?)\n", full_transcript):
        heading = m.group(1)
        hl = heading.lower()
        if any(t in hl for t in tokens[:3]):
            start = m.start()
            nxt = full_transcript.find("\n---", start + 1)
            best = full_transcript[start : nxt if nxt != -1 else start + 4000]
    return best


def _short_title(name: str) -> str:
    """Prefer compact table name; strip markdown bold."""
    name = re.sub(r"\*\*", "", name).strip()
    # Use table shorthand when present
    if "sne_identity" in name.lower():
        return "sne_identity Long Run"
    if "ldb" in name.lower() and "delivery" in name.lower():
        return "LDB agg up delivery context"
    if "rptng_fact_dr_sls_ordr" in name.lower() or "user_suspended" in name.lower():
        return "RPTNG_FACT_DR_SLS_ORDR — USER_SUSPENDED"
    # Long [AP][...] titles → keep but trim backticks
    return re.sub(r"`", "", name).strip()


def _clean_next_action(nxt: str) -> str:
    nxt = re.sub(r"\*\*", "", nxt)
    nxt = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", nxt)  # ticket refs → label only in action text
    nxt = re.sub(r"\s*—+\s*Done\s*✓?", "", nxt, flags=re.I)
    nxt = re.sub(r"\s*✓", "", nxt)
    nxt = re.sub(r"\s+", " ", nxt).strip(" —|")
    return nxt


def _pick_links(detail: str) -> list[dict[str, str]]:
    """Prefer Jira/ADINC/SKRULL, Teams, PD links from item detail block only."""
    all_links = _extract_links(detail)
    picked: list[dict[str, str]] = []
    seen: set[str] = set()

    def add_link(link: dict[str, str]) -> None:
        if link["url"] in seen:
            return
        seen.add(link["url"])
        picked.append(link)

    for link in all_links:
        label, url = link["label"], link["url"]
        if "atlassian.net/browse" in url or label.upper().startswith(("ADINC", "SKRULL", "ADIA")):
            add_link(link)
    for link in all_links:
        if "teams.microsoft.com" in link["url"]:
            add_link(link)
    for link in all_links:
        if "pagerduty.com" in link["url"]:
            add_link(link)
    return picked[:4]  # keep milestone to ~2 lines


def format_milestone_markdown(item: OncallItem) -> str:
    title = _short_title(item.name)
    action = _clean_next_action(item.next_action)
    parts = [title, action]
    link_bits = []
    for link in item.links:
        label = link["label"]
        if "teams.microsoft.com" in link["url"]:
            if "Prod - Linear Ad Sales" in label or "Linear Ad Sales" in label:
                label = "PRODPS thread"
            elif "message" in link["url"]:
                label = "Teams thread"
            else:
                label = "Teams chat"
        elif "pagerduty.com" in link["url"]:
            label = "PD"
        link_bits.append(f"[{label}]({link['url']})")
    if link_bits:
        parts.append(" · ".join(link_bits))
    raw = " \u2014 ".join(parts)
    item.raw_markdown = raw
    item.text = plain_text_for_dedup(raw)
    return raw


def parse_oncall_transcript(jsonl_path: Path) -> dict:
    texts = _extract_assistant_texts(jsonl_path)
    full = "\n\n".join(texts)
    block = _latest_open_items_block(texts)
    if not block:
        return {"transcript": str(jsonl_path), "open_items": [], "error": "no open items block"}

    table_rows = _parse_summary_table(block)
    # Also try Quick summary subsection
    if not table_rows:
        qs = re.search(r"## Quick summary.*", block, re.S | re.I)
        if qs:
            table_rows = _parse_summary_table(qs.group(0))

    items: list[OncallItem] = []
    for day, name, nxt in table_rows:
        if SKIP_NEXT_ACTION.match(nxt.strip()):
            continue
        if "~~" in name:
            continue
        detail = _find_item_detail_block(full, name, open_block=block)
        links = _pick_links(detail)
        item = OncallItem(day=day, name=name, next_action=nxt, links=links)
        format_milestone_markdown(item)
        items.append(item)

    return {
        "transcript": str(jsonl_path),
        "transcript_id": jsonl_path.parent.name,
        "open_items": [i.to_dict() for i in items],
        "open_count": len(items),
        "parent_task": oncall_items_to_task_tree([i.to_dict() for i in items]),
    }


def oncall_items_to_task_tree(open_items: list[dict]) -> dict | None:
    """Nest open oncall follow-ups under a single parent milestone task."""
    if not open_items:
        return None
    children = [
        {
            "raw": item["raw"],
            "text": item["text"],
            "complete": False,
            "children": [],
        }
        for item in open_items
    ]
    return {
        "raw": ONCALL_PARENT_TITLE,
        "text": ONCALL_PARENT_TITLE,
        "complete": False,
        "children": children,
    }


def parse_latest_oncall_log(root: Path | None = None) -> dict:
    root = root or TRANSCRIPT_ROOT
    transcripts = find_oncall_transcripts(root)
    if not transcripts:
        return {"open_items": [], "error": "no oncall transcripts found"}
    return parse_oncall_transcript(transcripts[0])


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse Oncall activity log open items")
    ap.add_argument("--transcript", help="Specific transcript jsonl path")
    ap.add_argument("--output", help="Write JSON output")
    ap.add_argument("--root", help="Agent transcripts root directory")
    args = ap.parse_args()

    if args.transcript:
        result = parse_oncall_transcript(Path(args.transcript))
    else:
        result = parse_latest_oncall_log(Path(args.root) if args.root else None)

    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
