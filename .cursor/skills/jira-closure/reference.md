# Jira Closure — Reference

## Closure note template

Use this structure. Omit sections with no data; do not pad with placeholders.

```markdown
**[[{KEY}]({browse_url})]** {summary}

**Closed:** {closure_date} PT
**Status:** {status} · **Assignee:** {assignee}

**Summary**
{1–2 sentences from description — problem, scope, impact}

**Resolution**
{from comments and/or description — what fixed it, final state}

**Actions / follow-ups** (if any)
- {action item from comments or description}
```

Omit **Actions / follow-ups** when none exist. Add a **Links** section **only** for non-Jira URLs (PagerDuty, Confluence, Teams thread, etc.) — never repeat the Jira browse link.

### Formatting rules

- Use markdown `**bold**` for section labels — Teams renders it as rich text.
- Keep total length suitable for a channel post: aim for **under 20 lines**.
- **Do not include Rationale or Justification** — omit background/explanation sections from the Jira description; report only the outcome.
- **No redundant Jira link** — put the browse URL on the ticket key in line 1 only; do not add a separate Links section for Jira.
- Preserve exact tokens: ticket keys, INC numbers, PD IDs, DAG names, pipeline names, dates in data.
- Convert Jira wiki markup in description/comments to plain markdown when synthesizing (see `jira-ticket` Jira Markup section).
- If multiple comments tell the story, merge chronologically into **Resolution** — do not dump raw comment threads.

## Closure date examples

| Changelog entry | Display |
|-----------------|---------|
| status → Done @ 2026-07-23T21:32:00Z | Closed: 2026-07-23 14:32 PT |
| status → Accepted @ … | Accepted: {date} PT |
| No terminal transition; resolutiondate set | Closed: {resolutiondate} PT |
| Open ticket | Status: In Progress — **not yet closed** (last updated: …) |

## Teams destination cheat sheet

| User provides | Resolution |
|---------------|------------|
| `TeamName / channel-name` | `channel teams --filter` → `channel send` |
| `https://teams.microsoft.com/l/message/19:...@thread.tacv2/170?...` | Parse IDs → `channel reply` |
| Chat URL with `@thread.v2` | `message send --from-url` or chat reply |
| Only channel name | `search channels --query` then confirm team |

Always verify team/channel match with the user when search returns multiple hits.

## Example output

**Input:** `ADINC-798`

```markdown
**[[ADINC-798](https://deept.atlassian.net/browse/ADINC-798)]** [AP][ADM][Measurement] missing D+ data for 7/21/26 in fact_ad_delivery

**Closed:** 2026-07-23 16:45 PT
**Status:** Done · **Assignee:** Jane Doe

**Summary**
Upstream delay in ap_addr_measurement_adlog_all_publishers_prod caused missing Disney+ delivery rows for 2026-07-21 in fact_ad_delivery.

**Resolution**
Vendor replay completed; downstream DAG re-run validated row counts. No further gaps for the affected date.
```

**Input:** `SKRULL-8718` (threshold change — no rationale)

```markdown
**[[SKRULL-8718](https://deept.atlassian.net/browse/SKRULL-8718)]** Adjust ADM Segmentation Long Run thresholds to reduce alert noise

**Closed:** 2026-08-07 00:03 PT
**Status:** Done · **Assignee:** Deepthi Konda

**Summary**
Updated Long Run monitor thresholds for ADM Segmentation pipelines.

**Resolution**
- **12h threshold:** ap_addr_audience_cross_sell_dms_inbound_prod, ap_addr_audience_cross_sell_dms_serving_prod, ap_addr_audience_disney_plus_fandom_inbound_prod
- **4h threshold:** remaining Segmentation Long Run monitors (Identity, Subscription, Hulu Fandom — 9 pipelines)
```
