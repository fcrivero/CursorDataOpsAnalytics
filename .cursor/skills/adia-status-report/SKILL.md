---
name: adia-status-report
description: >-
  Generates Ad Infrastructure Analytics (ADIA) Jira status reports for a date
  range or calendar month via user-jira-server MCP. Excludes Epics, includes
  story points and Jira URLs on deept.atlassian.net. Optionally posts to
  Microsoft Teams (default ap-dataenab-linear-devops-priv channel) after user
  confirmation. Use when the user asks for an ADIA status report, Analytics
  Weekly Status Report, or Dawid/Fernando ADIA ticket summary for a period.
---

# ADIA Jira Status Report

Generate a weekly or monthly status report for **Ad Infrastructure Analytics** (`ADIA`) assignees using Jira MCP. Optionally publish to Microsoft Teams.

## Configuration

| Setting | Value |
|---------|--------|
| Project | `ADIA` |
| Jira instance | `https://deept.atlassian.net/` |
| MCP server | `user-jira-server` |
| MCP tool | `jira_search_issues` |
| Browse URL | `https://deept.atlassian.net/browse/{KEY}` |
| Default assignees | `Dawid.Godzic.-ND@disney.com`, `fernando.c.rivero@disney.com` |
| Default Teams channel | [ap-dataenab-linear-devops-priv](https://teams.microsoft.com/l/channel/19%3A9a8a10354e704b85b6bb729535ef84fe%40thread.tacv2/ap-dataenab-linear-devops-priv?groupId=3d4f02b8-61b5-4761-8e3e-38a44e26ffba&tenantId=56b731a8-a2ac-4c32-bf6b-616810e913c6&ngc=true) |

Always read the MCP tool descriptor before calling `CallMcpTool`. Always pass `fields: "*all"` — story points are often null without it.

**Jira host:** All MCP queries and browse links must use **Jira Cloud** at [https://deept.atlassian.net/](https://deept.atlassian.net/). Never use `jira.disney.com`.

## Inputs

Collect from the user message (use defaults when omitted):

1. **Period** — explicit date range (`June 26 to July 2 2026`) or calendar month (`July 2026`). See [reference.md](reference.md) for date parsing.
2. **Assignees** — one or more `@disney.com` emails. Default to Dawid and Fernando when not specified.
3. **Teams channel** — optional override; default is `ap-dataenab-linear-devops-priv` (see [teams-posting.md](teams-posting.md)).
4. **Post to Teams** — one user request runs the **full workflow** end-to-end: Teams check → report → Teams prompt → post if confirmed. No second user message required.

## Workflow (single user input — strict order)

Complete all steps in **one continuous agent run**. The user provides the date range once.

```
Step 0    Teams connectivity (FIRST — before Jira)
Step 1–4  Jira queries → format report
Step 5    WRITE FULL REPORT in chat (user must see every ticket)
Step 6    AskQuestion — post to Teams? (ONLY after Step 5 is visible)
Step 7    Post to Teams OR confirm skipped
Step 8    Brief outcome only (no re-auth instructions)
```

### Step 0 — Microsoft Teams connectivity (mandatory first action)

**Run this immediately when the skill is invoked**, before Jira queries.

1. Run `teams --agent auth status`.
2. If `authenticated` is false and `refreshable` is true, run `teams auth refresh --force`, then `teams --agent auth status` again.
3. Tell the user in one line whether Teams is **ready to post** (`authenticated: true` and `usable: true`) or **not ready**.

**If Teams is not ready to deliver messages**, show the re-authentication steps from [teams-posting.md](teams-posting.md) **Teams auth when not connected** in chat **now** (at the start). Still continue with Steps 1–5 so the user gets the Jira report; Step 6 should note that posting will fail until auth is fixed unless refresh/login succeeds before Step 7.

**Do not** repeat those re-auth steps at the end of the workflow (Step 8).

### Critical rule — report before Teams prompt

**The full report must be written in your assistant message before `AskQuestion` is called.**

- After Step 0, run Jira MCP tools.
- Then **output the complete report** (header, all sections, summary table) in chat.
- **Then** call `AskQuestion` about Teams posting.
- **Never** call `AskQuestion` as the first or only user-visible action (Step 0 status line may precede the report).

### Steps 1–4 — Generate report (Jira)

1. Parse the reporting period into `start_date`, `end_date`, and `period_label` (compact `M/D-M/D` for Teams thread title).
2. Build the assignee list for JQL: `assignee in ("email1", "email2")`.
3. Run **three** Jira searches in parallel (paginate with `start_at` if `total` > `max_results`):

```jql
project = ADIA AND assignee in ({emails}) AND statusCategory = "In Progress" AND status != Blocked AND issuetype != Epic
```

```jql
project = ADIA AND assignee in ({emails}) AND statusCategory = Done AND resolved >= "{start_date}" AND resolved <= "{end_date}" AND issuetype != Epic
```

```jql
project = ADIA AND assignee in ({emails}) AND status = Blocked AND issuetype != Epic
```

4. For each issue: `key`, `summary`, assignee first name, `points` (`null` → **`NO POINTS`**).

### Step 5 — Display report in chat (mandatory before Teams prompt)

Format the complete report (see Output format). Omit empty sections.

**Write the entire report into your chat response** — header, all three sections, and the summary table. The user must see every ticket before anything else appears.

### Step 6 — Ask about Teams posting (after report only)

**Never post to Teams without explicit user confirmation via `AskQuestion`.**
**Never call `AskQuestion` before Step 5 is complete.**

Use `AskQuestion`:

- **Post to default channel** (ap-dataenab-linear-devops-priv) — Recommended
- **Post to a different channel** (user provides URL or name)
- **Do not post** — report stays in chat only

### Step 7 — Post or skip (same run)

**If user confirms posting**, immediately continue — do not stop and wait for another message.

Read [teams-posting.md](teams-posting.md) and the **`teams-cli`** skill, then:

1. Re-check auth — if Step 0 left Teams not ready, retry `teams auth refresh --force` once before posting.
2. **Create thread** — `--subject` only; do **not** duplicate title in `--content`.
3. **First reply** — ASCII-sanitized report body (**ticket sections only**). **Do not** include `CC: Hosamani, Vijaya Kumar Gray, Colin` in this message. **Do not** use `--content-type text` on the reply (default `auto` renders markdown as rich text).
4. **Second reply only** — `CC: Hosamani, Vijaya Kumar Gray, Colin` (this is the **only** place the CC line appears in Teams).
5. Confirm success with thread title and channel name.

**If user declines or cancels**, state that the report remains chat-only.

If `teams` returns `AUTH_FAILED` or `AADSTS53003`, point the user to [teams-posting.md](teams-posting.md) **Teams auth when not connected** — do not append a long PowerShell block at the end of the run.

### Step 8 — Brief closing (no re-auth block)

After Step 7, give a **short** closing only, for example:

- Posted → thread title + channel name.
- Skipped → report is chat-only.
- Failed → one-line error + “fix Teams auth using the steps shown at the start of this run.”

**Do not** show PowerShell re-authentication commands, VPN checklists, or “next week refresh” instructions at the end.

## Section semantics

| Section | Meaning |
|---------|---------|
| **In Progress** | Current snapshot — open tickets in progress now (not Blocked) |
| **Resolved** | Tickets whose **resolved** date falls within the reporting period |
| **Awaiting External Input / Blocked** | Current snapshot — all open Blocked tickets (not limited to period) |

## Output format

### Chat display (full header)

```markdown
**ADIA** (Ad Infrastructure Analytics) — **{Assignee names}** — **{Period label}**
*Epics excluded*

**Resolved** = tickets with **resolved** in that range. **In Progress** / **Blocked** = current workflow status in Jira.

---

## In Progress:

- [ADIA-1234](https://deept.atlassian.net/browse/ADIA-1234) — Ticket summary (Dawid) — **3 points**
```

### Teams post body (first thread reply — no CC)

Use section headers and `---` between non-empty sections. **Never** put the CC line in the Teams body file or first reply. See [teams-posting.md](teams-posting.md).

**Teams uses ASCII separators only** — never em dashes (`—`), en dashes (`–`), arrows (`→`), or other Unicode punctuation. They render as mojibake (`â€"`) in Teams.

### Line rules

**Chat display** (em dash OK):

- **In Progress / Resolved:** `summary (FirstName) — **N points**` or `— **NO POINTS**`
- **Blocked:** `summary (FirstName — Blocked) — **N points**` or `— **NO POINTS**`

**Teams post body** (ASCII hyphen `-` only):

- **In Progress / Resolved:** `summary (FirstName) - **N points**` or `- **NO POINTS**`
- **Blocked:** `summary (FirstName - Blocked) - **N points**` or `- **NO POINTS**`
- Sanitize every Jira summary before Teams output: replace `—`, `–`, `→`, smart quotes, and other non-ASCII punctuation with ASCII equivalents (`-`, `->`, `"`, `'`).
- Replace ASCII double quotes `"` inside summaries with single quotes `'` before posting (embedded `"` breaks the Teams CLI `--content` parser).

Shared rules:

- Sort each section by issue key ascending.
- Singular **point** only when value is exactly 1.

## Rules

- **Strict order:** Step 0 Teams → report in chat → `AskQuestion` → post or skip → brief Step 8 only.
- **Single-input workflow:** if user confirms posting, post in the same run — no second user message.
- **CC once:** CC names appear **only** in the second thread reply, never in the first reply body.
- **Exclude Epics** — `issuetype != Epic` on every JQL query.
- **ADIA only** unless the user explicitly changes the project.
- Never log or return API tokens or credentials.
- Do not invent tickets — only report issues returned by Jira.
- **Never post to Teams without user confirmation.**

## Anti-patterns (do not do these)

- Skipping **Step 0** Teams check before Jira.
- Calling `AskQuestion` **before** the full report is written in chat.
- Including `CC: Hosamani, Vijaya Kumar Gray, Colin` in the **first** Teams reply (duplicates the second CC message).
- Using `--content-type text` on the report body reply.
- Showing PowerShell re-auth / VPN maintenance blocks **after** posting (Step 8).
- Stopping after the user confirms Teams posting — continue and post immediately.
- Skipping `AskQuestion` after showing the report.
- Posting to Teams before the user confirms.
- Asking the user to send another message to trigger posting.

## Additional resources

- Date parsing, JQL patterns: [reference.md](reference.md)
- Teams channel, CC list, CLI commands: [teams-posting.md](teams-posting.md)
