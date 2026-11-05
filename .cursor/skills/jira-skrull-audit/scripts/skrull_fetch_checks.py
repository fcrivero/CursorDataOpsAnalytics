"""Fetch SKRULL audit check issue lists from Jira REST (same credentials as Jira MCP .env)."""
from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
REPORTS = SCRIPT_DIR.parent / "reports"

BASE_JQL = (
    "project = SKRULL AND issuetype in (Story, Task) "
    "AND status not in (Done, Closed, Resolved, Cancelled)"
)

# Check 1: only work that has started (exclude backlog / not-yet-started Open)
ASSIGNEE_SCOPE_JQL = f"{BASE_JQL} AND status not in (Open, Backlog)"

# Check 3: story points apply to Stories only (not Task or Sub-task)
POINTS_SCOPE_JQL = (
    "project = SKRULL AND issuetype = Story "
    "AND status not in (Done, Closed, Resolved, Cancelled)"
)

# Check 4: more than 8 calendar days open → Days Open >= 9
CHECK4_MIN_DAYS_OPEN = 9

CHECKS = {
    "assignee": (
        f"{ASSIGNEE_SCOPE_JQL} AND assignee is EMPTY "
        "ORDER BY assignee ASC, created ASC"
    ),
    "epic": (
        f"{BASE_JQL} AND \"Epic Link\" is EMPTY AND parent is EMPTY "
        "ORDER BY assignee ASC, created ASC"
    ),
    "points": (
        f"{POINTS_SCOPE_JQL} AND (points is EMPTY OR \"Story Points\" is EMPTY) "
        "ORDER BY assignee ASC, created ASC"
    ),
    "open_week": (
        f"{BASE_JQL} AND created <= -{CHECK4_MIN_DAYS_OPEN}d "
        "ORDER BY assignee ASC, created ASC"
    ),
    "blocked": (
        "project = SKRULL AND issuetype in (Story, Task) AND status = Blocked "
        "ORDER BY assignee ASC, created ASC"
    ),
}

POPULATION_JQL = f"{BASE_JQL} ORDER BY updated DESC"
EPICS_JQL = (
    "project = SKRULL AND issuetype = Epic "
    "AND status not in (Done, Closed, Resolved, Cancelled) ORDER BY updated DESC"
)

FIELDS = "summary,status,assignee,issuetype,created,description,points"


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def auth_header() -> str:
    import base64

    token = (os.environ.get("JIRA_API_TOKEN") or os.environ.get("JIRA_TOKEN") or "").strip()
    email = (
        os.environ.get("JIRA_EMAIL")
        or os.environ.get("JIRA_USERNAME")
        or ""
    ).strip()
    password = (os.environ.get("JIRA_PASSWORD") or "").strip()
    if email and token:
        cred = base64.b64encode(f"{email}:{token}".encode()).decode()
        return f"Basic {cred}"
    if email and password:
        cred = base64.b64encode(f"{email}:{password}".encode()).decode()
        return f"Basic {cred}"
    if token:
        return f"Bearer {token}"
    raise RuntimeError("Jira credentials not found in env file")


def jira_search_jql(jql: str, fields: str, max_results: int = 100) -> list[dict]:
    raw_issues: list[dict] = []
    page_token: str | None = None
    while True:
        params = [
            f"jql={quote(jql)}",
            f"maxResults={max_results}",
            f"fields={quote(fields)}",
        ]
        if page_token:
            params.append(f"nextPageToken={quote(page_token)}")
        url = f"https://deept.atlassian.net/rest/api/3/search/jql?{'&'.join(params)}"
        req = Request(
            url,
            headers={"Authorization": auth_header(), "Accept": "application/json"},
            method="GET",
        )
        with urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        batch = data.get("issues") or []
        raw_issues.extend(batch)
        page_token = data.get("nextPageToken")
        if not page_token or not batch:
            break
    return raw_issues


def normalize_issue(raw: dict) -> dict:
    f = raw.get("fields") or {}
    assignee = f.get("assignee")
    desc = f.get("description")
    if isinstance(desc, dict):
        desc = str(desc)
    return {
        "key": raw["key"],
        "summary": f.get("summary"),
        "status": (f.get("status") or {}).get("name"),
        "assignee": (assignee or {}).get("displayName") if assignee else None,
        "issuetype": (f.get("issuetype") or {}).get("name"),
        "created": f.get("created"),
        "description": desc,
        "points": f.get("customfield_10047"),
    }


def search_jql(jql: str, max_results: int = 100) -> list[dict]:
    raw = jira_search_jql(jql, FIELDS, max_results)
    return [normalize_issue(r) for r in raw]


def search_epics() -> list[dict]:
    raw = jira_search_jql(EPICS_JQL, "summary,status,description", 100)
    out = []
    for r in raw:
        f = r.get("fields") or {}
        desc = f.get("description")
        if isinstance(desc, dict):
            desc = str(desc)
        out.append(
            {
                "key": r["key"],
                "summary": f.get("summary"),
                "status": (f.get("status") or {}).get("name"),
                "description": desc,
            }
        )
    return out


def load_jira_credentials() -> None:
    load_dotenv(SCRIPT_DIR / ".env")
    mcp_env = Path(os.environ.get("SKRULL_JIRA_ENV", "")).expanduser()
    if mcp_env.is_file():
        load_dotenv(mcp_env)


def main() -> None:
    load_jira_credentials()
    REPORTS.mkdir(parents=True, exist_ok=True)

    pop = search_jql(POPULATION_JQL)
    (REPORTS / "population.json").write_text(
        json.dumps({"issues": pop, "total": len(pop)}, indent=2), encoding="utf-8"
    )

    for name, jql in CHECKS.items():
        issues = search_jql(jql)
        payload: dict = {"issues": issues, "total": len(issues)}
        if name == "assignee":
            scope = search_jql(ASSIGNEE_SCOPE_JQL)
            payload["scope_total"] = len(scope)
            payload["scope_jql"] = ASSIGNEE_SCOPE_JQL
        if name == "points":
            scope = search_jql(POINTS_SCOPE_JQL)
            payload["scope_total"] = len(scope)
            payload["scope_jql"] = POINTS_SCOPE_JQL
        (REPORTS / f"check_{name}.json").write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    epics = search_epics()
    (REPORTS / "open_epics.json").write_text(
        json.dumps({"issues": epics, "total": len(epics)}, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
