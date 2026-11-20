---
name: dataops-status-report
description: >-
  Generates the Foundations Engineering weekly **Data Operations** narrative
  (Work Accomplished and Work in Progress by workload area) plus an **Incidents**
  ADINC table for the reporting week. Synthesizes SKRULL Jira Epics and child
  tickets, ADINC incidents, and Cerebro-ingested DataOps meeting notes (SKRULL DSU,
  Standardization, ADINC dashboard, Incident Review, RCA). Use when the user asks
  for DataOps weekly status, Data Operations section, Foundations weekly Data Ops
  summary, or the format in the Data Enablement thread reference message.
---

# Data Operations — Weekly Status (Foundations)

Produce the **Data Operations** subsection for the [Foundations Engineering - Weekly Status](https://teams.microsoft.com/l/channel/19%3Ade9c52b337d443f285a6a0d14ac03f53%40thread.tacv2/Foundations%20Engineering%20-%20Weekly%20Status?groupId=dbe9c893-2d06-4b1c-8179-47e659184434) rollup — same style as the **Data Operations** block in [this reference message](https://teams.microsoft.com/l/message/19:de9c52b337d443f285a6a0d14ac03f53@thread.tacv2/1794507388972).

**Not** a ticket-by-ticket SKRULL export. Write **executive narrative prose** by workload area, then a **structured Incidents table** with ADINC keys (only in that table).

Companion narratives: [analytics-status-report](../analytics-status-report/SKILL.md) (Analytics platform), [adia-status-report](../adia-status-report/SKILL.md) (ADIA ticket list).

## Configuration

| Setting | Value |
|---------|--------|
| Jira — delivery work | `SKRULL` on [deept.atlassian.net](https://deept.atlassian.net/) |
| Jira — incidents | `ADINC` (Notes = RCA → [adinc-jira-notes.md](../adinc-jira-notes.md)) |
| MCP | `user-jira-server` / `jira_search_issues`, `jira_get_issue`, `fields: "*all"` |
| Default SKRULL scope | **Whole project** (Data Ops squad); optional assignee filter from user |
| Cerebro MCP | `user-ads-cerebro-qa` (VPN); meeting notes KB |
| Foundations post channel | [teams-posting.md](teams-posting.md) — 3-message thread (not adia ticket-list format) |
| Reference excerpt | Message `1794507463414` (reply under `1794507388972`) |

## Inputs

1. **Period** — date range or week ending today. Default: **current reporting week** (typically Wed–Tue or user dates). See [reference.md](reference.md).
2. **SKRULL scope** — default all SKRULL activity in period; user may restrict assignees or Epic labels.
3. **Deliverable** — **Data Operations section only** (paste into parent weekly doc) unless user asks to post.

## Workflow (strict order)

```
Step 0   Teams connectivity (read optional channel + optional post)
Step 1   Parse period → start_date, end_date, period_label
Step 2   Jira SKRULL — Epics + child rollups + ticket queries (synthesis)
Step 3   Jira ADINC — incidents for the reporting week → table rows
Step 4   Cerebro — DataOps-related meeting notes in period
Step 5   Optional — teams calendar cross-check for ingest log (Date, Meeting, mn-*)
Step 6   Synthesize narrative + Incidents table (see Output format)
Step 7   WRITE FULL SECTION in chat
Step 8   AskQuestion — post or copy-only
Step 9   Post if confirmed (brief outcome only)
```

### Step 0 — Microsoft Teams

Same as [adia-status-report Step 0](../adia-status-report/SKILL.md): `teams --agent auth status`, refresh if needed.

### Steps 2–4 — Gather sources (run in parallel when possible)

**SKRULL (Step 2)** — Same **two-layer model** as [analytics-status-report](../analytics-status-report/SKILL.md): **Epics (strategic)** + **children (tactical)** + orphan tickets. See [reference.md](reference.md) **SKRULL Epic hierarchy**.

**2a — Epics in scope** (run in parallel):

1. **Active Epics** — open `issuetype = Epic` with activity in the reporting window or children in flight.
2. **Epics closed in period** — `statusCategory = Done` with resolution in range.
3. **Epics with child activity in period** — any Epic whose children were resolved, updated, or moved status in range (even if the Epic issue is unchanged).
4. **Minutes call-outs** — Epics named in SKRULL DSU / Standardization / ADINC dashboard notes.

For each Epic in scope: read `summary`, `description`, `status`, `labels`, `updated`.

**2b — Children per Epic** — For every Epic in scope:

```jql
project = SKRULL AND parent = {EPIC-KEY} AND issuetype != Epic ORDER BY status ASC, key ASC
```

On deept SKRULL, **`parent` is the authoritative Epic→child link** (verify `epic_link` only if `parent` returns empty). Paginate with `start_at`.

Classify each child into Accomplished / In Progress / Blocked using the same rules as ticket queries. Compute a short **initiative health** line per Epic (internal only — e.g. “FY26 Qlik observability: 2 children done this week; DR testing epic still open”).

**2c — Ticket queries** ( `issuetype != Epic` ), scoped per user or whole project:

```jql
project = SKRULL AND statusCategory = "In Progress" AND status != Blocked AND issuetype != Epic
```

```jql
project = SKRULL AND statusCategory = Done AND resolved >= "{start}" AND resolved <= "{end}" AND issuetype != Epic
```

```jql
project = SKRULL AND status = Blocked AND issuetype != Epic
```

Add optional `AND assignee in (...)` when user narrows scope.

**2d — Rollup into workload buckets** — Map Epic-led and orphan items into **Linear Workloads**, **Addressable Workloads**, **Linear Cloud**, **Other** using Epic title, child summaries, labels, and minutes — see [reference.md](reference.md).

**Do not** output raw SKRULL lists or Epic keys in narrative sections. **Do** use **Epic summary text** to frame initiative bullets (e.g. under **Pipeline cost & performance optimization:** roll up children of *DataOps - Pipeline Cost & Performance Optimization*).

**Synthesis order (Step 6):** Epic-framed initiative bullets → rotation/orphan operational bullets → ADINC table.

**ADINC (Step 3)** — Populate **Incidents** only from live Jira.

```jql
project = ADINC AND (
  (cf[10489] >= "{start}" AND cf[10489] <= "{end}")
  OR (created >= "{start}" AND created <= "{end}" 23:59)
  OR (resolved >= "{start}" AND resolved <= "{end}")
)
ORDER BY key DESC
```

For each issue fetch: `summary`, `status`, `description`, `customfield_10253` (Notes / RCA), `customfield_10489` (Start DatePick), `resolved`, `created`.

Parse description lines `PIPELINE:` and `DAG:` for the **Pipeline and DAG** column. **Date** column: prefer **Start DatePick** (`YYYY-MM-DD`); else `created`.

**RCA column:** Compress Notes (`customfield_10253`) to 2–4 sentences covering cause, resolution, and business impact — match tone in the reference table. If Notes empty but status is Done, say `RCA pending in Notes` and flag for follow-up.

If no ADINC rows qualify, output the Incidents heading and a single line `NA` (no empty table).

**Cerebro minutes (Step 4)** — VPN required.

1. `GetDynamicTools` → `user-ads-cerebro-qa`.
2. **Primary:** `search_disney_ad_platform` or `search_knowledge` with queries such as:
   - `meeting notes SKRULL DSU {start} to {end}`
   - `meeting notes DataOps Standardization {start} to {end}`
   - `meeting notes ADINC Dashboard Weekly Review {start} to {end}`
   - `mn-{id}` when the user’s ingest table supplies a Cerebro ID
3. **Include meetings** whose titles match (case-insensitive), including partial matches:

| Pattern |
|---------|
| `SKRULL DSU` |
| `DataOps Standardization` |
| `ADINC Dashboard` |
| `DataOps - Incident Review` / `Incident Review` |
| `RCA` (DataOps / ADINC context) |
| `CI/CD` + `ADINC` |
| `EPIC and Oncall Review` |

4. **Calendar cross-check (optional):** `teams --agent meeting list --start-date <YYYY-MM-DD> --days <n>` — align subjects with ingest rows (Date, Meeting, `mn-*`).

If Cerebro returns empty, state that in chat and rely on Jira — **do not invent** meeting content.

### Step 6 — Synthesis rules

| Source | Maps to section |
|--------|-----------------|
| Epic **done** in period or children resolved | **Work Accomplished** → initiative-led bullet in workload subsection |
| Epic **open** + children in progress | **Work in Progress** → initiative status + what moved |
| Epic **blocked** or majority of children blocked | WIP bullet with `(blocked)` |
| SKRULL resolved / in flight (orphan, no Epic) | Same buckets by theme |
| SKRULL `Blocked` | Work in Progress bullet ending with `(blocked)` — **no separate Blockers heading** |
| ADINC in range | **Incidents** table only |
| Minutes | Color weekly support windows, on-call themes, standardization decisions; **minutes win** for nuance |
| User / shipped product correction | Overrides stale SKRULL summary or description text (e.g. metric renamed in dashboard but ticket title still wrong) |

**Writing style (mandatory):**

- **Synthesize from SKRULL + ADINC + Cerebro only** for the requested period. The Foundations reference thread is for **layout and rubric names**, not wording — **never** copy prior weekly posts (including Vijaya’s) sentence-for-sentence.
- Under each workload `<h3>`, use **HTML `<ul><li>` bullets** with **`<strong>{Rubric}:</strong>`** leaders (see [reference.md](reference.md)). No single-paragraph walls of text per subsection.
- Dense Foundation Engineering prose inside each bullet; semicolon-separated detail is fine.
- **No** `SKRULL-####` keys in Work Accomplished / Work in Progress (Epic **names** allowed).
- **ADINC-####** appears **only** in the Incidents table (and `Incident` column title text).
- Use **four workload subsections** under both Work Accomplished and Work in Progress: **Linear Workloads**, **Addressable Workloads**, **Linear Cloud**, **Other** — even when a subsection is `NA` or one short bullet (`<ul><li>NA</li></ul>`).
- Weekly support lines: include date span for the **prior** completed week in Accomplished and **current** week in Progress when minutes or squad convention use `MM/DD–MM/DD` windows (see reference).
- **Do not** include draft banners or **Sources used** in the Teams-published body (chat preview may include Sources used).

### Step 7 — Display in chat

Output the complete section using [reference.md](reference.md) template (HTML for Teams-ready copy). **Do not** append **Sources used**, draft banners, or Jira counts to the published body (chat may mention sources in prose when Cerebro is empty or data is thin).

### Step 8 — AskQuestion

- **Copy only** — section for pasting into Foundations report (Recommended)
- **Post to Foundations channel** — new thread per [teams-posting.md](teams-posting.md) (parent title + HTML reply + CC Vijaya)
- **Do not post**

### Step 9 — Posting (optional)

See [teams-posting.md](teams-posting.md): **3 messages** — root HTML parent (date + **Fleet:** Data Platform Enablement + **Squad:** DataOps), HTML report reply, then `CC: Hosamani, Vijaya Kumar`. Never a lone report `channel send` without the parent thread.

## Relationship to other skills

| Skill | Output |
|-------|--------|
| `dataops-status-report` | **Data Operations** narrative + ADINC incidents table |
| `analytics-status-report` | **Analytics platform** narrative |
| `jira-skrull-audit` | SKRULL hygiene audit (not weekly prose) |
| `jira-adinc-audit` | ADINC field/RCA audit |
| `meeting-notes-ingest` | Push Teams transcripts → Cerebro (upstream of Step 4) |

## Anti-patterns

- **Recycling** last week’s Foundations Data Operations text instead of rebuilding from Jira/minutes.
- Ignoring **SKRULL Epics** and reporting only orphan tickets (loses strategic view).
- Querying `issuetype != Epic` but never fetching Epic parents or `parent =` children.
- **Sources used** or draft banners in the Teams/Foundations body.
- **Paragraph-only** workload subsections when rubric bullets are required.
- Ticket bullet list with SKRULL keys in narrative (wrong deliverable).
- Omitting Incidents table when ADINC tickets exist in-period.
- Skipping Cerebro without trying VPN + search.
- Fabricating RCA or accomplishments unsupported by Jira or minutes.
- Adding a **Blockers** `<h2>` (Data Operations embeds blocked work in WIP).
- Duplicating Analytics platform content (different skill).

## Additional resources

- Output template, workload mapping, ADINC table: [reference.md](reference.md)
- Optional Teams post: [teams-posting.md](teams-posting.md)
