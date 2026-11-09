"""Multi-scene shows, world state and scene memory (F6 foundation).

A show is a manifest of inline scene documents played in order. Cast
continuity is by actor id across scenes: what a scene ends with — actor
positions, seated state, who holds which prop and where each prop rests
— is captured as scene memory, and the next scene's spawn and prop
positions can be carried forward from it.

This module is deliberately a foundation, not a show generator: it
defines the manifest, the memory rules, the continuity application and
the archival package format. It generates no scenes, branches no
stories and makes no pacing decisions. The roadmap's F6 exit (long-form
stable playback) is a long-term direction; what is claimed here is the
mechanics below, with test and headless evidence.

Manifest (docs/SHOW_FORMAT.md):

    {"schema_version": "1.0.0", "show_id": <id>, "title": <str>,
     "scenes": [{"scene_id": <id>, "scene": <scene document>}, ...]}

Every inline scene passes full `validate_scene`; each entry's scene_id
must equal its scene's scene_id, and entry scene_ids must be unique.

Memory capture (`capture_scene_memory`, pure): from `compute_schedule`
plus the scene document, in dispatch order —

- an actor's end position is the target of its last position-setting
  event (spawn position, then any move target, then any sit target);
  an actor that never moves keeps its spawn position, and an actor
  declared but never spawned records position None (continuity notes
  it and leaves that spawn alone);
- an actor's end holding / seated state is the `holding_after` /
  `seated_after` of its last schedule record;
- a prop's end position is its holder's end position when held at the
  scene's end, else the target of its last put_down (or its holder's
  position at release when that put_down names no target), else its
  declared position; `held_by` is the holder's id or None.

Continuity (`apply_continuity`, pure): returns a COPY of the next scene
with each actor's spawn position replaced by its memory position and
each declared prop's position replaced likewise, plus a `notes` list
recording every change and every non-application (actor in the scene
with no memory, actor in memory but not in the scene, prop ditto,
actor with no spawn event, prop held at the previous scene's end).
Holding is runtime state and is deliberately NOT written into the
scene document: a held prop's declared position is still set to its
holder's end position, and the note says so.

World state (migration 5): a `world_state` key/value table and a
`scene_memory` table holding captured memories per show. The store is
for show-level facts (where things are, what has happened); it is not
a second scene format.

Package (`export_show_package` / `verify_show_package`): a directory
holding `show.json`, one IPC-enveloped scene per manifest entry under
`scenes/<scene_id>.json`, and `package.json` — `{show_id,
ipc_version, exported_files: {relative path: sha256}}` covering every
file except `package.json` itself. Verification re-reads every listed
file, re-checks every hash, re-validates the manifest and every scene
envelope, and refuses any file added under `scenes/` that the package
does not list. Any failure names the offending path.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

try:
    from .ipc import IPC_VERSION, read_ipc, write_ipc
    from .library import Library
    from .schema import ValidationError, identifier, need, validate_scene
    from .timing import compute_schedule, resolve_timing
except ImportError:  # standalone module use (studio/ on sys.path)
    from ipc import IPC_VERSION, read_ipc, write_ipc  # type: ignore[no-redef]
    from library import Library  # type: ignore[no-redef]
    from schema import ValidationError, identifier, need, validate_scene  # type: ignore[no-redef]
    from timing import compute_schedule, resolve_timing  # type: ignore[no-redef]

SHOW_VERSION = "1.0.0"
SHOW_KEYS = frozenset({"schema_version", "show_id", "title", "scenes"})
SCENE_ENTRY_KEYS = frozenset({"scene_id", "scene"})
MAX_SCENES = 64


class ShowError(ValueError):
    """A show manifest, memory record or package was refused, with a
    named reason (and, for package verification, the offending path)."""


def validate_show(show: dict) -> dict:
    """Validate a show manifest end to end, including every scene."""
    need(isinstance(show, dict), "show must be object")
    unknown = set(show) - SHOW_KEYS
    need(not unknown, f"show: unknown keys {sorted(unknown)}")
    need(show.get("schema_version") == SHOW_VERSION, "unsupported show version")
    identifier(show.get("show_id"), "show_id")
    title = show.get("title")
    need(isinstance(title, str) and 1 <= len(title) <= 256, "title must be a string of 1..256 chars")
    entries = show.get("scenes")
    need(isinstance(entries, list) and 1 <= len(entries) <= MAX_SCENES,
         f"scenes must contain 1..{MAX_SCENES} entries")
    seen = set()
    for n, entry in enumerate(entries):
        prefix = f"scenes[{n}]"
        need(isinstance(entry, dict), prefix + ": not object")
        unknown = set(entry) - SCENE_ENTRY_KEYS
        need(not unknown, f"{prefix}: unknown keys {sorted(unknown)}")
        identifier(entry.get("scene_id"), prefix + ".scene_id")
        need(entry["scene_id"] not in seen, prefix + ": duplicate scene_id")
        seen.add(entry["scene_id"])
        scene = entry.get("scene")
        try:
            validate_scene(scene)
        except ValidationError as exc:
            raise ShowError(f"{prefix}.scene: invalid scene: {exc}") from exc
        need(scene["scene_id"] == entry["scene_id"],
             f"{prefix}: scene_id does not match its scene's scene_id")
    return show


def _scene_end(records: list, events: list) -> int:
    """Scene end (makespan): the same definition the F5.1 validation
    preview uses — per record, the latest of its dispatch time, its
    occupancy-window end (speak/interact) and, for a move, its arrival
    (dispatch + duration_ms)."""
    end = 0
    for record in records:
        at = record["effective_ms"]
        if record["window_end_ms"] is not None:
            at = max(at, record["window_end_ms"])
        if record["op"] == "move":
            event = events[record["index"]]
            at = max(at, record["effective_ms"] + int(event.get("duration_ms", 0)))
        end = max(end, at)
    return end


def capture_scene_memory(scene: dict) -> dict:
    """Compute a scene's end state. Pure: neither the scene nor the
    schedule records are mutated."""
    validate_scene(scene)
    timing = resolve_timing(scene.get("timing"))
    records = compute_schedule(scene["events"], timing)
    events = scene["events"]
    actors: dict[str, dict] = {}
    for actor in scene["actors"]:
        actors[actor["id"]] = {"position": None, "holding": None, "seated": False}
    props: dict[str, dict] = {}
    for prop in scene.get("props", []):
        props[prop["id"]] = {"position": list(prop["position"]), "held_by": None}
    for record in records:
        actor_id = record["actor_id"]
        if actor_id is None:
            continue
        state = actors[actor_id]
        event = events[record["index"]]
        if record["op"] == "spawn":
            state["position"] = list(event["position"])
        elif record["op"] == "move":
            state["position"] = list(event["target"])
        elif record["op"] == "interact" and record["action"] == "sit":
            state["position"] = list(event["target"])
        elif record["op"] == "interact" and record["action"] == "put_down":
            prop_id = record["prop_id"]
            if prop_id in props:
                props[prop_id]["position"] = (
                    list(event["target"]) if "target" in event
                    else list(state["position"]))
        state["holding"] = record["holding_after"]
        state["seated"] = record["seated_after"]
    for prop_id, prop in props.items():
        holder = None
        for actor_id, state in actors.items():
            if state["holding"] == prop_id:
                holder = actor_id
                break
        prop["held_by"] = holder
        if holder is not None:
            prop["position"] = list(actors[holder]["position"])
    return {
        "scene_id": scene["scene_id"],
        "makespan_ms": _scene_end(records, events),
        "actors": actors,
        "props": props,
    }


def apply_continuity(scene: dict, memory: dict | None) -> tuple[dict, list[str]]:
    """Return (scene copy, notes) with memory applied to spawn and prop
    positions. The input scene is never mutated; every change — and
    every non-application — is listed in `notes`, in scene order
    (actors, then props), with memory-only entries sorted by id after
    their section. A second application of the same memory to its own
    output returns an identical scene (positions already match; the
    notes then say so)."""
    validate_scene(scene)
    out = copy.deepcopy(scene)
    notes: list[str] = []
    if memory is None:
        notes.append("no prior scene memory: no continuity applied")
        return out, notes
    if not isinstance(memory, dict) or not isinstance(memory.get("actors"), dict) \
            or not isinstance(memory.get("props"), dict) \
            or not all(isinstance(v, dict) for v in memory["actors"].values()) \
            or not all(isinstance(v, dict) for v in memory["props"].values()):
        raise ShowError("continuity memory must carry actors and props objects")
    memory_actors = memory["actors"]
    memory_props = memory["props"]
    spawn_by_actor = {}
    for event in out["events"]:
        if event["op"] == "spawn":
            spawn_by_actor[event["actor_id"]] = event
    for actor in out["actors"]:
        actor_id = actor["id"]
        if actor_id not in memory_actors:
            notes.append(f"actor {actor_id}: no memory; spawn position unchanged")
            continue
        if memory_actors[actor_id].get("position") is None:
            notes.append(f"actor {actor_id}: memory carries no position "
                         "(never spawned there); spawn position unchanged")
            continue
        spawn = spawn_by_actor.get(actor_id)
        if spawn is None:
            notes.append(f"actor {actor_id}: no spawn event; memory position not applied")
            continue
        old = list(spawn["position"])
        new = list(memory_actors[actor_id]["position"])
        if old == new:
            notes.append(f"actor {actor_id}: spawn already at memory position {new}; unchanged")
        else:
            spawn["position"] = new
            notes.append(f"actor {actor_id}: spawn position {old} -> {new}")
    for actor_id in sorted(set(memory_actors) - {a["id"] for a in out["actors"]}):
        notes.append(f"actor {actor_id}: in memory but not in this scene; ignored")
    for prop in out.get("props", []):
        prop_id = prop["id"]
        if prop_id not in memory_props:
            notes.append(f"prop {prop_id}: no memory; declared position unchanged")
            continue
        old = list(prop["position"])
        new = list(memory_props[prop_id]["position"])
        held_by = memory_props[prop_id].get("held_by")
        if old == new:
            notes.append(f"prop {prop_id}: declared position already at memory position {new}; unchanged")
        else:
            prop["position"] = new
            if held_by is not None:
                notes.append(
                    f"prop {prop_id}: declared position {old} -> {new} "
                    f"(held by {held_by} at the previous scene's end; "
                    f"holding is runtime state, not declared)")
            else:
                notes.append(f"prop {prop_id}: declared position {old} -> {new}")
    for prop_id in sorted(set(memory_props) - {p["id"] for p in out.get("props", [])}):
        notes.append(f"prop {prop_id}: in memory but not in this scene; ignored")
    validate_scene(out)
    return out, notes


# --- World-state store (migration 5) ---------------------------------------


def set_state(lib: Library, key: str, value: object) -> None:
    """Upsert one world-state fact. The value must be JSON-serializable."""
    if not isinstance(key, str) or not key:
        raise ShowError("world-state key must be a non-empty string")
    try:
        encoded = json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ShowError(f"world-state value for {key!r} is not JSON-serializable") from exc
    lib.db.execute(
        "INSERT INTO world_state(key, value_json) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, "
        "updated_at=CURRENT_TIMESTAMP",
        (key, encoded),
    )
    lib.db.commit()


def get_state(lib: Library, key: str, default: object = None) -> object:
    """Read one world-state fact, or `default` when the key is absent."""
    row = lib.db.execute(
        "SELECT value_json FROM world_state WHERE key=?", (key,)).fetchone()
    return json.loads(row["value_json"]) if row is not None else default


def snapshot_state(lib: Library) -> dict:
    """The whole world-state table as {key: value}, sorted by key."""
    return {
        row["key"]: json.loads(row["value_json"])
        for row in lib.db.execute("SELECT key, value_json FROM world_state ORDER BY key")
    }


def record_scene_memory(lib: Library, show_id: str, memory: dict) -> int:
    """Append a captured memory record for a show; returns its id."""
    identifier(show_id, "show_id")
    if not isinstance(memory, dict) or not isinstance(memory.get("scene_id"), str):
        raise ShowError("scene memory must be an object carrying a scene_id")
    try:
        encoded = json.dumps(memory)
    except (TypeError, ValueError) as exc:
        raise ShowError("scene memory is not JSON-serializable") from exc
    cur = lib.db.execute(
        "INSERT INTO scene_memory(show_id, scene_id, memory_json) VALUES(?,?,?)",
        (show_id, memory["scene_id"], encoded),
    )
    lib.db.commit()
    return cur.lastrowid


def latest_memory(lib: Library, show_id: str, scene_id: str | None = None) -> dict | None:
    """The most recent memory record for a show (optionally for one
    scene), or None when none exists."""
    if scene_id is None:
        row = lib.db.execute(
            "SELECT memory_json FROM scene_memory WHERE show_id=? "
            "ORDER BY memory_id DESC LIMIT 1", (show_id,)).fetchone()
    else:
        row = lib.db.execute(
            "SELECT memory_json FROM scene_memory WHERE show_id=? AND scene_id=? "
            "ORDER BY memory_id DESC LIMIT 1", (show_id, scene_id)).fetchone()
    return json.loads(row["memory_json"]) if row is not None else None


# --- Show package ------------------------------------------------------------


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_show_package(show: dict, out_dir: Path) -> dict:
    """Write a show package directory: show.json, one IPC-enveloped
    scene per manifest entry under scenes/<scene_id>.json, and
    package.json listing every exported file's SHA-256. Returns the
    package document."""
    validate_show(show)
    out_dir = Path(out_dir)
    scenes_dir = out_dir / "scenes"
    scenes_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "show.json").write_text(
        json.dumps(show, indent=2) + "\n", encoding="utf-8")
    exported: dict[str, str] = {}
    exported["show.json"] = _sha256_file(out_dir / "show.json")
    for entry in show["scenes"]:
        scene_path = scenes_dir / f"{entry['scene_id']}.json"
        write_ipc(scene_path, entry["scene"])
        exported[f"scenes/{entry['scene_id']}.json"] = _sha256_file(scene_path)
    package = {
        "show_id": show["show_id"],
        "ipc_version": IPC_VERSION,
        "exported_files": exported,
    }
    (out_dir / "package.json").write_text(
        json.dumps(package, indent=2) + "\n", encoding="utf-8")
    return package


def verify_show_package(package_dir: Path) -> dict:
    """Re-verify a show package: every listed file exists and hashes
    to its recorded value, the manifest re-validates, every listed
    scene envelope re-validates and matches its manifest entry, and
    no unlisted file sits under scenes/. Returns a summary on success;
    raises ShowError naming the offending path on any failure."""
    package_dir = Path(package_dir)
    try:
        package = json.loads((package_dir / "package.json").read_text(encoding="utf-8"))
    except OSError as exc:
        raise ShowError(f"package verification: cannot read package.json: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ShowError(f"package verification: invalid package.json: {exc}") from exc
    if not isinstance(package, dict):
        raise ShowError("package verification: package.json must be an object")
    exported = package.get("exported_files")
    if not isinstance(exported, dict) or not exported:
        raise ShowError("package verification: package.json carries no exported_files")
    if package.get("ipc_version") != IPC_VERSION:
        raise ShowError(
            f"package verification: unsupported ipc_version {package.get('ipc_version')!r}")
    for rel, recorded in exported.items():
        if not isinstance(rel, str) or not isinstance(recorded, str):
            raise ShowError("package verification: exported_files entries must be path -> sha256 strings")
        path = package_dir / rel
        if not path.is_file():
            raise ShowError(f"package verification: missing file {rel}")
        actual = _sha256_file(path)
        if actual != recorded:
            raise ShowError(f"package verification: hash mismatch for {rel}")
    try:
        show = json.loads((package_dir / "show.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ShowError(f"package verification: cannot read show.json: {exc}") from exc
    try:
        validate_show(show)
    except (ValidationError, ShowError) as exc:
        raise ShowError(f"package verification: show.json failed validation: {exc}") from exc
    if show["show_id"] != package.get("show_id"):
        raise ShowError("package verification: package show_id does not match show.json")
    for entry in show["scenes"]:
        rel = f"scenes/{entry['scene_id']}.json"
        if rel not in exported:
            raise ShowError(f"package verification: manifest scene {entry['scene_id']} has no exported file")
        try:
            scene = read_ipc(package_dir / rel)
        except Exception as exc:
            raise ShowError(f"package verification: scene file {rel} failed validation: {exc}") from exc
        if scene["scene_id"] != entry["scene_id"]:
            raise ShowError(f"package verification: scene file {rel} id does not match the manifest")
    listed = set(exported)
    scenes_dir = package_dir / "scenes"
    if scenes_dir.is_dir():
        for path in sorted(scenes_dir.iterdir()):
            rel = f"scenes/{path.name}"
            if path.is_file() and rel not in listed:
                raise ShowError(f"package verification: unlisted file {rel}")
    return {
        "show_id": show["show_id"],
        "scene_count": len(show["scenes"]),
        "files_checked": len(exported),
    }
