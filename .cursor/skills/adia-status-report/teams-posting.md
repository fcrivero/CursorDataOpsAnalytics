# ADIA Status Report — Microsoft Teams Posting

Read this file when the user wants the report posted to Teams. Requires the **`teams-cli`** skill and a write-enabled `teams` CLI session (`teams --agent auth status` → `.data.authenticated == true` and `.data.usable == true`).

**Prerequisite:** Step 0 Teams check completed (see SKILL.md). The full report must already be displayed in chat and the user must confirm posting via `AskQuestion`. After confirmation, post immediately in the same agent run.

## Teams auth when not connected (Step 0 only)

Show this block **only when Step 0 finds Teams is not ready to post** — at the **start** of the skill run, before or alongside the Jira report. **Never** show this block again at the end after posting or skipping.

Run `teams --agent auth status` first, then give the user the steps that match their state.

### Template (copy into chat when auth fails at Step 0)

```markdown
### Microsoft Teams — not connected

**Status:** {not authenticated / refresh failed / usable: false}

Connect **ds-connect-me VPN**, then run:

```powershell
# Optional one-time setup (then restart PowerShell)
[System.Environment]::SetEnvironmentVariable('AITOOLS_MS_SYSTEM_BROWSER', '1', 'User')

teams --agent auth status

# If refreshable but not authenticated:
teams auth refresh --force
teams --agent auth status

# If refresh fails (e.g. AADSTS53003) — full login on VPN:
$env:AITOOLS_MS_SYSTEM_BROWSER = "1"
teams auth login
# Paste the device code at https://login.microsoft.com/device
teams --agent auth status
```

**Network check (login should not go out home Wi-Fi):**

```powershell
$ip = (Resolve-DnsName login.microsoftonline.com | Where-Object { $_.Type -eq 'A' } | Select-Object -First 1).IPAddress
Find-NetRoute -RemoteIPAddress $ip | Format-List InterfaceAlias, NextHop
```

After auth succeeds, confirm posting again or re-run the weekly report.
```

| Status | User action |
|--------|-------------|
| Not authenticated, refreshable | VPN → `teams auth refresh --force` |
| Not authenticated, not refreshable | VPN → `teams auth login` (device code) |
| 53003 on refresh | Full Disney VPN (ds-connect-me), not home Wi-Fi |

## Default channel

| Setting | Value |
|---------|--------|
| Channel name | `ap-dataenab-linear-devops-priv` |
| Channel URL | [ap-dataenab-linear-devops-priv](https://teams.microsoft.com/l/channel/19%3A9a8a10354e704b85b6bb729535ef84fe%40thread.tacv2/ap-dataenab-linear-devops-priv?groupId=3d4f02b8-61b5-4761-8e3e-38a44e26ffba&tenantId=56b731a8-a2ac-4c32-bf6b-616810e913c6&ngc=true) |
| Team ID (`--team-id`) | `3d4f02b8-61b5-4761-8e3e-38a44e26ffba` |
| Channel ID (`--channel-id`) | `19:9a8a10354e704b85b6bb729535ef84fe@thread.tacv2` |

User may override with a different Teams channel URL or name. Resolve IDs with:

```bash
teams --agent channel teams --filter "ap-dataenab"
```

## CC recipients (second message only)

| Display name (Teams) | Search query |
|----------------------|--------------|
| Hosamani, Vijaya Kumar | `Vijaya Kumar Hosamani` |
| Gray, Colin | `Colin Gray` |

**CC line (exact text for Step C only):**

```text
CC: Hosamani, Vijaya Kumar Gray, Colin
```

Do **not** append this line to the Teams report body file or the first reply. It appears **once**, as its own reply after the ticket list.

Resolve AAD GUIDs if using mentions:

```bash
teams --agent people search --query "Vijaya Kumar Hosamani"
teams --agent people search --query "Colin Gray"
```

Use `--mention "DisplayName:AAD_GUID"` on the **CC reply** if Graph allows; on `ACCESS_DENIED`, plain-text CC is fine.

## Thread title format

```
Analytics Weekly Status Report: {period_label}
```

**Period label** — compact `M/D-M/D` from the reporting window (no year, no leading zeros required):

| Input period | period_label |
|--------------|--------------|
| July 16 to July 22, 2026 | `7/16-7/22` |
| June 26 to July 2, 2026 | `6/26-7/2` |
| July 2026 (full month) | `7/1-7/31` |

## ASCII sanitization (required for Teams)

Teams mangles UTF-8 punctuation from the CLI (e.g. em dash `—` renders as `â€"`). **Always build a separate Teams copy** of the report with ASCII-only separators:

| Unicode | Teams replacement |
|---------|-------------------|
| `—` (em dash) | ` - ` |
| `–` (en dash) | `-` |
| `→` | `->` |
| `"` `"` | `'` (prefer single quotes in summaries) |
| `'` `'` | `'` |

Apply to every Jira summary and to all separator positions in ticket lines. Chat display may keep Unicode dashes; Teams body must not.

When passing content via PowerShell, read the temp file as UTF-8:

```powershell
$content = Get-Content -Raw -Encoding UTF8 "path\to\teams-report.md"
```

Write the Teams file as UTF-8 (no BOM). Temp file path pattern: `temp/adia-report-teams-{period_label}.md` (slashes in dates → hyphens, e.g. `10-22-10-28`).

## Teams report body (first reply only — no CC)

Use this format in the **first thread reply**. Omit empty sections. **Use ASCII hyphens, not em dashes.** End after the last ticket section — **no CC line here.**

```markdown
## In Progress:

- [ADIA-1234](https://deept.atlassian.net/browse/ADIA-1234) - Ticket summary (Dawid) - **3 points**

---

## Resolved:

- [ADIA-1235](https://deept.atlassian.net/browse/ADIA-1235) - Ticket summary (Fernando) - **1 point**

---

## Awaiting External Input / Blocked:

- [ADIA-1236](https://deept.atlassian.net/browse/ADIA-1236) - Ticket summary (Dawid - Blocked) - **5 points**
```

Line rules match [SKILL.md](SKILL.md). Use `---` between sections when the next section has items.

## Posting workflow (3 messages)

**Always confirm with the user before any Teams write** (see SKILL.md Step 6).

### Step A — Create thread (root message)

The `--subject` flag sets the thread title. **Do NOT repeat the title in `--content`** — that causes a doubled title in the channel (bold subject + plain body line).

Use a minimal placeholder for `--content` (required by CLI):

```bash
teams --agent channel send \
  --team-id "3d4f02b8-61b5-4761-8e3e-38a44e26ffba" \
  --channel-id "19:9a8a10354e704b85b6bb729535ef84fe@thread.tacv2" \
  --subject "Analytics Weekly Status Report: 7/16-7/22" \
  --content " " \
  --content-type text
```

Fetch the root `messageId` from `teams channel messages` (the send response may return `message_id: unknown`):

```bash
teams --agent channel messages \
  --team-id "3d4f02b8-61b5-4761-8e3e-38a44e26ffba" \
  --channel-id "19:9a8a10354e704b85b6bb729535ef84fe@thread.tacv2" \
  --limit 3
```

Use the newest message whose content matches the subject (or the `OriginalArrivalTime` from send).

### Step B — First reply: ticket report only (no CC)

**Do not pass `--content-type text` on the report body.** That flag sends the string verbatim, so Teams shows raw markdown. Omit `--content-type` (CLI default **`auto`**) or use `--content-type markdown`.

**Do not include the CC line in `$content`.**

PowerShell (read UTF-8 file; no `--content-type` on reply):

```powershell
$content = Get-Content -Raw -Encoding UTF8 "path\to\teams-report.md"
$args = @(
  '--agent','channel','reply',
  '--team-id','3d4f02b8-61b5-4761-8e3e-38a44e26ffba',
  '--channel-id','19:9a8a10354e704b85b6bb729535ef84fe@thread.tacv2',
  '--message-id','<root-message-id>',
  '--content',$content
)
& teams @args
```

### Step C — Second reply: CC only

Post a **separate** reply in the same thread. This is the **only** CC message:

```bash
teams --agent channel reply \
  --team-id "3d4f02b8-61b5-4761-8e3e-38a44e26ffba" \
  --channel-id "19:9a8a10354e704b85b6bb729535ef84fe@thread.tacv2" \
  --message-id "<root-message-id>" \
  --content "CC: Hosamani, Vijaya Kumar Gray, Colin"
```

## Pre-flight checks

1. Step 0 Teams connectivity checked (or re-checked before Step 7).
2. Full report shown in chat (SKILL.md Step 5 complete).
3. User confirmed posting via `AskQuestion` (Step 6).
4. Teams body file has **no** CC line; ASCII separators only.
5. On failure, report the error; do not retry send without user approval.

## Custom channel override

If the user provides a different channel URL:

- Parse `groupId` → `--team-id`
- Parse the channel segment before the channel name → URL-decode → `--channel-id`  
  (e.g. `19%3A9a8a10354e704b85b6bb729535ef84fe%40thread.tacv2` → `19:9a8a10354e704b85b6bb729535ef84fe@thread.tacv2`)

Or resolve by name via `teams --agent channel teams --filter "<team or channel hint>"`.

## Auth streamlining (reference for Step 0)

Tokens last **~24 hours** after login. Silent refresh works on **ds-connect-me VPN**; home Wi-Fi often returns **53003**.

**One-time setup:**

```powershell
[System.Environment]::SetEnvironmentVariable('AITOOLS_MS_SYSTEM_BROWSER', '1', 'User')
```

**Agent sequence at Step 0:**

```powershell
teams --agent auth status
# If authenticated == false AND refreshable == true:
teams auth refresh --force
teams --agent auth status
```

Only prompt for `teams auth login` when refresh fails.

### Do not

- Run `teams auth logout` unless troubleshooting.
- Rely on home-network refresh for Disney Conditional Access.
- Duplicate the CC line in the first reply and Step C.
