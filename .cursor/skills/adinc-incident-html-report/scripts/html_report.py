#!/usr/bin/env python3
"""Generate Ads Data incident metrics HTML from ADINC Jira issue dicts."""
from __future__ import annotations

import html
import re
from calendar import month_abbr, monthrange
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timezone

from adinc_lifecycle_metrics import compute_metrics, parse_jira_date

JIRA_BROWSE = "https://deept.atlassian.net/browse"
ALL_METRICS = frozenset({"mttr", "mttm", "mttd"})


@dataclass
class ReportConfig:
    month_label: str
    jql: str
    year: int
    month: int
    metrics: frozenset[str] = field(default_factory=lambda: ALL_METRICS)

    def includes(self, name: str) -> bool:
        return name in self.metrics

PRI_COLOR = {"P1": "#ef4444", "P2": "#f97316", "P3": "#eab308", "P4": "#d1d5db"}
PRI_BAR = {"P1": "bg-red-500", "P2": "bg-orange-500", "P3": "bg-yellow-500", "P4": "bg-neutral-300"}

CAT_GROUP = {
    "Code - Deployment": "code",
    "Code - Schedule": "code",
    "Code - Syntax": "code",
    "Spark": "code",
    "Data - DQ": "dq",
    "DATA - DQ": "dq",
    "Data - Partial": "dq",
    "Data - Object": "dq",
    "Data - Upstream Delay": "dq",
    "Network": "infra",
    "AWS - Kinesis": "infra",
    "Vendor - API": "infra",
    "Manual Error": "other",
}


def parse_desc(desc: str) -> dict:
    out = {}
    if not desc:
        return out
    text = desc.replace("*", "")
    for key in (
        "SOURCE_SYSTEM",
        "ISSUE_CATEGORY",
        "EXTERNAL",
        "MISSED_SLA",
        "PIPELINE",
        "INC_NUMBER",
        "PD_ID",
        "PRIOR_ADINC",
    ):
        m = re.search(rf"{key}:\s*(.+)", text, re.I)
        if m:
            out[key] = m.group(1).strip()
    return out


def parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    s = s.replace("+0000", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def fmt_duration(seconds: float) -> str:
    if seconds < 60:
        return "<1m"
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    d, h = divmod(h, 24)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m and not d:
        parts.append(f"{m}m")
    return " ".join(parts) if parts else f"{s}s"


def fmt_days(days: int | None) -> str:
    if days is None:
        return "—"
    if days == 0:
        return "<1d"
    return f"{days}d"


def issue_lifecycle(issue: dict) -> dict:
    if issue.get("mttr_days") is not None or issue.get("start_date_pick"):
        return {
            "mttr_days": issue.get("mttr_days"),
            "mttm_days": issue.get("mttm_days"),
            "mttd_days": issue.get("mttd_days"),
            "start_date_pick": issue.get("start_date_pick"),
            "end_date": issue.get("end_date"),
            "completion_date": issue.get("completion_date"),
        }
    return compute_metrics(issue)


def resolved_sort_date(issue: dict) -> datetime | None:
    end = parse_jira_date(issue.get("end_date"))
    if end:
        return datetime.combine(end, datetime.min.time(), tzinfo=timezone.utc)
    return parse_dt(issue.get("updated"))


def first_line(text: str, label: str) -> str | None:
    if not text:
        return None
    m = re.search(rf"(?i){label}\s*:?\s*(.+?)(?:\n|$)", text)
    return m.group(1).strip() if m else None


def extract_summary(issue: dict) -> str | None:
    notes = issue.get("notes") or ""
    for label in ("Business impact", "Business Impact"):
        v = first_line(notes, label)
        if v:
            return v
    desc_meta = parse_desc(issue.get("description") or "")
    return None


def extract_rca(issue: dict) -> str | None:
    notes = issue.get("notes") or ""
    m = re.search(r"(?is)\*?RCA:?\*?\s*(.+?)(?:\n\n|\nRoot Cause|\nResolution|\nActions|\nBusiness impact|\[Confluence)", notes)
    if m:
        t = re.sub(r"\s+", " ", m.group(1).strip())
        return t[:500] + ("…" if len(t) > 500 else "")
    m = re.search(r"(?is)^RCA:\s*(.+?)(?:\n\n|\nRoot Cause|\nResolution|\nActions|\nBusiness impact|\[Confluence)", notes)
    if m:
        t = re.sub(r"\s+", " ", m.group(1).strip())
        return t[:500] + ("…" if len(t) > 500 else "")
    return None


def is_core_issue(issue: dict, meta: dict) -> bool:
    cat = (meta.get("ISSUE_CATEGORY") or "").strip()
    pri = issue.get("priority") or ""
    missed = (meta.get("MISSED_SLA") or "N").upper() == "Y"
    notes = (issue.get("notes") or "").lower()
    if cat.lower() == "manual error":
        return False
    if "false-positive" in notes or "alert noise" in notes or "threshold was set below" in notes:
        return False
    if pri in ("P1", "P2") or missed:
        return True
    if cat in ("Code - Deployment", "Data - Object", "Vendor - API", "Spark", "AWS - Kinesis", "Network"):
        return True
    return pri == "P3"


def month_week_labels(year: int, month: int) -> list[str]:
    abbr = month_abbr[month]
    last_day = monthrange(year, month)[1]
    labels: list[str] = []
    start = 1
    while start <= last_day:
        end = min(start + 6, last_day)
        labels.append(f"{abbr} {start}–{end}")
        start = end + 1
    return labels


def week_bucket(dt: datetime, cfg: ReportConfig) -> str | None:
    d = dt.date()
    if d.year != cfg.year or d.month != cfg.month:
        return None
    abbr = month_abbr[cfg.month]
    last_day = monthrange(cfg.year, cfg.month)[1]
    start = 1
    while start <= last_day:
        end = min(start + 6, last_day)
        if start <= d.day <= end:
            return f"{abbr} {start}–{end}"
        start = end + 1
    return None


def stacked_bar(segments: list[tuple[str, int]], max_total: int, height_px: int = 180) -> str:
    total = sum(c for _, c in segments)
    if total == 0:
        return f'<div class="w-16" style="height:{height_px}px"></div>'
    scale = (height_px - 20) / max(max_total, 1)
    blocks = []
    for pri, count in segments:
        if count <= 0:
            continue
        h = max(4, int(count * scale))
        blocks.append(f'<div class="{PRI_BAR[pri]}" style="height:{h}px" title="{pri}: {count}"></div>')
    inner = "\n".join(blocks)
    return f'<div class="w-16 flex flex-col justify-end" style="height:{height_px}px">{inner}</div>'


def cat_bar(segments: list[tuple[str, int]], max_total: int, height_px: int = 180) -> str:
    colors = {"code": "bg-sky-500", "external": "bg-orange-500", "infra": "bg-violet-500", "dq": "bg-rose-500", "other": "bg-neutral-300"}
    labels = {"code": "Code", "external": "External", "infra": "Infrastructure", "dq": "Data Quality", "other": "Other"}
    scale = (height_px - 20) / max(max_total, 1)
    blocks = []
    for key, count in segments:
        if count <= 0:
            continue
        h = max(4, int(count * scale))
        blocks.append(f'<div class="{colors[key]}" style="height:{h}px" title="{labels[key]}: {count}"></div>')
    inner = "\n".join(blocks)
    return f'<div class="w-16 flex flex-col justify-end" style="height:{height_px}px">{inner}</div>'


def _filter_chips(cls: str, attr: str, label: str, values: list[str]) -> str:
    btns = [f'<button class="{cls} px-3 py-1 rounded-full text-xs font-semibold border border-black bg-black text-white" data-{attr}="all">All</button>']
    for v in sorted(values, key=str.lower):
        esc = html.escape(v, quote=True)
        btns.append(
            f'<button class="{cls} px-3 py-1 rounded-full text-xs font-semibold border border-neutral-300 text-neutral-700 hover:border-black" data-{attr}="{esc}">{html.escape(v)}</button>'
        )
    return f'<span class="text-[11px] uppercase tracking-wide text-neutral-400 font-semibold w-24 shrink-0">{html.escape(label)}</span>{"".join(btns)}'


def _metric_spans(lc: dict, cfg: ReportConfig) -> str:
    parts: list[str] = []
    if cfg.includes("mttr"):
        parts.append(
            f'<span class="inline-flex items-center gap-1" title="Start DatePick → End Date (Done)">'
            f'<i data-lucide="timer" class="h-3 w-3"></i>MTTR {html.escape(fmt_days(lc.get("mttr_days")))}</span>'
        )
    if cfg.includes("mttm"):
        parts.append(
            f'<span class="inline-flex items-center gap-1" title="Start DatePick → Completion Date">'
            f'<i data-lucide="shield-check" class="h-3 w-3"></i>MTTM {html.escape(fmt_days(lc.get("mttm_days")))}</span>'
        )
    if cfg.includes("mttd"):
        parts.append(
            f'<span class="inline-flex items-center gap-1" title="Defect introduction → Start DatePick (Confluence RCA §5)">'
            f'<i data-lucide="radar" class="h-3 w-3"></i>MTTD {html.escape(fmt_days(lc.get("mttd_days")))}</span>'
        )
    if not parts:
        return ""
    return f'<div class="text-[11px] text-neutral-500 mt-1 flex flex-wrap gap-x-3 gap-y-1">{" · ".join(parts)}</div>'


def render_card(issue: dict, meta: dict, end: datetime, lc: dict, cfg: ReportConfig) -> str:
    key = issue["key"]
    pri = issue.get("priority") or "P3"
    border = PRI_COLOR.get(pri, "#d1d5db")
    src = meta.get("SOURCE_SYSTEM") or "Unspecified"
    cat = meta.get("ISSUE_CATEGORY") or "Unspecified"
    ext = (meta.get("EXTERNAL") or "N").upper() == "Y"
    missed = (meta.get("MISSED_SLA") or "N").upper() == "Y"
    resolved = end.strftime("%b %d").lstrip("0").replace(" 0", " ") if end else "—"
    badges = ""
    if ext:
        badges += '<span class="text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded border border-orange-300 text-orange-700 bg-orange-50">External</span> '
    if missed:
        badges += '<span class="text-[9px] font-bold uppercase tracking-wide px-1.5 py-0.5 rounded border border-rose-300 text-rose-700 bg-rose-50">Missed SLA</span> '
    summary = extract_summary(issue)
    rca = extract_rca(issue)
    body = ""
    if summary:
        body += f'<p class="text-xs text-neutral-700 leading-relaxed mt-2 pt-2 border-t border-neutral-200"><span class="font-semibold uppercase tracking-wide text-[10px]">Business Impact</span> · {html.escape(summary)}</p>'
    if rca:
        body += f'<p class="text-xs text-neutral-500 leading-relaxed mt-2 pt-2 border-t border-neutral-200"><span class="font-semibold uppercase tracking-wide text-[10px]">RCA</span> · {html.escape(rca)}</p>'
    elif not summary:
        body += '<p class="text-xs italic text-neutral-400 mt-2">No executive summary recorded.</p>'
    badge_row = f'<div class="flex items-center gap-1.5 mt-2 flex-wrap">{badges}</div>' if badges else ""
    return f"""
        <div class="adinc-card border border-neutral-300 rounded-lg p-4 break-inside-avoid" data-priority="{html.escape(pri)}" data-source="{html.escape(src)}" data-category="{html.escape(cat)}" style="border-left:4px solid {border}">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <div class="text-[10px] font-mono text-neutral-400 tnum"><a href="{JIRA_BROWSE}/{key}" class="inline-flex items-center gap-1 hover:text-black underline decoration-neutral-300 underline-offset-2 hover:decoration-black">{key}<i data-lucide="external-link" class="h-2.5 w-2.5"></i></a></div>
              <h3 class="text-sm font-bold leading-snug mt-0.5 break-words">{html.escape(issue.get("summary") or "")}</h3>
            </div>
            <div class="flex flex-col items-end gap-1 shrink-0">
              <span class="text-[10px] font-bold px-2 py-0.5 rounded bg-neutral-900 text-white">Done</span>
              <span class="text-[10px] font-semibold text-neutral-500">{html.escape(pri)}</span>
            </div>
          </div>
          <div class="text-[11px] text-neutral-500 mt-2 flex flex-wrap gap-x-3 gap-y-1"><span class="inline-flex items-center gap-1"><i data-lucide="calendar" class="h-3 w-3"></i>End {html.escape(resolved)}</span> · <span class="inline-flex items-center gap-1"><i data-lucide="server" class="h-3 w-3"></i>{html.escape(src)}</span> · <span class="inline-flex items-center gap-1"><i data-lucide="tag" class="h-3 w-3"></i>{html.escape(cat)}</span></div>
          {_metric_spans(lc, cfg)}
          {badge_row}
          {body}
        </div>"""


def _kpi_metric_tile(
    title: str,
    icon: str,
    mean_d: float,
    med_d: float,
    n: int,
    footnote: str,
) -> str:
    return f"""
      <div class="border border-neutral-300 rounded-lg p-4">
        <div class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-neutral-500"><i data-lucide="{icon}" class="h-3.5 w-3.5"></i> {html.escape(title)}</div>
        <div class="text-3xl font-extrabold tnum mt-2">{html.escape(fmt_days(int(round(mean_d)) if n else None))}</div>
        <div class="text-xs text-neutral-500 mt-1 leading-snug">median {html.escape(fmt_days(int(med_d) if n else None))} · n={n}</div>
        <div class="text-[10px] text-neutral-400 mt-1.5 leading-snug">{html.escape(footnote)}</div>
      </div>"""


def _auto_highlights(parsed: list, cfg: ReportConfig) -> str:
    p1 = [p for p in parsed if (p[0].get("priority") or "") == "P1"]
    pri_line = f"{len(p1)} P1 incident(s)" if p1 else "No P1 incidents"
    p1_keys = ", ".join(p[0]["key"] for p in p1[:6])
    cat_counts: dict[str, int] = defaultdict(int)
    for iss, meta, _, _ in parsed:
        cat_counts[meta.get("ISSUE_CATEGORY") or "Unspecified"] += 1
    top_cat = max(cat_counts.items(), key=lambda x: x[1])[0] if cat_counts else "—"
    metrics_blurb = (
        "Counts and lifecycle metrics use Jira Start DatePick, Completion Date, and End Date."
        + (
            " MTTD uses Confluence Incident History RCA §5 when linked from Notes."
            if cfg.includes("mttd")
            else ""
        )
    )
    return f"""
        <div class="flex items-start gap-3 border border-neutral-300 rounded-lg p-4" style="border-left:4px solid #e11d48">
          <i data-lucide="alert-triangle" class="h-4 w-4 text-neutral-400 mt-0.5 shrink-0"></i>
          <div>
            <h3 class="text-sm font-bold">Severity — {html.escape(pri_line)}</h3>
            <p class="text-xs text-neutral-700 leading-relaxed mt-1">{html.escape(p1_keys or "—")}</p>
          </div>
        </div>
        <div class="flex items-start gap-3 border border-neutral-300 rounded-lg p-4" style="border-left:4px solid #3b82f6">
          <i data-lucide="search" class="h-4 w-4 text-neutral-400 mt-0.5 shrink-0"></i>
          <div>
            <h3 class="text-sm font-bold">Top issue category — {html.escape(top_cat)}</h3>
            <p class="text-xs text-neutral-700 leading-relaxed mt-1">{html.escape(metrics_blurb)}</p>
          </div>
        </div>"""


def build(issues: list[dict], open_issues: list[dict], cfg: ReportConfig) -> str:
    parsed = []
    for iss in issues:
        meta = parse_desc(iss.get("description") or "")
        lc = issue_lifecycle(iss)
        end = resolved_sort_date(iss) or parse_dt(iss.get("updated"))
        parsed.append((iss, meta, end, lc))

    parsed.sort(key=lambda x: x[2] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
    n = len(parsed)
    pri_counts = defaultdict(int)
    for iss, _, _, _ in parsed:
        pri_counts[iss.get("priority") or "P3"] += 1

    mttr_days_list = [p[3]["mttr_days"] for p in parsed if p[3].get("mttr_days") is not None]
    mttm_days_list = [p[3]["mttm_days"] for p in parsed if p[3].get("mttm_days") is not None]
    mttd_days_list = [p[3]["mttd_days"] for p in parsed if p[3].get("mttd_days") is not None]

    def mean_days(vals: list[int]) -> float:
        return sum(vals) / len(vals) if vals else 0.0

    def median_days(vals: list[int]) -> float:
        if not vals:
            return 0.0
        s = sorted(vals)
        return float(s[len(s) // 2])

    mean_mttr_d = mean_days(mttr_days_list)
    med_mttr_d = median_days(mttr_days_list)
    mean_mttm_d = mean_days(mttm_days_list)
    med_mttm_d = median_days(mttm_days_list)
    mean_mttd_d = mean_days(mttd_days_list)
    med_mttd_d = median_days(mttd_days_list)

    core_keys = [p[0]["key"] for p in parsed if is_core_issue(p[0], p[1])]
    other_keys = [p[0]["key"] for p in parsed if p[0]["key"] not in core_keys]
    core_pct = int(round(100 * len(core_keys) / n)) if n else 0

    weeks_order = month_week_labels(cfg.year, cfg.month)
    week_pri = {w: defaultdict(int) for w in weeks_order}
    week_cat = {w: defaultdict(int) for w in weeks_order}
    for iss, meta, end, _lc in parsed:
        if not end:
            continue
        w = week_bucket(end, cfg)
        if not w or w not in week_pri:
            continue
        pri = iss.get("priority") or "P3"
        week_pri[w][pri] += 1
        cat = meta.get("ISSUE_CATEGORY") or ""
        grp = CAT_GROUP.get(cat, "other")
        if (meta.get("EXTERNAL") or "N").upper() == "Y" and grp == "other":
            grp = "external"
        week_cat[w][grp] += 1

    max_week = max(sum(week_pri[w].values()) for w in weeks_order) or 1
    max_cat_week = max(sum(week_cat[w].values()) for w in weeks_order) or 1

    pri_bars = ""
    for w in weeks_order:
        total = sum(week_pri[w].values())
        segs = [(p, week_pri[w][p]) for p in ("P4", "P3", "P2", "P1")]
        pri_bars += f"""
            <div class="flex flex-col items-center flex-1">
              <span class="text-sm font-bold text-neutral-700 mb-1 tnum">{total}</span>
              {stacked_bar(segs, max_week)}
            </div>"""

    cat_bars = ""
    for w in weeks_order:
        total = sum(week_cat[w].values())
        segs = [(k, week_cat[w][k]) for k in ("other", "infra", "external", "code", "dq")]
        cat_bars += f"""
            <div class="flex flex-col items-center flex-1">
              <span class="text-sm font-bold text-neutral-700 mb-1 tnum">{total}</span>
              {cat_bar(segs, max_cat_week)}
            </div>"""

    sources = sorted({p[1].get("SOURCE_SYSTEM", "Unspecified") for p in parsed})
    categories = sorted({p[1].get("ISSUE_CATEGORY", "Unspecified") for p in parsed})

    cards = "\n".join(render_card(i, m, e, lc, cfg) for i, m, e, lc in parsed)

    open_n = len(open_issues)
    open_detail = ""
    if open_issues:
        o = open_issues[0]
        open_detail = f"{o.get('priority', '')} · {o['key']}"

    pri_sub = " · ".join(f"{pri_counts[p]} {p}" for p in ("P1", "P2", "P3", "P4") if pri_counts[p])

    donut_core = int(round(100 * len(core_keys) / n)) if n else 0
    donut_other = 100 - donut_core

    metric_kpis = ""
    if cfg.includes("mttr"):
        metric_kpis += _kpi_metric_tile(
            "MTTR (mean)", "timer", mean_mttr_d, med_mttr_d, len(mttr_days_list),
            "Start DatePick → End Date (Done)",
        )
    if cfg.includes("mttm"):
        metric_kpis += _kpi_metric_tile(
            "MTTM (mean)", "shield-check", mean_mttm_d, med_mttm_d, len(mttm_days_list),
            "Start DatePick → Completion Date",
        )
    if cfg.includes("mttd"):
        metric_kpis += _kpi_metric_tile(
            "MTTD (mean)", "radar", mean_mttd_d, med_mttd_d, len(mttd_days_list),
            "Defect intro → Start DatePick (Confluence RCA §5)",
        )

    kpi_count = 2 + sum(1 for m in ("mttr", "mttm", "mttd") if cfg.includes(m))
    if kpi_count <= 3:
        kpi_grid = "grid-cols-2 md:grid-cols-3"
    elif kpi_count == 4:
        kpi_grid = "grid-cols-2 md:grid-cols-4"
    else:
        kpi_grid = "grid-cols-2 md:grid-cols-3 xl:grid-cols-5"

    highlights = _auto_highlights(parsed, cfg)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width, initial-scale=1.0" />
<title>Ad and Data Platform — Incident Insights ({cfg.month_label})</title>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://unpkg.com/lucide@latest"></script>
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
<style>
  html {{ font-family: 'Inter', ui-sans-serif, system-ui, sans-serif; }}
  @media print {{
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .no-print {{ display: none !important; }}
    @page {{ size: letter; margin: 0.4in; }}
  }}
  .tnum {{ font-variant-numeric: tabular-nums; }}
</style>
</head>
<body class="bg-white text-black">
<header class="bg-black text-white">
  <div class="max-w-[1100px] mx-auto px-6 h-14 flex items-center justify-center gap-3">
    <span class="text-white text-lg font-bold tracking-[0.15em]">AD AND DATA PLATFORM INCIDENT INSIGHTS</span>
  </div>
</header>
<main class="max-w-[1100px] mx-auto px-6 py-8">

  <div class="flex items-center gap-1 border-b border-neutral-300 mb-6 no-print">
    <button type="button" class="tab-btn -mb-px px-5 py-2.5 text-sm font-semibold border-b-2 border-transparent text-neutral-500 hover:text-black" data-tab="ads">Ads</button>
    <button type="button" class="tab-btn -mb-px px-5 py-2.5 text-sm font-semibold border-b-2 border-black text-black" data-tab="adsdata">Ads Data</button>
    <button type="button" class="tab-btn -mb-px px-5 py-2.5 text-sm font-semibold border-b-2 border-transparent text-neutral-500 hover:text-black" data-tab="data">Data</button>
  </div>

  <div id="panel-ads" class="tab-panel hidden">
    <div class="border border-dashed border-neutral-300 rounded-lg py-20 text-center">
      <i data-lucide="layout-dashboard" class="h-8 w-8 mx-auto text-neutral-300"></i>
      <h3 class="text-sm font-bold uppercase tracking-wide mt-3">Ads</h3>
      <p class="text-xs text-neutral-400 mt-1">Content coming soon.</p>
    </div>
  </div>

  <div id="panel-adsdata" class="tab-panel">

    <div class="flex items-start justify-end border-b border-black pb-5 mb-6">
      <div class="text-right text-xs text-neutral-500 leading-relaxed">
        <div class="inline-flex items-center gap-1.5 bg-black text-white font-bold uppercase tracking-wide text-sm px-3 py-1.5 rounded-md mb-2"><i data-lucide="calendar" class="h-4 w-4"></i> {cfg.month_label}</div>
        <div class="flex items-center gap-1.5 justify-end mt-1"><i data-lucide="database" class="h-3.5 w-3.5"></i> Source: Jira ADINC (live) — <span class="font-mono">{html.escape(cfg.jql)}</span></div>
      </div>
    </div>

    <div class="grid {kpi_grid} gap-3 mb-8">
      <div class="border border-neutral-300 rounded-lg p-4">
        <div class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-neutral-500"><i data-lucide="alert-triangle" class="h-3.5 w-3.5"></i> Incidents Resolved</div>
        <div class="text-3xl font-extrabold tnum mt-2">{n}</div>
        <div class="text-xs text-neutral-500 mt-1">{html.escape(pri_sub)}</div>
      </div>
      <div class="border border-neutral-300 rounded-lg p-4">
        <div class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide text-neutral-500"><i data-lucide="loader" class="h-3.5 w-3.5"></i> Still Open</div>
        <div class="text-3xl font-extrabold tnum mt-2">{open_n}</div>
        <div class="text-xs text-neutral-500 mt-1">{html.escape(open_detail)}</div>
      </div>
      {metric_kpis}
    </div>

    <section>
      <h2 class="flex items-center gap-2 text-sm font-bold uppercase tracking-wide mb-3 pb-2 border-b border-neutral-300">
        <i data-lucide="bar-chart-3" class="h-4 w-4"></i> Resolved Incidents by Week — {cfg.month_label}
      </h2>
      <div class="flex items-center gap-1 mb-4 no-print">
        <button class="subtab-btn px-4 py-1.5 text-xs font-semibold rounded-md border border-black bg-black text-white" data-subtab="priority">By Priority</button>
        <button class="subtab-btn px-4 py-1.5 text-xs font-semibold rounded-md border border-neutral-300 text-neutral-700 hover:border-black" data-subtab="category">By Issue Category</button>
        <button class="subtab-btn px-4 py-1.5 text-xs font-semibold rounded-md border border-neutral-300 text-neutral-700 hover:border-black" data-subtab="core">Core Issues</button>
      </div>
      <div id="subpanel-priority" class="subtab-panel">
        <div class="border border-neutral-300 rounded-lg p-6">
          <div class="flex items-end justify-around gap-4 h-56 border-b border-neutral-300 pb-0">{pri_bars}
          </div>
          <div class="flex items-center justify-around gap-4 mt-2 text-xs text-neutral-500">
            {"".join(f'<span class="flex-1 text-center">{w}</span>' for w in weeks_order)}
          </div>
          <div class="flex items-center justify-center gap-6 mt-5 pt-4 border-t border-neutral-200 text-xs text-neutral-600">
            <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-sm bg-red-500"></span> P1 — Critical</span>
            <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-sm bg-orange-500"></span> P2 — High</span>
            <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-sm bg-yellow-500"></span> P3 — Medium</span>
            <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-sm bg-neutral-300"></span> P4 — Low</span>
          </div>
        </div>
      </div>
      <div id="subpanel-category" class="subtab-panel hidden">
        <div class="border border-neutral-300 rounded-lg p-6">
          <div class="flex items-end justify-around gap-4 h-56 border-b border-neutral-300 pb-0">{cat_bars}
          </div>
          <div class="flex items-center justify-around gap-4 mt-2 text-xs text-neutral-500">
            {"".join(f'<span class="flex-1 text-center">{w}</span>' for w in weeks_order)}
          </div>
          <div class="flex items-center justify-center gap-x-4 gap-y-1.5 mt-5 pt-4 border-t border-neutral-200 text-[11px] text-neutral-600 flex-wrap">
            <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-sm bg-sky-500"></span> Code</span>
            <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-sm bg-orange-500"></span> External</span>
            <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-sm bg-violet-500"></span> Infrastructure</span>
            <span class="flex items-center gap-1.5"><span class="h-3 w-3 rounded-sm bg-rose-500"></span> Data Quality</span>
          </div>
        </div>
      </div>
      <div id="subpanel-core" class="subtab-panel hidden">
        <div class="border border-neutral-300 rounded-lg p-6">
          <div class="flex flex-col md:flex-row items-center justify-center gap-10">
            <div class="relative shrink-0" style="width:200px;height:200px;">
              <div style="width:200px;height:200px;border-radius:9999px;background:conic-gradient(#e11d48 0% {donut_core}%, #f59e0b {donut_core}% 100%);"></div>
              <div class="absolute inset-0 flex items-center justify-center">
                <div class="bg-white rounded-full flex flex-col items-center justify-center shadow-sm" style="width:116px;height:116px;">
                  <span class="text-3xl font-extrabold tnum">{n}</span>
                  <span class="text-[10px] uppercase tracking-wide text-neutral-400 font-semibold">Resolved</span>
                </div>
              </div>
            </div>
            <div class="flex flex-col gap-4">
              <div class="flex items-start gap-2.5">
                <span class="h-3.5 w-3.5 rounded-sm bg-rose-600 shrink-0 mt-0.5"></span>
                <div>
                  <div class="text-sm font-bold">Core issue <span class="text-neutral-400 font-normal">— {len(core_keys)} of {n} ({core_pct}%)</span></div>
                  <div class="text-xs text-neutral-500">{", ".join(core_keys)}</div>
                </div>
              </div>
              <div class="flex items-start gap-2.5">
                <span class="h-3.5 w-3.5 rounded-sm bg-amber-500 shrink-0 mt-0.5"></span>
                <div>
                  <div class="text-sm font-bold">Other <span class="text-neutral-400 font-normal">— {len(other_keys)} of {n} ({100-core_pct}%)</span></div>
                  <div class="text-xs text-neutral-500">{", ".join(other_keys) if other_keys else "—"}</div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <section class="mt-8">
      <h2 class="flex items-center gap-2 text-sm font-bold uppercase tracking-wide mb-3 pb-2 border-b border-neutral-300">
        <i data-lucide="lightbulb" class="h-4 w-4"></i> Incident Highlights
      </h2>
      <div class="space-y-3">
        {highlights}
      </div>
    </section>

    <section class="mt-8">
      <div class="mb-3 pb-3 border-b border-neutral-300">
        <h2 class="flex items-center gap-2 text-sm font-bold uppercase tracking-wide mb-3">
          <i data-lucide="list" class="h-4 w-4"></i> Incident Log — ADINC, Resolved in {cfg.month_label} <span id="adIncCount" class="text-neutral-400 font-normal">({n})</span>
        </h2>
        <div class="space-y-2 no-print">
          <div class="flex flex-wrap items-center gap-1.5" id="adPriFilter">
            <span class="text-[11px] uppercase tracking-wide text-neutral-400 font-semibold w-24 shrink-0">Priority</span>
            <button class="adpri-chip px-3 py-1 rounded-full text-xs font-semibold border border-black bg-black text-white" data-pri="all">All</button>
            <button class="adpri-chip px-3 py-1 rounded-full text-xs font-semibold border border-neutral-300 text-neutral-700 hover:border-black" data-pri="P1">P1</button>
            <button class="adpri-chip px-3 py-1 rounded-full text-xs font-semibold border border-neutral-300 text-neutral-700 hover:border-black" data-pri="P2">P2</button>
            <button class="adpri-chip px-3 py-1 rounded-full text-xs font-semibold border border-neutral-300 text-neutral-700 hover:border-black" data-pri="P3">P3</button>
            <button class="adpri-chip px-3 py-1 rounded-full text-xs font-semibold border border-neutral-300 text-neutral-700 hover:border-black" data-pri="P4">P4</button>
          </div>
          <div class="flex flex-wrap items-center gap-1.5" id="adSrcFilter">{_filter_chips("adsrc-chip", "src", "Source System", sources)}</div>
          <div class="flex flex-wrap items-center gap-1.5" id="adCatFilter">{_filter_chips("adcat-chip", "cat", "Issue Category", categories)}</div>
        </div>
      </div>
      <div id="adIncGrid" class="grid md:grid-cols-2 gap-3" style="column-gap:0.75rem">
{cards}
      </div>
      <p id="adIncEmpty" class="hidden text-sm text-neutral-400 italic py-6 text-center">No incidents match the selected filters.</p>
    </section>

    <section class="mt-8">
      <h2 class="flex items-center gap-2 text-sm font-bold uppercase tracking-wide mb-3 pb-2 border-b border-neutral-300">
        <i data-lucide="link" class="h-4 w-4"></i> Resources
      </h2>
      <div class="grid md:grid-cols-2 gap-3">
        <a href="https://deept.atlassian.net/issues/?jql={html.escape(cfg.jql.replace(' ', '%20'))}" class="group border border-neutral-300 rounded-lg p-4 hover:border-black transition-colors">
          <div class="flex items-start justify-between gap-3">
            <div class="flex items-center gap-2">
              <i data-lucide="activity" class="h-4 w-4"></i>
              <h3 class="text-sm font-bold">Jira · ADINC filter</h3>
            </div>
            <i data-lucide="external-link" class="h-4 w-4 text-neutral-400 group-hover:text-black shrink-0"></i>
          </div>
          <p class="text-xs text-neutral-500 leading-relaxed mt-2">Live source of truth for this ticket set. JQL: <span class="font-mono">{html.escape(cfg.jql)}</span></p>
        </a>
      </div>
    </section>

  </div><!-- /panel-adsdata -->

  <div id="panel-data" class="tab-panel hidden">
    <div class="border border-dashed border-neutral-300 rounded-lg py-20 text-center">
      <i data-lucide="bar-chart-3" class="h-8 w-8 mx-auto text-neutral-300"></i>
      <h3 class="text-sm font-bold uppercase tracking-wide mt-3">Data</h3>
      <p class="text-xs text-neutral-400 mt-1">Content coming soon.</p>
    </div>
  </div>

<script>
(function(){{
  var btns=document.querySelectorAll('.tab-btn');
  var panels={{ads:document.getElementById('panel-ads'),adsdata:document.getElementById('panel-adsdata'),data:document.getElementById('panel-data')}};
  btns.forEach(function(b){{
    b.addEventListener('click',function(){{
      var t=b.getAttribute('data-tab');
      btns.forEach(function(x){{
        var active=x===b;
        x.className='tab-btn -mb-px px-5 py-2.5 text-sm font-semibold border-b-2 '+(active?'border-black text-black':'border-transparent text-neutral-500 hover:text-black');
      }});
      Object.keys(panels).forEach(function(k){{panels[k].classList.toggle('hidden',k!==t);}});
      if(typeof lucide!=='undefined'){{lucide.createIcons();}}
    }});
  }});
}})();
(function(){{
  var subBtns=document.querySelectorAll('.subtab-btn');
  var subPanels={{priority:document.getElementById('subpanel-priority'),category:document.getElementById('subpanel-category'),core:document.getElementById('subpanel-core')}};
  subBtns.forEach(function(b){{
    b.addEventListener('click',function(){{
      var t=b.getAttribute('data-subtab');
      subBtns.forEach(function(x){{
        var active=x===b;
        x.className='subtab-btn px-4 py-1.5 text-xs font-semibold rounded-md border '+(active?'border-black bg-black text-white':'border-neutral-300 text-neutral-700 hover:border-black');
      }});
      Object.keys(subPanels).forEach(function(k){{subPanels[k].classList.toggle('hidden',k!==t);}});
    }});
  }});
}})();
(function(){{
  var pri='all',src='all',cat='all';
  var priChips=document.querySelectorAll('.adpri-chip');
  var srcChips=document.querySelectorAll('.adsrc-chip');
  var catChips=document.querySelectorAll('.adcat-chip');
  var cards=Array.prototype.slice.call(document.querySelectorAll('.adinc-card'));
  var count=document.getElementById('adIncCount');
  var empty=document.getElementById('adIncEmpty');
  function paint(chips,active,dataAttr){{
    chips.forEach(function(x){{
      var on=x===active;
      x.className=(dataAttr==='pri'?'adpri-chip':dataAttr==='src'?'adsrc-chip':'adcat-chip')+' px-3 py-1 rounded-full text-xs font-semibold border '+(on?'border-black bg-black text-white':'border-neutral-300 text-neutral-700 hover:border-black');
    }});
  }}
  function apply(){{
    var shown=0;
    cards.forEach(function(c){{
      var show=(pri==='all'||c.getAttribute('data-priority')===pri)&&(src==='all'||c.getAttribute('data-source')===src)&&(cat==='all'||c.getAttribute('data-category')===cat);
      c.style.display=show?'':'none'; if(show) shown++;
    }});
    count.textContent='('+shown+')';
    empty.classList.toggle('hidden',shown>0);
  }}
  priChips.forEach(function(ch){{ch.addEventListener('click',function(){{pri=ch.getAttribute('data-pri');paint(priChips,ch,'pri');apply();}});}});
  srcChips.forEach(function(ch){{ch.addEventListener('click',function(){{src=ch.getAttribute('data-src');paint(srcChips,ch,'src');apply();}});}});
  catChips.forEach(function(ch){{ch.addEventListener('click',function(){{cat=ch.getAttribute('data-cat');paint(catChips,ch,'cat');apply();}});}});
}})();
lucide.createIcons();
</script>
</main>
</body>
</html>"""


