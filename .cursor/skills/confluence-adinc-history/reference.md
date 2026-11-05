# ADINC → Confluence reference

**RCA source:** [adinc-jira-notes.md](../adinc-jira-notes.md) — General tab → Notes → `customfield_10253`.

## Description fields

Parse each non-empty line as `FIELD: value`. Required fields (exact names):

```text
INC_NUMBER:
TEAM:
PIPELINE:
DAG:
TASK:
SOURCE_SYSTEM:
ISSUE_CATEGORY:
EXTERNAL:
MISSED_SLA:
PD_ID:
```

### Placeholder detection (Step 4)

Flag these in **any** field value (case-insensitive):

- `waiting for rca`
- `tbd`
- blank / whitespace-only value
- `#n/a` as entire value (except where `NA` is valid — see below)

`NA` is **valid** for: `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, `SOURCE_SYSTEM`, `EXTERNAL`, `MISSED_SLA`.

`NA` is **invalid** for: `TEAM`, `ISSUE_CATEGORY` on closed tickets.

---

## Page title format

```text
YYYYMMDD-{INC|ADINC}-{ID}-[{AP}][Team][SubTeam/Pipeline]{DAG}- {short description}
```

### Examples

```text
20260708-INC29281148-[AP][ODS][Metrics] Pacing % metric underreported for line items with non‑midnight start times
20260711-ADINC-778-[AP][ODS][Metrics] Multiple jobs failure - Databricks Outage
20260719-ADINC-791-[AP][ADM][Targeting] ap_addr_audience_compliance_manager_ccpa_user_brands_exposure_espn_prod - Failed due to timeout
```

### Construction rules

| Segment | Source |
|---------|--------|
| `YYYYMMDD` | Ticket `created` date (or user override) |
| `INC29281148` | From `INC_NUMBER` when not `NA` |
| `ADINC-778` | From ticket key when `INC_NUMBER` is `NA` |
| `[AP][Team][SubTeam]` | From Jira summary prefix |
| Optional 4th bracket | e.g. `[Long Run]` from summary |
| DAG segment | From summary after brackets (when present) |
| `- {description}` | Remainder of summary after DAG segment |

---

## Confluence hierarchy

```text
Incident History (192843672)
└── YYYYMM (e.g. 202607 → 192843692)
    └── YYYYMMDD-ADINC-... (incident page)
```

| Resource | ID / URL |
|----------|----------|
| Root | https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192843672/Incident+History |
| Space key | `ADSO` |

---

## Confluence page template

Use **storage** HTML (Confluence editor format). Section headings use teal: `<span style="color: rgb(0,128,128);">`.

### Section order

1. **Summary** — metadata table
2. **Problem details**
3. **Root Cause Analysis Summary**
4. **Investigation & Findings** (Initial Findings → Troubleshooting → Root Cause details)
5. **Resolution**
6. **Actions**

### Summary table fields

| Row label | Typical source |
|-----------|----------------|
| Pipeline | `PIPELINE` |
| Dag/Job | `DAG` or job name from summary |
| Problem Statement | One line from summary or Notes |
| SLA Impacted | `MISSED_SLA` → `Y` / `N` / `NA` |
| Teams Involved | `TEAM` + any PD assignee team |
| Incident Reported | EST time from `created` or PD `created_at` |
| Incident ID(s) | `INC_NUMBER` or external ref |
| Jira ID(s) | Link to `https://deept.atlassian.net/browse/{KEY}` |
| Teams Thread(s) | User-provided link or `—` |
| External References | PD link, vendor tickets, PR links |

### Minimal storage HTML skeleton

Adapt from a sibling page in the same month when possible. Skeleton:

```html
<h2><strong><span style="color: rgb(0,128,128);">Summary</span></strong></h2>
<table data-table-width="760" data-layout="default">
<colgroup><col style="width: 114.6px;" /><col style="width: 197.94px;" /></colgroup>
<tbody>
<tr><td><p>Pipeline</p></td><td><p>{PIPELINE}</p></td></tr>
<tr><td><p>Dag/Job</p></td><td><p>{DAG}</p></td></tr>
<tr><td><p>Problem Statement</p></td><td><p>{problem_statement}</p></td></tr>
<tr><td><p>SLA Impacted</p></td><td><p>{MISSED_SLA}</p></td></tr>
<tr><td><p>Teams Involved</p></td><td><p>{TEAM}</p></td></tr>
<tr><td><p>Incident Reported</p></td><td><p>{incident_reported_time}</p></td></tr>
<tr><td><p>Incident ID(s)</p></td><td><p>{INC_NUMBER or link}</p></td></tr>
<tr><td><p>Jira ID(s)</p></td><td><p><a href="https://deept.atlassian.net/browse/{KEY}">{KEY}</a></p></td></tr>
<tr><td><p>Teams Thread(s)</p></td><td><p>{teams_link or —}</p></td></tr>
<tr><td><p>External References:</p></td><td><p>{external_refs}</p></td></tr>
</tbody>
</table>

<h2><strong><span style="color: rgb(0,128,128);">Problem details:</span></strong></h2>
<p>{impact, scope, examples}</p>

<h2><strong><span style="color: rgb(0,128,128);">Root Cause Analysis Summary</span></strong></h2>
<h2>Investigation &amp; Findings</h2>
<ol>
<li><p><strong>Initial Findings:</strong></p><ul><li><p>{finding}</p></li></ul></li>
<li><p><strong>Trouble shooting:</strong></p><ul><li><p>{steps}</p></li></ul></li>
<li><p><strong>Root Cause details:</strong></p><ol><li><p>{root_cause_from_notes}</p></li></ol></li>
</ol>

<h2><strong><span style="color: rgb(0,128,128);">Resolution:</span></strong></h2>
<p>{resolution}</p>

<h2><strong><span style="color: rgb(0,128,128);">Actions:</span></strong></h2>
<p>{follow_up_actions or "No follow-up action needed."}</p>
```

### Content mapping from Jira Notes

| Notes pattern | Confluence section |
|---------------|-------------------|
| Full RCA paragraph | Root Cause Analysis Summary + Root Cause details |
| "auto-recovered", "retry" | Resolution |
| "no follow-up", "monitoring" | Actions |
| CHANGE ticket / PR in Notes | Resolution + Actions |

Keep **Jira Notes** concise in spirit; Confluence holds the expanded write-up.

---

## PagerDuty quick reference

When `PD_ID: 5494320` (or `#5494320`, or linked `[5494320|url]`):

1. `get_incident` with numeric id
2. `list_incident_notes` with UUID from step 1
3. Parse `[Incident agent — automated summary]` for Investigation sections

PD link: `https://disney.pagerduty.com/incidents/{uuid}`

Do not use `incident_number` where UUID is required (`list_alerts_from_incident`, `list_incident_notes`).

---

## Cross-agent enrichment

Mandatory before Confluence page create (Step 5). See [SKILL.md](SKILL.md#step-5--cross-agent-enrichment-mandatory).

| Source | Search pattern | Confluence fields |
|--------|----------------|-------------------|
| Oncall activity log | `ADINC-{n}`, DAG, `teams.microsoft.com` in session transcripts | Teams Thread(s) |
| Jira comments | `jira_get_comments` → `teams.microsoft.com` | Teams Thread(s) |
| dataops-pd-incident-analysis | `PD_ID` + PD MCP + DBX MCP | Investigation, External References |
| dataops-pd-incidents | PD list for incident date window, match DAG in title | PD link, DBX URLs |

**Priority for Teams Thread(s):** Oncall log primary thread → Jira auto-posted comment links → PD agent notes.

---

## Duplicate page detection

**Problem:** The same ADINC ticket can get multiple pages with different date prefixes (`20260722` vs `20260723`) or in different monthly folders.

**Solution:** Step 6b CQL search across all descendants of Incident History (`ancestor = 192843672`).

| Ticket type | CQL title token |
|-------------|-----------------|
| ADINC | `title ~ "ADINC-798"` |
| ServiceNow INC | `title ~ "INC29281148"` |

Example — ADINC-798 returned **two** pages before this check existed:

| Title | Author |
|-------|--------|
| `20260722 - ADINC-798 - [AP][ADM][Measurement][Fail] fact_ad_delivery_snowflake_write task has failed` | Tulasi Agina |
| `20260723-ADINC-798-[AP][ADM][Measurement] ap_addr_measurement_adlog_all_publishers_prod - missing D+ data...` | Fernando Rivero |

When matches exist → **update** the user-chosen primary page; do **not** create another.

---

## Example invocations

```text
@confluence-adinc-history document ADINC-791
@confluence-adinc-history publish RCA for ADINC-778 to Confluence
@confluence-adinc-history create Incident History page for ADINC-765
```
