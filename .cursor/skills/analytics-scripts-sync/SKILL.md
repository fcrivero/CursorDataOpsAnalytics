---
name: analytics-scripts-sync
description: >-
  Syncs the TWDC GitHub Enterprise repo AdPlatformV2/analytics to the personal
  github.com repo fcrivero/AnalyticsScripts (fetch all branches from TWDC, push
  to personal). Use when the user asks to sync Analytics scripts, mirror
  analytics repo, update AnalyticsScripts, or sync AdPlatformV2 analytics to
  personal GitHub.
---

# Analytics scripts sync (TWDC → personal)

Mirror **source of truth (enterprise):**  
`https://github.twdcgrid.net/AdPlatformV2/analytics`

**Personal backup:**  
`https://github.com/fcrivero/AnalyticsScripts` (**private**)

Primary script content lives on branch **`mstr-admin-scripts`** (AWS/OnPrem/MSTR scripts). **`main`** may only contain a stub README on TWDC — still mirror **all** branches.

## Prerequisites

- VPN / network access to `github.twdcgrid.net`
- `gh` authenticated to **both** hosts (`gh auth status` shows `github.twdcgrid.net` and `github.com`)
- Local working clone (default): `C:\Users\rivef104\Documents\AI\AnalyticsScripts` with remotes:
  - `origin` → `fcrivero/AnalyticsScripts`
  - `twdc` → `AdPlatformV2/analytics`

## When the user asks to sync

1. **Run the sync script** (preferred):

```powershell
& "$env:USERPROFILE\.cursor\skills\analytics-scripts-sync\scripts\sync_analytics_scripts.ps1"
```

2. **If the clone is missing**, create it once:

```powershell
gh repo clone fcrivero/AnalyticsScripts "C:\Users\rivef104\Documents\AI\AnalyticsScripts"
git -C "C:\Users\rivef104\Documents\AI\AnalyticsScripts" remote add twdc https://github.twdcgrid.net/AdPlatformV2/analytics.git
```

3. **Report to the user:**
   - Latest commit SHA on `twdc/mstr-admin-scripts` and `origin/mstr-admin-scripts` (should match after sync)
   - Any branches only on one side
   - Large-file warnings from GitHub (logs >50MB) — informational unless push fails

## Manual equivalent (if script fails)

```powershell
$repo = "C:\Users\rivef104\Documents\AI\AnalyticsScripts"
git -C $repo fetch twdc --prune
git -C $repo fetch origin
# Push each TWDC branch to personal origin
git -C $repo branch -r | Where-Object { $_ -match 'twdc/' -and $_ -notmatch 'HEAD' } | ForEach-Object {
  $b = $_ -replace '^\s*twdc/',''
  git -C $repo push origin "refs/remotes/twdc/${b}:refs/heads/${b}"
}
git -C $repo push origin --tags
```

Use git credential helper for github.com if push hangs:

```powershell
git -c credential.helper= -c "credential.helper=!gh auth git-credential" -C $repo push origin --all
```

Fetch TWDC with:

```powershell
$env:GH_HOST = 'github.twdcgrid.net'
gh auth setup-git  # only if twdc fetch fails with 401; user may need to approve once
Remove-Item Env:GH_HOST -ErrorAction SilentlyContinue
git -C $repo fetch twdc
```

## Security

- **Do not** change `AnalyticsScripts` to **public** without explicit user approval (TWDC content is internal).
- Do not commit `.env`, credentials, or local secrets into either repo.
- This skill only **copies git history/branches**; it does not run Analytics lambdas or touch AWS.

## See also

- [reference.md](reference.md) — remotes, branch map, troubleshooting
