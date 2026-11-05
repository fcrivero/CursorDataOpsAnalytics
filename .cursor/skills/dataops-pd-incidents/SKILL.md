---
name: dataops-pd-incidents
description: >-
  Lists PagerDuty incidents for Ad Platform Data Ops Service (High and Low
  Urgency) in a time window and renders a table with urgency, PD link, assignee,
  DBX workspace/job/run links (via ads-databricks MCP), team, and MS Teams
  on-call tags. Use when the user asks for Data Ops PD incidents, Ad Platform
  Data Ops incident report, high/low urgency Data Ops pages, or a PagerDuty +
  Databricks incident table for a given window.
---

# Data Ops PagerDuty Incidents (High + Low Urgency)

Produce a markdown table of **Ad Platform Data Ops** incidents (High and Low Urgency) for a user-specified time window, enriched with Databricks workspace and job/run links.

## Prerequisites

1. **PagerDuty MCP** (`user-pagerduty-mcp-manual`) — ensure the API token is configured in `~/.cursor/mcp.json` (`Authorization: Token …`). Stop and guide setup if not configured.
2. **ads-databricks MCP** — required for workspace and DBX links. If unavailable, still render the table with `—` for Workspace and DBX columns and note that enrichment was skipped.

Always call `GetMcpTools` before `CallMcpTool`.

## Configuration

| Setting | Value |
|---------|--------|
| High-urgency service | Ad Platform Data Ops Service High Urgency — `P7OFL7L` |
| Low-urgency service | Ad Platform Data Ops Service Low Urgency — `P3CUKVY` |
| PD incident URL | `https://disney.pagerduty.com/incidents/{incident_id}` |
| Default timezone | `America/Los_Angeles` (PT) unless the user specifies another |

Details: [reference.md](reference.md)

**Incident identity (when user asks about one PD#):** [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md) — run identity gate; never use `?incident_number=` query or `list_incidents[0]`.

## Inputs

Parse from the user message (ask if ambiguous):

| Input | Examples | Default |
|-------|----------|---------|
| **Window start** | "today from 9:30 AM", "since 2026-07-20 09:30" | Start of today 00:00 PT |
| **Window end** | "until now", "through 5 PM" | Now |
| **Relative window** | "last 24 hours", "last 8 hours" | — |
| **Urgency filter** | "high urgency only", "low urgency only" | Both High and Low |

Convert the window to ISO-8601 UTC for PagerDuty `since` / `until`.

Display timestamps in the table in **PT** unless the user requests another timezone.

## Workflow

### Step 1 — Fetch incidents

Query **both** Data Ops services in one call unless the user filtered urgency:

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

Urgency filter overrides:

| User request | `service_ids` |
|--------------|-----------------|
| High only | `["P7OFL7L"]` |
| Low only | `["P3CUKVY"]` |
| Default (both) | `["P7OFL7L", "P3CUKVY"]` |

Set **Urgency** column from `incident.service.id`:

| Service ID | Urgency |
|------------|---------|
| `P7OFL7L` | High |
| `P3CUKVY` | Low |

When the user filters to a **single PD#** (e.g. "show me #5793112 in today's list"), do **not** assume the first `list_incidents` row matches. Either:

1. Filter the list where `String(incident.incident_number) == String(requested_pd#)`, or
2. `get_incident` / `GET /incidents/{pd#}` and run the identity gate from [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md).

If zero or multiple matches, report clearly — do not enrich or link the wrong row.

If more than 1000 incidents, paginate by advancing `since` to the last incident's `created_at`.

### Step 2 — Parse each incident

From `title` / `summary`:

| Field | Extraction |
|-------|------------|
| **Job** | `job_name:(\w+)` or `service:(\w+)` (Datadog long-run/fail monitors) |
| **Run ID** | `@databricks_job_run_id:(\d+)` |
| **Team** | Derive from title — see [reference.md](reference.md#team-and-on-call-tags) |

Assignee: first entry in `assignments[].assignee.summary`, or `—` if empty.

### Step 3 — Enrich DBX workspace and link (when Job is present)

For each unique `(job_name, run_id)` pair:

1. **If run_id present** — call `get_run_details` on `sox-prod-uw2`, then `gen-prod-uw2` until found. Use returned `run_page_url` and `_metadata.workspace`.
2. **If run_id absent** — call `list_jobs` with `name_filter` on `sox-prod-uw2`, then `gen-prod-uw2`. Build job URL from [reference.md](reference.md#databricks-url-templates).

Skip enrichment for non-DBX incidents (e.g. Dag Change).

Batch lookups: dedupe by job name and run ID; do not call MCP once per row when rows share the same job/run.

If ads-databricks is down, set Workspace and DBX link to `—`.

### Step 4 — Render table

Use this column order exactly:

| PD# | Urgency | Status | Assignee | Timestamp | Title | Job | Workspace | DBX Job/Run link | Team | Oncall MS Teams Tag |

**Column rules:**

- **PD#** — incident number only (e.g. `5548281`).
- **Urgency** — `High` or `Low` (from service ID mapping above).
- **Status** — capitalize PagerDuty status (`Triggered`, `Acknowledged`, `Resolved`).
- **Timestamp** — incident `created_at` in PT, format `Mon DD, YYYY h:mm A PT`.
- **Title** — markdown link: `[short title](https://disney.pagerduty.com/incidents/{id})`. Short title = text after `[#NNNN] ` in summary, truncated to ~80 chars if needed.
- **Job** — backtick job name or `—`.
- **Workspace** — e.g. `sox-prod-uw2`, `gen-prod-uw2`, or `—`.
- **DBX Job/Run link** — markdown link: `[Run](url)` if run URL exists, else `[Job](url)`, else `—`.
- **Team** — `ODS`, `ADM`, `BI`, or `TBD` (Dag Change / unmatched — see reference).
- **Oncall MS Teams Tag** — tag(s) from [reference.md](reference.md#team-and-on-call-tags); use `@tag` format, or `—` when Team is `TBD`.

### Step 5 — Summary footer

After the table, add a short summary:

- Total incidents, open vs resolved counts
- Count by Urgency (High / Low)
- Count by Team (ODS / ADM / BI / TBD)
- Count by Workspace (sox-prod-uw2 / gen-prod-uw2 / N/A)
- Note if ads-databricks enrichment was partial or skipped

## Output template

```markdown
## Data Ops Incidents (High + Low Urgency)

**Window:** {start_pt} → {end_pt} (PT)
**Services:** Ad Platform Data Ops Service High Urgency, Ad Platform Data Ops Service Low Urgency

| PD# | Urgency | Status | Assignee | Timestamp | Title | Job | Workspace | DBX Job/Run link | Team | Oncall MS Teams Tag |
|-----|---------|--------|----------|-----------|-------|-----|-----------|------------------|------|---------------------|
| ... | ... | ... | ... | ... | ... | ... | ... | ... | ... | ... |

### Summary
- **Total:** N ({open} open, {resolved} resolved)
- **By urgency:** High: n, Low: n
- **By team:** ODS: n, ADM: n, BI: n, TBD: n
- **By workspace:** sox-prod-uw2: n, gen-prod-uw2: n, N/A: n
```

Sort rows by Timestamp ascending unless the user asks for newest first.

## Examples

**User:** "List Data Ops PD incidents today from 9:30 AM"

→ Window: today 09:30 PT → now. Both urgencies. Full table.

**User:** "High urgency Data Ops PD incidents last 24 hours"

→ Window: now − 24h → now. `service_ids: ["P7OFL7L"]` only.

**User:** "PD incidents for Ad Platform Data Ops last 24 hours"

→ Window: now − 24h → now. Both urgencies. Same table format.

## Do not

- Search PagerDuty by service name string — always use service IDs `P7OFL7L` and/or `P3CUKVY`.
- Match a user-supplied PD# to `list_incidents[0]` or `?incident_number=` — see [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md).
- Invent workspace or run URLs — only use MCP results or job-page fallback from [reference.md](reference.md).
- Set Team to `DataOps` — use `TBD` for Dag Change and unmatched titles.
- Expose PagerDuty API tokens or MCP auth headers in the output.
