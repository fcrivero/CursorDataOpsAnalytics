#!/usr/bin/env bash
# shellcheck disable=SC2016  # jq filters are single-quoted on purpose ($m/$v/$max are jq vars)

# Context-safe reader for the HOOP discovery index (~2155 records / ~1.5MB): it never
# prints the whole index. It resolves hoops-index.json (AIX_BUNDLES_DIR, the registry
# cache, then the repo-root copy only when origin ends in aix-registry), routes only a
# schemaVersion-1.x index, and jq-emits only a capped subset. Modes: summary (default)
# | id <HOOP-NNNN> | search <text> | status|doctype|agentuse|scope <v> | converted.
# Every record-returning mode projects a compact field set and caps at 100.
set -euo pipefail

mode="${1:-summary}"
arg="${2:-}"
MAX=100

# Emit an _error payload and stop. Build it with jq when available so an
# index-derived message (e.g. a crafted schemaVersion) can't break the JSON; the
# only jq-absent caller passes a hardcoded literal.
err() {
  if command -v jq >/dev/null 2>&1; then
    jq -cn --arg e "$1" '{hoops: [], _error: $e}'
  else
    printf '{"hoops":[],"_error":"%s"}\n' "$1"
  fi
  exit 0
}

resolve_index() {
  if [ -n "${AIX_BUNDLES_DIR:-}" ] && [ -f "$AIX_BUNDLES_DIR/hoops-index.json" ]; then
    printf '%s\n' "$AIX_BUNDLES_DIR/hoops-index.json"; return 0
  fi
  local cache="${AIX_CONFIG_DIR:-$HOME/.aix}/cache/hoops-index.json"
  if [ -f "$cache" ]; then printf '%s\n' "$cache"; return 0; fi
  if git config --get remote.origin.url 2>/dev/null | grep -qiE '[/:]aix-registry(\.git)?$'; then
    local root; root="$(git rev-parse --show-toplevel 2>/dev/null)"
    if [ -n "$root" ] && [ -f "$root/hoops-index.json" ]; then
      printf '%s\n' "$root/hoops-index.json"; return 0
    fi
  fi
  return 1
}

idx="$(resolve_index)" || err "hoops-index.json not found - run: aix sync (or set AIX_BUNDLES_DIR)"
command -v jq >/dev/null 2>&1 || err "jq is required for the context-safe HOOP index reader - install jq"

# Contract: only a schemaVersion major 1 index routes - a newer major may rename
# fields, and routing it would read every label as null. This one gate covers
# every mode, and a malformed/unreadable index trips it first.
sv="$(jq -r '(.schemaVersion // "")' "$idx" 2>/dev/null)" || err "hoops-index.json unreadable - run: aix sync"
case "$sv" in
  1.*) ;;
  *) err "hoops-index.json schemaVersion '$sv' is not 1.x - run: aix update" ;;
esac

# Run jq against the pinned index, falling back to _error JSON (exit 0) on any jq
# failure, so a malformed/truncated index behaves like every other failure path.
runjq() { jq "$@" "$idx" || err "hoops-index.json unreadable - run: aix sync"; }

# Compact, capped, null-safe projection with the match count so truncation is always
# visible.
project='{matched: ($m | length), truncated: (($m | length) > $max),
  hoops: ($m | .[:$max] | map({id, name, status, scope, docType, agentUse,
    conversionStatus, enforceable, canonicalUrl, convertedModule}))}'

case "$mode" in
  summary)
    runjq --argjson max "$MAX" '(.hoops // []) as $h | {
      schemaVersion, generatedAt,
      total: ($h | length),
      byStatus: ($h | group_by(.status) | map({((.[0].status) // "unknown"): length}) | add),
      byDocType: ($h | group_by(.docType) | map({((.[0].docType) // "unknown"): length}) | add),
      byAgentUse: ($h | group_by(.agentUse) | map({((.[0].agentUse) // "unknown"): length}) | add),
      convertedCount: ([$h[] | select(.conversionStatus == "converted")] | length),
      converted: ([$h[] | select(.conversionStatus == "converted")
        | {id, name, scope, docType, agentUse, convertedModule, canonicalUrl}] | .[:$max]),
      hint: "run: load-index.sh <mode> [arg] - modes: id <HOOP-NNNN> | search <text> | status|doctype|agentuse|scope <v> | converted"
    }'
    ;;
  id)
    up="$(printf '%s' "$arg" | tr '[:lower:]' '[:upper:]')"
    runjq --arg id "$up" 'first((.hoops // [])[] | select((.id // "") == $id)) // empty'
    ;;
  search)
    runjq --arg q "$arg" --argjson max "$MAX" '($q | ascii_downcase) as $ql |
      [(.hoops // [])[] | select(((.id // "") | ascii_downcase | contains($ql))
        or ((.name // "") | ascii_downcase | contains($ql)))] as $m | '"$project"
    ;;
  status)
    runjq --arg v "$arg" --argjson max "$MAX" '[(.hoops // [])[] | select(.status == $v)] as $m | '"$project"
    ;;
  doctype)
    runjq --arg v "$arg" --argjson max "$MAX" '[(.hoops // [])[] | select(.docType == $v)] as $m | '"$project"
    ;;
  agentuse)
    runjq --arg v "$arg" --argjson max "$MAX" '[(.hoops // [])[] | select(.agentUse == $v)] as $m | '"$project"
    ;;
  scope)
    runjq --arg v "$arg" --argjson max "$MAX" '[(.hoops // [])[] | select(.scope == $v)] as $m | '"$project"
    ;;
  converted)
    runjq --argjson max "$MAX" '[(.hoops // [])[] | select(.conversionStatus == "converted")] as $m | '"$project"
    ;;
  *)
    err "unknown mode - use: summary | id | search | status | doctype | agentuse | scope | converted"
    ;;
esac
