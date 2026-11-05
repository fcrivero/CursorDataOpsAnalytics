---
name: focus-plan
description: >-
  Generates Fernando Rivero's next weekly Confluence focus plan under F. Rivero's
  Focus Plans (APSW): carries over unfinished milestones (including nested task
  trees), merges ALL open items from the Daily activity and todo log
  (fcrivero/CursorDataOpsAnalytics daily-log.md) and Oncall activity log agent
  into Milestones with AskQuestion dedup, rolls personal/team goals, rebuilds
  accomplishments, validates carryover with validate_wfp_carryover.py before
  publish, and publishes via Confluence MCP. Use when the user asks to
  create, generate, or update a focus plan, weekly plan, or Fernando Rivero
  focus plan.
---

# Focus Plan Generator

Create the **next weekly focus plan** as a child of [F. Rivero's Focus Plans](https://disney-enterprise.atlassian.net/wiki/spaces/APSW/pages/197569776) in Confluence space **APSW**.

Always call `GetMcpTools` before `CallMcpTool`. Details: [reference.md](reference.md).

## Inputs

| Input | Required | Used in |
|-------|----------|---------|
| Target week (defaults to **current week**, Monday start) | No | Title `YYYY-MM-DD- Fernando Rivero` |
| Additional **Personal Goals** | No | Personal Goals table |
| Additional **Team Goals** | No | Team Goals table |
| Additional bullets for Touch-Points, Escalations, Non-Project, 1:1 | No | Respective sections (append only) |
| Work schedule / PTO updates | No | Right sidebar |

## Workflow checklist

```
- [ ] Step 1: Fetch latest focus plan
- [ ] Step 2: Parse previous plan (parser script)
- [ ] Step 3: Carry over unfinished milestones from previous plan
- [ ] Step 4: Fetch Daily activity and todo log — personal repo (mandatory)
- [ ] Step 5: Fetch Oncall activity log (mandatory)
- [ ] Step 6: Assemble Milestones section (carryover + daily log + oncall; dedup)
- [ ] Step 7: AskQuestion — similar items + full preview before publish
- [ ] Step 8: Personal Goals, Team Goals, append-only sections, Accomplishments
- [ ] Step 9: Spell-check all text
- [ ] Step 10: validate_wfp_carryover.py (block publish on failure)
- [ ] Step 11: Create or update Confluence page
- [ ] Step 12: Report page URL
```

## Carryover invariants (mandatory — do not skip)

These rules prevent dropping open WFP work when the daily log or fuzzy text match disagrees.

| Invariant | Rule |
|-----------|------|
| **Tree completion** | Remove a milestone **tree** only when **every** `<ac:task-status>` in the merged block is `complete` (`is_fully_complete_block`). |
| **Daily log ≠ plan** | A crossed-out daily-log line does **not** remove an incomplete nested tree on the prior WFP. Log lines are often umbrella follow-ups; subtasks on the plan are the source of truth until checked off **on the plan**. |
| **Accomplishments ≠ drop** | Listing text under **Accomplishments last week** does **not** authorize removing a still-incomplete milestone (same guard as daily log). |
| **Fuzzy match scope** | `matches_prior_completed` / `matches_prior_done` may **skip adding** a duplicate daily-log line — they must **not** filter out **carried** blocks from Step 3 unless the tree is fully complete. Use `filter_carried_blocks_by_daily_done()` only. |
| **No regex drops** | Do **not** use ad-hoc `patch_wfp_*.py` regex to delete `<ac:task>` subtrees unless you re-run validation and the tree is fully complete on the **previous** published plan. |
| **Pre-publish gate** | Run `validate_wfp_carryover.py` — **exit code must be 0** before `confluence_create_page` / `confluence_update_page`. |

**Canonical failure (Sep 2026):** Prior WFP had open **DBX CICD** + three children. Daily log #34 “Follow up on ADINC jobs/workbooks CICD” was done. Automation removed the whole tree — wrong. Fix: carry incomplete trees; allow accomplishment for the log line; keep plan subtasks until complete.

```bash
python ~/.cursor/skills/focus-plan/scripts/validate_wfp_carryover.py \
  --previous prev-wfp.json \
  --new page-bodies/YYYY-MM-DD-new.html
```

On failure: restore missing blocks from the previous page HTML (`carryover_html_blocks` + `merge_task_with_following_list`), fix build logic, re-run until OK.

```

---

### Step 1 — Fetch latest focus plan

1. Search for the most recent weekly plan:

```json
CallMcpTool user-confluence-disney confluence_search_content
{
  "cql": "ancestor = 197569776 AND type = page AND title ~ \"Fernando Rivero\" ORDER BY created DESC",
  "limit": 5,
  "expand": "version"
}
```

Pick the latest page whose title matches `YYYY-MM-DD- Fernando Rivero` (skip Archive, FY*, Self-Summary pages).

2. Fetch full body:

```json
CallMcpTool user-confluence-disney confluence_get_page
{
  "page_id": "<id>",
  "expand": "body.storage,version,space"
}
```

3. Compute **new title**: Monday of target week → `YYYY-MM-DD- Fernando Rivero`. Search parent children — if title exists, **update** that page; otherwise **create** under parent `197569776`.

---

### Step 2 — Parse previous plan

Save `confluence_get_page` response to a temp JSON file, then run:

```bash
python ~/.cursor/skills/focus-plan/scripts/parse_focus_plan.py --input <page.json> --output parsed.json
```

Read `parsed.json` for structured sections. When rebuilding Confluence storage HTML, **clone the previous page body** and replace section contents — preserve layout macros, DAchieve sidebar blocks, and formatting.

---

### Step 3 — Carry over milestones from previous plan

**Carryover (rules 2 & 3):**

| Rule | Behavior |
|------|----------|
| Checked top-level task, no incomplete children | **Remove** |
| Unchecked top-level task | **Carry over** as incomplete |
| Parent with nested children; parent **or any child** incomplete | **Carry entire tree** — keep parent + all children with **original check states** (checked children stay checked) |
| Daily log marks a **related** line done (e.g. “Follow up on ADINC jobs/workbooks CICD”) | **Do not remove** a nested WFP tree while **any** subtask is still incomplete on the prior plan — log wording ≠ full milestone completion |

Example (nested parent incomplete, mixed children):

```
☐ SLA Dashboard demo (Developers)
    ☑ Follow up with ADM to update SLAs
    ☑ Follow up with ODS to update SLAs
    ☐ Make sure SLAs for ADM are updated and shared
    ☐ Make sure SLAs for ODS are updated and shared
```

→ Carry all four lines exactly as shown.

Use `milestones_carryover` from parser output.

**Confluence nesting quirk:** child tasks may appear as a **sibling** `<ac:task-list>` immediately after the parent `<ac:task>` (not inside `<ac:task-body>`). The parser merges these; when rebuilding manually, preserve that structure or nest inside task-body — both render correctly.

**Prefer preserving `raw_xml`** from parser output for carried tasks (keeps Jira macros, links, `<time>` tags). Only regenerate XML for newly added oncall/daily-log items.

**Nested task trees (critical):** Confluence stores child tasks as a **sibling** `<ac:task-list>` immediately after the parent `<ac:task>`. When extracting or rebuilding the milestones list:

1. Use **balanced** `</ac:task-list>` matching (`scripts/milestone_carryover.py`) — never `find('</ac:task-list>')` on the first match, or nested lists truncate and children flatten to top level.
2. Merge each `<ac:task>` with its immediately following sibling `<ac:task-list>` into one tree block before carryover decisions.
3. If parent is **incomplete** OR **any child** is incomplete → carry the **entire** merged block with **all** original check states (checked children stay checked).

Use `scripts/milestone_carryover.py` → `carryover_html_blocks()` or `carryover_from_parsed()` + `rebuild_milestones_html()` when rebuilding the page body.

When removing carried blocks because a daily-log line was crossed out, **only** use:

```python
from milestone_carryover import carryover_html_blocks, filter_carried_blocks_by_daily_done

carried = carryover_html_blocks(previous_body)
kept, dropped = filter_carried_blocks_by_daily_done(carried, daily["done_items"])
```

Never implement a local `should_drop_block()` that omits the `is_fully_complete_block` check.

**HTML-accurate completion detection (critical):** Do not rely on `parse_focus_plan.py` → `milestones_completed` alone for daily-log dedup. Daily-log items appended at the end of the milestones list are often **missed by the parser** but are visible in storage HTML. Always call:

```python
from milestone_carryover import completed_block_texts_from_html, prune_complete_blocks
completed = completed_block_texts_from_html(previous_plan_body)
```

**After rebuilding milestones**, run `prune_complete_blocks(body)` as a safety net to drop any fully-complete trees that slipped through.

**Nested trees:** Checked **children** under an **incomplete parent** stay (with checks preserved). Only drop a tree when **every** task in the block is `complete` (no `incomplete` status anywhere in the block).

---

**Do not** carry checked-only items with no incomplete descendants.

This step produces the **baseline** milestone list. Steps 4–6 add items from external logs.

---

### Step 4 — Daily activity and todo log (mandatory)

Always read the latest **Daily activity and todo log** from the personal repo [fcrivero/CursorDataOpsAnalytics](https://github.com/fcrivero/CursorDataOpsAnalytics) — file **`daily-log.md`** (work todos). This is the same log used by the Cloud Agent **Daily activity and todo log (remote)**.

**Do not** use `personal-todo.md` for focus plans.

**Fetch freshest copy (try in order):**

```bash
python ~/.cursor/skills/focus-plan/scripts/fetch_daily_log.py --output daily-log.md --json-summary daily-fetch.json
```

This runs `git pull` on the local clone **and** fetches GitHub API / raw URL, then picks the freshest copy. **Always run this before parsing.**

**Staleness check (mandatory):** Pass the plan Monday so the script flags an out-of-date log:

```bash
python ~/.cursor/skills/focus-plan/scripts/fetch_daily_log.py \
  --json-summary daily-fetch.json \
  --warn-if-before YYYY-MM-DD
```

If `stale: true` in the summary → **stop and warn the user**. The Cloud Agent copy may be ahead of GitHub. Ask the user to sync/push from **Daily activity and todo log (remote)** (`scripts/sync-log.sh`) before building the WFP. Do not silently use an old log.

Compare `next_item_number` and `last_updated` against what the user expects. Example: GitHub at `#30` while user sees `#36` means unpushed Cloud Agent edits.

Manual fallbacks if the script fails:

1. **Local clone** — pull first if git repo:
   - `C:\Users\rivef104\Documents\AI\Cloud\CursorDataOpsAnalytics\daily-log.md`
2. **GitHub CLI** (personal host):
   ```powershell
   gh api --hostname github.com repos/fcrivero/CursorDataOpsAnalytics/contents/daily-log.md --jq ".content"
   ```
   (Base64-decode content if using API raw response.)
3. **Raw GitHub** (fallback):
   `https://raw.githubusercontent.com/fcrivero/CursorDataOpsAnalytics/main/daily-log.md`

Parse:

```bash
python ~/.cursor/skills/focus-plan/scripts/parse_daily_log.py --input daily-log.md --output daily-parsed.json
```

**Include in Milestones:** **every open item** from `open_items` — all numbered lines **without** `~~` strikethrough. Goal: the focus plan Milestones section reflects the full current work todo list.

**Exclude from Milestones:**
- Crossed-out / done items (`~~text~~`)
- Meta items about creating the focus plan itself (e.g. "Create Focus plan") when you are generating that plan

**Preserve links when adding:** Daily-log and oncall items often include markdown links — `[Teams chat](https://teams.microsoft.com/...)`, `[SKRULL-8785](https://deept.atlassian.net/browse/...)`, `[Google Slides](https://docs.google.com/...)`, `mailto:` links. When converting to milestones:

| Link type | Confluence output |
|-----------|-------------------|
| DEEPT Jira (`ADIA-*`, `SKRULL-*`, `ADINC-*`) | Jira macro (same as carried milestones) |
| MS Teams, Google Docs, GitHub, email, other URLs | `<a href="URL">label</a>` |

Use the **`raw`** field from `parse_daily_log.py` (not plain `text`) when calling `task_to_xml` / `format_task_body_inner`. Plain `text` is for dedup only.

Oncall log items with URLs: include markdown `[label](url)` in milestone text before formatting.

**Recently completed daily-log items** (newly crossed out since last focus plan) → candidates for **Accomplishments last week**.

**Dedup before adding** — for **each** open daily-log item, compare against the baseline milestones from Step 3 (and any Oncall items already queued):

| Match | Action |
|-------|--------|
| Exact or near-exact duplicate | **Skip** (already in plan) |
| Matches **completed milestone** (`completed_block_texts_from_html`) **or prior Accomplishments** (`matches_prior_done`) when **adding** a daily-log line | **Skip** re-add — already credited last week, even if daily log still open (no `~~`). **Does not** apply to Step 3 carryover — incomplete trees always carry regardless. |
| Similar wording (≥72% token overlap or substring match) | **AskQuestion** — show both texts; user picks **Replace** existing milestone / **Add** as new / **Skip** |
| Clearly distinct | **Add** as new incomplete milestone task |

**Completed-on-previous-plan guard (daily-log add only):** Items already done last week must not re-enter via daily log. Use `matches_prior_done(text, previous_plan_body)` — checks both checked milestones **and** the previous plan's Accomplishments section. Example: ADIA-1800 was listed under Accomplishments on the Sep 8 plan but still open in `daily-log.md` → skip daily-log #21, do not re-add as a milestone. The **DBX CICD** tree on the prior WFP still carries if any subtask is incomplete, even when a related daily-log follow-up is crossed out.

**AskQuestion format** (one prompt per similar pair):

```
Daily log item:  "Follow up with MSTR on 2-year contract renewal"
Existing milestone: "Follow up with MSTR on renewal process"

These look similar. What should I do?
- Replace existing milestone with daily-log wording
- Add daily-log item as a separate milestone
- Skip (keep existing only)
```

Preserve ticket keys (ADINC, SKRULL, ADIA) and **links** when converting to Confluence task text. Use `raw` markdown from daily log, not plain `text`.

---

### Step 5 — Oncall activity log (mandatory)

The **Oncall activity log** is a session agent that logs shift follow-ups. **Always check it** before finalizing milestones.

**Parse with script** (preferred):

```bash
python ~/.cursor/skills/focus-plan/scripts/parse_oncall_log.py --output oncall-parsed.json
```

Or pass a specific transcript:

```bash
python ~/.cursor/skills/focus-plan/scripts/parse_oncall_log.py --transcript "<uuid>/<uuid>.jsonl" --output oncall-parsed.json
```

The script:
1. Finds the **most recently updated** transcript under `agent-transcripts/` containing `Oncall log`, `Open items`, or `Pending items`
2. Reads the **latest Open items snapshot** (`## Open items`, `## Open items remaining`, or Quick summary table)
3. Parses the `| Day | Name | Next action |` table for all open rows
4. Enriches each row with links from the matching `###` detail section (Jira, Teams, PagerDuty)
5. Formats compact milestone markdown (1–2 lines) for each **child** task

**Nesting (mandatory):** All open oncall items nest under one parent milestone:

```
☐ Follow up with open Oncall items
    ☐ sne_identity Long Run — Close after threshold verify · [SKRULL-8718](url) · [Teams thread](url)
    ☐ LDB agg up delivery context — Threshold + naming + @oncall-linear-bi · [Teams thread](url) · [PD](url)
    ☐ RPTNG_FACT_DR_SLS_ORDR — USER_SUSPENDED — Create ADINC + assess SLA · [PRODPS thread](url)
```

Use `oncall_items_to_task_tree()` from `parse_oncall_log.py` → single parent dict with `children[]`, then `task_to_xml(parent)`.

**Reduced child format** (1–2 lines each):

```
{Title} — {Next action(s)} · [SKRULL-8718](url) · [Teams thread](url) · [PD](url)
```

- **Title:** short table name (e.g. `sne_identity Long Run`, `LDB agg up delivery context`)
- **Next action:** cleaned from table/detail (strip `**`, ticket refs in action text)
- **Links:** up to 4 relevant links from item detail — Jira first, then Teams, then PD
- Use **`raw`** field from each child when building the task tree (not plain `text`)

**Daily log #4:** Skip daily-log line `Follow up with open Oncall items` when synthesizing the oncall parent (avoids duplicate parent). The parent title matches daily-log #4 by design.

**Manual fallback** (if script unavailable): grep `agent-transcripts` for `Oncall log —` or `keep a log during the day of my oncall activity`; use the latest `## Open items` block.

For each pending oncall **child**, compare against carried-over milestones **and daily-log items already queued** using normalized text similarity (see [reference.md](reference.md#similar-item-detection-askquestion)).

| Match | Action |
|-------|--------|
| Parent already exists (same title) | **Replace** parent subtree with updated children from latest log |
| Child clearly distinct from all existing milestones | **Add** under oncall parent |
| Child similar to an existing top-level milestone (≥72% overlap) | **AskQuestion**: Replace existing / Add under oncall parent / Skip |
| Exact duplicate child | Skip |

Same **AskQuestion** dedup rules as Step 4 (Replace / Add / Skip).

---

### Step 6 — Assemble Milestones/Deliverables/Goals Due this Week

Merge into one `ac:task-list` in this order:

1. **Carried-over milestones** from Step 3 (preserve check states, nested trees, `raw_xml`)
2. **Daily log items** from Step 4 not skipped/merged
3. **Oncall parent task** from Step 5 — one `Follow up with open Oncall items` with all open log items as **nested children** (Confluence sibling `<ac:task-list>` after parent `<ac:task>`)

4. **Final prune:** `prune_complete_blocks(body)` — remove any fully-complete trees (no incomplete tasks in block)
5. **Carryover validation (mandatory):** `validate_wfp_carryover.py --previous <prior page JSON> --new <draft HTML>`. If exit code ≠ 0, fix before publish.

**Do not publish** until all **AskQuestion** prompts for similar items are resolved **and** carryover validation passes.

Report in preview:
- Carried: N | Dropped (completed): N | Added from daily log: N | Oncall children under parent: N | Skipped duplicates: N

---

### Step 7 — Personal Goals (rules 5 & 6)

From parsed **Personal Goals** table:

| Achieved Date | Action |
|---------------|--------|
| Empty | **Retain** row (renumber `#`) |
| Filled | **Remove** from table; add to Accomplishments (Step 8) |

Append any **user-provided Personal Goals** as new rows with today's date as Set Date.

Preserve: Goal Description, Type, Set Date, Carryover Reason, Carried From.

---

### Step 8 — Team Goals (rules 7 & 8)

Same rules as Personal Goals, but use **Team** column instead of Type.

Append user-provided Team Goals as new rows.

---

### Step 9 — Append-only sections (rule 9)

These sections **keep all existing content** — never remove items:

- Important Touch-Points/Interfaces Over the Next Two Weeks
- Potential Problems or Escalations this Week
- Non-Project Commitments
- Other Comments/Thoughts/Issues/Concerns to Discuss in 1:1 this Week

**Append** any user-provided additions. Copy sidebar blocks (DAchieve Yearly/Quarterly, Work Schedule, PTO) from previous plan unless user supplies updates.

---

### Step 10 — Accomplishments last week (rule 10)

**Remove** every item from the previous plan's Accomplishments section.

**Rebuild** from items completed since the previous plan:

1. **Milestones** newly checked (compare previous `milestones` vs carryover — items in `milestones_completed` that were incomplete on the prior published plan)
2. **Personal Goals** that had Achieved Date filled this cycle
3. **Team Goals** that had Achieved Date filled this cycle
4. **Daily log items** newly crossed out (`~~text~~`) since the previous focus plan

Output as a fresh numbered `<ol>`. Deduplicate near-identical lines.

---

### Step 11 — Validate carryover (mandatory gate)

```bash
python ~/.cursor/skills/focus-plan/scripts/validate_wfp_carryover.py \
  --previous <prior-wfp-page.json> \
  --new <draft-body.html> \
  --json
```

**Do not publish** if `ok` is false. See [Carryover invariants](#carryover-invariants-mandatory--do-not-skip).

---

### Step 11b — Spelling (rule 11)

Before publish, fix spelling and typos on **all** retained and new text (milestones, goals, bullets, accomplishments). Common fixes in [reference.md](reference.md#spelling-fixes-common).

---

### Step 11c — Confluence editable dates (mandatory for new tasks)

Confluence milestone due dates must use **editable calendar fields**, not plain text.

**Storage format** (from existing plans like [2026-08-03 focus plan](https://disney-enterprise.atlassian.net/wiki/spaces/APSW/pages/2898825427)):

```html
<time datetime="2026-08-24" local-id="2834a7a1485f" />
```

| Source | Rule |
|--------|------|
| Carried milestones | Keep existing `<time>` tags from `raw_xml` (already editable) |
| New daily-log / oncall items with dates | Run through `scripts/confluence_dates.py` → `format_task_body_inner()` |
| `(ongoing weekly effort)` tasks | Roll `<time datetime>` to **Thursday** of the target plan week via `roll_weekly_effort_dates()` |

**Detect dates in plain text:** `Aug 24`, `August 24, 2026`, `2026-08-24`, `due Aug 24`, `by Aug 6, 2026` → convert to `<time datetime="YYYY-MM-DD" local-id="…" />`.

**Never** leave plain-text month/day in newly generated milestone XML. Use `task_to_xml(..., plan_monday=date.fromisoformat("YYYY-MM-DD"))` so year inference uses the plan week.

---

### Step 11d — Hyperlinks (mandatory for daily log / oncall items)

Daily-log **`raw`** markdown and oncall log URLs must become clickable Confluence links.

| Link type | Output |
|-----------|--------|
| `[SKRULL-8785](https://deept.atlassian.net/browse/...)` | Jira macro |
| `[Teams chat/message/thread](https://teams.microsoft.com/...)` | `<a href="...">Teams chat</a>` |
| `[Google Slides](https://docs.google.com/...)` | `<a href="...">Google Slides</a>` |
| `[email](mailto:...)` | `<a href="mailto:...">...</a>` |

Use `format_task_body_inner(item["raw"], plan_monday)` or `task_to_xml({"raw": item["raw"], ...})`. See [confluence_links.py](scripts/confluence_links.py).

---

### Step 12 — Preview and publish

**AskQuestion** before writing to Confluence:

1. Proposed **title** and **parent**
2. Milestones assembly summary (carried / dropped / added from **daily log** / added from **oncall** / skipped)
3. **`validate_wfp_carryover.py` result** (must be OK)
4. List any **unresolved similar-item** conflicts (must be zero)
5. Personal/Team goals retained vs accomplished vs new
6. Accomplishments preview (first 5 items)
7. Confirm create vs update

On approval:

```json
CallMcpTool user-confluence-disney confluence_create_page
{
  "space_key": "APSW",
  "title": "YYYY-MM-DD- Fernando Rivero",
  "parent_id": "197569776",
  "body": "<cloned-and-updated storage HTML>"
}
```

Or `confluence_update_page` if the page already exists.

Report the Confluence URL when done.

---

## Quick example

**Previous plan milestones:**
- ☑ Request support bot for SKRULL
- ☐ Follow up with ADINC bot dropdown forms
- ☐ SLA Dashboard demo → ☑ ADM SLAs, ☑ ODS SLAs, ☐ ADM shared, ☐ ODS shared

**Next plan milestones carry:**
- Follow up with ADINC bot dropdown forms
- SLA Dashboard demo (full nested tree, mixed checks preserved)

**Daily log adds:** all 18 open items from `daily-log.md`; "Follow up with MSTR on 2-year contract renewal" → AskQuestion vs existing "Follow up with MSTR on renewal process".

**Oncall log adds:** nested under `Follow up with open Oncall items` — 3 children from latest Open items snapshot.

**Personal goal** "Explore DBX CLI…" with Achieved Date Jul 17 → removed from table, added to Accomplishments.

---

## Additional resources

- Confluence IDs, MCP payloads, oncall log extraction: [reference.md](reference.md)
- Parser script: [scripts/parse_focus_plan.py](scripts/parse_focus_plan.py)
- Milestone carryover / nesting: [scripts/milestone_carryover.py](scripts/milestone_carryover.py)
- Pre-publish carryover validation: [scripts/validate_wfp_carryover.py](scripts/validate_wfp_carryover.py)
- Confluence editable dates: [scripts/confluence_dates.py](scripts/confluence_dates.py)
- Confluence links (Teams, Jira, etc.): [scripts/confluence_links.py](scripts/confluence_links.py)
- Oncall log parser: [scripts/parse_oncall_log.py](scripts/parse_oncall_log.py)
