---
name: jira-adinc-tickets
description: >-
  Creates Tasks and other issues in the Ads Data Incidents Jira project (ADINC)
  on deept.atlassian.net via user-jira-server MCP. Uses the ADINC incident description
  template, story points, assignee resolution, and summary title format (INC_NUMBER=NA).
  Use when the user asks to create, draft, or file an ADINC ticket, Task, or incident in Jira.
---

# ADINC Jira tickets

Create issues in **Ads Data Incidents** (`ADINC`) at [https://deept.atlassian.net/](https://deept.atlassian.net/).

## Configuration

| Setting | Value |
|---------|--------|
| Project key | `ADINC` |
| MCP server | `user-jira-server` |
| Jira instance | `https://deept.atlassian.net/` |
| Browse URL | `https://deept.atlassian.net/browse/{KEY}` |
| Story points field | `customfield_10106` |
| Notes (RCA) field | See [adinc-jira-notes.md](../adinc-jira-notes.md) → `customfield_10253` |
| Dates tab | See [adinc-jira-dates.md](../adinc-jira-dates.md) — Start DatePick `customfield_10489`, Completion `customfield_10566`, End `customfield_10453` |
| SLA-miss priority | `P1` when `MISSED_SLA` is affirmative (see below) |
| Fixed `TEAM` value | `ads-data-support` (always; see below) |
| Default issue type | `Task` |
| **Preferred creation path** | **Support Bot** in **Microsoft Teams** (`/support`) — not manual Jira create |
| Chat / coordination | **Microsoft Teams only** — do not reference Slack in user-facing ADINC guidance |

## Workflow

1. **Collect** — summary, description fields (see template), assignee, story points, issue type (default `Task`).
2. **Validate enums** — before draft or create, check `ISSUE_CATEGORY`, `SOURCE_SYSTEM`, and `PIPELINE` against the allowlists in [reference.md](reference.md):
   - Trim leading/trailing whitespace, then require **exact** match (case-sensitive).
   - If any field is **empty** or **not in the allowlist**: **do not create** the ticket. Stop and ask the user which allowed value to use. Show the invalid/missing value and the full allowlist for that field.
   - If multiple fields fail, report **all** failures in one message.
   - Optional: suggest the closest allowlist match(es) for typos, but still require explicit user confirmation of the corrected value before proceeding.
3. **Normalize TEAM** — `TEAM` is always `ads-data-support` in the ticket description:
   - If the user omits `TEAM` or provides a different value (e.g. `ODS`, `Measurement (ADM Fleet)`), **warn** that it will be set to `ads-data-support`, then use `ads-data-support` in the description. Do **not** block creation for TEAM mismatches.
   - Include the warning in the draft preview and in the final confirmation when a override occurred.
4. **Validate title format** — when description `INC_NUMBER` is `NA` / `N/A` / `N.A.` / `NONE`, the summary must follow the ADINC title standard (same as `jira-adinc-audit` Check 5 — see [reference.md](reference.md)):
   - If the user **provides a summary** that fails validation: **do not create**. Report what is wrong and show a **Suggested Title**. Ask the user to confirm the suggested title or reply with `edit: <your title>` before proceeding.
   - If the user **does not provide a summary**: auto-generate a compliant title from `PIPELINE`, `DAG`, `ISSUE_CATEGORY`, and `TASK` using the suggestion rules in [reference.md](reference.md).
   - When `INC_NUMBER` is a real ServiceNow INC (not `NA`), skip title format validation — use the user's summary as given.
5. **Resolve assignee** — see [reference.md](reference.md). Use `accountId` on deept.atlassian.net.
6. **Draft** — show a preview table (summary, assignee, points, full description). Skip only if the user explicitly says to create without review.
7. **Create** — read MCP tool schema, then `jira_create_issue`:
   - Required: `project_key: "ADINC"`, `summary`, `issue_type`
   - Optional: `description`, `assignee` (`accountId` preferred on deept.atlassian.net), `custom_fields: { "customfield_10106": N }`
8. **Set priority** — if `MISSED_SLA` is affirmative (`Y`, `Yes`, `YES`, or starts with `Yes`), call `jira_update_issue` with `priority: { "name": "P1" }`. `jira_create_issue` has no priority field; always update after create.
9. **Confirm** — return issue key, browse URL, assignee, priority, story points. If TEAM was overridden, note the warning again.

**Dates (native ADINC only):** After create, remind the assignee to set **Start DatePick** when the **DEV team starts work** (not at ticket creation). Use **Completion Date** when moving to **Blocked** (mitigated, waiting RCA) and **End Date** when **Done** with RCA in Notes — see [adinc-jira-dates.md](../adinc-jira-dates.md). Migrated SNOW tickets already have Start DatePick populated from SNOW open time.

## Description template

Use this structure for ADINC incident Tasks. Preserve field names and order exactly:

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

Fill in values the user provides; leave trailing space after labels when the user did (e.g. `TEAM:  ELSA`).

## MCP usage

Always read the tool descriptor under `user-jira-server` before calling `CallMcpTool`.

**Create Task:**

```json
{
  "server": "user-jira-server",
  "toolName": "jira_create_issue",
  "arguments": {
    "project_key": "ADINC",
    "summary": "[Test][Task][Cursor] Example summary",
    "issue_type": "Task",
    "description": "INC_NUMBER: INC29000904\nTEAM: ELSA\n...",
    "assignee": "user.email@disney.com",
    "custom_fields": { "customfield_10106": 1 }
  }
}
```

**Current user (assign to self):** `jira_current_user` → use `emailAddress` as assignee.

**Set P1 when SLA missed** (after create):

```json
{
  "server": "user-jira-server",
  "toolName": "jira_update_issue",
  "arguments": {
    "issue_key": "ADINC-856",
    "fields": {
      "priority": { "name": "P1" }
    }
  }
}
```

Apply when description `MISSED_SLA:` is `Y`, `Yes`, `YES`, or begins with `Yes` (e.g. `Yes, data is available...`). Do **not** set P1 for `N`, `No`, `NO`, or `NA`.

**Update Notes (RCA) on existing ticket** — General tab only; see [adinc-jira-notes.md](../adinc-jira-notes.md):

```json
{
  "server": "user-jira-server",
  "toolName": "jira_update_issue",
  "arguments": {
    "issue_key": "ADINC-791",
    "fields": {
      "customfield_10253": "RCA: Upstream data delay; job auto-recovered on retry."
    }
  }
}
```

## Rules

- **Enum validation is mandatory:** never create if `ISSUE_CATEGORY`, `SOURCE_SYSTEM`, or `PIPELINE` is missing or not an exact allowlist match. Prompt the user with allowed values.
- **`TEAM` is always `ads-data-support`:** override any other value; warn the user before/at create, but do not block.
- **Title format (INC_NUMBER=NA):** if the user supplies a non-compliant summary, stop and suggest a compliant title; do not create until they confirm. Auto-generate a compliant title when none is provided. Skip this check when `INC_NUMBER` is a real INC.
- Do not create ADINC issues without user confirmation unless they explicitly request immediate creation.
- Never log or return API tokens or credentials.
- If assignee lookup fails, create unassigned only if the user agrees; otherwise ask for their `@disney.com` email.
- Do not use display name or `"Last, First X"` as assignee on create — Jira returns "User does not exist." Use `accountId` from `jira_search_users` or assign via `jira_update_issue` after create.
- **MISSED_SLA → P1:** affirmative SLA miss values require priority `P1` via post-create update.
- After create, link: `https://deept.atlassian.net/browse/{KEY}`

## Examples

**INC_NUMBER=NA with auto-generated title:**

- Description: `PIPELINE: ADM - Segmentation`, `DAG: ap_addr_audience_hulu_fandom_inbound_prod`, `ISSUE_CATEGORY: Data - DQ`
- Summary (generated): `[AP][ADM][Segmentation]ap_addr_audience_hulu_fandom_inbound_prod- Data - DQ failure`

**INC_NUMBER=NA with invalid user title:**

```text
Your summary does not match the ADINC title format:
- Missing [AP][Team][SubTeam] prefix
- DAG not found in title

Suggested title: [AP][ADM][Segmentation]ap_addr_audience_hulu_fandom_inbound_prod- landing-dq-check-app run failed

Reply with the suggested title, or edit: <your compliant title>
```

**Real INC_NUMBER — title check skipped:**

- `INC_NUMBER: INC29000904` → use user's summary as provided

**Assign to self, test ticket:**

- Summary: `[Test][Task][Cursor]  This is a Test`
- Assignee from `jira_current_user`
- `customfield_10106`: 1

**Assign to named person with filled incident fields:**

- Resolve assignee email via [reference.md](reference.md)
- Pass filled description template and story points as given

## Additional resources

- **Title format** (INC_NUMBER=NA): [reference.md](reference.md) — aligned with `jira-adinc-audit` Check 5 / [adinc_title_format.py](../jira-adinc-audit/scripts/adinc_title_format.py)
- **Allowlists** (`ISSUE_CATEGORY`, `SOURCE_SYSTEM`, `PIPELINE`): [reference.md](reference.md)
- Assignee resolution and known pitfalls: [reference.md](reference.md)
- **ADINC Notes (RCA) canonical field:** [adinc-jira-notes.md](../adinc-jira-notes.md)
