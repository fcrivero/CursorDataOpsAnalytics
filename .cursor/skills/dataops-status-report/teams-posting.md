# Data Operations Status Report — Microsoft Teams posting

Read when the user wants the **Data Operations** section posted to Foundations weekly status. Requires **`teams-cli`** and authenticated `teams` (`teams --agent auth status`).

Auth and channel IDs: [adia-status-report/teams-posting.md](../adia-status-report/teams-posting.md) (Step 0 template, team/channel, ASCII rules).

## Channel (default)

| Setting | Value |
|---------|--------|
| Channel | [Foundations Engineering - Weekly Status](https://teams.microsoft.com/l/channel/19%3Ade9c52b337d443f285a6a0d14ac03f53%40thread.tacv2/Foundations%20Engineering%20-%20Weekly%20Status?groupId=dbe9c893-2d06-4b1c-8179-47e659184434&tenantId=56b731a8-a2ac-4c32-bf6b-616810e913c6) |
| `--team-id` | `dbe9c893-2d06-4b1c-8179-47e659184434` |
| `--channel-id` | `19:de9c52b337d443f285a6a0d14ac03f53@thread.tacv2` |

**Do not** post the HTML report as a lone `channel send` at channel root (no parent thread). **Do not** reply under someone else's weekly prompt unless the user asks.

## Thread root (Step A — parent post)

Creates a **new thread** in the channel. Match the Foundations parent format (date line, then **Fleet** / **Squad**):

```text
{YYYY-MM-DD} WEEKLY REPORT & SUMMARY
Fleet: Data Platform Enablement
Squad: DataOps
```

| Field | Default | Override |
|-------|---------|----------|
| `{YYYY-MM-DD}` | Report anchor date (weekly cutover Wednesday unless user gives a date) | User message |
| **Fleet** | `Data Platform Enablement` | User only |
| **Squad** | `DataOps` | User only |

Post Step A as **HTML** so **Fleet:** and **Squad:** labels render bold (same as peer squad posts):

```html
<p>{YYYY-MM-DD} WEEKLY REPORT &amp; SUMMARY</p>
<p><strong>Fleet:</strong> Data Platform Enablement</p>
<p><strong>Squad:</strong> DataOps</p>
```

Use `--content-type html` on Step A `channel send`. Do **not** append squad name to the date line.

## Report body (first reply only)

- **HTML** section from Step 7 (`<h1>Data Operations</h1>`, workload `<h3>` + `<ul><li><strong>Rubric:</strong>`, Incidents `<table>`, WIP structure). No separate Blockers `<h2>`.
- **`--content-type html`** on the reply.
- **ASCII** punctuation in the HTML file (no em dashes).
- **No CC line** in the HTML body.

Preview/draft: `message send --chat-id 48:notes --content-type html` is fine.

## CC (second reply only)

Post **after** the HTML reply, same thread (`--message-id` = **root** id from Step A):

```text
CC: Hosamani, Vijaya Kumar
```

Vijaya only for Data Operations (not Colin Gray). Optional `@mention` via `teams people search --query "Vijaya Kumar Hosamani"`; plain-text CC is fine on `ACCESS_DENIED`.

## Posting workflow (mandatory for team channel)

Execute **in order** after the user confirms posting. Resolve `<root-message-id>` from Step A (`OriginalArrivalTime`) or `teams channel messages --limit 3`.

### Step A — Create thread (root)

```powershell
$anchor = '2026-11-18'
$root = @"
<p>$anchor WEEKLY REPORT &amp; SUMMARY</p>
<p><strong>Fleet:</strong> Data Platform Enablement</p>
<p><strong>Squad:</strong> DataOps</p>
"@
teams --agent channel send `
  --team-id 'dbe9c893-2d06-4b1c-8179-47e659184434' `
  --channel-id '19:de9c52b337d443f285a6a0d14ac03f53@thread.tacv2' `
  --content $root `
  --content-type html
```

Resolve root `messageId` from the send response (`OriginalArrivalTime`) or `teams channel messages --limit 3`.

### Step B — First reply: HTML report (no CC)

```powershell
$content = Get-Content -Raw -Encoding UTF8 'path\to\data-operations-section.html'
teams --agent channel reply `
  --team-id 'dbe9c893-2d06-4b1c-8179-47e659184434' `
  --channel-id '19:de9c52b337d443f285a6a0d14ac03f53@thread.tacv2' `
  --message-id '<root-message-id>' `
  --content-type html `
  --content $content
```

### Step C — Second reply: CC only

```powershell
teams --agent channel reply `
  --team-id 'dbe9c893-2d06-4b1c-8179-47e659184434' `
  --channel-id '19:de9c52b337d443f285a6a0d14ac03f53@thread.tacv2' `
  --message-id '<root-message-id>' `
  --content 'CC: Hosamani, Vijaya Kumar'
```

## Pre-flight

1. User confirmed post (SKILL Step 8).
2. HTML file has no CC line, no **Sources used** footer.
3. On failure, report error; no retry without user approval.

## Anti-patterns

- Plain-text Step A without bold Fleet/Squad labels.
- Appending `Data Ops` / `DataOps` to the date line instead of **Squad:** on its own line.
- One-shot HTML `channel send` for the full report (skips parent + CC).
- CC inside the HTML body.