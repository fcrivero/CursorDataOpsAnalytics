#!/usr/bin/env python3
"""Convert plain-text dates in milestone text to Confluence editable ``<time>`` tags.

Confluence calendar fields use storage format::

    <time datetime="2026-08-24" local-id="2834a7a1485f" />

Plain text like ``due Aug 24`` must be converted when generating new tasks.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, timedelta
from typing import Match

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# Month name + day, optional year: "Aug 24", "August 24, 2026"
MONTH_DAY_RE = re.compile(
    r"\b(Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|"
    r"Jul(?:y)?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|"
    r"Dec(?:ember)?)\.?\s+(\d{1,2})(?:,?\s+(\d{4}))?\b",
    re.IGNORECASE,
)

# ISO date not already inside a time tag
ISO_DATE_RE = re.compile(r"(?<!<time datetime=\")\b(\d{4}-\d{2}-\d{2})\b")


def thursday_of_week(plan_monday: date) -> date:
    """Return Thursday (ongoing weekly effort due date) for the plan week."""
    return plan_monday + timedelta(days=3)


def confluence_time_tag(iso_date: str, local_id: str | None = None) -> str:
    """Build a Confluence editable date element."""
    lid = local_id or uuid.uuid4().hex[:12]
    return f'<time datetime="{iso_date}" local-id="{lid}" />'


def _month_day_to_iso(match: Match[str], default_year: int) -> str | None:
    month_name = match.group(1).lower().rstrip(".")
    day = int(match.group(2))
    year = int(match.group(3)) if match.group(3) else default_year
    month = MONTHS.get(month_name)
    if not month:
        return None
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None


def inject_time_tags(text: str, plan_monday: date | None = None) -> str:
    """Replace recognizable date phrases with Confluence ``<time>`` tags.

    *text* is plain (not HTML). Returns HTML-safe inner content with ``&nbsp;``
    preserved where present; new time tags are inserted unescaped.
    """
    if not text or "<time datetime=" in text:
        return text

    default_year = (plan_monday or date.today()).year

    def repl_month(m: Match[str]) -> str:
        iso = _month_day_to_iso(m, default_year)
        return confluence_time_tag(iso) if iso else m.group(0)

    result = MONTH_DAY_RE.sub(repl_month, text)

    def repl_iso(m: Match[str]) -> str:
        return confluence_time_tag(m.group(1))

    result = ISO_DATE_RE.sub(repl_iso, result)
    return result


def format_task_body_inner(text: str, plan_monday: date | None = None) -> str:
    """Format milestone text as Confluence task-body inner HTML (links + dates)."""
    import html as html_mod

    from confluence_links import markdown_inline_to_html, split_markdown_segments  # noqa: WPS433

    default_year = (plan_monday or date.today()).year
    parts: list[str] = []

    for seg in split_markdown_segments(text):
        if seg.kind == "link":
            from confluence_links import link_to_html  # noqa: WPS433

            parts.append(link_to_html(seg.label, seg.url))
        else:
            chunk = seg.content
            if chunk and "<time datetime=" not in chunk:
                chunk = inject_time_tags(chunk, plan_monday=plan_monday)
            # Escape plain text but preserve injected time tags
            pos = 0
            for m in re.finditer(r"<time datetime=\"[^\"]+\" local-id=\"[^\"]+\" />", chunk):
                if m.start() > pos:
                    parts.append(html_mod.escape(chunk[pos : m.start()]))
                parts.append(m.group(0))
                pos = m.end()
            if pos < len(chunk):
                parts.append(html_mod.escape(chunk[pos:]))

    inner = "".join(parts) if parts else html_mod.escape(text)
    if not parts and "[" in text and "](" in text:
        inner = markdown_inline_to_html(inject_time_tags(text, plan_monday=plan_monday))

    return f'<span class="placeholder-inline-tasks">{inner}</span>'


def roll_weekly_effort_dates(html: str, plan_monday: date) -> str:
    """Update ``(ongoing weekly effort)`` task dates to Thursday of *plan_monday* week."""
    thursday = thursday_of_week(plan_monday).isoformat()

    def repl(m: Match[str]) -> str:
        block = m.group(0)
        return re.sub(
            r"<time datetime=\"\d{4}-\d{2}-\d{2}\"",
            f'<time datetime="{thursday}"',
            block,
            count=1,
        )

    return re.sub(
        r"<ac:task-body>.*?ongoing weekly effort.*?</ac:task-body>",
        repl,
        html,
        flags=re.S,
    )


def roll_carried_dates(html: str, plan_monday: date) -> str:
    """Roll dates in carried milestone blocks for the new plan week."""
    return roll_weekly_effort_dates(html, plan_monday)


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Convert plain dates to Confluence time tags")
    ap.add_argument("--text", required=True, help="Plain milestone text")
    ap.add_argument("--plan-monday", help="Plan week Monday YYYY-MM-DD (year inference)")
    args = ap.parse_args()
    monday = date.fromisoformat(args.plan_monday) if args.plan_monday else None
    print(format_task_body_inner(args.text, plan_monday=monday))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
