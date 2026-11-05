#!/usr/bin/env python3
"""Parse open items from CursorDataOpsAnalytics daily-log.md.

Usage:
  python parse_daily_log.py --input daily-log.md [--output out.json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from confluence_links import MD_LINK_RE, plain_text_for_dedup


def parse_daily_log(text: str) -> dict:
    open_items: list[dict] = []
    done_items: list[dict] = []
    in_list = False
    next_num = None
    last_updated = None

    for line in text.splitlines():
        m = re.match(r"\*\*Last updated:\*\*\s*(\S+)", line)
        if m:
            last_updated = m.group(1)
        m = re.match(r"\*\*Next item number:\*\*\s*(\d+)", line)
        if m:
            next_num = int(m.group(1))
        if line.strip() == "## Full List":
            in_list = True
            continue
        if in_list and line.startswith("## "):
            break
        if not in_list:
            continue
        item_m = re.match(r"^(\d+)\.\s+(.*)$", line.strip())
        if not item_m:
            continue
        num = int(item_m.group(1))
        body = item_m.group(2).strip()
        plain = plain_text_for_dedup(body)
        links = [
            {"label": m.group(1), "url": m.group(2)}
            for m in MD_LINK_RE.finditer(body)
        ]
        entry = {
            "number": num,
            "text": plain,
            "raw": body,
            "links": links,
            "has_links": bool(links),
        }
        if body.startswith("~~") and "~~" in body[2:]:
            done_items.append(entry)
        else:
            open_items.append(entry)

    return {
        "last_updated": last_updated,
        "next_item_number": next_num,
        "open_items": open_items,
        "done_items": done_items,
        "open_count": len(open_items),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Parse daily-log.md open todos")
    ap.add_argument("--input", required=True, help="Path to daily-log.md")
    ap.add_argument("--output", help="Write JSON output")
    args = ap.parse_args()
    text = Path(args.input).read_text(encoding="utf-8")
    result = parse_daily_log(text)
    out = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).write_text(out, encoding="utf-8")
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
