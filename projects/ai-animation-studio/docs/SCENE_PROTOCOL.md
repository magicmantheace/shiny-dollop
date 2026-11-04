# Scene command protocol v1

**Wire version:** `1.0.0`. See `schemas/scene.schema.json`, `studio/schema.py` and `examples/scene_demo.json`.

## Scene envelope

- `scene_id`, `environment_id`: stable snake-case identifiers.
- `actors`: each has `id`, `recipe_id`, `color` (color is temporary preview material).
- `events`: nondecreasing `at_ms` timeline, max one hour in current validator.

## Commands

| op | Required | Effect |
| --- | --- | --- |
| spawn | actor_id, position [x,y,z] | Creates actor once |
| move | actor_id, target [x,y,z], duration_ms | Time-bounded translation; future pathfinding |
| speak | actor_id, line | Logs line; optional `duration_ms` (ADR-009 hold) and `interrupt` (F3.3, below); future TTS/lip sync |
| emote | actor_id, emotion, intensity | Currently logs; future facial rig |
| camera | shot | Currently logs; future shot controller |

## Semantic rules

- `at_ms` ordered; actor must exist and be spawned before any non-spawn command.
- Commands never execute arbitrary script or shell actions.
- Coordinates bounded to ±1000; move duration 100–60000 ms; line maximum 500 characters.
- Unsupported schema versions or unknown opcodes fail closed.
- Runtime must also resolve referenced recipe/environment/rig/prop IDs to **approved** assets before production execution. Preview deliberately uses procedural stand-ins, not approved files.
- Event ordering on tied timestamps follows the dispatch priority rule (camera, then spawn, then JSON array order) — see the F3.3 dialogue runtime section below.
- Future: shot targets, animation IDs, state preconditions, cancellation, playback clocks, causality/acks, voice cues and bounded live IPC.

## Director-to-engine IPC (F2.4, implemented 2026-11-03)

The scene above reaches the engine inside a versioned envelope defined by `studio/ipc.py`. The transport is unchanged — offline, file-based: the director (CLI `demo`) writes the runtime scene document and the enriched asset manifest into `godot/data/`, and the preview picks them up at startup. What F2.4 adds is the formal contract around that exchange; live/streaming IPC remains future work (see `docs/ARCHITECTURE.md`).

- **Scene envelope:** `{"ipc_version": "1.0.0", "kind": "scene", "issued_at": "<ISO-8601 UTC>", "payload": <scene>}`. `issued_at` is informational; the payload is a scene document exactly as defined above and is fully validated (`studio.schema.validate_scene`) on unwrap.
- **Versioning rule:** `ipc_version` versions the *envelope* and is independent of the scene's `schema_version` — envelope `1.0.0` carries scene schema `1.0.0`. An unknown `ipc_version` or `kind` fails closed on both sides: `studio.ipc.unwrap_scene` raises `IpcError` with a named reason, and the preview refuses playback and records the rejection (below). The preview mirrors the version constant in `godot/main.gd` (parity guarded by `tests/test_ipc.py`).
- **Result record (engine -> director):** when the preview loads an *enveloped* scene it writes `godot/data/scene_result.json`: `{"ipc_version": "1.0.0", "kind": "result", "scene_id": <id>, "accepted": true|false, "detail": "<reason>"}` — accepted once the scene has passed load validation and been scheduled, or refused with the rejection reason (unsupported envelope version/kind, unsupported scene schema version, malformed actors/events). The director reads it back with `studio.ipc.read_result`, which validates the same shape. The preview speaks its own `ipc_version` in the result even when rejecting a foreign-version envelope.
- **Backward compatibility:** a bare scene document (no `ipc_version`/`kind` keys) still loads exactly as before and is *not* acknowledged — no result file is written for bare loads. ADR-008 approved-asset enforcement on the manifest is untouched by the envelope.

## AI adapter contract (future)

LLM may propose intent objects, never direct engine operations. A deterministic translator expands intent to commands and a strict validator rejects anything outside the protocol. Model/tool output is untrusted input.

## ADOPTED 2026-11-03 — speak/camera timing semantics (owner sign-off, provisional; ADR-009)

The v1 rules above define *when* events fire (`at_ms`) but not how long a `speak` occupies its actor, which F1 dialogue beats need. The owner adopted this section on 2026-11-03 (provisional acceptance). Adoption is forward-compatible — event objects already tolerate extra fields, so authors may write `duration_ms` on `speak` today and current validators accept it. **Implemented 2026-11-03:** the derivation lives in `studio/timing.py`; a scene may carry a top-level `timing` object (validated by `studio/schema.py` and `schemas/scene.schema.json`); the Godot preview schedules with the same variables via exported settings in `godot/main.gd`. An explicit `duration_ms` on `speak` is wire-bounded to 100–60000 ms, the same bounds as `move`. Owner condition: the derivation rate and the clamp bounds below are the defaults of changeable configuration variables, not hardcoded constants, so the rate can be increased later without revisiting this section.

- **Speak hold.** A `speak` event occupies its actor for a hold window `[at_ms, at_ms + hold)`. `hold` is the event's explicit `duration_ms` when present; otherwise it is derived deterministically from the line: `ceil(len(line) * 1000 / rate)` ms, where `rate` is a configuration variable whose default is 15 (15 characters/second ≈ 150 wpm natural delivery), clamped to a configurable minimum/maximum whose defaults are 800–15000 ms. Explicit-first is the choice because directed scenes need exact beats, while the derived default keeps existing scenes — including the demo, whose lines carry no duration — playable with sane pacing and zero reauthoring. The derivation is a pure function of the line, so previews are deterministic and the future TTS stage can reconcile the same number against real audio length.
- **Blocking scope: per actor, never global.** A speak hold gates only later events for the *same* actor: if such an event's `at_ms` falls inside the window, the runtime delays it until the window ends (safety net). Other actors and `camera` events are never delayed — conversation partners can react mid-line. Follow-up for a future wire revision (not this proposal): the Python validator should *reject* a scene whose same-actor events overlap a speak hold, so authoring errors surface at plan time instead of being silently delayed.
- **Camera cuts are instantaneous.** A `camera` event takes effect exactly at its `at_ms`, has no duration, is never blocked by a speak hold and blocks nothing. On tied timestamps the existing stable array-order rule decides application order. Fades/dolly moves are out of scope for v1 and would arrive as new ops, not as a duration on `camera`.
- **Move and emote unchanged.** `move` already carries a validated `duration_ms` (100–60000 ms); it remains fire-at-`at_ms` — its motion runs concurrently and a later same-actor event applies on schedule (interrupting/retargeting the motion), exactly as the preview behaves today. `emote` is an instantaneous state change at its `at_ms` with no hold. Speak is the only op this proposal gives a hold.
- **Demo check.** Under this model the demo scene stays consistent: the traveler's 44-character line at 3800 ms derives a 2934 ms hold ending at 6734 ms; the innkeeper's reply at 6600 ms is a different actor, so per-actor blocking does not delay it, and no same-actor event falls inside any hold. (Verified in the preview's headless run, 2026-11-03: no `Delayed` lines; holds logged 2934 ms and 2000 ms.)

## Dialogue runtime: interrupts, dispatch priority, queue safety (F3.3, implemented 2026-11-03)

Extends ADR-009 without changing it: non-interrupt behavior is exactly as ADR-009 specifies. The schedule computation has a single source of truth — `compute_schedule` in `studio/timing.py` — which the Godot preview mirrors; the whole schedule (including every truncation) is precomputed at load, with no runtime timers deciding order.

- **Speak interrupt.** A `speak` event may carry `"interrupt": true` (boolean; absent means false; enforced by `studio/schema.py` and `schemas/scene.schema.json`). An interrupting speak is never delayed by a hold — it starts exactly at its `at_ms`. When the actor's current speak window contains that start (`window_start <= at_ms < window_end`), the current window is **truncated** at `at_ms`: the interrupted line keeps the floor up to the cut and no further, and the interrupting speak's own hold is computed normally (explicit `duration_ms` first, else derived, per ADR-009). An interrupt at or after the window's end is a no-op, an interrupt never touches another actor's window, and interrupts chain — each interrupting speak truncates the window left by the previous one. Later same-actor events are gated by the window *as truncated*. The preview logs a truncation distinctly — `Speak interrupted for <actor> at <ms>` plus the revised window (`Truncated speak hold for <actor>: window <start>..<old end> -> <start>..<at_ms> ms`) — and an interrupted speak occupies (and animates) only its truncated window.
- **Dispatch priority on tied effective times.** When several events share an effective start time, dispatch order is: `camera` first, then `spawn`, then all remaining ops in scene (JSON array) order. This supersedes the tie-ordering sentences in the semantic rules and ADR-009 above: a camera cut authored at the same instant as a line is applied before the line, and a spawn always precedes same-instant commands for any actor. Camera events remain instantaneous, unblocked and blocking nothing (ADR-009).
- **Queue safety.** Dispatch is per-event best-effort: an event referencing an actor with no spawned node — impossible in a scene that passed load validation — is skipped with a named error (`Dispatch skipped: ...`) and the queue continues; there is no crash and no stall. This is a thin runtime guard, not a second validator; validation remains the fail-closed gate.
