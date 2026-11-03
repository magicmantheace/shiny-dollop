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
