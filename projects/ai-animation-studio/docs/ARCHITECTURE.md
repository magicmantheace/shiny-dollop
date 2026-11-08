# Technical architecture

## Pipeline

```text
User prompt / local LLM (future)
       |
       v
Scene writer -> staging planner -> validated scene contract v1
                                |
                   schema + semantic validation
                                |
          +---------------------+---------------------+
          |                                           |
  SQLite asset registry                         Missing-assets queue
  approved IDs, versions                        OFFLINE / background
          |                                           |
          v                                           v
  scheduler / action resolver                  authoring, retargeting,
  (future local backend)                       preview, license checks
          |                                           |
          v                                           v
  Godot main thread                           validation + promotion
  clip blend / IK / speech / camera                  |
          |___________________________________________|
                              new reusable assets
```

## Boundaries and components

- `studio/schema.py`: deterministic bounds and security rules; authoritative MVP validator. JSON Schema under `schemas/` documents wire shape and should be enforced by a standards-compliant validator in production.
- `studio/library.py`: local persistent registry, no network, candidate/approved/retired lifecycle.
- `studio/cli.py`: offline tools. Never treats a model response as code.
- `godot/`: engine project and procedural protocol preview; reads one JSON file at startup.
- `database/schema.sql`: SQLite local catalogue; schema migrations needed before changing layout.
- `examples/`: synthetic input fixtures, no media assets.

## Runtime thread ownership

1. Render loop and animation playback stay inside Godot; no synchronous model calls.
2. Director service (future) runs in a separate worker and publishes bounded scene events.
3. Worker sends only allowlisted IDs and action enums across IPC. Do not allow direct filesystem paths or arbitrary GDScript from the model.
4. Backend reads/writes SQLite via one transaction owner or short-lived connections; atomic updates and crash-safe replay.
5. Asset builder runs while the live scene plays, but GPU-heavy jobs require user-approved scheduling and can pause or queue.

## Planned IPC

Local loopback with versioned JSON lines or bounded websocket queue. Schema version negotiation mandatory. Message IDs, acknowledgements, max-queue length, backpressure, timestamps and replay isolation. No external listener, no unauthenticated network exposure.

## Failure policy

- LLM stalls: use scheduled beats or idle fallback, never freeze the renderer.
- Missing asset: choose explicit approved fallback, record request for later; no silent external downloads.
- Invalid command: reject and log without partial execution.
- GPU memory pressure: disable expensive AI inference, lower scene quality or reduce cast.
- Broken asset: quarantine; do not promote to live catalog.
- Bad frame timing: capture metrics and downgrade effects, not character controls.

## Growth path

Early stages use authored clips and blends; generated motion is an interchangeable plugin later. No requirement for continuously generating keyframes. Phase 1 uses simple color/shape stand-ins. Actual rigs, material style, voice pipeline, planner and motion generation are later work.
