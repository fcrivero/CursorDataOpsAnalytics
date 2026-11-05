# ADINC Weekly Audit — Windows Task Scheduler helper
#
# Prerequisites:
#   1. Copy .env.example to .env and fill in JIRA_TOKEN + email settings
#   2. Test manually: python run_weekly_audit.py --dry-run
#   3. Test email:     python run_weekly_audit.py
#
# Register weekly task (Mondays 8:00 AM local time):
#   powershell -ExecutionPolicy Bypass -File register_weekly_task.ps1
#
# Remove task:
#   Unregister-ScheduledTask -TaskName "ADINC-Weekly-Audit" -Confirm:$false

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "run_weekly_audit.py"
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source

if (-not $PythonExe) {
    $PythonExe = (Get-Command py -ErrorAction SilentlyContinue).Source
    if ($PythonExe) { $PythonExe = "py -3" }
}

if (-not (Test-Path $PythonScript)) {
    Write-Error "run_weekly_audit.py not found at $PythonScript"
}

if (-not (Test-Path (Join-Path $ScriptDir ".env"))) {
    Write-Warning ".env not found. Copy .env.example to .env and configure before scheduling."
}

$TaskName = "ADINC-Weekly-Audit"
$Action = New-ScheduledTaskAction -Execute "python" -Argument "`"$PythonScript`"" -WorkingDirectory $ScriptDir
$Trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Monday -At "08:00"
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Settings $Settings -Force

Write-Host "Registered scheduled task: $TaskName (every Monday at 8:00 AM)"
Write-Host "Logs: check reports/ folder under $ScriptDir"
