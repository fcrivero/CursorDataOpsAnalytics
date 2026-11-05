---
name: meeting-notes-ingest
description: >-
  Ingest daily Microsoft Teams meeting transcripts into the Cerebro Meeting Notes
  knowledge base. Lists the user's calendar for a date, finds meetings with
  recordings and transcripts, summarizes decisions and action items, and pushes
  via Cerebro MCP push_meeting_notes. Use when the user asks to push daily meeting
  notes, ingest Teams transcripts to Cerebro, sync meeting notes to the knowledge
  base, or run end-of-day meeting capture.
---

# Meeting Notes Ingest (Teams → Cerebro KB)

Push **daily meeting notes** from **Microsoft Teams meetings the user attended** where a **recording and transcript** are available.

## Prerequisites

| Tool | Purpose |
|------|---------|
| **Teams CLI** (`teams`) | Calendar, recordings, transcripts — see [teams-cli](../teams-cli/SKILL.md) |
| **Cerebro MCP** (`user-ads-cerebro-qa`) | `push_meeting_notes` — requires VPN |
| **Optional:** Cerebro `run_skill` | Server-side `meeting-notes-ingest` skill as fallback |

Before MCP calls: `GetDynamicTools` → verify `push_meeting_notes` is available.

**Auth:** Teams CLI uses the user's Microsoft session. Cerebro MCP requires VPN to `ads-cerebro-qa`.

## Inputs

Parse from the user message (ask if ambiguous):

| Input | Examples | Default |
|-------|----------|---------|
| **Date** | "today", "yesterday", "2026-09-21" | Today (local date) |
| **Dry run** | "preview only", "don't push" | Push to KB |
| **Single meeting** | "only ADINC Dashboard" | All eligible meetings that day |

Default timezone for display: **America/Chicago** (user local). Teams API times are UTC.

## What counts as eligible

Include a meeting when **all** of the following are true:

1. Appears on the user's calendar (`teams meeting list`) for the target date
2. `isOnlineMeeting` is true (skip focus blocks, OOO all-day, in-person-only)
3. Has a `threadId`
4. `meeting recordings --thread-id <threadId> --meeting-date <YYYY-MM-DD>` returns ≥1 recording
5. `meeting transcript --recording-id <recordingId>` returns transcript entries (non-empty)

**"Present" proxy:** Calendar events on the user's mailbox imply they were invited/scheduled. If the user says they did not attend a meeting, skip it. Do not ingest meetings the user explicitly excludes.

**Not Copilot recap:** This skill uses **VTT/speech transcripts** from Teams recordings, not the separate Copilot recap UI. If only `recapUrl` exists but transcript fails, report as "recording, no transcript yet" and skip push.

## Workflow

Copy this checklist and track progress:

```
Meeting notes ingest:
- [ ] Step 1 — Resolve date and user
- [ ] Step 2 — List calendar meetings + meeting get (time, invitees)
- [ ] Step 3 — Find recordings + transcripts
- [ ] Step 4 — Summarize (time, action items by attendee, participants)
- [ ] Step 5 — Push to Cerebro KB (unless dry run)
- [ ] Step 6 — Report results
```

### Step 1 — Resolve date and user

```bash
teams --agent user me
```

Note the user's `mail` / display name for the report footer.

Date for Teams list:

```bash
teams --agent meeting list --start-date <YYYY-MM-DD> --days 1
```

### Step 2 — List calendar meetings + fetch details

From `meeting list` JSON, keep rows where:

- `isOnlineMeeting` is true
- `threadId` is present
- Subject is not empty

Record from list: `id`, `subject`, `threadId`, `start.dateTime`, `end.dateTime`, `organizer.emailAddress.name`.

**Fetch full event details** (invitees + local timezone):

```bash
teams --agent meeting get <event-id>
```

From `meeting get`, also record:

- `start.dateTime`, `end.dateTime` (UTC)
- `originalStartTimeZone`, `originalEndTimeZone` (prefer for display, e.g. `Pacific Standard Time`)
- `attendees[].emailAddress.name` and `attendees[].type` (`required` / `optional`)
- `organizer.emailAddress.name`

**Convert meeting time for notes:** Display scheduled start–end in the organizer's/original timezone **and** UTC. Example: `2026-09-21 09:00–09:30 AM PST (16:00–16:30 UTC)`.

If user named one meeting, filter by subject (case-insensitive contains).

### Step 3 — Find recordings and transcripts

For each candidate meeting:

```bash
teams --agent meeting recordings --thread-id "<threadId>" --meeting-date <YYYY-MM-DD>
```

For each `recordingId` in the response (prefer the longest / most recent if multiple):

```bash
teams --agent meeting transcript --recording-id "<recordingId>"
```

If `data.entries` is empty or command fails → mark **skipped (no transcript)**.

If multiple recordings in one meeting (stop/resume), ingest **one note per recording** OR merge into a single note — prefer **one note per meeting** by concatenating entries in time order.

### Step 4 — Summarize each meeting

From transcript `entries` and calendar details, produce markdown.

**Attendee sources (merge, dedupe by name):**

1. **Transcript speakers** — unique `speaker` values from `entries`, or `data.speakers` if present
2. **Action-item owners** — names explicitly assigned in decisions/agreements (e.g. "Fernando will…", "Dawid — update…")
3. **Calendar invitees** (optional reference) — from `meeting get` `attendees[]`; list separately, do not treat as "present" unless they spoke

**Action items by attendee (required section):**

- Parse every action item from the transcript or user-provided notes
- Group under `### <Person name>` headings (use first name + surname as spoken in transcript when possible)
- Use `### Team / Unassigned` for items with no clear owner
- Each bullet: `- <action>`

**Matching owners:** Map informal names in transcript ("Fernando", "Dawid", "Salman") to full speaker/invitee names when confident; if ambiguous, use the spoken form and add `(owner TBD)` rather than guessing.

```markdown
## Summary
[2–4 sentences]

## Meeting time
<scheduled start–end in local TZ> (<UTC equivalent>)
Recording: <recordingStartTime> – <recordingEndTime> UTC

## Decisions
- ...

## Action items by attendee

### <Person A>
- <action>

### <Person B>
- <action>

### Team / Unassigned
- <action if any>

## Key discussion points
- ...

## Participants

### Spoke in meeting (transcript)
- <speaker names>

### Mentioned in action items (did not speak)
- <names only referenced as owners>

### Calendar invitees (reference)
- <required invitees>
- Optional: <optional invitees>

## Metadata
- Meeting date: YYYY-MM-DD
- Organizer: <name>
- Thread ID: <threadId>
- Recap URL: <recapUrl if available>
- Generated by: meeting-notes-ingest skill (Teams transcript)
```

Keep summaries factual — only include decisions/actions explicitly stated in the transcript or user-provided notes.

### Step 5 — Push to Cerebro KB

Unless dry run, for each summarized meeting:

```json
CallDynamicTool user-ads-cerebro-qa push_meeting_notes
{
  "title": "<meeting subject>",
  "content": "<markdown from Step 4 — must include Meeting time + Action items by attendee>",
  "date": "<YYYY-MM-DD from scheduled start>",
  "attendees": "<comma-separated: transcript speakers + action-item owners, deduped>",
  "tags": "teams-transcript,daily-ingest,<slug-from-subject>"
}
```

**`attendees` field rule:** Include everyone who **spoke** OR **owns an action item**. Do not list all calendar invitees in this field unless they also spoke or have an assigned action. Full invitee list stays in the `Calendar invitees` section of `content`.

**Manual ingest:** When the user provides notes (no transcript), still produce `Meeting time`, `Action items by attendee`, and `attendees` from the text they supply.

**Dedup:** If the user asks to avoid duplicates, search first:

```json
CallDynamicTool user-ads-cerebro-qa search_disney_ad_platform
{ "question": "meeting notes <subject> <YYYY-MM-DD>" }
```

Skip push if the same title+date already exists unless the user says "force" or "re-ingest".

**Alternative:** If `push_meeting_notes` fails, try:

```json
CallDynamicTool user-ads-cerebro-qa run_skill
{
  "skill_name": "meeting-notes-ingest",
  "input_text": "Ingest meeting notes for <subject> on <date>:\n\n<markdown>"
}
```

### Step 6 — Report results

Return a table:

| Meeting | Recording | Transcript | Cerebro ID | Status |
|---------|-----------|------------|------------|--------|
| SKRULL DSU | Yes | Yes | mn-xxx | Pushed |
| DataOps Incident Review | No | — | — | Skipped (no recording) |

Include counts: **pushed**, **skipped**, **failed**.

If dry run, show summaries without calling `push_meeting_notes`.

## Example user prompts

- "Push today's meeting notes to Cerebro"
- "Ingest yesterday's Teams transcripts into the knowledge base"
- "Daily meeting notes ingest — preview only"
- "Push meeting notes for ADINC Dashboard from today"

## Safety

- **Shared KB:** Notes pushed via `push_meeting_notes` go to the **team** Meeting Notes knowledge base. Do not ingest confidential or HR-sensitive content unless the user confirms.
- **VPN:** Cerebro MCP fails without VPN — report clearly, do not fabricate success.
- **No recording / no transcript:** Skip and report; do not invent meeting content.

## Related skills

- [teams-cli](../teams-cli/SKILL.md) — meeting list, recordings, transcript commands
- [teams](../teams/SKILL.md) — MCP-based Teams access (alternative path)
