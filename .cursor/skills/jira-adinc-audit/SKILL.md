---
name: jira-adinc-audit
description: >-
  Audits Ads Data Incidents (ADINC) Jira tickets for description field compliance,
  invalid placeholder values (TBD/blank and restricted NA), missing RCA in the Notes field,
  summary title format for tickets without ServiceNow (INC_NUMBER=NA), allowed dropdown value compliance
  in TEAM, ISSUE_CATEGORY, SOURCE_SYSTEM, and PIPELINE (aligned with jira-adinc-tickets create rules),
  Jira Priority P1 when MISSED_SLA=Y or (for tickets created after 2026-05-30) real INC_NUMBER,
  and open tickets that already have RCA in Notes.
  Use when the user asks to verify, audit, validate, or review ADINC tickets,
  incident field quality, open/closed ticket hygiene, or RCA completeness.
  Every run must fetch live data from Jira first — never reuse snapshot or prior audit JSON.
---

# ADINC ticket audit

Audit **Ads Data Incidents** (`ADINC`) at `https://deept.atlassian.net` via `user-jira-server` MCP.

Companion skill for ticket **creation**: `jira-adinc-tickets`.

## Configuration

| Setting | Value |
|---------|--------|
| Project key | `ADINC` |
| MCP server | `user-jira-server` |
| Browse URL | `https://deept.atlassian.net/browse/{KEY}` |
| Notes field (General tab) | [adinc-jira-notes.md](../adinc-jira-notes.md) → `customfield_10253` |
| Story points field | `customfield_10106` |

## Required description fields (exactly 10)

Preserve names and order when validating:

```text
INC_NUMBER:
TEAM:
PIPELINE:
DAG:
TASK:
SOURCE_SYSTEM:
ISSUE_CATEGORY:
EXTERNAL:
MISSED_SLA:
PD_ID:
```

> **Note:** `INC_NUMBER` is correct. Flag `NC_NUMBER` as misspelled.

## Skill inputs

The skill accepts optional filters. Defaults apply when omitted.

| Input | Type | Default | Purpose |
|-------|------|---------|---------|
| `audit_scope` | string or list | `all` | Which checks to run: `structure`, `open_invalid`, `closed_invalid`, `rca`, `rca_while_open`, `title_format`, `field_enums`, `jira_priority`, or `all` |
| `issue_keys` | list of keys | all ADINC | Audit specific tickets (e.g. `["ADINC-751"]`) |
| `jql` | string | `project = ADINC ORDER BY created DESC` | Custom Jira query to scope tickets |
| `status_filter` | string | none | Further narrow by status (e.g. `status = "In Progress"`) |
| `date_from` / `date_to` | ISO date | none | Filter by created date |
| `output_format` | string | `canvas` | `canvas` (interactive table), `markdown`, or `both` |
| `include_compliant` | boolean | `false` for targeted checks; `true` for full structure audit | Include passing tickets in output |

### Example invocations

```text
@jira-adinc-audit audit all ADINC tickets
@jira-adinc-audit show open tickets with TBD or NA in description fields
@jira-adinc-audit find closed ADINC tickets missing RCA in Notes
@jira-adinc-audit check ADINC-751, ADINC-735, ADINC-739
@jira-adinc-audit audit tickets created since 2026-06-01
@jira-adinc-audit find NA INC tickets with incorrect summary title format
@jira-adinc-audit find tickets with invalid TEAM, PIPELINE, SOURCE_SYSTEM, or ISSUE_CATEGORY
@jira-adinc-audit apply suggested title formats for Check 5 failures
@jira-adinc-audit list open tickets that already have RCA in Notes
```

## Eight audit checks

Run the checks requested by `audit_scope`. When `all`, run every check and produce one combined report with an **Audit Type** column or separate sections.

### Check 1 — Description structure (`structure`)

Verify every ticket description contains all 10 required fields, correctly spelled, with no extra non-standard fields.

**Flag when:**
- Description is empty
- Any required field is **missing** (absent from description)
- Any field name is **misspelled** (e.g. `NC_NUMBER` instead of `INC_NUMBER`; use fuzzy match cutoff 0.75)
- **Extra fields** present (e.g. `ERROR:`) not in the required 10
- **Unparsed content** exists outside `FIELD: value` lines

**Pass when:** All 10 fields present, correctly named, no extras.

### Check 2 — Open tickets with invalid values (`open_invalid`)

Scope: tickets where status is **open** (not Done/Closed).

Open statuses: `In Progress`, `Open`, `To Do`, `Reopened`, `Blocked`.

**Invalid values on open tickets:**
- Any field with blank (empty) value or missing field
- Any field with `TBD`
- `NA` / `N/A` / `N.A.` / `NONE` for fields **other than** `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, `SOURCE_SYSTEM`

`NA` is valid for `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, and `SOURCE_SYSTEM` when not applicable or no ServiceNow INC is created.

**Comments format:** list each offending field, e.g. `SOURCE_SYSTEM=TBD; ISSUE_CATEGORY=NA`.

> Open tickets should have real values — placeholders are not acceptable while work is active.

### Check 3 — Closed tickets with invalid values (`closed_invalid`)

Scope: tickets where status is **closed**.

Closed statuses: `Done`, `Closed`, `Resolved`.

**Excluded from all checks:** status `Cancelled`, or resolution `Cancelled` (status may remain `Done`).

**Invalid values on closed tickets:**
- Any field with blank (empty) value or missing field
- Any field with `TBD`
- `NA` / `N/A` / `N.A.` / `NONE` for fields **other than** `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, `SOURCE_SYSTEM`

`NA` is valid for `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, and `SOURCE_SYSTEM` when not applicable or no ServiceNow INC is created.

**Comments format:** same as Check 2.

> Closed tickets should be fully populated for reporting and traceability.

### Check 4 — Closed tickets missing RCA (`rca`)

Scope: closed tickets only.

**RCA source:** General tab → **Notes** (`customfield_10253`). See [adinc-jira-notes.md](../adinc-jira-notes.md).

**Do NOT use** Jira Comments (`jira_get_comments`) for RCA.

**Flag when Notes (`customfield_10253`) is:**
- null, empty, or whitespace only
- `#N/A`, `N/A`, `NA` (case-insensitive)
- Only a label with no substance (e.g. `RCA:` with nothing after)

**Pass when:** Notes contains substantive RCA text **or** a Confluence/wiki URL (plain or Jira smart-link after `RCA:`). See [adinc-jira-notes.md](../adinc-jira-notes.md).

**Do not flag** when Notes is `RCA:` followed by a Confluence page link (inline card / smart-link) — that is the standard ADINC history workflow.

**Comments format:** `Notes=Missing RCA` or `Notes=Placeholder (#N/A)`.

### Check 5 — Title format / Summary (`title_format`)

Scope: tickets where description field **`INC_NUMBER` is `NA`** (no ServiceNow counterpart). Tickets with a real `INC_NUMBER` are **not** evaluated by this check.

**Required title format:**

```text
[AP][Team name][Sub Team name / pipeline name (BI uses pipeline)]DAG name- short description of the issue
```

**Canonical example:**

```text
[AP][ODS][METRICS]ap_addr_ods_metrics_mc_metadata_dq_prod- 14 ERROR-level constraints violated
```

**Format rules:**

| Segment | Rule |
|---------|------|
| `[AP]` | Required prefix |
| `[Team name]` | Second bracket — team identifier (e.g. `ODS`, `ADI`, `ADM`) |
| `[Sub Team / pipeline]` | Third bracket — sub-team or pipeline name; for BI tickets use pipeline name (e.g. `[BI]`) |
| Optional 4th bracket | Allowed for qualifiers such as `[Long Run]` |
| `DAG name` | When description `DAG` is not `NA`, the primary DAG token must appear in the summary after the bracket prefix |
| Short description | Non-empty text after brackets / DAG segment (hyphen between DAG and description is **recommended** but **not audited**) |

**When description `DAG` is `NA`:** bracket prefix `[AP][Team][SubTeam/pipeline]` is still required; DAG name in the title is not required, but a substantive short description must follow the brackets.

**Flag when:**
- Summary does not start with `[AP]`
- Missing `[AP][Team][SubTeam]` prefix (optional 4th bracket segment is allowed)
- Description `DAG` is not `NA` but the DAG token is absent from the summary
- Description `DAG` is `NA` but no substantive description follows the bracket prefix

**Do not flag:** missing hyphen between DAG and description, or spacing style (`DAG- desc` vs `DAG desc`).

**Pass when:** Title matches the format for the ticket's `INC_NUMBER`/`DAG` context.

**Comments format:** `Summary must start with [AP]`; `DAG "ap_addr_foo_prod" not found in summary title`.

**Output (Check 5 only):** every flagged row must show **Current title** and **Proposed title** side by side. Implementation: [scripts/adinc_title_format.py](scripts/adinc_title_format.py) → `suggest_title_format()` (stored as `suggestedTitle` / `currentSummary` in JSON).

| Column | Content |
|--------|---------|
| Ticket | Link |
| Status | Current status |
| **Current title** | Existing Jira summary (full text) |
| **Proposed title** | Auto-generated title from `PIPELINE`, `DAG`, and current summary |
| Comments | Validation findings only (no duplicate of titles) |

**Proposed title rules:** preserve `[AP][Team][SubTeam]` (and optional 4th bracket) from the current title when present; otherwise derive from `PIPELINE`; include description `DAG` when not `NA`; use `- ` before short description in proposals (convention for remediation, not an audit requirement).

#### Check 5 remediation (apply suggested titles)

When the user asks to **fix**, **apply**, or **update** title formats after an audit:

1. Run Check 5 (or use the latest audit JSON) and list flagged tickets with **Current title** and **Proposed title**.
2. Process **one ticket at a time**. For each flagged ticket, ask:

```text
ADINC-XXX — apply suggested title?

Current:  [current summary]
Suggested: [suggested title]

Reply: yes | no | edit: <your title>
```

3. **Only update Jira when the user explicitly confirms** that ticket:
   - `yes` → apply the suggested title
   - `edit: ...` → apply the user-provided title
   - `no` / skip → leave unchanged; move to next ticket
4. **Never batch-update** summaries without per-ticket confirmation.
5. Update via MCP `jira_update_issue`:

```json
{
  "server": "user-jira-server",
  "toolName": "jira_update_issue",
  "arguments": {
    "issue_key": "ADINC-769",
    "fields": { "summary": "[AP][ADI][BI]ap_addr_bi_gen_programmatic_prod- Missed SLA" }
  }
}
```

6. After each successful update, confirm with the browse URL and show old → new summary.
7. When all tickets are processed (or user stops), summarize: applied / skipped / failed.

### Check 6 — Allowed Values in Fields (Dropdowns) (`field_enums`)

Scope: **all audited tickets** (open and closed). Validates that four description fields use **approved dropdown values** — the same fixed lists Support Bot and `jira-adinc-tickets` use at creation time. This is not about Jira field types; it checks the text in the description matches the allowlist exactly.

Canonical allowlists: [jira-adinc-tickets/reference.md](../jira-adinc-tickets/reference.md) (keep audit in sync when allowlists change).

| Field | Rule | Example pass | Example fail |
|-------|------|--------------|--------------|
| `TEAM` | Must be exactly `ads-data-support` (trim whitespace). Any other value is invalid (e.g. `ODS`, `ELSA`). | `ads-data-support` | `ODS`, blank |
| `ISSUE_CATEGORY` | Non-empty; **exact** case-sensitive match to allowlist. `NA` / `N/A` not allowed. | `Data - DQ`, `AWS - Kinesis`, `AWS - S3` | `AWS - S3*`, blank |
| `SOURCE_SYSTEM` | Non-empty; exact match to allowlist **or** `NA` / `N/A` (placeholder allowed by audit). | `ODS - Metrics`, `3P Vendor - Hightouch`, `NA` | typo or invented vendor name |
| `PIPELINE` | Non-empty; exact match to allowlist (`NA` and `Waiting for RCA` are valid allowlist entries). | `ADM - Targeting`, `NA` | typo or invented value |

**Flag when:**
- Field missing or blank
- `TEAM` ≠ `ads-data-support`
- `ISSUE_CATEGORY`, `SOURCE_SYSTEM`, or `PIPELINE` not in allowlist (after trim; case-sensitive)
- `ISSUE_CATEGORY` is `NA` / `N/A` / `TBD`

**Pass when:** All four fields satisfy create-skill rules.

**Comments format (technical):** `TEAM=Invalid (expected "ads-data-support", got "ODS"); ISSUE_CATEGORY=NotInAllowlist ("DATA - DQ"); suggest: Data - DQ`

**Plain-English format (user-facing):** use `explain_allowed_values_failure()` from [scripts/adinc_field_allowlists.py](scripts/adinc_field_allowlists.py), e.g. `ISSUE_CATEGORY "AWS - S3*" is not on the approved list — try: AWS - S3, AWS - EKS`

> Historical tickets may predate allowlists — use this check to find legacy values to normalize (e.g. `ADM Targeting` → `ADM - Targeting`, `DATA - DQ` → `Data - DQ`).

### Check 7 — Jira Priority (`jira_priority`)

Scope: **all audited tickets** (open and closed). Uses description text for triggers and the Jira **Priority** field (not a description line).

| Trigger | Rule |
|---------|------|
| `MISSED_SLA` | Value `Y` (case-insensitive) → Jira Priority must be **P1** (all tickets, any created date) |
| `INC_NUMBER` | Real ServiceNow incident (not `NA`, `N/A`, `N.A.`, `NONE`, or blank) → Jira Priority must be **P1** **only when** Jira **Created** is **after 2026-05-30** |

**SNOW migration (2026-05-30):** Tickets with Jira **`created` on or before 2026-05-30** were bulk-migrated from ServiceNow. They often have a valid `INC_NUMBER` but were **not** all P1 in SNOW — do **not** require P1 from the INC rule alone for those tickets. **`MISSED_SLA=Y` still requires P1** regardless of created date.

**Created date (Check 7 only):** Use Jira `created` (ISO timestamp); compare date portion `YYYY-MM-DD`. INC rule applies when `created > 2026-05-30` (i.e. **2026-05-31** and later). Constant: `INC_P1_RULE_CUTOFF_DATE` in [scripts/adinc_priority_check.py](scripts/adinc_priority_check.py). This is **not** the incident open date for migrated tickets.

**Incident dates (all agents):** Canonical rules in **[adinc-jira-dates.md](../adinc-jira-dates.md)** — **Start DatePick** (`customfield_10489`) holds **SNOW opened/created** on imports; for native ADINC it holds **DEV start work** date. **Completion Date** = mitigated / Blocked (waiting RCA); **End Date** = Done with RCA. Do **not** use Jira **Created** as SNOW open time for migrated rows.

**Pass when:** No trigger applies, or Jira Priority is exactly `P1`.

**Flag when:** A trigger applies and Jira Priority is missing or not `P1`.

**Comments format (technical):** `Jira Priority must be P1 (MISSED_SLA=Y); got P2`

**Plain-English format:** use `explain_priority_failure()` from [scripts/adinc_priority_check.py](scripts/adinc_priority_check.py).

Implementation: [scripts/adinc_priority_check.py](scripts/adinc_priority_check.py) → `check_jira_priority(found, priority, created)` and `inc_number_triggers_p1(created)`.

**Chat / report table (flagged tickets only):** use exactly four columns — no Status or Comments column.

| Ticket | INC (Customer Impacted) | SLA MISSED | Priority |
|--------|-------------------------|------------|----------|

| Column | Content |
|--------|---------|
| **Ticket** | Markdown link with **Jira summary (title)** as link text: `[{summary}](https://deept.atlassian.net/browse/{KEY})`. Do not use key-only link text for Check 7. |
| **INC (Customer Impacted)** | From description `INC_NUMBER` + created date via `format_inc_for_output(inc, created)`. Post-cutoff real INC → `{INC} (Customer Impacted)`. Pre/migration legacy real INC → `{INC} (legacy SNOW migration — INC does not require P1)`. Placeholders → as-is. Blank → `—`. |
| **SLA MISSED** | From description `MISSED_SLA`: **`Y`** or **`N`** only when present; blank/unknown → `—`. Use `format_sla_missed_for_output()`. |
| **Priority** | Current Jira **Priority** field (e.g. `P1`, `P3`). Flagged rows are those where Priority is not `P1` but a trigger applies. |

Example rows (link text = full Jira summary):

```markdown
| [EMEA Data Not Updated in SVEN…](https://deept.atlassian.net/browse/ADINC-861) | NA | Y | P4 |
| [New ADINC ticket after migration…](https://deept.atlassian.net/browse/ADINC-900) | INC29999999 (Customer Impacted) | N | P3 |
| [Migrated SNOW ticket…](https://deept.atlassian.net/browse/ADINC-1) | INC29062571 (legacy SNOW migration — INC does not require P1) | N | P3 |
```

(Legacy example row would **not** appear in flagged results unless `MISSED_SLA=Y`.)

If the summary contains `[` / `]` characters, use the full title anyway when the chat renderer supports it; otherwise use a shortened title that still identifies the ticket.

### Check 8 — RCA in Notes while not Done/Closed (`rca_while_open`)

Scope: tickets whose status is **not** `Done`, `Closed`, or `Resolved` (includes `Open`, `In Progress`, `To Do`, `Reopened`, `Blocked`, and any other non-terminal status). Cancelled tickets remain excluded from the whole audit.

**RCA source:** same as Check 4 — General tab → **Notes** (`customfield_10253`). Uses `is_rca_missing()` from [scripts/adinc_notes.py](scripts/adinc_notes.py) (substantive text or Confluence/URL smart-link counts as RCA present).

**Flag when:** Notes contain valid RCA **and** the ticket is still not Done/Closed/Resolved.

**Pass when:** Ticket is Done/Closed/Resolved, or Notes do not yet contain RCA.

**Comments format:** `Notes contain RCA but status is not Done/Closed — transition ticket when work is complete`

**Plain-English format:** use `explain_rca_while_open()` from [scripts/adinc_rca_open_check.py](scripts/adinc_rca_open_check.py).

Implementation: [scripts/adinc_rca_open_check.py](scripts/adinc_rca_open_check.py) → `check_rca_while_open(status, notes)`.

> Complement to Check 4: Check 4 flags **closed** tickets **missing** RCA; Check 8 flags **non-closed** tickets that **already have** RCA (likely ready to transition to Done).

**Output table (flagged tickets):**

| Ticket | Status | Comments |

Use the standard ticket link format (Checks 1–4). Optional **What's wrong** column with `explain_rca_while_open(comments)`.

Example section heading: `### Check 8 — RCA in Notes while not Done/Closed (3)`

## Fresh Jira data (mandatory)

Every audit run **must** load tickets from **live Jira** in that same run. **Do not reuse** prior pulls.

**Forbidden as audit input** (report artifacts only, never read back for checks):

- `adinc-live-snapshot.json`, `adinc-audit-full.json`, or older chat/CSV/HTML audit exports
- A previous turn’s MCP search results unless you **re-fetch** in this run
- “Run Check 7 from the last audit” without a new Jira pull

**Required behavior:**

| Surface | Fresh pull |
|---------|------------|
| **Cursor chat / MCP** | Paginate `jira_search_issues` (or equivalent) for **all** ADINC tickets **before** any check. State `fetched_at` (UTC) in the executive summary. |
| **Shell** | [scripts/adinc_fetch_live.py](scripts/adinc_fetch_live.py) or [scripts/run_weekly_audit.py](scripts/run_weekly_audit.py) — both call Jira on every run. Workspace runner: `agent-tools/adinc_audit_live_run.py` (fetch + audit). |
| **Single-ticket scope** | Still call `jira_get_issue` (or search) for that key **now** — do not rely on memory or old JSON. |

Optional: after a fresh fetch, write `reports/adinc-live-snapshot.json` or `adinc-audit-full.json` for debugging — **overwrite only**; never skip fetch because the file exists.

## Workflow

1. **Read MCP tool schemas** under `user-jira-server` before calling tools.
2. **Fetch tickets from Jira (same run, step 1 of execution)** — paginate until complete:
   - JQL: user-provided or default `project = ADINC ORDER BY created DESC` (shell fetch script uses key-range JQL for full coverage)
   - Fields: `summary,status,resolution,created,updated,description,customfield_10253,priority`
   - Resolve Notes text per [adinc-jira-notes.md](../adinc-jira-notes.md) **Read** section
   - `max_results`: 100; increment `start_at` until all issues retrieved
3. **Parse descriptions** — each non-empty line must match `FIELD: value`:
   - Normalize `\r\n` → `\n`; uppercase field names for comparison
   - Blank = field present but value is empty after `:`
   - Missing = required field not found in description
4. **Classify status** — map to open vs closed using lists above; skip cancelled tickets (status or resolution)
5. **Evaluate checks** — apply checks per `audit_scope`
6. **Produce output** — see Output section below
7. **Summarize** — counts per check type in chat; link to canvas when generated

## Output

**Always render the full audit in chat** as separate markdown tables — one section per check — even when a canvas is also generated. Do **not** stop at summary counts alone.

### Required chat format (mandatory)

1. Brief executive summary table (counts per check) plus **Jira fetched at** timestamp (UTC) from the pull in this run.
2. **One heading + table per flagged check**, in order Check 1 → Check 8.
3. Skip sections with zero flagged rows (omit the heading entirely).
4. **Ticket column (Checks 1–6):** markdown link with key as text: `[ADINC-XXX](https://deept.atlassian.net/browse/ADINC-XXX)`.
5. **Check 7 only:** Ticket column uses **summary/title** as link text (see Check 7 table spec above).
6. Use backticks for field tokens in Comments on Checks 1–6 (e.g. `INC_NUMBER=Blank`, `TEAM=Missing`, `Notes=Missing RCA`).

**Checks 1–4 — table columns:**

| Ticket | Status | Comments |

**Check 3 (closed invalid) — same columns** (include Status).

**Check 5 (title format) — table columns (mandatory):**

| Ticket | Status | Current title | Proposed title | Comments |

**Check 6 (allowed values / dropdowns) — always include two parts:**

1. **Reference table** (always show, even when zero failures) — copy from Check 6 section above or `ALLOWED_VALUES_REFERENCE` in `adinc_field_allowlists.py`:

| Field | Rule | Example pass | Example fail |

2. **Flagged tickets table** (omit when zero failures):

| Ticket | Status | What's wrong | Technical details |

- **What's wrong** = plain English via `explain_allowed_values_failure(comments)` — e.g. `ISSUE_CATEGORY "AWS - S3*" is not on the approved list — try: AWS - S3, AWS - EKS`
- **Technical details** = raw machine comments with backticks for field tokens

Example section heading: `### Check 6 — Allowed Values in Fields (Dropdowns) (4)`

Example section heading: `### Check 1 — Structure (3)`

**Check 7 (Jira Priority) — table columns (mandatory when flagged):**

| Ticket | INC (Customer Impacted) | SLA MISSED | Priority |

- One row per **flagged** ticket (Jira Priority ≠ `P1` when `MISSED_SLA=Y` and/or real `INC_NUMBER`).
- Column rules and helpers: see **Check 7 — Jira Priority** section (`format_inc_for_output`, `format_sla_missed_for_output`).

Example section heading: `### Check 7 — Jira Priority (P1 required) (12)`

When `skip_prior_adinc` or another interim override is active, note it once under the executive summary.

| Column | Content |
|--------|---------|
| ADINC Ticket | Clickable link: `https://deept.atlassian.net/browse/{KEY}` |
| Summary | Issue summary |
| Status | Current status |
| Created | `YYYY-MM-DD` |
| Updated | `YYYY-MM-DD` |
| Comments | Findings |

### Check 5 columns (title format)

| Column | Content |
|--------|---------|
| Ticket | Link |
| Status | Current status |
| **Current title** | Full existing Jira summary |
| **Proposed title** | Full auto-generated title (`suggest_title_format`) |
| Comments | Validation findings |

When running multiple checks, add **Audit Type** column or use separate canvas sections:
`Structure`, `Open Invalid Values`, `Closed Invalid Values`, `Missing RCA`, `RCA While Open`, `Title Format`, `Allowed Values in Fields (Dropdowns)`, `Jira Priority`.

### Canvas (supplementary — always produce chat tables too)

Read the canvas skill before writing. Create `{workspace}/canvases/adinc-audit-{scope}.canvas.tsx`:

- Summary stats row (total scanned, flagged per check)
- Section per audit check with flagged tickets only (unless `include_compliant: true`)
- Use `Link`, `Table`, `Pill`, `Stat`, `Callout` from `cursor/canvas`
- Embed all data inline — no fetch

### Markdown tables in chat (primary deliverable)

Always use the **Required chat format** above. Markdown tables in chat are the default user-facing output for every audit run, regardless of result size.

### Executive summary (always in chat — first)

```markdown
## ADINC audit summary

| Check | Scanned | Flagged |
|-------|---------|---------|
| Structure | N | N |
| Open invalid values | N | N |
| Closed invalid values | N | N |
| Missing RCA | N | N |
| Title format (INC_NUMBER=NA) | N | N |
| Allowed values in fields (dropdowns) | N | N |
| Jira Priority (P1 required) | N | N |
| RCA in Notes while not Done/Closed | N | N |
```

List flagged ticket keys and top findings. Link to canvas file path.

## Parsing reference

```python
# Invalid value classification
NA_ALLOWED_FIELDS = {"INC_NUMBER", "DAG", "TASK", "PD_ID", "PIPELINE", "SOURCE_SYSTEM", "EXTERNAL", "MISSED_SLA"}
def classify_value(field, val):
    if not val or not val.strip(): return "Blank"
    upper = val.strip().upper()
    if upper in ("NA", "N/A", "N.A.", "NONE") and field not in NA_ALLOWED_FIELDS: return "NA"
    if upper == "TBD": return "TBD"
    return None  # valid

# RCA missing — see adinc-jira-notes.md is_adinc_rca_missing()

# Title format (Check 5) — see adinc_title_format.py is_adinc_rca_missing()

from adinc_title_format import audit_title_format, suggest_title_format
# audit_title_format(summary, found) -> (flagged, comments, suggested_title)

from adinc_field_allowlists import check_field_enums, explain_allowed_values_failure
# explain_allowed_values_failure(comments) -> plain-English for Check 6 "What's wrong" column

from adinc_priority_check import (
    check_jira_priority, explain_priority_failure, requires_p1,
    inc_number_triggers_p1, format_inc_for_output, format_sla_missed_for_output,
    INC_P1_RULE_CUTOFF_DATE,
)
# check_jira_priority(found, priority, created) -> (flagged, comments)
# inc_number_triggers_p1(created) -> True if created date > INC_P1_RULE_CUTOFF_DATE ("2026-05-30")
# format_inc_for_output(inc_number, created) -> Customer Impacted vs legacy SNOW label
# format_sla_missed_for_output(missed_sla) -> "Y" | "N" | "—"

from adinc_rca_open_check import check_rca_while_open, explain_rca_while_open, is_resolved_status
# check_rca_while_open(status, notes) -> (flagged, comments)
```

## MCP usage

**Search (paginated):**

```json
{
  "server": "user-jira-server",
  "toolName": "jira_search_issues",
  "arguments": {
    "jql": "project = ADINC ORDER BY created DESC",
    "fields": "summary,status,resolution,created,updated,description,customfield_10253,priority",
    "max_results": 100,
    "start_at": 0
  }
}
```

**Single ticket deep check:**

```json
{
  "server": "user-jira-server",
  "toolName": "jira_get_issue",
  "arguments": {
    "issue_key": "ADINC-736",
    "fields": "summary,status,resolution,created,updated,description,customfield_10253,priority"
  }
}
```

## Rules

- **Fresh Jira pull every run** — see [Fresh Jira data (mandatory)](#fresh-jira-data-mandatory). Never audit from snapshots or prior audit JSON.
- Always paginate — ADINC has 300+ tickets; a single search page is incomplete.
- Use General → Notes (`customfield_10253`) for RCA — see [adinc-jira-notes.md](../adinc-jira-notes.md). Never Comments.
- Do not modify tickets unless the user explicitly asks to fix them.
- Never log or return API tokens.
- When the user asks for only one check (e.g. TBD/blank), run only that check — do not conflate with structure, RCA, or title format unless requested.
- Check 5 (title format) applies **only** when description `INC_NUMBER` is `NA`; skip tickets with a real ServiceNow INC number.
- Check 6 (allowed values / dropdowns) uses the same allowlists as `jira-adinc-tickets` create — update [scripts/adinc_field_allowlists.py](scripts/adinc_field_allowlists.py) when allowlists change. Always show the reference table and plain-English "What's wrong" column in chat output.
- Check 7 (Jira Priority): `MISSED_SLA=Y` always requires **P1**; real `INC_NUMBER` requires **P1** only when `created > 2026-05-30` (post-SNOW migration). Update [scripts/adinc_priority_check.py](scripts/adinc_priority_check.py) if cutoff or NA placeholders change.
- Check 5 suggested titles are **proposals** — always ask per ticket before `jira_update_issue`.
- `TEAM` must always be `ads-data-support` on create; audit flags any other value on existing tickets.
- Distinguish **NA** handling by field:
  - `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, `SOURCE_SYSTEM` → `NA` is valid
  - all other required fields → `NA` is invalid for open/closed value checks
- Blank remains invalid for every required field.
- **Microsoft Teams only** for Support Bot and team comms about ADINC — do not reference Slack in audit summaries, remediation notes, or suggested announcements.

## Related resources

- Field definitions, status lists, comment templates: [reference.md](reference.md)
- **ADINC Notes (RCA) canonical field:** [adinc-jira-notes.md](../adinc-jira-notes.md)
- Ticket creation and description template: `jira-adinc-tickets` skill
- Confluence incident history: `confluence-adinc-history` skill
- **Live Jira fetch (shell):** [scripts/adinc_fetch_live.py](scripts/adinc_fetch_live.py) — `fetch_all_adinc_issues()`; optional write to `scripts/reports/adinc-live-snapshot.json`
- **Weekly email automation:** [scripts/run_weekly_audit.py](scripts/run_weekly_audit.py)

## Weekly email automation

For scheduled reports (no Cursor chat required), use the standalone script:

```bash
cd ~/.cursor/skills/jira-adinc-audit/scripts
cp .env.example .env   # configure JIRA_TOKEN + SMTP + EMAIL_TO
python run_weekly_audit.py --dry-run   # test locally
python run_weekly_audit.py             # audit + email
```

**Windows Task Scheduler** (Mondays 8 AM):

```powershell
powershell -ExecutionPolicy Bypass -File register_weekly_task.ps1
```

The script **fetches from Jira on every run**, runs all eight audit checks, writes HTML/JSON/CSV to `scripts/reports/`, and emails an HTML report with CSV attachment.

Required env vars: `JIRA_SERVER`, `JIRA_TOKEN`, `SMTP_HOST`, `EMAIL_FROM`, `EMAIL_TO`. See [scripts/.env.example](scripts/.env.example).

**Cursor Automations** (alternative): schedule `@jira-adinc-audit audit all ADINC tickets` weekly via a cron trigger + Jira MCP — best for Microsoft Teams delivery; use the Python script for email.
