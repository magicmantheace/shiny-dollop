# muse-pc-bridge -- BOOT CORE management (v1.1).
#
# The core is a machine-boot Scheduled Task running the supervisor
# headless as SYSTEM (agent\supervisor.py --headless via
# scripts\start-bridge-core.cmd): the bridge comes up with the
# machine, before and without any user logon. The avatar stays a
# per-user logon component and ATTACHES to this core display-only --
# closing the avatar does not stop the core.
#
#   .\bridge-core.ps1 -Action install     register the boot task
#   .\bridge-core.ps1 -Action uninstall   remove the boot task
#   .\bridge-core.ps1 -Action start       start the core now
#   .\bridge-core.ps1 -Action stop        stop task + core processes
#   .\bridge-core.ps1 -Action status      task + supervisor state
#
# install/uninstall create a SYSTEM task and WILL prompt for UAC --
# run this yourself, interactively, from an elevated PowerShell.
# Installing is an activation step: do it only when you mean to
# switch the bridge to the boot topology. Before installing, stop
# any other bridge form (console supervisor / avatar in own mode) --
# two supervisors cannot own one agent port. ROLLBACK: uninstall
# this task and go back to the logon form (bridge-service.ps1
# -Action install, or the avatar task) -- nothing else changes; the
# config, token, state dir and audit log are shared and untouched.

param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('install', 'uninstall', 'start', 'stop', 'status')]
    [string]$Action
)

$ErrorActionPreference = "Stop"
$TaskName = "Muse PC Bridge (core)"
$LegacyTaskName = "Muse PC Bridge (supervised)"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Launcher = Join-Path $PSScriptRoot "start-bridge-core.cmd"
$StateDir = Join-Path $ProjectRoot "agent\state"
$StatusFile = Join-Path $StateDir "supervisor-status.json"

switch ($Action) {
    'install' {
        $legacy = Get-ScheduledTask -TaskName $LegacyTaskName -ErrorAction SilentlyContinue
        if ($null -ne $legacy -and $legacy.State -ne 'Disabled') {
            Write-Warning "The logon task '$LegacyTaskName' is still enabled. Disable or uninstall it (bridge-service.ps1) before starting the core, or the two supervisors will fight over the agent port."
        }
        $taskAction = New-ScheduledTaskAction -Execute "cmd.exe" `
            -Argument "/c `"$Launcher`"" -WorkingDirectory $ProjectRoot
        $trigger = New-ScheduledTaskTrigger -AtStartup
        $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" `
            -LogonType ServiceAccount -RunLevel Highest
        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
            -DontStopIfGoingOnBatteries -ExecutionTimeLimit ([TimeSpan]::Zero) `
            -RestartCount 0 -StartWhenAvailable
        Register-ScheduledTask -TaskName $TaskName -Action $taskAction `
            -Trigger $trigger -Principal $principal -Settings $settings `
            -Description "muse-pc-bridge core: headless supervisor at machine boot (no logon needed); avatar attaches at logon" `
            -Force | Out-Null
        Write-Output "Installed boot task '$TaskName'. The bridge core will start at machine boot, before logon. Run -Action start to start it now (stop other bridge forms first)."
    }
    'uninstall' {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Write-Output "Removed boot task '$TaskName'. (Core processes were not touched; stop them first with -Action stop if they are running.)"
    }
    'start' {
        Start-ScheduledTask -TaskName $TaskName
        Write-Output "Started '$TaskName'. Check -Action status in a few seconds; the supervisor log is agent\state\supervisor-core.log."
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
           requested_by = "bridge-core.ps1 -Action stop" } |
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
            Write-Output "Core stopped gracefully (audited shutdown -- see agent\logs\audit.jsonl for server_stop)."
            break
        }
        Write-Warning "Graceful stop did not complete within 20 s; terminating processes directly. The audit log may miss its server_stop entry for this stop."
        # Same process sweep as bridge-service.ps1: python processes
        # running this project's supervisor or agent.
        $stopped = @()
        Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe' OR Name='py.exe' OR Name='pyw.exe'" |
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
