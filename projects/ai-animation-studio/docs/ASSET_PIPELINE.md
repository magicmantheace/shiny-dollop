# Asset library and growth pipeline

## Lifecycle

`idea/request -> candidate -> imported -> validated -> approved -> reusable -> retired`

Current database implements candidate/approved/retired. Detailed transitions, jobs and revision history are planned; do not confuse a candidate record with a usable media file.

## Intake checklist

1. Record source, creator, license, restrictions, version, hash, rig family and dependencies.
2. Check files exist under approved asset roots; block symlinks, traversal, executables and unexpected formats.
3. Convert to glTF 2.0 / GLB where appropriate. Store source files outside the application repo if too large.
4. Validate skeleton/material slots, scale, sockets, LOD, texture sizes, polycount and animation duration.
5. Run automatic static tests plus visual animation/thumbnail review.
6. Promote explicitly to approved; record immutable asset version and provenance. Existing scenes pin versions.
7. Add semantic tags and compatibility graph entries. Reindex for offline retrieval.

## Character composition

Recipe references canonical rig_id, body/head/hair/outfit and materials. Recipe IDs are stable; rendering resolves them to approved asset versions. For missing components choose a known compatible fallback or refuse production use.

## Motion strategy

1. Hand-authored clips and retargeted licensed motions.
2. AnimationTree blends plus IK, gaze and emotion overlays.
3. Locally generated motion clips created in a non-live job, validated and added to the library.
4. Model-generated body pose stream only after latency, continuity and contact tests.

## Missing-action queue

During live scene, request `drink_mug` -> search compatible approved actions -> use existing or combine `hold`+`head_tilt`+`place` -> if unavailable, use idle/gesture fallback and queue an offline creation task. Never hold the render thread waiting for generation.

## Metadata proposals

Store: source_uri, SHA256, license SPDX/name and evidence, author, creation date, rig family, retarget profile, LOD, texture budget, polycount, clip type/loop, contacts, approved_by, version, thumbnails, dependencies and validation history.

## Storage policy

Git tracks code, docs and tiny metadata fixtures. Downloaded models, rigged asset packs, audio, rendered media and SQLite databases stay local or in a separate explicit artifact store. Backups must capture asset files and catalog together.

**Local asset store (from 2026-11-03, F1):** `~/workspace/ai-animation-studio-assets/` on the development VM (outside git). Registered URIs are relative to that directory (`assets/characters/…`, `assets/animations/…`, `assets/environment/…`); original vendor zips and full extractions stay alongside under `downloads/` and `store/` for provenance. The Godot preview resolves the store through the `AI_ANIMATION_ASSET_ROOT` environment variable and falls back to procedural capsules when it is unset or files are missing. The store path is machine-local state, not a project constant — a different machine sets the variable to its own copy.
