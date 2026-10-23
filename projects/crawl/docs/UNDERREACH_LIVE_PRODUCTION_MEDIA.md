# Underreach Live Production Media

The live Alpha media path is a read-only sidecar. The deterministic Crawl runtime remains the only gameplay authority.

## Authority boundary

```text
Deterministic Crawl runtime / canonical SQLite Ledger
                    |
                    | checkpointed read-only export
                    v
          Live production media worker
                    |
        separate media SQLite + artifacts
                    |
     Qwen -> SDXL -> Kokoro -> FFmpeg
                    |
             Wan for score 90+
```

Generated prose, stills, audio, videos, Unreal output, and media-worker failures cannot mutate canonical Crawl state.

The worker processes only canonical history whose current tick matches the Alpha runtime's latest durable checkpoint. Its restart cursor and media jobs are stored outside the canonical database.

## Production providers

The live worker requires the exact installer-backed production stack before it begins media processing:

- narrative writer: `qwen3:8b`
- auxiliary verifier: `qwen3:4b`
- image: `sd_xl_base_1.0.safetensors`
- voice: local Kokoro using `kokoro-v1_0.pth`
- optional high-tier video enhancement: `wan2.2_ti2v_5B_fp16.safetensors`

No cloud or paid provider is required or automatically substituted.

## Start a new live Alpha run

First start the installed model services in one PowerShell window:

```powershell
D:\CrawlMedia\start-underreach-media-services.bat
```

In another PowerShell window:

```powershell
cd D:\CrawlTesting
git checkout main
git pull origin main

.\.venv\Scripts\python.exe .\scripts\check-underreach-production-providers.py --require-all

$RunId = Get-Date -Format "yyyyMMdd-HHmmss"
$State = "D:\CrawlTesting\unreal\CrawlPresentation\Generated\runs\$RunId"

.\scripts\start-underreach-alpha.ps1 -Profile alpha -StateDirectory $State
```

The Alpha launcher automatically starts the live production media sidecar. Use `-DisableMedia` only when deliberately debugging the Crawl without production media.

## Runtime files

For a run stored in `$State`:

- canonical runtime database: `$State\state\underreach.sqlite3`
- canonical runtime state: `$State\state\runtime.json`
- media database: `$State\media\underreach_media.sqlite3`
- media worker status: `$State\media\worker.status.json`
- latest completed media summary: `$State\media\latest-media.json`
- generated artifacts: `$State\media\artifacts`
- media stdout: `$State\media\worker.stdout.log`
- media stderr: `$State\media\worker.stderr.log`

Useful inspection commands:

```powershell
Get-Content "$State\media\worker.status.json" -Raw
Get-Content "$State\media\latest-media.json" -Raw
Get-ChildItem "$State\media\artifacts" -Recurse
```

## Media selection policy

The existing deterministic highlight scorer remains the gate. The LLM does not decide whether an event deserves media.

- below 50: archive only
- 50-69: Chronicle content
- 70-89: production narrative, SDXL scene, Kokoro narration, and FFmpeg vertical motion story
- 90-94: the same guaranteed motion story plus bounded Wan local animation
- 95+: cinematic-priority Wan enhancement within the existing GPU budget

Wan is optional enhancement only. The FFmpeg motion story remains the completed review-ready fallback even when Wan fails or is unavailable after a job has already been created.

## Human review

Generated artifacts remain pending review. The live worker does not automatically publish to YouTube, Twitch, a website, or any other external destination.

## Clean stop and resume

`Ctrl+C` on the foreground Alpha launcher stops the canonical runtime and requests a clean media-worker shutdown. If a long model render does not exit within the launcher's shutdown window, the process may be stopped; the media database recovers interrupted durable jobs on the next resume.

Resume the same Crawl with the same state directory:

```powershell
cd D:\CrawlTesting
.\scripts\start-underreach-alpha.ps1 -Profile alpha -StateDirectory $State -Resume
```

## Local validation

```powershell
cd D:\CrawlTesting
.\scripts\run-underreach-live-media-validation.ps1
```

This validation is local-only and does not use GitHub Actions.
