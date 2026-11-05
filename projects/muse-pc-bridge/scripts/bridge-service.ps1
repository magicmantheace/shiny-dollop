# muse-pc-bridge — service-form management (v1 S3).
#
# The "service" is a per-user logon Scheduled Task that opens the
# supervisor in a VISIBLE console (never a hidden background process):
# closing that console stops the agent — the kill switch is preserved.
#
#   .\bridge-service.ps1 -Action install     register the logon task
#   .\bridge-service.ps1 -Action start       start it now
#   .\bridge-service.ps1 -Action stop        stop task + supervisor/agent
#   .\bridge-service.ps1 -Action status      task + supervisor state
#   .\bridge-service.ps1 -Action uninstall   remove the task
#
# install/uninstall touch Scheduled Tasks and may prompt for UAC —
# run them yourself, interactively.

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'uninstall', 'start', 'stop', 'status')]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$TaskName = "Muse PC Bridge (supervised)"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot "start-bridge-service.cmd"
$StateDir = Join-Path $ProjectRoot "agent\state"
$StatusFile = Join-Path $StateDir "supervisor-status.json"

switch ($Action) {
    'install' {
        $action = New-ScheduledTaskAction -Execute "cmd.exe" `
            -Argument "/c `"$Launcher`"" -WorkingDirectory $ProjectRoot
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -RestartCount 0
        Register-ScheduledTask -TaskName $TaskName -Action $action `
            -Trigger $trigger -Settings $settings `
            -Description "muse-pc-bridge supervised agent (visible console; closing it stops the bridge)" `
            -Force | Out-Null
        Write-Output "Installed logon task '$TaskName'. It will open the supervisor console at logon. Run -Action start to start it now."
    }
    'uninstall' {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output "Removed logon task '$TaskName'. (Supervisor/agent processes were not touched; stop them first with -Action stop if they are running.)"
    }
    'start' {
        Start-ScheduledTask -TaskName $TaskName
        Write-Output "Started '$TaskName'. The supervisor console should be visible on the desktop."
    }
    'stop' {
        Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        # Stopping the task does not always reap the console's children;
        # stop the supervisor (its status file names the agent pid, and
        # stopping the supervisor stops the agent by design).
        $stopped = @()
        Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='py.exe'" |
            Where-Object { $_.CommandLine -match 'supervisor\.py|bridge_agent\.py' } |
            ForEach-Object {
                Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
                $stopped += $_.ProcessId
            }
        if ($stopped.Count -gt 0) {
            Write-Output "Stopped bridge process(es): $($stopped -join ', ')"
        } else {
            Write-Output "No running supervisor/agent processes found."
        }
    }
    'status' {
        $task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
        if ($null -eq $task) {
            Write-Output "Task '$TaskName' is NOT installed."
        } else {
            $info = Get-ScheduledTaskInfo -TaskName $TaskName
            Write-Output "Task '$TaskName': state=$($task.State), lastRun=$($info.LastRunTime), lastResult=$($info.LastTaskResult)"
        }
        if (Test-Path $StatusFile) {
            Write-Output "Supervisor status file:"
            Get-Content -Raw $StatusFile | Write-Output
        } else {
            Write-Output "No supervisor status file yet ($StatusFile)."
        }
    }
}
