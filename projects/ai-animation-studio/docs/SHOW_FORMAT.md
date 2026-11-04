# Show format, world state and continuity (F6 foundation)

A **show** is an ordered set of scenes played as one production. This
document defines the manifest that names the set, the end-of-scene
**memory** the runtime captures, how that memory is carried into the
next scene (**continuity**), the **world-state store** that holds
show-level facts, and the archival **package** a show is exported as.

Scope: this is a foundation. Nothing here generates scenes, branches a
story, or decides pacing. The roadmap's F6 exit (long-form stable
playback) remains a long-term direction; see
`docs/IMPLEMENTATION_STATUS.md` for exactly what is implemented and
what is explicitly not claimed.

## Show manifest

One JSON document, validated by `studio.shows.validate_show` and
mirrored by `schemas/show.schema.json` (the hand validator and the
schema are kept in parity by `tests/test_shows.py`):

```json
{
  "schema_version": "1.0.0",
  "show_id": "tavern_evening",
  "title": "Tavern Evening",
  "scenes": [
    {"scene_id": "tavern_arrival", "scene": { "...scene document..." }},
    {"scene_id": "tavern_departure", "scene": { "...scene document..." }}
  ]
}
```

Rules:

- Scenes are **inline documents** (not file references), so a manifest
  validates end-to-end in one pass. Each inline scene must pass the
  full scene validator (`studio.schema.validate_scene`).
- Each entry's `scene_id` must equal its scene's own `scene_id`;
  entry ids must be unique; a show carries 1..64 scenes.
- No unknown keys at the manifest or entry level; `show_id` follows
  the usual identifier rule; `title` is 1..256 characters.
- Cast continuity is **by actor id** across scenes: the same id in two
  scenes is the same character, whatever recipe each scene declares.

A canonical example is `examples/show_tavern_evening.json`.

## Scene memory

`capture_scene_memory(scene)` is a pure function: from
`compute_schedule` plus the scene document it computes the scene's end
state —

```json
{"scene_id": "tavern_arrival", "makespan_ms": 9500,
 "actors": {"traveler": {"position": [-0.9, 0, 0], "holding": null, "seated": false}},
 "props": {"mug": {"position": [1.4, 0.78, 0.5], "held_by": null}}}
```

- `makespan_ms` is the schedule's scene end — the same definition the
  F5.1 validation preview uses (per event: latest of dispatch time,
  occupancy-window end, and, for a move, arrival).
- An actor's end **position** is the target of its last
  position-setting event in dispatch order: spawn position, then any
  move target, then any sit target. An actor that never moves keeps
  its spawn position; an actor declared but never spawned records
  `null`.
- An actor's end **holding** / **seated** state is the
  `holding_after` / `seated_after` of its last schedule record.
- A prop's end position is its holder's end position when held at the
  scene's end (the preview parents a held prop to the holder's hand
  socket, so it literally travels with them); otherwise the target of
  its last `put_down` — or its holder's position at release when that
  `put_down` names no target — otherwise its declared position.
  `held_by` is the holder's id or `null`.

## Continuity application

`apply_continuity(scene, memory)` returns `(scene_copy, notes)`. The
input scene is never mutated. Application rules:

- Each actor's **spawn position** is replaced by its memory position,
  and each declared prop's **position** likewise.
- **Holding is never written into the scene document.** Holding is
  runtime state; a held prop's declared position is still set (to its
  holder's end position) and the note says it was held, but the next
  scene starts with nobody holding anything unless its own events say
  so.
- `notes` lists **every** change and every non-application, in scene
  order: a replaced position (old -> new), an already-matching
  position, an actor/prop in the scene with no memory, an actor/prop
  in memory but not in the scene, and an actor whose memory carries no
  position.
- Applying the same memory to its own output is stable: the returned
  scene is identical (the notes then report positions as already
  matching).

The CLI prints and records the chain:

```
python -m studio continuity --show show_tavern_evening.json --scene-index 1
```

`--scene-index` is 0-based. The command validates the show, captures
each scene's memory in play order, prints the chain, and for scene
n > 0 prints the notes from applying scene n-1's memory to scene n.
When a library database exists at `--db`, each memory is also recorded
into it (a missing database is reported, never silently created).

## World-state store

Migration 5 adds two tables to the library database:

- `world_state(key TEXT PRIMARY KEY, value_json, updated_at)` —
  show-level facts (where things are, what has happened), addressed
  through `set_state` / `get_state` / `snapshot_state` in
  `studio/shows.py`. Values must be JSON-serializable.
- `scene_memory(memory_id, show_id, scene_id, memory_json,
  recorded_at)` — captured memories appended per show, read back with
  `record_scene_memory` / `latest_memory` (optionally filtered to one
  scene). Records are append-only; the latest record wins.

The store is bookkeeping for shows, not a second scene format: scenes
stay the only authored documents.

## Show package

`export_show_package(show, out_dir)` writes an archival package:

```
<out_dir>/
  show.json                  the manifest, as authored
  scenes/<scene_id>.json     one IPC envelope per scene (studio/ipc.py)
  package.json               {"show_id", "ipc_version",
                              "exported_files": {path: sha256}}
```

`package.json` hashes every exported file except itself.
`verify_show_package(dir)` re-reads everything: each listed file must
exist and hash to its recorded value, the manifest must re-validate,
each scene envelope must re-validate and match its manifest entry, and
no unlisted file may sit under `scenes/`. Any failure raises an error
naming the offending path. CLI:

```
python -m studio export-show --show show_tavern_evening.json --out pkg_dir
python -m studio verify-show --out pkg_dir
```
