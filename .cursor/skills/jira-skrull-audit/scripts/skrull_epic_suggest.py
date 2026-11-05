"""Rank open SKRULL Epics for a Story/Task missing Epic Link."""

from __future__ import annotations

import re
from typing import Iterable, Mapping, Sequence

# Pipeline / platform tokens common in SKRULL summaries (uppercase match)
BOOST_TOKENS = (
    "QLIK",
    "ELSA",
    "ADINC",
    "SUNSHINE",
    "VALIDATOR",
    "TIDAL",
    "DATADOG",
    "DATABRICKS",
    "DBX",
    "MONTE",
    "CARLO",
    "PRODOPS",
    "SNOWFLAKE",
    "ODS",
    "RALPH",
    "DATAOPS",
    "AUTOMATION",
    "SECURITY",
    "CICD",
    "HIGHTOUCH",
    "AIRFLOW",
)

WORD_RE = re.compile(r"[a-z0-9]+", re.I)
STATUS_PREFER = {"Open": 2, "In Progress": 2, "To Do": 1, "Backlog": 0}


def _tokens(text: str) -> set[str]:
    if not text:
        return set()
    words = {w.lower() for w in WORD_RE.findall(text) if len(w) >= 3}
    return words


def _boost_phrases(text: str) -> set[str]:
    upper = (text or "").upper()
    found = set()
    for tok in BOOST_TOKENS:
        if tok in upper:
            found.add(tok.lower())
    return found


def _epic_record(epic: Mapping) -> tuple[str, str, str, str]:
    key = epic.get("key") or ""
    summary = epic.get("summary") or ""
    description = epic.get("description") or ""
    status = epic.get("status") or ""
    return key, summary, description, status


def score_epic(
    ticket_summary: str,
    ticket_description: str | None,
    epic: Mapping,
) -> float:
    key, epic_summary, epic_desc, status = _epic_record(epic)
    if not key:
        return 0.0

    ticket_text = " ".join(filter(None, [ticket_summary, ticket_description or ""]))
    epic_text = " ".join(filter(None, [epic_summary, epic_desc]))

    t_tok = _tokens(ticket_text)
    e_tok = _tokens(epic_text)
    overlap = len(t_tok & e_tok)

    t_boost = _boost_phrases(ticket_text)
    e_boost = _boost_phrases(epic_text)
    boost = len(t_boost & e_boost) * 3

    # Substring: epic summary fragment in ticket or vice versa (short phrases)
    substring = 0.0
    es_lower = epic_summary.lower()
    ts_lower = ticket_summary.lower()
    if len(es_lower) >= 8 and es_lower in ts_lower:
        substring += 4.0
    if len(ts_lower) >= 8 and ts_lower in es_lower:
        substring += 2.0

    status_bonus = float(STATUS_PREFER.get(status, 0))

    return overlap + boost + substring + status_bonus


def suggest_epics(
    ticket_summary: str,
    ticket_description: str | None,
    epics: Sequence[Mapping],
    *,
    limit: int = 3,
) -> list[tuple[str, str, float]]:
    """
    Return [(epic_key, epic_summary, score), ...] best-first.
    """
    scored: list[tuple[str, str, float]] = []
    for epic in epics:
        key, summary, _, _ = _epic_record(epic)
        s = score_epic(ticket_summary, ticket_description, epic)
        if s > 0:
            scored.append((key, summary, s))

    scored.sort(key=lambda x: (-x[2], x[0]))
    return scored[:limit]


def _escape_table_cell(text: str) -> str:
    return (text or "").replace("|", "\\|")


def format_suggestions_markdown(
    suggestions: Iterable[tuple[str, str, float]],
    browse_base: str = "https://deept.atlassian.net/browse/",
) -> str:
    """Markdown links: epic key + Epic name (summary) as link text."""
    parts = []
    for key, summary, _ in suggestions:
        url = f"{browse_base}{key}"
        label = _escape_table_cell(f"{key}: {summary}".strip())
        parts.append(f"[{label}]({url})")
    return ", ".join(parts) if parts else "—"


def format_suggestions_plaintext(
    suggestions: Iterable[tuple[str, str, float]],
) -> str:
    """Excel-friendly epic suggestions: KEY: summary, comma-separated."""
    parts = [f"{key}: {summary}".strip() for key, summary, _ in suggestions]
    return ", ".join(parts) if parts else ""
