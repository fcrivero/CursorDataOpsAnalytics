# Data Ops PD Incidents — Reference

**PagerDuty identity (single-incident lookups):** [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md)

## PagerDuty services
| Name | ID | Urgency column |
|------|-----|----------------|
| Ad Platform Data Ops Service High Urgency | `P7OFL7L` | High |
| Ad Platform Data Ops Service Low Urgency | `P3CUKVY` | Low |

Default query includes **both** unless the user filters urgency.

## Time window parsing

Assume **America/Los_Angeles** unless the user specifies otherwise.

| User phrase | Start (`since`) | End (`until`) |
|-------------|-----------------|---------------|
| "today from 9:30 AM" | Today 09:30 PT | Now |
| "today" | Today 00:00 PT | Now |
| "last 24 hours" | Now − 24h | Now |
| "last N hours" | Now − Nh | Now |
| "YYYY-MM-DD HH:MM to ..." | Parse explicitly | Parse explicitly |

Convert PT → UTC for PagerDuty API (`since` / `until`).

Display in table as PT: `Mon DD, YYYY h:mm A PT`.

## Title parsing

### Job name

Regex (first match wins):

1. `job_name:([A-Za-z0-9_]+)`
2. `service:([A-Za-z0-9_]+)` — Datadog long-run monitors

Examples:

```
[AP][ODS][Core][Fail] foo on @databricks_job_run_id:123,job_name:ap_addr_ods_core_beacon_drax_event_prod
→ job: ap_addr_ods_core_beacon_drax_event_prod

[AP][ODS][Core][Long Run] ap_addr_ods_metrics_mc_metadata_prod on env:prod,...,service:ap_addr_ods_metrics_mc_metadata_prod
→ job: ap_addr_ods_metrics_mc_metadata_prod

DataOps|PROD|Dag Change|DRR| Dag -
→ no job (DataOps alert)
```

### Run ID

Regex: `@databricks_job_run_id:(\d+)`

When absent (Long Run alerts), link to job page only.

## Team and on-call tags

**Source of truth:** PagerDuty incident **`title`** only (not job name, DAG name, or alert body fields). Full precedence and examples: [dataops-pd-incident-analysis/reference.md](../dataops-pd-incident-analysis/reference.md#team-and-on-call-tags).

**Summary:** bracket subtitles in the title (`[Segmentation]`, `[Targeting]`, `[Metrics]`, …) **supersede** keyword matches such as `audience` / `fandom` embedded in the job name.

Derive **Team** from incident title (first match wins):

| Condition in title | Team | Oncall MS Teams Tag |
|--------------------|------|---------------------|
| `[AP][ODS]` or `[ODS]` | ODS | See ODS rules below |
| `[AP][ADM]` or `[ADM]` | ADM | See ADM rules below |
| `[AP][BI]`, `[BI]`, or `addr-bi`, `addr_bi` | BI | See BI rules below |
| `DataOps\|PROD\|Dag Change` or `Dag Change` | **TBD** | `—` |
| No match | **TBD** | `—` |

### ODS on-call (narrow when subtitle is clear)

Bracket subtitles in title (case-insensitive inside `[…]`):

| Subtitle in title | Oncall MS Teams Tag |
|-------------------|---------------------|
| `[Metrics]` | `@oncall-ods-metrics` |
| `[Core]` or other ODS | `@oncall-adi-data-core` |
| ODS, subtitle unclear | `@oncall-adi-data-core` `@oncall-ods-metrics` |

### ADM on-call (narrow when subtitle is clear)

Evaluate bracket subtitles **before** keyword fallback:

| Subtitle in title | Oncall MS Teams Tag |
|-------------------|---------------------|
| `[segmentation]` | `@oncall-segmentation` |
| `[Targeting]` or `[targeting]` | `@oncall-audience-targeting` |
| `[measurement]` | `@oncall-adm-measurement-eng` |
| ADM, no bracket subtitle above | `audience` / `fandom` / `targeting` in **title** → `@oncall-audience-targeting` |
| ADM, subtitle unclear | `@oncall-audience-targeting` `@oncall-segmentation` `@oncall-adm-measurement-eng` |

### BI on-call (narrow when subtitle is clear)

| Subtitle in title | Oncall MS Teams Tag |
|-------------------|---------------------|
| `[CRMA]` | `@oncall-crma` |
| `[Goldmine]` or other BI | `@oncall-addr-bi` |
| BI, subtitle unclear | `@oncall-addr-bi` `@oncall-crma` |

## Databricks workspace resolution

Prod workspaces to check (in order):

1. `sox-prod-uw2`
2. `gen-prod-uw2`

Optional fallbacks if not found: `sox-prod-ue1`, `gen-prod-ue1`.

### MCP tools

| Tool | When |
|------|------|
| `get_run_details(workspace, run_id)` | Run ID in title |
| `list_jobs(workspace, name_filter=job_name, limit=5)` | No run ID; need job_id |

Run IDs are workspace-scoped — try each prod workspace until `get_run_details` succeeds (no `error` field).

## Databricks URL templates

| Workspace | Org ID | Host |
|-----------|--------|------|
| sox-prod-uw2 | `3352005904589238` | `https://ads-data-sox-prod-uw2.cloud.databricks.com` |
| gen-prod-uw2 | `161202889771344` | `https://ads-data-gen-prod-uw2.cloud.databricks.com` |
| sox-prod-ue1 | (lookup via `list_workspaces` if needed) | `https://ads-data-sox-prod-ue1.cloud.databricks.com` |
| gen-prod-ue1 | (lookup via `list_workspaces` if needed) | `https://ads-data-gen-prod-ue1.cloud.databricks.com` |

**Run URL:** `{host}/?o={org_id}#job/{job_id}/run/{run_id}`

**Job URL (no run):** `{host}/?o={org_id}#job/{job_id}`

Prefer `run_page_url` from `get_run_details` when available.

## Common job → workspace hints

Most `_prod` ODS Core / Metrics jobs → **sox-prod-uw2**.

Most `_prod` ADM segmentation / audience / supply reporting / drax → **gen-prod-uw2**.

Always confirm via MCP — do not rely on hints alone.

## Example row

| PD# | Urgency | Status | Assignee | Timestamp | Title | Job | Workspace | DBX Job/Run link | Team | Oncall MS Teams Tag |
|-----|---------|--------|----------|-----------|-------|-----|-----------|------------------|------|---------------------|
| 5548051 | High | Acknowledged | Praveen Sadineni | Jul 20, 2026 2:46 PM PT | [[AP][ADM][segmentation][Fail] ap_addr_audience_hulu_fandom_serving_prod…](https://disney.pagerduty.com/incidents/Q1ZJYTU763M6O0) | `ap_addr_audience_hulu_fandom_serving_prod` | gen-prod-uw2 | [Run](https://ads-data-gen-prod-uw2.cloud.databricks.com/?o=161202889771344#job/573027999471240/run/344473032276319) | ADM | `@oncall-segmentation` |
| 5546205 | High | Resolved | — | Jul 20, 2026 9:36 AM PT | [DataOps\|PROD\|Dag Change\|DRR\| Dag - …](https://disney.pagerduty.com/incidents/Q2SZV81LJG60OF) | — | — | — | TBD | — |
