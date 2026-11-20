# Data Operations Status Report — Reference

## Output template (Data Operations section only)

Match the structure inside the Foundations weekly message. Reference: [Vijaya's 2026-11-12 Data Enablement reply](https://teams.microsoft.com/l/message/19:de9c52b337d443f285a6a0d14ac03f53@thread.tacv2/1794507463414) (parent thread `1794507388972`).

Teams delivery uses HTML. Post with `teams channel reply` and **`--content-type html`**.

## Reference thread — format only (not a content source)

You **may** read the latest Foundations **Data Operations** reply (e.g. message `1794507463414`) to confirm **heading order, rubric labels, bullet layout, and table columns**.

You **must not** copy, paraphrase closely, or recycle Vijaya’s (or any prior week’s) sentences. Every narrative bullet must be **new prose** derived from **SKRULL**, **ADINC**, and **Cerebro** for the requested period. If Jira/minutes are thin, say so in **Sources used** — do not backfill from last week’s Teams post.

## Narrative layout — rubric bullets (mandatory)

Under each workload `<h3>`, use a **`<ul>` of `<li>` items**. Each bullet starts with a **bold rubric** (`<strong>{Rubric}:</strong>`) followed by one dense clause (semicolons inside the clause are fine). **Do not** use a single `<p>` wall of text for a workload subsection.

**Typical rubrics by subsection** (use what applies; add others when SKRULL/minutes warrant):

| Subsection | Common rubrics |
|------------|----------------|
| Linear Workloads | `EDW:` `Qlik Replicate:` `Sunshine Validator:` `BOE:` `ProdOps & Linear support:` `Security findings:` |
| Addressable Workloads | `Pipeline analysis & optimization:` `Support:` `Monitoring:` `File operations:` |
| Linear Cloud | Often one bullet without a rubric, or `Weekly ELSA production and non-production support ({dates}):` |
| Other | `ADINC automation:` `Monitoring improvements:` `Knowledge & tooling:` `Routine upkeep:` |

```html
<h1>Data Operations</h1>
<h2>Work Accomplished</h2>
<h3>Linear Workloads</h3>
<ul>
  <li><strong>EDW:</strong> Weekly EDW support (11/02–11/08); …</li>
  <li><strong>Qlik Replicate:</strong> Weekly replication, monitoring, and flow analysis (11/02–11/08)…</li>
</ul>
<h3>Addressable Workloads</h3>
<ul>
  <li><strong>Pipeline analysis &amp; optimization:</strong> Completed analyses for …</li>
  <li><strong>Support:</strong> Weekly ODS support … (11/02–11/08)…</li>
  <li><strong>Monitoring:</strong> Daily ADM, BI, DRR, Ralph and DBX pipeline monitoring …</li>
  <li><strong>File operations:</strong> Ralph OP1 file download …</li>
</ul>
<h3>Linear Cloud</h3>
<ul>
  <li>Weekly ELSA production and non-production support (11/02–11/08) across the on-call rotation; ELSA and Traffic support.</li>
</ul>
<h3>Other</h3>
<ul>
  <li><strong>Routine upkeep:</strong> …</li>
</ul>
<h2>Incidents</h2>
<table>
  <thead>
    <tr>
      <th>ADINC</th>
      <th>Incident</th>
      <th>Date</th>
      <th>Status</th>
      <th>Pipeline and DAG</th>
      <th>RCA</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>ADINC-918</td>
      <td>{summary}</td>
      <td>2026-11-07</td>
      <td>Done</td>
      <td>{PIPELINE} / {DAG} (task: {TASK})</td>
      <td>{compressed Notes}</td>
    </tr>
  </tbody>
</table>
<h2>Work in Progress</h2>
<h3>Linear Workloads</h3>
<ul>
  <li>Weekly EDW, BOE and Linear support (11/09–11/15), including …</li>
  <li>Security findings remediation for Tidal … (blocked pending validation).</li>
</ul>
<h3>Addressable Workloads</h3>
<ul>
  <li>Weekly ODS support … (11/09–11/15)…</li>
  <li><strong>Pipeline cost and performance optimization:</strong> …</li>
</ul>
<h3>Linear Cloud</h3>
<ul>
  <li>Weekly ELSA … (11/09–11/15)…</li>
</ul>
<h3>Other</h3>
<ul>
  <li><strong>ADINC automation:</strong> … (both blocked) …</li>
</ul>
```

**When zero ADINC incidents qualify:** `<h2>Incidents</h2><p>NA</p>` (no table).

**No Blockers section** — unlike Analytics platform. Blocked SKRULL or automation work is called out inside Work in Progress with `(blocked)`.

**No Others / Incidents NA under Work Accomplished** — Incidents is its own section with ADINC data only.

### Example excerpt (layout only — text must be regenerated from Jira each week)

**Addressable Workloads — Work Accomplished** (bullets, not one paragraph):

- **Pipeline analysis & optimization:** …
- **Support:** …
- **Monitoring:** …
- **File operations:** …

**Incidents table** — ADINC keys, full summary in Incident column, RCA from Notes (live `customfield_10253`).

**Other — Work in Progress** — blocked inline: `… deploy … (blocked) …`

## Workload mapping (SKRULL → subsection)

Classify using Epic title, summary keywords, labels, PIPELINE themes from linked ADINC, and meeting minutes.

| Subsection | Typical themes |
|------------|----------------|
| **Linear Workloads** | EDW, BOE, BusinessObjects, Qlik Replicate, Sunshine Validator, LDB, ASR, ProdOps, Linear support trackers, Tidal, SAP GL, Travel & Concur, GoldenGate, DMRT, TWL DR, MicroStrategy playbook (Linear) |
| **Addressable Workloads** | ODS support, Addressable BI, ADM/BI/DRR/Ralph/DBX monitoring, PagerDuty, Datadog composite monitors, pipeline optimization/cost, Ralph/BI file ops, GAM/DRR, DQ jobs, pipeline documentation |
| **Linear Cloud** | ELSA prod/non-prod support, ELSA traffic, DATG/ELSA optimization, Linear Cloud rotations |
| **Other** | ADINC automation/dashboard, RCA tooling, Confluence/Jira sync, AIX/skills, WSR/dashboard metrics, standardization, learning modules, cross-cutting monitoring improvements |

When uncertain, prefer **Other** — note ambiguity in chat only (never in the published body).

**Published body:** no **Sources used**, draft banners, or ticket counts footer.

## SKRULL Epic hierarchy (strategic layer)

On **deept SKRULL**, child Stories/Tasks link via **`parent = {EPIC-KEY}`** (next-gen). MCP `epic_link` may be null — still run `parent =` JQL.

### Epic queries

**Active epics:**

```jql
project = SKRULL
AND issuetype = Epic
AND statusCategory != Done
ORDER BY key ASC
```

**Epics with children resolved in the reporting period** (discover parents from children):

```jql
project = SKRULL
AND issuetype != Epic
AND statusCategory = Done
AND resolved >= "{start}" AND resolved <= "{end}"
AND parent IS NOT EMPTY
```

Collect distinct `parent` keys from results, then fetch each Epic.

**Epics completed in period:**

```jql
project = SKRULL
AND issuetype = Epic
AND statusCategory = Done
AND resolved >= "{start}" AND resolved <= "{end}"
ORDER BY key ASC
```

**Children of one Epic:**

```jql
project = SKRULL AND parent = {EPIC-KEY} AND issuetype != Epic ORDER BY key ASC
```

Story points: `customfield_10047` (internal rollup only).

### Initiative rollup (internal worksheet — not in published narrative)

| Signal | Rule |
|--------|------|
| Children resolved in period | `statusCategory = Done` and resolved in `[start, end]` |
| In progress | `statusCategory = In Progress` and not Blocked |
| Blocked children | `status = Blocked` |
| Epic status | Drives whether initiative appears under Accomplished vs WIP |

Use Epic **description** for scope when summarizing; roll child outcomes into one initiative bullet (no Epic keys in prose).

### Example active Epic initiatives (SKRULL — changes over time)

| Epic (title only in prose) | Typical workload subsection |
|----------------------------|----------------------------|
| EDW \| FY26 \| Support | Linear Workloads |
| BOE \| FY26 \| Support | Linear Workloads |
| DataOps \| Linear Support \| QLIK REPLICATOR \| FY26 | Linear Workloads |
| DataOps \| Linear Support \| SUNSHINE VALIDATOR \| FY26 | Linear Workloads |
| FY26 - Build Observability for Qlik Replication tool | Linear Workloads |
| ELSA Support \| FY26 | Linear Cloud |
| DataOps \| Addressable Support \| ODS \| FY26 \| Support | Addressable Workloads |
| DataOps \| Support \| Monitoring/Observability Improvements | Addressable Workloads |
| DataOps - Pipeline Cost & Performance Optimization | Addressable Workloads |
| Databricks Job Cost Optimization - Cluster Right-Sizing & Autoscaling | Addressable Workloads |
| Standardize Data Pipeline Documentation Structure and Monitors | Addressable / Other |
| DataOps \| Automation \| ADINC DBX Dashboard \| FY26 | Other |
| DataOps \| Automation \| Incident Lifecycle & Pipeline Monitoring \| FY27 | Other |

### Orphan tickets

After Epic rollups, tickets from the standard three queries with **no** `parent` (or parent not in Epic scope) → thematic rubric bullets (rotations, one-off analyses, file ops).

## ADINC Incidents table — field rules

| Column | Source |
|--------|--------|
| ADINC | `key` |
| Incident | `summary` |
| Date | `customfield_10489` (Start DatePick) → else `created` (date portion) |
| Status | `status.name` |
| Pipeline and DAG | Parse `PIPELINE:` and `DAG:` from description; append `(task: {TASK})` when `TASK:` present |
| RCA | `customfield_10253` (Notes) — see [adinc-jira-notes.md](../adinc-jira-notes.md) |

Compress RCA for the table: root cause; resolution; SLA/customer impact. Preserve factual content; remove markdown noise.

**Sort order:** descending by Date (most recent first), then key.

## Cerebro ingested DataOps meetings

From the user's meeting-ingest log, prioritize rows like:

| Date | Meeting | Cerebro ID |
|------|---------|------------|
| 2026-11-12 | SKRULL DSU | `mn-eb7882ab` |
| 2026-11-12 | DataOps Standardization update | `mn-2d725e09` |
| 2026-11-12 | ADINC Dashboard - Weekly Review | `mn-2e212b06` |

**Search patterns (VPN):**

```text
CallDynamicTool user-ads-cerebro-qa search_disney_ad_platform
  question: "List meeting notes from {start} to {end} for SKRULL DSU, DataOps Standardization, ADINC Dashboard, DataOps Incident Review with full content"
```

```text
CallDynamicTool user-ads-cerebro-qa search_knowledge
  query: "mn-eb7882ab action items decisions"
  limit: 5
```

**Fallback:** [meeting-action-items-report](../meeting-action-items-report/SKILL.md) per-day queries for the range.

## Date parsing

Same rules as [adia-status-report/reference.md](../adia-status-report/reference.md): inclusive `YYYY-MM-DD` bounds and `period_label` `M/D-M/D` for thread titles if posting.

**Weekly support windows:** When minutes say "weekly X support (11/02–11/08)", Accomplished uses the **completed** window; Work in Progress uses the **current** window (often the week after).

**Foundations thread root (Step A, not in report HTML file):** `{YYYY-MM-DD} WEEKLY REPORT & SUMMARY`, then **Fleet:** Data Platform Enablement, **Squad:** DataOps — see [teams-posting.md](teams-posting.md).

## Foundations channel IDs

Same as [adia-status-report/teams-posting.md](../adia-status-report/teams-posting.md):

| Setting | Value |
|---------|--------|
| Team ID | `dbe9c893-2d06-4b1c-8179-47e659184434` |
| Channel ID | `19:de9c52b337d443f285a6a0d14ac03f53@thread.tacv2` |

## Reading the reference thread via CLI

```bash
teams --agent channel replies \
  --team-id "dbe9c893-2d06-4b1c-8179-47e659184434" \
  --channel-id "19:de9c52b337d443f285a6a0d14ac03f53@thread.tacv2" \
  --message-id "<weekly-root-message-id>" \
  --limit 20
```

Use the reply whose `content` contains `Data Operations` (example: message id `1794507463414` under root `1794507388972` for 2026-11-12).
