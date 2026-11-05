---
name: adinc-incident-html-report
description: >-
  Generates the standalone Ads Data ADINC incident metrics HTML report from live
  Jira (deept ADINC) and Confluence Incident History RCAs. Supports month
  timeframe, MTTR/MTTM/MTTD toggles, KPI tiles, weekly charts, and filterable
  cards. Use when the user asks for an ADINC monthly incident report, Ads Data
  metrics HTML, AdData-Metrics report, or ADINC MTTR/MTTM/MTTD dashboard.
---

# ADINC incident HTML report

Produces a **self-contained HTML** report (Tailwind + Lucide, print-friendly) matching the full **Ad and Data Platform Incident Insights** shell: top tabs **Ads**, **Ads Data**, **Data** (same as the monthly combined report). **Ads Data** is populated (resolved/open KPIs, lifecycle metric tiles, weekly charts, highlights, ADINC cards, Jira link). **Ads** and **Data** render empty placeholders (“Content coming soon”) until a future workflow fills them.

**No reference HTML or PDF required.** Data comes from live systems.

## Canonical date semantics

Read [adinc-jira-dates.md](../adinc-jira-dates.md) before changing metrics.

| Metric | Interval (date-only, later − earlier) |
|--------|----------------------------------------|
| **MTTR** | Start DatePick (`customfield_10489`) → End Date (`customfield_10453`) |
| **MTTM** | Start DatePick → Completion Date (`customfield_10566`) |
| **MTTD** | Defect introduction (Confluence RCA §5) → Start DatePick |

**Never** use Jira Created → Updated for MTTR.

- **Jira:** `https://deept.atlassian.net` project **ADINC**
- **Confluence MTTD:** ADSO [Incident History](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192843672/Incident+History) pages linked from Jira **Notes** (`customfield_10253`)

## User inputs

| Input | Default | Notes |
|-------|---------|--------|
| **Timeframe** | Previous **full calendar month** (1st–last day, by `resolutiondate`) | `--month YYYY-MM` or `--start` / `--end` |
| **Extra JQL** | none | e.g. `--jql-extra 'created >= "2026-10-06"'` to match Ads Incident Dashboard cohort |
| **Metrics** | `mttr,mttm,mttd` | `--metrics mttr` or `--exclude mttd` |
| **Output** | `~/Downloads/AdData-Metrics_AdsData_{MonthYear}.html` | `-o path` |

Parse natural language into CLI flags (e.g. “October 2026, no MTTD” → `--month 2026-10 --exclude mttd`).

## Primary workflow (preferred)

Run the bundled script from the skill `scripts/` directory:

```bash
cd ~/.cursor/skills/adinc-incident-html-report/scripts
python generate_adinc_incident_report.py
```

Examples:

```bash
# Explicit month, all metrics
python generate_adinc_incident_report.py --month 2026-10

# MTTR only
python generate_adinc_incident_report.py --month 2026-10 --metrics mttr

# Exclude MTTD (skip Confluence calls)
python generate_adinc_incident_report.py --month 2026-10 --exclude mttd

# Dashboard-aligned October cohort
python generate_adinc_incident_report.py --month 2026-10 --jql-extra 'created >= "2026-10-06"'

# Custom range
python generate_adinc_incident_report.py --start 2026-10-01 --end 2026-10-31

# Save intermediate JSON
python generate_adinc_incident_report.py --month 2026-10 --json-snapshot ./adinc_snapshot.json
```

### Credentials

Script loads **JIRA_USERNAME** + **JIRA_TOKEN** (or **CONFLUENCE_USERNAME** + **CONFLUENCE_TOKEN**) from:

1. `scripts/.env`
2. Skill `.env`
3. `ADINC_JIRA_ENV` path
4. `jira-adinc-audit/scripts/.env`
5. Confluence MCP `.env` (common on this machine)

Do not commit tokens.

## Fallback when REST auth fails

Use MCP in this order:

1. **Jira** `user-jira-server` — `jira_search_issues` with JQL and fields:  
   `summary,status,priority,created,updated,description,notes,customfield_10489,customfield_10566,customfield_10453,resolutiondate`  
   (Request notes field id `customfield_10253` if `notes` alias fails.)
2. **Confluence** `user-confluence-disney` — for each `pageId` in Notes, fetch page body when MTTD is enabled; parse **Defect introduction time** (§5).
3. Normalize into the same issue dict shape as `adinc_fetch.normalize_issue`, run `compute_metrics` / `enrich_mttd`, then call `html_report.build(resolved, open_issues, ReportConfig(...))`.

Do **not** ask the user for a template HTML or PDF.

## Agent checklist

```
- [ ] Resolve timeframe (default: last completed month)
- [ ] Resolve metrics set (default: all three)
- [ ] Run generate_adinc_incident_report.py (or MCP fallback → build)
- [ ] Confirm output path and ticket count
- [ ] Tell user: open HTML in browser; JQL link uses deept.atlassian.net
```

## Script map

| File | Role |
|------|------|
| `generate_adinc_incident_report.py` | CLI entry |
| `adinc_fetch.py` | Jira search + normalize |
| `adinc_confluence.py` | MTTD §5 enrichment |
| `adinc_lifecycle_metrics.py` | Day math + parsers |
| `adinc_credentials.py` | Auth |
| `html_report.py` | HTML builder (`ReportConfig`) |

## Optional narrative polish

Auto highlights are data-driven (P1 count, top category). If the user wants executive copy like a prior month, draft 1–2 bullets from ticket summaries after generation — do not require manual HTML input.
