"""Helpers for pipeline-docs-audit skill. No network — pure text/rules."""

from __future__ import annotations

import re
from typing import Iterable

# Legacy / invalid title prefixes and patterns
LEGACY_TITLE_PREFIXES = (
    "dbx-",
    "dbx -",
    "dbx- ",
    "dag-",
    "[prod",
)

INVALID_PLACEHOLDERS = frozenset(
    {"TBD", "TODO", "NA", "N/A", "N.A.", "NONE", "—", "-"}
)

# Fields where NA is explicitly allowed in body text
NA_ALLOWED_FIELD_HINTS = frozenset(
    {
        "long run monitor",
        "datadog — long run",
        "downstream teams",
        "display name",
        "skip dq",
        "cost",
    }
)

# §1.3 Owning squad / DL — approved team shorthand (case-insensitive)
OWNING_SQUAD_ACCEPTABLE = frozenset(
    {
        "adm",
        "ods",
        "bi linear",
        "bi addressable",
    }
)

ENV_SUFFIXES = ("_prod", "_uat", "_dev")

# BI → Addressable pipeline-group folders (Confluence; replaces legacy "Goldmine" catch-all)
ADDRESSABLE_PIPELINE_FOLDERS = frozenset(
    {
        "delivery",
        "data shares",
        "dimension data",
        "metadata",
        "programmatic",
        "realized metrics",
        "speciality ads",
        "specialty ads",
        "supply",
        "supply international",
        "drr (airflow)",
    }
)

# §1.1 subteam labels that map to BI → Addressable + group folder (not a Confluence folder name)
LEGACY_ADDRESSABLE_SUBTEAM_LABELS = frozenset(
    {
        "goldmine",
    }
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return normalize_whitespace(text)


def looks_like_storage_html(body: str) -> bool:
    b = body or ""
    return "<" in b and ("<p" in b.lower() or "<table" in b.lower() or "<h" in b.lower())


def normalize_body_for_checks(body_storage: str) -> tuple[str, str]:
    """
    Confluence MCP returns body.storage (XHTML). Always derive plain text for checks
    while keeping raw HTML for table/list parsing.

    Returns (plain_text, html).
    """
    html = body_storage or ""
    if looks_like_storage_html(html):
        return strip_html(html), html
    return normalize_whitespace(html), html


def _cell_text(cell_html: str) -> str:
    cell = cell_html or ""
    for pat in (
        r"<code[^>]*>(.*?)</code>",
        r"<a\b[^>]*>(.*?)</a>",
        r"<h3[^>]*>(.*?)</h3>",
    ):
        m = re.search(pat, cell, re.I | re.S)
        if m:
            return normalize_whitespace(strip_html(m.group(1)))
    return normalize_whitespace(strip_html(cell))


def extract_table_field_value(html: str, label_pattern: str) -> str | None:
    """
    Read a Confluence HTML table row: label in first th/td, value in second cell.
    label_pattern is a regex matched against de-tag'd row text (case-insensitive).
    """
    if not html or not looks_like_storage_html(html):
        return None
    label_re = re.compile(label_pattern, re.I)
    for tr_m in re.finditer(r"<tr\b[^>]*>(.*?)</tr>", html, re.I | re.S):
        row = tr_m.group(1)
        row_plain = normalize_whitespace(strip_html(row))
        if not label_re.search(row_plain):
            continue
        cells = re.findall(r"<t[dh]\b[^>]*>(.*?)</t[dh]>", row, re.I | re.S)
        if len(cells) < 2:
            continue
        value = _cell_text(cells[1])
        if value:
            return value
    return None


def canonical_job_name(name: str) -> str:
    """Strip trailing _prod / _uat / _dev for naming-chain comparison."""
    n = normalize_whitespace(name)
    lower = n.lower()
    for suf in ENV_SUFFIXES:
        if lower.endswith(suf):
            return n[: -len(suf)]
    return n


def job_names_equivalent(a: str, b: str) -> bool:
    return canonical_job_name(a).lower() == canonical_job_name(b).lower()


def suffix_only_job_name_diff(a: str, b: str) -> bool:
    """True when names match after canonicalization but literal strings differ."""
    return job_names_equivalent(a, b) and normalize_whitespace(a).lower() != normalize_whitespace(
        b
    ).lower()


def is_acceptable_owning_squad(value: str) -> bool:
    v = normalize_owning_squad(value)
    if not v:
        return False
    if v in OWNING_SQUAD_ACCEPTABLE:
        return True
    if "@" in v:
        return True
    if len(v) > 3 and v not in INVALID_PLACEHOLDERS:
        return True
    return False


def normalize_owning_squad(value: str) -> str:
    return normalize_whitespace(value).lower()


REQUIRED_TOP_SECTIONS = (
    ("1", re.compile(r"1\.?\s*pipeline\s+metadata", re.I)),
    ("2", re.compile(r"2\.?\s*pipeline\s+runbook", re.I)),
)

OPTIONAL_TOP_SECTIONS = (
    ("3", re.compile(r"3\.?\s*data\s+quality", re.I)),
    ("4", re.compile(r"4\.?\s*cost", re.I)),
    ("5", re.compile(r"5\.?\s*change\s+log", re.I)),
)

METADATA_SUBSECTIONS = tuple(f"1.{i}" for i in range(1, 7))

RUNBOOK_SUBSECTIONS = tuple(f"2.{i}" for i in range(1, 8))

DQ_SUBSECTIONS = tuple(f"3.{i}" for i in range(1, 8))


def is_blank_or_placeholder(value: str, field_hint: str = "") -> bool:
    v = normalize_whitespace(value)
    if not v:
        return True
    upper = v.upper()
    if upper in INVALID_PLACEHOLDERS:
        if any(h in field_hint.lower() for h in NA_ALLOWED_FIELD_HINTS):
            return False
        return True
    return False


def is_legacy_title(title: str) -> tuple[bool, str]:
    t = (title or "").strip()
    if not t:
        return True, "Title is empty"
    lower = t.lower()
    for prefix in LEGACY_TITLE_PREFIXES:
        if lower.startswith(prefix):
            return True, f"Legacy prefix ({prefix.strip()})"
    if " - " in t and not t.startswith("Dag-prod-"):
        if re.match(r"^[A-Za-z]{2,6}\s-\s", t):
            return True, "Friendly name pattern (Team - Name)"
    if "." in t and t.count(".") >= 2 and not t.startswith("ap_"):
        return True, "Dot-notation legacy name"
    if re.search(r"\s{2,}", t):
        return True, "Extra whitespace in title"
    return False, ""


def looks_like_job_or_dag_name(title: str) -> bool:
    t = (title or "").strip()
    if not t:
        return False
    if t.startswith("Dag-prod-") or t.startswith("Dag-"):
        return True
    if re.match(r"^ap_[a-z0-9_]+(_prod|_uat|_dev)?$", t, re.I):
        return True
    if re.match(r"^[a-z0-9_]+_(prod|uat|dev)$", t, re.I):
        return True
    return len(t) >= 8 and "_" in t and " " not in t


def extract_job_dag_name(body: str) -> str | None:
    """Job/DAG name from §1.1 (HTML table, then markdown pipe table, then stripped text)."""
    html = body if looks_like_storage_html(body) else ""
    if html:
        for pat in (
            r"job\s*/\s*dag\s+name",
            r"job/dag\s+name",
            r"pipeline\s+name",
        ):
            val = extract_table_field_value(html, pat)
            if val and looks_like_job_or_dag_name(val):
                return val
    text, _ = normalize_body_for_checks(body)
    patterns = [
        r"job\s*/\s*dag\s+name[^\n|]*\|\s*`?([^`|\\n]+)`?",
        r"pipeline\s+name[^\n|]*\|\s*`?([^`|\\n]+)`?",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return normalize_whitespace(m.group(1))
    return None


def ancestor_titles(ancestors: list[dict] | None) -> list[str]:
    if not ancestors:
        return []
    return [a.get("title", "") for a in ancestors if a.get("title")]


def normalize_folder_title(title: str) -> str:
    return normalize_whitespace(title).lower()


def extract_domain_from_body(body: str) -> str | None:
    html = body if looks_like_storage_html(body) else ""
    if html:
        val = extract_table_field_value(html, r"^domain\s*$|^domain\b")
        if val:
            return normalize_whitespace(val)
    text, _ = normalize_body_for_checks(body)
    m = re.search(r"domain[^\n|]*\|\s*([^|\n]+)", text, re.I)
    if m:
        return normalize_whitespace(m.group(1))
    return None


def _chain_after_data_pipelines(ancestors: list[dict] | None) -> list[str]:
    titles = ancestor_titles(ancestors)
    if "Data Pipelines" not in titles:
        return []
    return titles[titles.index("Data Pipelines") + 1 :]


def _team_folder_aliases(team: str) -> set[str]:
    aliases = {team}
    if team.upper().startswith("ADI "):
        aliases.add(team.split()[-1])
    return aliases


def placement_bi_addressable(
    ancestors: list[dict] | None,
    body_text: str,
    team: str,
    subteam: str | None,
) -> tuple[bool, str]:
    """
    Addressable pipelines live under Data Pipelines → BI → Addressable → [group folder] → leaf.
    Legacy §1.1 subteam 'Goldmine' is an ops label only — not a required folder name.
    """
    chain = _chain_after_data_pipelines(ancestors)
    if "BI" not in chain or "Addressable" not in chain:
        return False, "ancestry missing BI → Addressable"
    if not any(t in chain for t in _team_folder_aliases(team)):
        return False, f"§1.1 team {team} inconsistent with BI → Addressable path"

    domain = extract_domain_from_body(body_text)
    sub_norm = normalize_folder_title(subteam or "")
    addr_idx = chain.index("Addressable")
    group_folders = chain[addr_idx + 1 :]

    addressable_pipeline = (
        domain is not None and domain.lower() == "addressable"
        or sub_norm in LEGACY_ADDRESSABLE_SUBTEAM_LABELS
        or sub_norm in ADDRESSABLE_PIPELINE_FOLDERS
    )
    if not addressable_pipeline:
        return False, ""

    if not group_folders:
        return True, ""
    first_group = normalize_folder_title(group_folders[0])
    if first_group in ADDRESSABLE_PIPELINE_FOLDERS:
        return True, ""
    if sub_norm and sub_norm == first_group:
        return True, ""
    return (
        False,
        f"Addressable group folder '{group_folders[0]}' not in catalog "
        f"(see reference.md ADDRESSABLE_PIPELINE_FOLDERS)",
    )


def addressable_group_folder_from_ancestry(
    ancestors: list[dict] | None,
) -> str | None:
    """First catalog group folder under BI → Addressable, if any."""
    chain = _chain_after_data_pipelines(ancestors)
    if "Addressable" not in chain:
        return None
    idx = chain.index("Addressable")
    if idx + 1 >= len(chain):
        return None
    group = chain[idx + 1]
    if normalize_folder_title(group) in ADDRESSABLE_PIPELINE_FOLDERS:
        return group
    return None


def extract_pagerduty_alert_tag(body: str) -> str | None:
    html = body if looks_like_storage_html(body) else ""
    if html:
        for pat in (
            r"pagerduty\s*/\s*alert\s+title\s+tag",
            r"alert\s+title\s+tag",
        ):
            val = extract_table_field_value(html, pat)
            if val:
                return val
    text, _ = normalize_body_for_checks(body)
    m = re.search(
        r"(?:pagerduty\s*/\s*)?alert\s+title\s+tag[^\n|]*\|\s*([^|\n]+)",
        text,
        re.I,
    )
    if m:
        return normalize_whitespace(m.group(1))
    return None


def check_alert_tag_addressable(
    ancestors: list[dict] | None,
    body: str,
) -> tuple[bool, list[str]]:
    """
    Check 7 (Addressable): tag should reflect BI → Addressable → group folder,
    e.g. [AP][BI][Addressable][Data Shares][Fail] — not legacy [Goldmine].
    """
    comments: list[str] = []
    group = addressable_group_folder_from_ancestry(ancestors)
    if not group:
        return True, comments
    tag = extract_pagerduty_alert_tag(body)
    if not tag:
        return True, comments
    lower = tag.lower()
    if "goldmine" in lower:
        comments.append(
            "§1.3 alert tag uses legacy [Goldmine]; "
            f"expect [AP][BI][Addressable][{group}] (+ Fail/Long Run) per Confluence path"
        )
    if "addressable" not in lower:
        comments.append(
            f"§1.3 alert tag missing [Addressable] (path BI → Addressable → {group})"
        )
    # Group folder title may be multi-word (Data Shares)
    if group.lower() not in lower and group.replace(" ", "").lower() not in lower:
        comments.append(
            f"§1.3 alert tag missing [{group}] (Addressable group folder in ancestry)"
        )
    return (len(comments) == 0, comments)


def parse_team_subteam_from_body(body: str) -> tuple[str | None, str | None]:
    """Extract Team and Subteam from §1.1 (HTML table or pipe table)."""
    raw: str | None = None
    html = body if looks_like_storage_html(body) else ""
    if html:
        raw = extract_table_field_value(html, r"team\s*/\s*sub\s*team")
    text, _ = normalize_body_for_checks(body)
    if not raw:
        m = re.search(
            r"team\s*/\s*sub\s*team[^\n|]*\|\s*([^|\n]+)",
            text,
            re.I,
        )
        if m:
            raw = normalize_whitespace(m.group(1))
    if not raw:
        return None, None
    parts = [p.strip() for p in re.split(r"\s*/\s*", raw) if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[1]
    if len(parts) == 1:
        return parts[0], None
    return None, None


def ancestry_contains_team_subteam(
    ancestors: list[dict] | None,
    team: str,
    subteam: str,
) -> bool:
    """
    True if titles include Data Pipelines, then team, then subteam in order.
    Additional folder/page titles AFTER subteam (e.g. Drax Event) are allowed.
    """
    titles = ancestor_titles(ancestors)
    if "Data Pipelines" not in titles:
        return False
    start = titles.index("Data Pipelines") + 1
    chain = titles[start:]
    team_aliases = {team}
    if team.upper().startswith("ADI "):
        team_aliases.add(team.split()[-1])
    if team.upper() == "BI":
        team_aliases.add("BI")
    try:
        ti = min(chain.index(t) for t in team_aliases if t in chain)
        si = chain.index(subteam, ti + 1)
        return si >= ti
    except ValueError:
        return False


def check_adso_placement(
    space_key: str,
    ancestors: list[dict] | None,
    body_text: str = "",
) -> tuple[bool, list[str]]:
    """Returns (passed, comments). body_text may be storage HTML or plain text."""
    comments: list[str] = []
    if space_key != "ADSO":
        comments.append(f"Space={space_key} (expected ADSO)")
    titles = ancestor_titles(ancestors)
    if "Data Pipelines" not in titles:
        comments.append("Not under Data Pipelines ancestor")
    teams = {"ODS", "ADM", "BI", "Media", "CRMA"}
    if titles and not any(t in teams for t in titles):
        comments.append("Missing team folder (ODS/ADM/BI/Media/CRMA) in ancestry")

    team, subteam = parse_team_subteam_from_body(body_text)
    domain = extract_domain_from_body(body_text)
    chain = _chain_after_data_pipelines(ancestors)

    if team and subteam:
        placed = False
        # BI → Addressable (group folders; Goldmine is legacy §1.1 label only)
        if "Addressable" in chain and (
            (domain and domain.lower() == "addressable")
            or normalize_folder_title(subteam) in LEGACY_ADDRESSABLE_SUBTEAM_LABELS
            or normalize_folder_title(subteam) in ADDRESSABLE_PIPELINE_FOLDERS
        ):
            ok, msg = placement_bi_addressable(ancestors, body_text, team, subteam)
            placed = ok
            if not ok and msg:
                comments.append(msg)
        elif ancestry_contains_team_subteam(ancestors, team, subteam):
            placed = True
        if not placed and not any(
            c.startswith("Addressable group folder") for c in comments
        ):
            comments.append(
                f"§1.1 Team/Subteam {team}/{subteam} not found in ancestry order "
                f"(BI Addressable: use group folder under Addressable; "
                f"Goldmine in §1.1 is legacy ops label)"
            )

    return (len(comments) == 0, comments)


def infer_expected_path_suffix(body_text: str, ancestors: list[dict] | None) -> str | None:
    m = re.search(
        r"team\s*/\s*subteam[^\n|]*\|\s*([^|\n]+)",
        strip_html(body_text) if looks_like_storage_html(body_text) else body_text,
        re.I,
    )
    if not m:
        team, sub = parse_team_subteam_from_body(body_text)
        if team and sub:
            return f"{team} / {sub}"
    elif m:
        return normalize_whitespace(m.group(1))
    titles = ancestor_titles(ancestors)
    if "Data Pipelines" in titles:
        idx = titles.index("Data Pipelines")
        return " → ".join(titles[idx + 1 :])
    return None


def find_section_positions(text: str) -> dict[str, int]:
    positions: dict[str, int] = {}
    for key, pat in REQUIRED_TOP_SECTIONS + OPTIONAL_TOP_SECTIONS:
        m = pat.search(text)
        if m:
            positions[key] = m.start()
    return positions


def check_section_order(text: str) -> tuple[bool, list[str]]:
    if looks_like_storage_html(text):
        text, _ = normalize_body_for_checks(text)
    pos = find_section_positions(text)
    comments: list[str] = []
    if "1" not in pos:
        comments.append("Missing §1 Pipeline metadata heading")
    if "2" not in pos:
        comments.append("Missing §2 Pipeline runbook heading")
    if "1" in pos and "2" in pos and pos["1"] > pos["2"]:
        comments.append("§2 appears before §1")
    if "2" in pos and "3" in pos and pos["2"] > pos["3"]:
        comments.append("§3 appears before §2")
    legacy = re.search(r"^#?\s*details\s*:?", text, re.I | re.M)
    if legacy and "1" not in pos:
        comments.append("Legacy Details layout (no §1 heading)")
    return (len(comments) == 0, comments)


def _triage_chunks(text: str, html: str) -> tuple[str, str]:
    text_chunk = text
    html_chunk = html or ""
    m = re.search(r"2\.2[^\n]*triage", text, re.I)
    if m:
        text_chunk = text[m.start() : m.start() + 4000]
    if html_chunk:
        hm = re.search(r"2\.2[^<]*triage", html_chunk, re.I)
        if hm:
            html_chunk = html_chunk[hm.start() : hm.start() + 8000]
    return text_chunk, html_chunk


def count_numbered_steps(text: str, html: str = "") -> int:
    """Count §2.2 triage steps: markdown-style '1. …' lines and Confluence <ol><li>."""
    if looks_like_storage_html(text) and not html:
        text, html = normalize_body_for_checks(text)
    text_chunk, html_chunk = _triage_chunks(text, html)
    count = len(re.findall(r"(?m)^\s*\d+\.\s+\S", text_chunk))
    if not count:
        count = len(re.findall(r"\d+\.\s+\S", text_chunk))
    if html_chunk:
        ol_items = len(re.findall(r"<li\b", html_chunk, re.I))
        count = max(count, ol_items)
    return count


def count_failure_table_rows(text: str) -> int:
    if looks_like_storage_html(text):
        text, _ = normalize_body_for_checks(text)
    m = re.search(r"2\.3[^\n]*common\s+failures", text, re.I)
    if not m:
        return 0
    chunk = text[m.start() : m.start() + 6000].lower()
    symptoms = len(re.findall(r"symptom", chunk))
    return max(0, symptoms - 1)


def has_datadog_url(text: str) -> bool:
    if looks_like_storage_html(text):
        text, _ = normalize_body_for_checks(text)
    return bool(re.search(r"https?://[^\s]*datadoghq[^\s]*", text, re.I))


def has_databricks_job_url(text: str) -> bool:
    if looks_like_storage_html(text):
        text, _ = normalize_body_for_checks(text)
    return bool(re.search(r"https?://[^\s]*databricks[^\s]*/jobs/", text, re.I))


def title_matches_body_job_name(title: str, body_text: str) -> tuple[bool, str]:
    """
    Compare page title to §1.1 Job/DAG name.
    Pass when equal or suffix-only diff (_prod/_uat/_dev) — see Check 2 Decide note.
    """
    t = normalize_whitespace(title)
    body_name = extract_job_dag_name(body_text)
    if not body_name:
        return False, "Job/DAG name not found in body for title comparison"
    if job_names_equivalent(t, body_name):
        if suffix_only_job_name_diff(t, body_name):
            return True, (
                f"Info: suffix-only diff title='{t}' vs §1.1 '{body_name}' "
                f"(pass Check 2; list under Decide if team policy unclear)"
            )
        return True, ""
    return False, f"Title '{t}' ≠ body Job/DAG name '{body_name}'"


def extract_primary_job_link_text(html: str) -> str | None:
    """Anchor text from §1.2 Job / DAG link row when present."""
    if not looks_like_storage_html(html):
        return None
    return extract_table_field_value(html, r"job\s*/\s*dag\s+link")


def title_matches_orchestration_link(title: str, body_storage: str) -> tuple[bool, str]:
    link_name = extract_primary_job_link_text(body_storage)
    if not link_name:
        return True, ""
    if job_names_equivalent(title, link_name):
        if suffix_only_job_name_diff(title, link_name):
            return True, (
                f"Info: suffix-only diff title='{title}' vs Job link '{link_name}' "
                f"(pass Check 2; Decide if needed)"
            )
        return True, ""
    return False, f"Title '{title}' ≠ Job/DAG link text '{link_name}'"


def dq_section_required(body_text: str) -> bool:
    text, _ = normalize_body_for_checks(body_text)
    lower = text.lower()
    triggers = (
        "monte carlo",
        "data quality (dq)",
        "deequ",
        "great expectations",
        "completeness",
        "custom sql",
        "anomaly",
        "in-pipeline dq",
        "## 3. data quality",
    )
    return any(t in lower for t in triggers)


def explain_findings(comments: Iterable[str]) -> str:
    return "; ".join(comments)
