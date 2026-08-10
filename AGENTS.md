# CursorDataOpsAnalytics — Agent Instructions

Personal workspace for Fernando Rivero. This repo holds **two separate todo logs**. Use the correct file based on what the user is working on.

---

## Auto-Sync (applies to every log change)

After **any** change to a todo file (add, edit, cross-out, renumber, or archive), immediately sync it to the remote — do **not** wait for the user to ask to save/commit:

```bash
scripts/sync-log.sh ["optional commit message"]
```

The script stages the log files (`personal-todo.md`, `daily-log.md`, and any `*-log.md` archive), commits when there are changes, and pushes the current branch. It is a no-op when nothing changed, so it is always safe to run.

**Monthly archive:** at the start of a new month, freeze the previous month's `daily-log.md` into `<month>-log.md` (for example `july-log.md`), carry forward the open items into a fresh `daily-log.md`, and auto-sync.

---

## Personal To-Do List Agent

**Use when:** the user mentions personal todos, home/life tasks, or this is clearly not a work/DataOps item.

**Primary file:** `personal-todo.md`

### Behavior

1. **Read `personal-todo.md` first** on every session before responding.
2. **Update `personal-todo.md`** whenever the user adds, changes, crosses out, or renumbers items.
3. **Numbering rules:**
   - Use sequential numbers; never reuse or skip.
   - Done items stay in the list, crossed out with `~~text~~`.
   - New items get the next number (update the "Next item number" header).
4. **Do not take action** on todos unless the user explicitly asks — default mode is log-only.
5. **Auto-sync** after every change by running `scripts/sync-log.sh` (commit + push) — no need to wait for a save/commit request.

### Response format

After every add, remove, cross-out, or edit, show:

- Full numbered list (done items crossed out)
- **Open:** comma-separated numbers
- **Done:** comma-separated numbers

---

## Daily Activity & Todo Log Agent

**Use when:** the user mentions work, DataOps, Analytics Platform, daily log, or items in `daily-log.md`.

**Primary file:** `daily-log.md`

### Behavior

1. **Read `daily-log.md` first** on every session before responding.
2. **Update `daily-log.md`** whenever the user adds, changes, crosses out, or renumbers items.
3. **Numbering rules:**
   - Use sequential numbers; never reuse or skip.
   - Done items stay in the list, crossed out with `~~text~~`.
   - New items get the next number (update the "Next item number" header).
4. **Do not take action** on todos unless the user explicitly asks — default mode is log-only.
5. **Auto-sync** after every change by running `scripts/sync-log.sh` (commit + push) — no need to wait for a save/commit request.

### Response format

When showing the list, always include:

- Full numbered list (done items crossed out)
- **Open:** comma-separated numbers
- **Done:** comma-separated numbers

### Links

Common references are embedded in todo items (Confluence, Teams, Jira, GitHub). Preserve links when editing items.
