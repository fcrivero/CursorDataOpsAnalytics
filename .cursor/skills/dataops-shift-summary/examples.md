# Data Ops Shift Summary — Examples

## Example request

> Executive summary for Jul 22, 9:30 AM–3:30 PM PT

## Example output (target length)

**Data Ops shift summary — Jul 22, 9:30 AM–3:30 PM PT**

- **17** PagerDuty incidents — **10** resolved, **7** acknowledged/snoozed at shift end. No customer-facing service outages. Mostly recurring Databricks pipeline alerts.

- **ODS Metrics MC Metadata DQ (~6)** — `ap_addr_ods_metrics_mc_metadata_dq_prod` · [ADINC-757](https://deept.atlassian.net/browse/ADINC-757). Active MySQL line items with no matching SingleStore delivery data; snoozed pending ODS Metrics fix.

- **Resolved / low impact** — [#5559428](https://disney.pagerduty.com/incidents/Q…) false positive; [#5559431](https://disney.pagerduty.com/incidents/Q…) stale duplicate DBX job; `linked_mappings` / `lifetime_delivery` self-cleared.

- **Emerging** — Telemetry event DQ failures on `ap_addr_ods_metrics_telemetry_event_dq_prod` (3 open); routed to ODS Core for triage.

- **Bottom line** — High alert noise, one coordinated metrics DQ issue in flight; follow up with ODS Metrics (ADINC-757) and ODS Core on telemetry DQ.

## Shorter variant (when user asks for less detail)

**Data Ops shift summary — Jul 22, 9:30 AM–3:30 PM PT**

- **17** incidents (**10** resolved, **7** open/snoozed). No customer outages. Recurring DBX pipeline noise.

- **Main issue:** Metrics MC Metadata DQ (~6) on `ap_addr_ods_metrics_mc_metadata_dq_prod` — snoozed; [ADINC-757](https://deept.atlassian.net/browse/ADINC-757) tracks the fix.

- **Still open:** 3 telemetry event DQ alerts → ODS Core triage.

- **Bottom line:** Noisy shift; prod pipelines running; ODS Metrics + ODS Core follow-ups needed.

## Multi-day range

**User:** "Shift summary Jul 20–22"

**Data Ops shift summary — Jul 20–22 PT**

- **42** incidents across 3 days — **31** resolved, **11** still open/snoozed on Jul 22 EOD. No customer-facing outages.

- **Top themes:** Metrics MC Metadata DQ (12), ADM segmentation long-run (8), Dag Change notifications (5).

- **Carry-over:** 7 incidents snoozed on ADINC-757 / metrics DQ family; 3 telemetry DQ open with ODS Core.

- **Bottom line:** Elevated metrics DQ noise all week; one ADINC tracks the primary fix — other items mostly self-resolved or routed.
