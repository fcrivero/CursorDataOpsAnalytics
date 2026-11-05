---
name: oncall-handoff-incidents
description: >-
  Builds an oncall handoff summary of open and snoozed **High-urgency** PagerDuty
  incidents on Ad Platform Data Ops Service High Urgency (P7OFL7L) and renders
  it as a copy/paste chat message with a table of PD INC# (with URL),
  current status, snoozed-until, MS-Teams-style title, latest note, and
  context/next steps from the Oncall activity log agent and today's transcripts,
  and optionally reassigns those High-urgency incidents to the next oncall after the user confirms via plain-text yes/no (never in the same turn as the handoff). Low-urgency incidents (P3CUKVY) are excluded from the handoff and cannot be reassigned. Use when the user asks to hand off to the next oncall engineer, create an oncall handoff / shift
  handoff message, or summarize open/snoozed/active PagerDuty incidents.
---

# Oncall Handoff — Open & Snoozed Incidents

Produce a ready-to-paste handoff message summarizing every **open (triggered/acknowledged)** and **snoozed** **High-urgency** PagerDuty incident on Ad Platform Data Ops Service High Urgency (`P7OFL7L`), enriched with context from the **Oncall activity log** agent and other same-day transcripts, so the next oncall engineer knows the current state and what's already been decided.

**Low-urgency incidents** (`P3CUKVY`) are **out of scope**: do not list them in the table, detail blocks, Short Teams DM, or reassignment offer.

## Prerequisites

- **PagerDuty MCP** (`user-pagerduty-mcp-manual`) must have a valid API token configured in `mcp.json`. If tools return an auth error or the token placeholder is unset, stop and guide the user through PagerDuty MCP setup — do not fabricate incident data.
- **Oncall activity log** — a session agent (parallel chat) that keeps a running log of follow-ups, agreements, Teams threads, ADINC tickets, and snooze/resolution decisions during the shift. **Always check it** in Step 3 before finalizing context.
- **Agent transcripts** live in `<cursor-projects>/<workspace>/agent-transcripts/<uuid>/<uuid>.jsonl`.

Always call `GetMcpTools` before `CallMcpTool`.

**Incident identity (mandatory for writes):** [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md) — verify each `incident_id` before `manage_incidents`; bulk reassign only uses UUIDs from Step 1 list rows or re-gated fetches.

## Configuration

| Setting | Value |
|---------|-------|
| High-urgency service | Ad Platform Data Ops Service High Urgency — `P7OFL7L` |
| Low-urgency service | Ad Platform Data Ops Service Low Urgency — `P3CUKVY` |
| PD incident URL | `https://disney.pagerduty.com/incidents/{incident_id}` |
| Escalation policy | Data Enablement - Data Operations Escalation Policy — `PWNB722` |
| Primary schedule | Data Enablement - Data Operations Schedule — `PXBA1PX` |
| Timezone | `America/Los_Angeles` (PT) unless the user specifies another |

## Handoff scope — High urgency only

| Service ID | Urgency | In handoff? | Reassignable? |
|------------|---------|-------------|---------------|
| `P7OFL7L` | High | **Yes** | **Yes** (on user confirm) |
| `P3CUKVY` | Low | **No** | **No** |

After Step 1, **filter** to `incident.service.id === "P7OFL7L"` before Steps 2–6. If the filtered list is empty, use the "No open incidents" output (even when Low-urgency incidents remain open).

Optional one-liner in **Handoff notes** when Low-urgency incidents exist: `FYI — {n} Low-urgency incident(s) open on P3CUKVY (not included in handoff).`

## What counts as "open" and "snoozed"

- **Open** = incident `status` is `triggered` or `acknowledged` (never `resolved`).
- **Snoozed** = an `acknowledged` incident with a pending un-acknowledge action, i.e. `get_incident` returns a `pending_actions` entry of type `unacknowledge` with an `at` timestamp. That `at` time is the **Snoozed Until** value.

Both apply only to incidents in **handoff scope** (High urgency).

## Additional inputs (per incident)

Before generating the **final, definitive** handoff, the user provides two extra inputs for each **High-urgency** open/snoozed incident:

1. **MS Teams thread URL** — the canonical discussion thread for that incident.
2. **MS Teams thread summary** — the current human-authored summary of that thread.

Handling:

- Treat the MS Teams thread summary as the **authoritative source of truth** for root cause, current status, ownership, and next steps. It **overrides** the automated PD note and the agent-transcript context when they conflict.
- Fold the MS Teams summary into each incident's **Context & Next Steps** column and **Handoff detail** block, and add the thread URL as a **Thread:** link in the detail block.
- Do **not** produce the final output until these inputs are supplied. If the user runs the skill without them, generate the draft (Steps 1–5) and explicitly ask for the MS Teams thread URL + summary per incident before finalizing.
- Map each provided input to the correct incident by PD#, job/dag name, or thread content.

## Optional input — attached heads-up note

The outgoing oncall may provide an **attached heads-up note** (screenshot, paste, or bullet list) with warnings or guidance for the incoming engineer. Include it **verbatim** in the handoff under a **Heads-up from outgoing oncall** section in the per-incident detail block (or a dedicated section if it applies to multiple incidents). Do not paraphrase or omit bullets from the attachment.

## Workflow

### Step 1 — Fetch open incidents

Query both Data Ops services for non-resolved incidents:

```json
CallMcpTool user-pagerduty-mcp-manual list_incidents
{
  "query_model": {
    "service_ids": ["P7OFL7L", "P3CUKVY"],
    "status": ["triggered", "acknowledged"],
    "request_scope": "all",
    "limit": 1000,
    "sort_by": ["urgency:desc", "created_at:asc"]
  }
}
```

Map urgency from `incident.service.id`: `P7OFL7L` → High, `P3CUKVY` → Low. (Also available on `incident.urgency`.)

**Filter to handoff scope:** keep only rows where `service.id === "P7OFL7L"`. Drop all `P3CUKVY` rows — they are not handed off or reassigned.

If the **filtered** High-urgency list is empty, skip to the "No open incidents" output below.

### Step 2 — Detect snooze + get latest note (per incident)

For each **High-urgency** incident in handoff scope, in parallel where possible:

1. `get_incident` with the incident **`id` from the Step 1 row** (not a PD# from transcripts unless re-gated) → read `pending_actions`. If an entry has `type: "unacknowledge"`, record its `at` value as **Snoozed Until** (convert to PT). Otherwise Snoozed Until = `—`.
2. **Assert** `get_incident` response `id` and `incident_number` match the Step 1 row — if not, skip enrichment for that row and flag mismatch (see [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md)).
3. `list_incident_notes` with the same **verified UUID** → take the most recent note (`content` + author + `created_at`). This is the **Latest Note** = current action being taken. If no notes, use `—`.

Keep Latest Note concise — trim to ~120 chars and collapse newlines; note the timestamp/author only if it adds clarity.

Also build the **MS Teams title** for each incident (see rules below) so the handoff matches what is posted in the MS Teams channels.

### Step 3 — Enrich from Oncall activity log + today's transcripts (mandatory)

For each **High-urgency** open/snoozed incident in handoff scope, gather shift context so the handoff carries forward decisions, root cause, ADINC tickets, **MS Teams thread URLs**, related incidents, snooze agreements, and agreed next steps — not just the raw PD note.

#### 3a — Always check the Oncall activity log agent first

The **Oncall activity log** is a session agent (not a separate skill file) that logs follow-ups, agreements, snooze decisions, and Teams threads during the oncall shift.

1. **Locate today's log transcript.** Grep `agent-transcripts` for:
   - `Oncall log —` or `**Oncall log`
   - `keep a log during the day of my oncall activity`
   - Restrict to **today's date** (check file `LastWriteTime` and message `<timestamp>`).
2. **Read the full log** (or grep within it) for each open/snoozed incident using search keys: PD# (e.g. `5567329`), job/dag name (e.g. `ap_addr_audience_hulu_fandom_inbound_prod`), ADINC ticket, or `teams.microsoft.com`.
3. **Extract per incident:**
   - **Next action** / agreed follow-up
   - **Teams thread URL(s)** — main thread, upstream fix thread, related job threads (labeled by channel when known)
   - **ADINC ticket** and status
   - **Related PD#s** in the same family
   - **Snooze-until** decisions and heads-up notes already logged
   - **Owner / oncall tag** (`@oncall-…`)
4. Treat the Oncall activity log as the **primary context source** for shift decisions — it reflects what the outgoing oncall actually tracked and agreed to.

Cite as `[Oncall activity log]({uuid})` in the handoff detail **Source** line.

#### 3b — Supplement with other same-day agent transcripts

If Step 3a does not cover an incident, or for deeper RCA/DBX analysis:

1. `Grep` `agent-transcripts` for the PD#, PD id, or job name (`files_with_matches`) — **today only**.
2. Read matching discussions from other agents (e.g. `dataops-pd-incident-analysis` sessions).
3. Merge into the handoff; prefer Oncall activity log over other transcripts when they conflict on shift decisions.

#### 3c — Synthesize for handoff

For each incident, produce: consolidated root cause, thread/family membership, tracking ticket, related PD#s, owner, concrete next action, and all relevant Teams links. Prefer Oncall log + MS Teams summary over a single automated PD note.

**Priority when sources conflict:**

1. MS Teams thread summary (user-provided, Step "Additional inputs") — authoritative
2. Oncall activity log — authoritative for shift decisions, snoozes, heads-ups
3. Other agent transcripts / PD automated notes — supplementary

### Step 4 — Render the handoff message

Sort rows: snoozed last, then oldest `created_at` first (all rows are High urgency). Use this exact column order:

| PD# | Status | Snoozed Until | Title | Latest Note | Context & Next Steps |

**Column rules:**

- **PD#** — markdown link `[#{incident_number}](https://disney.pagerduty.com/incidents/{id})`.
- **Status** — capitalized (`Triggered`, `Acknowledged`). Append ` (Snoozed)` when snoozed.
- **Snoozed Until** — PT time `Mon DD, h:mm A PT`, or `—`.
- **Title** — **MS Teams format**: the incident title up to and including the job/dag name, with the monitor suffix stripped. Remove everything from ` on @databricks_job_run_id:…`, ` on env:…`, ` on dag:…`, or ` on …,service:…` onward. Example: `[AP][ODS][Metrics][Fail] ap_addr_ods_metrics_mc_metadata_dq_prod`.
- **Latest Note** — most recent PD note content (trimmed to ~120 chars), or `—`.
- **Context & Next Steps** — one-line synthesis from Step 3 (ADINC ticket + owner + agreed action), or `—`.

### Step 5 — Per-incident handoff detail

Below the table, add a short block per incident that has meaningful context (skip clean ones):

```markdown
**#{number} — {ms_teams_title}**
- **Root cause:** {consolidated cause — MS Teams summary authoritative}
- **Tracking:** {ADINC-xxx / RCA doc} · **Owner:** {@oncall tag / eng}
- **Related:** {other PD#s in the same family, if any}
- **Next step for oncall:** {concrete action — confirm run X SUCCESS, wait until snooze expires, escalate to owner, etc.}
- **Thread:** [MS Teams]({teams_thread_url}) — pull from Oncall activity log when user has not supplied one
- **Source:** [Oncall activity log]({uuid}) · [{other chat title}]({uuid}) if supplemented
```

### Step 6 — Offer to reassign High-urgency incidents to the next oncall

**Two-turn workflow — handoff first, reassignment second:**

1. **Handoff turn (this response):** Complete Steps 1–5 and output the **full handoff message** (table, detail blocks, handoff notes, optional Short Teams DM). End with a **plain-text** reassignment offer (see template below). **Do not** call `AskQuestion` or `manage_incidents` in this turn — tool calls here cause the reassignment UI to appear *above* the handoff text.

2. **Follow-up turn:** Only after the handoff is shown, if the user replies **yes** (or explicitly asks to reassign), call `manage_incidents`. If **no**, acknowledge and stop.

Skip Step 6 entirely when there are **zero** High-urgency incidents in handoff scope.

**Identify the next oncall** before writing the plain-text offer. Query `list_oncalls` on the primary schedule:

```json
CallMcpTool user-pagerduty-mcp-manual list_oncalls
{
  "query_model": {
    "schedule_ids": ["PXBA1PX"],
    "since": "<current_shift_end_or_now_utc>",
    "until": "<+18h_utc>",
    "earliest": false,
    "time_zone": "America/Los_Angeles",
    "limit": 20
  }
}
```

The next oncall = the escalation-level-1 entry on schedule `PXBA1PX` whose `start` is at/after the current shift end. Capture the user `id`, `summary` (full name), and shift `start`/`end`.

**Plain-text reassignment offer** (append after handoff notes — spell the engineer's **full name**):

```markdown
---

**Reassign to next oncall?**
- **Next oncall:** {Full Name} ({user_id}) — {start_pt} → {end_pt} PT
- **Incidents ({n}):** #{a}, #{b}, …

Reply **yes** to reassign all **High-urgency** incidents to {Full Name}, or **no** to leave assignment as-is.
```

**On explicit yes in a follow-up message**, reassign **High-urgency incidents only** in one bulk call. Note the schema field is spelled `assignement`.

**Pre-mutation gate:** `incident_ids` must be UUIDs from Step 1 **filtered to `P7OFL7L` only** (or fresh `get_incident` per PD# with identity gate — reject if `service.id !== P7OFL7L`). State PD#s and count before calling `manage_incidents`. Never paste UUIDs from transcripts without verifying `incident_number`. **Never** include Low-urgency (`P3CUKVY`) incidents in `manage_incidents`.

```json
CallMcpTool user-pagerduty-mcp-manual manage_incidents
{
  "manage_request": {
    "incident_ids": ["<verified_id1>", "<verified_id2>", "…"],
    "assignement": { "id": "<next_oncall_user_id>", "summary": "<Full Name>" }
  }
}
```

4. **Confirm the result** — list which incidents were reassigned to whom (full name), and flag any that failed. Note if status changed to `Triggered` on reassignment (incoming oncall must acknowledge).

**Rules:**

- This is a **write/destructive** action. Never reassign without explicit **yes** from the user in a follow-up message.
- **Low-urgency incidents cannot be reassigned** through this skill — only `P7OFL7L` UUIDs.
- Reassigning a snoozed incident does **not** un-snooze it; the pending un-acknowledge action is preserved.
- Do not change status or urgency during reassignment — assignment only.
- **Never** call `AskQuestion` or `manage_incidents` in the same turn as the handoff output.

## Output template

```markdown
## Oncall Handoff — Open & Snoozed Incidents
**Generated:** {now_pt} PT
**Scope:** Ad Platform Data Ops **High Urgency** (`P7OFL7L`) only

| PD# | Status | Snoozed Until | Title | Latest Note | Context & Next Steps |
|-----|--------|---------------|-------|-------------|----------------------|
| [#12345](…) | Acknowledged (Snoozed) | Jul 23, 8:00 AM PT | [AP][ODS][Metrics][Fail] job_name | Investigating; DQ task rework | ADINC-757 · @oncall-ods-metrics · snoozed pending fix |

### Handoff detail
{per-incident blocks from Step 5}

### Handoff notes
- **Open now (High urgency):** {n} ({t} triggered, {a} acknowledged) — {s} snoozed
- **Needs attention:** {triggered/unacknowledged items, snoozes expiring during the next shift, repairs in flight to verify}
- **FYI (optional):** {low_n} Low-urgency incident(s) on P3CUKVY — not in handoff
- **Next oncall:** {Full Name} — {start_pt} → {end_pt} PT

---

**Reassign to next oncall?**
- **Next oncall:** {Full Name} ({user_id}) — {start_pt} → {end_pt} PT
- **Incidents ({n}):** #{a}, #{b}, …

Reply **yes** to reassign all **High-urgency** incidents to {Full Name}, or **no** to leave assignment as-is.
```

When there are no open incidents, render:

```markdown
## Oncall Handoff — Open & Snoozed Incidents
**Generated:** {now_pt} PT
**Scope:** Ad Platform Data Ops **High Urgency** (`P7OFL7L`) only

No open or snoozed High-urgency incidents. Clean handoff.
{optional: FYI — {low_n} Low-urgency incident(s) still open on P3CUKVY (not handed off).}
```

### Short Teams DM (optional)

When the user wants a copy/paste DM for the next oncall, use this format:

- **Do not** prefix with "from {outgoing oncall name}" — start with a neutral greeting (e.g. `Hi Ashish — oncall handoff.`).
- Include **all relevant MS Teams thread links** for **High-urgency** incidents only (main discussion thread, upstream fix thread, related job threads) as labeled markdown links.
- Do **not** list Low-urgency incidents in the DM.
- Include the **Heads-up from outgoing oncall** bullets verbatim when provided.

## Do not

- Search PagerDuty by service name string — always use service IDs `P7OFL7L` and `P3CUKVY` when fetching; **handoff output** is High urgency (`P7OFL7L`) only.
- Include Low-urgency incidents in the handoff table, detail blocks, Teams DM, or reassignment offer.
- Reassign Low-urgency (`P3CUKVY`) incidents — not supported.
- Include resolved incidents.
- Invent notes, snooze times, incident URLs, ADINC tickets, Teams links, or transcript context — use only MCP results and real transcript content.
- Skip the **Oncall activity log** search in Step 3 — it is mandatory every run.
- Read transcripts from other days when mining context — restrict to the current day.
- Reassign incidents without explicit **yes** from the user in a follow-up message.
- Reassign or mutate PD using UUIDs from transcripts without identity gate — [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md).
- Call `AskQuestion` or `manage_incidents` in the **same turn** as the handoff output — handoff must render first with only plain text at the bottom.
- Guess the next oncall — if `list_oncalls` is ambiguous, ask the user who to assign to.
- Expose PagerDuty API tokens or MCP auth headers in the output.
