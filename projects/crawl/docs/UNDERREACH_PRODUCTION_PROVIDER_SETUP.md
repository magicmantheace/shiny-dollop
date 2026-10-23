# UNDERREACH — LOCAL PRODUCTION PROVIDER SETUP

Status: production provider + installer integration

Provider stack version: `production-provider-stack.2`

The supported production path is intentionally simple:

1. Run `install-underreach-media-pipeline.bat` from the Crawl repository root.
2. Start Ollama and ComfyUI with the launchers written under `CrawlMedia`.
3. Run Crawl. The production provider stack uses the exact models installed by the BAT.
4. Run `python scripts/check-underreach-production-providers.py --require-all` to verify the machine.

No cloud or paid provider is configured by this stack.

---

## Exact model contract

The installer and runtime are locked to these identities:

| Role | Exact model/file |
| --- | --- |
| Narrative writer | `qwen3:8b` |
| Auxiliary verifier | `qwen3:4b` |
| Still image | `sd_xl_base_1.0.safetensors` |
| Video diffusion | `wan2.2_ti2v_5B_fp16.safetensors` |
| Wan text encoder | `umt5_xxl_fp8_e4m3fn_scaled.safetensors` |
| Wan VAE | `wan2.2_vae.safetensors` |
| Voice | `Kokoro-82M v1.0` / `kokoro-v1_0.pth` |

The production stack does not treat another tag from the same model family as equivalent. Ollama readiness requires the exact requested tag. ComfyUI readiness requires the exact checkpoint/model filenames to appear in its local model inventory.

The validation PowerShell script also cross-checks these names against `install-underreach-media-pipeline.bat`, so a future edit that changes only the installer or only the provider code fails validation.

---

## Installer

Run from a Windows terminal in the Crawl repository root:

```powershell
.\install-underreach-media-pipeline.bat
```

The BAT installs or configures:

- Git
- Python 3.12
- Node.js LTS and the locked dashboard dependencies
- Visual C++ runtime
- FFmpeg / ffprobe
- Ollama
- eSpeak NG
- Crawl backend/test dependencies
- a dedicated media Python environment
- ComfyUI with NVIDIA CUDA PyTorch
- Qwen3 8B and Qwen3 4B in Ollama
- SDXL Base 1.0
- Wan 2.2 TI2V 5B, its UMT5 encoder, and its VAE
- Kokoro-82M v1.0 and voice packs

By default media is installed beside the repository:

```text
<repo parent>\CrawlMedia
```

To use another location, set `UNDERREACH_MEDIA_HOME` before running the installer and before launching Crawl.

The installer verifies the downloaded SDXL, Wan and Kokoro core files with SHA-256 and is designed to be safe to rerun.

---

## Ollama

The installer pulls exactly:

```text
qwen3:8b
qwen3:4b
```

Production defaults are the same values and the provider health check requires an exact tag match.

Default endpoint:

```text
http://127.0.0.1:11434
```

The installer writes a launcher similar to:

```text
CrawlMedia\start-ollama-underreach.bat
```

---

## ComfyUI images

Production still images use:

```text
sd_xl_base_1.0.safetensors
```

The checkpoint is loaded with the normal core ComfyUI checkpoint graph. A custom reference-conditioning image workflow remains optional; the ordinary production path does not require one.

Default ComfyUI endpoint:

```text
http://127.0.0.1:8188
```

---

## ComfyUI video

The installer downloads the official Wan assets:

```text
wan2.2_ti2v_5B_fp16.safetensors
umt5_xxl_fp8_e4m3fn_scaled.safetensors
wan2.2_vae.safetensors
```

Crawl ships its own API-format execution graph at:

```text
config/comfyui/wan2.2-ti2v-5b-api.json
```

That graph references those exact three filenames and contains the placeholders Crawl patches at runtime for prompt, source image, seed, dimensions, frame count, FPS and output prefix.

This avoids the previous mismatch where the installer downloaded a ComfyUI UI workflow while the headless provider required API-format prompt JSON.

---

## Kokoro voice

Production narration no longer requires a separate Kokoro FastAPI server.

The installer creates a dedicated media Python environment and downloads:

```text
CrawlMedia\models\Kokoro-82M\kokoro-v1_0.pth
CrawlMedia\models\Kokoro-82M\config.json
CrawlMedia\models\Kokoro-82M\voices\*.pt
```

The production provider launches:

```text
scripts/run-underreach-kokoro-tts.py
```

with the Python executable from:

```text
CrawlMedia\python\.venv\Scripts\python.exe
```

The runner loads the local `kokoro-v1_0.pth`, local config and selected local voice pack directly and forces Hugging Face/Transformers offline mode during synthesis. This prevents a narration request from silently downloading or switching to another model.

The legacy loopback HTTP Kokoro adapter remains available only as an explicit development configuration.

---

## Starting services

After installation, start the local model services using the launcher written by the BAT:

```powershell
..\CrawlMedia\start-underreach-media-services.bat
```

That starts Ollama and ComfyUI. Kokoro production narration is invoked on demand and does not need a resident service.

---

## Optional configuration

Defaults should work when the installer used its default media location. Optional overrides are documented in:

```text
config/underreach-providers.env.example
```

The exact writer, verifier and SDXL model identities are pinned by the production settings validator. Operational settings such as timeouts, output dimensions, voice, service URLs and deterministic fallbacks remain configurable.

---

## Validation without GitHub Actions

Run the code/regression validation locally:

```powershell
.\scripts\run-underreach-production-provider-validation.ps1
```

It performs:

- Python compilation of the production provider files
- focused mocked provider tests
- installer/runtime model-name lockstep checks
- bundled Wan workflow asset checks
- local/cloud/paid-provider safety checks
- the full Crawl pytest suite

It does not use GitHub Actions.

After the installer has been run on the target PC, verify the actual local services and files:

```powershell
.\.venv\Scripts\python.exe scripts\check-underreach-production-providers.py --require-all
```

The machine check reports readiness separately for the exact writer, verifier, SDXL checkpoint, Wan model/encoder/VAE, Kokoro model files, FFmpeg and ffprobe.

---

## Authority boundary

All of these providers remain presentation-only. The deterministic Crawl simulation and canonical event ledger remain authoritative. Ollama, SDXL, Wan, Kokoro, cameras, editing and narration may present accepted events but cannot alter canonical gameplay truth.
