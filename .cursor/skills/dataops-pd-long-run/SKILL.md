---
name: dataops-pd-long-run
description: >-
  Triage and monitor PagerDuty Data Ops Long Run incidents: same input as
  dataops-pd-incident-analysis (PD#, URL, job, DAG). Immediately checks whether
  the DBX/Airflow run finished; if run state cannot be verified (e.g. LDB Airflow
  without Airflow MCP), tell the user immediately—no auto-recheck on proxy metrics.
  If SUCCESS prompts to resolve; if RUNNING diagnoses blocker and suggests monitor
  vs escalate with timed recheck (DBX only). Can resolve PD with notes when user
  confirms. Use when the user says monitor long run, check if finished, close long
  run, recheck PD#, or triage [Long Run] alerts. For full RCA, past incidents, and
  ADINC use dataops-pd-incident-analysis instead.
---

# Data Ops PD Long Run Triage

Fast **Long Run** workflow: check run status first, then **resolve**, **monitor**, or **escalate**. Unlike [dataops-pd-incident-analysis](../dataops-pd-incident-analysis/SKILL.md), this skill **may resolve** PagerDuty when the user confirms.

Shared config (input, tags, DBX, patterns): [reference.md](reference.md)

**Incident identity (mandatory):** [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md) — identity gate on every fetch; pre-mutation gate before resolve/note.

## Prerequisites

1. **PagerDuty MCP** (`user-pagerduty-mcp-manual`)
2. **ads-databricks MCP** — required for DBX Long Runs; skip DBX for LDB/Airflow-only if no job in title
3. Always call `GetMcpTools` before `CallMcpTool`

## Input — same as dataops-pd-incident-analysis

| Input type | Examples | Lookup |
|------------|----------|--------|
| **PD#** | `5589258`, `#5589258` | `get_incident` |
| **PD URL** | `https://disney.pagerduty.com/incidents/Q38RV1C9G0516X` | Extract UUID or number |
| **Alert URL** | `https://disney.pagerduty.com/alerts/Q345DWC6ZO5O85` | Step 1a in [reference.md](reference.md#alert-url-to-incident) |
| **Job name** | `ap_addr_ods_metrics_dcm_prod` | `list_incidents` → most recent open `[Long Run]` for that job |
| **DAG** | `prod-ldb_usr_view_agg_…` | Most recent open Long Run matching DAG |

If ambiguous, ask once. **Never** substitute a different PD# from chat context.

Confirm the incident title contains **`[Long Run]`** (case-insensitive). If the user gave a **Fail** PD#, say so and offer `dataops-pd-incident-analysis` instead.

## Workflow overview

```
Input → PD + alert → Can we verify actual run status?
         ├─ NO (Airflow/LDB, no MCP) → Branch D — tell user immediately
         ├─ SUCCESS (finished)       → Branch A — resolve prompt (AskQuestion)
         ├─ FAILED (finished)        → Branch B — escalate / resolve-fail prompt
         └─ RUNNING (not finished)   → Branch C — diagnose → monitor | escalate
                                       └─ optional auto-recheck loop (DBX only)
```

Display times in **PT** unless the user requests another timezone.

---

## Mandatory single-pass workflow — CRITICAL

**One user invocation = one complete response:** MCP fetches → full analysis → **action picker card**. Never split across turns. Never ask the user to reply `go`, `options`, or `continue` to see the card.

```
long run {pd#}  →  [MCP fetches] → [AskQuestion rich card] → [full analysis message]
                   └──────────── same assistant turn ────────────┘
```

### Single-pass steps (every triage)

1. Run all MCP fetches (`get_incident`, alerts, DBX run state, `analyze_job_task_failure` if FAILED).
2. Classify branch (A / B / C / D) and compute `recheck_minutes` + recheck/escalate times (Branch C).
3. **`AskQuestion`** — rich action picker (see format below). **Required** unless exceptions below.
4. **Assistant message (MANDATORY — same turn)** — complete triage (verdict, tables, assessment, draft notes, monitor timing). **Never end the turn with only tool calls or only the action card.**
5. End message with **### Choose action** — bullet list mirroring the AskQuestion button labels (fallback if card is dismissed).

**Hard rule:** If you called `AskQuestion` or MCP tools, you **must** still send the full analysis **message body** in that same turn. A turn that ends with tools but **no written triage** is a skill violation.

**Skip AskQuestion only when:**

| Condition | Action |
|-----------|--------|
| User said “resolve with closure notes” (or equivalent) in the **same** message as the PD# | Go straight to Step 7 |
| PD already `resolved` | Report only |
| User's follow-up is an explicit action keyword after a prior triage | Execute — no new card |

**Never** stop after analysis without calling `AskQuestion` on the initial `long run {pd#}` invocation.

### AskQuestion rules (same turn as analysis)

- **Always** call `AskQuestion` in the **same turn** as the triage analysis — this is the primary UX.
- Use the **rich action picker**: `title`, one-line `prompt`, 3–5 **descriptive button labels** with `(Recommended)` and **computed wait times** (`Auto-recheck in ~15 min`, etc.).
- Keep the card `prompt` to **one sentence** — run state, pattern, recheck/escalate clock times. No markdown tables in the card.
- Do **not** put the only copy of run-state tables inside the card — full tables belong in the message body.
- After the user picks an option, execute Step 6/7 (or auto-recheck loop for `auto_recheck`).
- Plain-text keywords (`resolve`, `escalate`, `monitor`) in a **follow-up** message count the same as a card selection.

**Cursor UI note:** The action card may render **above** the analysis text in the chat stream (tool UI before message body). That is expected. The analysis is still in the **same response** below the card; the **### Choose action** footer duplicates the buttons at the bottom for reading order.

### AskQuestion card format (REQUIRED shape)

Every triage picker **must** use `AskQuestion` with:

1. **`title`** — `PD #{incident_number} — Long Run {SAFE TO RESOLVE | STILL RUNNING | FAILED | CANNOT VERIFY}`
2. **`prompt`** — **one sentence** of context from Turn 1 (run state, pattern, recheck/escalate time). No markdown tables.
3. **`options`** — 3–5 buttons; put **`(Recommended)`** on the best action; include **computed wait times** for monitor/recheck options.

**Example — Branch C (RUNNING, monitor recommended):**

```json
AskQuestion
{
  "title": "PD #5676116 — Long Run STILL RUNNING",
  "questions": [{
    "id": "long_run_action",
    "prompt": "Run 315974348822157 ~106 min — ad_metadata_external_sensor att 13 In run. Baseline ~23 min. Recommend auto-recheck in ~15 min (~4:50 PM PT); escalate @oncall-adi-data-core if not SUCCESS by ~5:10 PM PT.",
    "options": [
      { "id": "auto_recheck", "label": "Auto-recheck in ~15 min (Recommended)" },
      { "id": "escalate", "label": "Escalate DEV oncall now (@oncall-adi-data-core)" },
      { "id": "manual", "label": "I'll check manually — keep PD open" },
      { "id": "full_analysis", "label": "Full analysis first (dataops-pd-incident-analysis)" }
    ]
  }]
}
```

**Example — Branch A (SUCCESS):**

```json
{
  "title": "PD #5669897 — Long Run SAFE TO RESOLVE",
  "questions": [{
    "id": "resolve_action",
    "prompt": "Run 1024574250291075 → SUCCESS (~84 min, baseline ~72 min). Alert fired after completion — self-heal Long Run.",
    "options": [
      { "id": "resolve", "label": "Resolve PD with closure notes (Recommended)" },
      { "id": "resolve_teams", "label": "Resolve PD + show Teams closeout" },
      { "id": "note_only", "label": "Keep PD open — I'll resolve later" },
      { "id": "full_analysis", "label": "Run full analysis (dataops-pd-incident-analysis)" }
    ]
  }]
}
```

**Example — Branch B (FAILED):**

```json
{
  "title": "PD #5794672 — Long Run FAILED",
  "questions": [{
    "id": "fail_action",
    "prompt": "Run 758951544426530 FAILED — conf-dq-check-app: FuboId US snapshot inconsistency (1,500,276 vs 985,219). Escalate @oncall-segmentation for DQ investigation.",
    "options": [
      { "id": "escalate", "label": "Escalate DEV oncall now (@oncall-segmentation) (Recommended)" },
      { "id": "resolve_fail", "label": "Resolve PD with failure note" },
      { "id": "full_analysis", "label": "Full analysis + ADINC (dataops-pd-incident-analysis)" }
    ]
  }]
}
```

**After auto-recheck (still RUNNING):** show a **new** AskQuestion card with updated elapsed time, attempt count, and refreshed `(Recommended)` (often **escalate** after 2–3 failed recheck loops).

**Branch D:** no `auto_recheck` button — manual confirm / escalate / resolve-after-confirm only.

---

## After user selects an action — CRITICAL

When the user picks an option (from `AskQuestion` or a keyword reply), follow the branch handler below. **Never jump straight to `Start-Sleep` or MCP writes without a user-visible message first.**

### All action selections

| Selection | First message (required) | Then |
|-----------|--------------------------|------|
| `resolve` / `resolve_teams` / `resolve_fail` | Confirm PD#, title snippet, action | Step 7-pre → note → resolve |
| `escalate` | One-line confirm | Step 6 Teams draft |
| `manual` / `note_only` | Acknowledge — PD stays open | Stop |
| `full_analysis` | Hand off to `dataops-pd-incident-analysis` | Run that skill |
| **`auto_recheck`** | **Wait announcement (template below)** | **Sleep → re-fetch → recheck report — fully automatic; user does nothing** |

### Auto-recheck protocol (`auto_recheck`) — MANDATORY 4 phases

**User expectation:** When they click **Auto-recheck in ~N min (Recommended)** on the action card, the agent **waits and rechecks by itself**. The user must **not** be asked to reply `recheck`, `go`, or `continue` after the sleep.

**Agent obligation:** After `auto_recheck` is selected, run **Phases 1–4 in sequence in the same conversation** without waiting for another user message between sleep and recheck.

**Phase 1 — Wait announcement (post BEFORE sleep — never skip)**

Send this **in chat** immediately after the user selects `auto_recheck`. Do **not** call `Start-Sleep` until this message is sent.

```markdown
## Monitoring — PD #{incident_number}

**You selected:** Auto-recheck in ~{recheck_minutes} min

| Field | Value |
|-------|--------|
| **Run** | `{run_id}` — {state} (~{elapsed} min) |
| **Recheck at** | ~{recheck_time PT} |
| **Escalate if** | Not SUCCESS by ~{escalate_time PT} or task FAILED |

Waiting ~{recheck_minutes} min, then I will re-fetch DBX run state and report back automatically.
```

**Phase 2 — Sleep (automatic — do not delegate to user)**

`Shell`: `Start-Sleep -Seconds {recheck_minutes * 60}` (PowerShell) or equivalent.

- Set `block_until_ms` to **at least** `(recheck_minutes * 60 + 30) * 1000` so the shell waits the full duration.
- On Windows, if sandbox blocks sleep, retry with `required_permissions: ["all"]`.
- **Never** skip sleep and tell the user to ping back later.

**Phase 3 — Re-fetch (required — retry on failure)**

1. `get_run_details` (or `list_job_runs`) for the same primary `run_id`.
2. If MCP times out or is interrupted, **retry once** — do not end the turn silently.
3. Optionally re-fetch PD incident status.

**Phase 4 — Recheck report (required — never skip)**

Always post a **written recheck summary** before any new `AskQuestion`:

```markdown
## Recheck — PD #{incident_number} (~{recheck_minutes} min later)

| Field | Value |
|-------|--------|
| **Run** | `{run_id}` — **{SUCCESS | RUNNING | FAILED}** |
| **Elapsed** | ~{N} min (baseline ~{median} min) |
| **Active task** | `{task_key}` — {state} (attempt {n}) or — |
| **Verdict** | {SAFE TO RESOLVE | STILL RUNNING | FAILED} |

{1–2 sentence assessment}
```

Then:

- **SUCCESS** → Branch A: draft resolve note + **`AskQuestion`** (resolve recommended) or execute if user already confirmed.
- **Still RUNNING** → Branch C again (max **3** auto loops total, then force escalate as Recommended).
- **FAILED** → Branch B: failure summary + **`AskQuestion`** (escalate recommended).

**Auto-recheck violations (never do these):**

- Tell the user to **reply `recheck`**, **`go`**, or **check back later** after they selected `auto_recheck` — the agent waits and rechecks automatically
- Call `Start-Sleep` **without** Phase 1 wait announcement
- Sleep completes but **no Phase 4 recheck report** (even if MCP was slow)
- End the follow-up turn with only tool calls and no user-visible text

---

## Step 1 — Fetch incident and alert

```json
CallMcpTool user-pagerduty-mcp-manual get_incident
{ "incident_id": "<id_or_number>" }
```

Record: `id` (UUID), `incident_number`, `title`, `status`, `created_at`, `service`, `assignments`.

### Step 1-verify — Identity gate (MANDATORY)

Run [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md) checks before alerts or triage:

- PD# from user → `incident_number` must match exactly.
- UUID from URL → `id` must match.
- Job/DAG-only lookup → title must contain token; **one** match or ask user.
- Service must be Data Ops (`P7OFL7L` / `P3CUKVY`) unless user specified otherwise.

On failure: **stop** — show API `incident_number`, `id`, and title snippet vs request. Never triage or resolve the wrong ticket.

Store `verified_uuid` — use only this below.

```json
CallMcpTool user-pagerduty-mcp-manual list_alerts_from_incident
{ "incident_id": "<verified_uuid>", "query_model": {} }
```

Parse alert `body.details.body` (or `cef_details.details.body`):

- Monitor type: **fixed threshold** (`datadog.running_spans.duration … > N`) vs **anomaly**
- Threshold duration (convert ns → hours/minutes)
- Job / workspace / DBX job URL / runbook links

Derive **Team** and **DEV oncall tag** — [reference.md](reference.md#team-and-on-call-tags).

---

## Step 2 — Immediate run status (do this first)

### DBX jobs (default)

1. Extract `job_name` from title or alert body — [reference.md](../dataops-pd-incident-analysis/reference.md#title-parsing)
2. `list_jobs(name_filter=job_name)` on `sox-prod-uw2` then `gen-prod-uw2`
3. `list_job_runs(job_id, limit=25)` — pick **primary run**:
   - Run ID in title/alert if present
   - Else RUNNING run whose `start_time` is closest to incident `created_at`
   - If multiple RUNNING, list all; primary = longest elapsed or run active at alert time
4. `get_run_details(workspace, run_id)` — parent state + all tasks
5. `get_job_details` — schedule, `timeout_seconds`, recent baseline
6. Compute **baseline duration** from last **5** TERMINATED SUCCESS runs (median minutes) — see [reference.md](reference.md#monitor-duration)

### Non-DBX Long Run (LDB Airflow / Goldmine)

When the alert is **Airflow / LDB / Goldmine** (e.g. title contains `LDB|`, `Dag-`, `dag_id:`, or alert body references `airflow.dag.*`) and there is **no DBX job** in the alert:

1. **Do not** call `list_job_runs` / `get_run_details` — DBX step is N/A.
2. **Do not** treat Datadog `airflow.dag.task.ongoing_duration` (or similar) as proof of **SUCCESS**, **FAILED**, or **RUNNING** — it is a **proxy** only (task elapsed time, can lag, can reset on task handoff).
3. **Go to Branch D immediately** — do not classify as Branch A/B/C and do not compute monitor windows from proxy metrics alone.

Optional: query Datadog for context **only if** it helps explain the page (threshold, metric at alert time) — label it **“alert proxy, not run state.”**

---

## Branch D — Cannot verify actual run status (STOP)

Use when **no authoritative run-state source** is available in this session:

| Platform | Authoritative source | Usually missing? |
|----------|---------------------|------------------|
| **DBX** | `get_run_details` → parent `TERMINATED` + `SUCCESS`/`FAILED` | No — use Step 2 |
| **LDB Airflow** | Airflow UI / API — DAG run `success` / `failed` / `running` | **Yes** — no Airflow MCP |
| **Goldmine / other** | Platform UI or API for that pipeline | Often yes |

### D1 — Lead with limitation (first thing in the response)

Render prominently **before** any status table or recommendation:

```markdown
## ⚠️ Cannot verify run completion — #{incident_number}

**I do not have access to the actual {Airflow DAG / pipeline} run state** for `{dag_or_job_name}`.
Datadog metrics from the alert are **not sufficient** to confirm SUCCESS or still RUNNING.

**You need to check:** {Airflow UI link or runbook link from alert}
- Airflow: `{airflow_id}` → DAG `{dag_id}` → latest run state

I can help resolve PD **after you confirm** the run finished (or failed).
```

### D2 — What you may include (optional, clearly labeled)

From the alert only (no invention):

- Page threshold and metric value at trigger time
- Runbook / Confluence links from alert body
- PD status (`acknowledged` / `resolved`)
- If Datadog queried: **“Proxy metric now: ~X min ongoing — does not confirm DAG success”**

### D3 — Action card (same pass)

After Branch D analysis, call **AskQuestion** using the [card format](#askquestion-card-format-required-shape) (no `monitor` / `auto_recheck` on Branch D):

| Option id | Label |
|-----------|-------|
| `manual` | **I'll check {Airflow/platform} now** (Recommended) |
| `escalate` | Escalate oncall now |
| `full_analysis` | Full analysis (`dataops-pd-incident-analysis`) |
| `resolve` | Resolve PD — I confirmed run SUCCESS in {platform} |

**Never on Branch D:**

- `auto_recheck` or `Start-Sleep` wait loops
- “Monitor for N min” as the primary recommendation
- Branch A/B/C resolve notes implying DBX SUCCESS
- Saying the job “finished” or “still running” based only on Datadog proxy metrics

**If user confirms SUCCESS in a follow-up message** (“it completed”, “resolve it”) → draft Branch A resolve note (LDB wording) + Step 7 if they choose resolve.

---

## Step 3 — Classify outcome

**Skip to Branch D** if Step 2 cannot verify run state. Otherwise:

| Parent / run state | Branch |
|--------------------|--------|
| `TERMINATED` + `SUCCESS` | **A — Finished (resolve)** |
| `TERMINATED` + `FAILED` / `CANCELED` | **B — Finished (failed)** |
| `RUNNING` | **C — Not finished** |
| PD already `resolved` | Report only — do not re-resolve unless user asks |

For RUNNING, also classify **pattern** — [reference.md](reference.md#long-run-patterns):

| Pattern | Signal |
|---------|--------|
| **Active work** | Leaf task `RUNNING` / `In run` |
| **Sensor wait** | `*_sensor` / `WAITING_FOR_RETRY`; error `Not ready to process` |
| **Zombie span** | Parent elapsed ≫ baseline; long gap between task attempts; Datadog span ≫ active work |
| **Stuck** | No task `RUNNING`, no retry scheduled, elapsed > 2× baseline |

---

## Branch A — Run finished SUCCESS

### A1 — Render status block

```markdown
## Long Run Status — #{incident_number}

| Field | Value |
|-------|--------|
| **PD** | [{status}](https://disney.pagerduty.com/incidents/{uuid}) |
| **Job** | `{job_name}` |
| **Run** | `{run_id}` — **SUCCESS** |
| **Duration** | {start PT} → {end PT} (~{N} min) |
| **Baseline** | ~{median} min (last 5 SUCCESS) |
| **Pattern** | {self-heal / slow completion / zombie span cleared} |
| **DEV oncall** | {tag} |

**Assessment:** Safe to close — run completed; no DEV action required unless downstream SLA impacted.
```

### A2 — Provide artifacts

1. **PD resolve note** — template [reference.md](reference.md#pd-resolve-note-success)
2. **MS Teams closeout** (optional, concise) — template [reference.md](reference.md#teams-closeout)

### A3 — Action card (same pass)

Include draft resolve note in the message. Call **AskQuestion** using the [card format](#askquestion-card-format-required-shape) in the **same turn**.

**Default options** (alerting run SUCCESS, no other RUNNING runs on job):

| Option id | Label |
|-----------|-------|
| `resolve` | **Resolve PD with closure notes (Recommended)** |
| `resolve_teams` | Resolve PD + show Teams closeout |
| `note_only` | Keep PD open — I'll resolve later |
| `full_analysis` | Run full analysis (`dataops-pd-incident-analysis`) |

**Prompt must include:** run ID, SUCCESS, duration vs baseline, why safe to close.

**When alerting run SUCCESS but other RUNNING runs exist** on the same job, add:

| Option id | Label |
|-----------|-------|
| `wait` | **Wait ~{recheck_minutes} min then recheck** (monitor concurrent run `{run_id}`) (Recommended) |

Use `recheck_minutes` from [reference.md](reference.md#monitor-duration) for the concurrent run’s pattern (sensor wait → typically 15–30 min).

**If `resolve` or `resolve_teams`:** user confirmed write — execute Step 7.

**If `wait`:** follow Branch C auto-recheck loop for the concurrent run only; do not resolve until alerting run still SUCCESS and user confirms.

**If `note_only`:** do not call PagerDuty write APIs.

**If `full_analysis`:** read and follow `dataops-pd-incident-analysis` SKILL.md.

---

## Branch B — Run finished FAILED

1. `analyze_job_task_failure` on primary run
2. Render short failure summary (task, error line, run link) in the message
3. Call **AskQuestion** using the [card format](#askquestion-card-format-required-shape) in the **same turn**

| Option id | Label |
|-----------|-------|
| `escalate` | **Escalate DEV oncall now ({oncall_tag}) (Recommended)** |
| `resolve_fail` | Resolve PD with failure note |
| `full_analysis` | Full analysis + ADINC (`dataops-pd-incident-analysis`) |

**Prompt must include:** run ID, failed task, one-line error, oncall tag.

If **escalate** → Step 6. If **resolve_fail** or user replies `resolve` → use [failure note template](reference.md#pd-resolve-note-failure) + Step 7.

---

## Branch C — Run still RUNNING

### C1 — Diagnose and recommend

Render:

```markdown
## Long Run Status — #{incident_number} — STILL RUNNING

| Field | Value |
|-------|--------|
| **Elapsed** | ~{N} min (baseline ~{median} min) |
| **Active task** | `{task_key}` — {state} (attempt {n}) |
| **Pattern** | {Active work / Sensor wait / Zombie span / Stuck} |
| **Blocker** | {one-line from task state or sensor error} |

### Recommended course of action
{MONITOR | ESCALATE NOW | MONITOR then escalate — with rationale}
```

**Course rules** — [reference.md](reference.md#course-of-action):

| Situation | Recommendation |
|-----------|----------------|
| Active task `In run`, elapsed < baseline | **Monitor** |
| Sensor retry, upstream delay, prior self-heals on same job | **Monitor** (sensor interval × remaining attempts or until baseline + 30%) |
| Zombie span but active attempt just started | **Monitor** until attempt baseline elapses |
| FAILED leaf, no retry left | **Escalate now** |
| Stuck / no progress > 2× baseline | **Escalate now** |
| Elapsed > monitor threshold with no completion | **Escalate** |

### C2 — Compute monitor window

Set **recheck_minutes** using [reference.md](reference.md#monitor-duration). Show:

- **Recheck at:** `{time PT}` (~{recheck_minutes} min)
- **Escalate if:** not SUCCESS by `{escalate_time PT}` or task FAILED

### C3 — Action card (same pass)

**Branch C only** — when DBX run state was verified in Step 2.

Message includes C1 + C2 with **Recheck at** / **Escalate if** times. Call **AskQuestion** using the [card format](#askquestion-card-format-required-shape) in the **same turn**.

| Option id | Label |
|-----------|-------|
| `auto_recheck` | **Auto-recheck in ~{recheck_minutes} min (Recommended)** |
| `escalate` | Escalate DEV oncall now ({oncall_tag}) |
| `manual` | I'll check manually — keep PD open |
| `resolve` | Resolve PD with closure notes — only if run already SUCCESS |
| `full_analysis` | Full analysis first (`dataops-pd-incident-analysis`) |

**Prompt must include:** run ID, elapsed min, active task + attempt, pattern, **Recheck at** time, **Escalate if** time, oncall tag. Mark `auto_recheck` as Recommended when course-of-action is MONITOR; mark `escalate` as Recommended when course-of-action is ESCALATE NOW.

**If `auto_recheck`:** follow [Auto-recheck protocol](#auto-recheck-protocol-auto_recheck--mandatory-4-phases) — **Phase 1 wait announcement before sleep**, Phase 4 recheck report after. Do **not** resolve without user confirmation.

**If `escalate`** → Step 6.

**Do not use Branch C** for LDB/Airflow when run state is unverified — use **Branch D** instead.

---

## Step 6 — DEV oncall message

Draft a copy-paste Teams message:

```
{job_name} {oncall_tag}

SUMMARY
PD #{incident_number} (Long Run) — {still running / failed}. {one-line ask}.

ROOT CAUSE
{pattern + blocker — factual, from DBX only}

KEY EVIDENCE
Run {run_id} — {state} (~{elapsed} min, baseline ~{baseline} min)
Active task: {task_key} — {state/error}
{run_page_url}
PD: https://disney.pagerduty.com/incidents/{uuid}
Runbook: {runbook_url}

{Specific ask, e.g. "Is upstream partition delay expected?" / "Please review ham_pipeline_v2 retry."}
```

Use `@oncall-…` from title mapping. Do not invent log lines.

---

## Step 7 — Resolve PagerDuty (user confirmed only)

Only after AskQuestion selects resolve (or explicit user message: "resolve", "close with note").

### Step 7-pre — Pre-mutation identity gate (MANDATORY)

1. Re-fetch `get_incident` (or `GET /incidents/{verified_uuid}`) and assert `incident_number` still matches the user's PD#.
2. State in chat: **PD#**, **title** (truncated), **current status** — user must see which ticket will change.
3. If gate fails, **abort** — do not resolve or note.

```json
CallMcpTool user-pagerduty-mcp-manual add_note_to_incident
{ "incident_id": "<verified_uuid>", "note": "<resolve note text>" }
```

```json
CallMcpTool user-pagerduty-mcp-manual manage_incidents
{ "manage_request": { "incident_ids": ["<verified_uuid>"], "status": "resolved" } }
```

If MCP write returns empty or errors, REST fallback per [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md) — **only** with `verified_uuid` from the gate.

**Post-write verify:** fetch again; assert `status == resolved`. Empty MCP `[]` is not proof. Report PD link using `verified_uuid`.

**Never** resolve without explicit user choice via AskQuestion (or direct user message: "resolve it", "close with note").

---

## Output order (single pass)

1. **MCP fetches** — incident, alert, DBX run state
2. **`AskQuestion`** — rich action card (`title`, `prompt`, buttons with `(Recommended)` and wait times)
3. **Chat message (required)** — full triage:
   - Verdict line (`SAFE TO RESOLVE` / `STILL RUNNING` / `FAILED` / `CANNOT VERIFY`)
   - Incident + DBX state tables
   - Assessment + draft closure notes (if applicable)
   - Monitor timing (Branch C) — **Recheck at** / **Escalate if**
   - **### Choose action** — bullets mirroring card labels
4. After user picks an option: follow [After user selects an action](#after-user-selects-an-action--critical)

## Output order (auto-recheck follow-up)

1. **Wait announcement** — recheck time, run ID, escalate-if (before sleep)
2. **Sleep** — `Start-Sleep`
3. **MCP re-fetch** — run state (retry once on failure)
4. **Recheck report** — verdict table + assessment
5. **`AskQuestion`** — next action (resolve / monitor again / escalate)

Do **not** produce ADINC or full similar-incident report here — point to `dataops-pd-incident-analysis` when needed.

## Examples

**User:** `monitor 5589258`

→ Single pass: Step 1–2 → if RUNNING, diagnose → **AskQuestion** + **full analysis message** + Choose action footer. If user picks `auto_recheck` → wait announcement → sleep → recheck report → resolve/escalate card.

**User:** `check long run 5589003`

→ Single pass: if SUCCESS → **AskQuestion** (resolve recommended) + resolve note + Choose action footer.

**User:** `yes resolve with that note`

→ Skip card → Step 7 (direct confirmation in same message as PD#).

**User:** `long run 5682042` (LDB Airflow)

→ Single pass: Branch D — cannot verify + runbook links + **AskQuestion** (no auto-recheck) + Choose action footer.

## Do not

- Split triage and action card across **two turns** or require `go` / `options` / `continue`
- End a `long run {pd#}` response **without** calling **`AskQuestion`** (unless resolve-in-same-message or already resolved)
- **End any turn with only tool calls** — triage, wait announcement, and recheck report must always include a **written message body**
- Tell the user to **reply `recheck`** after they picked **`auto_recheck`** on the action card
- Call **`Start-Sleep` for `auto_recheck` without posting the wait announcement first**
- **Complete a sleep without posting the recheck report** — retry MCP if needed; never go silent after wait
- Use a bare prompt like “Choose action” without run context, recheck times, or `(Recommended)` labels
- Show **only** the AskQuestion card without the full analysis message in the same response
- Put the **only** run-state analysis inside the AskQuestion `prompt` — verdict and DBX table belong in the message body
- Omit the **### Choose action** footer that mirrors card button labels
- Resolve PD without user confirmation (footer reply, AskQuestion selection, or explicit “resolve with closure notes”)
- **Auto-recheck, sleep, or “check again in N min” when actual run status is unverified (Branch D)** — tell the user immediately and point them to Airflow/platform UI
- **Claim SUCCESS / RUNNING / FAILED** for Airflow/LDB/Goldmine without authoritative platform state
- Use Datadog `ongoing_duration` alone to close or monitor an LDB Long Run
- Invent run state, errors, or baseline durations — compute from MCP data
- Use `incident_number` with `list_alerts_from_incident` — use **verified UUID** only
- Substitute a different incident from conversation context
- Skip identity gate or pre-mutation gate — see [pagerduty-incident-identity](../pagerduty-incident-identity/reference.md)
- Use `GET /incidents?incident_number=` or `list_incidents[0]` to resolve a PD#
- Mutate (resolve/note) without post-write status verification
- Run full ADINC / 90-day similar-incident search in this skill — defer to `dataops-pd-incident-analysis`
- Escalate for active `In run` tasks still within baseline without stating monitor alternative

## See also

- Full RCA / ADINC / past incidents: [dataops-pd-incident-analysis](../dataops-pd-incident-analysis/SKILL.md)
- Shared PD/DBX reference: [dataops-pd-incident-analysis/reference.md](../dataops-pd-incident-analysis/reference.md)
- Incident identity safety: [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md)
