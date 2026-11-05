---
name: jira-skrull-tickets
description: >-
  Creates Stories in the SKRULL Jira project on deept.atlassian.net via
  user-jira-server MCP. Accepts assignee, story points, summary, description,
  and optional target date. Always uses issue type Story (never Task). Use when
  the user asks to create, draft, or file a SKRULL ticket or story on the
  SKRULL board.
---

# SKRULL Jira tickets

Create **Story** issues in **SKRULL** on [deept.atlassian.net](https://deept.atlassian.net/jira/software/c/projects/SKRULL/boards/489).

## Configuration

| Setting | Value |
|---------|--------|
| Project key | `SKRULL` |
| Board | [SKRULL board 489](https://deept.atlassian.net/jira/software/c/projects/SKRULL/boards/489) |
| MCP server | `user-jira-server` |
| Browse URL | `https://deept.atlassian.net/browse/{KEY}` |
| Story points field | `customfield_10047` |
| Target Date field | `customfield_10429` |
| Issue type | **`Story` only** (always; never Task) |
| Default assignee | Current user (`jira_current_user`) |
| Default story points | `3` |
| Allowed issue types | **`Story` only** (never create Epics or Tasks) |

## Inputs

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| **Summary** | Yes | — | Issue title |
| **Description** | Yes | — | Plain text or Jira wiki markup |
| **Assignee** | No | **Current user** | Resolve via `jira_current_user` → `emailAddress` |
| **Story points** | No | **3** | Numeric; pass via `custom_fields` |
| **Target date** | No | — | Optional; set Jira **Target Date** field (`customfield_10429`), not description text |

If **summary** or **description** is missing, ask the user before drafting. Apply defaults for assignee and story points when omitted. Parse target date from user input when provided (e.g. `Target Date: August 14, 2026`, `08/14/2026`) and convert to `YYYY-MM-DD` for Jira.

If the user says **Task**, treat it as SKRULL vocabulary only — still create a **Story** and mention that in the confirmation (do not create `issue_type: Task`).

## Workflow

1. **Collect** — summary, description, and optional overrides (assignee, story points, target date).
2. **Apply defaults** — if assignee omitted, call `jira_current_user` and use `emailAddress`; if story points omitted, use **3**; if target date omitted, leave unset. **Issue type is always `Story`.**
3. **Validate type** — reject Epic and any non-Story type on create. Do not offer Task as an option.
4. **Resolve assignee** — if user named someone other than self, see [reference.md](reference.md). Use email on create, not display name.
5. **Draft** — show preview table. Mark default-sourced values in **bold**; user overrides in plain text:

   | Field | Value |
   |-------|-------|
   | Project | SKRULL |
   | Type | **Story** |
   | Summary | … |
   | Assignee | … (resolved email) |
   | Story points | … |
   | Target date | … (or omitted) |
   | Description | … |

   Skip preview only if the user explicitly says to create without review.
6. **Create** — read MCP tool schema, then call `jira_create_issue`:
   - Required: `project_key: "SKRULL"`, `summary`, `issue_type: "Story"`
   - Optional: `description`, `assignee` (email), `custom_fields: { "customfield_10047": N, "customfield_10429": "YYYY-MM-DD" }`
7. **Assignee fix-up** — if assignee email on create does not stick, update with `jira_update_issue` and `assignee: { accountId: "..." }` from `jira_search_users`.
8. **Confirm** — return issue key, browse URL, assignee, story points, target date (if set), and type (**Story**).

## MCP usage

Always read the tool descriptor under `user-jira-server` before calling `CallMcpTool`.

**Create Story (always):**

```json
{
  "server": "user-jira-server",
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

**Default assignee (self):** when assignee is omitted, call `jira_current_user` → use `emailAddress`.

**Verify story points after create:** `jira_get_issue` with `fields: *all` — search results may return `points: null` even when points are set.

## Story points

- SKRULL uses **`customfield_10047`**, not `customfield_10106` (ADINC).
- Pass points on create via `custom_fields`.
- If create succeeds but points are missing, update with `jira_update_issue` and the same field ID.

## Target date

- SKRULL **Target Date** field: **`customfield_10429`** (type `date`).
- Optional input; omit when the user does not provide a target date.
- Accept natural-language dates from the user and normalize to **`YYYY-MM-DD`** before create/update.
- Set via `custom_fields` on create, or `jira_update_issue` after create if needed.
- Do **not** rely on putting target date only in the description — that does not populate the Jira field shown in the issue sidebar.

## Rules

- **Always** set `issue_type` to **`Story`** on create — never Task, even if the user says "task" or "SKRULL task."
- Do not create SKRULL issues without user confirmation unless they explicitly request immediate creation.
- Never log or return API tokens or credentials.
- Never create Epics through this skill (use Jira epic create flow separately when the user asks for an epic).
- If assignee lookup fails, create unassigned only if the user agrees; otherwise ask for `@disney.com` email.
- Do not use display name or `"Last, First X"` as assignee on create — Jira returns "User does not exist."
- After create, link: `https://deept.atlassian.net/browse/{KEY}`

## Examples

**Minimal create (all defaults):**

- Summary + description only
- Type: **Story**, Assignee: **you**, Points: **3**

**Story for Deepthi, 3 points (override assignee):**

- Type: **Story** (only option)
- Summary: `Jira ADINC → Databricks Incident Data Pipeline`
- Assignee: resolve `Deepthi Konda` → email (overrides self default)
- Points: `3` (matches default)

**User says "create a task for Charan" — still a Story:**

- Create with `issue_type: "Story"`
- Summary: `QLIK REPLICATOR | Qlik Replication for UAT`
- Assignee: resolve `Charan Arvapally` → email
- Points: `2` (user override)
- Confirm: "Created as **Story** SKRULL-XXXX (SKRULL uses Story for this work item type)."

## Additional resources

- Assignee resolution and field IDs: [reference.md](reference.md)
