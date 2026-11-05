"""Load Jira/Confluence credentials from env or .env files."""
from __future__ import annotations

import base64
import os
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent

JIRA_BASE = "https://deept.atlassian.net"
CONFLUENCE_BASE = "https://disney-enterprise.atlassian.net"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_credentials() -> tuple[str, str]:
    for p in (
        SCRIPT_DIR / ".env",
        SKILL_DIR / ".env",
        Path(os.environ.get("ADINC_JIRA_ENV", "")).expanduser(),
        Path.home() / ".cursor" / "skills" / "jira-adinc-audit" / "scripts" / ".env",
        Path(r"C:\Users\rivef104\Documents\AI\MCP-Cursor\confluence-mcp-server-main\.env"),
    ):
        if p.is_file():
            load_dotenv(p)
    user = os.environ.get("JIRA_USERNAME") or os.environ.get("CONFLUENCE_USERNAME", "")
    token = os.environ.get("JIRA_TOKEN") or os.environ.get("CONFLUENCE_TOKEN", "")
    if not user or not token:
        raise RuntimeError(
            "Jira/Confluence credentials missing. Set JIRA_USERNAME + JIRA_TOKEN "
            "(or CONFLUENCE_USERNAME + CONFLUENCE_TOKEN) in scripts/.env or ADINC_JIRA_ENV."
        )
    return user.strip(), token.strip()


def basic_auth(user: str, token: str) -> str:
    return base64.b64encode(f"{user}:{token}".encode()).decode()
