---
name: confluence-adinc-history
description: >-
  Documents a resolved ADINC Jira ticket to Confluence Incident History after
  validating closure status and RCA in General → Notes (customfield_10253).
  Confirms monthly folder and page title, optionally enriches from PagerDuty
  (PD_ID), and creates a page matching ADSO formatting. Use when the user asks
  to document RCA, publish an incident to Confluence, or create an Incident
  History page for ADINC-XXX.
---

# ADINC → Confluence Incident History

Publish a **closed** ADINC ticket as a Confluence RCA page under [Incident History](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192843672/Incident+History).

**Write workflow:** creates Confluence pages (and optionally a monthly folder). Does **not** close Jira tickets or modify ADINC fields unless the user explicitly asks after documentation.

Companion skills: `jira-adinc-audit`, `dataops-pd-incident-analysis`, `dataops-pd-incidents`, and **Oncall activity log** (session agent log — search prior chat transcripts).

**RCA field:** all reads use [adinc-jira-notes.md](../adinc-jira-notes.md) — General tab → Notes → `customfield_10253`.

## Configuration

| Setting | Value |
|---------|--------|
| Jira project | `ADINC` on `https://deept.atlassian.net` |
| Jira MCP | `user-jira-server` |
| Notes (RCA) | See [adinc-jira-notes.md](../adinc-jira-notes.md) |
| Confluence space | `ADSO` |
| Incident History root | page id `192843672` |
| Monthly folder pattern | `YYYYMM` (e.g. `202607`) |
| PagerDuty MCP | `user-pagerduty-mcp-manual` (optional, when `PD_ID` present) |

Always call `GetMcpTools` before `CallMcpTool`.

**PagerDuty identity (when `PD_ID` present):** [pagerduty-incident-identity/reference.md](../pagerduty-incident-identity/reference.md) — `get_incident` + gate before using PD data in the Confluence page.

## Input

Accept **one** ADINC key: `ADINC-791`, `791`, or a browse URL `https://deept.atlassian.net/browse/ADINC-791`.

Normalize to `ADINC-{number}`.

## Workflow overview

```
Fetch ADINC
  → Gate 2: Notes has RCA?             (evaluate early for close prompt)
  → Gate 1: Status Done/Closed?        (if open + RCA ready → prompt to close — STOP)
  → Gate 4: Description placeholders?  (prompt fixes — STOP until resolved)
  → Step 5: Cross-agent enrichment       (Teams, PD, DBX — mandatory search)
  → Step 6: Resolve monthly folder
  → Step 6b: Global duplicate check        (Incident History-wide — STOP if exists)
  → Step 7: Preview folder + title + enrichment → AskQuestion → create or update
  → Step 8: Create or update Confluence page
  → Report links
```

Copy this checklist and track progress:

```
- [ ] Step 1: Fetch ADINC ticket
- [ ] Step 2: Gate — RCA in Notes (evaluate before close prompt)
- [ ] Step 3: Gate — status closed
- [ ] Step 4: Gate — description placeholders
- [ ] Step 5: Cross-agent enrichment (Teams, PD, DBX)
- [ ] Step 6: Resolve monthly folder
- [ ] Step 6b: Global duplicate check (Incident History-wide)
- [ ] Step 7: Preview folder + title + enrichment → user confirms
- [ ] Step 8: Create or update Confluence page
```

---

### Step 1 — Fetch ADINC ticket

Follow [adinc-jira-notes.md](../adinc-jira-notes.md) **Read** section:

```json
CallMcpTool user-jira-server jira_get_issue
{
  "issue_key": "ADINC-791",
  "fields": "summary,status,created,updated,description,customfield_10253,resolution"
}
```

Parse the **10 description fields** — see [reference.md](reference.md#description-fields). Preserve field names and order when suggesting updates.

Extract Notes with `get_adinc_notes()` logic from [adinc-jira-notes.md](../adinc-jira-notes.md). If text is still missing but `cf[10253] is not EMPTY`, ask the user to paste **General → Notes** — do **not** invent RCA.

---

### Step 2 — Gate: RCA must exist in Notes

Use [adinc-jira-notes.md](../adinc-jira-notes.md) **Validation** rules on `customfield_10253`.

**Missing / invalid Notes** — stop and report:

| Condition | Action |
|-----------|--------|
| null, empty, whitespace | STOP — "Add RCA to General → Notes before documenting." |
| `#N/A`, `N/A`, `NA` (alone) | STOP |
| `RCA:` or `RCA` with no substance after | STOP |
| Substantive text (typically starts with `RCA:`) | Pass |

If Notes pass, extract the RCA text for the Confluence **Root Cause Analysis Summary** section. Keep this text for the Step 3 close prompt when the ticket is still open.

---

### Step 3 — Gate: ticket must be closed

**Closed statuses:** `Done`, `Closed`, `Resolved`.

**Open statuses:** `Open`, `In Progress`, `To Do`, `Reopened`, `Blocked`.

If status is **not** closed, **STOP** workflow automation and use **`AskQuestion`** for user input (do not ask the user to type "closed" or "yes" in chat).

#### Variant A — Open ticket, RCA **ready** (Step 2 passed)

Use when Notes contain substantive RCA. **Do not** block on `N/A` for `EXTERNAL` or `MISSED_SLA` — those are valid values.

**1. Show context** (markdown in chat before the question):

```markdown
## Close ADINC to publish RCA

**Ticket:** [ADINC-798](https://deept.atlassian.net/browse/ADINC-798)
**Current status:** Open
**RCA in General → Notes:** ✅ Ready

**RCA preview:** {Notes RCA — first 2 sentences}

**Proposed Confluence title:** `{proposed_title}`
**Folder:** `{YYYYMM}`
```

**2. Ask to close** — call `AskQuestion` with radio-style YES / NO:

```json
{
  "title": "ADINC-798 — Close ticket?",
  "questions": [{
    "id": "close-ticket",
    "prompt": "Close the ticket?",
    "options": [
      { "id": "yes", "label": "Yes — close ADINC-798 in Jira now (Recommended)" },
      { "id": "no", "label": "No — I'll close it manually" }
    ]
  }]
}
```

**3. Handle answer:**

| Answer | Action |
|--------|--------|
| **Yes** | `jira_get_transitions` → `jira_transition_issue` to **Done** → re-fetch issue → continue to Step 4 |
| **No** | STOP — tell user to close the ticket in Jira, then re-run this skill |

Do **not** create the Confluence page or show the final create prompt until Steps 5–7 complete.

#### Variant B — Open ticket, RCA **missing** (Step 2 failed)

```markdown
## RCA required before documenting

**Ticket:** [ADINC-798](https://deept.atlassian.net/browse/ADINC-798)
**Current status:** Open
**RCA in General → Notes:** ❌ Missing or placeholder

Add a substantive RCA to **General → Notes** (`RCA: …`) before closing and documenting this incident.
```

If status **is** closed, continue to Step 4 (skip close `AskQuestion`).

Skip cancelled tickets (`resolution = Cancelled`) — inform the user and stop.

---

### Step 4 — Gate: description placeholder fields

Scan **every** parsed description field value (case-insensitive) for placeholder patterns:

| Pattern | Examples |
|---------|----------|
| Waiting for RCA | `Waiting for RCA`, `waiting for RCA`, `Waiting for RCA ` |
| TBD | `TBD`, `tbd` |
| Blank | field present but empty after `:` |
| Obvious stub | `Team names`, `ID(s), Links` as sole value in a real field |

**Valid values (do not flag):** `NA` / `N/A` on `INC_NUMBER`, `DAG`, `TASK`, `PD_ID`, `PIPELINE`, `SOURCE_SYSTEM`, **`EXTERNAL`**, **`MISSED_SLA`**.

**Invalid `NA` / `N/A`:** only on `TEAM` and `ISSUE_CATEGORY`.

When any field matches:

1. List each offending field with its current value.
2. For each, suggest a replacement derived from Notes, summary, or PagerDuty (Step 5).
3. Ask the user what value to use for each field (or confirm suggested values).
4. **STOP** — do not create the Confluence page until placeholders are resolved **or** the user confirms they will update Jira separately and explicitly approves documenting with the suggested values shown in the preview.

Common stale field: `ISSUE_CATEGORY: Waiting for RCA` on already-closed tickets — suggest the category from Notes (e.g. `Data - Upstream Delay`, `Vendor - API`, `Spark`).

---

### Step 5 — Cross-agent enrichment (mandatory)

Before building the Confluence page, **search all available sources** for references to the ADINC key, linked PD incident, DAG, or summary keywords. Do not leave Teams Thread(s) as `—` when a link exists in any source.

#### Sources (check all)

| Source | How to search | Use for Confluence |
|--------|---------------|-------------------|
| **Oncall activity log** | Grep session / prior agent transcripts for `ADINC-{n}`, ticket URL, DAG name, `teams.microsoft.com` | **Teams Thread(s)**, timeline, follow-up context |
| **Jira Activity comments** | `jira_get_comments` on the ADINC ticket — look for `teams.microsoft.com`, PD links posted by automation | **Teams Thread(s)**, External References |
| **dataops-pd-incident-analysis** | If `PD_ID` present: follow that skill (`get_incident`, identity gate, `list_incident_notes`, DBX via `ads-databricks`) | Investigation, Problem details, PD link |
| **dataops-pd-incidents** | `list_incidents` around ticket `created` date; match by PD# or job/DAG in title — **filter** `incident_number == PD_ID`, never `incidents[0]` | PD link, DBX workspace/run URLs, urgency |
| **PagerDuty MCP** (direct) | When `PD_ID` not `NA`: `get_incident` or `GET /incidents/{PD_ID}` + **identity gate** + `list_incident_notes` | Agent summary, timestamps, external refs |

#### Oncall activity log search

The Oncall activity log is a **session agent** (not a separate skill file). Search:

1. Current conversation history for entries mentioning the ADINC key.
2. Prior agent transcripts under `~/.cursor/projects/*/agent-transcripts/` — grep for `ADINC-{n}`, browse URL, or DAG.

Extract **Teams thread URL(s)** with channel label when present (e.g. `ads-data-bi-support`).

#### Enrichment rules

- **Teams Thread(s):** Include every distinct `teams.microsoft.com` URL found — prefer Oncall log primary thread, plus Jira auto-posted links if different channels.
- **External References:** PD incident URL, DBX run links, vendor tickets — from PD/dataops skills.
- **Investigation & Findings:** Supplement from PD agent notes and Oncall log — **never override** Jira Notes RCA.
- **Do not invent** links or investigation steps. If no Teams thread found after searching all sources, use `—` and note "not found in Oncall log, Jira comments, or PD notes."

Record an **Enrichment summary** table for Step 7 preview:

```markdown
| Source | Found | Used in page |
|--------|-------|--------------|
| Oncall activity log | Teams thread URL | Teams Thread(s) |
| Jira comments | 2 auto-posted links | — (duplicate channel) |
| PD / dataops | skipped (PD_ID=NA) | — |
```

If `PD_ID` is `NA`, still run Oncall log + Jira comments search. Optionally run `dataops-pd-incidents` for the incident date window to catch related PD alerts by DAG name in title.

---

### Step 6 — Resolve monthly folder

Derive folder name from incident date:

1. Prefer **ticket created date** (`created` field) → `YYYYMM`.
2. If user specifies a different date, use that.

Check for existing folder under Incident History:

```json
CallMcpTool user-confluence-disney confluence_get_page_children
{ "page_id": "192843672" }
```

| Outcome | User message |
|---------|--------------|
| Folder `YYYYMM` exists | "Page will be created under [YYYYMM]({folder_url})." Record `parent_id` = that page's id. |
| Folder missing | "Monthly folder `{YYYYMM}` does not exist. Proposed new folder name: **{YYYYMM}**." Ask user to confirm folder creation. |

**Create missing folder** (only after user confirms):

```json
CallMcpTool user-confluence-disney confluence_create_page
{
  "space_key": "ADSO",
  "title": "202608",
  "body": "",
  "parent_id": "192843672"
}
```

Use returned page id as `parent_id` for the incident page.

---

### Step 6b — Global duplicate check (mandatory)

**Before** preview or create, search **all of Incident History** — not just the target monthly folder. A duplicate may live under a different `YYYYMM` folder or use a different date prefix in the title (e.g. `20260722` vs `20260723` for the same ADINC).

#### Search keys

Derive from the Jira ticket:

| Jira field | Search token | Example |
|------------|--------------|---------|
| Ticket key | `ADINC-{n}` | `ADINC-798` |
| `INC_NUMBER` (when not `NA`) | `INC{number}` | `INC29281148` |

#### CQL search (primary)

Search under [Incident History](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192843672/Incident+History) root (`192843672`):

```json
CallMcpTool user-confluence-disney confluence_search_content
{
  "cql": "space = ADSO AND type = page AND ancestor = 192843672 AND title ~ \"ADINC-798\"",
  "limit": 25
}
```

When `INC_NUMBER` is not `NA`, also run:

```json
{
  "cql": "space = ADSO AND type = page AND ancestor = 192843672 AND title ~ \"INC29281148\"",
  "limit": 25
}
```

Merge results; dedupe by page `id`.

#### Fallback (if zero results)

Broaden to full ADSO space (catches pages misplaced outside Incident History):

```json
{
  "cql": "space = ADSO AND type = page AND title ~ \"ADINC-798\"",
  "limit": 25
}
```

#### If any page matches — STOP create

Show every match:

```markdown
## Existing Confluence page(s) for ADINC-798

| Title | Page link | Last updated by |
|-------|-----------|-----------------|
| 20260722 - ADINC-798 - [AP][ADM][Measurement]... | [open]({url}) | Tulasi Agina |
| 20260723-ADINC-798-[AP][ADM][Measurement]... | [open]({url}) | Fernando Rivero |

**Do not create another page** for this ticket unless the user explicitly requests a duplicate.
```

Call **`AskQuestion`**:

```json
{
  "title": "ADINC-798 — Page already exists",
  "questions": [{
    "id": "duplicate-action",
    "prompt": "A Confluence page already exists for this ADINC ticket. What should I do?",
    "options": [
      { "id": "update-first", "label": "Update the existing page with current RCA/enrichment (Recommended)" },
      { "id": "cancel", "label": "Cancel — I'll pick the primary page manually" }
    ]
  }]
}
```

If multiple pages exist and user chooses **Update**, ask which page is primary (second `AskQuestion` listing each page title, or let user specify in chat).

| Answer | Action |
|--------|--------|
| **Update** | Skip create → Step 7 preview in **update mode** → Step 8 `confluence_update_page` on chosen `page_id` |
| **Cancel** | STOP |

Record `existing_page_id` when updating; pass to Step 8.

#### If no page matches — proceed

Continue to Step 7 (create new page).

**Never** rely on `confluence_get_page_children` on the monthly folder alone — duplicates across months or date prefixes will be missed (see [reference.md](reference.md#duplicate-page-detection)).

---

### Step 7 — Preview folder, title, enrichment — then confirm

**Required before Step 8:** show the user exactly where the page will live, what it will be named, and what enrichment was applied. Then use **`AskQuestion`**.

#### 7a — Build proposed title

Build title per [reference.md](reference.md#page-title-format):

```text
YYYYMMDD-{INC|ADINC}-{ID}-[{AP}][Team][SubTeam/Pipeline]{DAG or context}- {short description}
```

#### 7b — Duplicate check

Handled in **Step 6b** (global CQL search). Do not skip. If Step 6b found pages, Step 7 runs in **update mode** (show existing title + proposed changes, not a new title in a new folder).

#### 7c — Mandatory preview (show in chat before AskQuestion)

```markdown
## Ready to document — review before create

**Parent folder:** [202607](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/192843692/202607)
**Folder path:** Incident History → 202607

**Proposed page title:**
`20260723-ADINC-798-[AP][ADM][Measurement] ap_addr_measurement_adlog_all_publishers_prod - missing D+ data for 7/21/26 in fact_ad_delivery`

### Enrichment applied

| Field | Value |
|-------|-------|
| Teams Thread(s) | [ads-data-bi-support thread]({teams_url}) |
| External References | {pd_url or —} |
| RCA source | Jira General → Notes |

### Page sections (from Notes + enrichment)

- Summary table · Problem details · RCA · Investigation · Resolution · Actions
```

#### 7d — AskQuestion to create or update

Only after showing 7c.

**Create** (Step 6b found no duplicate):

```json
{
  "title": "ADINC-798 — Create Confluence page?",
  "questions": [{
    "id": "create-page",
    "prompt": "Create this Incident History page?",
    "options": [
      { "id": "proceed", "label": "Proceed — create page (Recommended)" },
      { "id": "cancel", "label": "Cancel" }
    ]
  }]
}
```

**Update** (Step 6b found existing page):

```json
{
  "title": "ADINC-798 — Update existing page?",
  "questions": [{
    "id": "update-page",
    "prompt": "Update the existing Incident History page with current RCA and enrichment?",
    "options": [
      { "id": "proceed", "label": "Proceed — update existing page (Recommended)" },
      { "id": "cancel", "label": "Cancel" }
    ]
  }]
}
```

Proceed to Step 8 **only** when user selects **Proceed**.

---

### Step 8 — Create or update Confluence page

1. Fetch one recent page from the same month as a formatting reference (optional for **create**; skip for **update** if existing page is the template):

```json
CallMcpTool user-confluence-disney confluence_get_page
{
  "page_id": "<sibling_or_existing_page_id>",
  "expand": "body.storage"
}
```

2. Build `body` using the storage-format template in [reference.md](reference.md#confluence-page-template). Populate from:
   - Parsed description fields → Summary table
   - Notes (`customfield_10253`) → Root Cause Analysis Summary
   - **Step 5 enrichment** → Teams Thread(s), External References, Investigation supplements
   - Summary + Notes + PD/Oncall data → Problem details, Resolution, Actions

3. **Create** (Step 6b found no duplicate):

```json
CallMcpTool user-confluence-disney confluence_create_page
{
  "space_key": "ADSO",
  "title": "<proposed_title>",
  "body": "<storage_html>",
  "parent_id": "<monthly_folder_id>"
}
```

4. **Update** (Step 6b found existing page — use `existing_page_id`, fetch current `version.number` first):

```json
CallMcpTool user-confluence-disney confluence_update_page
{
  "page_id": "<existing_page_id>",
  "title": "<existing_title_or_user_confirmed_title>",
  "body": "<storage_html>",
  "version": <current_version_number + 1>
}
```

5. Return the page URL from `_links.webui`.

---

## Output

After successful creation:

```markdown
## Incident documented

| Item | Link |
|------|------|
| ADINC ticket | https://deept.atlassian.net/browse/ADINC-791 |
| Confluence RCA | {new_page_url} |
| Folder | {monthly_folder_url} |
```

If stopped at a gate, state clearly which gate failed and what the user must do next.

---

## Do not

- Document incidents when the ADINC ticket is not **Done/Closed/Resolved**.
- Document without substantive **General → Notes** RCA (`customfield_10253`).
- Proceed past placeholder description fields without user input or explicit approval.
- Create a Confluence page without **Step 7 preview** (folder path + title + enrichment table) and **AskQuestion Proceed**.
- Use Jira Comments as the **RCA source** (Comments are OK for Teams links in Step 5 enrichment).
- Skip Step 5 cross-agent search when Teams or PD links may exist in Oncall log or Jira comments.
- Invent investigation details, PD timelines, or resolution steps not supported by Notes, description, or PD notes.
- Create a Confluence page without **Step 6b** global duplicate check under Incident History.
- Create duplicate pages for the same ADINC/INC when Step 6b found existing pages (update instead, or cancel).
- Modify Jira or PagerDuty unless explicitly asked.

## Additional resources

- **ADINC Notes (RCA) field:** [adinc-jira-notes.md](../adinc-jira-notes.md)
- Description fields, title rules, HTML template: [reference.md](reference.md)
- ADINC audit / Notes rules: `jira-adinc-audit`
- PD incident analysis: `dataops-pd-incident-analysis`
- PD incident listing: `dataops-pd-incidents`
- Enrichment source details: [reference.md](reference.md#cross-agent-enrichment)
