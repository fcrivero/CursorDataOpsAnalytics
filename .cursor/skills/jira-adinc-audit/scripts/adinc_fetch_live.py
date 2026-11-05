"""Fetch all ADINC tickets live from Jira REST API (no cache reads — write-only snapshot optional)."""
from __future__ import annotations

import base64
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_SNAPSHOT_PATH = SCRIPT_DIR / "reports" / "adinc-live-snapshot.json"
NOTES_FIELD = "customfield_10253"

JQL_RANGES = [
    "project = ADINC AND key < ADINC-400 ORDER BY key ASC",
    "project = ADINC AND key >= ADINC-400 AND key < ADINC-500 ORDER BY key ASC",
    "project = ADINC AND key >= ADINC-500 AND key < ADINC-600 ORDER BY key ASC",
    "project = ADINC AND key >= ADINC-600 AND key < ADINC-700 ORDER BY key ASC",
    "project = ADINC AND key >= ADINC-700 ORDER BY key ASC",
]

FIELDS = [
    "summary", "status", "resolution", "created", "updated", "description",
    NOTES_FIELD, "priority",
    "customfield_10489",  # Start DatePick (SNOW open on import; DEV start on native)
    "customfield_10566",  # Completion Date (Blocked / mitigated)
    "customfield_10453",  # End Date (Done / RCA)
]


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_jira_credentials() -> None:
    load_dotenv(SCRIPT_DIR / ".env")
    mcp_env = Path(os.environ.get("ADINC_JIRA_ENV", "")).expanduser()
    if mcp_env.is_file():
        load_dotenv(mcp_env)


def jira_base() -> str:
    return os.environ.get("JIRA_SERVER", "https://deept.atlassian.net").rstrip("/")


def auth_header() -> str:
    token = os.environ.get("JIRA_TOKEN", "").strip()
    if token:
        return f"Bearer {token}"
    user = os.environ.get("JIRA_USERNAME", "").strip()
    password = os.environ.get("JIRA_PASSWORD", "").strip()
    if user and password:
        cred = base64.b64encode(f"{user}:{password}".encode()).decode()
        return f"Basic {cred}"
    raise RuntimeError("JIRA credentials not configured (JIRA_TOKEN or JIRA_USERNAME/JIRA_PASSWORD)")


def jira_search_jql(jql: str, max_results: int = 100) -> list[dict]:
    issues: list[dict] = []
    page_token: str | None = None
    while True:
        params = [
            f"jql={quote(jql)}",
            f"maxResults={max_results}",
            f"fields={quote(','.join(FIELDS))}",
        ]
        if page_token:
            params.append(f"nextPageToken={quote(page_token)}")
        url = f"{jira_base()}/rest/api/3/search/jql?{'&'.join(params)}"
        req = Request(url, headers={"Authorization": auth_header(), "Accept": "application/json"}, method="GET")
        try:
            with urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Jira API error {e.code}: {detail[:500]}") from e
        batch = data.get("issues", [])
        issues.extend(batch)
        page_token = data.get("nextPageToken")
        if not page_token or not batch:
            break
    return issues


def adf_to_text(node) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(adf_to_text(n) for n in node)
    if not isinstance(node, dict):
        return str(node)

    kind = node.get("type")
    attrs = node.get("attrs") or {}

    if kind == "text":
        text = node.get("text", "")
        for mark in node.get("marks") or []:
            if mark.get("type") == "link":
                href = (mark.get("attrs") or {}).get("href", "")
                if href:
                    return f"[{href}|{text or href}|smart-link]"
        return text

    if kind in ("inlineCard", "blockCard", "embedCard"):
        url = attrs.get("url", "")
        if url:
            return f"[{url}|{url}|smart-link]"
        return ""

    if kind == "hardBreak":
        return "\n"
    if kind == "paragraph":
        return adf_to_text(node.get("content")) + "\n"
    return adf_to_text(node.get("content"))


def field_to_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return adf_to_text(value).strip()
    return str(value)


def normalize(raw: dict) -> dict:
    f = raw.get("fields", {})
    status = f.get("status") or {}
    resolution = f.get("resolution") or {}
    priority_field = f.get("priority")
    if isinstance(priority_field, dict):
        priority = priority_field.get("name") or ""
    else:
        priority = str(priority_field or "")
    return {
        "key": raw.get("key", ""),
        "summary": f.get("summary") or "",
        "status": status.get("name") if isinstance(status, dict) else str(status or ""),
        "resolution": resolution.get("name") if isinstance(resolution, dict) else str(resolution or ""),
        "created": (f.get("created") or "")[:10],
        "updated": (f.get("updated") or "")[:10],
        "description": field_to_text(f.get("description")),
        "notes": field_to_text(f.get(NOTES_FIELD)),
        "priority": priority,
    }


def fetch_all_adinc_issues(
    *,
    write_snapshot_path: Path | None = DEFAULT_SNAPSHOT_PATH,
) -> tuple[list[dict], dict]:
    """
    Pull all ADINC issues from Jira. Never reads a prior snapshot.
    Optional write_snapshot_path overwrites a report artifact only (not used as input).
    """
    load_jira_credentials()
    seen: dict[str, dict] = {}
    for jql in JQL_RANGES:
        for raw in jira_search_jql(jql):
            issue = normalize(raw)
            if issue["key"]:
                seen[issue["key"]] = issue
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    meta = {
        "source": "live",
        "jira_server": jira_base(),
        "fetched_at": fetched_at,
        "total": len(seen),
    }
    issues = list(seen.values())
    if write_snapshot_path is not None:
        write_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        write_snapshot_path.write_text(
            json.dumps({**meta, "issues": issues}, indent=2),
            encoding="utf-8",
        )
    return issues, meta


def main() -> int:
    issues, meta = fetch_all_adinc_issues()
    notes_n = sum(1 for i in issues if str(i.get("notes") or "").strip())
    print(f"Fetched {meta['total']} tickets from {meta['jira_server']} at {meta['fetched_at']}")
    print(f"Notes populated: {notes_n}/{meta['total']}")
    if DEFAULT_SNAPSHOT_PATH.exists():
        print(f"Wrote report artifact {DEFAULT_SNAPSHOT_PATH}")
    return 0


if __name__ == "__main__":
    import sys

    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
