# AnalyticsScripts mirror — reference

| Item | Value |
|------|--------|
| TWDC repo | `AdPlatformV2/analytics` |
| TWDC URL | `https://github.twdcgrid.net/AdPlatformV2/analytics.git` |
| Personal repo | `fcrivero/AnalyticsScripts` |
| Personal URL | `https://github.com/fcrivero/AnalyticsScripts.git` |
| Default local clone | `C:\Users\rivef104\Documents\AI\AnalyticsScripts` |
| Content branch | `mstr-admin-scripts` |

## Remotes in local clone

```
origin  → github.com/fcrivero/AnalyticsScripts
twdc    → github.twdcgrid.net/AdPlatformV2/analytics
```

## First-time personal repo creation (already done)

```powershell
Remove-Item Env:GH_HOST -ErrorAction SilentlyContinue
gh repo create fcrivero/AnalyticsScripts --private --description "Personal mirror of AdPlatformV2/analytics (TWDC Grid)"
```

Initial full push was performed from `Documents\AI\analytics-twdc` with remotes `origin` (TWDC) and `personal` (github.com).

## gh host switching

- **github.com:** unset `GH_HOST` before `gh repo create`, `gh repo view fcrivero/...`
- **TWDC:** `$env:GH_HOST = 'github.twdcgrid.net'` before `gh repo view AdPlatformV2/analytics`

## Large files

GitHub may warn on files >50MB (e.g. `migration.log` under OnPrem Scripts). Push usually still succeeds; use Git LFS only if GitHub rejects the push.
