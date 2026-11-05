# ADINC Jira dates — canonical semantics

All ADINC skills and agents **must** use this model for incident timing. Do **not** treat Jira **Created** as ServiceNow **opened** for migrated tickets.

| Property | Value |
|----------|--------|
| Jira UI | **Key details → Dates** tab |
| MCP / REST | Request custom fields explicitly (MCP `jira_get_issue` often omits them unless listed in `fields`) |
| Instance | `https://deept.atlassian.net` (project `ADINC`) |
| Lifecycle doc | [ADINC Ticket Lifecycle](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192839878/ADINC+Ticket+Lifecycle) |

## Field reference

| Jira UI field | Custom field ID | JQL |
|---------------|-----------------|-----|
| **Start DatePick** | `customfield_10489` | `cf[10489]` |
| **Completion Date** | `customfield_10566` | `cf[10566]` |
| **End Date** | `customfield_10453` | `cf[10453]` |
| **Created** (system) | `created` | `created` |

## Start DatePick — dual meaning (migration-aware)

| Ticket cohort | How to detect | **Start DatePick** means |
|---------------|---------------|---------------------------|
| **ServiceNow import** | Jira **`created` date ≤ 2026-05-30** (bulk migration; often `2026-05-30` with clustered timestamps) | **ServiceNow incident opened / created** (mapped at import) |
| **Native ADINC** | Jira **`created` date ≥ 2026-05-31** (Support Bot / manual create after migration) | **Date the DEV team started working** on the incident — **not** when the Jira ticket was created |

For migrated tickets, **Start DatePick** is the source of truth for **original SNOW open date**. Jira **Created** on those rows is usually the **Jira import time**, not the incident open time.

For new tickets, set **Start DatePick** when engineering begins triage/fix work (may be later than ticket creation).

## Completion Date vs End Date (workflow)

| Field | When to set | Meaning |
|-------|-------------|---------|
| **Completion Date** | Ticket **Blocked** (mitigated, waiting for RCA) | Impact ended / pipeline restored; RCA still pending |
| **End Date** | Ticket **Done** (RCA documented in **Notes**) | Closure with RCA received |

Do not conflate these with Jira **resolutiondate** (system Done transition); **End Date** is the operational close-with-RCA date on the Dates tab.

## Reporting and analytics

| Question | Migrated SNOW (`created` ≤ 2026-05-30) | Native ADINC (`created` > 2026-05-30) |
|----------|----------------------------------------|---------------------------------------|
| When was the incident **opened** (SNOW legacy)? | **Start DatePick** | N/A — use **Created** or Support Bot time if “ticket filed”; **Start DatePick** if “DEV started” |
| When was impact **mitigated**? | **Completion Date** (when populated) | Same |
| When was ticket **closed with RCA**? | **End Date** (when populated) | Same |

The [ADINC Ticket Lifecycle](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192839878/ADINC+Ticket+Lifecycle) Databricks appendix maps SNOW `opened_on` → Jira **Created**. That reflects an older export mapping. **Operational truth for imports:** use **Start DatePick** for SNOW `opened_on`.

## MCP read example

```json
CallMcpTool user-jira-server jira_get_issue
{
  "issue_key": "ADINC-644",
  "fields": "created,customfield_10489,customfield_10566,customfield_10453"
}
```

## SNOW migration cutoff (related rules)

**2026-05-30** is still the cutoff for **Check 7 priority** (real `INC_NUMBER` → P1 only when Jira **`created` > 2026-05-30**). That rule uses **Jira Created** to distinguish migrated vs native tickets — not **Start DatePick**.

See [jira-adinc-audit/scripts/adinc_priority_check.py](jira-adinc-audit/scripts/adinc_priority_check.py) → `INC_P1_RULE_CUTOFF_DATE`.
