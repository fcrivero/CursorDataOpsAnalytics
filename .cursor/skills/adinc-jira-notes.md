# ADINC Jira Notes (RCA) — canonical field

All ADINC skills and agents **must** read and write RCA through this single field.

| Property | Value |
|----------|--------|
| Jira UI | **General** tab → **Notes** |
| Field name | `Notes` |
| Custom field ID | `customfield_10253` |
| JQL | `cf[10253]` |
| MCP server | `user-jira-server` |
| Instance | `https://deept.atlassian.net` (project `ADINC`) |

**Never** use Jira **Comments** (Activity tab) or **RCA Description** (`customfield_11093`) for ADINC RCA.

---

## Read

Always request `customfield_10253` explicitly in MCP `fields`:

```json
CallMcpTool user-jira-server jira_get_issue
{
  "issue_key": "ADINC-791",
  "fields": "summary,status,description,customfield_10253"
}
```

```json
CallMcpTool user-jira-server jira_search_issues
{
  "jql": "project = ADINC ORDER BY updated DESC",
  "fields": "summary,status,description,customfield_10253",
  "max_results": 100
}
```

**Resolve Notes text** from the MCP response (use in this order):

1. MCP `notes` key — plain text (preferred)
2. `customfield_10253` from the issue payload (may be ADF dict via REST — convert to text)
3. JQL presence check: `key = ADINC-791 AND cf[10253] is not EMPTY` — if true but text still missing, use REST fallback or ask the user to paste General → Notes

### MCP read vs write

| Operation | Mechanism |
|-----------|-----------|
| **Write** | `jira_update_issue` with `customfield_10253` — always works |
| **Read** | MCP maps `notes` from `JIRA_NOTES_FIELD` env var (default `customfield_10253`) |

**Storage format:** On deept.atlassian.net, Notes values are often **ADF** (Atlassian Document Format), not plain strings. The MCP server converts ADF → plain text for the `notes` response key.

If `notes` is null but JQL shows `cf[10253] is not EMPTY`, the MCP server may be using a stale field ID or needs a restart. Fix: set `JIRA_NOTES_FIELD=customfield_10253` in `jira-mcp-server-main/.env` and **reload the MCP server** (Cursor: Settings → MCP → restart `user-jira-server`).

**REST fallback** (when MCP `notes` is null after reload):

```
GET /rest/api/3/issue/{key}?fields=customfield_10253
```

Use credentials from the MCP server's `.env` (`JIRA_SERVER`, `JIRA_TOKEN`). Never log token values.

```python
def adf_to_plain_text(node) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, dict):
        if node.get("type") == "text":
            return str(node.get("text", ""))
        return "".join(
            adf_to_plain_text(c) for c in (node.get("content") or []) if c
        )
    if isinstance(node, list):
        return "".join(adf_to_plain_text(item) for item in node)
    return str(node)


def get_adinc_notes(issue: dict) -> str:
    """Extract Notes from jira_get_issue or normalized audit row."""
    if issue.get("notes"):
        return str(issue["notes"]).strip()
    raw = issue.get("customfield_10253")
    if raw:
        return adf_to_plain_text(raw).strip()
    fields = issue.get("fields") or {}
    if fields.get("notes"):
        return str(fields["notes"]).strip()
    raw = fields.get("customfield_10253")
    if raw:
        return adf_to_plain_text(raw).strip()
    return ""
```

---

## Write

Use `jira_update_issue` with **`customfield_10253`** only:

```json
CallMcpTool user-jira-server jira_update_issue
{
  "issue_key": "ADINC-791",
  "fields": {
    "customfield_10253": "RCA: Upstream data delay; job auto-recovered after sensor cleared."
  }
}
```

Do not write RCA to Comments or other custom fields.

---

## Validation (RCA present / missing)

| Invalid | Examples |
|---------|----------|
| Empty | null, blank, whitespace only |
| Placeholder | `#N/A`, `N/A`, `NA` (entire value) |
| Label only | `RCA:` or `RCA` with no explanation or link |

| Valid | Examples |
|-------|----------|
| Substantive RCA | `RCA: Received corrected data from business.` |
| | `RCA: Databricks regional outage; jobs recovered after vendor mitigation.` |
| Confluence / URL link | `RCA: https://disney-enterprise.atlassian.net/wiki/spaces/ADSO/pages/...` |
| | `RCA: [https://...|page title|smart-link]` (Jira smart-link / inline card) |

```python
import re

_URL_RE = re.compile(r"https?://[^\s\]|]+", re.IGNORECASE)
_SMART_LINK_RE = re.compile(r"\[[^\]]+\|[^\]]+\|smart-link\]", re.IGNORECASE)

def is_adinc_rca_missing(notes: str | None) -> bool:
    if not notes or not str(notes).strip():
        return True
    s = str(notes).strip()
    if s.upper() in ("#N/A", "N/A", "NA", "RCA:", "RCA"):
        return True
    body = re.sub(r"^RCA\s*:\s*", "", s, flags=re.IGNORECASE).strip()
    if not body or body.upper() in ("#N/A", "N/A", "NA"):
        return True
    if _URL_RE.search(body) or _SMART_LINK_RE.search(body):
        return False
    return len(body) < 10
```

---

## Skills using this field

| Skill | Read | Write |
|-------|------|-------|
| `jira-adinc-audit` | RCA audit (Check 4) | No (unless user asks to fix) |
| `confluence-adinc-history` | Gate before Confluence publish | No (unless user asks) |
| `jira-adinc-tickets` | Optional | `customfield_10253` when user requests Notes update |
| `dataops-pd-incident-analysis` | N/A (description fields only) | If user asks to save RCA → `customfield_10253` only |

**Mandatory:** Any skill or agent that reads or writes ADINC RCA must link to this file and use `customfield_10253` / General → Notes — never Comments, never `customfield_10219`, never `customfield_11093`.
