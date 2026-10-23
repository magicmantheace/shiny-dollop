param(
    [Parameter(Position = 0)]
    [ValidateSet("help", "status", "list", "pull", "test", "start", "resume", "stop", "run-script", "tail")]
    [string]$Action = "help",

    [Parameter(Position = 1)]
    [string]$Value = "",

    [string[]]$ArgumentList = @(),

    [ValidateSet("qa", "alpha", "headless")]
    [string]$Profile = "alpha",

    [int]$TailLines = 60
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$GeneratedRoot = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\dev-runner"
$Worker = Join-Path $PSScriptRoot "underreach-dev-worker.ps1"
$PowerShellExe = (Get-Command powershell.exe -ErrorAction Stop).Source
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

function Ensure-GeneratedRoot {
    if (-not (Test-Path -LiteralPath $GeneratedRoot)) {
        New-Item -ItemType Directory -Path $GeneratedRoot -Force | Out-Null
    }
}

function Get-JobDirectories {
    Ensure-GeneratedRoot
    @(Get-ChildItem -LiteralPath $GeneratedRoot -Directory -ErrorAction SilentlyContinue | Sort-Object LastWriteTimeUtc -Descending)
}

function Read-JobStatus {
    param([Parameter(Mandatory = $true)][System.IO.DirectoryInfo]$Directory)
    $StatusPath = Join-Path $Directory.FullName "status.json"
    $SpecPath = Join-Path $Directory.FullName "spec.json"
    if (Test-Path -LiteralPath $StatusPath) {
        try { return Get-Content -LiteralPath $StatusPath -Raw | ConvertFrom-Json } catch { }
    }
    if (Test-Path -LiteralPath $SpecPath) {
        $Spec = Get-Content -LiteralPath $SpecPath -Raw | ConvertFrom-Json
        return [pscustomobject]@{
            job_name = $Spec.job_name
            state = "starting"
            worker_pid = $null
            started_at = $null
            finished_at = $null
            exit_code = $null
            command = $Spec.display_command
            output_log = (Join-Path $Directory.FullName "output.log")
            error = $null
        }
    }
    return $null
}

function Get-LatestJobDirectory {
    param([string]$RequestedName = "")
    $Jobs = Get-JobDirectories
    if (-not [string]::IsNullOrWhiteSpace($RequestedName)) {
        $Match = $Jobs | Where-Object { $_.Name -like "*$RequestedName*" } | Select-Object -First 1
        if ($null -eq $Match) { throw "No dev-runner job matched '$RequestedName'." }
        return $Match
    }
    $Latest = $Jobs | Select-Object -First 1
    if ($null -eq $Latest) { throw "No dev-runner jobs exist yet." }
    return $Latest
}

function Show-Status {
    param([string]$RequestedName = "")
    $Directory = Get-LatestJobDirectory -RequestedName $RequestedName
    $Status = Read-JobStatus -Directory $Directory
    if ($null -eq $Status) { throw "Job metadata is unreadable: $($Directory.FullName)" }

    $State = [string]$Status.state
    if ($State -eq "running" -and $Status.worker_pid) {
        $Process = Get-Process -Id ([int]$Status.worker_pid) -ErrorAction SilentlyContinue
        if ($null -eq $Process) { $State = "unknown-worker-exited" }
    }

    Write-Host ""
    Write-Host "UNDERREACH DEV RUNNER" -ForegroundColor Cyan
    Write-Host "Job:      $($Status.job_name)"
    Write-Host "State:    $State"
    if ($Status.worker_pid) { Write-Host "PID:      $($Status.worker_pid)" }
    if ($Status.started_at) { Write-Host "Started:  $($Status.started_at)" }
    if ($Status.finished_at) { Write-Host "Finished: $($Status.finished_at)" }
    if ($null -ne $Status.exit_code) { Write-Host "Exit:     $($Status.exit_code)" }
    Write-Host "Command:  $($Status.command)"
    Write-Host "Log:      $($Status.output_log)"
    if ($Status.error) { Write-Host "Error:    $($Status.error)" -ForegroundColor Red }
    Write-Host ""
}

function Start-DetachedJob {
    param(
        [Parameter(Mandatory = $true)][string]$JobName,
        [Parameter(Mandatory = $true)][string]$Executable,
        [string[]]$Arguments = @(),
        [Parameter(Mandatory = $true)][string]$DisplayCommand
    )

    Ensure-GeneratedRoot
    if (-not (Test-Path -LiteralPath $Worker)) { throw "Worker script is missing: $Worker" }
    if (-not (Test-Path -LiteralPath $Executable)) { throw "Executable is missing: $Executable" }

    $SafeName = ($JobName -replace '[^A-Za-z0-9_.-]', '-')
    $Stamp = Get-Date -Format "yyyyMMdd-HHmmss"
    $JobDirectory = Join-Path $GeneratedRoot "$Stamp-$SafeName"
    New-Item -ItemType Directory -Path $JobDirectory -Force | Out-Null

    $Spec = [ordered]@{
        protocol = "underreach.dev-runner-job.v1"
        job_name = $JobName
        created_at = [DateTimeOffset]::UtcNow.ToString("o")
        repo_root = $RepoRoot
        executable = $Executable
        arguments = @($Arguments)
        display_command = $DisplayCommand
    }
    $Spec | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $JobDirectory "spec.json") -Encoding UTF8

    $Process = Start-Process -FilePath $PowerShellExe -ArgumentList @(
        "-NoProfile",
        "-ExecutionPolicy", "Bypass",
        "-File", $Worker,
        "-JobDirectory", $JobDirectory
    ) -WindowStyle Hidden -PassThru

    Write-Host ""
    Write-Host "Detached job started." -ForegroundColor Green
    Write-Host "Job: $JobName"
    Write-Host "Launcher PID: $($Process.Id)"
    Write-Host "Directory: $JobDirectory"
    Write-Host ""
    Write-Host "You may disconnect SSH. Check later with:"
    Write-Host ".\scripts\underreach-dev.ps1 status"
    Write-Host ""
}

Set-Location -LiteralPath $RepoRoot

switch ($Action) {
    "help" {
        Write-Host @"
UNDERREACH REMOTE DEVELOPMENT RUNNER

Phone-friendly commands:
  .\scripts\underreach-dev.ps1 status [name]
  .\scripts\underreach-dev.ps1 list
  .\scripts\underreach-dev.ps1 pull
  .\scripts\underreach-dev.ps1 test [job-name]
  .\scripts\underreach-dev.ps1 start -Profile alpha
  .\scripts\underreach-dev.ps1 resume -Profile alpha
  .\scripts\underreach-dev.ps1 stop
  .\scripts\underreach-dev.ps1 run-script <relative-script-path> -ArgumentList <args>
  .\scripts\underreach-dev.ps1 tail [name] -TailLines 60

Detached commands (test/start/resume/run-script) continue after SSH disconnects.
Artifacts/logs live under:
  unreal\CrawlPresentation\Generated\dev-runner
"@
    }
    "status" { Show-Status -RequestedName $Value }
    "list" {
        $Jobs = Get-JobDirectories
        if ($Jobs.Count -eq 0) { Write-Host "No dev-runner jobs exist yet."; break }
        foreach ($Directory in $Jobs | Select-Object -First 20) {
            $Status = Read-JobStatus -Directory $Directory
            if ($null -ne $Status) {
                "{0,-28} {1,-22} {2}" -f $Directory.Name, $Status.state, $Status.job_name
            }
        }
    }
    "pull" {
        Write-Host "Checking working tree before pull..."
        & git status --short --branch
        if ($LASTEXITCODE -ne 0) { throw "git status failed." }
        Write-Host "Pulling current branch with fast-forward only..."
        & git pull --ff-only
        if ($LASTEXITCODE -ne 0) { throw "git pull --ff-only failed. Working tree was not reset or cleaned." }
    }
    "test" {
        if (-not (Test-Path -LiteralPath $Python)) { throw "Project Python is missing: $Python" }
        $JobName = if ([string]::IsNullOrWhiteSpace($Value)) { "full-tests" } else { $Value }
        Start-DetachedJob -JobName $JobName -Executable $Python -Arguments @("-m", "pytest", "-q") -DisplayCommand ".venv\Scripts\python.exe -m pytest -q"
    }
    "start" {
        $Script = Join-Path $PSScriptRoot "start-underreach-alpha.ps1"
        Start-DetachedJob -JobName "underreach-alpha" -Executable $PowerShellExe -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Script, "-Profile", $Profile) -DisplayCommand ".\scripts\start-underreach-alpha.ps1 -Profile $Profile"
    }
    "resume" {
        $Script = Join-Path $PSScriptRoot "start-underreach-alpha.ps1"
        Start-DetachedJob -JobName "underreach-alpha-resume" -Executable $PowerShellExe -Arguments @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Script, "-Profile", $Profile, "-Resume") -DisplayCommand ".\scripts\start-underreach-alpha.ps1 -Profile $Profile -Resume"
    }
    "stop" {
        $Script = Join-Path $PSScriptRoot "stop-underreach-alpha.ps1"
        if (-not (Test-Path -LiteralPath $Script)) { throw "Stop script is missing: $Script" }
        & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $Script
        if ($LASTEXITCODE -ne 0) { throw "Underreach stop request failed with exit code $LASTEXITCODE." }
    }
    "run-script" {
        if ([string]::IsNullOrWhiteSpace($Value)) { throw "run-script requires a repository-relative .ps1 path." }
        $Script = Join-Path $RepoRoot $Value
        $Script = [System.IO.Path]::GetFullPath($Script)
        if (-not $Script.StartsWith([System.IO.Path]::GetFullPath($RepoRoot), [System.StringComparison]::OrdinalIgnoreCase)) {
            throw "Script path must stay inside the repository."
        }
        if ([System.IO.Path]::GetExtension($Script) -ne ".ps1") { throw "run-script accepts only .ps1 files." }
        if (-not (Test-Path -LiteralPath $Script)) { throw "Script not found: $Script" }
        $JobName = [System.IO.Path]::GetFileNameWithoutExtension($Script)
        $Args = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $Script) + @($ArgumentList)
        $ShownArgs = if ($ArgumentList.Count -gt 0) { " " + ($ArgumentList -join " ") } else { "" }
        Start-DetachedJob -JobName $JobName -Executable $PowerShellExe -Arguments $Args -DisplayCommand "$Value$ShownArgs"
    }
    "tail" {
        $Directory = Get-LatestJobDirectory -RequestedName $Value
        $Log = Join-Path $Directory.FullName "output.log"
        if (-not (Test-Path -LiteralPath $Log)) { throw "Job log does not exist yet: $Log" }
        Get-Content -LiteralPath $Log -Tail $TailLines
    }
}
