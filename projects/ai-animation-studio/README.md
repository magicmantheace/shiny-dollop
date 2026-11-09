# AI Animation Studio

**Status:** foundation/scaffold; **not** a completed real-time AI show generator.

A self-contained, local-first system for AI-directed, stylized 3D scenes. Godot renders characters and environments. A planner issues **versioned intent commands**, a persistent asset library caches reusable content, and optional future models provide writing, motion and speech. New assets are built and vetted outside the frame loop.

**Active project:** `projects/ai-animation-studio/`. Do not modify other projects or claim an AthenZ/Synveil dependency.

## Hardware target and scope

Windows 11; Intel i5-10400F, 32 GB RAM, RTX 3060 12 GB VRAM. Prioritize a two-character, one-room **30 FPS target**, with a deterministic fallback whenever the AI or asset builder stalls. 30/60 FPS is a design target, not a measured result.

## First runnable vertical slice

Requires Python 3.11+; Godot 4.x is optional for graphical preview. No Python dependencies or remote services are needed.

```powershell
cd projects/ai-animation-studio
python -m studio validate
python -m studio init-db
python -m studio seed
python -m studio list-assets
python -m studio demo
python -m unittest discover -s tests -v
```

To view the **procedural capsule-character** preview: open `godot/project.godot` in Godot 4, then run the main scene. `demo` writes an optional `godot/data/scene_runtime.json`; otherwise Godot loads its committed built-in demo. It is a control-protocol preview, not production-quality animation. Spoken lines print to the Godot output; TTS, lip sync and actual rigged assets are planned.

## Documentation map

- [Product requirements](docs/PRODUCT_SPEC.md), [system architecture](docs/ARCHITECTURE.md), [visual style](docs/ART_DIRECTION.md)
- [Scene protocol](docs/SCENE_PROTOCOL.md), [rig contract](docs/RIG_CONTRACT.md), [asset pipeline](docs/ASSET_PIPELINE.md)
- [schemas](schemas/), [SQLite schema](database/schema.sql), [examples](examples/)
- [hardware budgets](docs/PERFORMANCE_BUDGET.md), [roadmap](docs/ROADMAP.md), [test plan](docs/TEST_PLAN.md)
- [status](docs/IMPLEMENTATION_STATUS.md) and [Muse handoff](docs/MUSE_HANDOFF.md)

## Design rules

1. The renderer never waits for model inference or asset generation.
2. Treat LLM output as **untrusted intent**, validated against a versioned schema and asset allowlist.
3. Reuse compatible humanoid skeletons and retarget clips; separate creature rigs.
4. Persist character recipes, motion/prop metadata and validated assets with provenance/licensing.
5. Promote generated assets only after mechanical and visual checks; preserve asset versions.
6. No proprietary character/voice data or private recordings in Git.
7. Explicitly report actual test results, limitations and hardware measurements.
