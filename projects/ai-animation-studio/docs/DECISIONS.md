# Architecture decisions

## ADR-001: Render poses, not video pixels

**Accepted.** Godot renders stylized 3D; AI emits semantic action/scene commands. This avoids full video diffusion costs and allows deterministic playback.

## ADR-002: Offline-first, persistent assets

**Accepted.** SQLite and local files are durable catalog; generated candidates require validation before promotion. No cloud dependence.

## ADR-003: Fixed humanoid rig family

**Accepted for MVP.** A canonical rig permits reusing animations across modular characters. Other creature types use separate rig_id families.

## ADR-004: Separate offline generation from frame loop

**Accepted.** Asset generation cannot stall gameplay/animation; use asynchronous jobs and fallbacks.

## ADR-005: Python stdlib + Godot 4

**Accepted for initial foundation.** Python provides validation/catalog CLI without dependency installation; Godot renders preview. Future local inference adapters can be independent processes.

## ADR-006: Reviewable branch, independent project

**Accepted.** Do not modify other project implementations; root README registration only.

## Open decisions

- Model runtime (llama.cpp/Ollama or another) after resource profiling.
- Voice/TTS engine after licensing/latency/VRAM testing.
- Authoring style pack licensing and first canonical humanoid rig source.
- IPC transport once deterministic runtime succeeds.
