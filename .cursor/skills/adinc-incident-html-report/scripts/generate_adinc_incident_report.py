#!/usr/bin/env python3
"""Generate Ads Data ADINC incident metrics HTML from live Jira + Confluence."""
from __future__ import annotations

import argparse
import json
import sys
from calendar import month_name, monthrange
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from adinc_confluence import enrich_mttd
from adinc_credentials import basic_auth, load_credentials
from adinc_fetch import jira_search
from html_report import ALL_METRICS, ReportConfig, build

SCRIPT_DIR = Path(__file__).resolve().parent


def last_completed_month(today: date | None = None) -> tuple[int, int]:
    today = today or date.today()
    first_this = today.replace(day=1)
    last_prev = first_this - timedelta(days=1)
    return last_prev.year, last_prev.month


def month_bounds(year: int, month: int) -> tuple[date, date]:
    last = monthrange(year, month)[1]
    return date(year, month, 1), date(year, month, last)


def month_label(year: int, month: int) -> str:
    return f"{month_name[month]} {year}"


def slug_month(year: int, month: int) -> str:
    return f"{month_name[month]}{year}"


def build_jql(
    start: date,
    end_exclusive: date,
    extra: str | None,
) -> str:
    jql = (
        f'project = ADINC AND resolutiondate >= "{start.isoformat()}" '
        f'AND resolutiondate < "{end_exclusive.isoformat()}"'
    )
    if extra:
        jql = f"{jql} AND ({extra})"
    return jql + " ORDER BY resolutiondate DESC"


def parse_metrics(raw: str | None, exclude: str | None) -> frozenset[str]:
    if raw:
        chosen = {m.strip().lower() for m in raw.split(",") if m.strip()}
    else:
        chosen = set(ALL_METRICS)
    if exclude:
        for m in exclude.split(","):
            chosen.discard(m.strip().lower())
    unknown = chosen - set(ALL_METRICS)
    if unknown:
        raise SystemExit(f"Unknown metrics: {', '.join(sorted(unknown))}. Use mttr,mttm,mttd.")
    if not chosen:
        raise SystemExit("At least one metric must remain after --exclude.")
    return frozenset(chosen)


def default_output(year: int, month: int) -> Path:
    return Path.home() / "Downloads" / f"AdData-Metrics_AdsData_{slug_month(year, month)}.html"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate ADINC Ads Data incident HTML report.")
    parser.add_argument(
        "--month",
        metavar="YYYY-MM",
        help="Report month (default: previous completed calendar month)",
    )
    parser.add_argument("--start", metavar="YYYY-MM-DD", help="Custom range start (overrides --month)")
    parser.add_argument("--end", metavar="YYYY-MM-DD", help="Custom range end inclusive (overrides --month)")
    parser.add_argument(
        "--jql-extra",
        help='Extra AND clause, e.g. created >= "2026-10-06" for dashboard-aligned cohorts',
    )
    parser.add_argument(
        "--metrics",
        help="Comma-separated lifecycle metrics: mttr,mttm,mttd (default: all)",
    )
    parser.add_argument(
        "--exclude",
        help="Comma-separated metrics to omit, e.g. mttd",
    )
    parser.add_argument("-o", "--output", type=Path, help="Output HTML path")
    parser.add_argument(
        "--json-snapshot",
        type=Path,
        help="Optional path to write fetched issue JSON",
    )
    parser.add_argument(
        "--no-open-count",
        action="store_true",
        help="Skip fetching still-open ADINC tickets for KPI",
    )
    args = parser.parse_args()

    if args.start or args.end:
        if not (args.start and args.end):
            parser.error("--start and --end must be used together")
        start = date.fromisoformat(args.start)
        end_inclusive = date.fromisoformat(args.end)
        year, month = start.year, start.month
        end_exclusive = end_inclusive + timedelta(days=1)
        label = f"{start.isoformat()} – {end_inclusive.isoformat()}"
    elif args.month:
        year_s, month_s = args.month.split("-", 1)
        year, month = int(year_s), int(month_s)
        start, end_inclusive = month_bounds(year, month)
        end_exclusive = end_inclusive + timedelta(days=1)
        label = month_label(year, month)
    else:
        year, month = last_completed_month()
        start, end_inclusive = month_bounds(year, month)
        end_exclusive = end_inclusive + timedelta(days=1)
        label = month_label(year, month)

    metrics = parse_metrics(args.metrics, args.exclude)
    jql = build_jql(start, end_exclusive, args.jql_extra)
    cfg = ReportConfig(month_label=label, jql=jql, year=year, month=month, metrics=metrics)
    out_path = args.output or default_output(year, month)

    try:
        user, token = load_credentials()
    except RuntimeError as exc:
        print(exc, file=sys.stderr)
        print(
            "Fallback: use Jira MCP (user-jira-server) + Confluence MCP to build a JSON snapshot, "
            "then pass --json-snapshot if you add that loader.",
            file=sys.stderr,
        )
        return 1

    auth = basic_auth(user, token)
    print(f"Fetching resolved ADINC: {jql}", flush=True)
    resolved = jira_search(jql, auth)
    print(f"  {len(resolved)} resolved", flush=True)

    if metrics & {"mttd"}:
        print("Enriching MTTD from Confluence RCA pages …", flush=True)
        resolved = [enrich_mttd(i, auth) for i in resolved]

    open_issues: list[dict] = []
    if not args.no_open_count:
        open_jql = 'project = ADINC AND status != Done ORDER BY updated DESC'
        open_issues = jira_search(open_jql, auth, max_results=50)
        print(f"  {len(open_issues)} open (for KPI)", flush=True)

    payload = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "source": "adinc-incident-html-report skill (Jira REST + Confluence)",
        "jql_resolved": jql,
        "metrics": sorted(metrics),
        "resolved": resolved,
        "open": open_issues[:5],
    }
    if args.json_snapshot:
        args.json_snapshot.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"Wrote snapshot {args.json_snapshot}")

    html_out = build(resolved, open_issues[:5], cfg)
    out_path.write_text(html_out, encoding="utf-8")
    print(f"Wrote {out_path} ({len(resolved)} incidents, {len(html_out)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
