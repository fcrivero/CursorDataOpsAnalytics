---
name: pagerduty-incident-identity
description: >-
  Mandatory safety rules for fetching or mutating a specific PagerDuty incident.
  Identity gate (verify PD# and UUID match user input), forbidden API patterns,
  pre-mutation checks, and post-write verification. Referenced by all Data Ops PD
  skills. Use before get_incident, manage_incidents, add_note, or REST incident
  writes when a user supplies a PD#, URL, or job name.
---

# PagerDuty Incident Identity Verification

**Read [reference.md](reference.md) before any single-incident PagerDuty fetch or write.**

This skill has no separate workflow — it is a **safety contract** linked from:

- `dataops-pd-long-run`
- `dataops-pd-incident-analysis`
- `dataops-pd-incidents`
- `dataops-shift-summary`
- `oncall-handoff-incidents`
- `confluence-adinc-history`

## Quick checklist

1. **Fetch** — `get_incident` or `GET /incidents/{pd#_or_uuid}` (path only; never `?incident_number=`).
2. **Verify** — `incident_number` and/or UUID and title match user intent.
3. **Store** — `verified_uuid` for all downstream MCP/REST calls.
4. **Mutate** — re-gate; show PD# + title; use UUID only in `manage_incidents`.
5. **Confirm** — re-fetch; assert status changed.

On any verify failure: **abort** and report mismatch — never touch a different ticket.

Full rules, forbidden patterns, and regression example (#5793112): [reference.md](reference.md).
