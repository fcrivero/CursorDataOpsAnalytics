---
name: dataops-pd-incident-analysis
description: >-
  Analyzes a single PagerDuty Data Ops incident: fetches the [Incident agent —
  automated summary] note, enriches with Databricks job/run failure analysis via
  ads-databricks MCP (workspace, failed tasks, logs), renders Root Cause / Key
  Evidence / AI Agent Recommendations / On-Call Action Plan, and finds similar past incidents (same title or
  job/run) with how they were resolved. Use when the user asks to analyze one PD
  incident, investigate an incident agent summary, root cause for PD#, DBX logs
  for a failed run, past resolution for a failed job, or an MS Teams on-call
  handoff message for a Data Ops incident. Applies mandatory leaf-error extraction
  (Step 4b-leaf) so DEV handoffs quote Spark/application errors, not wrappers like
  ExitSecurityException. ADINC block suggests allowlist-valid fields for DEV to file
  via Support Bot (/support) — Data Ops does not create ADINC tickets. Extracts Job Runbook URL from PagerDuty
  alert custom details, with Confluence Data Pipelines search as fallback. Renders
  a concise MS Teams handoff, On-Call Action Plan in the full report, and a
  separate ADINC block for Jira description fields with dev-input flags.
---

# Data Ops PD Incident Analysis

Analyze **one** PagerDuty incident: parse the Incident agent automated summary, enrich with Databricks job/run failure details, then find similar past incidents and how they were closed in the past.

**Read-only:** this skill looks up and analyzes incidents — it does **not** change PagerDuty incident status.

**Microsoft Teams only:** ADINC and Support Bot guidance in this skill assumes **Microsoft Teams** (`/support`, `/incident`, on-call handoffs). Do not mention Slack in outputs or templates.

## Performance (mandatory)

Target **under 3 minutes** wall time for a standard Fail alert. Accuracy rules (identity gate, leaf errors, allowlists) are unchanged — optimize **how** data is fetched, not **what** is reported.

| Phase | Fast path | Never do |
|-------|-----------|----------|
| **PD fetch** | MCP `get_incident` + parallel `list_incident_notes` / `list_alerts_from_incident` | `GET /incidents?incident_number=`; unbounded REST pagination |
| **MCP down** | Run [scripts/pd_incident_fetch.py](scripts/pd_incident_fetch.py) once (`python …/pd_incident_fetch.py {pd#}`) | Hand-write one-off fetch scripts; paginate 90d of all incidents |
| **DBX** | `get_run_details` + `analyze_job_task_failure` on primary run (parallel when workspace unknown: try sox + gen) | `list_job_runs` with default limit 1600+; retry `get_run_output` more than **once** per task when logs are null |
| **Similar incidents** | **Step 5 tiered search** (below) — default **30d, 1 page** | Full 90d pagination until window covered |
| **Datadog / CLI** | Skip if ads-databricks MCP already has leaf error | Retry `pup`, `dbx`, or Datadog MCP after one empty/error result |
| **Confluence** | Only when PD alert has no runbook URL | Search Confluence when runbook already in alert body |
| **for_each / S3 sensor** | **Step 4b-sensor** fast path when iteration logs unavailable | Brute-force child run IDs or Datadog span hunting |

**Parallelize after Step 1-verify:** launch DBX `get_run_details` (or `analyze_job_task_failure`) in the same turn as PD notes/alerts when run ID is known from title or alert body.

## Prerequisites

1. **PagerDuty MCP** (`user-pagerduty-mcp-manual`) — token in `~/.cursor/mcp.json`. Stop and guide setup if missing.
2. **ads-databricks MCP** — required when the incident involves a DBX job (Fail/Long Run monitors). If unavailable, render the PD sections and note that DBX enrichment was skipped.
3. **Confluence MCP** (`user-confluence-disney`) — optional fallback to resolve runbook URL from [Data Pipelines](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841195/Data+Pipelines) when PD alert has no runbook link. If unavailable, leave runbook as `—`.

Always call `GetMcpTools` before `CallMcpTool`.

Shared config (services, title parsing, DBX): [reference.md](reference.md)

**Incident identity (mandatory):** [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md) — identity gate before every fetch; never mutate without verified `incident_number` + UUID.

## Input — look up one incident

Accept **any one** of these (ask if ambiguous or multiple matches):

| Input type | Examples | Lookup |
|------------|----------|--------|
| **PD#** | `5548051`, `#5548051` | `get_incident` with `incident_id` = number |
| **PD URL** | `https://disney.pagerduty.com/incidents/Q1ZJYTU763M6O0` | Extract ID from path after `/incidents/` |
| **Alert URL** | `https://disney.pagerduty.com/alerts/Q05YTAE59W0O08` | Extract alert ID from path after `/alerts/` — see **Step 1a** (do **not** guess incident from conversation context) |
| **Title fragment** | `[AP][ADM][segmentation][Fail] ap_addr_audience_hulu_fandom_serving_prod` | Search past incidents (Step 5 window), pick best title match; if several, list candidates and ask |
| **Job / run name** | `ap_addr_audience_hulu_fandom_serving_prod`, run `344473032276319` | Search incidents whose title contains the job name or run ID |

If the user gives a job name and multiple open/recent incidents match, prefer the **most recent** unless they specified a PD# or URL.

## Workflow

### Step 1a — Resolve alert URL to incident (when input is an alert link)

Extract `alert_id` from `https://disney.pagerduty.com/alerts/{alert_id}`.

The MCP has no standalone "get alert by ID" — locate the parent incident:

1. `list_incidents` on both Data Ops services for the **last 7 days** (expand to 90d if not found).
2. For each candidate incident, `list_alerts_from_incident` with incident **UUID** and `query_model: {}`.
3. Match `response[].id == alert_id`.
4. On match: set `incident_id` from `alert.incident.id`, keep the matched alert for Step 1b, then continue Step 1.

If still not found, ask the user for the incident PD# or URL.

**Never** substitute a different incident based on prior conversation context or a similar-looking job/run.

When `incident_id` is set from an alert, still run **Step 1-verify** — if the user also supplied a PD#, assert `incident_number` matches.

### Step 1 — Fetch incident

**Prefer MCP** (single call):

```json
CallMcpTool user-pagerduty-mcp-manual get_incident
{ "incident_id": "<id_or_number>" }
```

**MCP fallback** (when `get_incident` / `list_incident_notes` unavailable — e.g. `tool_groups (full-api)` error):

```bash
python ~/.cursor/skills/dataops-pd-incident-analysis/scripts/pd_incident_fetch.py <pd#>
```

Optional: `--similar-days 90 --max-pages 3` only when user asks for deep past context or Step 5 tier-1 finds zero matches.

The script returns `incident`, `verified_uuid`, `notes`, `alerts`, `parsed` (job, run_id, runbook_url, workspace), and `similar`. Use `parsed` before re-parsing alert bodies manually.

Record: `id`, `incident_number`, `title`, `summary`, `status`, `created_at`, `resolved_at`, `service`, `assignments`.

### Step 1-verify — Identity gate (MANDATORY before Step 1b+)

Immediately after fetch, run checks from [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md):

1. If user gave **PD#**: `String(incident_number) == String(expected_incident_number)`.
2. If user gave **URL/UUID**: `id == expected_uuid`.
3. If user gave **job/DAG only**: title contains expected token; if `list_incidents` returned multiple matches, **stop and ask** — do not pick the first row.
4. `service.id` is `P7OFL7L` or `P3CUKVY` (Data Ops) unless user explicitly asked about another service.

On failure: **abort** — report what the API returned vs what was requested; do not analyze or write to a different ticket.

Store `verified_uuid` = `id` — use **only** this for `list_alerts_from_incident`, notes, and any user-requested writes.

PD link: `https://disney.pagerduty.com/incidents/{verified_uuid}`

Extract **job name** and **run ID** from title — see [reference.md](reference.md#title-parsing).

Derive **Team** and **Oncall MS Teams Tag** from the PagerDuty incident **`title` only** — see [reference.md](reference.md#team-and-on-call-tags). **Bracket subtitles in the title** (`[Segmentation]`, `[Targeting]`, `[Metrics]`, …) **supersede** job-name keywords (`audience`, `fandom`, etc.); never route from job name when the title already names subteam. Use `TBD` / `—` for Dag Change and unmatched titles.

### Step 1b — Fetch alert custom details (runbook URL)

Use the incident **`id`** (UUID from Step 1) — **not** `incident_number` (`#5546450` returns 404).

```json
CallMcpTool user-pagerduty-mcp-manual list_alerts_from_incident
{ "incident_id": "<uuid>", "query_model": {} }
```

From the alert in `response[]`, read the Datadog custom-details **`body`** string. When the user supplied an **alert URL**, use the matched alert from Step 1a; otherwise use the first alert.

| Path (try in order) | Field |
|---------------------|-------|
| `body.details.body` | Primary |
| `body.cef_details.details.body` | Fallback |

Parse the markdown body — see [reference.md](reference.md#alert-custom-details-runbook-url):

| Field | Use |
|-------|-----|
| **Runbook URL** | `[Link to Job Runbooks]( URL )` or Goldmine `_Runbook: [Runbook]( URL )` — see reference |
| Job / Run / Workspace | Supplement title parsing when present |
| Databricks page URL | Cross-check against DBX MCP `run_page_url` |
| Job Trace / Data Pipelines | Optional links in full report |

If no alerts, empty `body`, or no runbook link: leave `runbook_url` unset for Step 2b (do not invent a URL).

### Step 2 — Fetch Incident agent summary

```json
CallMcpTool user-pagerduty-mcp-manual list_incident_notes
{ "incident_id": "<id>" }
```

Find the note whose `content` starts with `[Incident agent — automated summary]`.

Parse into three sections (case-insensitive headers):

| Section | Header in note | Output heading |
|---------|----------------|----------------|
| Root cause | `Root cause:` | ## Root Cause |
| Evidence | `Evidence from tools:` | ## Key Evidence |
| Actions | `Recommendations:` | ## AI Agent Recommendations |

**Parsing rules:**

- Strip the `[Incident agent — automated summary]` prefix and leading blank lines.
- Split on the headers above; each section body is markdown — preserve bullets, backticks, and links.
- Under **Key Evidence**, keep bullet list items as-is (do not flatten).
- Under **AI Agent Recommendations**, keep numbered list as-is.

If **no agent note** exists: say so clearly, then use `title` + any **human notes** (notes not starting with `[Incident agent`) as a fallback under a `## Available Notes` section. Do not invent root cause.

### Step 2b — Resolve runbook URL (fallback)

Run when `runbook_url` is still unset after Step 1b. Skip when there is no DBX **job name** (Dag Change, LDB-only, Goldmine DAG).

**Priority order:**

| Priority | Source | Action |
|----------|--------|--------|
| 1 | Step 1b PD alert | Already set — skip Step 2b |
| 2 | Agent note | Regex first `https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/\d+[^\s\)]*` in Recommendations or full note; set `runbook_source` = `agent note` |
| 3 | Confluence search | See [reference.md](reference.md#confluence-runbook-fallback) — set `runbook_source` = `Confluence (Data Pipelines)` |

**Confluence fallback** (`user-confluence-disney`) — only when priorities 1–2 found nothing:

```json
CallMcpTool user-confluence-disney confluence_search_content
{ "cql": "ancestor = 192841195 AND title ~ \"{job_or_stem}\"", "limit": 10 }
```

Retry with `text ~ "{job_name}"` if title search returns no ranked match. Build URL: `https://disney-enterprise.atlassian.net/wiki{result._links.webui}`.

Record `runbook_source` in the full report (e.g. `PagerDuty alert`, `agent note`, `Confluence (Data Pipelines)`). If still no match: `runbook_url` = `—`, `runbook_source` = `not found`.

### Step 3 — Fetch all notes for context

From the same `list_incident_notes` response, collect **human notes** (content does **not** start with `[Incident agent`).

Use these only to supplement the current incident header (e.g., manual resolution comments). Do not duplicate the agent summary in the output.

### Step 4 — Databricks job/run analysis

Run when a **DBX job name** is extracted from the incident title (skip for Dag Change, LDB-only, or Goldmine/Airflow-only alerts with no DBX job).

See [reference.md](reference.md#databricks-analysis) for workspace order, tools, and upstream-run extraction.

**4a — Resolve workspace and primary run**

| Situation | Actions |
|-----------|---------|
| **Run ID in title** | `get_run_details` on `sox-prod-uw2`, then `gen-prod-uw2` until found (no `error` field) |
| **No run ID (Long Run)** | `list_jobs(name_filter=job_name)` on sox then gen → `list_job_runs(job_id=…, limit=25)` → pick run whose start time is closest to incident `created_at` |
| **Job only in user input** | Same as above using supplied job name |

Record: `workspace`, `job_id`, `job_name`, `run_id`, `run_page_url`, parent `state` (`result_state`, `state_message`).

**4b — Analyze failure and logs**

For the primary run (and each related upstream run — Step 4c):

```json
CallMcpTool user-ads-databricks analyze_job_task_failure
{ "workspace": "<workspace>", "run_id": <run_id> }
```

From the response, extract and show:

- Overall run state and failure message
- **Failed tasks** — `task_key`, task `run_id`, `result_state`, `state_message`
- **Leaf error** — see **Step 4b-leaf** below (mandatory before any DEV handoff)
- Stack traces — show first ~500 chars per task; note if truncated by MCP (2000 char limit)

If `analyze_job_task_failure` returns no failed tasks but run state is FAILED/TIMEDOUT, call:

```json
CallMcpTool user-ads-databricks get_run_output
{ "workspace": "<workspace>", "run_id": <failed_task_run_id> }
```

Use the failed task's `run_id` from `get_run_details.tasks[]`, not always the parent run ID.

**4b-leaf — Leaf error extraction (MANDATORY before DEV handoff)**

DEV handoffs, **Root Cause**, **On-Call Action Plan**, and **MS Teams ROOT CAUSE** must quote the **leaf application/Spark error** — never a wrapper. Full rules: [reference.md](reference.md#leaf-error-extraction).

**Always do this after `analyze_job_task_failure`:**

1. **`get_run_details`** — list every failed task and **every retry attempt** (`attempt_number` 0, 1, 2, …).
2. **Scan all attempts** — `analyze_job_task_failure` returns one row per attempt. Search **all** rows for the leaf task (e.g. `hourly_mrc_job`), not just attempt 0.
3. **Search all text fields** on each attempt: `error`, `error_trace`, `logs`, `metadata`, `notebook_output`. Search the **full** string — do not use log tail only.
4. **Select leaf error** using the priority table in reference.md. The line DEV can act on (often `ExtendedAnalysisException: [ERROR_CODE] …` or the `Execute sql:` line immediately above it) wins over infra stack traces.
5. **If top-level `error` is a wrapper** (`ExitSecurityException`, `Program attempted to exit with code 1`, bare `Workload failed, see run output`) — you **must** dig deeper; do not report that as root cause.
6. **Optional confirm** — `get_run_output(workspace, task_run_id)` for the attempt that contains the leaf error when `logs` were truncated or empty in step 2. **At most one** `get_run_output` per failed task — if `logs` is null, proceed to **4b-sensor** or report wrapper + DBX UI link.

**4b-sensor — for_each / S3 / partition sensor fast path (accuracy-preserving)**

Apply when **all** of:

- Failed `task_key` matches `*_sensor`, `s3_sensor`, or `for_each` wrapper message (`Some iterations failed`)
- `analyze_job_task_failure` shows `for_each` stats (`failed_iterations`, `succeeded_iterations`, `inputs`) **or** sensor timeout pattern (run duration ≫ prior successful hour)
- `get_run_output` returned null/empty on first attempt

**Then (do not retry Datadog, dbx CLI, or child-run brute force):**

1. Quote **verbatim** the for_each state message and stats from `analyze_job_task_failure` metadata (failed count, input list).
2. Compare to **prior successful run** on same job if incident time − 1h: one `get_run_details` on previous periodic run is enough.
3. Apply **runbook RCA** when alert links a sensor runbook (e.g. Drax Deals — upstream S3 file missing for `utc_hour`). Cite runbook section + escalation tag (`@oncall-adserver-lemonade`, etc.).
4. State in ROOT CAUSE / action plan: open failed task run in DBX UI to identify **which for_each branch** failed and exact S3 path — this is actionable for DEV without inventing a path.
5. **DEV handoff gate satisfied** when tier-3 sensor RCA is documented with task_key, for_each stats, runbook link, and DBX task run URL — even if iteration notebook logs are unavailable via MCP.

**Hard rules:**

- **Never** put `ExitSecurityException` / `System.exit` / `TrapExitSecurityManager` in Root Cause or DEV messages.
- **Never** infer root cause from stack-trace tail (e.g. Delta `MetadataChangedException`) when a clearer `ExtendedAnalysisException` / `AnalysisException` exists on any attempt.
- **Always** quote the leaf error **verbatim** (including Spark error codes like `[TABLE_OR_VIEW_NOT_FOUND]`).
- When the same leaf error appears on multiple retry attempts, state that — it confirms a stable failure mode, not a one-off retry glitch.

**4c — Related upstream runs from agent summary**

Parse the agent note (Root cause + Evidence) for additional run IDs:

- `Run ID: (\d+)`, `run_id: (\d+)`, `@databricks_job_run_id:(\d+)`
- Upstream job names mentioned with a run (e.g. `ap_addr_audience_hulu_fandom_inbound_prod`)

Deduplicate against the primary run. For each distinct upstream `(job_hint, run_id)`:

1. `get_run_details` (sox then gen) to confirm workspace
2. `analyze_job_task_failure` for that run
3. Summarize under **Related upstream runs** in the output

**4d — Long Run / no hard failure**

If the incident is Long Run and the run is still `RUNNING` or succeeded but slow:

- Report run duration vs `timeout_seconds` from `get_job_details` if useful
- Optionally `identify_stuck_runs` on the workspace when run appears hung

If ads-databricks is down: set DBX section to "Skipped — ads-databricks MCP unavailable" and continue with PD-only sections.

### Step 5 — Find similar past incidents

**Tiered search (mandatory)** — stop as soon as enough matches exist; never paginate the full window by default.

| Tier | When | Lookback | Pages | Stop when |
|------|------|----------|-------|-----------|
| **1** | Default | **30 days** | **1** (`limit=100`) | ≥3 same-title or same-job matches, or page exhausted |
| **2** | Tier 1 found 0 same-title/job | **90 days** | **+2** pages max | ≥3 matches or 3 pages fetched |
| **3** | User asks "deep history" / "6 months" | User window | **5 pages max** | 15 matches total |

Use MCP `list_incidents` **or** `pd_incident_fetch.py` (`--similar-days 30` default; `--max-pages 3` for tier 2). Client-side filter only — API has no text search.

**Exclude** the current incident. Classify matches:

| Priority | Match rule | Label |
|----------|------------|-------|
| 1 | Exact same `title` (ignore `[#NNNN]` prefix in `summary`) | Same title |
| 2 | Same **job name** extracted from title | Same job |
| 3 | Same **run ID** in title (rare) | Same run |

Include up to **5** past incidents per match tier (15 max total). Sort each tier by `created_at` descending. Prefer **resolved** incidents when summarizing how issues were fixed.

For each similar incident (max **5** to fetch notes for — pick most recent per tier):

1. `list_incident_notes` for that incident's `id`.
2. Extract agent summary (same parsing as Step 2) — one-line root cause if present.
3. Extract **resolution signal** from:
   - Human notes (any note not from Incident agent)
   - Agent **Recommendations** if they mention repair-run, re-run, skip, acknowledged, or resolved
   - `resolved_at` and `status`

**Resolution summary** for each past incident (2–4 sentences):

- What failed (from agent root cause or title)
- How it was closed (human note quote or inferred action from recommendations)
- If no notes and only auto-resolved: state "Resolved at {time PT}; no human or agent resolution notes recorded"

Link each past incident: `[#5548051](https://disney.pagerduty.com/incidents/{id})`.

### Step 6 — Synthesize on-call action plan and past context

Before rendering output, prepare sections for the **full report** and **MS Teams message**:

**ON-CALL ACTION PLAN** (3–6 bullets) — rendered in the **full analysis report** under `## On-Call Action Plan`, from DBX MCP + your analysis only:

1. **Leaf failure** — failed `task_key`, **verbatim leaf error from Step 4b-leaf** (not wrapper), attempt number if relevant, workspace/run link
2. **Fix order** — upstream before downstream (sensors, dependencies)
3. **Concrete commands** — job IDs, repair-run task name, **runbook URL** (Steps 1b / 2b), escalation

**Do not repeat** bullets from the agent's Recommendations unless you add **new** detail (run ID, task key, log quote, PD#). If an agent bullet is generic ("investigate inbound"), the action plan should instead state **what DBX found** and **exact re-run sequence**.

**DEV handoff gate:** Before rendering MS Teams or any message for `@oncall-*`, verify bullet 1 uses the Step 4b-leaf error **or** a completed **4b-sensor** RCA (for_each stats + runbook + DBX task URL). If you only have a generic wrapper with no sensor/fast-path context, go back to Step 4b-leaf once — do not loop on external tools.

**PAST CONTEXT** (2–5 bullets) — rendered in the **MS Teams message** only, from similar-incident search (Step 5):

- Recurring pattern (count, date range)
- Prior PD# with same root cause or resolution (human notes, maintenance, repair-run)
- One bullet per notable past incident — not a single prose line

### Step 6b — Prepare ADINC fields (DEV-owned ticket)

Populate the 10 ADINC description fields for the separate **ADINC** output block (Step 7c). **Data Ops does not create ADINC tickets** — DEV creates via **Support Bot** (`/support`).

Field rules must match **`jira-adinc-tickets`** and **`jira-adinc-audit`** allowlists exactly — see [reference.md](reference.md#adinc-block) and [jira-adinc-tickets/reference.md](../jira-adinc-tickets/reference.md).

**RCA (when saving to Jira):** write only to General → Notes (`customfield_10253`) — see [adinc-jira-notes.md](../adinc-jira-notes.md). This step covers the 10 **description** fields, not Notes.

#### Allowlist-only values (mandatory)

| Field | Rule |
|-------|------|
| **TEAM** | Always exactly `ads-data-support` |
| **PIPELINE** | Exact match to [PIPELINE allowlist](../jira-adinc-tickets/reference.md#pipeline) — map from PD title via reference table |
| **ISSUE_CATEGORY** | Exact match to [ISSUE_CATEGORY allowlist](../jira-adinc-tickets/reference.md#issue_category) — never invent categories |
| **SOURCE_SYSTEM** | Exact match to [SOURCE_SYSTEM allowlist](../jira-adinc-tickets/reference.md#source_system), or `NA` when unknown |
| **INC_NUMBER** | Real ServiceNow INC or `NA` |
| **DAG**, **TASK**, **PD_ID** | Job/task/PD# from incident; `NA` when N/A |
| **EXTERNAL** | `Y` or `N` only |
| **MISSED_SLA** | `Y`, `N`, or `NA` — never auto-fill |

When uncertain on an allowlist field, output the **best allowlist guess** (e.g. `Waiting for RCA` for `ISSUE_CATEGORY` or `SOURCE_SYSTEM`) and flag in **DEV INPUT NEEDED** with the allowed alternatives — do **not** embed non-allowlist text in the field value.

#### Suggested ticket title (canonical PD alert taxonomy)

Build from the PD incident **title**, truncated before the first ` on ` (same rule as MS Teams title line). This is the title DEV should use in Support Bot — per [Canonical alert taxonomy](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard).

Examples:

| PD title (full) | Suggested ticket title |
|-----------------|------------------------|
| `[AP][ODS][Core][Fail] ap_addr_ods_core_news_ent_hourly_dq_prod on @databricks_job_run_id:…` | `[AP][ODS][Core][Fail] ap_addr_ods_core_news_ent_hourly_dq_prod` |
| `[AP][BI][Goldmine][Long Run] ap_addr_bi_gen_programmatic_prod on env:prod,…` | `[AP][BI][Goldmine][Long Run] ap_addr_bi_gen_programmatic_prod` |

Optional: also show ADINC Jira summary format (`[AP][ODS][Core]ap_addr_ods_core_news_ent_hourly_dq_prod- short description`) from `jira-adinc-audit` Check 5 **only if** Support Bot requires the hyphen form — default to PD alert taxonomy above.

| Field | Auto-fill when possible | DEV INPUT NEEDED when |
|-------|-------------------------|------------------------|
| **INC_NUMBER** | User-supplied INC or `NA` | Always confirm `NA` vs real INC |
| **TEAM** | `ads-data-support` | Never — fixed value |
| **PIPELINE** | Map from PD title → allowlist value | Ambiguous title or upstream job ≠ alert job |
| **DAG** | DBX `job_name` or Goldmine `dag:` | Dag Change / multi-DAG |
| **TASK** | Leaf failed `task_key` from Step 4b-leaf | Sensor vs upstream leaf unclear |
| **SOURCE_SYSTEM** | Best allowlist match from pipeline + DBX | Always confirm unless agent RCA is explicit |
| **ISSUE_CATEGORY** | Best allowlist match from failure type | Always confirm unless agent RCA is explicit |
| **EXTERNAL** | `N` unless 3P vendor in DBX logs → `Y` | When SOURCE_SYSTEM uncertain |
| **MISSED_SLA** | Never auto-fill | Always — DEV provides Y/N |
| **PD_ID** | `{incident_number}` | Never |

**Marking rules for ADINC block:**

- Field values → **allowlist-valid text only** (no `<<< DEV TO CONFIRM >>>` suffix on the value line)
- Uncertainty → bullet under **DEV INPUT NEEDED** with field name, suggested value, and allowed alternatives
- Unknown enum → use `Waiting for RCA` or `NA` (where allowed) plus DEV INPUT NEEDED to pick final value

After the intro line, include sections in this order: **DEV RESPONSIBILITIES** (first), **SUGGESTED TICKET TITLE**, **ADINC FIELDS**, **DEV INPUT NEEDED**.

### Step 7 — Render report

Produce **three** output blocks in this order:

1. **Full analysis report** (Step 7a)
2. **MS Teams handoff message** (Step 7b) — copy-paste ready for the on-call channel
3. **ADINC block** (Step 7c) — copy-paste ready for Jira ticket drafting

#### Step 7a — Full analysis report

Use this template exactly (omit empty sections with a one-line "None found" where appropriate):

```markdown
# Incident Analysis — #{incident_number}

| Field | Value |
|-------|--------|
| **Title** | {title} |
| **Status** | {Status} |
| **Urgency** | {High or Low from service ID} |
| **Opened** | {created_at PT} |
| **Resolved** | {resolved_at PT or —} |
| **Assignee** | {assignee or —} |
| **Job** | `{job}` or — |
| **Run ID** | `{run_id}` or — |
| **Team** | {ODS / ADM / BI / TBD} |
| **Oncall MS Teams Tag** | {@tag or —} |
| **Runbook** | [Confluence]({runbook_url}) ({runbook_source}) or — |
| **PD link** | [Open in PagerDuty](https://disney.pagerduty.com/incidents/{id}) |

## Root Cause

{parsed root cause from agent note when present; otherwise **Step 4b-leaf** leaf error with task_key and attempt — never wrapper-only. If no agent note: lead with verbatim leaf error, not "No agent note found" alone.}

## Key Evidence

{bullets from agent note when present; otherwise DBX leaf error lines from Step 4b-leaf — task_key, attempt, verbatim exception}

## AI Agent Recommendations

{numbered list from agent note, or —}

## On-Call Action Plan

{3–6 bullets from Step 6 — leaf failure, fix order, concrete run/task IDs, runbook URL, escalation. Do not duplicate AI Agent Recommendations unless adding new DBX detail.}

## Databricks Analysis

{Skip entire section with one line if no DBX job, or MCP unavailable.}

### Primary job/run

| Field | Value |
|-------|--------|
| **Job** | `{job_name}` |
| **Workspace** | `{workspace}` |
| **Job ID** | `{job_id}` |
| **Run ID** | `{run_id}` |
| **Run state** | `{life_cycle_state}` / `{result_state}` |
| **State message** | {state_message or —} |
| **DBX link** | [Run]({run_page_url}) or [Job]({job_url}) |

### Failed tasks

| Task key | Task run ID | State | Error summary |
|----------|-------------|-------|---------------|
| {task_key} | {task_run_id} | {result_state} | {short error from analyze_job_task_failure} |

### Log / error output

{Per **leaf** failed task — bullet with `task_key`, `attempt_number`, and **verbatim leaf error** from Step 4b-leaf. Include the triggering line when present (e.g. `Execute sql: …` immediately before `ExtendedAnalysisException`). Do not quote wrapper-only lines. Truncate long output with "(truncated)".}

### Related upstream runs

{For each upstream run cited by the agent or blocking a sensor — same sub-structure (job, workspace, run state, failed task, key log lines). If none: "None identified."}

## Similar Past Incidents

{If none: "No similar incidents in the last {N} days on Data Ops High/Low urgency services."}

### Same title ({count})

{For each past incident:}

#### [#{number}](https://disney.pagerduty.com/incidents/{id}) — {date PT} — {Status}

- **Root cause (agent):** {one-line or —}
- **How it was resolved:** {resolution summary}
- **Relevant notes:** {quoted human note snippet or —}

### Same job `{job_name}` ({count})

{same sub-structure}

### Same run ID `{run_id}` ({count})

{only if run ID present and matches found; otherwise omit subsection}
```

Display times in **PT** (`Mon DD, YYYY h:mm A PT`) unless the user requests another timezone.

#### Step 7b — MS Teams handoff message

Render a **separate** section `## MS Teams message` immediately after the full report, containing a **single fenced code block** (plain text) the user can copy-paste into Teams. Template: [reference.md](reference.md#ms-teams-handoff-message).

**MS Teams formatting rules:**

- **First line format:** `{pd_title_to_job_or_dag} {oncall_tag}` — see [reference.md](reference.md#ms-teams-title-line).
- **Section order (ALL CAPS headers):** `SUMMARY` → `ROOT CAUSE` → `KEY EVIDENCE` → `PAST CONTEXT` only.
- **Do not include** alert URL — the PD incident link is sufficient (alerts reachable from PD UI).
- **Do not include** `AI AGENT RECOMMENDATIONS` — those live in the full report under `## AI Agent Recommendations`; review and add manually to Teams only if needed.
- **Do not include** `ON-CALL ACTION PLAN` — that lives in the full report under `## On-Call Action Plan`.
- **Do not include** ADINC fields — those live in the separate ADINC block (Step 7c).
- **ROOT CAUSE / KEY EVIDENCE** — must use Step 4b-leaf verbatim error; see [reference.md](reference.md#leaf-error-extraction). Never send `ExitSecurityException` or log-tail inferences to DEV.
- No "(Incident agent)" or other suffixes on ROOT CAUSE / KEY EVIDENCE.
- **PAST CONTEXT** — bullets from similar-incident findings (Step 5); not a single sentence.
- Use plain text inside the code block (no markdown tables — use aligned labels as shown)
- Full URLs on their own lines (Teams auto-links)
- Keep total message concise; truncate log quotes to one line
- If Team is `TBD`, omit `@` tag on first line and note "No on-call tag — route via DataOps" in the full report On-Call Action Plan
- If multiple tags apply (ADM unclear subtitle), append all `@` tags after the title on the first line

#### Step 7c — ADINC block

Render a **separate** section `## ADINC` after the MS Teams message, containing a **single fenced code block** (plain text). Template: [reference.md](reference.md#adinc-block).

Required sections **in order** inside the code block:

1. **ADINC — {@oncall tag} please create ADINC Ticket** — use same DEV on-call tag as MS Teams handoff; one-line note: Data Ops suggests values; DEV files via Support Bot `/support`
2. **DEV RESPONSIBILITIES** — create via Support Bot (`/support`); P1 if SLA missed; assignee; RCA in General → Notes within 2 days
3. **SUGGESTED TICKET TITLE** — truncate PD title at ` on ` (canonical PD alert taxonomy)
4. **ADINC FIELDS** — all 10 fields; allowlist-valid values only
5. **DEV INPUT NEEDED** — bullets for fields DEV must confirm (with allowlist alternatives when helpful)

- Do **not** instruct Data Ops to create the Jira ticket.
- Omit **DEV INPUT NEEDED** only when every field is confirmed (rare).

## Examples

**User:** "Analyze PD 5548051"

→ `get_incident(5548051)` → `list_alerts_from_incident(uuid)` for runbook → agent note → Confluence fallback if needed → DBX analysis → search past incidents.

**User:** "What did the incident agent say for https://disney.pagerduty.com/incidents/Q1ZJYTU763M6O0"

→ Extract `Q1ZJYTU763M6O0` → full report.

**User:** "Past resolutions for ap_addr_audience_hulu_fandom_serving_prod failures"

→ Search by job name → pick most recent incident if not specified → full report with emphasis on Similar Past Incidents.

**User:** "Analyze PD 5548051 and draft MS Teams message"

→ Full report + MS Teams handoff with `@oncall-segmentation` + separate ADINC block.

**User:** "Draft DEV message for PD 5703545"

→ Step 4b-leaf on all `hourly_mrc_job` attempts → quote `ExtendedAnalysisException: [TABLE_OR_VIEW_NOT_FOUND] …` (not `ExitSecurityException` or Delta stack tail) → MS Teams block for `@oncall-adi-data-core`.

## Do not

- Paginate **all** Data Ops incidents for 90 days when searching similar incidents — use Step 5 tiered search (30d / 1 page default).
- Retry Datadog logs, `pup`, or `dbx` CLI after **one** failed or empty attempt when DBX MCP already returned task failure metadata.
- Call `list_job_runs` with large limits to hunt child for_each iterations — use **4b-sensor** instead.
- Write ad-hoc PD fetch scripts per incident — use [scripts/pd_incident_fetch.py](scripts/pd_incident_fetch.py).
- Report **wrapper errors** as root cause (`ExitSecurityException`, `Program attempted to exit with code 1`, generic `Workload failed, see run output`) — always apply Step 4b-leaf or **4b-sensor**.
- Report root cause from **log tail / stack trace alone** when `ExtendedAnalysisException`, `AnalysisException`, or `[ERROR_CODE]` messages exist on any retry attempt.
- Send DEV handoff messages without completing Step 4b-leaf and the DEV handoff gate in Step 6.
- Create ADINC Jira tickets — DEV owns creation via Support Bot `/support`; Data Ops only suggests field values.
- Put non-allowlist text in ADINC `PIPELINE`, `ISSUE_CATEGORY`, or `SOURCE_SYSTEM` field lines — use allowlist values + DEV INPUT NEEDED for uncertainty.
- Invent root cause, log lines, or resolution details not present in PagerDuty notes or DBX MCP responses.
- Change PagerDuty incident status (this skill is read-only) unless the user explicitly asks to resolve/update PD.
- Expose PagerDuty API tokens in output.
- Confuse the current incident with similar ones — always label match reason and PD#.
- Search only High urgency — always use both service IDs `P7OFL7L` and `P3CUKVY` unless the user restricts urgency.
- Invent workspace or run URLs — use MCP `run_page_url` or [reference.md](reference.md#databricks-url-templates).
- Use `incident_number` with `list_alerts_from_incident` — always pass the **verified UUID** from Step 1-verify.
- Skip the identity gate or use `GET /incidents?incident_number=` — use path lookup `GET /incidents/{pd#}` per [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md).
- Reuse a UUID from chat context without re-verifying against the user's PD#.
- Invent runbook URLs — only use PD alert, agent note, or Confluence search hits under [Data Pipelines](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841195/Data+Pipelines).
- Write ADINC RCA to Jira Comments or description — use General → Notes (`customfield_10253`) per [adinc-jira-notes.md](../adinc-jira-notes.md).
