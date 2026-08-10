# CursorDataOpsAnalytics

Personal workspace for todo tracking via Cursor Cloud Agent.

## Files

| File | Purpose |
| ---- | ------- |
| [`personal-todo.md`](personal-todo.md) | Personal / life todo list (source of truth) |
| [`daily-log.md`](daily-log.md) | Work DataOps / Analytics daily activity and todo list (current month) |
| [`july-log.md`](july-log.md) | Frozen monthly archive (July 2026) |
| [`scripts/sync-log.sh`](scripts/sync-log.sh) | Auto-sync helper: stage logs, commit, and push |
| [`AGENTS.md`](AGENTS.md) | Instructions for Cursor / Cloud Agent sessions |

## Usage

1. Open this repo in Cursor (local or Cloud Agent).
2. Start an agent session — it reads `AGENTS.md` and the relevant log file.
3. Add, update, or cross out todos in chat; the agent updates the log file.
4. The agent **auto-syncs** after every change via `scripts/sync-log.sh` (commit + push), so logs stay current across devices without a manual save.

Each month is archived: the previous `daily-log.md` is frozen into `<month>-log.md` (e.g. `july-log.md`) and open items are carried forward into a fresh `daily-log.md`.

### Auto-sync

```bash
scripts/sync-log.sh ["optional commit message"]
```

Stages the log files (`personal-todo.md`, `daily-log.md`, and any `*-log.md` archive), commits when there are changes, and pushes the current branch. It is a no-op when nothing changed.

## Cloud Agent

Start a Cloud Agent at [cursor.com/agents](https://cursor.com/agents) against `fcrivero/CursorDataOpsAnalytics` (branch: `main`).

**Personal todos:** open a session and say *"This is my personal to-do list"* — the agent uses `personal-todo.md`.

**Work todos:** open a session and say *"Daily activity and todo log"* — the agent uses `daily-log.md`.

## Development

The logs are Markdown, so the "app" here is Markdown quality tooling. Dependencies are managed with npm (Node 18+).

```bash
npm ci            # install pinned dev tooling
npm run lint      # markdownlint-cli2 over all *.md files
npm run check-links  # validate relative + public links (private SSO hosts skipped)
npm run check     # lint + link-check together
npm run lint:fix  # auto-fix lint issues
```

Config lives in `.markdownlint-cli2.jsonc` (lint rules) and `.markdown-link-check.json` (link-check, with enterprise/SSO hosts ignored to avoid false failures). In a Cloud Agent, `.cursor/environment.json` runs `npm ci` on setup so these commands are ready immediately.
