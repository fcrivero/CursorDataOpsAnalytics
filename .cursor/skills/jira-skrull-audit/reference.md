# SKRULL audit reference

## Status classification

| Category | Status names (typical) |
|----------|-------------------------|
| Terminal | `Done`, `Closed`, `Resolved`, `Cancelled` |
| Open / active | `Open`, `In Progress`, `To Do`, `Backlog`, `Blocked`, `Reopened`, others not terminal |
| Blocked (Check 5) | Exact status name `Blocked` |

Default audit population excludes terminal statuses.

## Check 4 — open age

Check 4 uses **created** only (`created` field / `created <= -Nd` JQL). Never use `updated` for this check.

Default: open **more than 8 days** → **Days Open ≥ 9**; JQL `created <= -9d`.

## Output row sort

All check tables: **Assignee** (A→Z, `(Unassigned)` first) then **Created** (oldest first). Show **Assignee** and **Created** columns in every check table.

## Custom fields

| Friendly name | Field ID | Audit use |
|---------------|----------|-----------|
| Story Points | `customfield_10047` | Check 3 (Stories only) |
| Target Date | `customfield_10429` | Not audited by default |

MCP search often returns `"points": null` when points exist — use `jira_get_issue` for disputed rows.

## Epic detection

SKRULL may link work to an Epic via:

1. **Epic Link** (company-managed) — JQL `"Epic Link" is not EMPTY`
2. **Parent** (team-managed) — JQL `parent is not EMPTY` where parent is an Epic

**Missing Epic:** `"Epic Link" is EMPTY AND parent is EMPTY`

MCP normalized fields: `epic_link`, `parent` (may be null even when Jira UI shows a link — prefer JQL confirmation for edge cases).

## Open Epics for suggestions

Include Epics that are still active:

```jql
project = SKRULL AND issuetype = Epic
AND status not in (Done, Closed, Resolved, Cancelled)
ORDER BY updated DESC
```

Prefer suggesting **Open** or **In Progress** Epics over stale Backlog Epics when scores tie (tie-breaker in `skrull_epic_suggest.py`).

## Epic suggestion heuristics

`scripts/skrull_epic_suggest.py` scores overlap between ticket text and Epic `summary` + `description`:

- Token overlap (alphanumeric words length ≥ 3)
- Boost when Epic summary contains a known pipeline/platform token also in the ticket (e.g. `QLIK`, `ELSA`, `ADINC`, `SUNSHINE`, `TIDAL`, `DATADOG`, `DATABRICKS`, `MONTE CARLO`, `PRODOPS`, `SNOWFLAKE`)
- Boost for shared person-name tokens in weekly support titles (`CHARAN`, `SALMAN`, etc.) matching Epic naming patterns

Return up to **3** Epics with score > 0; if none score, return empty list (show `—` in table).

## Assignee (Check 1)

Unassigned when `assignee` is null or empty string in MCP results. JQL equivalent: `assignee is EMPTY`.

Check 1 **does not** evaluate tickets in **`Open`** or **`Backlog`** — only statuses beyond not-yet-started (e.g. In Progress, In Review, Blocked, Test Queue, etc.).

## URLs

| Resource | URL |
|----------|-----|
| Board | https://deept.atlassian.net/jira/software/c/projects/SKRULL/boards/489 |
| Issue | https://deept.atlassian.net/browse/{KEY} |

## Team display names

See [jira-skrull-tickets/reference.md](../jira-skrull-tickets/reference.md) for common assignee JQL names.
