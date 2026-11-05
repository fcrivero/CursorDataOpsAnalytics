---
name: rds-query
description: Query AWS RDS PostgreSQL (Xwing/MSTR, shield schema) using the RDS_NoopenAI Python CLI. Use when the user asks database questions in natural language, mentions RDS, xwing, mstr, shield schema, or wants to explore tables, run SQL, or analyze data from dev/sandbox/prod.
---

# RDS Natural Language Query

Answer database questions by exploring schema and running SQL through the CLI at:

`C:\Users\rivef104\Documents\AI\RDS_NoopenAI`

**Never** write ad-hoc Python/SQLAlchemy connection code. **Always** use `main.py`.

## Python command

```powershell
cd "C:\Users\rivef104\Documents\AI\RDS_NoopenAI"
.\.venv-local\Scripts\python.exe main.py <subcommand> [options]
```

If `.venv-local` is missing, create it: `python -m venv .venv-local` then `pip install -r requirements.txt`.

## Environments

| Env | Flag | Access |
|-----|------|--------|
| dev (default) | `-e dev` | Read-only SELECT |
| prod | `-e prod` | Read-only SELECT |
| sandbox | `-e sandbox` | SELECT + INSERT/UPDATE/DELETE |

Default schema: `shield` (from `databases.yaml`).

**Default to `dev`** unless the user names another environment. Confirm before using `prod`. Use `sandbox` only when the user explicitly asks to write data.

## Workflow

1. **Clarify** environment if ambiguous.
2. **Discover schema** when table/column names are unknown:
   - `main.py tables -e <env>`
   - `main.py describe <table> -e <env>`
3. **Draft SQL** as a single statement. Rules enforced by the CLI:
   - dev/prod: SELECT only; LIMIT 100 auto-added if missing
   - sandbox: SELECT/INSERT/UPDATE/DELETE allowed
   - Never: DROP, TRUNCATE, ALTER, CREATE, multi-statement SQL
4. **Execute**:
   ```powershell
   .\.venv-local\Scripts\python.exe main.py query "SELECT ..." -e dev
   ```
   For complex SQL, write to a temp `.sql` file and use `-f query.sql`.
5. **Answer in plain language** — summarize findings, cite row counts, show key rows in a table when helpful.

## CLI reference

```powershell
main.py environments          # list envs
main.py test -e dev           # test connection
main.py test --all            # test all envs
main.py tables -e dev
main.py describe my_table -e dev
main.py query "SELECT ..." -e dev
main.py query -f query.sql -e dev
```

## Safety

- Never read, log, or echo `.env` passwords.
- Never bypass `main.py` validation.
- If a query is rejected, explain why and rewrite compliant SQL.
- If connection fails, suggest VPN/network access — RDS is not publicly open.

## Example

**User:** "How many rows are in the campaign table in dev?"

**Agent:**
1. `main.py describe campaign -e dev` (confirm table exists)
2. `main.py query "SELECT COUNT(*) AS row_count FROM campaign" -e dev`
3. Answer: "The campaign table in dev has N rows."
