param(
    [Parameter(Mandatory = $true)]
    [string]$JobDirectory
)

$ErrorActionPreference = "Stop"

function Write-JsonAtomic {
    param(
        [Parameter(Mandatory = $true)]$Value,
        [Parameter(Mandatory = $true)][string]$Path
    )
    $Temp = "$Path.tmp"
    $Value | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $Temp -Encoding UTF8
    Move-Item -LiteralPath $Temp -Destination $Path -Force
}

$JobDirectory = [System.IO.Path]::GetFullPath($JobDirectory)
$SpecPath = Join-Path $JobDirectory "spec.json"
$StatusPath = Join-Path $JobDirectory "status.json"
$LogPath = Join-Path $JobDirectory "output.log"

if (-not (Test-Path -LiteralPath $SpecPath)) {
    throw "Job spec is missing: $SpecPath"
}

$Spec = Get-Content -LiteralPath $SpecPath -Raw | ConvertFrom-Json
$Started = [DateTimeOffset]::UtcNow
$Status = [ordered]@{
    protocol = "underreach.dev-runner-status.v1"
    job_name = [string]$Spec.job_name
    state = "running"
    worker_pid = $PID
    started_at = $Started.ToString("o")
    finished_at = $null
    exit_code = $null
    command = [string]$Spec.display_command
    repo_root = [string]$Spec.repo_root
    output_log = $LogPath
    error = $null
}
Write-JsonAtomic -Value $Status -Path $StatusPath

$ExitCode = 1
try {
    Set-Location -LiteralPath ([string]$Spec.repo_root)
    "[$([DateTimeOffset]::UtcNow.ToString('o'))] START $($Spec.display_command)" | Set-Content -LiteralPath $LogPath -Encoding UTF8

    $Executable = [string]$Spec.executable
    $Arguments = @()
    foreach ($Argument in $Spec.arguments) { $Arguments += [string]$Argument }

    & $Executable @Arguments *>> $LogPath
    if ($null -eq $LASTEXITCODE) {
        $ExitCode = 0
    } else {
        $ExitCode = [int]$LASTEXITCODE
    }
} catch {
    $ExitCode = 1
    $Status.error = $_.Exception.Message
    "[$([DateTimeOffset]::UtcNow.ToString('o'))] ERROR $($_.Exception.ToString())" | Add-Content -LiteralPath $LogPath -Encoding UTF8
} finally {
    $Finished = [DateTimeOffset]::UtcNow
    $Status.state = if ($ExitCode -eq 0) { "complete" } else { "failed" }
    $Status.finished_at = $Finished.ToString("o")
    $Status.exit_code = $ExitCode
    $Status.duration_seconds = [Math]::Round(($Finished - $Started).TotalSeconds, 3)
    "[$($Finished.ToString('o'))] END exit=$ExitCode" | Add-Content -LiteralPath $LogPath -Encoding UTF8
    Write-JsonAtomic -Value $Status -Path $StatusPath
}

exit $ExitCode
