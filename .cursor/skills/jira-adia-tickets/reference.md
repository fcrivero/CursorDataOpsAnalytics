# ADIA reference

## Assignee resolution

Jira create accepts **username / email**, not display name.

| Input user gives | Works on create? |
|------------------|------------------|
| `fernando.c.rivero@disney.com` | Yes |
| `Dawid.Godzic.-ND@disney.com` | Yes (contractor suffix `-ND`) |
| `Dawid Godzic` | No |
| `Godzic, Dawid` | No |

### Steps to resolve a display name

1. Search ADIA issues assigned to that person:
   ```jql
   project = ADIA AND assignee = "Dawid Godzic" ORDER BY updated DESC
   ```
   Use the Jira **display name** exactly as returned in search results.

2. If issues exist, resolve email from a recent issue (MCP `jira_get_issue` may not expose email; use Jira REST if needed):
   - `GET /rest/api/2/issue/{KEY}?fields=assignee`
   - Use `fields.assignee.emailAddress` as the `assignee` value on create.

3. If no ADIA issues found, broaden search:
   ```jql
   assignee = "Dawid Godzic" ORDER BY updated DESC
   ```

4. If still not found, ask the user for the person's `@disney.com` email.

### Assign to current user (default)

When the user does not specify an assignee, this is the skill default:

```
jira_current_user → emailAddress
```

Call `jira_current_user` before drafting so the preview shows the resolved name and email.

## ADIA team display names (common)

Use these exact strings in JQL assignee search when resolving email:

- Dawid Godzic
- Fernando Rivero

## Issue types

| Type | When to use |
|------|-------------|
| **Story** | Default and only type supported by this skill |
| Epic | **Not supported** by this skill |
| Task | **Not supported** by this skill — use `jira-adinc-tickets` for ADINC Tasks |

## Custom fields

| Friendly name | Field ID | Default |
|---------------|----------|---------|
| Story Points | `customfield_10047` | **3** when not specified |

Do **not** use `customfield_10106` — that is ADINC, not ADIA.

## MCP tools (user-jira-server)

| Action | Tool |
|--------|------|
| Create | `jira_create_issue` |
| Update | `jira_update_issue` |
| Search / validate assignee | `jira_search_issues` |
| Current user | `jira_current_user` |
| Get issue / verify points | `jira_get_issue` |
| Create metadata | `jira_get_create_meta` |

## URLs

| Resource | URL |
|----------|-----|
| ADIA board | https://deept.atlassian.net/jira/software/c/projects/ADIA/boards/3704 |
| Issue browse | https://deept.atlassian.net/browse/{KEY} |
| Project | https://deept.atlassian.net/jira/software/c/projects/ADIA |

## Points verification pitfall

`jira_search_issues` often returns `"points": null` for ADIA tickets even when the UI shows story points. After create or when reporting points, call `jira_get_issue` with `fields: *all` to read `customfield_10047` / `points` accurately.
