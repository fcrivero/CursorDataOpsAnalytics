# CursorDataOpsAnalytics — Agent Instructions

Personal workspace for Fernando Rivero. This repo holds **two separate todo logs**. Use the correct file based on what the user is working on.

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
5. **Commit changes** when the user asks to save, sync, or commit.

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
5. **Commit changes** when the user asks to save, sync, or commit.

### Response format

When showing the list, always include:

- Full numbered list (done items crossed out)
- **Open:** comma-separated numbers
- **Done:** comma-separated numbers

### Links

Common references are embedded in todo items (Confluence, Teams, Jira, GitHub). Preserve links when editing items.
