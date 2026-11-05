#!/usr/bin/env python3
"""Convert markdown links in daily-log / oncall text to Confluence storage HTML."""

from __future__ import annotations

import html
import re
import uuid
from dataclasses import dataclass
from typing import Literal

# DEEPT Jira (ADIA, SKRULL, ADINC, …) — matches existing focus-plan pages
DEEPT_JIRA_SERVER_ID = "e73d01c9-7f3e-3ea9-879c-d0da26ec7298"
DEEPT_JIRA_SERVER_NAME = "DEEPT Jira"

JIRA_KEY_RE = re.compile(r"^(ADIA|SKRULL|ADINC|ADI)-\d+$", re.IGNORECASE)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BARE_TICKET_RE = re.compile(r"\b(ADIA|SKRULL|ADINC|ADI)-(\d+)\b", re.IGNORECASE)


@dataclass
class Segment:
    kind: Literal["text", "link"]
    content: str
    label: str = ""
    url: str = ""


def split_markdown_segments(text: str) -> list[Segment]:
    """Split *text* into plain-text and ``[label](url)`` markdown link segments."""
    segments: list[Segment] = []
    pos = 0
    for m in MD_LINK_RE.finditer(text):
        if m.start() > pos:
            segments.append(Segment("text", text[pos : m.start()]))
        segments.append(Segment("link", "", m.group(1), m.group(2)))
        pos = m.end()
    if pos < len(text):
        segments.append(Segment("text", text[pos:]))
    if not segments:
        segments.append(Segment("text", text))
    return segments


def jira_macro(key: str) -> str:
    """Confluence Jira macro for DEEPT ticket keys."""
    key = key.upper()
    lid = uuid.uuid4().hex[:12]
    mid = str(uuid.uuid4())
    return (
        f'<ac:structured-macro ac:name="jira" ac:schema-version="1" '
        f'ac:local-id="{lid}" ac:macro-id="{mid}">'
        f'<ac:parameter ac:name="key">{html.escape(key)}</ac:parameter>'
        f'<ac:parameter ac:name="serverId">{DEEPT_JIRA_SERVER_ID}</ac:parameter>'
        f'<ac:parameter ac:name="server">{DEEPT_JIRA_SERVER_NAME}</ac:parameter>'
        f'</ac:structured-macro>'
    )


def link_to_html(label: str, url: str) -> str:
    """Convert one markdown link to Confluence HTML (Jira macro or ``<a href>``)."""
    label = label.strip()
    url = url.strip()
    if JIRA_KEY_RE.match(label) and "atlassian.net/browse" in url:
        return jira_macro(label)
    safe_url = html.escape(url, quote=True)
    safe_label = html.escape(label)
    return f'<a href="{safe_url}">{safe_label}</a>'


def plain_text_for_dedup(text: str) -> str:
    """Strip URLs but keep link labels and ticket keys for dedup matching."""
    plain = MD_LINK_RE.sub(r"\1", text)
    plain = re.sub(r"\s+", " ", plain).strip()
    return plain


def markdown_inline_to_html(text: str) -> str:
    """Convert markdown links in *text* to Confluence HTML fragments (no outer span)."""
    parts: list[str] = []
    for seg in split_markdown_segments(text):
        if seg.kind == "link":
            parts.append(link_to_html(seg.label, seg.url))
        else:
            parts.append(html.escape(seg.content))
    return "".join(parts)


def has_markdown_links(text: str) -> bool:
    return bool(MD_LINK_RE.search(text))


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Convert markdown links to Confluence HTML")
    ap.add_argument("--text", required=True, help="Text with [label](url) markdown links")
    args = ap.parse_args()
    print(markdown_inline_to_html(args.text))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
