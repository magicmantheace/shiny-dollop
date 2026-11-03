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
| speak | actor_id, line | Currently logs line; future TTS/lip sync |
| emote | actor_id, emotion, intensity | Currently logs; future facial rig |
| camera | shot | Currently logs; future shot controller |

## Semantic rules

- `at_ms` ordered; actor must exist and be spawned before any non-spawn command.
- Commands never execute arbitrary script or shell actions.
- Coordinates bounded to ±1000; move duration 100–60000 ms; line maximum 500 characters.
- Unsupported schema versions or unknown opcodes fail closed.
- Runtime must also resolve referenced recipe/environment/rig/prop IDs to **approved** assets before production execution. Preview deliberately uses procedural stand-ins, not approved files.
- Event ordering on tied timestamps is stable in JSON array order.
- Future: shot targets, animation IDs, state preconditions, cancellation, playback clocks, causality/acks, voice cues and bounded live IPC.

## AI adapter contract (future)

LLM may propose intent objects, never direct engine operations. A deterministic translator expands intent to commands and a strict validator rejects anything outside the protocol. Model/tool output is untrusted input.

## PROPOSED 2026-11-03 — speak/camera timing semantics (pending owner sign-off, not yet canonical)

The v1 rules above define *when* events fire (`at_ms`) but not how long a `speak` occupies its actor, which F1 dialogue beats need. This section is a proposal only: it changes no code, no validator rule and no schema. Adoption path is forward-compatible — event objects already tolerate extra fields, so authors may write `duration_ms` on `speak` today and current validators accept it; the preview ignores it until this proposal is adopted and implemented.

- **Speak hold.** A `speak` event occupies its actor for a hold window `[at_ms, at_ms + hold)`. `hold` is the event's explicit `duration_ms` when present; otherwise it is derived deterministically from the line: `ceil(len(line) / 15) * 1000` ms (15 characters/second ≈ 150 wpm natural delivery), clamped to 800–15000 ms. Explicit-first is the choice because directed scenes need exact beats, while the derived default keeps existing scenes — including the demo, whose lines carry no duration — playable with sane pacing and zero reauthoring. The derivation is a pure function of the line, so previews are deterministic and the future TTS stage can reconcile the same number against real audio length.
- **Blocking scope: per actor, never global.** A speak hold gates only later events for the *same* actor: if such an event's `at_ms` falls inside the window, the runtime delays it until the window ends (safety net). Other actors and `camera` events are never delayed — conversation partners can react mid-line. Follow-up for a future wire revision (not this proposal): the Python validator should *reject* a scene whose same-actor events overlap a speak hold, so authoring errors surface at plan time instead of being silently delayed.
- **Camera cuts are instantaneous.** A `camera` event takes effect exactly at its `at_ms`, has no duration, is never blocked by a speak hold and blocks nothing. On tied timestamps the existing stable array-order rule decides application order. Fades/dolly moves are out of scope for v1 and would arrive as new ops, not as a duration on `camera`.
- **Move and emote unchanged.** `move` already carries a validated `duration_ms` (100–60000 ms); it remains fire-at-`at_ms` — its motion runs concurrently and a later same-actor event applies on schedule (interrupting/retargeting the motion), exactly as the preview behaves today. `emote` is an instantaneous state change at its `at_ms` with no hold. Speak is the only op this proposal gives a hold.
- **Demo check.** Under this model the demo scene stays consistent: the traveler's 43-character line at 3800 ms derives a ≈2867 ms hold ending at ≈6667 ms; the innkeeper's reply at 6600 ms is a different actor, so per-actor blocking does not delay it, and no same-actor event falls inside any hold.
