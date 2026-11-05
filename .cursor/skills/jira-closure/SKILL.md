---
name: jira-closure
description: >-
  Generates closure notes from a Jira ticket (description, comments, closure
  date) and optionally posts them to Microsoft Teams. Use when the user asks
  for closure notes, ticket closure summary, post closure to Teams, or provides
  a Jira key/URL and wants a shareable wrap-up message.
---

# Jira Closure Notes → Microsoft Teams

Generate a concise **closure note** from a Jira ticket, show it to the user, then optionally post it to Microsoft Teams.

**Read workflow:** fetches Jira data and may post to Teams. Does **not** transition, edit, or close Jira tickets unless the user explicitly asks separately.

Companion skills: `jira-ticket`, `teams-cli`.

## Configuration

| Setting | Value |
|---------|--------|
| Jira MCP | `user-jira-server` |
| Teams CLI | `teams --agent` (see `teams-cli` skill) |
| Default Jira host | `https://deept.atlassian.net` (browse links) |

Always call `GetMcpTools` before `CallMcpTool`.

## Input

Accept **one** issue identifier:

| Form | Example |
|------|---------|
| Full key | `ADINC-791`, `SLQA-100` |
| Key only | `791` (use project from URL if present; otherwise ask) |
| Browse URL | `https://deept.atlassian.net/browse/ADINC-791` |

Normalize to `PROJECT-{number}`. Extract project from URL path when the user gives only a number.

## Workflow overview

```
Parse issue key
  → Fetch issue + comments + changelog
  → Derive closure date
  → Synthesize closure notes
  → Show notes to user
  → AskQuestion: post to Teams?
  → If yes: resolve channel or thread URL → post → confirm
```

Copy this checklist and track progress:

```
- [ ] Step 1: Parse and normalize issue key
- [ ] Step 2: Fetch Jira issue
- [ ] Step 3: Fetch comments
- [ ] Step 4: Derive closure date from changelog
- [ ] Step 5: Synthesize closure notes
- [ ] Step 6: Present notes to user
- [ ] Step 7: Ask to post to Teams
- [ ] Step 8: Resolve destination and post (if approved)
```

---

### Step 1 — Parse issue key

Extract `PROJECT-NUMBER` from the user message. If only a number is given and no project context exists, ask once for the project key.

Build browse URL: `https://deept.atlassian.net/browse/{KEY}` (adjust host if the user's URL used a different Jira instance).

---

### Step 2 — Fetch Jira issue

```json
CallMcpTool user-jira-server jira_get_issue
{
  "issue_key": "ADINC-791",
  "fields": "summary,status,description,resolution,resolutiondate,created,updated,assignee,reporter"
}
```

If `description` is empty, note that in the closure notes — do not invent content.

---

### Step 3 — Fetch comments

```json
CallMcpTool user-jira-server jira_get_comments
{
  "issue_key": "ADINC-791"
}
```

Use comments for **closure context** — resolution steps, RCA snippets, handoff notes, links. Prefer the **most recent substantive comments** (skip empty, bot-only, or duplicate auto-posts when a clearer comment exists).

Do **not** treat comments as a substitute for a missing description; synthesize from what is present.

---

### Step 4 — Derive closure date

Fetch changelog:

```json
CallMcpTool user-jira-server jira_get_issue_changelog
{
  "issue_key": "ADINC-791",
  "max_results": 100
}
```

**Closure date priority:**

1. **Status transition** — earliest or latest transition to a terminal status? Use the **most recent** transition where `field = status` and `toString` matches (case-insensitive):
   - `Done`, `Closed`, `Resolved`, `Accepted`
2. **`resolutiondate`** — from Step 2 issue fields, if set.
3. **`updated`** — last resort; label as "last updated" not "closed" in the note.

Format for display: `YYYY-MM-DD HH:mm` in **America/Los_Angeles** (PT) unless the user specifies another timezone.

If the ticket is **not** in a terminal status, still generate notes but flag: **Status: {current} — not yet closed.** Use the best available date with a clear label.

---

### Step 5 — Synthesize closure notes

Build closure notes using the template in [reference.md](reference.md#closure-note-template). Rules:

- **Lead with** ticket key as a **linked** `[KEY](browse_url)` plus summary on line 1.
- **Description** — one or two sentences max; preserve critical identifiers (DAG, pipeline, INC#, PD#) verbatim.
- **Comments** — distill resolution/action items only; attribute by author when helpful.
- **Closure date** — from Step 4 with source label (`Closed`, `Accepted`, or `Last updated`).
- **Keep it short** — aim for **under 20 lines**. Bullet lists over paragraphs.
- **Skip Rationale / Justification** — do not copy or summarize "Rationale", "Justification", or similar sections from the Jira description; state only what changed or was decided.
- **No redundant Jira link** — do not add a **Links** section for the Jira ticket; line 1 is enough. Only add **Links** for other URLs (PD, Confluence, etc.).
- **Never fabricate** root cause, resolution, or dates not supported by Jira data.
- If data is thin, say so briefly — do not pad.

---

### Step 6 — Present notes to user

**Mandatory order:** show the full closure note in chat **first** and **wait for the user to read it** before Step 7. Never call `AskQuestion` or ask about Teams in the same turn as fetching Jira data — finish synthesis and display the note in one response, then ask about Teams in a **separate** follow-up (next turn or after the note is fully rendered).

Show the full closure note inside a fenced markdown block so the user can copy it. Include a one-line metadata header:

```markdown
## Closure notes — ADINC-791

**Status:** Done · **Closure date:** 2026-07-23 14:32 PT · [Open in Jira](https://deept.atlassian.net/browse/ADINC-791)

(copyable note below)
```

End Step 6 with the copyable note only — **no** Teams question yet.

---

### Step 7 — Ask to post to Teams

**Only after Step 6 is complete** (closure message already shown), call **`AskQuestion`** or ask in chat:

```json
{
  "title": "ADINC-791 — Post closure notes to Teams?",
  "questions": [{
    "id": "post-teams",
    "prompt": "Post these closure notes to Microsoft Teams?",
    "options": [
      { "id": "yes", "label": "Yes — I'll provide the channel or thread URL" },
      { "id": "no", "label": "No — notes only (Recommended if unsure of destination)" }
    ]
  }]
}
```

| Answer | Action |
|--------|--------|
| **No** | STOP — user has the notes in chat |
| **Yes** | Continue to Step 8 — ask for destination |

When the user selects **Yes**, ask them to provide **one** of:

1. **Channel** — team name + channel name (e.g. `Growth Life Orchestrator / general`)
2. **Thread URL** — a Teams message deep link (`https://teams.microsoft.com/l/message/...`)

Do not post until the destination is confirmed.

---

### Step 8 — Resolve destination and post

#### 8a — Resolve channel (team + channel name)

```bash
teams --agent channel teams --filter "<team name substring>"
teams --agent search channels --query "<channel name>"
```

Pick the best match; if ambiguous, ask the user to choose before sending.

Send a **new top-level channel message**:

```bash
teams --agent channel send \
  --team-id "<team-id>" \
  --channel-id "<channel-id>" \
  --content "<closure note markdown>"
```

Markdown renders as rich text by default (`--content-type auto`).

#### 8b — Post to an existing thread (URL)

Parse the URL from the user.

**Channel thread** — extract team-id, channel-id, and message-id from the URL or use:

```bash
teams --agent channel reply \
  --team-id "<team-id>" \
  --channel-id "<channel-id>" \
  --message-id "<root-message-id>" \
  --content "<closure note markdown>"
```

**Chat thread** — when the URL is a chat (not a team channel):

```bash
teams --agent message send \
  --from-url "<teams message url>" \
  --content "<closure note markdown>"
```

For reply-in-thread on chats, use `message list --from-url` to get `chat-id` and parent `message-id`, then send with appropriate threading if the CLI supports it; otherwise post to the chat with a quoted first line referencing the thread topic.

If `teams auth status` fails, tell the user to run `teams auth login` and retry.

#### 8c — Confirm

After a successful send, report:

```markdown
## Posted to Teams

| Item | Detail |
|------|--------|
| Jira | [ADINC-791](https://deept.atlassian.net/browse/ADINC-791) |
| Destination | {team / channel name or "thread reply"} |
| Posted | {timestamp PT} |
```

If send fails, show the CLI error and leave the notes in chat for manual paste.

---

## Do not

- Close, transition, or edit the Jira ticket unless explicitly asked (use `jira-ticket` for that).
- Post to Teams without user approval (Step 7) and a confirmed destination.
- Invent RCA, resolution, or closure dates not in Jira.
- Skip showing the notes before asking about Teams.
- Use the generic AIX `jira` CLI when Jira MCP is available (`aix-mcp-overrides`).

## Additional resources

- Closure note template and examples: [reference.md](reference.md)
