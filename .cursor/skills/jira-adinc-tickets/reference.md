# ADINC reference

## TEAM (fixed value)

`TEAM` is **always** `ads-data-support` in the ticket description.

| User provides | Action |
|---------------|--------|
| `ads-data-support` | Use as-is |
| Any other value (e.g. `ODS`, `ELSA`, `Measurement (ADM Fleet)`) | **Warn** user it will be changed to `ads-data-support`, then write `ads-data-support` |
| Empty / omitted | Set to `ads-data-support` (no warning unless user explicitly sent a different TEAM) |

**Warning example:**

```text
Note: TEAM was provided as "ODS" — ADINC tickets always use TEAM: ads-data-support. I will set TEAM to ads-data-support in the ticket.
```

## Field allowlists (required before create)

Validate **exact** match after trimming whitespace. If invalid or empty, **stop** and ask the user to pick from the list below. Do not create the ticket.

### ISSUE_CATEGORY

- AWS - Athena
- AWS - EKS
- AWS - Flink
- AWS - Glue
- AWS - KDA
- AWS - Kinesis
- AWS - Lambda
- AWS - S3
- AWS - vCPU
- Code - Deployment
- Code - Invalid Identifier
- Code - Schedule
- Code - Syntax
- Credentials
- Data - DQ
- Data - Format
- Data - Object
- Data - Partial
- Data - Upstream Delay
- Manual Error
- Network
- Spark
- Vendor - API
- Waiting for RCA

### SOURCE_SYSTEM

- 3P Vendor - AWS
- 3P Vendor - AX
- 3P Vendor - AdIntel
- 3P Vendor - Airflow
- 3P Vendor - ComScore
- 3P Vendor - Databricks
- 3P Vendor - FUBO
- 3P Vendor - Fluentbit
- 3P Vendor - GAM
- 3P Vendor - Hightouch
- 3P Vendor - Kalido
- 3P Vendor - ListenFirst
- 3P Vendor - LiveRamp
- 3P Vendor - Nielsen
- 3P Vendor - O1
- 3P Vendor - Oracle
- 3P Vendor - Pathmatics
- 3P Vendor - Qlik
- 3P Vendor - SAP BOE
- 3P Vendor - SQL-MI
- 3P Vendor - STAQ
- 3P Vendor - SalesHub
- 3P Vendor - Salesforce
- 3P Vendor - Snowflake
- 3P Vendor - TalkWalker
- 3P Vendor - Taxonomy
- 3P Vendor - Telaria
- 3P Vendor - Tidal
- ADM - Measurement
- ADM - Segmentation
- ADM - Targeting
- AdVisor
- Ads Data Infra
- Ads Server
- BI DRR
- BI Goldmine
- BI Ralph
- Data Ops
- Harps
- Linear BI
- ODS - Data Core
- ODS - Metrics
- Waiting for RCA

### PIPELINE

- ADM - Measurement
- ADM - Segmentation
- ADM - Targeting
- D+ - International - Ralph
- Disney O&O - DRR
- EDW - AdSales
- EDW - Prodops
- Goldmine - Addressable B&W
- Goldmine - Delivery Context
- Goldmine - Delivery/Supply/Prg
- Goldmine - Realized Metrics
- Goldmine - STAQ
- Goldmine - STR
- Linear - ASR
- Linear - DART
- Linear - DATG
- Linear - ELSA
- Linear - LDB
- NA
- ODS - Data Core
- ODS - Metric
- ODS - Metrics
- Waiting for RCA

### Prompt template when validation fails

```text
Cannot create ADINC ticket — invalid or missing field(s):

- ISSUE_CATEGORY: "<provided>" — not in allowlist
  Allowed values: [list]

- SOURCE_SYSTEM: "<provided>" — not in allowlist
  Allowed values: [list]

Which value should I use for each field?
```

Which value should I use for each field?
```

## Summary title format (INC_NUMBER=NA only)

Aligned with `jira-adinc-audit` Check 5. When description `INC_NUMBER` is `NA`, `N/A`, `N.A.`, or `NONE`, the Jira **summary** must follow this format. Tickets with a real ServiceNow `INC_NUMBER` are **exempt**.

### Template

```text
[AP][Team name][Sub Team / pipeline name]DAG name- short description
```

Optional 4th bracket for qualifiers (e.g. `[Long Run]`).

### Canonical example

```text
[AP][ODS][METRICS]ap_addr_ods_metrics_mc_metadata_dq_prod- 14 ERROR-level constraints violated
```

### Format rules

| Segment | Rule |
|---------|------|
| `[AP]` | Required prefix |
| `[Team name]` | Second bracket — e.g. `ODS`, `ADI`, `ADM`, `Linear`, `EDW`, `BI` |
| `[Sub Team / pipeline]` | Third bracket — e.g. `METRICS`, `Core`, `Segmentation`, `BI` |
| Optional 4th bracket | e.g. `[Long Run]` |
| `DAG name` | When description `DAG` ≠ `NA`, primary DAG token must appear in summary after brackets |
| Short description | Non-empty after brackets / DAG (hyphen before description is recommended, not required for audit) |

### Validation failures (block create if user supplied title)

Aligned with `jira-adinc-audit` Check 5:

- Summary does not start with `[AP]`
- Missing `[AP][Team][SubTeam]` prefix
- Description `DAG` ≠ `NA` but DAG token absent from summary
- Description `DAG` is `NA` but no substantive text after bracket prefix

**Not validated:** missing hyphen between DAG and description.

### Suggested title generation

When the user omits a summary, or when suggesting a fix, build:

1. **Prefix** from `PIPELINE` (see mapping below) or from brackets in the user's draft title
2. **DAG segment** — primary token from description `DAG` (first token if multiple, ignore `NA`)
3. **Short description** — from user title text, `ISSUE_CATEGORY`, `TASK`, or `landing-dq-check-app run failed`-style fallback

**When `DAG` is present:**

```text
{prefix}{dag_display}- {short_description}
```

**When `DAG` is `NA`:**

```text
{prefix}{short_description}
```

### PIPELINE → prefix mapping

| PIPELINE | Prefix |
|----------|--------|
| ODS - Metrics / ODS - Metric | `[AP][ODS][METRICS]` |
| ODS - Data Core | `[AP][ODS][Core]` |
| ADM - Measurement | `[AP][ADM][Measurement]` |
| ADM - Segmentation | `[AP][ADM][Segmentation]` |
| ADM - Targeting | `[AP][ADM][Targeting]` |
| BI Goldmine, Goldmine - *, D+ - International - Ralph | `[AP][ADI][BI]` |
| Disney O&O - DRR | `[AP][BI][DRR]` |
| Linear - ASR / ELSA / DATG / DART / LDB | `[AP][Linear][{name}]` |
| EDW - AdSales | `[AP][EDW][AdSales]` |
| EDW - Prodops | `[AP][EDW][Prodops]` |
| NA / Waiting for RCA / unknown | `[AP][ADI][BI]` (default) |

For full logic, mirror [../jira-adinc-audit/scripts/adinc_title_format.py](../jira-adinc-audit/scripts/adinc_title_format.py) → `suggest_title_format()`.

### Prompt when user title fails validation

```text
Summary does not match the ADINC title format (INC_NUMBER=NA):

Your title:   {provided}
Issues:       {findings joined with "; "}
Suggested:    {suggested_title}

Reply: use suggested | edit: <your compliant title>
```

Do **not** create the ticket until the user confirms a compliant summary.

## Assignee resolution

Jira create accepts **username / email**, not display name.

| Input user gives | Works on create? |
|------------------|------------------|
| `Fernando.C.Rivero@disney.com` | Yes |
| `Charan.X.Arvapally.-ND@disney.com` | Yes (contractor suffix `-ND`) |
| `Charan Arvapally` | No |
| `Arvapally, Charan X` | No |

### Steps to resolve a display name

1. `jira_search_issues` with JQL:
   ```jql
   assignee = "Charan Arvapally" ORDER BY updated DESC
   ```
   (Use the Jira display name from search results, not HR `"Last, First X"` format.)

2. If issues exist, get assignee email from any issue key via Jira REST (MCP `jira_get_issue` may not expose email):
   - `GET /rest/api/2/issue/{KEY}?fields=assignee`
   - Use `fields.assignee.emailAddress` as the `assignee` value on create.

3. If no issues found, ask the user for the person's `@disney.com` email.

### Assign to current user

```text
jira_current_user → emailAddress
```

Example: `Fernando.C.Rivero@disney.com`

## Verified ADINC creates

| Key | Assignee email | Notes |
|-----|----------------|-------|
| ADINC-734 | Fernando.C.Rivero@disney.com | Test task, 1 SP |
| ADINC-735 | Charan.X.Arvapally.-ND@disney.com | Incident fields filled, 1 SP |

## Issue types

- **Task** — default for ADINC incidents (used in production workflow)
- **Story** — use only when the user explicitly requests `Story`

## Priority (MISSED_SLA → P1)

`jira_create_issue` does not accept priority. After create, if `MISSED_SLA` is affirmative, update:

```json
{
  "issue_key": "ADINC-####",
  "fields": { "priority": { "name": "P1" } }
}
```

| `MISSED_SLA` value | Priority |
|--------------------|----------|
| `Y`, `Yes`, `YES` | **P1** |
| Starts with `Yes` (e.g. `Yes, data is stale...`) | **P1** |
| `N`, `No`, `NO`, `NA` | Default (do not force P1) |

## Assignee on deept.atlassian.net

Email alone may not stick on create. Prefer:

1. `jira_search_users` → `accountId`
2. `jira_update_issue` with `{ "assignee": { "accountId": "712020:..." } }`

Known: **Praveen Sadineni** → `712020:c18733c5-ca17-4edb-a63c-664f3eb65780` (`praveen.sadineni@disney.com`)

## Dates tab (Key details)

Full semantics: **[adinc-jira-dates.md](../adinc-jira-dates.md)**

| UI field | Field ID | Native ADINC (post-migration) |
|----------|----------|-------------------------------|
| Start DatePick | `customfield_10489` | Set when **DEV starts work** (not Jira Created) |
| Completion Date | `customfield_10566` | Set when **Blocked** — mitigated, waiting for RCA |
| End Date | `customfield_10453` | Set when **Done** — RCA in Notes |

Imported SNOW tickets (`created` ≤ 2026-05-30): **Start DatePick** already holds **SNOW opened/created** from migration.

Update via `jira_update_issue` when the user provides dates, e.g. `"customfield_10489": "2026-10-23"`.

## Story points

Field ID: `customfield_10106`

Pass on create:

```json
"custom_fields": { "customfield_10106": 1 }
```

Or update after create with `jira_update_issue` if needed.

## Summary conventions

**INC_NUMBER=NA** — must follow [Summary title format](#summary-title-format-inc_numberna-only) above.

**Real ServiceNow INC** — any summary the user provides; title format check skipped.

Test tickets (optional):

```text
[Test][Task][Cursor]  <short description>
```

## MCP tools (user-jira-server)

| Action | Tool |
|--------|------|
| Create | `jira_create_issue` |
| Update | `jira_update_issue` |
| Search / validate | `jira_search_issues` |
| Current user | `jira_current_user` |
| Get issue | `jira_get_issue` |

User search (`jira_search_users`) may fail on this Jira instance; prefer assignee JQL + issue lookup.
