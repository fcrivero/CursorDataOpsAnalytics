---
name: jira-adia-tickets
description: >-
  Creates Stories in the ADIA (Ad Infrastructure Analytics) Jira project on
  deept.atlassian.net via user-jira-server MCP. Accepts summary, description,
  optional assignee and story points. Defaults to current user and 3 story
  points. Use when the user asks to create, draft, or file an ADIA story or
  ticket on the ADIA board.
---

# ADIA Jira Stories

Create **Story** issues in **ADIA** (Ad Infrastructure Analytics) on [board 3704](https://deept.atlassian.net/jira/software/c/projects/ADIA/boards/3704).

## Configuration

| Setting | Value |
|---------|--------|
| Project key | `ADIA` |
| Board | [ADIA board 3704](https://deept.atlassian.net/jira/software/c/projects/ADIA/boards/3704) |
| MCP server | `user-jira-server` |
| Browse URL | `https://deept.atlassian.net/browse/{KEY}` |
| Story points field | `customfield_10047` |
| Default issue type | `Story` |
| Default assignee | Current user (`jira_current_user`) |
| Default story points | `3` |
| Allowed issue types | `Story` only (never create Epics or Tasks through this skill) |

## Inputs

| Input | Required | Default | Notes |
|-------|----------|---------|-------|
| **Summary** (title) | Yes | — | Issue title |
| **Description** | Yes | — | Plain text or Jira wiki markup |
| **Assignee** | No | **Current user** | Resolve via `jira_current_user` → `emailAddress` |
| **Story points** | No | **3** | Numeric; pass via `custom_fields` |

If **summary** or **description** is missing, ask the user before creating. Apply defaults for assignee and story points when omitted.

## Workflow

1. **Collect** — summary, description, and optional overrides (assignee, story points).
2. **Apply defaults** — if assignee omitted, call `jira_current_user` and use `emailAddress`; if story points omitted, use **3**.
3. **Validate type** — always `Story`. Reject Epic, Task, and other types unless the user explicitly asks for a different skill.
4. **Resolve assignee** — if user named someone other than self, see [reference.md](reference.md). Use email on create, not display name.
5. **Create immediately** — do not ask for confirmation when summary and description are provided. Read MCP tool schema, then call `jira_create_issue`:
   - Required: `project_key: "ADIA"`, `summary`, `issue_type: "Story"`
   - Optional: `description`, `assignee` (email), `custom_fields: { "customfield_10047": N }`
6. **Confirm** — return issue key, browse URL, assignee, and story points.

## MCP usage

Always read the tool descriptor under `user-jira-server` before calling `CallMcpTool`.

**Create Story (defaults: self, 3 points):**

```json
{
  "server": "user-jira-server",
  "toolName": "jira_create_issue",
  "arguments": {
    "project_key": "ADIA",
    "summary": "Example ADIA story",
    "issue_type": "Story",
    "description": "What needs to be done and acceptance criteria.",
    "assignee": "fernando.c.rivero@disney.com",
    "custom_fields": { "customfield_10047": 3 }
  }
}
```

**Default assignee (self):** when assignee is omitted, call `jira_current_user` → use `emailAddress`.

**Verify story points after create:** `jira_get_issue` with `fields: *all` — search results may return `points: null` even when points are set.

## Story points

- ADIA uses **`customfield_10047`**, not `customfield_10106` (ADINC).
- Pass points on create via `custom_fields`.
- If create succeeds but points are missing, update with `jira_update_issue` and the same field ID.

## Rules

- Create immediately when summary and description are provided — no preview or confirmation step.
- Never log or return API tokens or credentials.
- Never create Epics or Tasks through this skill — Stories only.
- If assignee lookup fails, create unassigned only if the user agrees; otherwise ask for `@disney.com` email.
- Do not use display name or `"Last, First X"` as assignee on create — Jira returns "User does not exist."
- After create, link: `https://deept.atlassian.net/browse/{KEY}`

## Examples

**Minimal create (all defaults):**

- Summary + description only
- Type: **Story**, Assignee: **you**, Points: **3**

**Story for Dawid, 5 points (override assignee and points):**

- Summary: `Add Datadog dashboard for ADIA pipeline latency`
- Description: acceptance criteria and scope
- Assignee: resolve `Dawid Godzic` → email (overrides self default)
- Points: `5`

**Story assigned to self, 2 points (override points only):**

- Summary: `Document ADIA status report skill`
- Assignee: **you** (default)
- Points: `2`

## Additional resources

- Assignee resolution and field IDs: [reference.md](reference.md)
