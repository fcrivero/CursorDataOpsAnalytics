# PagerDuty Incident Identity Verification — MANDATORY

**Applies to every skill** that fetches, enriches, or mutates a **specific** PagerDuty incident (by PD#, URL, alert URL, or job name). Incidents are identified by **two** fields — do not conflate them:

| Field | Example | Use |
|-------|---------|-----|
| **`incident_number`** (PD#) | `5793112` | User-facing number; safe in notes and links |
| **`id`** (UUID) | `Q1ZG8BRYTFBE4J` | Required for `list_alerts_from_incident`, `manage_incidents`, REST `PUT /incidents/{id}` |

**Never** assume a UUID from chat history, a prior failed lookup, or `list_incidents[0]` matches the user's requested PD#.

---

## Forbidden patterns (caused wrong-incident updates)

| Pattern | Why it fails |
|---------|----------------|
| `GET /incidents?incident_number=5793112` | **Not a valid filter** — API ignores it and returns an unrelated paginated list |
| `list_incidents` → take `incidents[0]` without filtering | First page item is arbitrary |
| Reuse UUID from conversation summary / prior turn | May be from a different incident (e.g. #5620723 vs #5793112) |
| `manage_incidents` with PD# in `incident_ids` | Returns 400 or silent failure — UUID only |
| Mutate after MCP `get_incident` without reading `incident_number` | MCP may return data; agent must still assert match |

---

## Identity gate — run before trusting or mutating

Capture **user intent** at the start:

| User gave | Store as `expected_*` |
|-----------|------------------------|
| PD# (`5793112`, `#5793112`) | `expected_incident_number` |
| Incident URL (`…/incidents/Q1ZG8BRYTFBE4J`) | `expected_uuid` (optional: also PD# if visible) |
| Alert URL | Resolve to incident via alert → incident id, then gate |
| Job/DAG name only | `expected_title_token` (job or DAG substring) — **must** disambiguate if multiple open |

### Step A — Fetch (in order)

1. **PagerDuty MCP** `get_incident` with `incident_id` = PD# or UUID from user input.
2. If MCP read tools are blocked (`full-api` tool group), **REST fallback** (token from `~/.cursor/mcp.json` — never expose in output):
   ```
   GET https://api.pagerduty.com/incidents/{pd_number_or_uuid}
   ```
   Use the **path** segment (`/incidents/5793112`), **not** a query parameter.
3. If user gave job name only: `list_incidents` (scoped to known service IDs) → filter client-side by title → if **≠1** match, **stop and ask** — do not pick the first row.

### Step B — Verify (abort on any failure)

After fetch, **before** alerts, notes, DBX, or writes:

```text
PASS only if ALL applicable checks succeed:

  [PD#]     String(response.incident_number) == String(expected_incident_number)
  [UUID]    response.id == expected_uuid
  [Title]   expected_title_token in response.title  (when user gave job/DAG only)
  [Service] response.service.id in allowed_service_ids  (Data Ops: P7OFL7L, P3CUKVY)
```

On failure:

- **Do not** call `manage_incidents`, `add_note_to_incident`, or REST `PUT`/`POST` on incidents.
- Tell the user: requested identifier, what the API returned (`incident_number`, `id`, title snippet), and that you stopped to avoid touching the wrong ticket.
- Re-fetch with the correct method; never guess.

### Step C — Record verified tuple

Only after PASS, store and use everywhere downstream:

```text
verified_incident_number
verified_uuid          ← ONLY this for list_alerts_from_incident, manage_incidents, REST writes
verified_title
verified_status
```

PD link: `https://disney.pagerduty.com/incidents/{verified_uuid}`

---

## Pre-mutation gate (resolve, note, reassign, snooze)

**Additional** checks immediately before any write:

1. Re-run identity gate **or** confirm stored `verified_uuid` still matches `expected_incident_number` via a fresh `get_incident` / `GET /incidents/{verified_uuid}`.
2. For single-incident actions, state in chat: **PD#**, **title** (truncated), **status** — so the user can catch a mismatch.
3. `manage_incidents.manage_request.incident_ids` — **verified UUID only** (never PD#).
4. `add_note_to_incident.incident_id` — prefer **verified UUID**; if using PD#, re-verify `incident_number` in the response before posting.
5. After write, **confirm**: fetch again and assert `status` (or note count) changed as expected. Empty MCP `[]` response is **not** proof of success.

### REST resolve (when MCP write fails)

```http
PUT https://api.pagerduty.com/incidents/{verified_uuid}
From: {requester_email from GET /users/me}
{"incident": {"type": "incident_reference", "status": "resolved"}}
```

Only after identity gate PASS. Never resolve by UUID that was not verified against the user's PD#.

---

## `list_incidents` bulk fetch (tables, handoffs, shift summaries)

When listing many incidents, each row is already self-consistent (`id` + `incident_number` from the same object). Extra rules:

- Filter by **service IDs** (`P7OFL7L`, `P3CUKVY` for Data Ops) — never by service display name.
- When enriching one row with `get_incident`, use that row's **`id`** — do not substitute a PD# from a transcript without re-gating.
- When merging transcript context by PD#, match `String(incident.incident_number) == String(transcript_pd#)` — never attach transcript notes to a different row.

---

## MCP tool quick reference

| Tool | `incident_id` accepts | Notes |
|------|---------------------|-------|
| `get_incident` | PD# or UUID | Always run identity gate on response |
| `list_alerts_from_incident` | **UUID only** | 404 if PD# passed |
| `list_incident_notes` | UUID preferred | Gate if using PD# |
| `add_note_to_incident` | UUID preferred | Re-verify after |
| `manage_incidents` | **UUID only** in `incident_ids` | Flat schema: `{ "manage_request": { "incident_ids": ["…"], "status": "resolved" } }` |

---

## Regression example (#5793112, Sep 2026)

| Step | Wrong | Correct |
|------|-------|---------|
| Lookup | `?incident_number=5793112` → `#5620723` `Q2NYNST32FMSZM` | `GET /incidents/5793112` → `#5793112` `Q1ZG8BRYTFBE4J` |
| Verify | Skipped — assumed resolved | `incident_number == 5793112` && title contains `ldb_usr_view_agg` |
| User impact | #5793112 stayed Acknowledged; notes may have targeted wrong UUID | Resolved correct incident with closure note |

---

## Skills that MUST follow this reference

- [dataops-pd-long-run](../dataops-pd-long-run/SKILL.md)
- [dataops-pd-incident-analysis](../dataops-pd-incident-analysis/SKILL.md)
- [dataops-pd-incidents](../dataops-pd-incidents/SKILL.md)
- [dataops-shift-summary](../dataops-shift-summary/SKILL.md)
- [oncall-handoff-incidents](../oncall-handoff-incidents/SKILL.md)
- [confluence-adinc-history](../confluence-adinc-history/SKILL.md) (when `PD_ID` present)
