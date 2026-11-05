---
name: meeting-action-items-report
description: >-
  Show all action items grouped by attendee from Cerebro meeting notes for a
  date or range (today, tomorrow, week, month, custom). Queries pushed meeting
  notes, parses "Action items by attendee" sections, and renders a consolidated
  report. Use when the user asks for action items from meeting notes, my action
  items this week, what did we commit to in meetings, or per-person follow-ups
  from ingested Teams notes.
---

# Meeting Action Items Report (Cerebro)

Consolidate **action items by attendee** from **Cerebro Meeting Notes** for a date or date range.

Works with notes pushed via [meeting-notes-ingest](../meeting-notes-ingest/SKILL.md) (`push_meeting_notes`) or manual pushes.

## Prerequisites

| Tool | Purpose |
|------|---------|
| **Cerebro MCP** (`user-ads-cerebro-qa`) | `search_disney_ad_platform` — primary read path |
| **Teams CLI** (`teams`) | Optional — resolve `teams user me` for "my action items" filter |

Before MCP calls: `GetDynamicTools` → verify Cerebro MCP is available. **VPN required.**

Default timezone: **America/Chicago** (user local).

## Inputs

Parse from the user message (ask if ambiguous):

| Input | Examples | Resolved range |
|-------|----------|----------------|
| **Single day** | `today`, `tomorrow`, `yesterday`, `2026-09-21` | That calendar day (local) |
| **Week** | `this week`, `week` | Monday–Sunday of current week (local) |
| **Last 7 days** | `last 7 days`, `past week` | Today − 6 days through today |
| **Month** | `this month`, `month`, `September` | First–last day of month (local) |
| **Range** | `2026-09-15 to 2026-09-21`, `Sep 15–21` | Inclusive start/end dates |
| **Scope** | `my action items`, `assigned to me` | Filter to current user only |
| **Scope** | `from my meetings` (default) | Meetings where user appears in note attendees/organizer |
| **Attendee filter** | `for Dawid`, `Salman's items` | Single person's section only |

If no date given → **today**.

## Workflow

```
Action items report:
- [ ] Step 1 — Parse date range + filters
- [ ] Step 2 — Resolve current user (if scoped)
- [ ] Step 3 — Fetch meeting notes from Cerebro
- [ ] Step 4 — Parse action items by attendee
- [ ] Step 5 — Aggregate and render report
```

### Step 1 — Parse date range

Convert natural language to inclusive **`start_date`** and **`end_date`** (`YYYY-MM-DD`, local timezone).

Examples (when today = 2026-09-21 Monday):

| Phrase | start_date | end_date |
|--------|------------|----------|
| today | 2026-09-21 | 2026-09-21 |
| tomorrow | 2026-09-22 | 2026-09-22 |
| yesterday | 2026-09-20 | 2026-09-20 |
| week / this week | 2026-09-15 (Mon) | 2026-09-21 (Sun) |
| month / this month | 2026-09-01 | 2026-09-30 |

State the resolved range in the report header.

### Step 2 — Resolve current user (optional)

When user asks for **"my action items"** or **"from my meetings"**:

```bash
teams --agent user me
```

Record `displayName` and `mail` for matching (e.g. `Rivero, Fernando C.` / `Fernando.C.Rivero@disney.com`).

**Name matching:** Compare case-insensitive; match last name, first name, or `attendees` comma-list substring.

### Step 3 — Fetch meeting notes from Cerebro

**Primary query** — one call per day in range (or one range query if single block ≤ 31 days):

```json
CallDynamicTool user-ads-cerebro-qa search_disney_ad_platform
{
  "question": "List all meeting notes dated <YYYY-MM-DD> (or from <start> to <end>) with full content including action items, attendees, meeting title, and meeting time. Include notes tagged daily-ingest or teams-transcript."
}
```

If the range spans multiple days and results are thin, **query each day separately** and merge (dedupe by meeting title + date).

**Fallback queries** (if primary returns empty):

```json
{ "question": "Search meeting notes for <user display name> action items between <start> and <end>" }
```

```json
CallDynamicTool user-ads-cerebro-qa run_skill
{
  "skill_name": "meeting-notes-ingest",
  "input_text": "List meeting notes and action items for dates <start> to <end>"
}
```

If still no results, tell the user explicitly — do not invent action items. Suggest running `/ingest-daily-meeting-notes` for missing days.

### Step 4 — Parse action items by attendee

For each meeting note returned, extract:

| Field | Source |
|-------|--------|
| **Title** | Meeting title / `title` |
| **Date** | `date` or Metadata `Meeting date` |
| **Time** | `## Meeting time` section or Metadata |
| **Cerebro ID** | `mn-*` if present |

**Parse action items** — prefer structured section (new format):

```markdown
## Action items by attendee

### Person Name
- action bullet
```

**Legacy format** (older notes):

```markdown
## Action items
- Person — action bullet
```

**Parsing rules:**

1. Under each `### <Name>` heading, collect `- ` bullets until next heading
2. Legacy: split `- Owner — task` on first ` — ` or ` - ` after owner name
3. Normalize attendee names (trim, collapse whitespace)
4. Merge duplicates only if same meeting + same text; keep distinct meetings separate

**Filter — `from my meetings`:** Include note if current user's name appears in `attendees`, `Participants`, organizer, or action-item owner fields.

**Filter — `my action items` / `assigned to me`:** Include only bullets under the user's heading (fuzzy name match).

**Filter — `for <name>`:** Show only that attendee's section.

### Step 5 — Aggregate and render report

Group all bullets **by attendee** (across meetings). Under each person, subgroup by meeting:

```markdown
# Action items by attendee — <start_date> to <end_date>

**Scope:** <all meetings | my meetings | my action items | filter>
**Meetings found:** <count> | **Total action items:** <count>

---

## <Attendee Name> (<N> items)

### <Meeting Title> — <date> <time if known>
- <action item>
- <action item>

### <Another Meeting> — <date>
- <action item>

---

## <Next Attendee>
...

---

## Team / Unassigned
...
```

**Sort order:**

1. Attendees alphabetically by last name (Team / Unassigned last)
2. Meetings chronologically within each attendee

If zero items: say so and list meetings found without parsed action items.

## Example prompts

- "Show action items by attendee from my meeting notes today"
- "What action items came out of this week's meetings?"
- "My action items for September"
- "Action items assigned to Dawid from meeting notes this month"
- `/meeting-action-items-report tomorrow`

## Limitations

- Read path depends on **Cerebro search** returning pushed notes; indexing may lag minutes
- Notes **without** structured action items (old format or empty transcripts) may show under **Unparsed meetings**
- Shared KB may include other people's meetings — use **from my meetings** to narrow

## Related skills

- [meeting-notes-ingest](../meeting-notes-ingest/SKILL.md) — push daily notes (write path)
- [teams-cli](../teams-cli/SKILL.md) — current user identity
