---
name: jira-skrull-tickets
description: >-
  Creates Stories (and Epics when requested) in the SKRULL Jira project on
  deept.atlassian.net via user-jira-server MCP. Stories accept assignee, story
  points, summary, description, optional target date. Epic creation sets default
  Fix version SKRULL.2027 and current fiscal-quarter Affects version unless
  overridden. Story creates always use issue type Story (never Task). Use when
  the user asks to create, draft, or file a SKRULL ticket, story, or epic.
---

# SKRULL Jira Stories & tickets

Create **Story** issues (and **Epic** issues when requested) in **SKRULL** on [deept.atlassian.net](https://deept.atlassian.net/jira/software/c/projects/SKRULL/boards/489).

## Configuration

| Setting | Value |
|---------|--------|
| Project key | `SKRULL` |
| Board | [SKRULL board 489](https://deept.atlassian.net/jira/software/c/projects/SKRULL/boards/489) |
| MCP server | `user-jira-server` |
| Browse URL | `https://deept.atlassian.net/browse/{KEY}` |
| Story points field | `customfield_10047` |
| Target Date field | `customfield_10429` |
| Default assignee | Current user (`jira_current_user`) — **Stories only** |
| Default story points | `3` — **Stories only** |
| Allowed issue types | **`Story`** (default); **`Epic`** only when the user explicitly requests epic creation |
| Epic Fix / Affects | **`SKRULL.2027`** + current FY quarter — **Epics only** — see [Version defaults](#version-defaults-epic-creation-only) |

## Version defaults (**Epic creation only**)

Do **not** set Fix or Affects versions on **Story** creation unless the user explicitly asks for versions on that issue.

When the user requests an **Epic**, apply after create (unless overridden):

| Field | Default | User override examples |
|-------|---------|-------------------------|
| **Fix versions** | `SKRULL.2027` | `"Fix version …"`, `"no Fix versions"` |
| **Affects versions** | Current fiscal quarter (e.g. `SKRULL.2027.Q1` on 2026-11-18) | `"no Affects versions"`, `"Affects SKRULL.2027.Q2"` |

**Override rules (Epics)**

- User-specified Fix version(s) replace `SKRULL.2027`.
- **no Affects versions** → `versions: []`.
- Named Affects quarter → use that instead of computed current quarter.
- **no Fix versions** → `fixVersions: []` only when user is explicit.

**How to set versions on Epics**

`jira_create_issue` may not reliably set Fix/Affects on SKRULL. After a successful Epic create, call `jira_update_issue` with resolved `fixVersions` and `versions`. Compute names via [`scripts/skrull_version_defaults.py`](scripts/skrull_version_defaults.py) → `default_version_fields()` unless the user overrides.

**Current fiscal quarter (Epic Affects default)**

Use the **calendar date of creation**:

1. Quarter table in [reference.md](reference.md) and `fiscal_quarter_affects_version()` in the script.
2. If outside ranges, `jira_get_project_versions` for `SKRULL`, match `SKRULL.2027.Q*` by `startDate` / `releaseDate`.
3. If ambiguous, ask the user.

## Inputs

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| **Summary** | Yes | — | Issue title |
| **Description** | Yes | — | Plain text or Jira wiki markup |
| **Assignee** | No | **Current user** (Stories) | Resolve via `jira_current_user` → `emailAddress` |
| **Story points** | No | **3** | Stories only; `custom_fields` |
| **Target date** | No | — | Stories only; **Target Date** field (`customfield_10429`), not description text |
| **Fix / Affects versions** | No | **Epics only** | See table above; never auto-set on Stories |

If **summary** or **description** is missing, ask the user before drafting. Apply assignee and story point defaults when omitted (**Stories only**). Parse target date from user input when provided (e.g. `Target Date: August 14, 2026`, `08/14/2026`) and convert to `YYYY-MM-DD` for Jira.

**Epic-only inputs** (when user requests epic creation): optional assignee; optional **epic name** (`epic_name` on create if the Epic Name field is required); Fix/Affects per [Version defaults](#version-defaults-epic-creation-only).

If the user says **Task**, treat it as SKRULL vocabulary only — still create a **Story** and mention that in the confirmation (do not create `issue_type: Task`).

## Workflow

### Stories (default path)

1. **Collect** — summary, description, and optional overrides (assignee, story points, target date).
2. **Route by type** — if the user explicitly asks to **create an Epic**, follow [Epic workflow](#epic-workflow) instead.
3. **Apply Story defaults** — assignee (`jira_current_user` if omitted), story points **3**, target date if provided. **Do not** set fix/affects versions.
4. **Validate type** — **Story** only; never **Task** (map "task" language to Story).
5. **Resolve assignee** — see [reference.md](reference.md). Use email on create, not display name.
6. **Draft** — preview table (default values in **bold**). Include: Project, Type, Summary, Assignee, Story points, Target date, Description. Skip preview only if the user explicitly says to create without review.
7. **Create** — `jira_create_issue`:
   - Required: `project_key: "SKRULL"`, `summary`, `issue_type: "Story"`
   - Optional: `description`, `assignee` (email), `custom_fields` with story points and target date only (**no** fix/affects versions)
8. **Assignee fix-up** — if assignee email on create does not stick, `jira_update_issue` with `assignee: { accountId: "..." }` from `jira_search_users`.
9. **Confirm** — issue key, browse URL, assignee, story points, target date (if set), type (**Story**).

### Epic workflow

Use **only** when the user explicitly asks to create a SKRULL **Epic**.

1. **Collect** — summary, description, optional assignee, optional epic name, optional Fix/Affects overrides.
2. **Apply Epic version defaults** — Fix `SKRULL.2027`, Affects = current FY quarter (`default_version_fields()`), unless user overrides in the same request.
3. **Draft** — preview including **Fix** and **Affects** rows (defaults in **bold**).
4. **Create** — `jira_create_issue` with `issue_type: "Epic"`, `description`, optional `assignee`, optional `epic_name` if required by create meta.
5. **Set versions** — `jira_update_issue` with `fixVersions` and `versions` (names or ids from [reference.md](reference.md)). Repeat if create left versions empty.
6. **Assignee fix-up** — same as Stories if needed.
7. **Confirm** — key, URL, assignee, **Fix** and **Affects** versions applied.

## MCP usage

Always read the tool descriptor under `user-jira-server` before calling `CallDynamicTool`.

**Create Story (no automatic Fix/Affects):**

```json
{
  "namespace": "user-jira-server",
  "toolName": "jira_create_issue",
  "arguments": {
    "project_key": "SKRULL",
    "summary": "Example SKRULL story",
    "issue_type": "Story",
    "description": "What needs to be done and acceptance criteria.",
    "assignee": "user.email@disney.com",
    "custom_fields": {
      "customfield_10047": 3,
      "customfield_10429": "2026-08-14"
    }
  }
}
```

**Create Epic, then set versions:**

```json
{
  "namespace": "user-jira-server",
  "toolName": "jira_update_issue",
  "arguments": {
    "issue_key": "SKRULL-1234",
    "fields": {
      "fixVersions": [{ "name": "SKRULL.2027" }],
      "versions": [{ "name": "SKRULL.2027.Q1" }]
    }
  }
}
```

**Default assignee (self):** when assignee is omitted on Stories, call `jira_current_user` → use `emailAddress`.

**Verify story points after create:** `jira_get_issue` with `fields: *all` — search results may return `points: null` even when points are set.

## Story points

- SKRULL uses **`customfield_10047`**, not `customfield_10106` (ADINC).
- Pass points on create via `custom_fields`.
- If create succeeds but points are missing, update with `jira_update_issue` and the same field ID.

## Target date

- SKRULL **Target Date** field: **`customfield_10429`** (type `date`).
- Optional input on **Stories**; omit when the user does not provide a target date.
- Accept natural-language dates from the user and normalize to **`YYYY-MM-DD`** before create/update.
- Set via `custom_fields` on create, or `jira_update_issue` after create if needed.
- Do **not** rely on putting target date only in the description — that does not populate the Jira field shown in the issue sidebar.

## Rules

- **Stories:** always set `issue_type` to **Story** — never Task, even if the user says "task" or "SKRULL task."
- **Epic only:** apply Fix/Affects defaults (Epic workflow step 5) unless user overrides in the same request.
- **Stories:** do not touch Fix or Affects unless the user explicitly asks.
- Do not create SKRULL issues without user confirmation unless they explicitly request immediate creation.
- Never log or return API tokens or credentials.
- Create **Epics** only when the user explicitly requests an epic.
- If assignee lookup fails, create unassigned only if the user agrees; otherwise ask for `@disney.com` email.
- Do not use display name or `"Last, First X"` as assignee on create — Jira returns "User does not exist."
- After create, link: `https://deept.atlassian.net/browse/{KEY}`

## Examples

**Minimal Story (all defaults):**

- Summary + description only → **Story**, assignee **you**, points **3**, **no** version update.

**Epic (default versions):**

- User: `create epic on SKRULL: Platform Modernization`
- Fix: `SKRULL.2027`, Affects: current quarter (e.g. `SKRULL.2027.Q1`).

**Epic with no Affects:**

- User: `… Fix Versions SKRULL.2027 and no Affects versions`
- Fix: `SKRULL.2027`; Affects: `[]`

**Story for Deepthi, 3 points (override assignee):**

- Type: **Story**; no automatic Fix/Affects.

**User says "create a task for Charan" — still a Story:**

- Create with `issue_type: "Story"` and confirm: "Created as **Story** SKRULL-XXXX (SKRULL uses Story for this work item type)."

## Additional resources

- Assignee resolution, version IDs, quarter calendar: [reference.md](reference.md)