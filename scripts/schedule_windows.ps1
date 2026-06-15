# ─── Windows Task Scheduler Setup ───────────────────────────────────────────
# Run as administrator to register a daily 7:00 AM run.
#
# Usage:
#   .\scripts\schedule_windows.ps1
#
# To remove later:
#   schtasks /delete /tn "JobHuntBot" /f

$projectPath = (Get-Location).Path
$pythonExe = (Get-Command python).Source

if (-not $pythonExe) {
    Write-Host "ERROR: Python not found on PATH. Install Python 3.11 first." -ForegroundColor Red
    exit 1
}

$action = "& '$pythonExe' '$projectPath\main.py'"
$cmd = "powershell.exe -NoProfile -Command `"Set-Location '$projectPath'; $action`""

Write-Host "Registering scheduled task 'JobHuntBot'..."
Write-Host "  Project: $projectPath"
Write-Host "  Python : $pythonExe"
Write-Host ""

schtasks /create `
    /tn "JobHuntBot" `
    /tr "$cmd" `
    /sc daily `
    /st 07:00 `
    /f

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "✓ Task registered. JobHuntBot will run daily at 7:00 AM." -ForegroundColor Green
    Write-Host ""
    Write-Host "To run manually right now:  schtasks /run /tn JobHuntBot"
    Write-Host "To check status:            schtasks /query /tn JobHuntBot"
    Write-Host "To remove:                  schtasks /delete /tn JobHuntBot /f"
} else {
    Write-Host "✗ Failed to register task. Re-run as Administrator." -ForegroundColor Red
}
