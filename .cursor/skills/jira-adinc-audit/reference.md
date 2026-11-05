# ADINC audit reference

## Required description fields

| # | Field | Example valid values |
|---|-------|---------------------|
| 1 | INC_NUMBER | `INC29062571`, `NA` (valid when no ServiceNow INC) |
| 2 | TEAM | **`ads-data-support` only** (fixed; see Check 6 — Allowed Values) |
| 3 | PIPELINE | `ADM - Segmentation`, `BI Goldmine`, `NA`, `Waiting for RCA` (allowlist) |
| 4 | DAG | `ap_addr_bi_gen_programmatic_prod`, `NA` |
| 5 | TASK | `conf-dq-check-app`, `NA` |
| 6 | SOURCE_SYSTEM | `3P Vendor - STAQ`, `ADM - Targeting` (allowlist) |
| 7 | ISSUE_CATEGORY | `Data - Upstream Delay`, `Data - DQ` (allowlist; case-sensitive) |
| 8 | EXTERNAL | `Y`, `N`, `NA`, `N/A` |
| 9 | MISSED_SLA | `Y`, `N`, `NA`, `N/A` |
| 10 | PD_ID | `1234`, `5306811`, `NA` (valid when no ServiceNow INC) |

## Common misspellings

| Found | Should be |
|-------|-----------|
| `NC_NUMBER` | `INC_NUMBER` |
| `ADM Targeting` | `ADM - Targeting` |
| `DATA - DQ` | `Data - DQ` |
| `ADM-Segmentation` | `ADM - Segmentation` |

## Allowed values in fields — dropdowns (Check 6)

Synced with [jira-adinc-tickets/reference.md](../jira-adinc-tickets/reference.md). Implementation: [scripts/adinc_field_allowlists.py](scripts/adinc_field_allowlists.py).

| Field | Validation |
|-------|------------|
| `TEAM` | Exactly `ads-data-support` |
| `ISSUE_CATEGORY` | Exact allowlist match; no `NA` |
| `SOURCE_SYSTEM` | Exact allowlist match; `NA`/`N/A` also allowed (placeholder) |
| `PIPELINE` | Exact allowlist match (`NA` is on allowlist) |

When updating allowlists in `jira-adinc-tickets`, update `adinc_field_allowlists.py` in the same change.

## Invalid value matrix by check

| Value type | Structure check | Open invalid check | Closed invalid check |
|------------|-----------------|--------------------|-----------------------|
| Field missing | Fail | Fail | Fail |
| Blank (empty after `:`) | Pass (field exists) | Fail | Fail |
| `TBD` | Pass | Fail | Fail |
| `NA` / `N/A` on `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, `SOURCE_SYSTEM`, `EXTERNAL`, `MISSED_SLA` | Pass | Pass | Pass |
| `NA` / `N/A` on other required fields | Pass | Fail | Fail |
| Real value | Pass | Pass | Pass |

## Status classification

### Open (active work)

- `In Progress`
- `Open`
- `To Do`
- `Reopened`
- `Blocked`

JQL: `project = ADINC AND status in ("In Progress", "Open", "To Do", "Reopened", "Blocked")`

### Closed (completed)

- `Done`
- `Closed`
- `Resolved`

JQL: `project = ADINC AND status in (Done, Closed, Resolved)`

### Excluded from audit (cancelled / void)

- Status `Cancelled`, **or**
- Resolution `Cancelled` (Jira workflow may keep status as `Done` with resolution `Cancelled`)

These tickets are skipped for all checks — they do not count toward scanned or flagged totals.

## Dates tab (Start DatePick, Completion Date, End Date)

Canonical definition: **[adinc-jira-dates.md](../adinc-jira-dates.md)**

| Field | ID | Use |
|-------|-----|-----|
| Start DatePick | `customfield_10489` | Migrated SNOW: **SNOW opened/created**. Native ADINC: **DEV started work** (not Jira Created). |
| Completion Date | `customfield_10566` | **Blocked** — mitigated, waiting for RCA |
| End Date | `customfield_10453` | **Done** — RCA received (Notes) |

Jira **Created** on tickets imported **2026-05-30** is usually **bulk import time**, not incident open time — use **Start DatePick** for legacy SNOW open date.

## Notes / RCA field

Canonical definition: **[adinc-jira-notes.md](../adinc-jira-notes.md)**

| Property | Value |
|----------|--------|
| Jira UI location | General tab → **Notes** |
| Custom field ID | `customfield_10253` |
| JQL | `cf[10253]` |
| Valid RCA example | `RCA: Received the corrected data from business.` |
| Invalid / missing | empty, `#N/A`, `N/A`, `NA`, `RCA:` alone |

**Never use** Activity → Comments for RCA audits.

## Comments column templates

### Structure issues

```text
Missing: PD_ID, INC_NUMBER
Misspelled: NC_NUMBER (likely meant INC_NUMBER)
Extra fields: ERROR
Unparsed content: some free text line
Description is empty
All 10 required fields present and correctly named
```

### Invalid values (open or closed)

```text
SOURCE_SYSTEM=TBD; ISSUE_CATEGORY=TBD
PD_ID=Missing (field absent)
PIPELINE=Blank (empty value)
TEAM=NA
```

### Missing RCA

```text
Notes=Missing RCA
Notes=Placeholder (#N/A)
```

### Allowed values in fields (Check 6)

```text
TEAM=Invalid (expected "ads-data-support", got "ODS")
ISSUE_CATEGORY=NotInAllowlist ("DATA - DQ"); suggest: Data - DQ
SOURCE_SYSTEM=Blank ((empty))
PIPELINE=NotInAllowlist ("ADM-Segmentation"); suggest: ADM - Segmentation
Allowed values compliant
```

# Title format (Check 5 — INC_NUMBER=NA only)

```text
Summary must start with [AP]
Expected prefix [AP][Team][SubTeam] (optional extra bracket segment)
DAG "ap_addr_ods_metrics_mc_metadata_dq_prod" not found in summary title
Title format compliant
```

Proposed title example (audit output columns: **Current title** | **Proposed title**):

```text
Current title:   [AP][ADI][BI] ap_addr_bi_gen_programmatic_prod Missed SLA
Proposed title:  [AP][ADI][BI]ap_addr_bi_gen_programmatic_prod- Missed SLA
```

Remediation prompt (one ticket at a time):

```text
ADINC-769 — apply proposed title?
Current title:   ...
Proposed title:  ...
Reply: yes | no | edit: <custom title>
```

### Title format reference (Check 5)

**Scope:** description `INC_NUMBER` is `NA` only.

**Template:**

```text
[AP][Team name][Sub Team name / pipeline name (BI uses pipeline)]DAG name- short description
```

**Example:**

```text
[AP][ODS][METRICS]ap_addr_ods_metrics_mc_metadata_dq_prod- 14 ERROR-level constraints violated
```

| Segment | Examples |
|---------|----------|
| Team | `ODS`, `ADI`, `ADM` |
| Sub-team / pipeline | `METRICS`, `Core`, `BI`, `Targeting`, `Measurement`, `Segmentation` |
| Optional qualifier | `[Long Run]` (4th bracket, optional) |
| DAG | From description `DAG` field (primary token when multiple DAGs) |
| Separator | Hyphen `-` between DAG and description when `DAG` ≠ `NA` |

## Useful JQL snippets

```jql
# All ADINC tickets
project = ADINC ORDER BY created DESC

# Open tickets only
project = ADINC AND status = "In Progress" ORDER BY updated DESC

# Closed this month
project = ADINC AND status = Done AND created >= 2026-06-01

# Specific tickets
key in (ADINC-751, ADINC-735, ADINC-739)
```

## Pagination pattern

ADINC typically has 350+ tickets. Fetch in batches:

```text
start_at=0,   max_results=100  → issues 1–100
start_at=100, max_results=100  → issues 101–200
start_at=200, max_results=100  → issues 201–300
start_at=300, max_results=100  → remaining
```

Stop when `startAt + len(issues) >= total`.

## Output file naming

| Audit scope | Canvas filename |
|-------------|-----------------|
| Full audit | `adinc-audit-full.canvas.tsx` |
| Structure only | `adinc-audit-structure.canvas.tsx` |
| Open invalid values | `adinc-audit-open-invalid.canvas.tsx` |
| Closed invalid values | `adinc-audit-closed-invalid.canvas.tsx` |
| Missing RCA | `adinc-audit-rca.canvas.tsx` |
| Title format (INC_NUMBER=NA) | `adinc-audit-title-format.canvas.tsx` |
| Allowed values (dropdowns) | `adinc-audit-field-enums.canvas.tsx` |
| TBD/blank (user shorthand) | `adinc-audit-tbd-blank.canvas.tsx` |

## Example output row

| ADINC Ticket | Summary | Status | Created | Updated | Comments |
|---|---|---|---|---|---|
| [ADINC-751](https://deept.atlassian.net/browse/ADINC-751) | Snowflake Dimension Table empty | In Progress | 2026-06-15 | 2026-06-22 | SOURCE_SYSTEM=TBD; ISSUE_CATEGORY=TBD |

## Known ADINC scale (as of 2026-06)

- ~363 total tickets
- `NA` is accepted for `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, and `SOURCE_SYSTEM` when not applicable
- Typical flagged counts: structure 0–10, TBD/blank ~6, missing RCA varies
