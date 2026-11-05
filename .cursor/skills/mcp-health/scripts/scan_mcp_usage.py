#!/usr/bin/env python3
"""Scan Cursor agent transcripts for MCP server last-used timestamps."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TIMESTAMP_RE = re.compile(
    r"<timestamp>([^<]+)</timestamp>", re.IGNORECASE
)
MCP_TOOL_NAMES = {"CallMcpTool", "GetMcpTools", "FetchMcpResource"}

# Servers omitted from mcp-health reports (retired or redundant integrations).
EXCLUDED_SERVERS = frozenset({"plugin-atlassian-atlassian"})


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cursor-root",
        default=str(Path.home() / ".cursor"),
        help="Path to ~/.cursor (default: %(default)s)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit JSON instead of a markdown table",
    )
    return parser.parse_args()


def normalize_server_id(server: str) -> str | None:
    server = (server or "").strip()
    if not re.fullmatch(r"[\w-]+", server):
        return None
    if server.startswith(("user-", "plugin-")):
        return server
    return f"user-{server}"


def parse_timestamp(raw: str) -> datetime | None:
    raw = raw.strip()
    for fmt in (
        "%A, %b %d, %Y, %I:%M %p (UTC%z)",
        "%A, %B %d, %Y, %I:%M %p (UTC%z)",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def extract_tool_uses(record: dict[str, Any]) -> list[tuple[str, str]]:
    """Return (tool_name, server_id) pairs from an assistant message."""
    hits: list[tuple[str, str]] = []
    message = record.get("message") or {}
    content = message.get("content") or []
    if not isinstance(content, list):
        return hits

    for block in content:
        if not isinstance(block, dict):
            continue
        name = block.get("name") or block.get("tool")
        if name not in MCP_TOOL_NAMES:
            continue
        payload = block.get("input") or {}
        server = payload.get("server")
        if isinstance(server, str) and server.strip():
            hits.append((name, server.strip()))
    return hits


def scan_transcripts(cursor_root: Path) -> dict[str, dict[str, Any]]:
    """Map server id -> {last_used, last_tool, transcript_id}."""
    usage: dict[str, dict[str, Any]] = {}
    projects_root = cursor_root / "projects"
    if not projects_root.is_dir():
        return usage

    for jsonl in projects_root.glob("*/agent-transcripts/*/*.jsonl"):
        current_ts: datetime | None = None
        transcript_id = jsonl.parent.name
        try:
            lines = jsonl.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue

        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = record.get("role")
            if role == "user":
                text_parts: list[str] = []
                message = record.get("message") or {}
                for block in message.get("content") or []:
                    if isinstance(block, dict) and block.get("type") == "text":
                        text_parts.append(block.get("text") or "")
                for text in text_parts:
                    match = TIMESTAMP_RE.search(text)
                    if match:
                        parsed = parse_timestamp(match.group(1))
                        if parsed:
                            current_ts = parsed

            if role != "assistant":
                continue

            for tool_name, server_raw in extract_tool_uses(record):
                server = normalize_server_id(server_raw)
                if not server or server in EXCLUDED_SERVERS:
                    continue
                candidate_ts = current_ts
                if candidate_ts is None:
                    candidate_ts = datetime.fromtimestamp(
                        jsonl.stat().st_mtime, tz=timezone.utc
                    )

                prev = usage.get(server)
                if prev is None or candidate_ts > prev["last_used_dt"]:
                    usage[server] = {
                        "last_used_dt": candidate_ts,
                        "last_used": candidate_ts.strftime("%Y-%m-%d %H:%M %Z"),
                        "last_tool": tool_name,
                        "transcript_id": transcript_id,
                    }

    return usage


def load_mcp_configs(cursor_root: Path) -> dict[str, dict[str, Any]]:
    configs: dict[str, dict[str, Any]] = {}
    mcp_json = cursor_root / "mcp.json"
    if not mcp_json.is_file():
        return configs

    try:
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return configs

    for name, cfg in (data.get("mcpServers") or {}).items():
        if isinstance(cfg, dict):
            configs[normalize_server_id(name)] = cfg
            configs[name] = cfg
    return configs


def main() -> int:
    args = parse_args()
    cursor_root = Path(args.cursor_root)
    usage = scan_transcripts(cursor_root)
    configs = load_mcp_configs(cursor_root)

    payload = {
        "scanned_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M %Z"),
        "usage_by_server": {
            server: {
                "last_used": info["last_used"],
                "last_tool": info["last_tool"],
                "transcript_id": info["transcript_id"],
            }
            for server, info in sorted(
                usage.items(), key=lambda item: item[1]["last_used_dt"], reverse=True
            )
            if server not in EXCLUDED_SERVERS
        },
        "configured_servers": sorted(set(configs.keys())),
    }

    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
