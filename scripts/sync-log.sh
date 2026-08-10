#!/usr/bin/env bash
#
# Auto-sync the todo logs to the remote.
#
# Stages only the known log/archive Markdown files, commits when there are
# staged changes, and pushes to the current branch. Safe to run repeatedly:
# it is a no-op when nothing changed.
#
# Usage:
#   scripts/sync-log.sh ["optional commit message"]
#
# SECURITY-REVIEW: performs git commit/push using the caller's already-configured
# git credentials. It never handles or logs secrets and only stages an explicit,
# fixed allowlist of Markdown log files (no user-controlled paths).

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Explicit allowlist of files this workspace treats as logs/archives.
LOG_FILES=(personal-todo.md daily-log.md)

# Include any monthly archives (e.g. july-log.md, 2026-07-log.md) if present.
shopt -s nullglob
LOG_FILES+=(*-log.md)
shopt -u nullglob

# Stage only the log files that actually exist.
staged_any=0
for f in "${LOG_FILES[@]}"; do
  if [ -f "$f" ]; then
    git add -- "$f"
    staged_any=1
  fi
done

if [ "$staged_any" -eq 0 ]; then
  echo "sync-log: no log files found to sync."
  exit 0
fi

if git diff --cached --quiet; then
  echo "sync-log: no changes to sync."
  exit 0
fi

commit_msg="${1:-chore(log): auto-sync todo logs ($(date -u +%Y-%m-%dT%H:%M:%SZ))}"
git commit -m "$commit_msg"

branch="$(git rev-parse --abbrev-ref HEAD)"
git push origin "$branch"
echo "sync-log: synced to origin/${branch}."
