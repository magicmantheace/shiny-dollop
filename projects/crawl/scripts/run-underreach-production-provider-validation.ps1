$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) { $Python = "python" }

Write-Host "[providers] Compile production provider adapters"
$ProviderSources = @(
    "src\livingworld\underreach_ollama_providers.py",
    "src\livingworld\underreach_comfyui_providers.py",
    "src\livingworld\underreach_comfyui_production_image.py",
    "src\livingworld\underreach_kokoro_provider.py",
    "src\livingworld\underreach_production_provider_stack.py",
    "scripts\run-underreach-kokoro-tts.py",
    "scripts\check-underreach-production-providers.py"
)
& $Python -m py_compile @ProviderSources
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[providers] Focused mock contract tests - no external model services required"
& $Python -m pytest -q tests/test_underreach_production_provider_integrations.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[providers] Installer/model contract audit"
$Installer = Get-Content -Raw (Join-Path $RepoRoot "install-underreach-media-pipeline.bat")
$StackSource = Get-Content -Raw (Join-Path $RepoRoot "src\livingworld\underreach_production_provider_stack.py")
$KokoroSource = Get-Content -Raw (Join-Path $RepoRoot "src\livingworld\underreach_kokoro_provider.py")
$OllamaSource = Get-Content -Raw (Join-Path $RepoRoot "src\livingworld\underreach_ollama_providers.py")
$ComfySource = Get-Content -Raw (Join-Path $RepoRoot "src\livingworld\underreach_comfyui_providers.py")
$WanWorkflow = Get-Content -Raw (Join-Path $RepoRoot "config\comfyui\wan2.2-ti2v-5b-api.json")
$AllProviderSource = $StackSource + "`n" + $KokoroSource + "`n" + $OllamaSource + "`n" + $ComfySource

if ($AllProviderSource -match "api\.openai\.com" -or $AllProviderSource -match "api\.anthropic\.com") {
    throw "production provider stack introduced a cloud API endpoint"
}
if ($AllProviderSource -match "ProviderDescriptor\([\s\S]{0,500}?paid=True") {
    throw "production provider stack introduced a paid executable provider"
}

$ExactPairs = @(
    @('set "WRITER_MODEL=qwen3:8b"', 'INSTALLER_WRITER_MODEL = "qwen3:8b"'),
    @('set "VERIFIER_MODEL=qwen3:4b"', 'INSTALLER_VERIFIER_MODEL = "qwen3:4b"'),
    @('sd_xl_base_1.0.safetensors', 'INSTALLER_SDXL_CHECKPOINT = "sd_xl_base_1.0.safetensors"'),
    @('wan2.2_ti2v_5B_fp16.safetensors', 'INSTALLER_WAN_MODEL = "wan2.2_ti2v_5B_fp16.safetensors"'),
    @('umt5_xxl_fp8_e4m3fn_scaled.safetensors', 'INSTALLER_WAN_TEXT_ENCODER = "umt5_xxl_fp8_e4m3fn_scaled.safetensors"'),
    @('wan2.2_vae.safetensors', 'INSTALLER_WAN_VAE = "wan2.2_vae.safetensors"'),
    @('kokoro-v1_0.pth', 'INSTALLER_KOKORO_MODEL = "kokoro-v1_0.pth"')
)
foreach ($Pair in $ExactPairs) {
    if ($Installer -notmatch [regex]::Escape($Pair[0])) {
        throw "installer lost required model declaration: $($Pair[0])"
    }
    if ($StackSource -notmatch [regex]::Escape($Pair[1])) {
        throw "production stack is not pinned to installer declaration: $($Pair[1])"
    }
}

foreach ($WanAsset in @(
    'wan2.2_ti2v_5B_fp16.safetensors',
    'umt5_xxl_fp8_e4m3fn_scaled.safetensors',
    'wan2.2_vae.safetensors'
)) {
    if ($WanWorkflow -notmatch [regex]::Escape($WanAsset)) {
        throw "bundled Wan API workflow lost exact installer asset: $WanAsset"
    }
}

if ($StackSource -notmatch "_exact_ollama_model_ready" -or $StackSource -notmatch "exact_model_ready") {
    throw "production provider stack lost exact Ollama model-tag gating"
}
if ($StackSource -notmatch "exact_installer_checkpoint_ready" -or $StackSource -notmatch "exact_installer_models_ready") {
    throw "production provider stack lost exact ComfyUI model gating"
}
if ($KokoroSource -notmatch 'backend == "subprocess"' -or $KokoroSource -notmatch "KOKORO_INSTALLER_MODEL_FILE") {
    throw "Kokoro provider lost direct installer-model backend"
}
if ($OllamaSource -notmatch "supporting_allowed_fact_ids=\(fact\.fact_id,\)" -or $OllamaSource -notmatch "target_or_value=fact\.value") {
    throw "Ollama writer no longer binds factual claims directly to canonical AllowedFact values"
}
if ($ComfySource -notmatch "image_to_video=True" -or $ComfySource -notmatch "estimated_vram_mb=8192") {
    throw "ComfyUI Wan provider lost the 12GB-class local I2V profile"
}

Write-Host "[providers] Full Crawl regression suite"
& $Python -m pytest -q
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "[providers] PASS"
Write-Host "Code validation used mocked provider endpoints only."
Write-Host "After running install-underreach-media-pipeline.bat, real-machine health is:"
Write-Host "  python scripts\check-underreach-production-providers.py --require-all"
