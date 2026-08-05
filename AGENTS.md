# Daily Activity & Todo Log Agent

This repository is a **personal daily activity and todo-list log** for Fernando Rivero (DataOps / Analytics Platform).

## Primary file

- **`daily-log.md`** — source of truth for all todo items and their status.

## Agent behavior

1. **Read `daily-log.md` first** on every session before responding.
2. **Update `daily-log.md`** whenever the user adds, changes, crosses out, or renumbers items.
3. **Numbering rules:**
   - Use sequential numbers; never reuse or skip.
   - Done items stay in the list, crossed out with `~~text~~`.
   - New items get the next number (update the "Next item number" header).
4. **Do not take action** on todos unless the user explicitly asks — default mode is log-only.
5. **Commit changes** to `daily-log.md` when the user asks to save, sync, or commit.

## Response format

When showing the list, always include:
- Full numbered list (done items crossed out)
- **Open:** comma-separated numbers
- **Done:** comma-separated numbers

## Links

Common references are embedded in todo items (Confluence, Teams, Jira, GitHub). Preserve links when editing items.
