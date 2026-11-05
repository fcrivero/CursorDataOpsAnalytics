---
name: pipeline-docs-audit
description: >-
  Audits Confluence pipeline leaf pages against ADSO Data Pipelines structure and
  Pipeline Documentation Standard (metadata, runbook, data quality). Checks placement,
  exact job/DAG page title, section structure, required fields, placeholders, alert
  routing consistency, and duplicate/wrong-space docs. Use when the user asks to audit,
  validate, review, or assess pipeline documentation compliance, uCPM/DBX/Airflow
  runbooks, or Data Pipelines Confluence pages.
---

# Pipeline documentation audit

Audit **pipeline leaf pages** in Confluence against:

- [Data Pipelines Confluence Structure — Standard](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard) (placement + naming)
- [Pipeline Documentation — Standard](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895775777/Pipeline+Documentation+-+Standard) (content template)

**MCP:** `user-confluence-disney` (`confluence_get_page`, `confluence_search_content`, `confluence_get_page_children` as needed).

**Helpers:** [scripts/pipeline_doc_checks.py](scripts/pipeline_doc_checks.py) — title/placeholder/section heuristics (run locally when batching).

**Field lists & path map:** [reference.md](reference.md)

## Configuration

| Setting | Value |
|---------|--------|
| Compliant space | `ADSO` |
| Data Pipelines root | page id `192841195` |
| Browse URL | `https://disney-enterprise.atlassian.net/wiki{webui}` |

## Skill inputs

| Input | Type | Default | Purpose |
|-------|------|---------|---------|
| `audit_scope` | string or list | `all` | Which checks to run (see below) or `all` |
| `page_urls` | list | none | One or more Confluence page URLs to audit |
| `page_ids` | list | none | Confluence page IDs (alternative to URLs) |
| `job_names` | list | none | Search Confluence for pages matching job/DAG names |
| `cql` | string | none | Custom CQL (must scope to pipeline candidates) |
| `subteam_path` | string | none | Audit all leaves under a folder (e.g. `BI → Linear → LDB`) |
| `include_compliant` | boolean | `false` | Include passing pages in output |
| `output_format` | string | `markdown` | `markdown`, `canvas`, or `both` |
| `report_audience` | string | `dev` | `dev` (Keep/Change/Decide) or `dataops` (routing focus) |

### Example invocations

```text
@pipeline-docs-audit audit https://disney-enterprise.atlassian.net/wiki/spaces/DAPPM/pages/871072465/...
@pipeline-docs-audit check ap_asf_unified_cpm_linear_cable_prod
@pipeline-docs-audit audit all pages under ADSO Data Pipelines → BI → Linear → LDB
@pipeline-docs-audit run checks placement, page_title, page_structure on page id 871072465
@pipeline-docs-audit gap audit: monitored jobs vs Confluence (team BI)
@pipeline-docs-audit produce dev-team shareable report for uCPM linear cable page
```

## Audit checks (15)

Run checks requested by `audit_scope`. When `all`, run every check applicable to **leaf pipeline pages**. Skip index-only checks (14–15) unless auditing an index page.

Legacy scope alias: `title_body_match` → same as `page_title` (Check 2).

### Check 1 — Confluence placement (`placement`)

**Standard:** [Structure §2–5](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard)

**Verify:**

- Space is **ADSO** (pages in DAPPM, other spaces → flag `WrongSpace`)
- Ancestor chain includes **Data Pipelines**
- Ancestry includes the correct **`{Team} → {Subteam}`** from §1.1 (e.g. `ODS → Core`, `ADM → Segmentation`, `BI → Linear → LDB`)
- **Pipeline-group subfolders** under the subteam are **allowed** (e.g. `ODS → Core → Drax Event → {job}`) — do not flag extra depth between subteam and leaf
- **BI → Addressable:** **`Goldmine` is not a Confluence folder** (legacy catch-all removed). Pass when ancestry is **`BI → Addressable → {group folder}`** per [reference.md — Addressable group folders](reference.md#bi--addressable-group-folders). §1.1 **Domain = Addressable** or subteam **Goldmine** (ops label) satisfies Addressable placement — e.g. **Data Shares** for Fubo/datashare pipelines
- BI Linear vs Media top-level rules (Media not under BI)
- Page is a **leaf** (pipeline doc), not an index-only catalog page

**Flag when:** Wrong space; missing `Data Pipelines`; missing or wrong **team/subteam** vs §1.1; orphan under Data Pipelines; program/PRD tree (e.g. DAPPM Unified CPM); Media nested under BI.

**Pass when:** ADSO + Data Pipelines + placement rules above — including **BI → Addressable → catalog group folder** (or direct under Addressable) for Addressable/Goldmine-metadata pipelines.

**Do not fail Check 1** for `§1.1 Subteam=Goldmine` when path is `BI → Addressable → Data Shares` (or another catalog group folder).

**Comments format:** `Space=DAPPM (expected ADSO)`; `§1.1 ODS/Core but ancestry missing Core`; `Addressable group folder 'Foo' not in catalog`; `Team=ADM in §1.1 but page under ODS`

Use `placement_bi_addressable()` and `ADDRESSABLE_PIPELINE_FOLDERS` from [scripts/pipeline_doc_checks.py](scripts/pipeline_doc_checks.py).

See nested-folder examples in [reference.md](reference.md).

---

### Check 2 — Page title & naming consistency (`page_title`)

**Standard:** Structure §2 principle 2, §8 leaf naming; §1.1 Job/DAG name must match page title

**Verify (single naming chain):**

- Page title = exact monitored **DBX job** or **Airflow/MWAA DAG** name
- No `DBX-`, friendly names (`ASR - ComScore`), dot notation (`adi.metrics.*`), bracket prod labels
- §1.1 **Job / DAG name** (or legacy “Pipeline Name”) equals page title (exact match preferred)
- Page title equals job name on primary **Job / DAG link** (Databricks Jobs UI or Airflow grid)
- All three agree when more than one is present on the page

**Flag when:** Legacy title pattern; **base name** mismatch among title, §1.1, and primary orchestration link (after ignoring env suffix).

**Pass when:** Names match exactly **or** differ only by trailing **`_prod` / `_uat` / `_dev`** (common: Confluence title without suffix, Databricks job with `_prod`). Do **not** fail Check 2 for suffix-only diffs — add a **Decide** line if team policy is unclear.

**Do not flag:** `ap_foo` (page title) vs `ap_foo_prod` (§1.1 or Job link) when the base name is identical.

**Comments format:** `Title has legacy prefix DBX-`; `Title 'ap_foo' ≠ §1.1 'ap_bar'`; `Info: suffix-only diff title vs link (Decide)`

Use `is_legacy_title()`, `looks_like_job_or_dag_name()`, `title_matches_body_job_name()`, and `title_matches_orchestration_link()` from [scripts/pipeline_doc_checks.py](scripts/pipeline_doc_checks.py).

---

### Check 3 — Page structure (`page_structure`)

**Standard:** [Pipeline Documentation — Standard §3 overview](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895775777/Pipeline+Documentation+-+Standard)

**Required top-level sections (in order):**

```text
# {exact_job_or_dag_name}

## 1. Pipeline metadata
   1.1 Identity & placement
   1.2 Orchestration
   1.3 Ownership & escalation
   1.4 Dependencies
   1.5 Data stores & targets
   1.6 Observability

## 2. Pipeline runbook
   2.1 Alert types … 2.7 External runbooks

## 3. Data quality (optional)
## 4. Cost (optional)
## 5. Change log (optional)
```

**Flag when:** Legacy `Details:` / `Alerts` layout; missing §1 or §2; §2 before §1; missing subsections 1.1–1.6 or 2.1–2.7 (headings or equivalent labeled tables); metadata and runbook not on same page.

**Do not flag:** Missing §3 Data quality; §2 followed by §4/§5 optional sections (renumbering gap is OK).

**Pass when:** §1 and §2 present in order with all subsections (heading level may be `##`/`###`).

**Comments format:** `Missing §2.3 Common failures`; `Legacy Details table without §1 heading`

---

### Check 4 — Metadata required fields (`metadata_required`)

**Standard:** Pipeline Documentation §5 (§1.1–1.6), minimum viable §8

**Verify all R fields populated (not blank/TBD/NA):**

| Block | Required |
|-------|----------|
| 1.1 | Job/DAG name, Description, Team/Subteam, Domain, Environment |
| 1.2 | Orchestrator, Workspace (if DBX/DLT), Job/DAG link, Schedule |
| 1.3 | Owning squad/DL, Primary oncall tag, PagerDuty/alert title tag |
| 1.5 | Target platform, Target catalog/database, Output tables/paths |
| 1.6 | Datadog Fail monitor URL; Long Run URL or explicit N/A |

**Owning squad / DL (§1.3):** Accept **`ADM`**, **`ODS`**, **`BI Linear`**, **`BI Addressable`** (case-insensitive) as valid minimum values, plus email DLs and other substantive owner strings. See [reference.md](reference.md) and `is_acceptable_owning_squad()`.

**Flag when:** Any R field missing or placeholder (naming mismatches → Check 2 only, do not duplicate here). **Do not flag** `Owning squad / DL=ADM` (or ODS / BI Linear / BI Addressable).

**Pass when:** All R fields have substantive values.

**Comments format:** `§1.3 Primary oncall tag=Blank`; `§1.6 Datadog Fail monitor=Missing`

---

### Check 5 — Runbook required content (`runbook_required`)

**Standard:** Pipeline Documentation §6 (§2.1–2.6)

**Verify:**

| Block | Rule |
|-------|------|
| 2.1 | Fail row: Monitor + Routes to; Long Run if job monitored for runtime |
| 2.2 | ≥ **5** numbered triage steps |
| 2.3 | Failure table ≥ **2** data rows |
| 2.4 | Platform + Context + validation SQL (or clear pointer to §3.5 if DQ-only) |
| 2.5 | Standard retry / repair procedure |
| 2.6 | Escalation table ≥ **1** row |

**Flag when:** Runbook only an external link with no §2 content; empty Alerts table; `NA` in Routes to for Fail.

**Pass when:** All R blocks satisfied on the leaf page (external deep-dive allowed in §2.7).

**Comments format:** `§2.2 Triage steps=3 (need ≥5)`; `§2.3 Common failures=0 rows (need ≥2)`

---

### Check 6 — Invalid placeholders (`invalid_values`)

**Scope:** All required (R) fields in §1 and §2.

**Invalid:** blank, `TBD`, `TODO`, `NA`/`N/A` where not explicitly allowed (see [reference.md](reference.md)).

**Flag when:** Open ticket-style placeholders on active pipeline docs.

**Comments format:** `§1.3 Owner=Blank`; `§2.1 Fail Routes to=NA`

---

### Check 7 — Alert tag & routing consistency (`alert_routing`)

**Standard:** Structure §3 canonical taxonomy `[AP][Team][Subteam][AlertType] {exact_job_name}` (extend brackets for Addressable — below)

**Verify:**

- §1.3 PagerDuty/alert title tag aligns with **Confluence path** and §1.1 **Domain** (not legacy §1.1 subteam alone)
- **BI → Linear:** e.g. `[AP][BI][Linear][LDB]` / `[ASR]` matching folder under Linear
- **BI → Addressable → {group folder}:** e.g. `[AP][BI][Addressable][Data Shares][Fail]` / `[Long Run]` — **group folder** = ancestor under Addressable (Delivery, Data Shares, Supply, …). **`[Goldmine]` in §1.3 is legacy** for leaves under Addressable group folders — flag **Change** (monitors may still use old titles until retagged)
- §2.1 **Routes to** matches §1.3/§1.6 (e.g. `PD → DataOps → @oncall-…`) — not a conflicting Teams-only / “no Datadog” row when §1.6 lists Datadog monitors
- Primary oncall tag matches squad (e.g. `@oncall-addr-bi` for Addressable BI)

**Flag when:** Tag missing; Linear/ODS bracket ≠ folder; Addressable path but tag lacks `[Addressable]` and `[{group folder}]`; legacy `[Goldmine]` tag under `BI → Addressable → Data Shares` (etc.); §2.1 routing contradicts PD/Datadog metadata.

**Comments format:** `§1.3 [Goldmine] but path BI → Addressable → Data Shares`; `expect [AP][BI][Addressable][Data Shares]`; `§2.1 Teams-only vs §1.6 Datadog`

Use `check_alert_tag_addressable()` from [scripts/pipeline_doc_checks.py](scripts/pipeline_doc_checks.py) for Addressable leaves.

---

### Check 8 — Dependencies consistency (`dependencies`)

**Verify §1.4 internal consistency:**

- Upstream jobs not listed as `NA` when Dependent DAG / upstream links exist elsewhere on page
- Related jobs cross-linked when inbound/serving pairs documented
- Downstream consumers documented when job feeds known unified/gold tables

**Flag when:** Contradictory `NA` vs linked jobs; missing upstream when description cites ELSA/S3 sensors.

**Comments format:** `§1.4 Upstream=NA but Dependent DAG lists 2 jobs`

---

### Check 9 — Observability & monitor links (`observability`)

**Verify §1.6 and §2.1 together:**

- Datadog URLs reachable format (`datadoghq.com`)
- Fail monitor in §1.6 appears in §2.1 Fail row
- Long Run documented or N/A with rationale

**Optional cross-check:** If user provides PagerDuty/Databricks context, job name in monitor title matches page title (Datadog standardization may be on hold — flag as **Info** not Critical).

---

### Check 10 — Data validation quality (`validation_quality`)

**Verify §2.4 (and §3.5 when DQ):**

- Platform and catalog/role context stated
- SQL or validation steps present (legacy “Query's to check data” counts if substantive)
- Expected results or thresholds documented (Rec — flag as **Medium** if missing)

**Comments format:** `§2.4 Missing expected results`; `§2.4 SQL present without platform context`

---

### Check 11 — External runbook delegation (`external_runbook`)

**Verify:** If §2.7 or inline link points to squad runbook (e.g. uCPM_Runbook):

- Leaf page still has minimum §2.1–2.2–2.6 (Check 5)
- §2.3 may summarize top failures + link for full catalog

**Flag when:** Entire runbook delegated externally with no triage/escalation on leaf page.

**Pass when:** §2.7 link plus minimum inline runbook (template principle 7).

---

### Check 12 — Data quality section (`dq_section`) — optional

**§3 is not required** for minimum compliance. DQ may be documented only in §2.1 / §2.3 / §2.4.

**Default (`audit_scope=all`):** **Pass** — do not flag missing §3; exclude this check from compliance % and from executive summary **Flagged** counts.

**When `audit_scope` includes `dq_section` or `full_template`:** Evaluate §3.1–3.7 per [Pipeline Documentation — Standard](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895775777/Pipeline+Documentation+-+Standard) §10; report gaps as **Informational (recommended depth)** only — never as required failures.

**Comments format (informational):** `Optional: add §3 for MC inventory`; `§2 covers DQ; §3 would add routing detail`

---

### Check 13 — Optional sections (`optional_sections`)

**Info-only (Low):** §3 Data quality absent; §4 Cost empty; §5 Change log missing; optional labels (`team:bi`, `pipeline-metadata`).

Do not fail minimum compliance unless user asks for `full_template` depth.

---

### Check 14 — Subteam index page (`index_page`)

**Scope:** Index/catalog pages only (same name as subteam folder).

**Verify:** Pipeline catalog table with links to child leaf pages; no runbook content on index.

**Flag when:** Index missing table; pipeline doc pasted on index instead of leaf.

---

### Check 15 — Duplicates & wrong-space copies (`duplicates`)

**Verify via CQL:** Same job name in ADSO + DAPPM (or other spaces).

**Flag when:** Multiple pages claim same pipeline; DAPPM copy without ADSO canonical page.

**Comments format:** `Duplicate: DAPPM 871072465 + ADSO (none)` — recommend ADSO canonical + link from program space.

---

## Workflow

1. **Read MCP schemas** for `user-confluence-disney`.
2. **Resolve targets** — from `page_urls`, `page_ids`, `job_names` (CQL `text ~ "job"`), or `subteam_path` (walk children under Data Pipelines).
3. **Fetch each page** — `body.storage`, `ancestors`, `space`, `title`, `version`.
4. **Normalize body** — Confluence returns **storage XHTML** (tables, `local-id`, optional `ac:layout`). Call `normalize_body_for_checks(body.storage)` for plain text **and** keep raw HTML for table/list parsing. Do **not** assume markdown pipe tables.
5. **Run checks** per `audit_scope` (default `all`). Use HTML-aware helpers (`extract_job_dag_name`, `parse_team_subteam_from_body`, `count_numbered_steps(text, html)`) before concluding a field or §2.2 is missing.
6. **Score** — % of applicable R checks passed (**exclude Check 12**; §3 optional).
7. **Output** — dev-team report (below); optional canvas per canvas skill.

## Output

**Always render in chat** (like `jira-adinc-audit`):

1. **Executive summary** table — checks scanned / flagged / compliance %
2. **Keep / Change / Decide** (when `report_audience=dev`)
3. **One heading + table per check** with flagged pages only (skip empty sections)
4. **Open questions** for owner/DataOps

### Executive summary template

```markdown
## Pipeline documentation audit summary

| Check | Scanned | Flagged |
|-------|---------|---------|
| 1 Placement | N | N |
| 2 Page title | N | N |
| … | | |

**Overall compliance (required checks):** ~X%
**Pages:** [links]
**Standards:** [Structure](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/...) · [Content](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895775777/...)
```

### Per-check table columns

| Page | Job / title | What's wrong | Technical details |

- **Page:** markdown link to Confluence
- **Job / title:** canonical job name if known
- **What's wrong:** plain English
- **Technical details:** `Check N`; field tokens with backticks

### Dev-team shareable report (full single-page audit)

When user asks for a report to share with DEV:

1. Executive summary + compliance score
2. **Keep** — bullet list of compliant content to migrate
3. **Change** — prioritized (P0 routing/observability, P1 structure/fields, P2 recommended depth)
4. **Decide** — path/subteam, exact job suffix, oncall tag
5. Per-check findings (condensed)
6. Suggested action plan (phases)

### Canvas (optional)

If `output_format` includes `canvas`, read canvas skill; file `{workspace}/canvases/pipeline-docs-audit-{slug}.canvas.tsx` with summary stats and flagged rows.

## Rules

- Do **not** edit Confluence unless the user explicitly asks to fix pages.
- Prefer **ADSO** as compliance target; document DAPPM/program copies as duplicates (Check 15).
- **Suffix-only naming** (`_prod` / `_uat` / `_dev`): pass Check 2; mention under **Decide** only when policy is unknown — do not treat as compliance failure.
- When job **base name** is ambiguous, list **Decide** — do not guess.
- **Microsoft Teams** for oncall/escalation — do not suggest Slack in remediation text.
- Paginate CQL search (`start` += `limit`) for folder-wide audits.
- Reload [reference.md](reference.md) when standards change on Confluence.
- For **gap audits** (monitored jobs without pages): combine Confluence search with user-provided Datadog/DBX lists — output missing-page checklist (Structure §12 Phase 4).

## Related skills

- `jira-adinc-audit` — similar multi-check audit pattern
- `audit-docs` — cross-doc consistency (local markdown)
- `confluence-adinc-history` — incident history (separate from pipeline leaves)
