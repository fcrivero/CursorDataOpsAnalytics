#!/usr/bin/env python3
"""Fetch latest daily-log.md from fcrivero/CursorDataOpsAnalytics.

Fetches from every available source, picks the freshest copy, and reports
staleness when GitHub has not been updated recently.

Usage:
  python fetch_daily_log.py [--output PATH] [--json-summary PATH]
  python fetch_daily_log.py --warn-if-before 2026-09-14
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

DEFAULT_CLONE = Path(r"C:\Users\rivef104\Documents\AI\Cloud\CursorDataOpsAnalytics")
DEFAULT_FILE = DEFAULT_CLONE / "daily-log.md"
REPO = "fcrivero/CursorDataOpsAnalytics"
RAW_URL = f"https://raw.githubusercontent.com/{REPO}/main/daily-log.md"

SKILLS = Path(__file__).resolve().parent
sys.path.insert(0, str(SKILLS))
from parse_daily_log import parse_daily_log  # noqa: E402


@dataclass
class DailyLogSource:
    label: str
    text: str
    sha: str | None = None
    commit_date: str | None = None
    last_updated: str | None = None
    next_item_number: int | None = None
    open_count: int = 0


def git_pull(clone_dir: Path) -> bool:
    if not (clone_dir / ".git").exists():
        return False
    try:
        subprocess.run(
            ["git", "pull", "origin", "main"],
            cwd=clone_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return DEFAULT_FILE.exists()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def local_clone_sha(clone_dir: Path) -> str | None:
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=clone_dir,
            check=True,
            capture_output=True,
            text=True,
        )
        return proc.stdout.strip() or None
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def fetch_via_gh_api() -> tuple[str | None, str | None, str | None]:
    """Return (text, blob_sha, commit_date)."""
    try:
        proc = subprocess.run(
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                f"repos/{REPO}/contents/daily-log.md",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(proc.stdout)
        b64 = (data.get("content") or "").replace("\n", "")
        text = base64.b64decode(b64).decode("utf-8") if b64 else None
        blob_sha = data.get("sha")

        commit_proc = subprocess.run(
            [
                "gh",
                "api",
                "--hostname",
                "github.com",
                f"repos/{REPO}/commits?path=daily-log.md&per_page=1",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        commits = json.loads(commit_proc.stdout)
        commit_date = commits[0]["commit"]["author"]["date"] if commits else None
        commit_sha = commits[0]["sha"] if commits else None
        return text, commit_sha or blob_sha, commit_date
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError, KeyError, IndexError):
        pass
    return None, None, None


def fetch_via_raw() -> str | None:
    try:
        with urllib.request.urlopen(RAW_URL, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except OSError:
        return None


def source_from_text(label: str, text: str, sha: str | None = None, commit_date: str | None = None) -> DailyLogSource:
    parsed = parse_daily_log(text)
    return DailyLogSource(
        label=label,
        text=text,
        sha=sha,
        commit_date=commit_date,
        last_updated=parsed.get("last_updated"),
        next_item_number=parsed.get("next_item_number"),
        open_count=parsed.get("open_count", 0),
    )


def freshness_key(src: DailyLogSource) -> tuple[int, int, str]:
    """Higher is fresher: next item number, open+done count, last_updated."""
    parsed = parse_daily_log(src.text)
    total = parsed.get("open_count", 0) + len(parsed.get("done_items", []))
    next_num = parsed.get("next_item_number") or 0
    last = parsed.get("last_updated") or "0000-00-00"
    return (next_num, total, last)


def collect_sources() -> list[DailyLogSource]:
    sources: list[DailyLogSource] = []

    if git_pull(DEFAULT_CLONE) and DEFAULT_FILE.exists():
        text = DEFAULT_FILE.read_text(encoding="utf-8")
        sources.append(
            source_from_text(
                "local-clone (git pull)",
                text,
                sha=local_clone_sha(DEFAULT_CLONE),
            )
        )

    gh_text, gh_sha, gh_date = fetch_via_gh_api()
    if gh_text:
        sources.append(source_from_text("github-api", gh_text, sha=gh_sha, commit_date=gh_date))

    raw_text = fetch_via_raw()
    if raw_text and not any(s.text == raw_text for s in sources):
        sources.append(source_from_text("raw-github", raw_text))

    if not sources and DEFAULT_FILE.exists():
        text = DEFAULT_FILE.read_text(encoding="utf-8")
        sources.append(source_from_text("local-clone (stale fallback)", text))

    return sources


def pick_freshest(sources: list[DailyLogSource]) -> DailyLogSource:
    if not sources:
        raise RuntimeError("Could not fetch daily-log.md from any source")
    return max(sources, key=freshness_key)


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def build_summary(
    chosen: DailyLogSource,
    all_sources: list[DailyLogSource],
    warn_before: date | None,
) -> dict:
    parsed = parse_daily_log(chosen.text)
    last_updated = parse_iso_date(parsed.get("last_updated"))
    today = date.today()

    mismatched = []
    if len(all_sources) > 1:
        keys = {freshness_key(s) for s in all_sources}
        if len(keys) > 1:
            mismatched = [
                {
                    "source": s.label,
                    "last_updated": s.last_updated,
                    "next_item_number": s.next_item_number,
                    "open_count": s.open_count,
                    "sha": (s.sha or "")[:12],
                }
                for s in all_sources
            ]

    stale_reasons: list[str] = []
    if last_updated and (today - last_updated).days > 7:
        stale_reasons.append(
            f"last_updated is {parsed.get('last_updated')} ({(today - last_updated).days} days ago)"
        )
    if warn_before and last_updated and last_updated < warn_before:
        stale_reasons.append(f"last_updated {parsed.get('last_updated')} is before {warn_before.isoformat()}")

    return {
        "source": chosen.label,
        "output": None,
        "remote_sha": chosen.sha,
        "remote_commit_date": chosen.commit_date,
        "last_updated": parsed.get("last_updated"),
        "next_item_number": parsed.get("next_item_number"),
        "open_count": parsed.get("open_count"),
        "done_count": len(parsed.get("done_items", [])),
        "total_items": parsed.get("open_count", 0) + len(parsed.get("done_items", [])),
        "sources_checked": [s.label for s in all_sources],
        "sources_mismatch": mismatched,
        "stale": bool(stale_reasons),
        "stale_reasons": stale_reasons,
        "warning": (
            "Daily log on GitHub appears stale. Push/sync from the Cloud Agent "
            "(Daily activity and todo log) before building the WFP."
            if stale_reasons
            else None
        ),
    }


def fetch_daily_log(output: Path, warn_before: date | None = None) -> tuple[str, dict]:
    sources = collect_sources()
    chosen = pick_freshest(sources)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(chosen.text, encoding="utf-8")
    summary = build_summary(chosen, sources, warn_before)
    summary["output"] = str(output)
    return chosen.text, summary


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch latest daily-log.md from GitHub")
    ap.add_argument("--output", type=Path, default=DEFAULT_FILE, help="Write fetched file here")
    ap.add_argument("--json-summary", type=Path, help="Write fetch metadata JSON")
    ap.add_argument(
        "--warn-if-before",
        help="Mark stale if **Last updated** is before YYYY-MM-DD (e.g. plan Monday)",
    )
    args = ap.parse_args()

    warn_before = parse_iso_date(args.warn_if_before) if args.warn_if_before else None
    _, summary = fetch_daily_log(args.output, warn_before=warn_before)

    if args.json_summary:
        args.json_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 1 if summary.get("stale") else 0


if __name__ == "__main__":
    raise SystemExit(main())
