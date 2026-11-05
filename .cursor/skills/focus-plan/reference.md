# Focus Plan — Reference

## Confluence constants

| Setting | Value |
|---------|-------|
| Parent page | [F. Rivero's Focus Plans](https://disney-enterprise.atlassian.net/wiki/spaces/APSW/pages/197569776) — id `197569776` |
| Space key | `APSW` |
| Owner name suffix | ` Fernando Rivero` |
| Title pattern | `YYYY-MM-DD- Fernando Rivero` (Monday of the week) |
| Optional title suffix | ` (PTO …)`, ` (on PTO)`, ` (Strategy World Week)`, etc. |

## Week-start date

Use **Monday** of the target week in `YYYY-MM-DD` format.

Example: if today is Mon Aug 10, 2026 → title `2026-08-10- Fernando Rivero`.

Before creating, search for an existing page with the same title under parent `197569776`. If found, **update** (`confluence_update_page`) instead of create.

## Page layout (2026 template)

Two-column `ac:layout` with `two_right_sidebar`:

**Left — MAIN FOCUS info panel**
1. Milestones/Deliverables/Goals Due this Week — `ac:task-list`
2. Personal Goals — table (8 rows)
3. Team Goals I'm Setting This Week — table (8 rows)
4. Important Touch-Points/Interfaces Over the Next Two Weeks — bullets
5. Potential Problems or Escalations this Week — bullets
6. Non-Project Commitments — `ac:task-list`
7. Accomplishments last week — ordered list
8. Other Comments/Thoughts/Issues/Concerns to Discuss in 1:1 this Week — ordered list

**Right sidebar**
1. DAchieve Yearly Commitments — copy from previous plan unchanged
2. DAchieve Quarterly Commitments — copy from previous plan unchanged
3. Work Schedule this Week / Future Planned Time Off — copy + user updates

## Milestones carryover rules

| Case | Action |
|------|--------|
| Top-level task **complete**, no incomplete children | **Drop** |
| Top-level task **incomplete** | **Keep** |
| Parent with nested children; **any** task in tree incomplete | **Keep entire subtree** with original check states (including checked children) |
| Parent complete, all children complete | **Drop** entire subtree |
| Daily log crosses out a **related** line (different wording) | **Keep** incomplete WFP tree — log line is not proof all subtasks done |
| Text appears under prior **Accomplishments** | **Keep** incomplete milestone; accomplishments guard applies to **re-adding** daily-log lines only |

**Nested carryover example** (parent incomplete, mixed children — carry entire tree):

```
☐ Request Tags for ADM and BI OnCall/ Teams for incident reporting
    ☑ Review Virtual tag for ADM
    ☐ Test Virtual tag once created
    ☐ Apply Virtual Tag to dashboards
```

→ Carry all four lines exactly as shown (parent + sibling `<ac:task-list>`, checked children preserved).

**Implementation:** `scripts/milestone_carryover.py` — balanced tag extraction, sibling-list merge, `task_tree_to_html()` rebuild. Never use first-match `find('</ac:task-list>')` on the milestones section.

| Helper | Purpose |
|--------|---------|
| `carryover_html_blocks(body)` | Incomplete trees only |
| `is_fully_complete_block(block)` | True only when no `incomplete` status in merged tree |
| `filter_carried_blocks_by_daily_done(blocks, done_items)` | **Only** way to drop carried blocks for daily-log done lines (requires full tree complete) |
| `completed_block_texts_from_html(body)` | All fully-complete milestone texts (for daily-log skip + accomplishments) |
| `prune_complete_blocks(body)` | Post-build safety net — drop complete-only trees |
| `remove_blocks_matching_completed(body, texts)` | Remove re-added items matching prior completions (skips incomplete trees) |
| `matches_prior_completed(text, texts)` | Dedup vs a list of prior completion texts |
| `accomplishments_texts_from_html(body)` | Prior plan Accomplishments lines (for dedup guard) |
| `matches_prior_done(text, prior_plan_body)` | Dedup daily-log item vs prior milestones **and** accomplishments (**add** path only) |

### Pre-publish validation (mandatory)

```bash
python ~/.cursor/skills/focus-plan/scripts/validate_wfp_carryover.py \
  --previous prev-wfp.json \
  --new draft.html
```

Ensures every incomplete task label from the **previous** WFP milestones still exists on the draft (exit 0 = OK). Run after assembly, before Confluence write. Reference incident: **DBX CICD** tree dropped when daily log #34 was done but three plan subtasks were still open.

**Anti-patterns:** regex `patch_wfp_*.py` deleting `<ac:task>` trees; local `should_drop_block` without `is_fully_complete_block`; using `matches_prior_done` to filter Step 3 carryover.

Use `scripts/parse_focus_plan.py` for deterministic parsing; preserve Jira macros and links in task text when rebuilding XML.

## Personal / Team goals table columns

| Column | Carryover rule |
|--------|----------------|
| # | Renumber 1…N after filtering |
| Goal Description | Keep if **Achieved Date** empty |
| Type / Team | Keep as-is |
| Set Date | Keep as-is |
| Achieved Date | Empty = active; filled = accomplished → move to Accomplishments |
| Carryover Reason | Keep as-is |
| Carried From | Keep as-is |

## Cloud daily log — Daily activity and todo log

**Repo:** [fcrivero/CursorDataOpsAnalytics](https://github.com/fcrivero/CursorDataOpsAnalytics) (personal **github.com**)

**Cloud Agent name:** Daily activity and todo log (remote)

| File | Purpose |
|------|---------|
| `daily-log.md` | Work DataOps / Analytics todos — **merge ALL open items into Milestones** |
| `july-log.md` | Frozen monthly archive |
| `personal-todo.md` | Personal/life todos — **never** merge into focus plan |

### Fetch paths (in priority order)

```bash
python ~/.cursor/skills/focus-plan/scripts/fetch_daily_log.py --output daily-log.md
```

Fetches **all sources** (local clone + `git pull`, GitHub API, raw GitHub), picks the freshest by `next_item_number` / `last_updated`, and reports staleness. **Required before every focus-plan build.**

```bash
python ~/.cursor/skills/focus-plan/scripts/fetch_daily_log.py \
  --warn-if-before 2026-09-14 --json-summary daily-fetch.json
```

| Summary field | Meaning |
|---------------|---------|
| `stale: true` | Log `last_updated` is too old — stop and ask user to push from Cloud Agent |
| `sources_mismatch` | Local vs remote differ (should not happen after pick) |
| `remote_sha` / `remote_commit_date` | Latest GitHub commit for `daily-log.md` |
| `next_item_number` | Cross-check with user — if lower than their Cloud Agent view, GitHub is behind |

Manual fallbacks:

1. Local clone (git pull first):
   `C:\Users\rivef104\Documents\AI\Cloud\CursorDataOpsAnalytics\daily-log.md`
2. GitHub CLI — **must use personal host**:
   ```powershell
   gh api --hostname github.com repos/fcrivero/CursorDataOpsAnalytics/contents/daily-log.md
   ```
3. Raw GitHub:
   `https://raw.githubusercontent.com/fcrivero/CursorDataOpsAnalytics/main/daily-log.md`

Enterprise `gh` default (`github.twdcgrid.net`) will **not** find this repo.

### Open vs done

| Line pattern | Milestones | Accomplishments |
|--------------|------------|-----------------|
| `N. ~~text~~` | Skip | Candidate if newly done |
| `N. text` (no strikethrough) | **Add all** (use **`raw`** for HTML) | — |
| Summary `**Open:**` | Cross-check | — |

### Merge into Milestones (mandatory)

For **each** open daily-log item:

1. Compare against existing milestones (carried from previous plan + already-added items).
2. **Exact duplicate** → skip.
3. **Similar** (≥72% token overlap or substring) → **AskQuestion**: Replace / Add / Skip.
4. **Distinct** → add as new incomplete task.

AskQuestion example:

```
Daily log:     "Follow up on SLA/BI Performance Dashboard and Subscription"
Milestone:     "SLA Dashboard demo (Developers)"

Similar — Replace, Add, or Skip?
```

Skip meta items like "Create Focus plan" when generating the plan.

Parse helper:

```bash
python ~/.cursor/skills/focus-plan/scripts/parse_daily_log.py --input daily-log.md --output daily-parsed.json
```

Each open item includes `raw` (markdown with links), `text` (plain, for dedup), and `links` (structured).

---

## Confluence hyperlinks (Teams, Jira, email, docs)

When merging daily-log or oncall items into milestones, **preserve all URLs** as clickable Confluence links.

### Daily-log markdown → Confluence

| Source in `daily-log.md` | Confluence storage |
|--------------------------|-------------------|
| `[Teams chat](https://teams.microsoft.com/...)` | `<a href="https://teams.microsoft.com/...">Teams chat</a>` |
| `[SKRULL-8785](https://deept.atlassian.net/browse/SKRULL-8785)` | Jira macro (`ac:structured-macro ac:name="jira"`) |
| `[ADIA-1800](https://deept.atlassian.net/browse/ADIA-1800)` | Jira macro |
| `[Google Slides](https://docs.google.com/...)` | `<a href="...">Google Slides</a>` |
| `[email](mailto:...)` | `<a href="mailto:...">email</a>` |

### Implementation

1. Parse daily log → use **`raw`** field per open item (never plain `text` alone for new milestones).
2. Call `format_task_body_inner(raw, plan_monday)` — handles links **and** editable dates.
3. Pass to `task_to_xml({"raw": item["raw"], ...})` or set `body_html` from formatter output.

```bash
python ~/.cursor/skills/focus-plan/scripts/confluence_links.py --text "[Teams chat](https://teams.microsoft.com/l/chat/...)"
```

### Oncall activity log

If oncall items include URLs, format milestone text with markdown links before `format_task_body_inner()`. Example:

```
Check RCA for ADINC-793 — [Teams thread](https://teams.microsoft.com/l/message/...)
```

---

## Oncall activity log — pending item extraction

Session agent (not a skill file). Transcripts: `<projects>/c-Users-rivef104-cursor-projects/agent-transcripts/<uuid>/<uuid>.jsonl`.

### Parse script (mandatory)

```bash
python ~/.cursor/skills/focus-plan/scripts/parse_oncall_log.py --output oncall-parsed.json
```

The script:
1. Finds the most recently updated transcript containing `Oncall log`, `Open items`, or `Pending items`
2. Reads the latest `## Open items` / `## Open items remaining` snapshot
3. Parses `| Day | Name | Next action |` table rows (skips closed/`~~` items)
4. Matches each row to its `###` detail section for Jira/Teams/PD links
5. Outputs `open_items[]` with `raw` (compact markdown), `text` (dedup), `links`
6. Builds `parent_task` via `oncall_items_to_task_tree()` — nests all open items under **`Follow up with open Oncall items`**

### Nesting structure (mandatory)

All oncall follow-ups are **children** of one parent milestone (Confluence sibling `<ac:task-list>` pattern):

```
☐ Follow up with open Oncall items
    ☐ {Title} — {Next action} · [links]
    ☐ ...
```

Skip daily-log `#4 Follow up with open Oncall items` when adding the oncall parent (same title — parent comes from oncall log).

### Reduced child format (1–2 lines each)

```
{Title} — {Next action(s)} · [SKRULL-8718](url) · [Teams thread](url) · [PD](url)
```

Examples from Aug 10, 2026 log:

```
sne_identity Long Run — Close after threshold verify · [SKRULL-8718](...) · [Teams thread](...) · [PD](...)
LDB agg up delivery context — Threshold + naming + @oncall-linear-bi · [Teams thread](...) · [PD](...)
RPTNG_FACT_DR_SLS_ORDR — USER_SUSPENDED — Create ADINC + assess SLA · [PRODPS thread](...)
```

Use **`raw`** from each child in `oncall_items_to_task_tree()` → `task_to_xml(parent_task)`. Plain `text` is for dedup only.

```python
from parse_oncall_log import oncall_items_to_task_tree
parent = oncall_items_to_task_tree(result["open_items"])
xml, _ = task_to_xml(parent, plan_monday=plan_monday)
```

### Manual fallback

Grep for `Oncall log —` or `keep a log during the day of my oncall activity`. Prefer the most recently updated transcript. Extract from latest `## Open items` block.

### Dedup with daily log and existing milestones

- **Daily log #4** (`Follow up with open Oncall items`): skip when oncall parent is synthesized (same title).
- **Existing parent** on carried-over plan: replace subtree with latest oncall children.
- **Each child**: compare against all existing milestone text; **AskQuestion** if similar (≥72% overlap).

For each oncall child, compare against existing milestones using similar-item rules below.

## Similar-item detection (AskQuestion)

Applies to **daily log items** and **oncall log items** when merging into Milestones.

Compare normalized tokens between candidate item and existing milestone text. Flag as **similar** when:
- Token overlap ≥ 72%, or
- One normalized string contains the other

Use `AskQuestion` per match:
- **Replace** existing milestone with new wording (from daily log or oncall)
- **Add** as new milestone
- **Skip** new item (keep existing)

**Do not publish** the focus plan while similar-item AskQuestion prompts are unresolved.

## Accomplishments last week

**Remove** all items from the previous plan's Accomplishments section.

**Add** (deduplicated):
1. Milestones marked complete this week (from diff: were incomplete last week → complete now, or newly checked since last publish)
2. Personal goals that gained an Achieved Date since last plan
3. Team goals that gained an Achieved Date since last plan
4. Daily log items newly crossed out (`~~text~~`) since last focus plan

Format as numbered `<ol>` items. Fix spelling on all entries.

## Spelling fixes (common)

| Wrong | Correct |
|-------|---------|
| Confoigure | Configure |
| dashbaord | dashboard |
| remapimng | remapping |
| Souce | Source |
| Histical | Historical |
| but for SKRULL | bot for SKRULL |

Run spell-check pass on all retained and new text before publish.

## Confluence editable dates

Milestone due dates must render as **clickable calendar fields** in Confluence, not plain text.

### Storage format

```html
<span class="placeholder-inline-tasks">DataOps presentation due <time datetime="2026-08-24" local-id="2834a7a1485f" /></span>
```

Inside `<ac:task-body>`, wrap text in `<span class="placeholder-inline-tasks">` and insert self-closing `<time datetime="YYYY-MM-DD" local-id="12-char-hex" />` for each date.

### When to convert

| Case | Action |
|------|--------|
| Carried task with existing `<time>` in `raw_xml` | **Preserve** as-is |
| New task from daily log / oncall with date in text | **Convert** via `format_task_body_inner(text, plan_monday)` |
| `(ongoing weekly effort)` lines | **Roll** date to Thursday of target plan week |

### Plain-text patterns → `<time>`

- `Aug 24`, `August 24`, `Aug 24, 2026`
- `due Aug 24`, `by Aug 6, 2026`
- ISO `2026-08-24`

Year defaults to the plan week's year when omitted.

### Helper

```bash
python ~/.cursor/skills/focus-plan/scripts/confluence_dates.py --text "DataOps presentation due Aug 24" --plan-monday 2026-08-10
```

Pass `plan_monday` into `task_to_xml()` and `rebuild_milestones_html(..., plan_monday=...)`.

## MCP calls

```json
CallMcpTool user-confluence-disney confluence_search_content
{
  "cql": "ancestor = 197569776 AND type = page ORDER BY created DESC",
  "limit": 1,
  "expand": "version"
}
```

```json
CallMcpTool user-confluence-disney confluence_get_page
{
  "page_id": "<latest_id>",
  "expand": "body.storage,version,space"
}
```

```json
CallMcpTool user-confluence-disney confluence_create_page
{
  "space_key": "APSW",
  "title": "2026-08-10- Fernando Rivero",
  "parent_id": "197569776",
  "body": "<ac:layout>...</ac:layout>"
}
```

Save fetched page JSON to a temp file, then:

```bash
python ~/.cursor/skills/focus-plan/scripts/parse_focus_plan.py --input page.json --output parsed.json
```
