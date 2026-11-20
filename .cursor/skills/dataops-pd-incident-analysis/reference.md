# Data Ops PD Incident Analysis — Reference

## PagerDuty services

| Name | ID | Urgency |
|------|-----|---------|
| Ad Platform Data Ops Service High Urgency | `P7OFL7L` | High |
| Ad Platform Data Ops Service Low Urgency | `P3CUKVY` | Low |

### Default scope (listing / similar-incident / multi-incident work)

Unless the user explicitly asks for Low urgency, both services, or names a Low-urgency PD#/alert: use **`P7OFL7L` only** for `list_incidents` and similar-incident search. **Exceptions:** (1) user-supplied PD#/URL — analyze regardless of service; (2) **alert URL → parent incident** (Step 1a) — search **both** `P7OFL7L` and `P3CUKVY` until the parent incident is found. Full rules: [SKILL.md](SKILL.md) — section **Default PagerDuty scope (urgency) — mandatory**.

## PD URL pattern

```
https://disney.pagerduty.com/incidents/{incident_id}
```

`incident_id` in URLs is the UUID (e.g. `Q1ZJYTU763M6O0`). PD# (e.g. `5548051`) is the numeric `incident_number`.

**Identity verification (mandatory):** Before trusting or mutating any incident, follow [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md). Always run the **identity gate** after `get_incident` or `GET /incidents/{pd_or_uuid}` — assert `incident_number` and/or UUID match user input. **Never** use `GET /incidents?incident_number=` (invalid filter).

`get_incident` accepts PD# or UUID. **`list_alerts_from_incident` requires the verified UUID**, not the PD#.

## Incident assignee (resolved)

PagerDuty UI timeline vs REST `assignments` on the incident object:

| UI timeline | REST field | Report use |
|-------------|------------|------------|
| “Assigned to …” | `assign_log_entry` | Fallback when `assignments` empty |
| “Acknowledged by …” | `acknowledge_log_entry` → `agent.summary` | Preferred when resolved |
| Assignee column (open) | `assignments[].assignee.summary` | Use first when non-empty |
| Resolved via integration/API | `assignments: []` | **Normal** — active assignee cleared; **still show** name from log entries |

**Mandatory (open and resolved):** Step **1-assignee** in [SKILL.md](SKILL.md). Fetch `GET /incidents/{uuid}/log_entries?limit=100` when `status == resolved` or `assignments` is empty. Newest-first: `acknowledge_log_entry` then `assign_log_entry`.

**Example #6204259:** API `assignments: []` after resolve; log entries → **Assignee:** `Praveen Sadineni (acknowledged; resolved)`.

`pd_incident_fetch.py` sets `parsed.assignee` `{name, source}` (same as `parsed.responder`).

## Job-only lookup

When the user provides a **job or DAG name** but no PD# (minimal input trigger):

1. `browse_incidents` **list** — `service_ids: [P7OFL7L]`, `statuses: [triggered, acknowledged]`, `since` = now − 7 days, `limit` = 100 (one page).
2. Filter incidents whose `title` or `summary` contains the job/DAG token (case-insensitive). For DAGs, also match `dag_id:` / `Dag-{name}` fragments.
3. **Pick one:** prefer **acknowledged/triggered** over resolved; among open, **most recent** `created_at`. If none open, pick most recent **resolved** in window and say one line that no open PD exists (still analyze if user intent is RCA).
4. Run **identity gate** on the chosen `incident_number`, then **Step 0**.

Do not ask the user to paste a PD# when exactly one open incident matches the job.

## Alert type classification

Used by [SKILL.md](SKILL.md) **Step 0**. Parent skill routes **Long Run** to [dataops-pd-long-run](../dataops-pd-long-run/SKILL.md); **Fail** continues incident analysis Steps 1.5–7.

| Type | Title signals (case-insensitive) | Alert tie-break |
|------|----------------------------------|-----------------|
| **Long Run** | `[Long Run]` in title | `running_spans.duration`, `ongoing_duration`, `anomalies(` in monitor query; no explicit fail metric |
| **Fail** | `[Fail]`; `DataOps\|PROD\|Fail\|`; `DataOps\|DBX\|PROD\|Fail\|` | `status:error`, `dagrun.duration.failed`, body `Failed: Task`, Airflow “dag … has failed” |

**Examples**

| Title | Step 0 result |
|-------|----------------|
| `[AP][ODS][Metrics][Fail] ap_addr_ods_metrics_drax_deals_hourly_prod` | Fail |
| `[AP][BI][Goldmine][Long Run] ap_addr_bi_gen_programmatic_prod on env:prod,…` | Long Run |
| `DataOps\|PROD\|Fail\|LDB\|Dag-prod-ldb_linear_consumption` | Fail |
| `DataOps\|PROD\|Dag Change\|DRR\| Dag -` | Ambiguous — peek alert or ask user |

**User override:** Full RCA / ADINC / “analyze” with explicit Fail ask on a Long Run PD → stay on incident analysis. `monitor long run` / long-run skill name → long-run skill even if title also looks Fail.

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
2. **Legacy PD summary note** — if a note starts with `[Incident agent — automated summary]`, regex the **first** `https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/\d+…` URL in the **full** note body (do not use Recommendations alone). Use only for runbook discovery; **do not** treat legacy text as current RCA.
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

## Runbook (Step 7a)

**Placement:** Eighth section — after **`## MS Teams channel context`**, immediately before **`## On-Call Recommendation`**.

**Workflow:** Step **2c** in [SKILL.md](SKILL.md) (always when `job_name` is known).

**Standards:**

| Doc | Purpose |
|-----|---------|
| [Data Pipelines root](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841195/Data+Pipelines) | Search ancestor `192841195` |
| [Confluence structure — Standard](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard) | Team/subteam folders, alert taxonomy |
| [Pipeline Documentation — Standard](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895775777/Pipeline+Documentation+-+Standard) | Metadata (§1) + runbook (§2) on same leaf |

### Render template

**Keep the section minimal:** one table, then optional Confluence runbook text. No comparison prose, no ancestry line, no flag bullets outside the table.

```markdown
## Runbook

| Source | Runbook | Flags |
|--------|---------|-------|
| **PagerDuty alert** | [DBX - ap_addr_ods_metrics_mc_metadata_prod](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192842258/…) | — |
| **Canonical (Data Pipelines)** | [ap_addr_ods_metrics_mc_metadata_prod](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192842258/…) | — |

### From Confluence ({Fail | Long Run})

{**2.2 Triage steps** only — see [§2 excerpt by alert type](#confluence-2-excerpt-by-alert-type)}
```

| **Flags** value | When |
|-----------------|------|
| `—` | No issue for that row |
| `URL mismatch` | PD page ID ≠ canonical page ID |
| `Missing leaf` | No ranked leaf under `192841195` |
| `Placement mismatch` | Canonical ancestry team ≠ title taxonomy ([mapping](#expected-placement-from-pd-title)) |

Both flags on Canonical row allowed: e.g. `Placement mismatch` only on canonical; `URL mismatch` on PD row when IDs differ.

### Confluence §2 excerpt by alert type

Use **`alert_type`** from **Step 0** (`Fail` \| `Long Run`). Heading: **`### From Confluence (Fail)`** or **`### From Confluence (Long Run)`**.

After the runbook table, when a leaf page was resolved:

1. `confluence_get_page` — canonical page ID (prefer over PD).
2. From `body.storage`, extract **`2.2 Triage steps`** / **`### 2.2`** only — **no** 2.1, 2.3–2.7, no §1, no §3.
3. Plain-text numbered list (preserve links as markdown).
4. **Fail:** include all **2.2** steps; if `job_name` ends **`_dq_prod`**, do not drop steps mentioning **DQ** / sub-job.
5. **Long Run:** include **2.2** steps that mention **duration**, **SLA**, **09:00 UTC**, **anomaly**, or **dashboard**; if none match, include the full **2.2** list.
6. No **2.2** block: one line — `No triage steps on canonical page — open link above.`
7. Cap ~25 lines; suffix `(truncated)` if needed.

### Expected placement from PD title

Parse bracket segments before the job name (same taxonomy as ADINC title). Map to the **first team folder** expected under Data Pipelines:

| PD title signal | Expected ancestry prefix (under Data Pipelines) |
|-----------------|--------------------------------------------------|
| `[AP][ODS][Core]` / `[ODS][Core]` | `ODS → Core` |
| `[AP][ODS][Metrics]` / `[ODS][Metrics]` | `ODS → Metrics` |
| `[AP][ADM][segmentation]` | `ADM → Segmentation` |
| `[AP][ADM]` targeting / audience | `ADM → Targeting` |
| `[AP][ADM]` measurement | `ADM → Measurement` |
| `[AP][BI][Goldmine]` / Addressable BI | `BI → Addressable → {group folder}` (see [pipeline-docs-audit/reference.md](../pipeline-docs-audit/reference.md)) |
| `[AP][BI]` Linear / LDB / ASR / DART | `BI → Linear → {subteam}` |
| `[Media]` | `Media → ProdOps` |

**Placement mismatch flag** when the Confluence leaf’s ancestry **team** (second segment after Data Pipelines) ≠ expected team — e.g. alert **`[AP][ODS][Metrics]`** but leaf under **`ADM → Segmentation`**. Include both **expected** and **actual** paths in the flag text.

**Missing leaf flag** when Step 2c CQL (title + normalized stems + `text ~`) returns no ranked leaf, or Confluence MCP is down and PD also has no URL.

### Exemplar — PD #6204259

```markdown
## Runbook

| Source | Runbook | Flags |
|--------|---------|-------|
| **PagerDuty alert** | [DBX - ap_addr_ods_metrics_mc_metadata_prod](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192842258/DBX+-+ap_addr_ods_metrics_mc_metadata_prod) | — |
| **Canonical (Data Pipelines)** | [ap_addr_ods_metrics_mc_metadata_prod](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192842258/ap_addr_ods_metrics_mc_metadata_prod) | — |

### From Confluence (Fail)

1. Open Job / DAG link …
2. …
```

### MS Teams handoff

`Runbook:` in the SUMMARY block = **PagerDuty alert URL** when present; else **canonical** URL from Step 2c; else `—`. Do not paste **`### From Confluence`** into Teams.

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

**Upstream ownership:** When DBX analysis shows the leaf failure is in a different pipeline than the PD title job (e.g. serving alert but inbound/Hightouch failed), keep Team/tag from the **PD title** for the MS Teams `@` mention, and add a second `@` tag or "CC" line in **`## On-Call Recommendation`** if the upstream job maps to a different on-call group.

### ads-data-bi-support search (Step 1.5)

Before Datadog trace pulls or DBX MCP, search channel **[ads-data-bi-support](https://teams.microsoft.com/l/channel/19%3Ad8264169c3d34e6182652bda83c14e57%40thread.tacv2/ads-data-bi-support?groupId=00792fe9-ce40-4530-9561-d415894f214f&tenantId=56b731a8-a2ac-4c32-bf6b-616810e913c6)** for the **job name** (and related tokens) in the **last 30 days**. Use `teams` CLI — see [teams-cli/SKILL.md](../teams-cli/SKILL.md):

`teams --agent search messages --query "{job_name} OR fail OR failed" --team "<team>" --channel "ads-data-bi-support"`

Open the best thread with `message list --from-url` when a URL is returned.

## MS Teams channel context (Step 7a)

**Placement:** Section 7 — after **`## Root Cause`**.

**Source:** **Step 1.5** only — [ads-data-bi-support](https://teams.microsoft.com/l/channel/19%3Ad8264169c3d34e6182652bda83c14e57%40thread.tacv2/ads-data-bi-support) threads from the last **30 days**.

| Include | Exclude |
|---------|---------|
| Thread summaries, short quotes, sender/date | Human **PagerDuty notes** (any note from `list_incident_notes`) |
| Links to Teams threads when available | “No human PD notes”, snooze/ack narrative from PD log |
| Prior agreed actions **in channel** | Legacy automated PD summary text |

2–6 bullets, or one line: `No relevant threads in ads-data-bi-support (last 30d) for this job.`

Thread takeaways may inform **Root Cause**, **On-Call Recommendation**, and the Teams **closing question** — but **not** be duplicated as PD note content in this section.

## MS Teams handoff message

### Paste safety — no icons or images

Output for Teams copy-paste must be **plain text and ASCII labels only**. Do **not** include inline icons (PagerDuty, Databricks, Confluence glyphs), emoji, or markdown images — they **break or render wrong** when pasted into Teams. Use lines such as `PD: https://…` and `Databricks run: https://…` instead of logo characters or rich previews.

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
| **On-Call Recommendation** | Full report only | Step 6-recommendation | **1–2 lines** — resolve / keep open / escalate |
| **SUMMARY** | MS Teams | Step 7b template | PD#, status, run, workspace, DBX run URL, runbook — **omit** Job (line 1 title), Urgency, Team, Opened, PD URL |
| **ROOT CAUSE** | MS Teams | Step 4b-leaf / DBX | 2–4 sentences — **verbatim leaf error**, include `task_key` / attempt; never wrapper |
| **Closing line** | MS Teams (last line) | Step 6-teams-close | Direct **question or comment** to on-call (`@tag`) — not an ALL CAPS header |
| **ADINC FIELDS** | ADINC block | Step 6b | All 10 ADINC description fields |
| **DEV INPUT NEEDED** | ADINC block | Step 6b flags | Bullets for fields needing dev input — omit if none |

**MS Teams exclusions:** Do not include alert URL (reachable from PD link), **MS Teams channel context** (full report section), **On-Call Recommendation**, **Similar Past Incidents**, or ADINC fields in the Teams message.

**MS Teams ROOT CAUSE rule:** Must pass the Step 6 DEV handoff gate — leaf error only. If legacy automated summary text in PD disagrees with Step 4b-leaf, **trust DBX leaf error** for Teams; mention legacy discrepancy in **Root Cause** if needed.

Plain-text template inside a ` ```text ` code block under heading `## MS Teams message`:

```
{ms_teams_title_line} {oncall_tag}

SUMMARY
PD#:        {incident_number}
Status:     {Status}
Run:        {run_id or —}
Workspace:  {workspace or —}
Databricks run: {run_page_url or —}
Runbook:    {runbook_url or —}

ROOT CAUSE
{2–4 sentences — task_key, attempt, verbatim leaf error from Step 4b-leaf; reference.md#leaf-error-extraction}

{@oncall_tag} — {direct question or comment, e.g. Can you confirm repair run … fixed hour … before we resolve PD #{n}?}
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
Run:        344473032276319
Workspace:  gen-prod-uw2
Databricks run: https://ads-data-gen-prod-uw2.cloud.databricks.com/?o=161202889771344#job/573027999471240/run/344473032276319
Runbook:    https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192841547/DBX+Fandom+Hulu

ROOT CAUSE
Task hulu_fandom_inbound_job_sensor (attempts exhausted) — sensor error "No successful job or task run found, not ready" on every retry; upstream inbound run 447313802235465 never succeeded within the 4h window (16:00 UTC trigger). All downstream serving tasks SKIPPED (UPSTREAM_FAILED).

@oncall-segmentation — can you confirm inbound run 447313802235465 is healthy so we can re-run serving, or should this PD stay open?
```

**On-Call Recommendation** (in full report, not Teams — **1–2 lines**):

```
Keep PD open; escalate to @oncall-segmentation — repair inbound run 447313802235465 (empty Hightouch segment data) before re-running serving job 573027999471240.
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

## Legacy automated summary note format (deprecated for RCA)

Historical incidents may still contain notes from the **decommissioned** PagerDuty Incident agent. Structure was:

```
[Incident agent — automated summary]

Root cause:
…

Evidence from tools:
…

Recommendations:
…
```

**Skill rule:** Do **not** output **AI Agent Recommendations**. Do **not** use these sections for **Root Cause** or **Key Evidence** on the **current** incident — use **DBX Step 4b-leaf** + PD alert + human notes. The **only** allowed use on the **current** incident is **runbook URL regex** from the full note body (see Confluence runbook fallback above).

## Human vs legacy automated notes

| Prefix | Type | Use |
|--------|------|-----|
| `[Incident agent — automated summary]` | Legacy | Runbook URL discovery only; **never** current RCA |
| Anything else | Human | Resolution quotes — fold into **Summary** / **Root Cause** / **On-Call Recommendation** (no **Available Notes** section) |

## Similar-incident search

**Step 5a — Same job (30d) is mandatory** when the current incident has a **`job_name`** or DAG token in the title. See [SKILL.md](SKILL.md) Step 5a.

| Tier | Lookback | Max pages | Use when |
|------|----------|-----------|----------|
| **5a Same job** | **30 days** | **3** (`limit=100`) | **Always** when job/DAG known — paginate until `more=false` or 3 pages |
| 1 Same title | 30 days | 1 | Supplement 5a when useful |
| 2 | 90 days | 3 cumulative | **5a + tier 1** found **0** same-job/title |
| 3 | User-specified | 5 max | User asks for deep history |

**Helper script:** `scripts/pd_incident_fetch.py` — use **`--similar-days 30 --max-pages 3`** for Step **5a** (default `--max-pages` is **3**).

```bash
python ~/.cursor/skills/dataops-pd-incident-analysis/scripts/pd_incident_fetch.py 6204259
python ~/.cursor/skills/dataops-pd-incident-analysis/scripts/pd_incident_fetch.py 6204259 --similar-days 90 --max-pages 3
python ~/.cursor/skills/dataops-pd-incident-analysis/scripts/pd_incident_fetch.py 6204259 --include-low
```

Default similar-incident search uses **High Urgency** (`P7OFL7L`) only; pass **`--include-low`** when the user widens scope.

Client-side filter (API has no text search):

```python
# Step 5a — same job (mandatory)
same_job = job_name and (job_name in (inc.title or "") or job_name in (inc.summary or ""))
same_title = normalized(summary) == normalized(current.summary)
same_run   = run_id and f"@databricks_job_run_id:{run_id}" in incident.title
```

After **5a**, **`list_incident_notes`** on the **most recent** same-job PD (for **Incident Details** row). **Incident Details** shows **one** peer row + legend with **total** 30d count.

**Output rule:** Do not write “no similar incidents in 30d” if **5a** found any same-job PD#.

## Resolution inference (past incidents)

Use this priority when writing "How it was resolved":

1. **Human note** explicitly stating fix (repair run, re-run, config change, acknowledged as benign, etc.) — quote ≤200 chars.
2. **Legacy Root cause line** from that past incident’s automated summary (**one line**, labeled historical) if step 1 is empty and the incident predates decommission.
3. **Fallback:** "Resolved at {resolved_at PT}. No resolution notes in PagerDuty."

Never claim a specific fix without note evidence.

## Datadog resource analysis

Step **3** in [SKILL.md](SKILL.md). Read-only checks via **`plugin-datadog-datadog`** (not AIX `pup` unless MCP is down). Goal: see whether **CPU or memory** during the incident window plausibly explains a **Fail** or **Long Run**, without replacing DBX leaf-error RCA.

### Incident window

| Alert type | `from` / `to` (UTC in queries; show **PT** in report) |
|------------|--------------------------------------------------------|
| Fail | `incident.created_at − 30m` → `created_at + 15m` (or run end from DBX) |
| Long Run | DBX run `start_time − 15m` → now or run end |
| Baseline | Same length as incident window, ending at incident window `from` |

Pin windows once; pass the same `from`/`to` to every metric query in the batch.

### Scope — where to get tags

| Source | Fields |
|--------|--------|
| PD alert `body` (Step 1b) | `dag_id`, `airflow_id`, `env`, `team`, `pipeline`, hostname, monitor grouping tags |
| Incident title | `job_name`, DAG name (`Dag-prod-ldb_*`) |
| DBX `get_run_details` (after 4a) | `cluster_id`, cluster name, run start/end |
| Job Trace URL in alert | `service`, `env`, `host` query parameters |

### Pipeline-specific paths

**Databricks (DBX)**

1. After **Step 4a**, read cluster / job tags from `get_run_details`.
2. `search_datadog_metrics` with `query: "databricks"` or `"spark"` and `tag_filter` including `job_name:{job}` when available.
3. Query **CPU** and **memory** metrics that support those tags (names vary by integration — use search results, not hard-coded guesses).
4. If cluster-scoped series exist, report **max** and **avg** for incident vs baseline windows.

**Airflow / LDB**

1. Scope with `dag_id:{dag}`, `airflow_id:{instance}` (e.g. `uaplinear-prod`), `env:prod`, `pipeline:ldb` from alert tags.
2. Search metrics containing `airflow` or worker host `system.cpu.*` / `system.mem.*` with matching tags.
3. Worker CPU spike during failed dagrun window → **resource_likely** only when DBX/Airflow task error does not already explain the fail (e.g. generic timeout).

**Goldmine / non-DBX**

Use whatever compute tags appear in the alert; if only `dag_id` is known, scope Airflow workers for that DAG.

### Verdict (report verbatim)

| Verdict | Meaning |
|---------|---------|
| `resource_likely` | Sustained high CPU and/or memory pressure or OOM signals in window; compatible with TIMEDOUT/hang/slow run |
| `resource_unlikely` | Resources normal in window; application/upstream leaf error likely |
| `inconclusive` | No matching metric series (list tags tried) |
| `skipped` | Datadog MCP unavailable |

### Example metric batch (`get_datadog_metric`)

Replace metric names after `search_datadog_metrics`. Two windows = incident + baseline (scalar `max` + `avg`).

```json
{
  "from": "2026-11-11T20:30:00Z",
  "to": "2026-11-11T21:15:00Z",
  "response_format": "scalar",
  "queries": [
    {
      "name": "cpu_max",
      "metric_name": "system.cpu.user",
      "space_aggregator": "avg",
      "aggregator": "max",
      "filters": ["dag_id:prod-ldb_linear_consumption", "env:prod"]
    },
    {
      "name": "mem_pct",
      "metric_name": "system.mem.pct_usable",
      "space_aggregator": "avg",
      "aggregator": "min",
      "filters": ["dag_id:prod-ldb_linear_consumption", "env:prod"]
    }
  ]
}
```

Low `system.mem.pct_usable` **min** during the window = memory pressure. Document actual metric names returned by search.

## Report Summary (Step 7a)

**Placement:** First section after `# Incident Analysis — #{pd}` — **above** the metadata table. Readers should not scroll to understand the incident.

**Format:** `## Summary` then **one prose block** (optionally 2 short paragraphs). **No bullets, no tables, no code blocks.**

**Length:** 3–6 sentences. Target ~80–120 words unless the incident has multiple concurrent threads (repair + upstream + PD auto-resolve).

### Content checklist (Fail / DQ)

| Sentence | Content |
|----------|---------|
| 1 | Job + leaf DQ task + **partition/hour** (UTC) |
| 2 | Failure mode (constraint count, ERROR vs WARN, sensor vs leaf) |
| 3 | Follow-up runs (repair at {time}, same failure / partial fix) |
| 4 | **PD status vs fix status** — critical when they diverge |
| 5 | Current remediation (upstream rerun queued/running) |
| 6 | Prior pattern from Step 5a (date + fix that worked) |

### Exemplar — PD #6204259 (MC metadata DQ)

> The hourly MC metadata DQ check `dq_a_line_item_metrics` failed for **hour 2026-11-18 10:00 UTC**: two error-level data quality rules were broken. A repair of the DQ run at 16:30 failed the same way. PagerDuty closed the page on its own at 18:58, so the page is **resolved but the problem isn't fixed**. Someone has started a re-run of the upstream line item metrics for that hour; it was queued at 19:08 UTC. The last time this happened (Nov 17), the fix was exactly that: correct the hour's data, then repair the DQ run.

Agents should match this **tone and density** — facts only from MCP/notes/Teams, no speculation.

### Long Run (when user runs full Fail-style report or long-run → full analysis)

| Sentence | Content |
|----------|---------|
| 1 | Job + Long Run monitor fired (duration anomaly) |
| 2 | Run outcome vs baseline minutes |
| 3 | PD already resolved vs still open |
| 4 | Recurring pattern count (Step 5a) if noisy |

## Report Timeline (Step 7a)

**Placement:** Second section — immediately after **`## Summary`**.

**Heading:** `## Timeline (in PST time)` (exact string).

**Format:**

| Time | Event |
|------|--------|
| … | … |

Convert DBX millis and PD ISO timestamps with `America/Los_Angeles`. Prefer **clock times on the incident day** (`13:42–14:42`) over full datetimes when all events share one day.

**Event rows should cover (when data exists):**

**Pipeline (DBX)**

1. Primary / repair DQ (or failed) run start and early successes  
2. Partition/sensors — attempt counts and message (`Not ready to process`)  
3. Upstream producer job window + SUCCESS + linked run  
4. Leaf DQ fail (constraint count, task name)  
5. Repair fail window  
6. Follow-up upstream repair + **QUEUED** / concurrency explanation  

**Paging (max one row each — no snooze / re-ack / notify spam)**

| Row | Source | Event text pattern |
|-----|--------|-------------------|
| **Datadog detection** | Alert `creation_time` (Step 1b) | `**Datadog** — monitor {id} detected …` |
| **Incident opened** | `incident.created_at` | `**PagerDuty** — incident #{n} opened` |
| **First acknowledge** | Earliest `acknowledge_log_entry` with human `agent` | `**On-call** — {name} acknowledged ({channel})` |
| **First escalation** | Earliest `escalate_log_entry` or escalation `delegate_log_entry` | `**PagerDuty** — escalated to {target}` — **omit if none** |
| **Resolved** | `resolved_at` + `resolve_log_entry` | `**PagerDuty** — {name} resolved` or `**PagerDuty** — auto-resolved (integration API)` |

Prefixes **Datadog** / **PagerDuty** / **On-call** only. Parse log entries **oldest-first** to find first ack and first escalate.

### Exemplar — PD #6204259

| Time | Event |
|------|--------|
| 8:59 | **Datadog** — monitor [271437528](https://disneystreaming.datadoghq.com/monitors/271437528) detected failure on `ap_addr_ods_metrics_mc_metadata_dq_prod` (`creation_time` on PD alert) |
| 11:57 | DQ run for hour 10 starts. The 17 dimension checks pass by 12:09 |
| 11:58–14:49 | `a_line_item_metrics_history_partition_sensor` waits for the hour-10 data: 17 failed checks ("Not ready to process"), then passes |
| 13:42–14:42 | Upstream `line_item_metrics_job` builds hour 10 and succeeds (run [936936501505331](https://ads-data-sox-prod-uw2.cloud.databricks.com/?o=3352005904589238#job/870337267486358/run/936936501505331)) |
| 14:49 | `dq_a_line_item_metrics` fails: 2 rules broken |
| 16:30–16:55 | DQ repair fails with the same error |
| 10:07 | Upstream repair for hour 10 started; `line_item_metrics_job` **stays QUEUED** (max 3 concurrent runs — 15:55, 16:55, 17:55 still running) |
| 9:01 | **PagerDuty** — incident [#6204259](https://disney.pagerduty.com/incidents/Q36KX72I6SXI7T) opened (High Urgency) |
| 9:04 | **On-call** — Praveen Sadineni acknowledged (phone) — *first ack only* |
| 10:58 | **PagerDuty** — auto-resolved (integration API) — *no escalation row on this incident* |

**Ordering:** Pipeline block first when run precedes page; paging tail is **Datadog (above) → opened → first ack → first escalate (if any) → resolved** — never extra PD rows.

## Incident Details (Step 7a)

**Placement:** Third section — immediately after **`## Timeline (in PST time)`**.

**Purpose:** One compact table for paging context. **No Runbook row** — use **`## Runbook`**. **Do not** add a standalone **PD link** row — the **PD alert** cell is the incident URL.

| Row | Source |
|-----|--------|
| **PD alert** | `title` truncated at first ` on `; markdown link to `https://disney.pagerduty.com/incidents/{verified_uuid}` |
| **Datadog monitor** | Parse monitor id from alert `client_url` (`/monitors/{id}`) or `details` body; link `https://disneystreaming.datadoghq.com/monitors/{id}` |
| **Assignee** | Step 1-assignee |
| **Job / Run ID** | Title + alert body; see title parsing |
| **Similar past incidents** | Step **5a** — **one row** (most recent peer) + legend `{N} same-job PDs…; showing most recent one.` |

### Exemplar — PD #6204259

| Field | Value |
|-------|--------|
| **PD alert** | [[AP][ODS][Metrics][Fail] ap_addr_ods_metrics_mc_metadata_dq_prod](https://disney.pagerduty.com/incidents/Q36KX72I6SXI7T) |
| **Status** | Resolved |
| **Urgency** | High (`P7OFL7L`) |
| **Opened** | Nov 18, 2026 9:01 AM PT |
| **Resolved** | Nov 18, 2026 10:58 AM PT |
| **Assignee** | Praveen Sadineni (acknowledged; resolved) |
| **Job** | `ap_addr_ods_metrics_mc_metadata_dq_prod` |
| **Run ID** | `772819542218407` |
| **Team** | ODS / Metrics |
| **Oncall MS Teams Tag** | `@oncall-ods-metrics` |
| **Datadog monitor** | [Monitor 271437528](https://disneystreaming.datadoghq.com/monitors/271437528) |

**### Similar past incidents (30d, same job)**

*27 same-job PDs on High in the last 30 days; showing most recent one.*

| Opened (PST) | PD alert | Notes |
|--------------|----------|-------|
| Nov 17, 2026 5:48 AM | [[AP][ODS][Metrics][Fail] ap_addr_ods_metrics_mc_metadata_dq_prod](https://disney.pagerduty.com/incidents/Q0F5TEZZDQLVNX) | Resolved — same DQ Fail family |

### Report placement (Step 7a — section order)

| # | Section | Notes |
|---|---------|--------|
| 1 | `## Summary` | Prose only |
| 2 | `## Timeline (in PST time)` | Step 6-timeline — [#report-timeline-step-7a](#report-timeline-step-7a) |
| 3 | `## Incident Details` | No runbook row |
| 4 | `## Datadog Analysis (resources)` | **Unchanged** — Step 3; [#datadog-resource-analysis](#datadog-resource-analysis) |
| 5 | `## Databricks Analysis` | **Unchanged** — Step 4; [#databricks-analysis](#databricks-analysis) — primary run, failed tasks, leaf logs, upstream |
| 6 | `## Root Cause` | **Unchanged** — leaf narrative; no separate Key Evidence section |
| 7 | `## MS Teams channel context` | Step **1.5** threads only — [#ms-teams-channel-context-step-7a](#ms-teams-channel-context-step-7a) |
| 8 | `## Runbook` | Step **2c** — PD alert URL vs canonical Confluence leaf — [#runbook-step-7a](#runbook-step-7a) |
| 9 | `## On-Call Recommendation` | Step 6-recommendation — **1–2 lines** (was PD disposition) |

**Similar past incidents:** Step **5a** only inside **`## Incident Details`** (sub-table). No standalone `## Similar Past Incidents` section.

**Removed from Step 7a:** `## Key Evidence`, `## Available Notes`, `## On-Call Action Plan`. **MS Teams handoff (7b):** `SUMMARY` → `ROOT CAUSE` → closing question to on-call only.

Render **`## Datadog Analysis (resources)`** (section 4) with:

- Verdict + time window + tags tried
- CPU: incident vs baseline (numbers only if returned by Datadog)
- Memory: same
- **Interpretation** — one short paragraph for on-call (does this look like a resource problem?)

### Performance

Target **≤ 45s** for Step 3: one discovery search + one batched query (or one `execute_code` script). Do not paginate unrelated logs unless metrics are inconclusive and OOM keywords are still needed (same batch).

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

### Upstream run extraction (from PD notes and DBX)

Regex patterns (collect all, dedupe):

- `Run ID:\s*(\d+)`
- `run_id:\s*(\d+)`
- `@databricks_job_run_id:(\d+)`
- `parent run_id:\s*(\d+)`

Cross-reference with job names in **human** notes or DBX output (backtick job names or `job \`name\``). Ignore legacy automated summary **for current-incident RCA**.

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
| PD fetch (Steps 1–2) | &lt; 20s | MCP parallel or `pd_incident_fetch.py` |
| Datadog resources (Step 3) | &lt; 45s | One metric batch; discover names via search |
| DBX primary run (Step 4) | &lt; 60s | 2–3 MCP calls; parallel workspace probe |
| Similar incidents (Step 5a) | &lt; 45s | 30d, up to 3 pages + notes on **1** peer |
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

- **Root cause (historical):** Upstream `ap_addr_audience_hulu_fandom_inbound_prod` run 447313802235465 failed (`segment-data-loading-app`).
- **How it was resolved:** Resolved at Jul 20, 2026 11:14 AM PT; inbound pipeline failure blocked serving sensor (same upstream run family).
- **Relevant notes:** —

## MCP tools used

| Tool | Server | Purpose |
|------|--------|---------|
| `get_incident` | PagerDuty | Look up PD# / ID — then [identity gate](../pagerduty-incident-identity/reference.md) |
| `list_alerts_from_incident` | PagerDuty | Alert custom details — **Job Runbook URL**, DBX/trace links |
| `confluence_search_content` | Confluence | CQL search for runbook under Data Pipelines (`192841195`) |
| `list_incident_notes` | PagerDuty | Human notes; legacy automated summary (runbook URL only) |
| `teams --agent search messages` / `message list` | teams CLI | Step 1.5 — ads-data-bi-support |
| `list_incidents` | PagerDuty | Historical similar-incident search |
| `get_run_details` | ads-databricks | Workspace, run state, tasks, run URL |
| `analyze_job_task_failure` | ads-databricks | Failed tasks + error output |
| `get_run_output` | ads-databricks | Task-level logs when needed |
| `list_jobs` / `list_job_runs` | ads-databricks | Long Run run resolution |
| `get_job_details` | ads-databricks | Job timeout / schedule |
| `identify_stuck_runs` | ads-databricks | Optional hung-run check |
