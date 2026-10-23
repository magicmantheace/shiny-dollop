param([string]$StateDirectory = "")

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Generated = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated"
if ([string]::IsNullOrWhiteSpace($StateDirectory)) { $StateDirectory = Join-Path $Generated "runtime" }
$LockPath = Join-Path $StateDirectory "runtime.lock"
if (-not (Test-Path $LockPath)) { throw "No active Underreach runtime lock exists at $LockPath" }
$Lock = Get-Content $LockPath -Raw | ConvertFrom-Json
$Process = Get-CimInstance Win32_Process -Filter "ProcessId=$($Lock.pid)" -ErrorAction SilentlyContinue
if ($null -eq $Process -or $Process.CommandLine -notlike "*livingworld.underreach_alpha_runtime*") {
    throw "The lock does not identify a live Underreach runtime; no process was signaled."
}
$Request = @{ protocol = "underreach.alpha-stop-request.v1"; runtime_id = $Lock.runtime_id; requested_at_unix_ms = [DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds() }
$Request | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $StateDirectory "stop.request") -Encoding UTF8
Write-Host "Clean shutdown requested for $($Lock.runtime_id)."
