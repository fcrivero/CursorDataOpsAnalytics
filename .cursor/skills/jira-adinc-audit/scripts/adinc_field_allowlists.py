"""ADINC description field allowlists — synced with jira-adinc-tickets/reference.md."""

from __future__ import annotations

import re
from difflib import get_close_matches

TEAM_FIXED_VALUE = "ads-data-support"

ISSUE_CATEGORY_ALLOWLIST = frozenset({
    "AWS - Athena",
    "AWS - EKS",
    "AWS - Flink",
    "AWS - Glue",
    "AWS - KDA",
    "AWS - Kinesis",
    "AWS - Lambda",
    "AWS - S3",
    "AWS - vCPU",
    "Code - Deployment",
    "Code - Invalid Identifier",
    "Code - Schedule",
    "Code - Syntax",
    "Credentials",
    "Data - DQ",
    "Data - Format",
    "Data - Object",
    "Data - Partial",
    "Data - Upstream Delay",
    "Manual Error",
    "Network",
    "Spark",
    "Vendor - API",
    "Waiting for RCA",
})

SOURCE_SYSTEM_ALLOWLIST = frozenset({
    "3P Vendor - AWS",
    "3P Vendor - AX",
    "3P Vendor - AdIntel",
    "3P Vendor - Airflow",
    "3P Vendor - ComScore",
    "3P Vendor - Databricks",
    "3P Vendor - FUBO",
    "3P Vendor - Fluentbit",
    "3P Vendor - GAM",
    "3P Vendor - Hightouch",
    "3P Vendor - Kalido",
    "3P Vendor - ListenFirst",
    "3P Vendor - LiveRamp",
    "3P Vendor - Nielsen",
    "3P Vendor - O1",
    "3P Vendor - Oracle",
    "3P Vendor - Pathmatics",
    "3P Vendor - Qlik",
    "3P Vendor - SAP BOE",
    "3P Vendor - SQL-MI",
    "3P Vendor - STAQ",
    "3P Vendor - SalesHub",
    "3P Vendor - Salesforce",
    "3P Vendor - Snowflake",
    "3P Vendor - TalkWalker",
    "3P Vendor - Taxonomy",
    "3P Vendor - Telaria",
    "3P Vendor - Tidal",
    "ADM - Measurement",
    "ADM - Segmentation",
    "ADM - Targeting",
    "AdVisor",
    "Ads Data Infra",
    "Ads Server",
    "BI DRR",
    "BI Goldmine",
    "BI Ralph",
    "Data Ops",
    "Harps",
    "Linear BI",
    "ODS - Data Core",
    "ODS - Metrics",
    "Waiting for RCA",
})

PIPELINE_ALLOWLIST = frozenset({
    "ADM - Measurement",
    "ADM - Segmentation",
    "ADM - Targeting",
    "D+ - International - Ralph",
    "Disney O&O - DRR",
    "EDW - AdSales",
    "EDW - Prodops",
    "Goldmine - Addressable B&W",
    "Goldmine - Delivery Context",
    "Goldmine - Delivery/Supply/Prg",
    "Goldmine - Realized Metrics",
    "Goldmine - STAQ",
    "Goldmine - STR",
    "Linear - ASR",
    "Linear - DART",
    "Linear - DATG",
    "Linear - ELSA",
    "Linear - LDB",
    "NA",
    "ODS - Data Core",
    "ODS - Metric",
    "ODS - Metrics",
    "Waiting for RCA",
})

ENUM_NA_ALLOWED = {"SOURCE_SYSTEM"}  # NA/N/A allowed outside allowlist (audit placeholder rule)


def _is_na(val: str) -> bool:
    return val.strip().upper() in {"NA", "N/A", "N.A.", "NONE"}


def _suggest(value: str, allowlist: frozenset[str], n: int = 2) -> str:
    matches = get_close_matches(value, sorted(allowlist), n=n, cutoff=0.6)
    if not matches:
        return ""
    return f"; suggest: {', '.join(matches)}"


def check_field_enums(found: dict[str, str]) -> tuple[bool, str]:
    """Validate TEAM, ISSUE_CATEGORY, SOURCE_SYSTEM, PIPELINE against create-skill allowlists."""
    findings: list[str] = []

    team = found.get("TEAM")
    if team is None:
        findings.append("TEAM=Missing (field absent)")
    elif not team.strip():
        findings.append("TEAM=Blank ((empty))")
    elif team.strip() != TEAM_FIXED_VALUE:
        findings.append(
            f'TEAM=Invalid (expected "{TEAM_FIXED_VALUE}", got "{team.strip()}")'
        )

    issue_cat = found.get("ISSUE_CATEGORY")
    if issue_cat is None:
        findings.append("ISSUE_CATEGORY=Missing (field absent)")
    elif not issue_cat.strip():
        findings.append("ISSUE_CATEGORY=Blank ((empty))")
    elif issue_cat.strip() not in ISSUE_CATEGORY_ALLOWLIST:
        findings.append(
            f'ISSUE_CATEGORY=NotInAllowlist ("{issue_cat.strip()}")'
            + _suggest(issue_cat.strip(), ISSUE_CATEGORY_ALLOWLIST)
        )

    source = found.get("SOURCE_SYSTEM")
    if source is None:
        findings.append("SOURCE_SYSTEM=Missing (field absent)")
    elif not source.strip():
        findings.append("SOURCE_SYSTEM=Blank ((empty))")
    elif not (_is_na(source) and "SOURCE_SYSTEM" in ENUM_NA_ALLOWED):
        if source.strip() not in SOURCE_SYSTEM_ALLOWLIST:
            findings.append(
                f'SOURCE_SYSTEM=NotInAllowlist ("{source.strip()}")'
                + _suggest(source.strip(), SOURCE_SYSTEM_ALLOWLIST)
            )

    pipeline = found.get("PIPELINE")
    if pipeline is None:
        findings.append("PIPELINE=Missing (field absent)")
    elif not pipeline.strip():
        findings.append("PIPELINE=Blank ((empty))")
    elif pipeline.strip() not in PIPELINE_ALLOWLIST:
        findings.append(
            f'PIPELINE=NotInAllowlist ("{pipeline.strip()}")'
            + _suggest(pipeline.strip(), PIPELINE_ALLOWLIST)
        )

    if findings:
        return True, "; ".join(findings)
    return False, "Allowed values compliant"


# Reference text for Check 6 chat/canvas output (dropdown allowlists).
ALLOWED_VALUES_REFERENCE = """\
| Field | Rule | Example pass | Example fail |
|-------|------|--------------|--------------|
| `TEAM` | Must be exactly `ads-data-support` | `ads-data-support` | `ODS`, `ELSA` |
| `ISSUE_CATEGORY` | Must match the approved list (case-sensitive) | `Data - DQ`, `AWS - Kinesis`, `AWS - S3` | `AWS - S3*`, blank |
| `SOURCE_SYSTEM` | Must match approved list, or `NA` / `N/A` | `ODS - Metrics`, `3P Vendor - Hightouch`, `NA` | typo or invented vendor name |
| `PIPELINE` | Must match approved list | `ADM - Targeting`, `NA` | typo or invented value |"""


def _explain_finding(token: str) -> str:
    token = token.strip()
    if not token:
        return ""

    if token == "TEAM=Missing (field absent)":
        return "TEAM is missing from the description"
    if token == "TEAM=Blank ((empty))":
        return "TEAM is blank — must be ads-data-support"
    if token.startswith("TEAM=Invalid"):
        m = re.match(r'TEAM=Invalid \(expected "([^"]+)", got "([^"]+)"\)', token)
        if m:
            return f'TEAM must be "{m.group(1)}" but is "{m.group(2)}"'

    if token == "ISSUE_CATEGORY=Missing (field absent)":
        return "ISSUE_CATEGORY is missing — pick a value from the approved category list"
    if token == "ISSUE_CATEGORY=Blank ((empty))":
        return "ISSUE_CATEGORY is blank — must be filled with an approved category (e.g. Data - DQ, AWS - S3)"
    if token.startswith("ISSUE_CATEGORY=NotInAllowlist"):
        m = re.match(r'ISSUE_CATEGORY=NotInAllowlist \("([^"]+)"\)(?:; suggest: (.+))?', token)
        if m:
            msg = f'ISSUE_CATEGORY "{m.group(1)}" is not on the approved list'
            if m.group(2):
                msg += f" — try: {m.group(2)}"
            return msg

    if token == "SOURCE_SYSTEM=Missing (field absent)":
        return "SOURCE_SYSTEM is missing — pick a value from the approved source list or use NA"
    if token == "SOURCE_SYSTEM=Blank ((empty))":
        return "SOURCE_SYSTEM is blank — must be filled with an approved source or NA"
    if token.startswith("SOURCE_SYSTEM=NotInAllowlist"):
        m = re.match(r'SOURCE_SYSTEM=NotInAllowlist \("([^"]+)"\)(?:; suggest: (.+))?', token)
        if m:
            msg = f'SOURCE_SYSTEM "{m.group(1)}" is not on the approved list'
            if m.group(2):
                msg += f" — try: {m.group(2)}"
            return msg

    if token == "PIPELINE=Missing (field absent)":
        return "PIPELINE is missing — pick a value from the approved pipeline list"
    if token == "PIPELINE=Blank ((empty))":
        return "PIPELINE is blank — must be filled with an approved pipeline (e.g. ADM - Targeting, NA)"
    if token.startswith("PIPELINE=NotInAllowlist"):
        m = re.match(r'PIPELINE=NotInAllowlist \("([^"]+)"\)(?:; suggest: (.+))?', token)
        if m:
            msg = f'PIPELINE "{m.group(1)}" is not on the approved list'
            if m.group(2):
                msg += f" — try: {m.group(2)}"
            return msg

    return token


def explain_allowed_values_failure(comments: str) -> str:
    """Translate Check 6 machine comments into plain English for audit output."""
    parts: list[str] = []
    for token in comments.split("; "):
        token = token.strip()
        if not token:
            continue
        if token.startswith("suggest: "):
            if parts:
                parts[-1] += f" — try: {token[len('suggest: '):]}"
            continue
        explained = _explain_finding(token)
        if explained:
            parts.append(explained)
    return "; ".join(parts) if parts else comments
