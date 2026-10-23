param(
    [string]$UnrealEditorCmd = "D:\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Project = Join-Path $RepoRoot "unreal\CrawlPresentation\CrawlPresentation.uproject"
$Manifest = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\stage_manifest.json"
$RecoveryScript = Join-Path $RepoRoot "unreal\CrawlPresentation\Content\Python\recover_build_metadata.py"
$Result = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\unreal_build_result.json"
$Diagnostic = Join-Path $RepoRoot "unreal\CrawlPresentation\Generated\unreal_recovery_result.json"

if (-not (Test-Path $UnrealEditorCmd)) {
    throw "UnrealEditor-Cmd.exe not found at $UnrealEditorCmd"
}
if (-not (Test-Path $Manifest)) {
    throw "Stage manifest not found at $Manifest. Run the vertical-slice exporter first."
}

$env:CRAWL_STAGE_MANIFEST = (Resolve-Path $Manifest).Path
Remove-Item $Result -Force -ErrorAction SilentlyContinue
Remove-Item $Diagnostic -Force -ErrorAction SilentlyContinue

Write-Host "== Recover Unreal build metadata =="
& $UnrealEditorCmd $Project "-ExecutePythonScript=$RecoveryScript" -unattended -nop4 -nosplash -log

if (Test-Path $Diagnostic) {
    Write-Host ""
    Write-Host "Recovery diagnostic:"
    Get-Content $Diagnostic
}

if (-not (Test-Path $Result)) {
    throw "Recovery could not create unreal_build_result.json. The diagnostic above tells us whether the generated level/sequence actually exist."
}

Write-Host ""
Write-Host "RECOVERY PASS"
Write-Host "Metadata: $Result"
Get-Content $Result
