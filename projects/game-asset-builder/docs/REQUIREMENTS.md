# Requirements — Game Asset Builder

## Owner PC (GPU stages)

- Windows 11, NVIDIA GPU with ≥12 GB VRAM (developed against RTX 3060 12 GB).
- ~40 GB free disk for model weights + caches (weights live outside git).
- A standalone Python 3.12 (via `uv`) for the model environment — the system
  Python 3.14 is too new for current PyTorch wheels.
- PyTorch with CUDA, installed per-model-stage environment or one shared
  stage environment; each stage still runs as its own process.
- One-time internet access to download open model weights (Hugging Face).
  No network is used during generation.

## Build VM / any CPU machine (orchestration, rig, scoring)

- Python 3.11+ (stdlib only for the orchestrator and CLI).
- Blender 4.x headless for rig, animation, normalization, and scoring
  renders (developed against Blender 4.2.3 LTS).
- No GPU required — and no GPU result may be claimed from this machine.

## Inputs

- A concept image per asset (PNG/JPG; RGBA cutout preferred). For the Pip
  benchmark, the fixed input in `benchmarks/pip/`.
