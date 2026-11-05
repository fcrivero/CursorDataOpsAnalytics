---
name: dataops-shift-summary
description: >-
  Generates a concise executive Data Ops shift summary for a date or date range
  by cross-checking PagerDuty incidents (Ad Platform Data Ops High/Low Urgency)
  with agent transcripts and optional Jira ADINC tickets. Use when the user asks
  for an oncall executive summary, shift summary for their boss, Data Ops daily
  recap, or end-of-shift report for a given day or time window.
---

# Data Ops Shift Summary (Executive)

Produce a **short, boss-ready** bullet summary of an oncall shift — similar to a Microsoft Teams channel post, not a full incident table.

## Prerequisites

1. **PagerDuty MCP** (`user-pagerduty-mcp-manual`) — token configured in `~/.cursor/mcp.json`. If missing, read `pagerduty-mcp-setup` skill and stop — do not fabricate incidents.
2. **Agent transcripts** — `<workspace>/agent-transcripts/<uuid>/<uuid>.jsonl`. Used to enrich root cause, ADINC tickets, and agreed actions. If unavailable, note it and rely on PD notes only.
3. **Jira MCP** (`user-jira-server`) — optional. Use to confirm ADINC ticket status when transcripts mention a ticket key.

Always call `GetMcpTools` before `CallMcpTool`.

**Incident identity:** [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md) — when enriching a specific PD# from transcripts, gate before `get_incident`; merge transcript context only when `incident_number` matches.

## Configuration

| Setting | Value |
|---------|-------|
| High-urgency service | Ad Platform Data Ops Service High Urgency — `P7OFL7L` |
| Low-urgency service | Ad Platform Data Ops Service Low Urgency — `P3CUKVY` |
| PD incident URL | `https://disney.pagerduty.com/incidents/{incident_id}` |
| Default timezone | `America/Los_Angeles` (PT) |
| Title parsing / teams | Reuse [../dataops-pd-incidents/reference.md](../dataops-pd-incidents/reference.md) |

## Inputs

Parse from the user message (ask if ambiguous):

| Input | Examples | Default |
|-------|----------|---------|
| **Single day** | "Jul 22", "yesterday", "today" | Today 00:00 → now PT |
| **Shift window** | "Jul 22 9:30 AM–3:30 PM PT" | Full day if no times given |
| **Date range** | "Jul 20–22", "last 3 days" | Start/end dates inclusive |
| **Urgency filter** | "high urgency only" | Both High and Low |

Convert window to ISO-8601 UTC for PagerDuty `since` / `until`. Display the header in **PT**.

## Workflow

Copy this checklist and track progress:

```
Shift summary progress:
- [ ] Step 1 — Parse time window
- [ ] Step 2 — Fetch PagerDuty incidents
- [ ] Step 3 — Enrich status (snooze, notes)
- [ ] Step 4 — Mine agent transcripts
- [ ] Step 5 — Cross-check & cluster
- [ ] Step 6 — Render executive summary
```

### Step 1 — Parse time window

Resolve start/end in PT, then convert to UTC for API calls.

Common patterns — see [../dataops-pd-incidents/reference.md](../dataops-pd-incidents/reference.md#time-window-parsing).

For **date ranges**, query the full span in one PD call; group output **per day** only if the user asked for multiple days separately.

### Step 2 — Fetch PagerDuty incidents

```json
CallMcpTool user-pagerduty-mcp-manual list_incidents
{
  "query_model": {
    "service_ids": ["P7OFL7L", "P3CUKVY"],
    "since": "<start_utc_iso>",
    "until": "<end_utc_iso>",
    "request_scope": "all",
    "limit": 1000,
    "sort_by": ["created_at:asc"]
  }
}
```

Urgency filter: High only → `["P7OFL7L"]`; Low only → `["P3CUKVY"]`.

Paginate if >1000 by advancing `since` to the last incident's `created_at`.

Compute counts:

| Bucket | Rule |
|--------|------|
| **Resolved** | `status == resolved` |
| **Open** | `triggered` or `acknowledged` (not snoozed) |
| **Snoozed** | `acknowledged` + `get_incident` → `pending_actions` entry with `type: "unacknowledge"` |
| **Acknowledged/snoozed** (exec line) | Open + snoozed combined for the headline stat |

Extract per incident: PD#, title (MS Teams format — strip monitor suffix), job name, team, status, created_at.

MS Teams title rule: keep text through job/dag name; strip from ` on @databricks_job_run_id:`, ` on env:`, ` on dag:`, or ` on …,service:` onward.

### Step 3 — Enrich status (parallel per open/snoozed incident)

For incidents still open or snoozed at window end (or currently open):

1. `get_incident` using the **`id` from Step 2 list row** → detect snooze (`pending_actions` unacknowledge `at`). Assert returned `incident_number` matches the row — see [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md).
2. `list_incident_notes` with the same verified UUID → latest note (~120 chars) for context if transcripts are thin.

Skip deep DBX analysis — this is an executive summary, not a per-incident RCA. Use `dataops-pd-incident-analysis` only if the user asks to drill into one incident.

### Step 4 — Mine agent transcripts

Search transcripts whose messages fall **inside the shift window** (check JSONL `<timestamp>` fields and file modification time).

For each incident, grep/search keys:

- PD number (e.g. `5559767`, `#5559767`)
- PD UUID
- Job/dag name (e.g. `ap_addr_ods_metrics_mc_metadata_dq_prod`)
- ADINC ticket keys found in discussion (e.g. `ADINC-757`)

Synthesize per cluster:

- Root cause (one line)
- Tracking ticket + owner/oncall tag
- Agreed action (snooze, wait for fix, escalate, false positive)
- Related PD#s in the same family

Prefer transcript consensus over a single automated PD note when they conflict.

Cite source chats as `[short title](uuid)` only in an optional **Sources** footnote — omit from the boss-facing bullets unless the user asks.

### Step 5 — Cross-check & cluster

**Cross-check (mandatory before writing):**

1. Every PD incident in the window appears in your internal tally — no orphans.
2. Transcript-mentioned PD#s either match a fetched incident or are flagged as out-of-window / typo.
3. Cluster counts (~N incidents) sum to ≤ total; overlapping families dedupe by primary job/theme.
4. Open/snoozed at shift end matches PD `get_incident` state, not stale transcript text.
5. Transcript PD#s attach only to list rows where `String(incident_number)` matches — never to a different incident.

**Clustering rules:**

| Priority | Group by |
|----------|----------|
| 1 | Same job/dag name |
| 2 | Same title prefix (`[AP][ODS][Metrics]`, `[AP][ADM][segmentation]`, etc.) |
| 3 | Same ADINC ticket mentioned in transcripts |
| 4 | Dag Change / misc → "Other" bucket |

Label clusters with a **short theme name** + approximate count, e.g. `ODS Metrics MC Metadata DQ (~6)`.

Split output themes:

- **Primary theme** — largest cluster or highest-impact open issue (2+ incidents or still open/snoozed).
- **Resolved / low impact** — false positives, stale duplicates, self-cleared, auto-resolved.
- **Emerging / still open** — new toward end of shift or still acknowledged/snoozed; note owner/routing.

**Customer impact:** default to "No customer-facing service outages" unless PD notes, transcripts, or ADINC tickets explicitly indicate otherwise. Never invent impact.

### Step 6 — Render executive summary

**Tone:** concise, factual, no table. Target **4–6 bullets**, ~80–120 words total. Fewer words than a full handoff.

**Do not** include assignee names, DBX URLs, or long PD note quotes unless the user asks for detail.

Use this template:

```markdown
**Data Ops shift summary — {start_pt}–{end_pt} PT**

- **{total}** PagerDuty incidents — **{resolved}** resolved, **{open_snoozed}** acknowledged/snoozed at shift end. {customer_impact}. {one-line volume driver, e.g. "Mostly recurring Databricks pipeline alerts."}

- **{Primary theme} (~{n})** — `{job_or_pipeline}`{optional: · [ADINC-xxx](https://deept.atlassian.net/browse/ADINC-xxx)}. {one-line root cause + current status}.

- **Resolved / low impact** — {brief grouped list: #PD false positive; #PD stale duplicate; `job` self-cleared; etc.}.

- **{Emerging or open}** — {brief: what failed, how many open, routed to whom}. {Only if something still needs follow-up.}

- **Bottom line** — {one sentence: noise level, prod standing, who to follow up with}.
```

**Formatting rules:**

- Link PD# inline: `[#5559428](https://disney.pagerduty.com/incidents/{id})` — max 2–3 links per bullet; otherwise use counts.
- Link ADINC tickets to `https://deept.atlassian.net/browse/{KEY}`.
- Wrap job/pipeline names in backticks.
- Omit bullets that would be empty (e.g. skip "Emerging" if everything resolved).
- For multi-day ranges, either one combined summary or one header block per day — follow the user's request.

### Optional appendix (only when user asks for detail)

Add after the executive bullets:

- Compact incident list (reuse `dataops-pd-incidents` table format)
- Source transcript links
- Open incidents handoff (reuse `oncall-handoff-incidents`)

## Examples

See [examples.md](examples.md).

**User:** "Executive summary for my oncall shift Jul 22, 9:30 AM–3:30 PM"

→ Window Jul 22 09:30–15:30 PT. Fetch PD + mine that day's transcripts. Render 4–6 bullets.

**User:** "Shift summary for yesterday"

→ Yesterday 00:00–23:59 PT (or user's typical shift if known from context).

**User:** "Recap Jul 20 through Jul 22 for my boss"

→ Combined 3-day summary with per-theme totals; keep under ~150 words unless asked for more.

## Do not

- Fabricate incidents, counts, root causes, ADINC tickets, or customer impact.
- Include resolved incidents in "still open" unless re-opened inside the window.
- Dump the full `dataops-pd-incidents` table in the default executive output.
- Search PagerDuty by service name — always use `P7OFL7L` / `P3CUKVY`.
- Attach transcript context to the wrong PD# — follow [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md).
- Expose PagerDuty API tokens or MCP auth headers.
- Reassign incidents or change PD state — this skill is read-only.
