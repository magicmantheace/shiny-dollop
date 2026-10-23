param(
    [ValidateSet("qa", "alpha", "headless")]
    [string]$Profile = "alpha",
    [switch]$Resume,
    [double]$DurationSeconds = 0,
    [int]$ViewerPort = 8011,
    [string]$StateDirectory = "",
    [string]$Seed = "underreach-alpha-0.1-autonomous",
    [switch]$FaultInjection,
    [switch]$DisableMedia,
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$Npm = "C:\Program Files\nodejs\npm.cmd"
$Viewer = Join-Path $RepoRoot "viewer"
$ViewerDist = Join-Path $Viewer "dist"
$Generated = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated"
$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
if ([string]::IsNullOrWhiteSpace($StateDirectory)) { $StateDirectory = Join-Path $Generated "runtime" }

if (-not (Test-Path $Python)) { throw "Project Python is missing: $Python" }
if ($Profile -ne "headless") {
    if (-not (Test-Path $Npm)) { throw "Node/npm is missing: $Npm" }
    Push-Location $Viewer
    try {
        & $Npm run build
        if ($LASTEXITCODE -ne 0) { throw "Viewer build failed." }
    } finally { Pop-Location }
}
if ($Profile -ne "headless") {
    foreach ($Required in @($UnrealEditorCmd, $Project)) {
        if (-not (Test-Path $Required)) { throw "Required Unreal input is missing: $Required" }
    }
}

$Arguments = @(
    "-m", "livingworld.underreach_alpha_runtime_entry",
    "--repo-root", $RepoRoot,
    "--profile", $Profile,
    "--state-directory", $StateDirectory,
    "--generated-directory", $Generated,
    "--viewer-port", "$ViewerPort",
    "--seed", $Seed
)
if ($Profile -ne "headless") {
    $Arguments += @("--viewer-static-directory", $ViewerDist, "--unreal-editor-cmd", $UnrealEditorCmd, "--unreal-project", $Project)
}
if ($Resume) { $Arguments += "--resume" }
if ($DurationSeconds -gt 0) { $Arguments += @("--duration-seconds", "$DurationSeconds") }
if ($FaultInjection) { $Arguments += "--fault-injection" }

$MediaEnabled = ($Profile -eq "alpha" -and -not $DisableMedia)
$MediaProcess = $null
$MediaDirectory = Join-Path $StateDirectory "media"
$MediaStopRequest = Join-Path $MediaDirectory "stop.request"
$MediaStatus = Join-Path $MediaDirectory "worker.status.json"
$MediaStdout = Join-Path $MediaDirectory "worker.stdout.log"
$MediaStderr = Join-Path $MediaDirectory "worker.stderr.log"

Write-Host ""
Write-Host "UNDERREACH ALPHA" -ForegroundColor Green
Write-Host "Profile: $Profile"
if ($Profile -ne "headless") { Write-Host "Viewer: http://127.0.0.1:$ViewerPort" }
Write-Host "State: $StateDirectory"
Write-Host "Checkpointing: ACTIVE"
Write-Host ("Production media: " + ($(if ($MediaEnabled) { "ACTIVE" } else { "DISABLED" })))
if ($MediaEnabled) { Write-Host "Media status: $MediaStatus" }
Write-Host "Press Ctrl+C for clean shutdown."
Write-Host ""

try {
    if ($MediaEnabled) {
        # Live Alpha uses strict installer-backed providers. These overrides are
        # inherited by the spawned sidecar only; restore the caller's process
        # environment immediately afterward so later tests/operator commands do
        # not accidentally inherit live-production policy.
        $MediaEnvironmentOverrides = @{
            "UNDERREACH_PROVIDER_DETERMINISTIC_IMAGE_FALLBACK_ENABLED" = "false"
            "UNDERREACH_PROVIDER_DETERMINISTIC_VOICE_FALLBACK_ENABLED" = "false"
            "UNDERREACH_PROVIDER_DETERMINISTIC_VIDEO_FALLBACK_ENABLED" = "false"
            "UNDERREACH_PROVIDER_COMFYUI_FREE_GPU_AFTER_IMAGE" = "true"
        }
        $PreviousMediaEnvironment = @{}
        foreach ($Name in $MediaEnvironmentOverrides.Keys) {
            $PreviousMediaEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, "Process")
            Set-Item -LiteralPath "Env:$Name" -Value $MediaEnvironmentOverrides[$Name]
        }

        New-Item -ItemType Directory -Path $MediaDirectory -Force | Out-Null
        Remove-Item -LiteralPath $MediaStopRequest -Force -ErrorAction SilentlyContinue
        $MediaArguments = @(
            "-m", "livingworld.underreach_live_production_media_worker_alpha",
            "--repo-root", $RepoRoot,
            "--state-directory", $StateDirectory
        )
        try {
            $MediaProcess = Start-Process `
                -FilePath $Python `
                -ArgumentList $MediaArguments `
                -WorkingDirectory $RepoRoot `
                -RedirectStandardOutput $MediaStdout `
                -RedirectStandardError $MediaStderr `
                -WindowStyle Hidden `
                -PassThru
        }
        finally {
            foreach ($Name in $MediaEnvironmentOverrides.Keys) {
                $PreviousValue = $PreviousMediaEnvironment[$Name]
                if ($null -eq $PreviousValue) {
                    Remove-Item -LiteralPath "Env:$Name" -Force -ErrorAction SilentlyContinue
                }
                else {
                    Set-Item -LiteralPath "Env:$Name" -Value $PreviousValue
                }
            }
        }
        Write-Host "Production media worker: STARTING (PID $($MediaProcess.Id))"
    }

    & $Python @Arguments
    $RuntimeExitCode = $LASTEXITCODE
}
finally {
    if ($null -ne $MediaProcess) {
        New-Item -ItemType Directory -Path $MediaDirectory -Force | Out-Null

        # The sidecar watches the canonical runtime lock and normally performs a
        # final checkpointed ingest on its own. Give it a short natural-exit
        # window before sending the explicit stop request.
        $NaturalDeadline = [DateTime]::UtcNow.AddSeconds(10)
        while (-not $MediaProcess.HasExited -and [DateTime]::UtcNow -lt $NaturalDeadline) {
            Start-Sleep -Milliseconds 250
            $MediaProcess.Refresh()
        }

        if (-not $MediaProcess.HasExited) {
            @{
                protocol = "underreach.live-media-stop-request.v1"
                requested_at_unix_ms = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
            } | ConvertTo-Json | Set-Content -LiteralPath $MediaStopRequest -Encoding UTF8

            $StopDeadline = [DateTime]::UtcNow.AddSeconds(10)
            while (-not $MediaProcess.HasExited -and [DateTime]::UtcNow -lt $StopDeadline) {
                Start-Sleep -Milliseconds 250
                $MediaProcess.Refresh()
            }
        }

        if (-not $MediaProcess.HasExited) {
            Write-Warning "Media worker did not exit within the shutdown window; stopping it. Its durable jobs will recover on -Resume."
            Stop-Process -Id $MediaProcess.Id -Force -ErrorAction SilentlyContinue
        }
    }
}

if ($RuntimeExitCode -ne 0) { throw "Underreach Alpha runtime failed with exit code $RuntimeExitCode." }
