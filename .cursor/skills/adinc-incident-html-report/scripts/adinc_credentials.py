"""Load Jira/Confluence credentials (same pattern as jira-adinc-audit / Jira MCP .env)."""
from __future__ import annotations

import base64
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent

DEFAULT_JIRA_BASE = "https://deept.atlassian.net"
DEFAULT_CONFLUENCE_BASE = "https://disney-enterprise.atlassian.net"

# Back-compat alias used by adinc_fetch / adinc_confluence imports
JIRA_BASE = DEFAULT_JIRA_BASE
CONFLUENCE_BASE = DEFAULT_CONFLUENCE_BASE


def load_dotenv(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _normalize_jira_server() -> None:
    url = (os.environ.get("JIRA_URL") or "").strip().rstrip("/")
    server = (os.environ.get("JIRA_SERVER") or "").strip().rstrip("/")
    if url and not server:
        os.environ.setdefault("JIRA_SERVER", url)
    elif server and not url:
        os.environ.setdefault("JIRA_URL", server)


def _normalize_confluence_server() -> None:
    url = (os.environ.get("CONFLUENCE_URL") or "").strip().rstrip("/")
    server = (os.environ.get("CONFLUENCE_SERVER") or "").strip().rstrip("/")
    if url and not server:
        os.environ.setdefault("CONFLUENCE_SERVER", url)
    elif server and not url:
        os.environ.setdefault("CONFLUENCE_URL", server)


def load_jira_env() -> None:
    """Load Jira env from skill .env, shared ADINC audit .env, and ADINC_JIRA_ENV."""
    for p in (
        SCRIPT_DIR / ".env",
        SKILL_DIR / ".env",
        Path.home() / ".cursor" / "skills" / "jira-adinc-audit" / "scripts" / ".env",
    ):
        load_dotenv(p)
    mcp_env = Path(os.environ.get("ADINC_JIRA_ENV", "")).expanduser()
    if mcp_env.is_file():
        load_dotenv(mcp_env)
    _normalize_jira_server()


def load_confluence_env() -> None:
    """Load Confluence env (Confluence MCP .env); pull Jira MCP .env for shared email if needed."""
    for p in (
        SCRIPT_DIR / ".env",
        SKILL_DIR / ".env",
    ):
        load_dotenv(p)
    confluence_mcp = Path(os.environ.get("ADINC_CONFLUENCE_ENV", "")).expanduser()
    if confluence_mcp.is_file():
        load_dotenv(confluence_mcp)
    jira_mcp = Path(os.environ.get("ADINC_JIRA_ENV", "")).expanduser()
    if jira_mcp.is_file():
        load_dotenv(jira_mcp)
    _normalize_confluence_server()


def jira_base() -> str:
    return (
        os.environ.get("JIRA_SERVER")
        or os.environ.get("JIRA_URL")
        or DEFAULT_JIRA_BASE
    ).rstrip("/")


def confluence_base() -> str:
    return (
        os.environ.get("CONFLUENCE_SERVER")
        or os.environ.get("CONFLUENCE_URL")
        or DEFAULT_CONFLUENCE_BASE
    ).rstrip("/")


def jira_auth_header() -> str:
    token = (os.environ.get("JIRA_TOKEN") or os.environ.get("JIRA_API_TOKEN") or "").strip()
    user = (os.environ.get("JIRA_USERNAME") or os.environ.get("JIRA_EMAIL") or "").strip()
    password = (os.environ.get("JIRA_PASSWORD") or "").strip()
    if user and token:
        cred = base64.b64encode(f"{user}:{token}".encode()).decode()
        return f"Basic {cred}"
    if user and password:
        cred = base64.b64encode(f"{user}:{password}".encode()).decode()
        return f"Basic {cred}"
    if token:
        return f"Bearer {token}"
    raise RuntimeError(
        "Jira credentials not configured. Set JIRA_TOKEN in scripts/.env or point "
        "ADINC_JIRA_ENV at the same .env file used by Jira MCP (jira-mcp-server-main/.env)."
    )


def confluence_auth_header() -> str:
    token = (os.environ.get("CONFLUENCE_TOKEN") or "").strip()
    user = (
        os.environ.get("CONFLUENCE_USERNAME")
        or os.environ.get("JIRA_USERNAME")
        or os.environ.get("JIRA_EMAIL")
        or ""
    ).strip()
    password = (os.environ.get("CONFLUENCE_PASSWORD") or "").strip()
    if user and token:
        cred = base64.b64encode(f"{user}:{token}".encode()).decode()
        return f"Basic {cred}"
    if user and password:
        cred = base64.b64encode(f"{user}:{password}".encode()).decode()
        return f"Basic {cred}"
    if token:
        return f"Bearer {token}"
    raise RuntimeError(
        "Confluence credentials not configured. Set ADINC_CONFLUENCE_ENV to the Confluence "
        "MCP .env, add CONFLUENCE_TOKEN to scripts/.env, or use --exclude mttd."
    )