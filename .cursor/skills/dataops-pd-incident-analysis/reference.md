# Data Ops PD Incident Analysis — Reference

## PagerDuty services

| Name | ID | Urgency |
|------|-----|---------|
| Ad Platform Data Ops Service High Urgency | `P7OFL7L` | High |
| Ad Platform Data Ops Service Low Urgency | `P3CUKVY` | Low |

## PD URL pattern

```
https://disney.pagerduty.com/incidents/{incident_id}
```

`incident_id` in URLs is the UUID (e.g. `Q1ZJYTU763M6O0`). PD# (e.g. `5548051`) is the numeric `incident_number`.

**Identity verification (mandatory):** Before trusting or mutating any incident, follow [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md). Always run the **identity gate** after `get_incident` or `GET /incidents/{pd_or_uuid}` — assert `incident_number` and/or UUID match user input. **Never** use `GET /incidents?incident_number=` (invalid filter).

`get_incident` accepts PD# or UUID. **`list_alerts_from_incident` requires the verified UUID**, not the PD#.

## Alert custom details (runbook URL)

Datadog alerts populate PagerDuty **Custom Details** (UI: Details → `body`). Fetch via `list_alerts_from_incident` using the incident UUID.

### API paths

| Priority | JSON path |
|----------|-----------|
| 1 | `response[0].body.details.body` |
| 2 | `response[0].body.cef_details.details.body` |

### Body format (markdown)

Typical structure inside `body`:

```
Job: {job_name}

Run: {run_id}

Failed: Task {task_key} failed with message: ...

Workspace: {sox-prod-uw2|gen-prod-uw2}

- [Link to Databricks page]( {url} )
- [Link to Job Trace]( {url} )
- [Link to Job Runbooks]( {url} )
- [Link to Data Pipelines]( {url} )
```

Note: URLs may have spaces inside parentheses — trim whitespace when extracting.

### Extraction regex

| Field | Pattern |
|-------|---------|
| **Runbook URL** | `\[Link to Job Runbooks\]\(\s*(https?://[^)\s]+)\s*\)` |
| Goldmine runbook | `_Runbook:\s*\[Runbook\]\(\s*(https?://[^)\s]+)\s*\)` |
| Databricks page | `\[Link to Databricks page\]\(\s*(https?://[^)\s]+)\s*\)` |
| Job Trace | `\[Link to Job Trace\]\(\s*(https?://[^)\s]+)\s*\)` |
| Data Pipelines | `\[Link to Data Pipelines\]\(\s*(https?://[^)\s]+)\s*\)` |
| Job (body) | `^Job:\s*(.+)$` (multiline) |
| Run (body) | `^Run:\s*(\d+)$` (multiline) |
| Workspace (body) | `^Workspace:\s*(\S+)$` (multiline) |

Prefer run ID and job name from the incident **title** when both exist; use body fields as fallback (especially when title lacks run ID on Long Run alerts).

### Example (#5546450)

Runbook from alert body:

```
https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192842258/DBX+-+ap_addr_ods_metrics_mc_metadata_prod
```

## Confluence runbook fallback

When Step 1b (PD alert) has no `[Link to Job Runbooks]` URL, search under the ADSO **Data Pipelines** tree via Confluence MCP (`user-confluence-disney`).

| Setting | Value |
|---------|--------|
| Root page | [Data Pipelines](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841195/Data+Pipelines) |
| Page ID | `192841195` |
| Space | `ADSO` |
| Tool | `confluence_search_content` (CQL) |

### Resolution priority

1. **PagerDuty alert** (Step 1b) — preferred when present
2. **Agent note** — first ADSO wiki URL in Recommendations or full note body
3. **Confluence CQL** — search descendant pages of `192841195`

### Job name normalization

Before title search, derive search stems from the incident job name:

| Step | Rule | Example |
|------|------|---------|
| Full name | Use as-is first | `ap_addr_ods_metrics_mc_metadata_dq_prod` |
| Strip `_dq_prod` | DQ jobs often share prod runbook | `ap_addr_ods_metrics_mc_metadata_prod` |
| Strip trailing `_prod` | Last resort stem | `ap_addr_ods_metrics_mc_metadata` |

Also try distinctive middle tokens (e.g. `mc_metadata`, `fandom`) when full-name search returns nothing.

### CQL queries (run in order until a ranked match)

```
ancestor = 192841195 AND title ~ "{job_name}"
ancestor = 192841195 AND title ~ "{normalized_stem}"
ancestor = 192841195 AND text ~ "{job_name}"
```

Optional team-scoped search (faster, narrower) when title indicates team:

| Title signal | Subtree page ID | Subtree title |
|--------------|-----------------|---------------|
| `[AP][ODS]` / `[ODS]` | `192841789` | Addressable ODS Pipelines |
| `[AP][ADM][segmentation]` | `192843596` | Addressable ADM Segmentation |
| `[AP][ADM]` targeting/audience | `192842271` | Addressable ADM Targeting |
| `[AP][BI]` / BI jobs | `192840829` | Addressable BI pipelines |

Use `ancestor = {subtree_id}` instead of `192841195` when the team is known; fall back to full tree if no hit.

### Match ranking

Score each result; pick highest:

| Score | Condition |
|-------|-----------|
| +10 | Page title contains full normalized job name |
| +8 | Title starts with `DBX -` or `DBX ` |
| +5 | Title contains job stem (e.g. `mc_metadata`) |
| +3 | `text ~` hit only (no title match) |
| −5 | Title is generic (`Copy of …`, index page, `Daily Support Check List`) |

If top two scores tie within 2 points, list both in the report and pick the `DBX`-prefixed page; note ambiguity.

### Build runbook URL

From search result `_links.webui`:

```
https://disney-enterprise.atlassian.net/wiki{webui}
```

Example: `webui` = `/spaces/ADSO/pages/192841547/DBX+Fandom+Hulu` →  
`https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841547/DBX+Fandom+Hulu`

### Verified examples

| Job name | CQL | Matched page |
|----------|-----|--------------|
| `ap_addr_ods_metrics_mc_metadata_dq_prod` | `title ~ "mc_metadata"` | DBX - ap_addr_ods_metrics_mc_metadata_prod |
| `ap_addr_audience_hulu_fandom_inbound_prod` | `text ~ "{job_name}"` | DBX Fandom Hulu |

### Limitations

- Runbook page title may differ from job name — always run `text ~` fallback
- Confluence index may lag briefly after new pages are published
- Multiple matches possible — always record `runbook_source` and page title in report
- Skip entirely for Dag Change / non-DBX incidents (no job name)

## Title parsing

Same rules as [dataops-pd-incidents/reference.md](../dataops-pd-incidents/reference.md):

| Field | Regex |
|-------|--------|
| Job name | `job_name:([A-Za-z0-9_.]+)` then `service:([A-Za-z0-9_.]+)` then Long Run job token before ` on env:` |
| Run ID | `@databricks_job_run_id:(\d+)` |
| DAG (Airflow) | `dag:([A-Za-z0-9_.]+)` |

**Normalized title** for "same title" matching: strip leading `[#NNNN] ` from `summary`, compare remainder to current incident's `title` (case-sensitive).

## Team and on-call tags

**Source of truth:** PagerDuty incident **`title`** (same text as the Datadog alert title for Data Ops monitors). Team and subteam / `@oncall-*` tags come **only** from that title — not from the job name, DAG name, runbook, Confluence, or DBX notebook path.

Same rules as [dataops-pd-incidents/reference.md](../dataops-pd-incidents/reference.md).

### Routing precedence (mandatory)

Apply in order; **stop at the first match**:

1. **Top-level team** — `[AP][ODS]` / `[AP][ADM]` / `[AP][BI]` (table below).
2. **Bracket subtitles** in the title — `[Metrics]`, `[Core]`, `[segmentation]`, `[Targeting]`, `[measurement]`, etc. (ODS/ADM tables below). Match **case-insensitively** inside square brackets (e.g. `[Segmentation]` = `[segmentation]`).
3. **Keyword fallback** — only if step 2 found **no** ADM/ODS bracket subtitle: then `audience`, `fandom`, or `targeting` anywhere in the **title** (still not the job name alone).
4. **Unclear** — multi-tag fallback row for that team.

**Do not override the title with job-name tokens.** Examples:

- Title `[AP][ADM][Segmentation][Forensics][Fail] ap_addr_audience_gen_landing_anomaly_prod on …` → **`@oncall-segmentation`** (subtitle `[Segmentation]` wins; `audience` in the job name does **not** imply targeting).
- Title `[AP][ADM][segmentation][Fail] ap_addr_audience_hulu_fandom_serving_prod on …` → **`@oncall-segmentation`** (not targeting despite `audience` / `fandom` in the job name).

Extra brackets such as `[Forensics]` are **not** separate on-call routes; use the sibling ADM subtitle (`[Segmentation]`, `[Targeting]`, …) for routing.

| Condition in title | Team | Oncall MS Teams Tag |
|--------------------|------|---------------------|
| `[AP][ODS]` or `[ODS]` | ODS | See ODS rules below |
| `[AP][ADM]` or `[ADM]` | ADM | See ADM rules below |
| `[AP][BI]`, `[BI]`, or `addr-bi`, `addr_bi` | BI | See BI rules below |
| `DataOps\|PROD\|Dag Change` or `Dag Change` | **TBD** | `—` |
| No match | **TBD** | `—` |

### ODS on-call

Bracket subtitles in the **title** (step 2 above):

| Subtitle in title | Oncall MS Teams Tag |
|-------------------|---------------------|
| `[Metrics]` | `@oncall-ods-metrics` |
| `[Core]` or other ODS | `@oncall-adi-data-core` |
| ODS, subtitle unclear | `@oncall-adi-data-core` `@oncall-ods-metrics` |

### ADM on-call

Bracket subtitles in the **title** (step 2 above) — evaluate **before** keyword fallback:

| Subtitle in title | Oncall MS Teams Tag |
|-------------------|---------------------|
| `[segmentation]` | `@oncall-segmentation` |
| `[Targeting]` or `[targeting]` | `@oncall-audience-targeting` |
| `[measurement]` | `@oncall-adm-measurement-eng` |
| ADM, no bracket subtitle above | Keyword fallback: `audience`, `fandom`, or `targeting` in title → `@oncall-audience-targeting`; else `measurement` in title → `@oncall-adm-measurement-eng` |
| ADM, still unclear | `@oncall-audience-targeting` `@oncall-segmentation` `@oncall-adm-measurement-eng` |

### BI on-call

Bracket subtitles in the **title** (step 2 above) — evaluate **before** default `@oncall-addr-bi`:

| Subtitle in title | Oncall MS Teams Tag |
|-------------------|---------------------|
| `[CRMA]` | `@oncall-crma` |
| `[Goldmine]` or other BI | `@oncall-addr-bi` |
| BI, subtitle unclear | `@oncall-addr-bi` `@oncall-crma` |

Example: `[AP][BI][CRMA][Fail] prod_ap_analytics_crma_gen_sp_prod_hulu_bi_scheduled` → **`@oncall-crma`** (not `@oncall-addr-bi`).

**Upstream ownership:** When DBX analysis shows the leaf failure is in a different pipeline than the PD title job (e.g. serving alert but inbound/Hightouch failed), keep Team/tag from the **PD title** for the MS Teams `@` mention, and add a second `@` tag or "CC" line in the full report **On-Call Action Plan** if the upstream job maps to a different on-call group.

## MS Teams handoff message

### MS Teams title line

Build the **first line** of the message from the incident `title`:

1. Take the PD incident title as-is.
2. **Truncate before** the first ` on ` suffix (removes `@databricks_job_run_id`, `env:`, `dag:`, etc.).
3. Result is the title **through the job or DAG name**.

| Full title | MS Teams title line |
|------------|---------------------|
| `[AP][ADM][segmentation][Fail] ap_addr_audience_hulu_fandom_serving_prod on @databricks_job_run_id:…` | `[AP][ADM][segmentation][Fail] ap_addr_audience_hulu_fandom_serving_prod` |
| `[AP][ADM][Targeting][Fail] adi.goldmine_loss_reason_report_prod on dag:…` | `[AP][ADM][Targeting][Fail] adi.goldmine_loss_reason_report_prod` |
| `DataOps\|PROD\|Dag Change\|DRR\| Dag -` | `DataOps\|PROD\|Dag Change\|DRR\| Dag -` (no ` on ` — use full title) |

**First line:** `{ms_teams_title_line} {oncall_tag}` — title, space, then `@oncall-…` (omit tag when Team is TBD).

### Section guide

| Section | Where | Source | Content |
|---------|-------|--------|---------|
| **AI Agent Recommendations** | Full report | Agent note `Recommendations:` | Numbered list from agent — review before adding to Teams |
| **On-Call Action Plan** | Full report | Step 6 (DBX MCP + synthesis) | Up to 6 bullets — concrete dev actions: task keys, log lines, job/run IDs, re-run order, runbook URL |
| **ROOT CAUSE** | MS Teams | Step 4b-leaf / DBX logs | 2–4 sentences — **verbatim leaf error** (Spark `[ERROR_CODE]` or named exception); never wrapper |
| **KEY EVIDENCE** | MS Teams | Step 4b-leaf + DBX | Up to 5 bullets — `task_key`, attempt #, verbatim error line(s) |
| **PAST CONTEXT** | MS Teams | Step 5 similar incidents | 2–5 bullets — prior PD#, dates, how closed, recurring pattern |
| **ADINC FIELDS** | ADINC block | Step 6b | All 10 ADINC description fields |
| **DEV INPUT NEEDED** | ADINC block | Step 6b flags | Bullets for fields needing dev input — omit if none |

**On-Call Action Plan** vs **AI Agent Recommendations:** Agent may say "investigate inbound job"; the action plan must state **what DBX found** (e.g. `segment-data-loading-app` + Hightouch error) and **ordered fix steps**. Never copy the same bullet into both sections.

**MS Teams exclusions:** Do not include alert URL (reachable from PD link), AI Agent Recommendations, On-Call Action Plan, or ADINC fields in the Teams message.

**MS Teams ROOT CAUSE rule:** Must pass the Step 6 DEV handoff gate — leaf error only. If agent note Root cause disagrees with Step 4b-leaf, **trust DBX leaf error** for Teams and note agent note separately in the full report only.

Plain-text template inside a ` ```text ` code block under heading `## MS Teams message`:

```
{ms_teams_title_line} {oncall_tag}

SUMMARY
PD#:        {incident_number}
Status:     {Status}
Urgency:    {High/Low}
Team:       {Team}
Job:        {job_name}
Run:        {run_id or —}
Workspace:  {workspace or —}
Opened:     {created_at PT}
PD:         https://disney.pagerduty.com/incidents/{id}
DBX Run:    {run_page_url or —}
Runbook:    {runbook_url or —}

ROOT CAUSE
{2–4 sentences — leaf error from Step 4b-leaf / reference.md#leaf-error-extraction; quote Spark [ERROR_CODE] or exception message verbatim}

KEY EVIDENCE
• {up to 5 bullets — include failed task_key, attempt number, and verbatim leaf error line(s)}

PAST CONTEXT
• {similar incident PD#, date, pattern}
• {how a prior incident was resolved — human note or maintenance}
• {recurring count / trend}
```

## ADINC block

Separate output block under heading `## ADINC` — **after** the MS Teams message. Plain-text template inside a ` ```text ` code block.

**Header:** First line is `ADINC — {@oncall tag} please create ADINC Ticket` — use the same DEV on-call tag as the MS Teams handoff (see [on-call routing](#on-call-routing)). Omit the tag only when Team is TBD.

**Ownership:** DEV team creates ADINC tickets via **Support Bot** (`/support`). Data Ops **suggests** field values only — never creates the ticket.

**Allowlists:** `PIPELINE`, `ISSUE_CATEGORY`, and `SOURCE_SYSTEM` must be **exact** matches from [jira-adinc-tickets/reference.md](../jira-adinc-tickets/reference.md) (same lists as `jira-adinc-audit` Check 6). Never invent values or append `<<< DEV TO CONFIRM >>>` on the value line.

Ten fields for ADINC description — per [ServiceNow/JIRA(ADINC) config](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841984/ServiceNow+JIRA+ADINC+-+Incident+Tags+and+Tracking+Configuration).

#### PIPELINE mapping (PD title → allowlist value)

| PD title signal | ADINC `PIPELINE:` (allowlist) |
|-----------------|-------------------------------|
| `[AP][ODS][Metrics]` | `ODS - Metrics` or `ODS - Metric` |
| `[AP][ODS][Core]` or other `[AP][ODS]` | `ODS - Data Core` |
| `[AP][ADM][segmentation]` | `ADM - Segmentation` |
| `[AP][ADM]` + measurement | `ADM - Measurement` |
| `[AP][ADM]` + targeting / audience / fandom | `ADM - Targeting` |
| `[AP][BI]` / Goldmine / `addr-bi` | Match Goldmine pipeline from allowlist (e.g. `Goldmine - STAQ`) |
| `Dag Change` / no job | `NA` |
| Ambiguous | `Waiting for RCA` + DEV INPUT NEEDED |

#### SOURCE_SYSTEM suggestions (allowlist only)

| Context | Suggested `SOURCE_SYSTEM:` |
|---------|----------------------------|
| ODS Metrics job | `ODS - Metrics` |
| ODS Core job | `ODS - Data Core` |
| ADM Segmentation | `ADM - Segmentation` |
| ADM Targeting | `ADM - Targeting` |
| ADM Measurement | `ADM - Measurement` |
| 3P vendor named in DBX logs | Matching `3P Vendor - *` from allowlist → `EXTERNAL: Y` |
| RCA not yet known | `Waiting for RCA` or `NA` |

#### ISSUE_CATEGORY suggestions (allowlist only)

| Signal | Suggested `ISSUE_CATEGORY:` |
|--------|------------------------------|
| DQ task / Deequ / constraint violated | `Data - DQ` |
| Partition sensor / upstream not ready / late data | `Data - Upstream Delay` |
| Empty feed / partial files / EOF | `Data - Partial` |
| Format / column / type mismatch | `Data - Format` |
| AWS quota / vCPU | `AWS - vCPU` |
| AWS S3 / Glue / etc. | Matching `AWS - *` from allowlist |
| Spark / cluster failure | `Spark` |
| Vendor API / sync failure | `Vendor - API` |
| RCA unknown | `Waiting for RCA` |

#### Suggested ticket title (canonical PD alert taxonomy)

Use the PD incident **title** truncated before the first ` on ` — same segments as Datadog/PagerDuty alerts. Reference: [Data Pipelines Confluence Structure — Standard (Canonical alert taxonomy)](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard).

| Full PD title | Suggested ticket title for Support Bot |
|---------------|--------------------------------------|
| `[AP][ODS][Core][Fail] ap_addr_ods_core_news_ent_hourly_dq_prod on @databricks_job_run_id:560874309866315,…` | `[AP][ODS][Core][Fail] ap_addr_ods_core_news_ent_hourly_dq_prod` |
| `[AP][BI][Goldmine][Long Run] ap_addr_bi_gen_programmatic_prod on env:prod,operation_name:…` | `[AP][BI][Goldmine][Long Run] ap_addr_bi_gen_programmatic_prod` |
| `[AP][ODS][Metrics][Fail] ap_addr_ods_metrics_line_item_metrics_prod on @databricks_job_run_id:…` | `[AP][ODS][Metrics][Fail] ap_addr_ods_metrics_line_item_metrics_prod` |

Preserve bracket segments (`[Fail]`, `[Long Run]`, etc.) from the PD title — do not strip alert-type qualifiers.

#### Field reference

| Field | Rule |
|-------|------|
| **TEAM** | Always `ads-data-support` |
| **INC_NUMBER** | `NA` unless user supplied ServiceNow INC |
| **EXTERNAL** | `Y` or `N` only |
| **MISSED_SLA** | DEV provides `Y`, `N`, or `NA` — never auto-fill |
| **PD_ID** | PD `incident_number` |

#### DEV RESPONSIBILITIES (always include)

| Requirement | Wording in output |
|-------------|-------------------|
| Ticket creation | Create via Support Bot (run `/support` in Microsoft Teams) |
| SLA miss → P1 | If `MISSED_SLA` is Y or Yes, set ticket priority to **P1** (per `jira-adinc-tickets`) |
| Assignee | Assign to **DEV on-call** or **owning DEV engineer** — include `{@oncall tag}` from incident when known |
| RCA deadline | Provide RCA in ticket **General → Notes** within **2 days** — not Comments (see [adinc-jira-notes.md](../adinc-jira-notes.md)) |

#### DEV INPUT NEEDED

List fields DEV must confirm. For allowlist fields, cite **allowed alternatives** from [jira-adinc-tickets/reference.md](../jira-adinc-tickets/reference.md) when the suggestion is uncertain.

ADINC block template:

```
ADINC — {@oncall tag} please create ADINC Ticket
Data Ops suggests values below. DEV team: create the ADINC ticket via Support Bot (/support).

DEV RESPONSIBILITIES
• Create via Support Bot (run /support in Microsoft Teams).
• If MISSED_SLA is Y or Yes, set ticket priority to P1.
• Assign the ticket to the DEV on-call or owning DEV engineer.
• Provide RCA in the ticket's General → Notes section within 2 days — do not use Comments.

SUGGESTED TICKET TITLE
{pd_title_truncated_at_first_" on "}
Ref: https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard

ADINC FIELDS (copy into Support Bot)
INC_NUMBER:     {NA or INC#}
TEAM:           ads-data-support
PIPELINE:       {allowlist value}
DAG:            {job_name or dag or NA}
TASK:           {leaf task_key or NA}
SOURCE_SYSTEM:  {allowlist value or NA}
ISSUE_CATEGORY: {allowlist value}
EXTERNAL:       {Y or N}
MISSED_SLA:     {leave blank or NA — DEV to fill}
PD_ID:          {incident_number}

DEV INPUT NEEDED
• {FIELD} — confirm or replace suggested value; allowed: {short list from allowlist when applicable}
• ...
```

### Example (#5548051)

**MS Teams message:**

```
[AP][ADM][segmentation][Fail] ap_addr_audience_hulu_fandom_serving_prod @oncall-segmentation

SUMMARY
PD#:        5548051
Status:     Resolved
Urgency:    High
Team:       ADM
Job:        ap_addr_audience_hulu_fandom_serving_prod
Run:        344473032276319
Workspace:  gen-prod-uw2
Opened:     Jul 20, 2026 2:46 PM PT
PD:         https://disney.pagerduty.com/incidents/Q1ZJYTU763M6O0
DBX Run:    https://ads-data-gen-prod-uw2.cloud.databricks.com/?o=161202889771344#job/573027999471240/run/344473032276319
Runbook:    https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841547/DBX+Fandom+Hulu

ROOT CAUSE
Serving job failed because hulu_fandom_inbound_job_sensor exhausted 49 retries — upstream inbound run 447313802235465 never succeeded within the 4h window (16:00 UTC trigger).

KEY EVIDENCE
• Sensor error on every attempt: "No successful job or task run found, not ready"
• All 4 downstream serving tasks SKIPPED (UPSTREAM_FAILED)
• Upstream run 447313802235465 is the blocking dependency

PAST CONTEXT
• Same sensor/upstream failure 4+ consecutive days on ap_addr_audience_hulu_fandom_serving_prod
• #5546167 (Jul 20, 9:31 AM PT) — same inbound run 447313802235465 failed earlier today (HT empty data)
• #5542206 (Jul 19) — identical root cause: inbound HT empty data blocked serving sensor
• #5537628 (Jul 18) — Praveen Sadineni placed job on maintenance until Monday
```

**On-Call Action Plan** (in full report, not Teams):

```
• Leaf failure: inbound segment-data-loading-app (run 783568452354319) — "Empty HT segment data found, please check Hightouch sync is on and completed generating files in source bucket"
• Confirm Hightouch sync + source S3 bucket have segment files before any re-run
• Re-run order: inbound job 904582290854944 / run 447313802235465 first → then repair serving job 573027999471240 from hulu_fandom_inbound_job_sensor
• Runbook: https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841547/DBX+Fandom+Hulu
```

**ADINC block:**

```
ADINC — @oncall-segmentation please create ADINC Ticket
Data Ops suggests values below. DEV team: create the ADINC ticket via Support Bot (/support).

DEV RESPONSIBILITIES
• Create via Support Bot (run /support in Microsoft Teams).
• If MISSED_SLA is Y or Yes, set ticket priority to P1.
• Assign the ticket to the DEV on-call or owning DEV engineer (@oncall-segmentation).
• Provide RCA in the ticket's General → Notes section within 2 days — do not use Comments.

SUGGESTED TICKET TITLE
[AP][ADM][segmentation][Fail] ap_addr_audience_hulu_fandom_serving_prod
Ref: https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard

ADINC FIELDS (copy into Support Bot)
INC_NUMBER:     NA
TEAM:           ads-data-support
PIPELINE:       ADM - Segmentation
DAG:            ap_addr_audience_hulu_fandom_serving_prod
TASK:           hulu_fandom_inbound_job_sensor
SOURCE_SYSTEM:  Waiting for RCA
ISSUE_CATEGORY: Data - Upstream Delay
EXTERNAL:       N
MISSED_SLA:     
PD_ID:          5548051

DEV INPUT NEEDED
• SOURCE_SYSTEM — confirm after RCA: ADM - Segmentation | 3P Vendor - Hightouch | Waiting for RCA
• ISSUE_CATEGORY — confirm: Data - Upstream Delay | Data - Partial | Waiting for RCA
• TASK — confirm leaf: hulu_fandom_inbound_job_sensor vs upstream segment-data-loading-app
• MISSED_SLA — Y/N did serving pipeline miss SLA?
• INC_NUMBER — NA or ServiceNow INC if created separately
```

### Example ADINC block (#5702691 — ODS Core DQ, upstream sensor)

```
ADINC — @oncall-adi-data-core please create ADINC Ticket
Data Ops suggests values below. DEV team: create the ADINC ticket via Support Bot (/support).

DEV RESPONSIBILITIES
• Create via Support Bot (run /support in Microsoft Teams).
• If MISSED_SLA is Y or Yes, set ticket priority to P1.
• Assign the ticket to the DEV on-call or owning DEV engineer (@oncall-adi-data-core).
• Provide RCA in the ticket's General → Notes section within 2 days — do not use Comments.

SUGGESTED TICKET TITLE
[AP][ODS][Core][Fail] ap_addr_ods_core_news_ent_hourly_dq_prod
Ref: https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard

ADINC FIELDS (copy into Support Bot)
INC_NUMBER:     NA
TEAM:           ads-data-support
PIPELINE:       ODS - Data Core
DAG:            ap_addr_ods_core_news_ent_hourly_dq_prod
TASK:           enriched_pod_fill_sensor
SOURCE_SYSTEM:  ODS - Data Core
ISSUE_CATEGORY: Data - Upstream Delay
EXTERNAL:       N
MISSED_SLA:     
PD_ID:          5702691

DEV INPUT NEEDED
• TASK — confirm leaf: enriched_pod_fill_sensor vs upstream f_pod_fill_enriched producer
• SOURCE_SYSTEM — confirm: ODS - Data Core | Waiting for RCA
• ISSUE_CATEGORY — confirm: Data - Upstream Delay | Data - DQ | Waiting for RCA
• MISSED_SLA — Y/N did hourly News/ENT DQ miss SLA?
```

### Example ADINC block (#5546450 — ODS Metrics DQ) — legacy reference

```
ADINC — @oncall-ods-metrics please create ADINC Ticket
Data Ops suggests values below. DEV team: create the ADINC ticket via Support Bot (/support).

DEV RESPONSIBILITIES
• Create via Support Bot (run /support in Microsoft Teams).
• If MISSED_SLA is Y or Yes, set ticket priority to P1.
• Assign the ticket to the DEV on-call or owning DEV engineer (@oncall-ods-metrics).
• Provide RCA in the ticket's General → Notes section within 2 days — do not use Comments.

SUGGESTED TICKET TITLE
[AP][ODS][Metrics][Fail] ap_addr_ods_metrics_mc_metadata_dq_prod

ADINC FIELDS (copy into Support Bot)
INC_NUMBER:     NA
TEAM:           ads-data-support
PIPELINE:       ODS - Metrics
DAG:            ap_addr_ods_metrics_mc_metadata_dq_prod
TASK:           dq_a_line_item_metrics
SOURCE_SYSTEM:  ODS - Metrics
ISSUE_CATEGORY: Data - DQ
EXTERNAL:       N
MISSED_SLA:     
PD_ID:          5546450

DEV INPUT NEEDED
• SOURCE_SYSTEM — confirm after RCA: ODS - Metrics | Waiting for RCA
• ISSUE_CATEGORY — confirm: Data - DQ | Data - Upstream Delay
• MISSED_SLA — Y/N did MC Metadata metrics pipeline miss SLA?
```

## Incident agent note format

Notes from PagerDuty Incident agent follow this structure:

```
[Incident agent — automated summary]

Root cause:
{paragraph(s)}

Evidence from tools:
- **{label}**: {detail}
- ...

Recommendations:
- **{action}**: {detail}
- ...
```

Author attribution in API: note `user.summary` may show the agent owner (e.g. "Maksym Ivashchenko") — do not treat as human on-call unless content lacks the agent prefix.

## Human vs agent notes

| Prefix | Type | Use |
|--------|------|-----|
| `[Incident agent — automated summary]` | Agent | Root Cause / Key Evidence / AI Agent Recommendations |
| Anything else | Human | Resolution quotes, manual actions |

## Similar-incident search

**Default: tiered search (fast).** Full 90d pagination is **opt-in only** — it can take 5–10+ minutes and rarely changes the report.

| Tier | Lookback | Max pages | Use when |
|------|----------|-----------|----------|
| 1 | 30 days | 1 | Every analysis (default) |
| 2 | 90 days | 3 cumulative | Tier 1 returned 0 same-title/job matches |
| 3 | User-specified | 5 max | User asks for deep history |

**Helper script:** `scripts/pd_incident_fetch.py` — fetches incident + notes + alerts + tier-1 similar in one call (~5–15s). Example:

```bash
python ~/.cursor/skills/dataops-pd-incident-analysis/scripts/pd_incident_fetch.py 5794432
python ~/.cursor/skills/dataops-pd-incident-analysis/scripts/pd_incident_fetch.py 5794432 --similar-days 90 --max-pages 3
```

Client-side filter on `list_incidents` results (API has no text search):

```python
# Pseudocode
same_title = normalized(summary) == normalized(current.summary)
same_job   = job_name in incident.title
same_run   = run_id and f"@databricks_job_run_id:{run_id}" in incident.title
```

When job name appears in multiple alert types (Fail vs Long Run), still match on job — group by alert subtype in the report if helpful.

## Resolution inference (past incidents)

Use this priority when writing "How it was resolved":

1. **Human note** explicitly stating fix (repair run, re-run, config change, acknowledged as benign, etc.) — quote ≤200 chars.
2. **Agent Recommendations** from that past incident if step 1 is empty and recommendations mention concrete closure actions taken.
3. **Agent Root cause** only if it states the issue "self-resolved" or downstream recovered.
4. **Fallback:** "Resolved at {resolved_at PT}. No resolution notes in PagerDuty."

Never claim a specific fix without note evidence.

## Databricks analysis

### When to run

| Incident type | DBX step |
|---------------|----------|
| Fail / Long Run with `job_name:` or `service:` | Full analysis (Step 4) |
| Dag Change, LDB Long Run, Goldmine DAG | Skip — no DBX job in title |

### Workspace resolution

Try prod workspaces in order until `get_run_details` succeeds (no `error`):

1. `sox-prod-uw2`
2. `gen-prod-uw2`
3. `sox-prod-ue1`, `gen-prod-ue1` (fallback)

### Databricks URL templates

| Workspace | Org ID | Host |
|-----------|--------|------|
| sox-prod-uw2 | `3352005904589238` | `https://ads-data-sox-prod-uw2.cloud.databricks.com` |
| gen-prod-uw2 | `161202889771344` | `https://ads-data-gen-prod-uw2.cloud.databricks.com` |

**Run URL:** `{host}/?o={org_id}#job/{job_id}/run/{run_id}`

Prefer `run_page_url` from `get_run_details`.

### MCP tool sequence

| Order | Tool | Purpose |
|-------|------|---------|
| 1 | `get_run_details(workspace, run_id)` | Workspace, job_id, run state, task list, run_page_url |
| 2 | `analyze_job_task_failure(workspace, run_id)` | Failed tasks **per attempt**; search all for leaf error |
| 3 | `get_run_output(workspace, task_run_id)` | **Required** when wrapper-only error or logs truncated — use **task** run_id per attempt |
| 4 | `list_jobs(workspace, name_filter=…)` | Resolve job_id when title has no run ID |
| 5 | `list_job_runs(workspace, job_id=…)` | Pick run nearest incident time for Long Run alerts |
| 6 | `get_job_details(workspace, job_id=…)` | Schedule, timeout_seconds (Long Run context) |
| 7 | `identify_stuck_runs(workspace)` | Optional — hung runs |

### Upstream run extraction (from agent note)

Regex patterns (collect all, dedupe):

- `Run ID:\s*(\d+)`
- `run_id:\s*(\d+)`
- `@databricks_job_run_id:(\d+)`
- `parent run_id:\s*(\d+)`

Cross-reference with job names in the agent text (backtick job names or `job \`name\``).

### Log output rules

- Quote error text **verbatim** from MCP (exceptions, `state_message`, cluster termination reasons).
- One row per failed task in the Failed tasks table; include **attempt number** when retries differ.
- Under **Log / error output**, group by `task_key`; include the **leaf error** per [Leaf error extraction](#leaf-error-extraction).
- Truncate displayed stack traces at ~500 chars with `(truncated)` — full detail is in DBX UI via run link.
- Highlight infra patterns: `AWS_RESOURCE_QUOTA_EXCEEDED`, `VcpuLimitExceeded`, `TIMEDOUT`, `UPSTREAM_FAILED`.

### Leaf error extraction

**Purpose:** DEV handoffs and Root Cause must state the error the owning team can act on — not JVM/DBX wrappers or incidental stack-trace lines.

#### Wrapper errors — never report as root cause

These appear in MCP `error` / `error_trace` top lines but are **not** the leaf failure:

| Wrapper | Why it misleads |
|---------|-----------------|
| `ExitSecurityException: Program attempted to exit with code 1` | Finagle/Twitter `App.exitOnError` — common in JAR jobs (`MRCHourly`, etc.) |
| `TrapExitSecurityManager.checkExit` / `System.exit` | Same — JVM shutdown after real Spark/app error |
| `Workload failed, see run output for details` | DBX generic task message |
| `Run result unavailable: The task was skipped…` | Skipped task, not leaf |

When you see a wrapper → search `logs`, `metadata`, and **all retry attempts** for the real exception.

#### Mandatory scan procedure

1. `get_run_details` → identify leaf failed `task_key` and every `attempt_number`.
2. `analyze_job_task_failure` → one entry per attempt; **scan all entries** for that `task_key`.
3. Search **full text** of `error`, `error_trace`, `logs`, `metadata`, `notebook_output` on each attempt.
4. Regex / string search (case-sensitive codes in brackets):

   | Pattern | Example leaf error |
   |---------|-------------------|
   | `ExtendedAnalysisException:\s*\[[A-Z0-9_]+\]` | `[TABLE_OR_VIEW_NOT_FOUND]` |
   | `AnalysisException:` | Spark SQL analysis failures |
   | `UnknownHostException` | Vault DNS (`secrets.prod.hulu.com`) |
   | `PERMISSION_DENIED` | Cluster policy / IAM |
   | `AWS_RESOURCE_QUOTA_EXCEEDED` / `VcpuLimitExceeded` | vCPU quota |
   | `Exception: Not ready to process` | Partition / pipeline_status sensor |
   | `Exception: NOT_FOUND` | Named partition missing |
   | `ConstraintViolation` / Deequ | DQ check failure |

5. Prefer the **highest-priority** match below. If tied, prefer the error that **recurs across retry attempts**.
6. Include the **triggering line** when present (line immediately above the exception), e.g.:

   ```
   >>> Execute sql: SELECT ID FROM INPUT_TABLE_1352818856 THIS WHERE rule_marker == 6
   org.apache.spark.sql.catalyst.ExtendedAnalysisException: [TABLE_OR_VIEW_NOT_FOUND] ...
   ```

7. If `logs` empty/truncated → **one** `get_run_output(workspace, task_run_id)` per failed task. If still empty and task is `*_sensor` / for_each → follow [Sensor / for_each fast path](#sensor--for_each-fast-path) below.

#### Sensor / for_each fast path

When the leaf task is an **S3/partition/job sensor** or a **for_each** wrapper (`Some iterations failed`) and MCP cannot return iteration notebook logs:

| Source | What to report (verbatim or from metadata) |
|--------|-------------------------------------------|
| `analyze_job_task_failure` | `task_key`, `state_message`, for_each `inputs`, `failed_iterations` / `succeeded_iterations` |
| Prior hour run | One `get_run_details` on previous successful periodic run — compare sensor duration |
| PD alert body | `Failed: Task …`, workspace, runbook URL |
| Runbook | Sensor-failure RCA (e.g. upstream S3 missing for `utc_hour`) + escalation `@` tag |

**Action plan must include:** DBX URL to the **failed task run** (not only parent job run) so DEV can open the failed for_each branch.

**Do not:** paginate `list_job_runs`, brute-force child run IDs, or retry Datadog/`dbx` CLI after one empty result.

#### Leaf error priority (pick highest tier found)

| Tier | Error type | Report as root cause? |
|------|------------|------------------------|
| 1 | Spark `ExtendedAnalysisException` / `AnalysisException` with `[ERROR_CODE]` | **Yes — preferred** |
| 2 | Named infra/auth: `UnknownHostException`, `PERMISSION_DENIED`, `AWS_RESOURCE_QUOTA_EXCEEDED`, `VcpuLimitExceeded` | **Yes** |
| 3 | Sensor / upstream: `Not ready to process`, `NOT_FOUND … partition`, `No successful job or task run found` | **Yes** (when sensor is leaf) |
| 4 | DQ: Deequ `ConstraintViolation`, explicit DQ assert messages | **Yes** |
| 5 | Delta concurrency: `MetadataChangedException`, `ConcurrentCreateExceptions` | Only if **no tier 1–4** on any attempt |
| — | Wrappers (`ExitSecurityException`, generic workload failed) | **Never** |

#### Anti-pattern — #5703545 / #5703547 (Aug 2026)

| Wrong (wrapper / tail inference) | Correct (leaf, attempts 1–3) |
|----------------------------------|------------------------------|
| `MetadataChangedException` / `ConcurrentCreateExceptions` from attempt 0 log tail | `ExtendedAnalysisException: [TABLE_OR_VIEW_NOT_FOUND] The table or view \`INPUT_TABLE_1352818856\` cannot be found` on DQ rule `rule_marker == 6` |
| "Delta write concurrency between concurrent publisher jobs" | Temp view not registered before DQ rule — same error on **both** HUP and Disney+ MRC hourly runs |

**Lesson:** Attempt 0 ran ~13 min and logged Delta stack frames at the end; **retries 1–3** held the actionable Spark error DEV copied from the DBX UI. Always scan **all attempts** before DEV handoff.

#### Failed tasks table — Error summary column

Use **one short leaf line**, not the wrapper:

| Bad | Good |
|-----|------|
| `ExitSecurityException: Program attempted to exit with code 1` | `[TABLE_OR_VIEW_NOT_FOUND] INPUT_TABLE_1352818856 (rule_marker == 6)` |
| `MetadataChangedException` (from stack tail only) | `UnknownHostException: secrets.prod.hulu.com` |
| `Workload failed, see run output for details` | `Exception: Not ready to process` (sensor) **or** for_each stats + runbook sensor RCA (see fast path) |

## Performance budgets

| Step | Target time | Notes |
|------|-------------|-------|
| PD fetch (Steps 1–3) | &lt; 20s | MCP parallel or `pd_incident_fetch.py` |
| DBX primary run (Step 4) | &lt; 60s | 2–3 MCP calls; parallel workspace probe |
| Similar incidents (Step 5) | &lt; 30s tier 1 | Notes for ≤5 matches only |
| **Total** | **&lt; 3 min** | Sensor fast path if logs unavailable |

### Example DBX excerpt (#5548051)

**Primary:** `ap_addr_audience_hulu_fandom_serving_prod` — gen-prod-uw2 — run `344473032276319` — FAILED

| Task key | State | Error summary |
|----------|-------|---------------|
| `hulu_fandom_inbound_job_sensor` | FAILED | `No successful job or task run found, not ready` (attempt 48) |

**Related upstream:** `ap_addr_audience_hulu_fandom_inbound_prod` — gen-prod-uw2 — run `447313802235465`

| Task key | State | Error summary |
|----------|-------|---------------|
| `segment-data-loading-app` | FAILED | Workload failed — see run output |

## Example output excerpt

For `#5548051` / `ap_addr_audience_hulu_fandom_serving_prod`:

**Root Cause:** `hulu_fandom_inbound_job_sensor` exhausted 49 retries waiting for inbound run `447313802235465`.

**Similar past — Same job:**

#### [#5546167](...) — Jul 20, 2026 9:31 AM PT — Resolved

- **Root cause (agent):** Upstream `ap_addr_audience_hulu_fandom_inbound_prod` run 447313802235465 failed (`segment-data-loading-app`).
- **How it was resolved:** Resolved at Jul 20, 2026 11:14 AM PT; inbound pipeline failure blocked serving sensor (same upstream run family).
- **Relevant notes:** —

## MCP tools used

| Tool | Server | Purpose |
|------|--------|---------|
| `get_incident` | PagerDuty | Look up PD# / ID — then [identity gate](../pagerduty-incident-identity/reference.md) |
| `list_alerts_from_incident` | PagerDuty | Alert custom details — **Job Runbook URL**, DBX/trace links |
| `confluence_search_content` | Confluence | CQL search for runbook under Data Pipelines (`192841195`) |
| `list_incident_notes` | PagerDuty | Agent summary + human notes |
| `list_incidents` | PagerDuty | Historical similar-incident search |
| `get_run_details` | ads-databricks | Workspace, run state, tasks, run URL |
| `analyze_job_task_failure` | ads-databricks | Failed tasks + error output |
| `get_run_output` | ads-databricks | Task-level logs when needed |
| `list_jobs` / `list_job_runs` | ads-databricks | Long Run run resolution |
| `get_job_details` | ads-databricks | Job timeout / schedule |
| `identify_stuck_runs` | ads-databricks | Optional hung-run check |
