# Sync AdPlatformV2/analytics (TWDC) -> fcrivero/AnalyticsScripts (github.com)
$ErrorActionPreference = 'Stop'

$ClonePath = if ($env:ANALYTICS_SCRIPTS_CLONE) { $env:ANALYTICS_SCRIPTS_CLONE } else {
    Join-Path $env:USERPROFILE 'Documents\AI\AnalyticsScripts'
}
$TwdcUrl = 'https://github.twdcgrid.net/AdPlatformV2/analytics.git'
$PersonalUrl = 'https://github.com/fcrivero/AnalyticsScripts.git'

function Ensure-Clone {
    if (Test-Path (Join-Path $ClonePath '.git')) { return }
    $parent = Split-Path $ClonePath -Parent
    if (-not (Test-Path $parent)) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
    Write-Host "Cloning personal repo to $ClonePath ..."
    gh repo clone fcrivero/AnalyticsScripts $ClonePath
    git -C $ClonePath remote add twdc $TwdcUrl
}

function Ensure-Remote($name, $url) {
    $remotes = git -C $ClonePath remote
    if ($remotes -notcontains $name) {
        git -C $ClonePath remote add $name $url
    }
}

Ensure-Clone
Ensure-Remote 'twdc' $TwdcUrl
Ensure-Remote 'origin' $PersonalUrl

Write-Host "Fetching twdc ..."
git -C $ClonePath fetch twdc --prune
Write-Host "Fetching origin ..."
git -C $ClonePath fetch origin

$twdcBranches = git -C $ClonePath branch -r | ForEach-Object { $_.Trim() } |
    Where-Object { $_ -like 'twdc/*' -and $_ -notlike '*HEAD*' }

if (-not $twdcBranches) {
    Write-Error "No twdc/* branches found. Check VPN and twdc remote."
}

$gitCred = @('-c', 'credential.helper=', '-c', 'credential.helper=!gh auth git-credential')

foreach ($ref in $twdcBranches) {
    $branch = $ref -replace '^twdc/', ''
    Write-Host "Pushing branch $branch -> origin ..."
    & git @gitCred -C $ClonePath push origin "refs/remotes/twdc/${branch}:refs/heads/${branch}"
}

Write-Host "Pushing tags ..."
& git @gitCred -C $ClonePath push origin --tags

Write-Host "Done. Branches on origin:"
git -C $ClonePath branch -r | Where-Object { $_ -match 'origin/' }
