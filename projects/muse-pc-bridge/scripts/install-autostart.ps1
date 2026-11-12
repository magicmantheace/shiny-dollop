# OPTIONAL: register a logon task that starts the muse-pc-bridge agent
# in a VISIBLE console window at logon (same indicator + kill-switch
# model as scripts\start-bridge.cmd -- closing the window stops it).
#
# This is NOT required for v0. Only run it if you want the agent to
# come up automatically when you log on to Windows.
#
# Run from an ordinary (non-admin) PowerShell:
#   powershell -ExecutionPolicy Bypass -File .\install-autostart.ps1
#
# Remove later with:
#   Unregister-ScheduledTask -TaskName "Muse PC Bridge" -Confirm:$false

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $PSScriptRoot
$startCmd = Join-Path $projectDir "scripts\start-bridge.cmd"
if (-not (Test-Path $startCmd)) {
    throw "start-bridge.cmd not found at $startCmd"
}

$action = New-ScheduledTaskAction -Execute "cmd.exe" `
    -Argument "/c `"$startCmd`""
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -ExecutionTimeLimit (New-TimeSpan -Days 0)

Register-ScheduledTask -TaskName "Muse PC Bridge" `
    -Action $action -Trigger $trigger -Settings $settings `
    -Description "muse-pc-bridge agent (visible console; closing it stops the agent)" `
    -Force | Out-Null

Write-Host "Registered logon task 'Muse PC Bridge'. It starts the agent"
Write-Host "in a visible console at next logon. To start it right now:"
Write-Host "  Start-ScheduledTask -TaskName 'Muse PC Bridge'"
