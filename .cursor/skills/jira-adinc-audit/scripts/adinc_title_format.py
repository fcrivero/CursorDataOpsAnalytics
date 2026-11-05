"""ADINC Check 5 — title format validation and suggested title generation."""

from __future__ import annotations

import re

NA_INC_VALUES = {"NA", "N/A", "N.A.", "NONE"}

TITLE_PREFIX_RE = re.compile(
    r"^\[AP\]\[[^\]]+\]\[[^\]]+\](?:\[[^\]]+\])?\s*",
    re.IGNORECASE,
)
BRACKET_RE = re.compile(r"\[([^\]]+)\]")

PIPELINE_PREFIX = {
    "ODS - Metrics": "[AP][ODS][METRICS]",
    "ODS - Metric": "[AP][ODS][METRICS]",
    "ODS - Data Core": "[AP][ODS][Core]",
    "ADM - Measurement": "[AP][ADM][Measurement]",
    "ADM - Segmentation": "[AP][ADM][Segmentation]",
    "ADM - Targeting": "[AP][ADM][Targeting]",
    "BI Goldmine": "[AP][ADI][BI]",
    "Goldmine - Delivery/Supply/Prg": "[AP][ADI][BI]",
    "Goldmine - STR": "[AP][ADI][BI]",
    "Goldmine - Realized Metrics": "[AP][ADI][BI]",
    "Goldmine - STAQ": "[AP][ADI][BI]",
    "Goldmine - Delivery Context": "[AP][ADI][BI]",
    "D+ - International - Ralph": "[AP][ADI][BI]",
    "Disney O&O - DRR": "[AP][BI][DRR]",
    "Linear - ASR": "[AP][Linear][ASR]",
    "Linear - ELSA": "[AP][Linear][ELSA]",
    "Linear - DATG": "[AP][Linear][DATG]",
    "Linear - DART": "[AP][Linear][DART]",
    "Linear - LDB": "[AP][Linear][LDB]",
    "EDW - AdSales": "[AP][EDW][AdSales]",
    "EDW - Prodops": "[AP][EDW][Prodops]",
    "Waiting for RCA": "[AP][ADI][BI]",
}


def is_inc_number_na(found: dict[str, str]) -> bool:
    return found.get("INC_NUMBER", "").strip().upper() in NA_INC_VALUES


def primary_dag_display(dag_value: str | None) -> str | None:
    if not dag_value or str(dag_value).strip().upper() in NA_INC_VALUES:
        return None
    primary = str(dag_value).split(" and ")[0].strip()
    return primary or None


def primary_dag_token(dag_value: str | None) -> str | None:
    display = primary_dag_display(dag_value)
    return display.lower() if display else None


def _pipeline_prefix(pipeline: str) -> str:
    p = (pipeline or "").strip()
    if p in PIPELINE_PREFIX:
        return PIPELINE_PREFIX[p]
    if p.upper() == "NA" or not p:
        return "[AP][ADI][BI]"
    if p.startswith("ADM - "):
        return f"[AP][ADM][{p.replace('ADM - ', '')}]"
    if p.startswith("ODS - "):
        tail = p.replace("ODS - ", "")
        if tail.lower() in ("metrics", "metric"):
            return "[AP][ODS][METRICS]"
        return f"[AP][ODS][{tail}]"
    if "DRR" in p:
        return "[AP][BI][DRR]"
    if "Goldmine" in p or p.startswith("D+"):
        return "[AP][ADI][BI]"
    if p.startswith("Linear - "):
        return f"[AP][Linear][{p.replace('Linear - ', '')}]"
    return "[AP][ADI][BI]"


def _build_prefix(brackets: list[str], pipeline: str) -> str:
    labels = [b.strip() for b in brackets if b.strip()]
    qualifier = ""
    if labels and labels[-1].upper() in {"FAIL", "LONG RUN"}:
        qualifier = f"[{labels[-1]}]"
        labels = labels[:-1]

    if labels and labels[0].upper() == "AP":
        core = labels[:3]
        while len(core) < 3:
            core.append("BI" if len(core) == 2 else "General")
    elif labels and labels[0].upper() in {"ADM", "ODS", "ADI", "BI", "LINEAR", "ELSA", "EDW"}:
        core = ["AP", labels[0], labels[1] if len(labels) > 1 else "General"]
    else:
        prefix = _pipeline_prefix(pipeline)
        return prefix + qualifier

    while len(core) < 3:
        core.append("General")
    prefix = "".join(f"[{part}]" for part in core[:3])
    return prefix + qualifier


def _strip_brackets(text: str) -> str:
    return BRACKET_RE.sub("", text).strip()


def _extract_short_description(title: str, dag_display: str | None) -> str:
    text = _strip_brackets(title)
    if dag_display:
        lower_text = text.lower()
        lower_dag = dag_display.lower()
        if lower_text.startswith(lower_dag):
            text = text[len(dag_display) :].strip()
        elif lower_dag in lower_text:
            idx = lower_text.index(lower_dag)
            text = text[idx + len(dag_display) :].strip()
    text = re.sub(r"^[-–—:|/\s]+", "", text).strip()
    if len(text) < 3:
        fallback = _strip_brackets(title)
        if dag_display and fallback.lower().startswith(dag_display.lower()):
            fallback = fallback[len(dag_display) :].strip()
        fallback = re.sub(r"^[-–—:|/\s]+", "", fallback).strip()
        text = fallback or "incident"
    return text


def check_title_format(summary: str, found: dict[str, str]) -> tuple[bool, str]:
    if not is_inc_number_na(found):
        return False, ""

    findings: list[str] = []
    title = (summary or "").strip()
    if not title:
        return True, "Summary is empty"

    if not title.upper().startswith("[AP]"):
        findings.append("Summary must start with [AP]")

    match = TITLE_PREFIX_RE.match(title)
    if not match:
        findings.append("Expected prefix [AP][Team][SubTeam] (optional extra bracket segment)")
        return True, "; ".join(findings)

    body = title[match.end() :].strip()
    dag_token = primary_dag_token(found.get("DAG"))

    if dag_token:
        if dag_token not in body.lower():
            display_dag = primary_dag_display(found.get("DAG")) or ""
            findings.append(f'DAG "{display_dag}" not found in summary title')
    elif len(body) < 5:
        findings.append("Missing short description after team brackets (DAG is NA)")

    if findings:
        return True, "; ".join(findings)
    return False, "Title format compliant"


def suggest_title_format(summary: str, found: dict[str, str]) -> str:
    """Build a compliant title suggestion from current summary + description fields."""
    title = (summary or "").strip()
    brackets = BRACKET_RE.findall(title)
    pipeline = found.get("PIPELINE", "")
    dag_display = primary_dag_display(found.get("DAG"))

    prefix = _build_prefix(brackets, pipeline)
    short_desc = _extract_short_description(title, dag_display)

    if dag_display:
        return f"{prefix}{dag_display}- {short_desc}"
    return f"{prefix}{short_desc}"


def audit_title_format(summary: str, found: dict[str, str]) -> tuple[bool, str, str]:
    """Returns (flagged, comments, suggested_title). suggested_title empty when not in scope."""
    if not is_inc_number_na(found):
        return False, "", ""
    flagged, comments = check_title_format(summary, found)
    suggested = suggest_title_format(summary, found)
    return flagged, comments, suggested
