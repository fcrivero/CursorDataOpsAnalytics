# CursorDataOpsAnalytics

Personal workspace for todo tracking via Cursor Cloud Agent.

## Files

| File | Purpose |
|------|---------|
| [`personal-todo.md`](personal-todo.md) | Personal / life todo list (source of truth) |
| [`daily-log.md`](daily-log.md) | Work DataOps / Analytics daily activity and todo list |
| [`AGENTS.md`](AGENTS.md) | Instructions for Cursor / Cloud Agent sessions |

## Usage

1. Open this repo in Cursor (local or Cloud Agent).
2. Start an agent session — it reads `AGENTS.md` and the relevant log file.
3. Add, update, or cross out todos in chat; the agent updates the log file.
4. Commit and push to sync across devices.

## Cloud Agent

Start a Cloud Agent at [cursor.com/agents](https://cursor.com/agents) against `fcrivero/CursorDataOpsAnalytics` (branch: `main`).

**Personal todos:** open a session and say *"This is my personal to-do list"* — the agent uses `personal-todo.md`.

**Work todos:** open a session and say *"Daily activity and todo log"* — the agent uses `daily-log.md`.
