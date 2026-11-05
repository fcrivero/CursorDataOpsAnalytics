# ADIA Status Report — Reference

## Jira instance

| Setting | Value |
|---------|--------|
| Jira Cloud | [https://deept.atlassian.net/](https://deept.atlassian.net/) |
| Browse URL | `https://deept.atlassian.net/browse/{KEY}` |
| MCP server | `user-jira-server` (`JIRA_SERVER=https://deept.atlassian.net`) |

Never use `jira.disney.com` for queries or links.

### Story points field

The MCP maps story points via `JIRA_STORY_POINTS_FIELD` in the Jira MCP `.env` file. On [deept.atlassian.net](https://deept.atlassian.net/), use `customfield_10047` (discovered via `jira_get_fields`). Rebuild the Docker image after changing env vars.

## Date parsing

Convert the user's period to inclusive `start_date` and `end_date` in `YYYY-MM-DD`.

| User input | start_date | end_date |
|------------|------------|----------|
| `June 26 to July 2 2026` | `2026-06-26` | `2026-07-02` |
| `June 26–July 2, 2026` | `2026-06-26` | `2026-07-02` |
| `July 2026` | `2026-07-01` | `2026-07-31` |
| `June` (no year) | `YYYY-06-01` | `YYYY-06-30` — use current calendar year |
| `Q3 2026` | `2026-07-01` | `2026-09-30` | 

If the period is ambiguous (e.g. "last week" with no anchor date), ask the user for explicit dates.

**Resolved JQL** uses both bounds inclusively: `resolved >= "{start}" AND resolved <= "{end}"`.

**Teams thread title** uses compact `period_label`: `M/D-M/D` (e.g. July 16–22 → `7/16-7/22`, June 26–July 2 → `6/26-7/2`).

## Microsoft Teams posting

Optional. Default channel, CC recipients, and CLI workflow: [teams-posting.md](teams-posting.md). Always confirm with the user before posting.

## Default assignees

| Name | Email |
|------|-------|
| Dawid Godzic | `Dawid.Godzic.-ND@disney.com` |
| Fernando Rivero | `fernando.c.rivero@disney.com` |

For additional team members, resolve to `@disney.com` email before querying. Display names alone do not work reliably in JQL — search existing ADIA issues for the person's assignee email if needed (see `jira-adinc-tickets` reference).

## JQL templates

Replace `{emails}`, `{start}`, `{end}`:

**In Progress (current snapshot):**
```jql
project = ADIA AND assignee in ({emails}) AND statusCategory = "In Progress" AND status != Blocked AND issuetype != Epic ORDER BY key ASC
```

**Resolved (period-bound):**
```jql
project = ADIA AND assignee in ({emails}) AND statusCategory = Done AND resolved >= "{start}" AND resolved <= "{end}" AND issuetype != Epic ORDER BY key ASC
```

**Blocked (current snapshot):**
```jql
project = ADIA AND assignee in ({emails}) AND status = Blocked AND issuetype != Epic ORDER BY key ASC
```

## Story points

- Field returned as `points` when using `fields: "*all"`.
- `points: null` → display **`NO POINTS`** (all caps).
- `points: 1.0` → display **1 point** (singular).
- `points: 3.0` → display **3 points**.

## Assignee first name

From Jira `assignee` display name (e.g. `Dawid Godzic` → `Dawid`, `Fernando Rivero` → `Fernando`). Use the first whitespace-delimited token.

## Trigger phrases

- `ap-dataenab-adinc-support`
- `ADIA status report`
- `Ad Infrastructure Analytics` weekly/monthly report
- Report for Dawid and Fernando (with date range)

## Common pitfalls

1. **Missing In Progress tickets** — report is a point-in-time snapshot; tickets moved to In Progress after the query won't appear until re-run.
2. **Epics in results** — forgot `issuetype != Epic`; Epics often have null points and skew totals.
3. **Null points** — querying with `fields: "points"` instead of `*all` returns null for many issues.
4. **Blocked vs Resolved** — tickets resolved during the period belong in **Resolved**, not Blocked, even if they were Blocked earlier.
