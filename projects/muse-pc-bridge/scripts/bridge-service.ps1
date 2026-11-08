# muse-pc-bridge -- service-form management (v1 S3).
#
# The "service" is a per-user logon Scheduled Task that opens the
# supervisor in a VISIBLE console (never a hidden background process):
# closing that console stops the agent -- the kill switch is preserved.
#
#   .\bridge-service.ps1 -Action install     register the logon task
#   .\bridge-service.ps1 -Action start       start it now
#   .\bridge-service.ps1 -Action stop        stop task + supervisor/agent
#   .\bridge-service.ps1 -Action status      task + supervisor state
#   .\bridge-service.ps1 -Action uninstall   remove the task
#
# install/uninstall touch Scheduled Tasks and may prompt for UAC --
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
        $taskAction = New-ScheduledTaskAction -Execute "cmd.exe" `
            -Argument "/c `"$Launcher`"" -WorkingDirectory $ProjectRoot
        $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -RestartCount 0
        Register-ScheduledTask -TaskName $TaskName -Action $taskAction `
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
        # Graceful first: ask the supervisor for an audited shutdown
        # by dropping a stop-request file into the state dir. The
        # supervisor consumes it and stops the agent through its
        # normal path, so the audit log gains its server_stop entry.
        # Killing processes outright would bypass that entry -- the
        # sweep below is only the fallback for a supervisor that
        # does not answer within 20 s.
        $requestFile = Join-Path $StateDir "stop-request.json"
        @{ requested_at = (Get-Date).ToUniversalTime().ToString("o")
           requested_by = "bridge-service.ps1 -Action stop" } |
            ConvertTo-Json | Set-Content -Encoding UTF8 $requestFile
        $graceful = $false
        $deadline = (Get-Date).AddSeconds(20)
        while ((Get-Date) -lt $deadline) {
            if (Test-Path $StatusFile) {
                try {
                    $supState = (Get-Content -Raw $StatusFile |
                        ConvertFrom-Json).state
                    if ($supState -eq 'stopped') { $graceful = $true; break }
                } catch { }
            }
            Start-Sleep -Milliseconds 500
        }
        if ($graceful) {
            Write-Output "Bridge stopped gracefully (audited shutdown -- see agent\logs\audit.jsonl for server_stop)."
            break
        }
        Write-Warning "Graceful stop did not complete within 20 s; terminating processes directly. The audit log may miss its server_stop entry for this stop."
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
