# SKRULL reference

## Assignee resolution

Jira create accepts **username / email**, not display name.

| Input user gives | Works on create? |
|------------------|------------------|
| `Deepthi.Konda@disney.com` | Yes |
| `Charan.X.Arvapally.-ND@disney.com` | Yes (contractor suffix `-ND`) |
| `Deepthi Konda` | No |
| `Konda, Deepthi` | No |

### Steps to resolve a display name

1. Search SKRULL issues assigned to that person:
   ```jql
   project = SKRULL AND assignee = "Deepthi Konda" ORDER BY updated DESC
   ```
   Use the Jira **display name** exactly as returned in search results.

2. If issues exist, resolve email from a recent issue (MCP `jira_get_issue` may not expose email; use Jira REST if needed):
   - `GET /rest/api/2/issue/{KEY}?fields=assignee`
   - Use `fields.assignee.emailAddress` as the `assignee` value on create.

3. If no SKRULL issues found, broaden search:
   ```jql
   assignee = "Deepthi Konda" ORDER BY updated DESC
   ```

4. If still not found, ask the user for the person's `@disney.com` email.

### Assign to current user (default)

When the user does not specify an assignee, this is the skill default:

```
jira_current_user → emailAddress
```

Call `jira_current_user` before drafting so the preview shows the resolved name and email.

## SKRULL team display names (common)

Use these exact strings in JQL assignee search when resolving email:

- Amrita TE
- Aravind Padmanabhan
- Ashish Patil
- Ch Nabin Patro
- Charan Arvapally
- Deepthi Konda
- Gowri Swetha GS
- Juhi Kumari
- Karishma Shah
- Pawan Bhagwan
- Prashant Shirke
- Praveen Sadineni
- Salman Khan
- Sara Chabukswar
- Shivani M R
- Shusma Kafle

## Issue types

| Type | When to use |
|------|-------------|
| **Story** | Default — routine ticket creation |
| Task | **Never** — if the user says "task," still create a **Story** and say so in the confirmation |
| **Epic** | When the user **explicitly** requests epic creation — see [SKILL.md](SKILL.md#version-defaults-epic-creation-only) |

## Fix & Affects versions (**Epic create only**)

Do **not** set these on **Story** creates unless the user explicitly asks.

| Friendly name | Jira field | Role | Epic default |
|---------------|------------|------|----------------|
| Fix versions | `fixVersions` | Target release train | **SKRULL.2027** |
| Affects versions | `versions` | Quarter / planning bucket | **Current `SKRULL.2027.Q*`** |

Refresh IDs with `jira_get_project_versions` → `project_key: "SKRULL"` if an update fails.

### Fix version IDs (as of 2026)

| Name | Version id |
|------|------------|
| SKRULL.2027 | `106017` |

### SKRULL.2027 fiscal quarters (Affects default)

Use **creation date** to pick the Affects version name (aligned with Jira `startDate` / `releaseDate`):

| Affects version | Version id | Start | Release (end) |
|-----------------|------------|-------|----------------|
| SKRULL.2027.Q1 | `106018` | 2026-09-30 | 2026-12-31 |
| SKRULL.2027.Q2 | `106551` | 2027-01-01 | 2027-03-31 |
| SKRULL.2027.Q3 | `106553` | 2027-04-01 | 2027-06-30 |
| SKRULL.2027.Q4 | `106552` | 2027-07-01 | 2027-09-30 |

**Calendar shortcut** (matches `scripts/skrull_version_defaults.py`):

| Calendar months | Affects version |
|-----------------|-----------------|
| Oct–Dec | `SKRULL.(Y+1).Q1` |
| Jan–Mar | `SKRULL.Y.Q2` |
| Apr–Jun | `SKRULL.Y.Q3` |
| Jul–Sep | `SKRULL.Y.Q4` |

**Examples**

- 2026-11-18 → **SKRULL.2027.Q1** (`106018`)
- 2027-02-15 → **SKRULL.2027.Q2** (`106551`)

**Empty Affects:** `jira_update_issue` → `"versions": []`

**Empty Fix:** `jira_update_issue` → `"fixVersions": []` (only when user explicitly requests no Fix version)

## Custom fields

| Friendly name | Field ID | Default |
|---------------|----------|---------|
| Story Points | `customfield_10047` | **3** when not specified |
| Target Date | `customfield_10429` | unset when not specified |

Do **not** use `customfield_10106` — that is ADINC, not SKRULL.

### Target Date format

- Jira expects **`YYYY-MM-DD`** (e.g. `2026-08-14` for August 14, 2026).
- Parse common user inputs: `August 14, 2026`, `08/14/2026`, `2026-08-14`.
- Pass on create/update:
  ```json
  "custom_fields": { "customfield_10429": "2026-08-14" }
  ```

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
| SKRULL board | https://deept.atlassian.net/jira/software/c/projects/SKRULL/boards/489 |
| Issue browse | https://deept.atlassian.net/browse/{KEY} |
| Project | https://deept.atlassian.net/jira/software/c/projects/SKRULL |

## Points verification pitfall

`jira_search_issues` often returns `"points": null` for SKRULL tickets even when the UI shows story points. After create or when reporting points, call `jira_get_issue` with `fields: *all` to read `customfield_10047` / `points` accurately.
