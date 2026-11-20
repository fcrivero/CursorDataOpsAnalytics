---
name: dataops-pd-incident-analysis
description: >-
  **AUTO-TRIGGER:** Use immediately when the user sends only a Data Ops **PD#** (e.g. `6160071`, `#6160071`, `PD 6160071`), a **PagerDuty incident/alert URL**, a **Databricks job name** / DAG, or a **short failure phrase** (`ap_addr_* failed`, `analyze 5548051`) — no need to name this skill or say “analyze”. Read this SKILL.md and run the full workflow in the same turn (Step 0 routes Long Run vs Fail).
  Entry router and analyzer for a single PagerDuty Data Ops incident: after fetch + identity gate,
  classifies alert type (Long Run vs Fail) — **Long Run** → follow dataops-pd-long-run skill; **Fail** →
  this skill’s full RCA workflow. For Fail: fetches PagerDuty notes (human notes;
  legacy automated summary notes are ignored for RCA — see skill body), enriches with Databricks job/run failure analysis via
  ads-databricks MCP (workspace, failed tasks, logs), renders Root Cause / On-Call Recommendation, Datadog CPU/memory resource check (Step 3 —
  before Databricks output), and finds similar past incidents (same title or
  job/run) with how they were resolved. Use when the user asks to analyze one PD
  incident, root cause for PD#, DBX logs
  for a failed run, past resolution for a failed job, or an MS Teams on-call
  handoff message for a Data Ops incident. **Unless the user explicitly asks about Low urgency or names a specific Low-urgency PD#/URL, treat all multi-incident listing, bundling, and “open incidents” analysis as High urgency only** (`P7OFL7L` — see Default scope). Applies mandatory leaf-error extraction
  (Step 4b-leaf) so DEV handoffs quote Spark/application errors, not wrappers like
  ExitSecurityException. ADINC block suggests allowlist-valid fields for DEV to file
  via Support Bot (/support) — Data Ops does not create ADINC tickets. **`## Runbook`** section: PD alert runbook URL vs canonical Confluence metadata+runbook leaf under [Data Pipelines](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841195/Data+Pipelines) (flags missing leaf or team placement mismatch). Searches MS Teams channel ads-data-bi-support for recent threads on the job before DBX. Renders
  a concise MS Teams handoff (plain text, paste-safe), **On-Call Recommendation** in the full report, and a
  separate ADINC block for Jira description fields with dev-input flags.
---

# Data Ops PD Incident Analysis

## Minimal input — auto-start (mandatory for agents)

**The user does not need to invoke a skill by name.** If the message is (or contains) any **single-incident** trigger below, **immediately read this file and execute** Steps 1 → **Step 0** → the routed workflow. Do **not** ask “do you want analysis?” or “which skill?” unless the lookup is **ambiguous** (multiple PD# matches).

| User sends | Agent does |
|------------|------------|
| **PD# only** — `6160071`, `#6160071`, `pd 6160071`, `pagerduty 6160071` | `get_incident` → identity gate → **Step 0** → full output (Long Run triage **or** Fail Step 7a–7c) |
| **PD / alert URL** | Step 1a if alert URL; else `get_incident` → same as above |
| **Job / DAG only** — `ap_addr_ods_metrics_mc_metadata_prod`, `prod-ldb_linear_consumption` | `list_incidents` (`P7OFL7L`, open first, else last 7d) → best title match → same as above |
| **Short failure line** — `analyze 6160071`, `{job} failed`, `check 6160071`, `6160071?` | Treat as PD# or job token; same as above |
| **Bulk** — open queue, shift summary, “all PDs” (no single PD#) | Use **dataops-pd-incidents** / shift skills — **not** this auto-start |

**Do not invoke `dataopsctl`** on minimal-input auto-start (bare PD#, URL, job). Use MCP/skills only unless the user explicitly says `use dataopsctl` / `dataops agent` (see [rules/dataopsctl-opt-out.mdc](../../rules/dataopsctl-opt-out.mdc) — installed to `~/.cursor/rules/` by `install.sh`).

**Output contract (same turn):**

- **Fail** → Step **7a** full report (**`## Summary` first**) + **7b** MS Teams + **7c** ADINC (unless user asked for a subset).
- **Long Run** → [dataops-pd-long-run](../dataops-pd-long-run/SKILL.md) single-pass triage + **AskQuestion** action card + written summary (resolve/monitor/escalate per user choice).
- First line: `Alert type: {Long Run \| Fail} — following dataops-pd-{long-run \| incident-analysis} skill.`

**Job-only resolution:** See [reference.md](reference.md#job-only-lookup).

**Single-incident entry point:** For one PD# / URL / job (not bulk listing), run **Step 0 — Alert type router** after Step 1-verify. **Long Run** → [dataops-pd-long-run](../dataops-pd-long-run/SKILL.md). **Fail** → continue below through Step 7 (full analysis + Teams + ADINC when applicable).

Analyze **one** **Fail** incident (after routing): classify PagerDuty notes (human vs legacy automated summary), search **MS Teams** (`ads-data-bi-support`) for recent threads on the same job/pipeline **before** Datadog/DBX deep analysis (Step 1.5), derive **Root Cause** from **DBX MCP + PD alert/title + human notes + Teams context** (legacy automated summaries are deprecated — see Step 2), check **Datadog CPU/memory** (Step 3) for resource pressure, enrich with Databricks job/run failure details, then find similar past incidents and how they were closed in the past.

**Read-only:** this skill looks up and analyzes incidents — it does **not** change PagerDuty incident status.

**Default PagerDuty scope (urgency) — mandatory**

| Situation | Include **Ad Platform Data Ops High Urgency** (`P7OFL7L`) | Include **Low Urgency** (`P3CUKVY`) |
|-----------|-------------------------------------------------------------|-------------------------------------|
| User asks for **open incidents**, **lists**, **bundles**, **queues**, **“all PDs”**, **similar-incident search**, or **any multi-incident** triage **without** naming specific PD#s/URLs | **Yes (default)** | **No** — skip Low unless the user explicitly asks for Low urgency or to include both |
| User explicitly says **Low urgency**, **include Low**, **both services**, or **P3CUKVY** | As needed | **Yes** |
| User gives a **specific PD# or incident URL** to analyze | Analyze that incident **regardless** of service; if it resolves to Low, proceed and note one line: “PagerDuty service: Low Urgency” | Same row |
| **Alert URL** resolution (Step 1a) — find parent incident | Search **both** `P7OFL7L` and `P3CUKVY` until the alert is found (the incident may live on either service) | Same |

If the user’s request is ambiguous (“check PD”) and they did not name a PD#, **default to High only** and state that Low was omitted unless they ask to include it.

**Microsoft Teams only:** ADINC and Support Bot guidance in this skill assumes **Microsoft Teams** (`/support`, `/incident`, on-call handoffs). Do not mention Slack in outputs or templates.

## Performance (mandatory)

Target **under 3 minutes** wall time for a standard Fail alert. Accuracy rules (identity gate, leaf errors, allowlists) are unchanged — optimize **how** data is fetched, not **what** is reported.

| Phase | Fast path | Never do |
|-------|-----------|----------|
| **PD fetch** | MCP `get_incident` + parallel `list_incident_notes` / `list_alerts_from_incident` | `GET /incidents?incident_number=`; unbounded REST pagination |
| **MCP down** | Run [scripts/pd_incident_fetch.py](scripts/pd_incident_fetch.py) once (`python …/pd_incident_fetch.py {pd#}`) | Hand-write one-off fetch scripts; paginate 90d of all incidents |
| **DBX** | `get_run_details` + `analyze_job_task_failure` on primary run (parallel when workspace unknown: try sox + gen) | `list_job_runs` with default limit 1600+; retry `get_run_output` more than **once** per task when logs are null |
| **Similar incidents** | **Step 5a** — **30d**, **up to 3 pages**; **1** row in Incident Details + total count in legend | “No similar” without 5a; full 90d pagination by default |
| **Datadog resources (Step 3)** | One bounded batch (`get_datadog_metric` or `execute_code`) — CPU + memory in incident window | Retry Datadog MCP after one empty/error; span/log hunting unrelated to Step 3 |
| **Confluence (Step 2c)** | One CQL batch + one `get_page` for §2 excerpt when leaf found | Full subtree crawl; paste full page HTML |
| **for_each / S3 sensor** | **Step 4b-sensor** fast path when iteration logs unavailable | Brute-force child run IDs or Datadog span hunting |
| **Teams (Step 1.5)** | One `search messages` + optional `message list --from-url` on top hit | Full channel backfill before Step 1.5 |

**Order:** Run **Step 1.5 (MS Teams)** immediately after **Step 1-verify** (job name known). Run **Step 1b** (alert/runbook) and **Step 4a** (DBX) **after** Step 1.5 so channel threads inform the on-call plan. Run **Step 2c** (canonical Confluence leaf) after **1b** when `job_name` is known — may parallel with early **4a**. Run **Step 3** (Datadog resources) after **1b** (LDB) or after **4a** (DBX, for cluster tags). **Step 6-timeline** needs Step **4** + PD times — build before Step 7a. Render order: Summary → Timeline → Incident Details → Datadog → Databricks → Root Cause → MS Teams context → **Runbook** → On-Call Recommendation. Optionally parallelize Step 1b + Step 2 (notes) with Step 4a once Teams context is captured.

## Prerequisites

1. **PagerDuty MCP** (`user-pagerduty-mcp-manual`) — token in `~/.cursor/mcp.json`. Stop and guide setup if missing.
2. **Microsoft Teams CLI** (`teams`) — required for **Step 1.5** channel search. Install per [EXTERNAL_PREREQUISITES.md](../../EXTERNAL_PREREQUISITES.md) (not bundled in this repo). Optional local skill: `teams-cli` via AIX if present. If `teams` is unavailable or auth fails, state "Teams context skipped" and continue with PD + DBX only.
3. **ads-databricks MCP** — required when the incident involves a DBX job (Fail/Long Run monitors). If unavailable, render the PD sections and note that DBX enrichment was skipped.
4. **Datadog MCP** (`plugin-datadog-datadog`) — required for **Step 3** CPU/memory resource analysis. Prefer `get_datadog_metric` or `execute_code` (read-only). If unavailable or auth fails, set `## Datadog Analysis (resources)` to one line: `Skipped — Datadog MCP unavailable` and continue.
5. **Confluence MCP** (`user-confluence-disney`) — **Step 2c** canonical leaf lookup under [Data Pipelines](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841195/Data+Pipelines) for every DBX job incident (compare to PD alert URL). If unavailable, render **`## Runbook`** with PD URL only and one line: `Confluence check skipped — MCP unavailable.`

Always call `GetDynamicTools` before `CallDynamicTool` for MCP namespaces (PagerDuty, Datadog, Databricks, Confluence).

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

If the user gives a job name and multiple open/recent incidents match, prefer the **most recent** unless they specified a PD# or URL. If **multiple open** incidents share the job, list PD# + opened time and ask **once** which to analyze; if **one** open match, proceed without asking.

## Step 0 — Alert type router (mandatory)

Run **once per invocation** immediately after **Step 1** + **Step 1-verify** (you need `title` and `verified_uuid`). Do **not** run Step 1.5 or Fail RCA until routing completes.

**Scope:** Applies when the user is triaging or analyzing **one** incident (PD#, URL, alert URL, or a single resolved job/DAG match). **Skip Step 0** for bulk work only (open-incident lists, shift summaries, multi-PD bundles) unless the user also named one PD to analyze.

### User overrides (evaluated before title rules)

| User intent in the message | Action |
|----------------------------|--------|
| Explicit **long run** verbs (`monitor long run`, `recheck long run`, `close long run`, `long run triage`, …) | Route to **dataops-pd-long-run** even if you have not re-fetched yet — still run identity gate after fetch |
| Explicit **Fail RCA** (`full analysis`, `root cause`, `DEV handoff`, `ADINC`, `similar past incidents`) on a Long Run PD | Stay on **this skill** (full Step 7); say one line that the title is Long Run but user asked for Fail-style RCA |
| User names only **`dataops-pd-long-run`** / “use long run skill” | Route to **dataops-pd-long-run** |
| User names only **`dataops-pd-incident-analysis`** / “full incident analysis” on a Fail PD | Continue **this skill** (Steps 1.5–7) |

### Classify from incident `title` (primary)

| Alert type | Match on `title` (case-insensitive) |
|------------|--------------------------------------|
| **Long Run** | Contains **`[Long Run]`** (canonical AP/BI/ODS/ADM taxonomy) |
| **Fail** | Contains **`[Fail]`** in bracket taxonomy **or** starts with **`DataOps\|PROD\|Fail\|`** **or** starts with **`DataOps\|DBX\|PROD\|Fail\|`** |
| **Ambiguous** | Neither signal (e.g. `DataOps\|PROD\|Dag Change\|`, title is only a job name) → use **tie-break** below |

### Tie-break (ambiguous title)

1. **`list_alerts`** on `verified_uuid` (Step 1b peek only — do not run full Fail workflow yet).
2. **Long Run** if alert `details.query` or monitor text suggests duration / slowness, e.g. `running_spans.duration`, `ongoing_duration`, `anomalies(`, or Long Run monitor templates — **and** no `status:error` / `dagrun.duration.failed` Fail signature.
3. **Fail** if alert body or query shows **`status:error`**, **`dagrun.duration.failed`**, **`Failed: Task`**, or Airflow “dag … has failed”.
4. Still ambiguous → ask the user once: **Long Run triage** vs **Fail RCA**; default **Fail** if the body explicitly states a failed task/DAG.

### Route

| Classified type | Next step |
|-----------------|-----------|
| **Long Run** | **Stop** this skill’s Fail workflow. **Read and follow** [dataops-pd-long-run/SKILL.md](../dataops-pd-long-run/SKILL.md) from the top (identity already verified — reuse `verified_uuid`, `incident_number`, `title`). Deliver **Long Run** outputs (status, action picker, monitor/resolve/escalate). Do **not** render Step 7a–7c Fail templates unless the user chose full Fail RCA per overrides. |
| **Fail** | Continue **Step 1.5** through **Step 7** in this skill. |

**First line of user-visible output** after routing:  
`Alert type: {Long Run | Fail} — following dataops-pd-{long-run | incident-analysis} skill.`

Classification rules and examples: [reference.md](reference.md#alert-type-classification).

## Workflow

### Step 1a — Resolve alert URL to incident (when input is an alert link)

Extract `alert_id` from `https://disney.pagerduty.com/alerts/{alert_id}`.

The MCP has no standalone "get alert by ID" — locate the parent incident:

1. `list_incidents` on **both** Data Ops services (`P7OFL7L` and `P3CUKVY`) for the **last 7 days** (expand to 90d if not found) — **alert parent lookup must see Low incidents** when the alert is routed there.
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

Optional: `--similar-days 90 --max-pages 3` only when user asks for deep past context or Step 5 tier-1 finds zero matches. **`--include-low`** adds `P3CUKVY` to similar-incident search (default script/MCP scope is High `P7OFL7L` only).

The script returns `incident`, `verified_uuid`, `notes`, `alerts`, `log_entries`, `parsed` (job, run_id, runbook_url, workspace, **`assignee`**), and `similar`. Use `parsed` before re-parsing alert bodies manually.

Record: `id`, `incident_number`, `title`, `summary`, `status`, `created_at`, `resolved_at`, `service`, `assignments`, **`assignee_display`** (from Step 1-assignee).

**Step 1-assignee (mandatory — open or resolved)** — The report **Assignee** row must name who worked the incident (matches PagerDuty timeline). **`assignments` alone is wrong for resolved PDs** — PagerDuty clears `assignments: []` on resolve while timeline still shows ack/assign.

**When to fetch log entries:** Always when `status` is **`resolved`** OR `assignments` is empty. MCP `browse_incidents` get often omits log entries → use REST `GET /incidents/{verified_uuid}/log_entries?limit=100` or `pd_incident_fetch.py` (parallel with notes/alerts).

**Resolution order** (`assignee_display`):

1. `assignments[0].assignee.summary` when present (open incidents).
2. Else newest `acknowledge_log_entry.agent.summary` in log entries.
3. Else newest `assign_log_entry.agent.summary`.
4. Only then **—** (rare: auto-resolved with no human ack).

**Report formatting (Step 7a table row Assignee):**

| Situation | Example |
|-----------|---------|
| Open, from `assignments` | `Praveen Sadineni` |
| Resolved, from ack timeline | `Praveen Sadineni (acknowledged; resolved)` |
| Only assign at trigger | `Praveen Sadineni (assigned at trigger; resolved)` |

Rules: [reference.md](reference.md#incident-assignee-resolved).

### Step 1-verify — Identity gate (MANDATORY before Step 1b+)

Immediately after fetch, run checks from [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md):

1. If user gave **PD#**: `String(incident_number) == String(expected_incident_number)`.
2. If user gave **URL/UUID**: `id == expected_uuid`.
3. If user gave **job/DAG only**: title contains expected token; if `list_incidents` returned multiple matches, **stop and ask** — do not pick the first row.
4. **Service gate:** `service.id` is `P7OFL7L` (**default** for analysis) **or** `P3CUKVY` **only when** the user explicitly asked for Low urgency, asked to include both services, or supplied a PD#/URL that resolves to a Low-urgency incident. If the user asked for **High-only** context but the fetched incident is Low, **abort** and say the incident is Low urgency — offer to analyze only if they confirm (or ask them to include Low in scope). **Exception:** **Step 1a** (alert URL → incident) may resolve to either service — then continue. Another service only if the user explicitly asked about that service.

On failure: **abort** — report what the API returned vs what was requested; do not analyze or write to a different ticket.

Store `verified_uuid` = `id` — use **only** this for `list_alerts_from_incident`, notes, and any user-requested writes.

PD link: `https://disney.pagerduty.com/incidents/{verified_uuid}`

Extract **job name** and **run ID** from title — see [reference.md](reference.md#title-parsing).

Derive **Team** and **Oncall MS Teams Tag** from the PagerDuty incident **`title` only** — see [reference.md](reference.md#team-and-on-call-tags). **Bracket subtitles in the title** (`[Segmentation]`, `[Targeting]`, `[Metrics]`, …) **supersede** job-name keywords (`audience`, `fandom`, etc.); never route from job name when the title already names subteam. Use `TBD` / `—` for Dag Change and unmatched titles.

### Step 1.5 — MS Teams search (`ads-data-bi-support`) before Datadog / DBX

Run **immediately** after Step 1-verify when **`job_name`** is extracted from the title (or from minimal alert peek). Do **not** wait for DBX or Datadog trace pulls.

**Channel (fixed):** [ads-data-bi-support](https://teams.microsoft.com/l/channel/19%3Ad8264169c3d34e6182652bda83c14e57%40thread.tacv2/ads-data-bi-support?groupId=00792fe9-ce40-4530-9561-d415894f214f&tenantId=56b731a8-a2ac-4c32-bf6b-616810e913c6) — scope searches to this channel.

**Shell** (see [EXTERNAL_PREREQUISITES.md](../../EXTERNAL_PREREQUISITES.md); optional local **teams-cli** skill via AIX if installed):

1. Resolve team display name if needed: `teams --agent channel teams --filter "data bi"` or similar until the team containing **ads-data-bi-support** is found; record `team` string for `--team`.
2. Search last ~30d of discussion for this failure family:

```bash
teams --agent search messages --query "{job_name} OR fail OR failed" --team "<team_display_name>" --channel "ads-data-bi-support"
```

Use **OR** (uppercase) per teams-cli KQL. Add tokens from the PD title (e.g. upstream job name from brackets) if the first query returns nothing. Prefer hits from the **last 30 days** (`sent>YYYY-MM-DD` if the CLI accepts it on `search messages` — see `teams agent schema`).

3. If a promising **thread URL** appears in results, read it: `teams --agent message list --from-url "<message_or_thread_url>" --limit 50` (or `channel replies` per teams-cli).

**Use of results:** Summarize under **`## MS Teams channel context`** (2–6 bullets) — **ads-data-bi-support thread content only** (quotes, dates, who said what, thread links). **Do not** put human **PagerDuty notes**, PD note quotes, or “no human PD notes” in this section — PD notes belong in **Summary** / **Root Cause** / **On-Call Recommendation** only. Feed thread takeaways into **Root Cause**, **On-Call Recommendation**, and the Teams **closing question** when relevant. If **no hits**, one line: `No relevant threads in ads-data-bi-support (last 30d) for this job.`

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
| **`creation_time`** (CEF/details) | **Step 6-timeline** — Datadog detection row (convert to PST) |
| Databricks page URL | Cross-check against DBX MCP `run_page_url` |
| Job Trace / Data Pipelines | Optional links in full report |

If no alerts, empty `body`, or no runbook link: leave `runbook_url` unset for Step 2b (do not invent a URL).

### Step 2 — PagerDuty notes (human vs legacy automated summary)

```json
CallMcpTool user-pagerduty-mcp-manual list_incident_notes
{ "incident_id": "<id>" }
```

**PagerDuty Incident agent is decommissioned.** Do **not** output **AI Agent Recommendations**, do **not** populate **Root Cause** or **Key Evidence** from automated agent text, and do **not** parse or quote `Recommendations:` from legacy notes.

| Note type | Detection | Use in report |
|-----------|-----------|---------------|
| **Legacy automated summary** | `content` starts with `[Incident agent — automated summary]` | **Runbook URL extraction only** (regex ADSO wiki URL anywhere in that note for Step 2b priority 2). Set `runbook_source` = `legacy PD summary note` when used. Otherwise **ignore** for RCA — do not quote Root cause / Evidence / Recommendations. |
| **Human notes** | Any note that does **not** use that prefix | Fold into **Summary**, **Root Cause**, or **On-Call Recommendation** when factual — **no** `## Available Notes` section in the report. |

**Standard output (Step 7):** The first line of the analysis **must** be:

`Analysis for PD #{incident_number} (PagerDuty MCP + Datadog MCP + ads-databricks MCP). {legacy_summary_sentence}`

Where `{legacy_summary_sentence}` is **one** of:

- If a legacy note exists: `Legacy [Incident agent — automated summary] note present — ignored for RCA (PagerDuty Incident agent decommissioned).`
- If none: `No [Incident agent — automated summary] note.`

### Step 2b — Resolve runbook URL (fallback)

Run when `runbook_url` is still unset after Step 1b. Skip when there is no DBX **job name** (Dag Change, LDB-only, Goldmine DAG).

**Priority order:**

| Priority | Source | Action |
|----------|--------|--------|
| 1 | Step 1b PD alert | Already set — skip Step 2b |
| 2 | Legacy PD summary note | Regex first `https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/\d+[^\s\)]*` in the **full** legacy note body (if present); set `runbook_source` = `legacy PD summary note` |
| 3 | Confluence search | See [reference.md](reference.md#confluence-runbook-fallback) — set `runbook_source` = `Confluence (Data Pipelines)` |

**Confluence fallback** (`user-confluence-disney`) — only when priorities 1–2 found nothing:

```json
CallMcpTool user-confluence-disney confluence_search_content
{ "cql": "ancestor = 192841195 AND title ~ \"{job_or_stem}\"", "limit": 10 }
```

Retry with `text ~ "{job_name}"` if title search returns no ranked match. Build URL: `https://disney-enterprise.atlassian.net/wiki{result._links.webui}`.

Record `runbook_source` for MS Teams / working vars (e.g. `PagerDuty alert`, `legacy PD summary note`, `Confluence (Data Pipelines)`). If still no match after 2b: `runbook_url` = `—`, `runbook_source` = `not found`.

### Step 2c — Canonical Confluence runbook leaf (Step 7a `## Runbook`)

Run for every incident with a **job name** (Fail / full RCA Long Run). **Always** execute after Step 1b (even when PD already has `[Link to Job Runbooks]`). Skip only for Dag Change / non-DBX titles with no job.

**Goal:** Find the standardized **metadata + runbook leaf** under [Data Pipelines](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841195/Data+Pipelines) — same search/ranking as Step 2b priority 3 — see [reference.md](reference.md#confluence-runbook-fallback) and [reference.md](reference.md#runbook-step-7a).

| Output var | Meaning |
|------------|---------|
| `pd_runbook_url` | From Step 1b (Goldmine `_Runbook:` counts too) — **shown as-is** in report |
| `confluence_canonical_url` | Best-ranked leaf page URL from CQL |
| `confluence_page_title` | Matched page title |
| `confluence_ancestry` | Team path under Data Pipelines (from `ancestors` on `confluence_get_page` or breadcrumb in search snippet) |

**Compare page IDs** — regex `pages/(\d+)/` on both URLs. Set **table flags** only (no prose comparison block):

| Condition | **Flags** cell (PD row / Canonical row) |
|-----------|----------------------------------------|
| Same page ID | `—` on both rows |
| Different IDs | PD row: `URL mismatch`; Canonical row: `—` |
| No canonical leaf | Canonical row: `Missing leaf` |
| Placement ≠ title taxonomy | Canonical row: `Placement mismatch` (append `URL mismatch` on PD row when IDs also differ) |

**Placement vs alert taxonomy** — full rules in [reference.md](reference.md#runbook-step-7a).

**Structure spot-check:** Prefer ranked hits with **Pipeline metadata** + **Pipeline runbook** (§1/§2). If top hit is an index page, retry per **Match ranking**.

**Confluence body (Step 7a):** One `confluence_get_page` on the canonical page ID. Render **`### From Confluence ({alert_type})`** with **`2.2 Triage steps` only** — [reference.md](reference.md#confluence-2-excerpt-by-alert-type). No other §2 subsections.

**MS Teams SUMMARY `Runbook:` line** — use `pd_runbook_url` when set; else `confluence_canonical_url`; else `—`.

Human notes from Step 2 inform Summary / Root Cause / On-Call Recommendation; they do not replace DBX leaf-error RCA.

### Step 3 — Datadog resource analysis (CPU / memory)

**Purpose:** Decide whether the failure or Long Run is **plausibly resource-related** (CPU saturation, memory pressure, OOM) vs an application/upstream error. **Step 7a placement:** fourth section — **`## Datadog Analysis (resources)`** after **`## Incident Details`** (same content as below; execution may still follow Step 4a for cluster tags).

**When:** Every Fail or full Fail-style RCA on a Long Run PD. **Skip sub-queries** only for Dag Change with no runnable workload in the alert.

**Tooling:** `plugin-datadog-datadog` — `load_datadog_skill` with `datadog/metrics` (and `datadog/visualizations` if charting) on first use this session; then `search_datadog_metrics` / `get_datadog_metric` or one `execute_code` script that batches queries. **Do not** use AIX `pup`/`datadog` CLI unless Datadog MCP is down (one CLI attempt max).

**Timing (mandatory):**

| Anchor | Window |
|--------|--------|
| **Fail** | `T0` = `created_at` − 30m, `T1` = `created_at` + 15m (extend `T1` to run end when DBX `get_run_details` shows termination time) |
| **Long Run** | `T0` = run `start_time` − 15m (from DBX when known, else `created_at` − 30m), `T1` = now or run end |
| **Baseline** | Same duration as `T0`→`T1`, ending at `T0` — compare max/avg CPU and memory |

**Scope — tags (from Step 1b alert body, monitor tags, title):**

| Pipeline | Tags to try (AND together when known) |
|----------|----------------------------------------|
| **DBX** | `job_name:{job}`, `databricks_job_id:*`, `cluster_name:*`, `cluster_id:*` from `get_run_details` (**refine after Step 4a**) |
| **LDB / Airflow** | `dag_id:{dag}`, `airflow_id:{host}`, `env:prod`, `team:bi-ops`, `pipeline:ldb` |
| **APM / Job Trace link** | `service` from alert Job Trace URL or `@job_name` in trace tags |

If Step 1b has a **Job Trace** Datadog URL, parse `env`, `service`, `host` query params when present.

**Metrics (discover, do not guess):**

1. `search_datadog_metrics` with `query` containing `databricks`, `airflow`, or `spark` + `tag_filter` from scope.
2. Prefer integration metrics for **CPU** and **memory** on the executing hosts/clusters (e.g. `*.cpu.*`, `*.memory.*`, `system.mem.*`, `system.cpu.*` — exact names from search).
3. One batched query: **avg** and **max** CPU + memory over `T0`–`T1`; repeat for baseline window.
4. Optional: `search_datadog_logs` / `execute_code` logs query for `OOM`, `OutOfMemoryError`, `Memory limit exceeded`, `kubectl.*oom` in the same window (only if metrics inconclusive — counts as part of the same Step 3 batch, not a second retry).

**Verdict** (state explicitly in the report):

| Verdict | Criteria |
|---------|----------|
| **resource_likely** | Max CPU ≥ ~85% (or integration “high” threshold) **or** memory near limit / OOM log lines in window **and** failure type compatible (TIMEDOUT, hung stage, generic workload failure without tier-1 leaf) |
| **resource_unlikely** | CPU/memory flat or low during incident window; clear application leaf error from DBX |
| **inconclusive** | No series for scoped tags (document tags tried) |
| **skipped** | Datadog MCP/CLI unavailable |

**RCA rules:**

- **Never** replace Step 4b-leaf root cause with “high CPU” alone — resource findings **supplement** leaf errors.
- When **resource_likely** **and** DBX shows `TIMEDOUT`, OOM, or cluster termination for resources, add one bullet under **Root Cause** tying resource pressure to symptoms.
- For **Long Run**, if CPU/memory normal but run still slow, state **resource_unlikely** and keep blocker analysis in DBX/long-run skill.

Full tag lists, example queries, and Airflow vs DBX paths: [reference.md](reference.md#datadog-resource-analysis).

**Order with Step 4:** For DBX jobs, run **Step 4a** first when needed to obtain `cluster_id` / run end time, then complete **Step 3** queries in the same turn (Step 3 output still appears **above** Databricks in the report). For LDB-only, run Step 3 right after Step 1b.

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

DEV handoffs, **Root Cause**, and **MS Teams ROOT CAUSE** must quote the **leaf application/Spark error** — never a wrapper. Full rules: [reference.md](reference.md#leaf-error-extraction).

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

**4c — Related upstream runs from PD notes and DBX**

Parse **human** notes and DBX task metadata for additional run IDs (ignore legacy automated summary bodies for RCA):

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

**Tiered search (mandatory)** — **Step 5a (same job, 30d)** runs first whenever a **`job_name`** or DAG token is known from the title (almost every DBX/LDB Fail). Do **not** write “no similar incidents” until **5a** completes.

| Tier | When | Lookback | Pages | Stop when |
|------|------|----------|-------|-----------|
| **5a — Same job** | **`job_name` / DAG known** (required) | **30 days** | **Up to 3** (`limit=100` each) | All pages fetched or `more=false` or oldest incident &lt; 30d |
| **1 — Same title** | After 5a (or no job token) | **30 days** | **1** | Same as legacy tier-1 |
| **2** | **5a + tier 1** found **0** same-job/title | **90 days** | **+2** pages max | ≥3 matches or 3 pages |
| **3** | User asks "deep history" / "6 months" | User window | **5 pages max** | 15 matches total |

Use MCP `list_incidents` **or** `pd_incident_fetch.py`. **Default:** **`service_ids`: [`P7OFL7L`] only**. Script: `--similar-days 30 --max-pages 3` when using the helper for **5a**. Client-side filter only — API has no text search.

#### Step 5a — Same job within 30 days (mandatory)

Run when **`job_name`** (or DAG id from title) is extracted in Step 1-verify. **Skip 5a** only for Dag Change / alerts with **no** job or DAG token in title.

1. Set `since` = now − **30 days**, `until` = now; **High only** (`P7OFL7L`) unless user widened scope.
2. **`list_incidents`** with `sort_by: created_at:desc`, `limit: 100`. **Paginate** (offset += page size) until **3 pages** fetched, **`more` is false**, or the oldest row in the page is **before** the 30d window.
3. **Client filter** — include incident when **`job_name in title`** OR **`job_name in summary`** (case-sensitive token match on the full job/DAG string from the current incident).
4. **Exclude** current `incident_number`. Collect **all** matches in the window (not only the first page). Sort by `created_at` descending.
5. **`list_incident_notes`** on the **single most recent** same-job incident (for **Incident Details** row).
6. **Report:** In **`## Incident Details`**, sub-table **`### Similar past incidents (30d, same job)`** — legend `{N} same-job PDs on High in the last 30 days; showing most recent one.` — **one table row** only (most recent by `created_at`, excluding current PD).
7. **Forbidden:** Saying “No similar incidents in the last 30 days” when **any** same-job incident exists in **5a** results. If zero matches after **3 pages**, say explicitly: “No other PDs with job `{job_name}` in the last **30 days** on High Urgency (searched 3 pages).”

**Same title** and **same run** tiers are **in addition** to 5a (dedupe PD#s already listed under same job).

| Priority | Match rule | Label |
|----------|------------|-------|
| 1 | Exact same `title` (ignore `[#NNNN]` prefix in `summary`) | Same title |
| 2 | Same **job name** in title/summary (Step **5a**) | Same job |
| 3 | Same **run ID** in title (rare) | Same run |

**Incident Details** shows **1** most-recent same-job PD.

For the similar incident where notes are fetched:

1. `list_incident_notes` for that incident's `id`.
2. Legacy `[Incident agent — automated summary]` — **one historical root-cause line only** if no human note; label legacy.
3. **Resolution signal** from human notes, else `resolved_at` / `status` per [reference.md](reference.md#resolution-inference).

**Resolution summary** for each past incident (2–4 sentences):

- What failed (title, human notes, or labeled legacy line)
- How it was closed (quote human note when present)
- If no notes: "Resolved at {time PT}; no human resolution notes recorded"

Link each past incident: `[#5548051](https://disney.pagerduty.com/incidents/{id})`.

### Step 6 — Synthesize for output

Before rendering output, prepare the **full report** and **MS Teams handoff**:

**ON-CALL RECOMMENDATION** (Step 6-recommendation) — **1–2 lines** in Step 7a **`## On-Call Recommendation`** only: resolve / keep open / escalate — aligned with DBX, similar incidents, and Teams context.

**TEAMS CLOSING LINE** (Step 6-teams-close) — **last line** of the MS Teams handoff (after **ROOT CAUSE**): one **direct question or comment** to the on-call engineer — include `{@oncall tag}` when known. Phrase from **`## On-Call Recommendation`** but as an ask, not a directive. Examples: `@oncall-ods-metrics — did repair run {run_id} clear the DQ constraints for hour {utc_hour}?` / `@oncall-segmentation — can you confirm inbound is green before we resolve PD #{n}?`

**DEV handoff gate:** Before MS Teams handoff, **ROOT CAUSE** in Teams and **`## Root Cause`** in the report must use Step 4b-leaf **or** **4b-sensor** RCA. Quote **task_key** and verbatim leaf error **inside ROOT CAUSE** (no separate evidence section).

**SUMMARY** (Step 6-summary → **first section** of Step 7a) — **3–6 short sentences**, plain language, **prose only** (no bullets, no tables). Goal: on-call understands the situation **without scrolling** past metadata tables or logs.

| # | Include when known | Source |
|---|-------------------|--------|
| 1 | **What failed or triggered** — job/DAG, leaf task or DQ check name, **business time window** (e.g. hour UTC for DQ partition) | Title, alert body, Step 4b-leaf |
| 2 | **What broke** — count/severity (e.g. “two ERROR constraints”), one-line error class — **not** full stack | Step 4b-leaf, alert body |
| 3 | **Remediation already tried** — repair runs, re-runs, snooze (outcome: still failing / queued / SUCCESS) | Human PD notes, DBX run list, Step 1.5 Teams |
| 4 | **PagerDuty vs pipeline truth** — e.g. **resolved** on PD but **data still bad**, or opposite (run SUCCESS, safe to close) | `status`, DBX result, notes |
| 5 | **In-flight work** — upstream re-run queued/running, who acknowledged | Notes, Teams, DBX |
| 6 | **One precedent line** (optional) — prior PD date + what fixed it | Step 5a human notes |

**Style:** Lead with the failure families operators care about (hour, task, constraints). Use **bold** sparingly: partition hour, **resolved**/**failed**/**still broken**, critical task names. **Do not** duplicate the Root Cause paragraph or quote verbatim Spark traces here.

Canonical example: [reference.md](reference.md#report-summary-step-7a).

**TIMELINE** (Step 6-timeline → second section of Step 7a) — **`## Timeline (in PST time)`** immediately after **`## Summary`**. Chronological **two-column table**; facts from DBX + PagerDuty + notes/Teams only.

```markdown
| Time | Event |
|------|--------|
| {HH:MM or HH:MM–HH:MM} | {one plain-language row} |
```

| Rule | Detail |
|------|--------|
| **Timezone** | Convert all timestamps to **PST** (`America/Los_Angeles`). Heading says **PST** even when daylight time — match user-facing on-call convention. |
| **Time column** | Same calendar day as primary failure when possible: `11:57`, or range `11:58–14:49` for multi-hour waits. Omit date unless the incident spans days. |
| **Event column** | Short clauses; **bold** task/job names when helpful; link DBX runs: `[{run_id}]({run_page_url})`. |
| **What to include** | DQ run start + dimension checks; **sensor** wait (attempt count + error snippet); **upstream** job builds (SUCCESS + run link); **leaf fail** (constraint count); **repair** retries; **queue/concurrency** blockers (`max_concurrent_runs`, QUEUED). |
| **Paging (cap — reduce noise)** | At most **one row each** for observability + PD lifecycle (see below). **Do not** add rows for snooze, unack, re-ack, notify, or duplicate acks. |
| **Datadog detection** | One row — alert `cef_details.creation_time` or `details.creation_time` (Step 1b). `**Datadog** — monitor {id} detected …` |
| **Incident opened** | One row — `incident.created_at` or oldest `trigger_log_entry`. `**PagerDuty** — incident #{n} opened` |
| **First acknowledge** | One row — **earliest** `acknowledge_log_entry` where `agent.type` is `user_reference` (`created_at` + name + channel if known). Omit if no human ack. |
| **First escalation** | One row — **earliest** `escalate_log_entry` (or `delegate_log_entry` when summary indicates escalation). Omit if none — **initial policy assign is not escalation**. |
| **Resolved** | One row — `resolved_at` + `resolve_log_entry` (human name or **auto-resolved** via integration). Omit only if still open. |
| **Sources** | Step 1b alerts; `GET /incidents/{uuid}/log_entries` (sort asc for first ack/escalate); DBX; notes. |
| **Ordering** | Default: **pipeline block**, then paging rows **Datadog → opened → first ack → first escalate (if any) → resolved**. Long Run: strict PST sort if simpler. |
| **Skip** | Do not fabricate times; do not expand PD beyond the five paging row types above. |

Exemplar: [reference.md](reference.md#report-timeline-step-7a).

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
| **SOURCE_SYSTEM** | Best allowlist match from pipeline + DBX | Always confirm unless RCA from human notes or DBX is explicit |
| **ISSUE_CATEGORY** | Best allowlist match from failure type | Always confirm unless RCA from human notes or DBX is explicit |
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

**Render order:** **`## Summary`** → **`## Timeline (in PST time)`** → **`## Incident Details`** (includes **Similar past incidents** sub-table) → **`## Datadog Analysis (resources)`** → **`## Databricks Analysis`** → **`## Root Cause`** → **`## MS Teams channel context`** → **`## Runbook`** → **`## On-Call Recommendation`**. **Do not** render **`## Similar Past Incidents`** as its own section (moved into Incident Details). **Do not** render **`## Available Notes`**, **`## On-Call Action Plan`**, or **`## Key Evidence`**.

Use this template exactly (omit empty sections with a one-line "None found" where appropriate):

```markdown
Analysis for PD #{incident_number} (PagerDuty MCP + Datadog MCP + ads-databricks MCP). {legacy_summary_sentence}

# Incident Analysis — #{incident_number}

## Summary

{Step 6-summary — 3–6 sentences, prose only; see Step 6 SUMMARY table and reference.md#report-summary-step-7a}

## Timeline (in PST time)

{Step 6-timeline — | Time | Event | table; PST; reference.md#report-timeline-step-7a}

## Incident Details

Compact table — **no Runbook row** (see **`## Runbook`** below). **No separate PD link row** — link the alert title to PagerDuty.

| Field | Value |
|-------|--------|
| **PD alert** | [{title_truncated}](https://disney.pagerduty.com/incidents/{verified_uuid}) — `title_truncated` = title before first ` on ` (include `[#pd]` only in link anchor if helpful: `PD #6204259 — …`) |
| **Status** | {Status} |
| **Urgency** | {High \| Low} (`P7OFL7L` \| `P3CUKVY`) |
| **Opened** | {created_at PT} |
| **Resolved** | {resolved_at PT or —} |
| **Assignee** | {assignee_display from Step 1-assignee} |
| **Job** | `{job_name}` |
| **Run ID** | `{run_id}` or — |
| **Team** | {team from title taxonomy} |
| **Oncall MS Teams Tag** | {@tag from reference team table} |
| **Datadog monitor** | [Monitor {monitor_id}]({datadog_monitor_url}) — from alert `client_url` / `cef_details.client_url`; strip query string for display link when possible |

**Similar past incidents (Step 5a)** — append below the table (same section, not a separate `##`). After **Step 5a**, record **`{total_count}`** from full 5a filter; show **only the most recent** peer (exclude current PD):

```markdown
### Similar past incidents (30d, same job)

*{N} same-job PDs on High in the last 30 days; showing most recent one.*

| Opened (PST) | PD alert | Notes |
|--------------|----------|-------|
| {Nov 17, 2026 5:48 AM} | [[AP][ODS][Metrics][Fail] ap_addr_…](https://disney.pagerduty.com/incidents/{uuid}) | {one line — human PD note or resolution snippet} |
```

- **PD alert** column = truncated title (before ` on `) linked to incident UUID.
- **Opened (PST)** = `created_at` in PST (same convention as Timeline).
- **Notes** = one line from `list_incident_notes` when present; else status + resolved time or fail task from title/run id.
- If **0** matches after 5a: one line under the heading: `No other High-urgency PDs for job \`{job}\` in the last 30 days (searched 3 pages).`
- **Do not** render a separate **`## Similar Past Incidents`** section in Step 7a — detail lives in Incident Details sub-table only.

Rules: [reference.md](reference.md#incident-details-step-7a).

## Datadog Analysis (resources)

{Step 3 — always present. Table: **Verdict**, **Window (PT)**, **Scope (tags tried)**. Subsections **CPU**, **Memory**, **Interpretation** (2–4 sentences: resource vs app/upstream). If skipped/inconclusive, one line each. **Keep this section unchanged** — see [reference.md](reference.md#datadog-resource-analysis).}

## Databricks Analysis

{Step 4 — **keep as-is** (no format changes in this readability pass). Skip entire section with one line if no DBX job or MCP unavailable. See [reference.md](reference.md#databricks-analysis).}

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

{For each upstream run cited by human notes/DBX or blocking a sensor — same sub-structure (job, workspace, run state, failed task, key log lines). If none: "None identified."}

## Root Cause

{**Step 4b-leaf** leaf error and narrative — task_key, attempt — never wrapper-only. Supplement with human notes, **Step 1.5 MS Teams** context, or alert context only when they add factual timeline/ownership; do **not** use legacy automated summary text. **Unchanged** — do not duplicate a separate Key Evidence section; verbatim errors belong in **Databricks Analysis → Log / error output** as well.}

## MS Teams channel context

{**Step 1.5** only — bullets from **ads-data-bi-support** threads (last 30d). **No PagerDuty notes.** One line if no threads. See reference.md#ms-teams-channel-context-step-7a.}

## Runbook

{**Step 2c** — [reference.md](reference.md#runbook-step-7a)}

| Source | Runbook | Flags |
|--------|---------|-------|
| **PagerDuty alert** | [{link text}]({pd_runbook_url}) or — | {— \| URL mismatch} |
| **Canonical (Data Pipelines)** | [{confluence_page_title}]({confluence_canonical_url}) or — | {— \| Missing leaf \| Placement mismatch} |

{`### From Confluence (Fail)` or `(Long Run)` — **2.2 Triage** only; omit if no page/2.2/MCP down.}

## On-Call Recommendation

{Step 6-recommendation — **1–2 lines**: resolve / keep open / escalate}

```

(Step **5a** similar incidents render inside **`## Incident Details`** only — see template above.)

Display times in **PT** (`Mon DD, YYYY h:mm A PT`) unless the user requests another timezone.

#### Step 7b — MS Teams handoff message

Heading in the deliverable: **`## MS Teams handoff (copy-paste)`** (synonym `## MS Teams message` allowed). Render a **separate** section immediately after the full report, containing a **single fenced code block** (plain text) the user can copy-paste into Teams. Template: [reference.md](reference.md#ms-teams-handoff-message).

**Paste safety (mandatory):** MS Teams often breaks **inline icons, emoji, or images** when pasting from chat — **never** put icons, Unicode pictographs, or `![alt](url)` images in the handoff block or any skill output meant for Teams. Use **ASCII labels only**.

**SUMMARY fields (7b):** Include `PD#`, `Status`, `Run`, `Workspace`, `Databricks run`, `Runbook`. **Do not** include `Job` (already on **line 1** title), `Urgency`, `Team`, `Opened`, or a **PD** URL — the engineer anchors the thread when opening Teams.

Do **not** use vendor glyphs (PagerDuty logo, DBX logo, Confluence triangle, etc.).

**MS Teams formatting rules:**

- **First line format:** `{pd_title_to_job_or_dag} {oncall_tag}` — see [reference.md](reference.md#ms-teams-title-line).
- **Section order (ALL CAPS headers):** `SUMMARY` → `ROOT CAUSE` only — then **one closing line** (Step 6-teams-close): direct question or comment to on-call with `@` tag when known. **No** `KEY EVIDENCE`, `PAST CONTEXT`, or `RECOMMENDATION` headers.
- **Do not include** alert URL — the PD incident link is sufficient (alerts reachable from PD UI).
- **Do not include** any **PagerDuty Incident agent** or **AI Agent Recommendations** section — that integration is decommissioned.
- **Do not include** a separate on-call action-plan block — full report uses **`## On-Call Recommendation`** only.
- **Do not include** ADINC fields — those live in the separate ADINC block (Step 7c).
- **ROOT CAUSE** — Step 4b-leaf verbatim error + `task_key` / attempt in 2–4 sentences; see [reference.md](reference.md#leaf-error-extraction). Never wrapper-only or log-tail inferences.
- No "Incident agent" attribution suffixes on ROOT CAUSE.
- **Closing line** — must end the message; plain text; no icons; not an ALL CAPS header.
- Use plain text inside the code block (no markdown tables — use aligned labels as shown)
- Full URLs on their own lines (Teams auto-links)
- Keep total message concise; truncate log quotes to one line
- If Team is `TBD`, omit `@` tag on first line and note "No on-call tag — route via DataOps" in **`## On-Call Recommendation`**
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

**User:** `6160071` (PD# only)

→ Auto-start: `get_incident(6160071)` → identity gate → Step 0 → route (no “which skill?” prompt).

**User:** `ap_addr_ods_metrics_mc_metadata_prod` (job only, one open PD)

→ Job-only lookup → `get_incident` → Step 0 → Fail or Long Run output.

**User:** "Analyze PD 5676116" (title contains `[Long Run]`)

→ `get_incident` → identity gate → **Step 0** → Long Run → [dataops-pd-long-run](../dataops-pd-long-run/SKILL.md) (run state, AskQuestion action card, monitor/resolve path).

**User:** "Analyze PD 6134667" (title contains `[Fail]`)

→ `get_incident` → identity gate → **Step 0** → Fail → Step 1.5 Teams → alerts/runbook → DBX **4a** → Step **3** resources → **4b-leaf** → Step 7 full report + MS Teams + ADINC.

**User:** "Analyze PD 5548051"

→ `get_incident(5548051)` → Step 0 (expect Fail) → Step 1.5 Teams search → `list_alerts_from_incident(uuid)` for runbook → `list_incident_notes` → Confluence fallback if needed → DBX analysis → search past incidents.

**User:** "Analyze https://disney.pagerduty.com/incidents/Q1ZJYTU763M6O0"

→ Extract `Q1ZJYTU763M6O0` → identity gate → full report (legacy automated summary ignored for RCA if present).

**User:** "Past resolutions for ap_addr_audience_hulu_fandom_serving_prod failures"

→ Search by job name → pick most recent incident if not specified → full report with emphasis on Similar Past Incidents.

**User:** "Analyze PD 5548051 and draft MS Teams message"

→ Full report + MS Teams handoff with `@oncall-segmentation` + separate ADINC block.

**User:** "Draft DEV message for PD 5703545"

→ Step 4b-leaf on all `hourly_mrc_job` attempts → quote `ExtendedAnalysisException: [TABLE_OR_VIEW_NOT_FOUND] …` (not `ExitSecurityException` or Delta stack tail) → MS Teams block for `@oncall-adi-data-core`.

## Do not

- Run Fail **Step 7** full RCA on a classified **Long Run** without user override (use **dataops-pd-long-run** first).
- Run **dataops-pd-long-run** on a classified **Fail** without user override (Long Run skill is for duration/slowness triage, not failed-task RCA).
- Skip **Step 0** on single-incident `analyze PD {n}` / incident URL requests.
- Run **`dataopsctl.exe ask`** on minimal-input auto-start — **forbidden** unless the user explicitly opts in ([rules/dataopsctl-opt-out.mdc](../../rules/dataopsctl-opt-out.mdc)).
- Paginate **all** Data Ops incidents for 90 days when searching similar incidents — use Step 5 tiered search; **5a** is **30d / up to 3 pages** for same **job_name**.
- Claim **no similar incidents** for a DBX/LDB job without completing **Step 5a** (30d, same job, up to 3 pages) and **`list_incident_notes`** on matches shown.
- Show **Assignee —** on a **resolved** incident from `assignments` only — **always** run **Step 1-assignee** (`log_entries` when `assignments` is empty).
- Omit **`## Summary`** or render it as bullets/tables — **prose only**, 3–6 sentences (Step 6-summary).
- Fabricate **Timeline** rows without DBX/PD/notes evidence — use Step 6-timeline rules; say less when data is thin.
- Add timeline rows for **snooze**, **re-ack**, **notify**, or **second+ acknowledge** — **one opened, one first ack, one first escalate (if any), one resolved** only (+ one Datadog detection).
- Render **`## Key Evidence`**, **`## Available Notes`**, or **`## On-Call Action Plan`** in Step 7a — **removed** from full report.
- Put **`KEY EVIDENCE`**, **`PAST CONTEXT`**, or **`RECOMMENDATION`** headers in the MS Teams handoff — use **SUMMARY** → **ROOT CAUSE** → closing question only.
- Retry Datadog **trace/log** hunts after **one** failed or empty attempt when DBX MCP already returned task failure metadata (Step 3 **resource** batch is separate — still at most **one** bounded batch).
- Skip **Step 3** or report **inconclusive** without claiming resource pressure when no metric series matched — do not invent CPU/memory percentages.
- Call `list_job_runs` with large limits to hunt child for_each iterations — use **4b-sensor** instead.
- Write ad-hoc PD fetch scripts per incident — use [scripts/pd_incident_fetch.py](scripts/pd_incident_fetch.py).
- Report **wrapper errors** as root cause (`ExitSecurityException`, `Program attempted to exit with code 1`, generic `Workload failed, see run output`) — always apply Step 4b-leaf or **4b-sensor**.
- Report root cause from **log tail / stack trace alone** when `ExtendedAnalysisException`, `AnalysisException`, or `[ERROR_CODE]` messages exist on any retry attempt.
- Send DEV handoff messages without completing Step 4b-leaf and the DEV handoff gate in Step 6.
- Create ADINC Jira tickets — DEV owns creation via Support Bot `/support`; Data Ops only suggests field values.
- Put non-allowlist text in ADINC `PIPELINE`, `ISSUE_CATEGORY`, or `SOURCE_SYSTEM` field lines — use allowlist values + DEV INPUT NEEDED for uncertainty.
- Invent root cause, log lines, or resolution details not present in PagerDuty notes, **MS Teams Step 1.5** (when run), or DBX MCP responses.
- Emit **icons, emoji, or images** in MS Teams handoff blocks or paste-oriented output — use ASCII labels and bare URLs only.
- Change PagerDuty incident status (this skill is read-only) unless the user explicitly asks to resolve/update PD.
- Expose PagerDuty API tokens in output.
- Confuse the current incident with similar ones — always label match reason and PD#.
- For **multi-incident** lists, bundles, queues, and similar-incident search: use **High urgency only** (`P7OFL7L`) unless the user explicitly asks for Low urgency, both services, or names specific Low PD#s. Use **both** `P7OFL7L` and `P3CUKVY` only for **Step 1a** (alert URL → parent incident) or when the user explicitly widens scope.
- Invent workspace or run URLs — use MCP `run_page_url` or [reference.md](reference.md#databricks-url-templates).
- Use `incident_number` with `list_alerts_from_incident` — always pass the **verified UUID** from Step 1-verify.
- Skip the identity gate or use `GET /incidents?incident_number=` — use path lookup `GET /incidents/{pd#}` per [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md).
- Reuse a UUID from chat context without re-verifying against the user's PD#.
- Invent runbook URLs — only use PD alert, legacy PD summary note (URL regex), human notes, or Confluence search hits under [Data Pipelines](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841195/Data+Pipelines).
- Write ADINC RCA to Jira Comments or description — use General → Notes (`customfield_10253`) per [adinc-jira-notes.md](../adinc-jira-notes.md).
