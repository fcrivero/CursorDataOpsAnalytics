# Cursor skills — DataOps (SKRULL) & Analytics (ADIA)

Author-maintained agent skills copied from `~/.cursor/skills`. Install by syncing this folder into your Cursor skills path (or symlink):

```powershell
# Example: mirror into user skills (review diff first)
robocopy "%USERPROFILE%\.cursor\skills-source\CursorDataOpsAnalytics\.cursor\skills" "%USERPROFILE%\.cursor\skills" /E
```

After clone, point the source at this repo:  
`C:\Users\rivef104\Documents\AI\CursorDataOpsAnalytics\.cursor\skills`

Shared ADINC reference: [`adinc-jira-notes.md`](adinc-jira-notes.md) (linked as `../adinc-jira-notes.md` from skill folders).

## DataOps / SKRULL / ADINC / PagerDuty

| Skill | Purpose |
| ----- | ------- |
| `confluence-adinc-history` | Publish closed ADINC tickets to Confluence Incident History |
| `dataops-pd-incident-analysis` | Deep dive on one PagerDuty Data Ops incident |
| `dataops-pd-incidents` | List Data Ops PD incidents for a time window |
| `dataops-pd-long-run` | Triage `[Long Run]` PagerDuty alerts |
| `dataops-shift-summary` | Executive Data Ops shift summary |
| `jira-adinc-audit` | Audit ADINC ticket fields and RCA |
| `jira-adinc-tickets` | Create/update ADINC tickets |
| `jira-skrull-audit` | SKRULL board hygiene audit (scripts + Excel template) |
| `jira-skrull-tickets` | Create SKRULL stories and tasks |
| `oncall-handoff-incidents` | High-urgency on-call handoff summary |
| `pagerduty-incident-identity` | Safety rules before PD incident fetch/mutate |

## Analytics (ADIA)

| Skill | Purpose |
| ----- | ------- |
| `adia-status-report` | ADIA Jira status report for a period; optional Teams post |
| `jira-adia-tickets` | Create ADIA Jira stories/tasks |

## MCP servers typically required

`user-jira-server`, `user-pagerduty-mcp-manual`, `user-ads-databricks`, `user-confluence-disney` (per skill). Teams/outlook CLIs where noted in each `SKILL.md`.
