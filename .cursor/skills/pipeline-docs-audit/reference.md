# Pipeline documentation audit — reference

Canonical standards (refresh when Confluence changes):

| Document | Page ID | URL |
|----------|---------|-----|
| Confluence structure | 2895637552 | [Data Pipelines Confluence Structure — Standard](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895637552/Data+Pipelines+Confluence+Structure-+Standard) |
| Leaf page content | 2895775777 | [Pipeline Documentation — Standard](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895775777/Pipeline+Documentation+-+Standard) |
| Data Pipelines root | 192841195 | ADSO → Data Pipelines |

## ADSO placement rules

| Rule | Value |
|------|--------|
| Space key | `ADSO` only for compliant pipeline leaf pages |
| Root ancestor | `Data Pipelines` (page id `192841195` or title match) |
| Top-level team folders | `ODS`, `ADM`, `BI`, `Media`, `CRMA` |
| BI under Addressable | `BI → Addressable → {group folder}` — see [Addressable group folders](#bi--addressable-group-folders) (legacy **Goldmine** folder removed) |
| BI under Linear | `BI → Linear → {ASR,DART,DATG,LDB}` |
| Media | `Media → ProdOps` (not under BI) |
| Leaf pages | Under the correct **team → subteam** chain; may be a direct child of the subteam folder **or** nested under **pipeline-group subfolders** (see below) |
| Pipeline-group subfolders | **Allowed** under a main subteam for logical grouping (e.g. `ODS → Core → Drax Event → {job}`). These are not index catalogs — they group related leaf pages. |
| Index pages | Same name as subteam folder (or designated catalog page); contains pipeline catalog table linking to leaf pages — **not** a substitute for leaf runbook content |

### Nested folders (allowed)

Minimum compliant ancestry pattern:

```text
Data Pipelines → {Team} → {Subteam} → [optional group folder(s)] → {exact_job_or_dag_name}
```

**Examples (pass Check 1):**

| Path under Data Pipelines |
|---------------------------|
| `ODS → Core → ap_addr_ods_core_beacon_drax_event_prod` |
| `ODS → Core → Drax Event → ap_addr_ods_core_beacon_drax_event_prod` |
| `ADM → Segmentation → ap_addr_audience_cross_sell_dms_inbound_prod` |
| `BI → Linear → LDB → Dag-prod-ldb_*` |
| `BI → Addressable → Data Shares → ap_addr_bi_gen_daily_fubo_reports` |

**Do not flag** extra folder depth between **{Subteam}** and the leaf page when §1.1 Team/Subteam matches the `{Team} → {Subteam}` segment of the ancestry — **except BI Addressable:** use [group folder rules](#bi--addressable-group-folders) below.

**Still flag:** leaf under wrong team/subteam vs §1.1; leaf outside `Data Pipelines`; wrong space; program/PRD trees (e.g. DAPPM); Addressable leaf not under `BI → Addressable` or unknown group folder.

### BI → Addressable group folders

**Goldmine** is **no longer** a Confluence folder under Addressable (former catch-all). Leaf pages belong under **`Data Pipelines → BI → Addressable → {group folder}`**.

| Group folder (Confluence title) | Typical use |
|---------------------------------|-------------|
| Delivery | Delivery / reporting pipelines |
| Data Shares | Partner exports, datashare, Fubo-style shares |
| Dimension Data | Dimension pipelines |
| Metadata | Metadata pipelines |
| Programmatic | Programmatic BI |
| Realized Metrics | Realized metrics |
| Speciality Ads | Speciality ads |
| Supply | Supply pipelines |
| Supply International | International supply |
| DRR (Airflow) | Airflow DRR (may be index/page) |

**Check 1 pass (Addressable):**

- Ancestry includes **`BI` → `Addressable`**
- Next ancestor (if any) is one of the **group folders** above, **or** leaf is a direct child of **Addressable**
- §1.1 **Domain** = `Addressable` **or** legacy §1.1 subteam **`Goldmine`** (ops/alert label only — **do not** require a Goldmine folder)
- §1.1 subteam may also match the **group folder name** (e.g. `Data Shares`) when teams adopt folder names in metadata

**Check 1 flag:** Under Addressable but group folder not in catalog; under wrong branch (e.g. Linear); §1.1 Domain Linear but page under Addressable.

### Subteam → Confluence path (from structure standard)

| Team | Subteam / domain | Expected path suffix (under Data Pipelines) |
|------|------------------|-----------------------------------------------|
| ODS | Core | `ODS → Core` |
| ODS | Metrics | `ODS → Metrics` |
| ADM | Segmentation | `ADM → Segmentation` |
| ADM | Targeting | `ADM → Targeting` |
| ADM | Measurement | `ADM → Measurement` |
| BI | Addressable (+ group folder) | `BI → Addressable → {Delivery, Data Shares, …}` |
| BI | Goldmine (§1.1 legacy label) | Same as Addressable — **not** `→ Goldmine` |
| BI | ASR | `BI → Linear → ASR` |
| BI | DART | `BI → Linear → DART` |
| BI | DATG | `BI → Linear → DATG` |
| BI | LDB | `BI → Linear → LDB` |
| BI | uCPM | `BI → Linear → uCPM` |
| Media | ProdOps | `Media → ProdOps` |
| CRMA | (TBD) | `CRMA` — flag as review required |

**Extensions:** New **group folders** under Addressable need DataOps/catalog update in this table and `ADDRESSABLE_PIPELINE_FOLDERS` in [scripts/pipeline_doc_checks.py](scripts/pipeline_doc_checks.py). **Pipeline-group** names under ODS/Core (e.g. `Drax Event`) unchanged.

## Confluence storage format (MCP)

- Pipeline leaf pages are fetched as **`body.storage`** XHTML (Cloud editor): `<table>`, `<h2>`, `<ol><li>`, `ac:layout`, etc.
- Audits must use **`normalize_body_for_checks()`** plus HTML table helpers in [scripts/pipeline_doc_checks.py](scripts/pipeline_doc_checks.py) — not markdown-only regex.
- **§1.1 fields** live in `<th>` / `<td>` rows (e.g. `Job / DAG name`, `Team / Sub team`); **§2.2 triage** may be `<ol><li>` rather than lines starting with `1.`.

## Page title rules

- Leaf title = monitored DBX job or Airflow/MWAA DAG id (exact match preferred).
- **Invalid title patterns:** `DBX-`, `DBX -`, `[prod …]`, friendly names (`ASR - ComScore`), dot notation (`adi.metrics.*`), trailing/leading spaces.
- Title must match **Job / DAG name** in §1.1 and the primary orchestration link (**Check 2**). Compare using **`canonical_job_name()`** (strip trailing `_prod`, `_uat`, `_dev`).
- **Suffix convention:** Many teams use **base name** on the Confluence page title and **`_prod` on the Databricks job** — that is **Check 2 pass**; note under **Decide** only if ownership wants strict literal equality.

## Required page structure (headings)

Acceptable heading variants (normalize before compare):

- `## 1. Pipeline metadata` / `## Pipeline metadata` / `## 1. Pipeline Metadata`
- Subsections `### 1.1` … `### 1.6` or table blocks labeled Identity, Orchestration, etc.
- `## 2. Pipeline runbook` with `### 2.1` … `### 2.7`
- `## 3. Data quality` with `### 3.1` … `### 3.7` — **optional** (DQ may live in §2 only)
- `## 4. Cost` optional; `## 5. Change log` optional

**Order:** §1 before §2; §2 before §3; metadata before runbook.

## §1 required fields (R)

From [Pipeline Documentation — Standard](https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/2895775777/Pipeline+Documentation+-+Standard):

| Block | Required fields |
|-------|-----------------|
| 1.1 Identity | Job/DAG name, Description, Team/Subteam, Domain, Environment |
| 1.2 Orchestration | Orchestrator, Workspace (DBX/DLT), Job/DAG link, Schedule |
| 1.3 Ownership | Owning squad/DL, Primary oncall tag, PagerDuty/alert title tag (see allowlist below) |
| 1.5 Data stores | Target platform(s), Target catalog/database, Output tables/paths |
| 1.6 Observability | Datadog Fail monitor URL; Long Run URL or explicit N/A |

## §2 required fields (R)

| Block | Required content |
|-------|------------------|
| 2.1 Alert types | Fail row with Monitor + Routes to; Long Run if monitored |
| 2.2 Triage | ≥5 numbered steps |
| 2.3 Common failures | Table with ≥2 rows (Symptom, Likely cause, Action) |
| 2.4 Data validation | Platform + Context; validation SQL or explicit deferral |
| 2.5 Repair/rerun | Standard retry procedure |
| 2.6 Escalation | ≥1 Condition/Action row |

§2.7 External runbooks: recommended when deep runbook lives elsewhere.

## Alert title tag (Check 7) — BI Addressable

For leaves under **`Data Pipelines → BI → Addressable → {group folder}`**, §1.3 **PagerDuty / alert title tag** should follow **path**, not the legacy §1.1 subteam **Goldmine** (ops name only).

| Confluence path (after Addressable) | Expected tag segments (example) |
|-----------------------------------|----------------------------------|
| Data Shares | `[AP][BI][Addressable][Data Shares][Fail]` / `[Long Run]` |
| Delivery | `[AP][BI][Addressable][Delivery][Fail]` |
| Supply | `[AP][BI][Addressable][Supply][Fail]` |
| … | `[AP][BI][Addressable][{same as folder title}]` |

Datadog monitor names may lag Confluence — flag doc for update; optional **Info** if monitors still say `Goldmine` until retitled.

**BI → Linear** unchanged: `[AP][BI][Linear][LDB]` (or ASR, DART, DATG, uCPM folder name).

## §1.3 Owning squad / DL — acceptable shorthand

These **team labels** satisfy **Owning squad / DL** for minimum compliance (case-insensitive; trim whitespace):

| Value | Notes |
|-------|--------|
| `ADM` | Addressable ADM pipelines |
| `ODS` | ODS Core / Metrics |
| `BI Linear` | BI → Linear subteams (ASR, DART, DATG, LDB) |
| `BI Addressable` | BI → Addressable (e.g. Goldmine) |

Email DLs and longer squad names remain valid. **Invalid:** blank, `TBD`, `NA`/`N/A` alone.

Implementation: `is_acceptable_owning_squad()` in [scripts/pipeline_doc_checks.py](scripts/pipeline_doc_checks.py).

## §3 Data quality — optional

**§3 is not required** for minimum compliance. Document DQ in **§2.1** (alert types), **§2.3** (failures), and **§2.4** (validation) when sufficient.

**Optional (recommended depth):** Add `## 3. Data quality` when Monte Carlo inventory, §3 vs §2 routing, or central MC runbook links add oncall value. Evaluate only when `audit_scope` includes `dq_section` or `full_template` — report gaps as **informational**, not compliance failures.

## Invalid placeholder values

Treat as **invalid** on required (R) metadata/runbook fields:

- Empty / whitespace only
- `TBD`, `TODO`, `NA`, `N/A`, `N.A.`, `NONE` (except explicit allowed N/A: Long Run monitor, optional downstream teams; **§3 entire section optional**)

**Legacy layout:** Single “Details” table without §1/§2 headings → fail Check 3 and Check 4–6.

## Non-pipeline pages under Data Pipelines

Flag if ancestor is Data Pipelines and title matches known non-pipeline pages: Dashboards, DBX Tracking, Daily Support Check List, SOP, Ralph, platform docs (Linear Adsales ops), duplicate “Copy of …”.

## MCP fetch pattern

```json
{
  "namespace": "user-confluence-disney",
  "toolName": "confluence_get_page",
  "arguments": {
    "page_id": "{id}",
    "expand": "body.storage,version,space,ancestors"
  }
}
```

After fetch:

```python
from pipeline_doc_checks import normalize_body_for_checks, extract_job_dag_name, parse_team_subteam_from_body, count_numbered_steps

plain, html = normalize_body_for_checks(page["body"]["storage"]["value"])
job = extract_job_dag_name(html)
team, subteam = parse_team_subteam_from_body(html)
triage_count = count_numbered_steps(plain, html)
```

Search scope:

```json
{
  "namespace": "user-confluence-disney",
  "toolName": "confluence_search_content",
  "arguments": {
    "cql": "space = ADSO AND ancestor = 192841195 AND type = page",
    "limit": 25,
    "start": 0
  }
}
```

Paginate with `start` until `size` < `limit`.

## Dev-team shareable report sections

1. Executive summary (compliance %, counts per check)
2. Keep / Change / Decide tables
3. Per-check findings (only flagged rows)
4. Open questions
5. Links to standards
