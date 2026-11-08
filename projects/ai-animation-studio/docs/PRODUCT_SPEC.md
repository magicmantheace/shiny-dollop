# Product specification: AI Animation Studio

## Product promise

An offline-first **real-time directed 3D animation** workstation. User or LLM describes an event; runtime chooses existing approved, retargetable assets and schedules validated intent. Godot renders every frame. New character parts, animations and sets are created separately and admitted to a durable library after verification.

## Primary user story

"Two stylized characters meet in a tavern. A traveler approaches, acts nervous and asks for a room." The studio previews the characters, path, gesture, speech timing and camera without generating video pixels.

## MVP acceptance criteria

1. Load a versioned scene with two characters and an environment; reject unknown commands.
2. Godot runs a scene timeline without a Python/model dependency during playback.
3. SQLite retains character recipes, assets and scenes between sessions.
4. Scene planner uses only existing approved assets at runtime; if missing, choose fallback or record a queued creation request (future stage).
5. Python validation tests cover schema failures, unknown actors, path traversal, idempotent library writes.
6. Render two stylized rigged characters, one room, locomotion and speaking (planned: requires asset pack).
7. Provide owner-hardware performance measurements before claiming 30 FPS.

## Non-goals for MVP

- Continuous diffusion/video-frame generation; fully autonomous art or rigging; photorealistic humans.
- Cloud model requirement, copyrighted characters/voices, live VR, online multi-user scenes.
- Direct integration with AthenZ, Developmental-AI or Synveil.

## Success metrics

- Frame time p95 <= 33.3 ms for target 30 FPS *on owner hardware* with 2 characters (not yet measured).
- AI/event planning has a bounded queue; renderer keeps moving during model delays.
- 100% scene commands schema+semantic validated before dispatch.
- At least 10 reusable animation tags, 5 expressions and 2 distinct character recipes once MVP art is added.
- Crash recovery replays a saved scene safely; persistent catalog schema can migrate.

## Personas and use modes

- Creator: text prompt to editable scene.
- Director: dialogue, acting, shot choice and staging.
- Librarian: intake, inspect, version, validate, tag and retire assets.
- Runtime: low-latency renderer with deterministic fallbacks.

**Status:** this file specifies future behavior. Current preview is a procedural stand-in with stdout dialogue only.
