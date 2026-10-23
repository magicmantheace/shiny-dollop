param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) { throw "Project Python is missing: $Python" }

Write-Host "UNDERREACH LIVE MEDIA VALIDATION" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"
Write-Host ""

& $Python -m py_compile `
    "src\livingworld\underreach_live_production_media_worker.py" `
    "src\livingworld\underreach_live_production_media_worker_alpha.py" `
    "src\livingworld\underreach_alpha_highlight_scoring.py" `
    "src\livingworld\underreach_alpha_ollama_runtime.py" `
    "src\livingworld\underreach_alpha_presentation_polish.py" `
    "src\livingworld\underreach_alpha_cinematic_reference_image.py" `
    "src\livingworld\underreach_ollama_providers.py" `
    "src\livingworld\underreach_comfyui_production_image.py" `
    "src\livingworld\underreach_media_event_export.py" `
    "src\livingworld\underreach_production_provider_stack.py" `
    "src\livingworld\underreach_atomic_json_io.py" `
    "src\livingworld\underreach_alpha_runtime_entry.py"
if ($LASTEXITCODE -ne 0) { throw "Python compile validation failed." }

# Provider-stack tests assert the library defaults, not whichever strict live
# policy a previous Alpha launcher may have placed in this PowerShell process.
# Override only for the pytest child process and restore the caller state after.
$TestEnvironmentOverrides = @{
    "UNDERREACH_PROVIDER_DETERMINISTIC_IMAGE_FALLBACK_ENABLED" = "true"
    "UNDERREACH_PROVIDER_DETERMINISTIC_VOICE_FALLBACK_ENABLED" = "true"
    "UNDERREACH_PROVIDER_DETERMINISTIC_VIDEO_FALLBACK_ENABLED" = "true"
}
$PreviousTestEnvironment = @{}
$TestExitCode = 1
try {
    foreach ($Name in $TestEnvironmentOverrides.Keys) {
        $PreviousTestEnvironment[$Name] = [Environment]::GetEnvironmentVariable($Name, "Process")
        Set-Item -LiteralPath "Env:$Name" -Value $TestEnvironmentOverrides[$Name]
    }

    & $Python -m pytest -q `
        "tests\test_underreach_live_production_media_worker.py" `
        "tests\test_underreach_alpha_highlight_scoring.py" `
        "tests\test_underreach_alpha_ollama_runtime.py" `
        "tests\test_underreach_alpha_viewer_media.py" `
        "tests\test_underreach_alpha_character_continuity.py" `
        "tests\test_underreach_alpha_advisory_qwen_verifier.py" `
        "tests\test_underreach_alpha_cinematic_image_quality.py" `
        "tests\test_underreach_production_provider_integrations.py" `
        "tests\test_underreach_installer_model_contract.py" `
        "tests\test_underreach_atomic_json_io.py"
    $TestExitCode = $LASTEXITCODE
}
finally {
    foreach ($Name in $TestEnvironmentOverrides.Keys) {
        $PreviousValue = $PreviousTestEnvironment[$Name]
        if ($null -eq $PreviousValue) {
            Remove-Item -LiteralPath "Env:$Name" -Force -ErrorAction SilentlyContinue
        }
        else {
            Set-Item -LiteralPath "Env:$Name" -Value $PreviousValue
        }
    }
}
if ($TestExitCode -ne 0) { throw "Focused live-media/provider/runtime tests failed." }

$StartScript = Get-Content "scripts\start-underreach-alpha.ps1" -Raw
foreach ($Required in @(
    "livingworld.underreach_live_production_media_worker_alpha",
    "livingworld.underreach_alpha_runtime_entry",
    "DisableMedia",
    "worker.status.json",
    "stop.request"
)) {
    if ($StartScript -notlike "*$Required*") { throw "Alpha launcher is missing required runtime/media contract: $Required" }
}

foreach ($WorkerPath in @(
    "src\livingworld\underreach_live_production_media_worker.py",
    "src\livingworld\underreach_live_production_media_worker_alpha.py",
    "src\livingworld\underreach_alpha_highlight_scoring.py",
    "src\livingworld\underreach_alpha_ollama_runtime.py",
    "src\livingworld\underreach_alpha_presentation_polish.py",
    "src\livingworld\underreach_alpha_cinematic_reference_image.py",
    "src\livingworld\underreach_ollama_providers.py",
    "src\livingworld\underreach_comfyui_production_image.py"
)) {
    $Worker = Get-Content $WorkerPath -Raw
    foreach ($Forbidden in @(
        "api.openai.com",
        "api.anthropic.com"
    )) {
        if ($Worker -like "*$Forbidden*") { throw "Live media code contains forbidden cloud endpoint in ${WorkerPath}: $Forbidden" }
    }
}

Write-Host ""
Write-Host "PASS: live production media, Alpha score calibration, bounded Ollama runtime, advisory-only Qwen verification, cinematic SDXL quality, stable character continuity, reference-conditioned setup/action/outcome scenes, compact viewer captions, and resilient runtime wiring are locally valid." -ForegroundColor Green
Write-Host "No GitHub Actions are used by this validation."
