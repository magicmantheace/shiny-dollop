# AGENTS.md — game-asset-builder

Rules for anyone working in this project.

- Work only inside `projects/game-asset-builder/`. Do not modify other projects.
- **Fully local, no APIs.** Asset generation must run entirely on the owner's
  hardware. No cloud generation services, no API keys, no per-asset costs.
  The only network use permitted is the one-time download of open model
  weights (e.g. from Hugging Face) before a model is used.
- **Staged models, unloaded between uses.** Mesh generation and texturing are
  separate models run as separate stages. Each stage runs in its own process:
  load → run → exit. Never hold two heavy models resident at once; the target
  GPU has 12 GB VRAM total.
- **The benchmark is Pip.** Every candidate model is scored against the
  owner's Meshy-generated Pip (the reference) on the fixed input cutout,
  using the protocol in `docs/DESIGN.md`. Report scores honestly, including
  failures; a model that melts the character is a failed candidate, not a
  tuning problem to hide.
- Never claim Windows/GPU verification from VM runs. The build VM has no GPU;
  model stages are verified on the owner's PC (RTX 3060 12 GB) or not at all.
- Commit messages are project-prefixed (`game-asset-builder: ...`).
- After substantive changes, update `README.md`, `docs/MUSE_HANDOFF.md`,
  and `docs/TEST_PLAN.md` with the verified / unverified split.
- Model weights, caches, venvs, and generated outputs never enter git
  (see `.gitignore`). Catalogued, finished assets may be committed when the
  owner approves them.
