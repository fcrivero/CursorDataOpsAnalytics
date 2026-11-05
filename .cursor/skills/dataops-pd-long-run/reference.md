# Data Ops PD Long Run — Reference

Extends [dataops-pd-incident-analysis/reference.md](../dataops-pd-incident-analysis/reference.md) with Long Run triage patterns and monitor math.

**PagerDuty identity (mandatory):** [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md)

## Alert URL to incident

Same as parent skill Step 1a: `list_incidents` (7d, both services) → `list_alerts_from_incident(uuid)` → match alert id.

## Team and on-call tags

Same table as parent skill — extract `@oncall-…` from the **PagerDuty title** (bracket subtitles supersede job-name keywords). See [dataops-pd-incident-analysis/reference.md](../dataops-pd-incident-analysis/reference.md#team-and-on-call-tags).

| Title pattern (brackets in PD title) | Tag |
|--------------------------------------|-----|
| `[AP][ODS][Metrics]` | `@oncall-ods-metrics` |
| `[AP][ODS][Core]` | `@oncall-adi-data-core` |
| `[AP][ADM][segmentation]` / `[Segmentation]` | `@oncall-segmentation` |
| `[AP][ADM][Targeting]` / `[targeting]` | `@oncall-audience-targeting` |
| `[AP][BI]` | `@oncall-addr-bi` |

## Monitor type parsing

| Alert query signal | Type | Typical threshold |
|--------------------|------|-------------------|
| `> 35700000000000` (ns) | Fixed | ~9.9 h |
| `> 7899900000000` (ns) | Fixed | ~2.2 h |
| `anomalies(…running_spans.duration…)` | Anomaly | vs predicted; compare to job baseline |

Convert ns: `seconds = ns / 1e9`, `minutes = seconds / 60`, `hours = minutes / 60`.

## Unverifiable run status (Branch D)

Use when the agent **cannot** read authoritative run completion state in-session.

| Signal in alert | Authoritative check | Agent can verify? |
|-----------------|---------------------|-------------------|
| DBX job URL / `operation_name:databricks.job` | `get_run_details` | **Yes** → Step 2 / Branch A–C |
| `LDB\|`, `Dag-prod-ldb_`, `airflow.dag.*` | Airflow UI/API (`uaplinear-prod`, etc.) | **No** → Branch D |
| Goldmine / other | Platform-specific UI | Usually **no** → Branch D |

**Datadog Airflow proxies (NOT run state):**

- `airflow.dag.task.ongoing_duration` — seconds the **current task** has been running; drops on task change; does **not** prove DAG `success`
- Monitor recovery (metric below threshold) ≠ DAG succeeded

**Required behavior:** First response must state the limitation. No `auto_recheck`, no `Start-Sleep`, no “wait and check later” as primary path.

**LDB resolve note (after user confirms SUCCESS in Airflow):**

```
Resolved — self-heal Long Run (LDB Airflow).

DAG: {dag_id} ({airflow_id})
Alert: task ongoing_duration exceeded {threshold} during run; user confirmed DAG run SUCCESS in Airflow.
No DBX job; no DEV action required unless downstream SLA impacted.

Runbook: {runbook_url}
PD: https://disney.pagerduty.com/incidents/{uuid}
```

## Long-run patterns

### 1 — Active work (monitor)

- Leaf task `life_cycle_state`: `RUNNING`, `state_message`: `In run`
- Parent elapsed may exceed Datadog threshold while work is legitimate
- **Action:** Monitor until task completes or exceeds **task baseline + 30%**

### 2 — Partition / job sensor wait (monitor)

- Task key contains `_sensor`; state `WAITING_FOR_RETRY` or repeated FAILED attempts
- Common error: `Exception: Not ready to process`
- Retry interval ~**10 min** between attempts (verify from attempt timestamps)
- **Action:** Monitor through expected retries or until **baseline + 50%**; escalate if upstream never lands same day

### 3 — Zombie parent span (monitor if active attempt running)

- Parent run RUNNING **many hours**; large **gap** between task attempts
- Datadog span duration ≫ wall-clock of active work
- New attempt started recently → often self-heals (e.g. `ham_pipeline_v2` att 2)
- **Action:** Monitor for **current attempt baseline**; resolve when parent SUCCESS

### 4 — Stuck (escalate)

- No task RUNNING, no WAITING_FOR_RETRY, elapsed > **2× baseline**
- `identify_stuck_runs` flags the run
- **Action:** Escalate DEV immediately

### 5 — Concurrent duplicate runs

- Multiple RUNNING ONE_TIME runs on same job (e.g. DQ backfills)
- **Action:** Note all run IDs; monitor primary; mention stragglers in resolve note; escalate if failures diverge

## Monitor duration

Compute in order; use the **first applicable** rule, then apply **+15 min buffer** (round up to nearest 5 min).

### Baseline from history

From `list_job_runs`, last **5** `TERMINATED` + `SUCCESS` + same trigger type (`PERIODIC` preferred):

```
baseline_min = median(end_time - start_time) in minutes
```

If fewer than 3 SUCCESS runs, use available count and note low confidence.

### Rule A — Active task in progress

```
remaining = max(0, task_baseline_min - task_elapsed_min)
recheck_minutes = remaining + 15
```

`task_baseline_min`: median duration of same `task_key` from last 3 successful runs (from `get_run_details.tasks[].execution_duration`), or **30 min** default for unknown Spark tasks.

Cap single recheck at **45 min**; if longer, set intermediate recheck at 30 min.

### Rule B — Sensor retry loop

```
attempts_remaining = max(0, max_attempts - current_attempt - 1)  # default max_attempts 15 if unknown
recheck_minutes = min(60, attempts_remaining * 10 + 10)
```

If sensor errors are **not** `Not ready to process`, treat as Rule D.

### Rule C — Zombie span, new attempt just started

Use Rule A on the **current attempt** only (ignore parent elapsed for recheck timing).

### Rule D — Default

```
recheck_minutes = max(15, min(45, baseline_min - elapsed_min + 20))
```

### Escalate deadline

```
escalate_if_not_success_by = now + max(baseline_min * 1.5, recheck_minutes + 30 min)
```

For fixed **2.2 h** threshold jobs, also escalate if elapsed approaches **130 min** without SUCCESS.

## Course of action

| Pattern | Elapsed vs baseline | Recommend |
|---------|---------------------|-----------|
| Active work | < baseline | Monitor |
| Active work | baseline – 1.5× baseline | Monitor + warn |
| Active work | > 1.5× baseline | Monitor one cycle, then escalate |
| Sensor wait | < baseline + 50% | Monitor |
| Sensor wait | > baseline + 50% | Monitor + CC DEV if SLA-sensitive |
| Zombie + fresh attempt | attempt < task baseline | Monitor |
| Stuck | > 2× baseline | Escalate now |
| FAILED, no retry | any | Escalate now |

## PD resolve note — SUCCESS

```
Resolved — self-heal Long Run.

Job: {job_name} ({workspace}, job {job_id})
Run: {run_id} — SUCCESS ({start PT}–{end PT}, ~{duration_min} min)
{Optional: Pattern line, e.g. "Zombie parent span; final task {task_key} att {n} SUCCESS."}

Datadog Long Run monitor fired while run duration exceeded {threshold or anomaly baseline}. Run completed without failure; no repair or DEV action required.
{Optional: Related PD# if same run re-page.}

DBX: {run_page_url}
Runbook: {runbook_url}
```

## PD resolve note — FAILURE

```
Resolved — Long Run associated with failed run.

Job: {job_name} ({workspace}, job {job_id})
Run: {run_id} — FAILED
Failed task: {task_key} — {error_summary}

DEV engaged / repair required: {Y/N per user action}

DBX: {run_page_url}
Runbook: {runbook_url}
```

## Teams closeout

```
{job_name} {oncall_tag}

SUMMARY
PD #{incident_number} (Long Run) — RESOLVED. Run {run_id} completed SUCCESS; no DEV action needed.

ROOT CAUSE
{One sentence — pattern + why monitor fired}

KEY EVIDENCE
Run {run_id} — SUCCESS ({duration} min, baseline ~{baseline} min)
{run_page_url}
PD: https://disney.pagerduty.com/incidents/{uuid}

No action needed unless downstream SLA was impacted.
```

## Verified examples (patterns)

| PD | Job | Pattern | Resolution |
|----|-----|---------|------------|
| #5587690 / #5589258 | `ap_addr_ods_metrics_dcm_prod` | Zombie span + `ham_pipeline_v2` retries | Self-heal when attempt SUCCESS |
| #5587902 / #5588655 | `ap_addr_ods_metrics_mc_metadata_dq_prod` | Partition sensor `Not ready to process` | Self-heal when sensor clears; watch duplicate runs |
| #5589003 | `ap_addr_audience_nrt_ifp_unified_table_creator_snapshot_audience_prod` | Anomaly + active snapshot | Self-heal ~80 min vs ~50 min baseline |
| #5682042 | `prod-ldb_usr_view_agg_up_delivery_context_source_to_sf` | LDB Airflow — no Airflow MCP | Branch D: user checks Airflow; do not auto-recheck on Datadog proxy |

## Auto-recheck loop

**DBX verified runs only (Branch C).** Do not use for Branch D.

1. Max **3** consecutive auto-rechecks per user session
2. After 3rd still RUNNING → AskQuestion: escalate / one more recheck / full analysis
3. If run transitions to SUCCESS → Branch A immediately
4. Sleep command: PowerShell `Start-Sleep -Seconds {n}`; add 30s buffer to block_until_ms
