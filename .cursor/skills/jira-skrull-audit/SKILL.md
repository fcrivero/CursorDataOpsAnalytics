---
name: jira-skrull-audit
description: >-
  Audits SKRULL Jira Stories and Tasks for missing assignees, missing Epic links
  (with suggested open Epics), missing story points, tickets open more than 8 days,
  and Blocked status. Use when the user asks to verify, audit, validate, or review
  SKRULL tickets, board hygiene, or backlog grooming. Every run must fetch live
  data from Jira first — never reuse snapshot or prior audit JSON.
---

# SKRULL ticket audit

Audit **SKRULL** (`Story` and `Task` only) at `https://deept.atlassian.net` via `user-jira-server` MCP.

Companion skill for ticket **creation**: `jira-skrull-tickets`.

## Configuration

| Setting | Value |
|---------|--------|
| Project key | `SKRULL` |
| Board | [SKRULL board 489](https://deept.atlassian.net/jira/software/c/projects/SKRULL/boards/489) |
| MCP server | `user-jira-server` |
| Browse URL | `https://deept.atlassian.net/browse/{KEY}` |
| Story points field | `customfield_10047` |
| Allowed issue types | `Story`, `Task` only (never audit Epics, Bugs, Sub-tasks unless user explicitly expands scope) |
| Open-age threshold | **More than 8 days** — flag when Days Open **≥ 9** (UTC `created` date) |

Terminal (excluded from default scan unless user asks): `Done`, `Closed`, `Resolved`, `Cancelled`.

## Skill inputs

| Input | Type | Default | Purpose |
|-------|------|---------|---------|
| `audit_scope` | string or list | `all` | Checks to run: `assignee`, `epic`, `points`, `open_week`, `blocked`, or `all` |
| `issue_keys` | list of keys | all in scope | Audit specific tickets (e.g. `["SKRULL-9176"]`) |
| `jql` | string | see [Default JQL](#default-jql) | Custom Jira query (must still restrict to Story/Task unless user overrides) |
| `open_days` | integer | `8` | Check 4: flag when open **more than** this many days (`Days Open >= open_days + 1`, default **9+**) |
| `output_format` | string | `markdown` | `markdown` (chat tables), `canvas`, or `both` |
| `include_compliant` | boolean | `false` | Include passing tickets in output |
| `excel_output` | string | auto | Optional path for `.xlsx`; default see [Excel workbook](#excel-workbook) |

### Example invocations

```text
@jira-skrull-audit audit all SKRULL stories and tasks
@jira-skrull-audit find SKRULL tickets missing assignees
@jira-skrull-audit show missing epics on the SKRULL board
@jira-skrull-audit list blocked SKRULL tasks
@jira-skrull-audit tickets open more than a week
@jira-skrull-audit check SKRULL-9176, SKRULL-9898
```

## Five audit checks

Run checks requested by `audit_scope`. When `all`, run every check and produce one combined report with separate sections per check.

**Default scan population:** open SKRULL Stories and Tasks (not terminal). Check 5 (Blocked) is a subset of that population.

### Check 1 — Missing assignees (`assignee`)

Scope: Stories and Tasks in the audit population **that have started** — **exclude** status **`Open`** and **`Backlog`** (unstarted / not yet picked up).

**Flag when:** Jira assignee is null, empty, or unassigned.

**Pass when:** Assignee is set, **or** status is `Open` / `Backlog` (out of scope for this check).

**JQL (fetch):**

```jql
project = SKRULL AND issuetype in (Story, Task)
AND status not in (Done, Closed, Resolved, Cancelled, Open, Backlog)
AND assignee is EMPTY
ORDER BY assignee ASC, created ASC
```

Executive summary **Scanned** count for Check 1 = issues matching the scope line above **without** the `assignee is EMPTY` clause.

### Check 2 — Missing Epic (`epic`)

Scope: Stories and Tasks in the audit population.

**Flag when:** Both are true:

- `"Epic Link"` is empty (JQL: `"Epic Link" is EMPTY`), **and**
- `parent` is empty (JQL: `parent is EMPTY`)

If MCP JSON shows `epic_link` / `parent` as null for all issues, **re-evaluate with JQL** (`"Epic Link" is EMPTY AND parent is EMPTY`) or spot-check with `jira_get_issue` — do not assume every ticket lacks an Epic.

**Pass when:** Epic Link is set **or** parent Epic is set.

**Epic catalog (same run):** Before scoring suggestions, paginate **open Epics**:

```jql
project = SKRULL AND issuetype = Epic AND status not in (Done, Closed, Resolved, Cancelled)
ORDER BY updated DESC
```

Fields: `summary`, `status`, `description`.

**Suggested Epic(s):** For each flagged ticket, rank open Epics using [scripts/skrull_epic_suggest.py](scripts/skrull_epic_suggest.py) → `suggest_epics(summary, description, epics)`. Show the **top 1–3** matches in the output table.

Format each suggestion as markdown: `[{epic summary}](https://deept.atlassian.net/browse/{EPIC_KEY})` plus key in Comments if helpful, e.g. `Suggest: SKRULL-4570`.

**Comments format:** `Epic=Missing`

### Check 3 — Missing story points (`points`)

Scope: **Stories only** — open SKRULL `issuetype = Story`. **Exclude** Tasks and Sub-tasks (story points are not required on Tasks in this audit).

**JQL (fetch):**

```jql
project = SKRULL AND issuetype = Story
AND status not in (Done, Closed, Resolved, Cancelled)
AND (points is EMPTY OR "Story Points" is EMPTY)
ORDER BY assignee ASC, created ASC
```

**Flag when:** Story points are missing — `points` is null/empty from search **or** `customfield_10047` is unset after `jira_get_issue` when search returns ambiguous null.

Do **not** flag `0` unless the user explicitly asks to treat zero as invalid.

**Pass when:** Points are a positive number.

> SKRULL uses `customfield_10047`, not ADINC’s `customfield_10106`. See `jira-skrull-tickets`.

### Check 4 — Open more than 8 days (`open_week`)

Scope: Stories and Tasks in the audit population (non-terminal).

**Age source:** Jira **`created`** timestamp only. Do **not** use `updated` or status-change history for this check.

**Default threshold:** Open **more than 8** calendar days → **Days Open ≥ 9** (`audit_date - created_date >= 9`).

With skill input `open_days` (default **8**): flag when `audit_date - created_date > open_days` (equivalently **≥ open_days + 1**).

**Pass when:** Days Open is 8 or less, or ticket is terminal (excluded from population).

**Days Open column:** Integer only — calendar days from `created` (UTC date) to audit date; no extra label text.

**JQL helper** (pre-filter; report also filters in code):

```jql
created <= -9d
```

Use `-Nd` where `N` = `open_days + 1` (default `N = 9`).

### Check 5 — Blocked items (`blocked`)

Scope: Stories and Tasks where **status name** is exactly `Blocked` (case-insensitive match on status string).

**Flag when:** Status is Blocked.

**Pass when:** Status is anything else.

> This check lists blocked work for visibility; it is not a “failure” hygiene check unless the user treats it that way.

## Default JQL

When the user does not provide `jql` or `issue_keys`:

```jql
project = SKRULL AND issuetype in (Story, Task)
AND status not in (Done, Closed, Resolved, Cancelled)
ORDER BY updated DESC
```

For `issue_keys`, use `key in (SKRULL-1, SKRULL-2)` and still restrict types unless the user says otherwise.

## Fresh Jira data (mandatory)

Every audit run **must** load tickets from **live Jira** in that same run. **Do not reuse** prior pulls, chat tables, or JSON snapshots.

**Required behavior:**

1. Paginate `jira_search_issues` until all issues in scope are retrieved (`max_results`: 100, increment `start_at`).
2. Fetch open Epics catalog when Check 2 runs (same run).
3. State **`Jira fetched at`** (UTC) in the executive summary.

Optional: write `reports/skrull-audit-{date}.json` for debugging — **overwrite only**; never skip fetch because the file exists.

## Workflow

1. **Read MCP tool schemas** under `user-jira-server` before calling tools.
2. **Fetch Stories/Tasks** — paginate with fields:
   `summary,status,assignee,issuetype,created,updated,description,points,customfield_10047,parent,epic_link`
3. **Fetch open Epics** when running Check 2 (or `all`).
4. **Evaluate checks** per `audit_scope` on each issue in scope.
5. **Sort flagged rows** for every check table — see [Row sort order](#row-sort-order).
6. **Produce output** — see [Output](#output) (chat tables are mandatory).
7. **Write Excel workbook** — after a full audit (`all`), run [scripts/generate_excel.py](scripts/generate_excel.py) (also invoked automatically from `generate_report.py` unless `--no-excel`).
8. **Summarize** — counts per check; optional canvas path when `output_format` includes canvas.

## Output

**Always render the full audit in chat** as separate markdown tables — **one section per check** — matching the ADINC audit style. Do **not** stop at summary counts alone.

### Ticket link format (all checks)

**Ticket** column: markdown link with the **Jira summary (title)** as link text:

```markdown
[{summary}](https://deept.atlassian.net/browse/{KEY})
```

Do not use key-only link text (e.g. `[SKRULL-123](...)`). If the summary contains `[` / `]`, use the full title when the renderer supports it; otherwise shorten without dropping meaning.

### Required chat format (mandatory)

1. Brief **executive summary** table (counts per check) plus **Jira fetched at** (UTC).
2. **One heading + table per check** with flagged rows, in order Check 1 → Check 5.
3. **Omit sections with zero flagged rows** (no heading for that check).
4. Section heading pattern: `### Check N — {Name} ({flagged_count})`
5. **Every check table** includes **Assignee** and **Created** columns and rows sorted per [Row sort order](#row-sort-order).

### Row sort order (mandatory)

Sort **all flagged rows** in **every** check section (and canvas tables) using:

1. **Assignee** — ascending by display name (case-insensitive). Empty / unassigned → show **`(Unassigned)`**; those rows sort **before** named assignees.
2. **Created** — ascending by Jira `created` timestamp (oldest first within the same assignee).

When assignee display name is missing from MCP, use `(Unassigned)`.

**Created column format:** `YYYY-MM-DD` (UTC date from `created`).

Do not sort by ticket key, summary, or status unless the user explicitly asks for a different order.

### Executive summary (always first)

```markdown
## SKRULL audit summary

| Check | Scanned | Flagged |
|-------|---------|---------|
| Missing assignees | N | N |
| Missing Epic | N | N |
| Missing story points | N | N |
| Open > 8 days (9+ by created) | N | N |
| Blocked | N | N |

**Jira fetched at:** YYYY-MM-DD HH:MM UTC
**Scope:** {brief JQL or keys}
```

### Table columns by check

Column order is fixed. Rows sorted by **Assignee**, then **Created** (see above).

**Check 1 — Missing assignees:**

| Ticket | Assignee | Created | Status |

**Check 3 — Missing story points:**

| Ticket | Assignee | Created | Status |

**Check 4 — Open more than 8 days:**

| Ticket | Assignee | Created | Status | Days Open |

**Check 5 — Blocked items:**

| Ticket | Assignee | Created | Status |

**Check 2 — Missing Epic:**

| Ticket | Assignee | Created | Status | Suggested Epic(s) |

- **Suggested Epic(s):** Top 1–3 markdown links from `format_suggestions_markdown()` — each link text is **`{EPIC-KEY}: {Epic summary}`** (Epic name visible); `—` when no reasonable match.

Example section:

```markdown
### Check 2 — Missing Epic (12)

| Ticket | Assignee | Created | Status | Suggested Epic(s) |
|--------|----------|---------|--------|-------------------|
| [CICD for ADINC DBXs Workbooks and Jobs](https://deept.atlassian.net/browse/SKRULL-9339) | Salman Khan | 2026-09-15 | Open | [SKRULL-4819: DataOps \| Automation \| SLA Monitoring for Databricks](https://deept.atlassian.net/browse/SKRULL-4819) |
```

### Canvas (optional)

When `output_format` is `canvas` or `both`, read the canvas skill and create `{workspace}/canvases/skrull-audit-{scope}.canvas.tsx` with summary stats and one section per check. Use the same columns and **Assignee → Created** row order. **Still produce chat tables.**

### Excel workbook

Every **full** audit run also produces an `.xlsx` aligned with the Fernando Rivero share format (`102726-SKRULL AUDIT.xlsx`):

| Sheet | Check |
|-------|--------|
| Missing Epic | 2 |
| Missing story points | 3 |
| Open more than 8 days | 4 |
| Blocked items | 5 |

- **Template:** [assets/SKRULL-AUDIT-template.xlsx](assets/SKRULL-AUDIT-template.xlsx) (column widths, sheet names).
- **Ticket** column: summary text + hyperlink to `https://deept.atlassian.net/browse/{KEY}`.
- **Suggested Epic(s):** plain text `SKRULL-xxxx: Epic name`, comma-separated (same ranking as chat).
- **Created:** Excel date (UTC calendar date from Jira `created`).
- **Check 1:** not in the default template; a **Missing assignees** sheet is added only when Check 1 has flagged rows.

**Default file name:** `MMDDYY-SKRULL AUDIT.xlsx` (UTC audit date).

**Default directory:** `jira-skrull-audit/reports/` unless `SKRULL_AUDIT_XLSX_DIR` is set (e.g. `C:\Users\{you}\Downloads`).

**Commands (after live fetch):**

```bash
python scripts/run_audit.py
# or
python scripts/skrull_fetch_checks.py
python scripts/generate_report.py          # chat + Excel
python scripts/generate_excel.py           # Excel only
python scripts/generate_report.py --no-excel   # chat only
python scripts/generate_excel.py "C:\path\to\custom.xlsx"
```

Tell the user the **full path** to the generated `.xlsx` in chat after every full audit.

## MCP usage

**Search Stories/Tasks (paginated):**

```json
{
  "namespace": "user-jira-server",
  "toolName": "jira_search_issues",
  "arguments": {
    "jql": "project = SKRULL AND issuetype in (Story, Task) AND status not in (Done, Closed, Resolved, Cancelled) ORDER BY updated DESC",
    "fields": "summary,status,assignee,issuetype,created,updated,description,points,customfield_10047,parent,epic_link",
    "max_results": 100,
    "start_at": 0
  }
}
```

**Open Epics catalog:**

```json
{
  "namespace": "user-jira-server",
  "toolName": "jira_search_issues",
  "arguments": {
    "jql": "project = SKRULL AND issuetype = Epic AND status not in (Done, Closed, Resolved, Cancelled) ORDER BY updated DESC",
    "fields": "summary,status,description",
    "max_results": 100,
    "start_at": 0
  }
}
```

**Verify points when search returns null:**

```json
{
  "namespace": "user-jira-server",
  "toolName": "jira_get_issue",
  "arguments": {
    "issue_key": "SKRULL-9166",
    "fields": "summary,points,customfield_10047"
  }
}
```

## Rules

- **Fresh Jira pull every run** — never audit from snapshots or prior JSON.
- Always paginate; SKRULL has hundreds of Stories/Tasks.
- **Do not modify tickets** unless the user explicitly asks to fix assignee, Epic, or points.
- Never log or return API tokens.
- When the user asks for a single check, run only that check.
- Restrict to **Story** and **Task** unless the user explicitly widens scope.
- Epic suggestions are **recommendations** — confirm with the team before bulk Epic Link updates.

## Related resources

- SKRULL fields and assignees: [reference.md](reference.md)
- Epic matching helper: [scripts/skrull_epic_suggest.py](scripts/skrull_epic_suggest.py)
- Ticket creation: `jira-skrull-tickets` skill
- Output pattern reference: `jira-adinc-audit` skill
