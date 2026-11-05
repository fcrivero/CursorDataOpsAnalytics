---
name: mcp-health
description: >-
  Checks health of all configured Cursor MCP servers and AIX Manager connectivity
  for Microsoft Teams, SharePoint, and Google Docs. Renders status tables with
  server name, type (Plugin, Docker, HTTP, Stdio, AIX CLI), live health, tool
  count, auth/connectivity probes, and last-used time from agent transcripts and
  AIX telemetry. Use when the user asks to check MCP health, AIX connectivity,
  Teams/SharePoint/Google Docs access, list MCP status, audit MCP servers, or find
  unused or broken integrations.
---

# MCP Health Check

Produce a health report for **every MCP server** visible to the current Cursor session **and** AIX Manager connectivity for **Microsoft Teams**, **SharePoint**, and **Google Docs** (via local AIX CLIs, not MCP).

## Excluded servers

Do **not** include these in the MCP table, healthy/total counts, needs-attention list, stale list, or recommendations:

| Server id | Reason |
|-----------|--------|
| `plugin-atlassian-atlassian` | Retired — Docker Jira/Confluence MCPs cover the same use cases |

Skip excluded servers when merging the Step 1 catalog, Step 3 usage scan, and Step 6 report. The usage scanner (`scan_mcp_usage.py`) already omits them from output.

## Workflow

Copy this checklist and track progress:

```
MCP Health Progress:
- [ ] Step 1 — Live catalog (GetMcpTools)
- [ ] Step 2 — Config inventory (mcp.json + plugins)
- [ ] Step 3 — Last-used scan (scan_mcp_usage.py)
- [ ] Step 4 — AIX connectivity (check_aix_connectivity.py)
- [ ] Step 5 — Optional deep probes
- [ ] Step 6 — Render report
```

### Step 1 — Live catalog

Call `GetMcpTools` with **no arguments** to fetch the full server catalog. **Filter out excluded servers** (see above) before building the report.

For each remaining server record, capture:

| Field | Source |
|-------|--------|
| `server` | Catalog `server` id (e.g. `user-jira-server`, `plugin-datadog-datadog`) |
| `serverStatus` | `ready`, `needsAuth`, `error`, or `loading` |
| Tool count | Length of `tools` array |

**Health mapping**

| `serverStatus` | Display | Meaning |
|----------------|---------|---------|
| `ready` | Healthy | Connected; tools callable |
| `needsAuth` | Needs Auth | Run `mcp_auth` for that server (one at a time) |
| `error` | Error | Connection or startup failure |
| `loading` | Loading | Still initializing |
| *(missing from catalog)* | Not Connected | Defined in config but not loaded this session |

Do **not** call `mcp_auth` unless the user explicitly asks to fix auth during the health check.

### Step 2 — Config inventory

Read `~/.cursor/mcp.json` for user-configured servers. Merge with plugin-provided servers discovered in Step 1 (excluding retired plugins).

**Type classification** (apply in order):

| Condition | Type |
|-----------|------|
| Server id starts with `plugin-` | **Plugin** |
| `mcp.json` entry command/args contain `docker` | **Docker** |
| `mcp.json` entry has `url` | **HTTP** |
| `mcp.json` entry has `command` (non-Docker) | **Stdio** |
| Otherwise | **Unknown** |

**Display name**: strip `user-` or `plugin-` prefix; replace hyphens with spaces; title-case for readability (e.g. `user-jira-server` → `Jira Server`, `plugin-datadog-datadog` → `Datadog`).

**Disabled servers**: if `mcp.json` has `"disabled": true`, set Health to **Disabled** regardless of catalog.

Also note project-level `.cursor/mcp.json` if present in the open workspace — include those servers with source `project`.

### Step 3 — Last-used scan

Run the usage scanner against all agent transcripts:

```bash
python "%USERPROFILE%\.cursor\skills\mcp-health\scripts\scan_mcp_usage.py" --json
```

On macOS/Linux:

```bash
python ~/.cursor/skills/mcp-health/scripts/scan_mcp_usage.py --json
```

The script scans `~/.cursor/projects/*/agent-transcripts/*/*.jsonl` for `CallMcpTool`, `GetMcpTools`, and `FetchMcpResource` invocations. It pairs each tool call with the nearest preceding `<timestamp>` tag in the transcript, falling back to transcript file mtime.

Merge `usage_by_server` into the report. Servers with no transcript hits → **Never**.

### Step 4 — AIX connectivity (Teams, SharePoint, Google Docs)

AIX Manager installs Disney productivity CLIs under `~/.aix/bin`. Cursor agents reach Teams, SharePoint, and Google Docs through these **shell CLIs**, not MCP. Always include this section in the health report.

Run the connectivity checker:

```bash
python "%USERPROFILE%\.cursor\skills\mcp-health\scripts\check_aix_connectivity.py" --json
```

On macOS/Linux:

```bash
python ~/.cursor/skills/mcp-health/scripts/check_aix_connectivity.py --json
```

**Services checked**

| Service | AIX CLI | Auth check | Live probe |
|---------|---------|------------|------------|
| Microsoft Teams | `teams` | `teams --agent auth status` → `.data.usable == true` | `teams --agent chat list --limit 1` |
| SharePoint | `udoc` | Same MS Graph token as Teams (`teams --agent auth status` → `.data.usable`) | `udoc --agent search documents --query report --limit 1 --provider microsoft` |
| Google Docs | `gdrive` | `gdrive --agent auth status` → `.data.authenticated == true` | `gdrive --agent search recent --limit 1` |

**Health mapping (AIX section)**

| Condition | Display |
|-----------|---------|
| CLI missing from `~/.aix/bin` | Not Installed |
| Auth field false / missing | Needs Auth |
| Auth OK + live probe succeeds | Healthy |
| Auth OK + live probe fails | Degraded |
| Auth-only check (`--skip-probe`) | Authenticated |

**Last used** comes from `~/.aix/telemetry/events.ndjson` (most recent successful non-auth command per tool). If no telemetry hit → **Never**.

**Platform pre-check**: note whether `~/.aix/bin` exists and is on PATH. If PATH is missing, warn: restart Cursor after `aix doctor --fix`.

**Remediation (AIX)**

| Health | Action |
|--------|--------|
| Not Installed | Open **AIX Manager** or run `aix setup` |
| Needs Auth | **AIX Manager → Auth** → re-sign in; or `teams auth login` / `gdrive auth login` |
| Degraded (Teams/SharePoint) | Re-auth MS Graph: `teams auth login`; verify Disney VPN for SSO |
| Degraded (Google Docs) | Re-auth Google: `gdrive auth login` |
| PATH missing | Run `aix doctor --fix`; fully restart Cursor |

Do **not** print tokens or credential file contents. Account email from auth status is OK.

Use `--skip-probe` only when the user asks for a quick auth-only check.

### Step 5 — Optional deep probes

Run only when the user asks for a **deep** or **full** health check, or when a server shows `ready` but has suspiciously low tool count.

For each non-healthy server, add a one-line **Remediation** note:

| Health | Remediation hint |
|--------|------------------|
| Needs Auth | Open MCP panel → authenticate, or call `mcp_auth` once |
| Error (Docker) | Verify Docker/Colima is running; check `docker ps` and env files referenced in `mcp.json` |
| Error (HTTP) | Verify URL reachable; check VPN; validate bearer token in `mcp.json` headers |
| Not Connected | Reload Cursor window; confirm server not disabled in MCP settings |
| Disabled | Re-enable in `mcp.json` or Cursor MCP settings |

For Docker MCPs, optionally run:

```bash
docker ps --format "table {{.Names}}\t{{.Status}}"
```

Do not print secrets from `mcp.json` headers or env files.

### Step 6 — Render report

Present **two tables**: MCP servers, then AIX connectivity. Sort each by health severity, then by last-used (oldest/never first).

```markdown
# MCP Health Report

**Generated:** {local datetime}  
**MCP session:** {count ready}/{count total} healthy  
**AIX connectivity:** {aix healthy}/{aix total} healthy

## MCP Servers

| MCP Server | Type | Health | Tools | Last Used | Notes |
|------------|------|--------|-------|-----------|-------|
| Jira Server | Docker | Healthy | 87 | 2026-07-24 11:56 PT | |
| Datadog | Plugin | Healthy | 34 | 2026-07-20 09:12 PT | |

## AIX Manager — Teams, SharePoint, Google Docs

| Service | Type | Health | Auth | Connectivity | Last Used | Account | Notes |
|---------|------|--------|------|--------------|-----------|---------|-------|
| Microsoft Teams | AIX CLI | Healthy | Authenticated | OK | 2026-07-28 10:12 PT | user@disney.com | |
| SharePoint | AIX CLI | Healthy | Authenticated | OK | 2026-07-28 09:45 PT | (shared MS token) | via udoc |
| Google Docs | AIX CLI | Healthy | Authenticated | OK | 2026-07-28 11:03 PT | user@apps.disney.com | via gdrive |
```

**Summary block** (always include after both tables):

- **MCP healthy:** count
- **AIX healthy:** count (Teams / SharePoint / Google Docs)
- **Needs attention:** list MCP servers and AIX services with non-Healthy status
- **Stale (30+ days unused):** list integrations whose last used is older than 30 days or Never
- **Recommendations:** 1–3 bullet actions (auth, restart Docker, AIX re-login, reload window, etc.)

Prefer a **Canvas** when the user wants an interactive or shareable dashboard; otherwise the markdown table above is sufficient.

## Server id reference

Cursor prefixes configured servers with `user-` and plugin servers with `plugin-`. Map `mcp.json` keys to catalog ids:

| mcp.json key | Catalog id |
|--------------|------------|
| `jira-server` | `user-jira-server` |
| `pagerduty-mcp-manual` | `user-pagerduty-mcp-manual` |
| `datadog` (plugin) | `plugin-datadog-datadog` |

When matching last-used data, normalize bare config names to `user-{name}`.

## Constraints

- Read-only by default — do not mutate `mcp.json`, restart services, or call destructive MCP tools.
- Never log or display credential values from config files.
- Report only servers known to the **current session** catalog plus entries in `mcp.json`; do not invent servers.

## Examples

**User:** "Check MCP health" / `@mcp-health`  
→ Run Steps 1–4 and 6; output both tables + summary.

**User:** "Which MCPs haven't been used lately?"  
→ Emphasize Last Used column; flag Never and 30+ day stale entries across MCP and AIX sections.

**User:** "Deep MCP health check"  
→ Run all steps including Step 5 probes and remediation notes.

**User:** "Are Teams and Google Docs working?"  
→ Run Step 4 only if MCP section not requested; otherwise include AIX table in full report.
