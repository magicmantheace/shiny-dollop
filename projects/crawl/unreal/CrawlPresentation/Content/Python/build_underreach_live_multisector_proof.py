"""Headless UE 5.8 live traversal proof for Underreach Slice 29B.2.1.

The proof instantiates the accepted 29B.2 multi-Sector geometry, spawns one live
Descender presentation actor plus Follow/Auto camera actors, physically moves the
Descender through every proof-route Sector, updates both cameras every frame, and
verifies checkpoint/resume state against the same Stratum and presentation digests.

This remains presentation-only and uses NullRHI in the validation runner.
"""

from __future__ import annotations

import importlib.util
import json
import math
import sys
from pathlib import Path

import unreal

PROJECT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
REPO_ROOT = PROJECT_DIR.parents[1]
SRC_DIR = REPO_ROOT / "src" / "livingworld"
OUTPUT_DIR = PROJECT_DIR / "Generated" / "underreach-29b21"
OUTPUT_PATH = OUTPUT_DIR / "live-multisector-unreal-debug.json"
CHECKPOINT_PATH = OUTPUT_DIR / "live-multisector-checkpoint.json"
SEED = "underreach-29b21-unreal-proof"
SECTOR_COUNT = 9


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module spec: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# Load only stdlib-only 29B modules; do not execute livingworld.__init__, which
# would require third-party packages absent from Unreal's embedded Python.
stratum_environment = _load_module("underreach_29b1_stratum_environment", SRC_DIR / "stratum_environment.py")

# 29B.2 uses a relative import. Create a tiny synthetic package that contains
# only the accepted Stratum module so the relative import resolves cleanly.
import types
pkg = types.ModuleType("underreach_29b")
pkg.__path__ = [str(SRC_DIR)]
sys.modules["underreach_29b"] = pkg
sys.modules["underreach_29b.stratum_environment"] = stratum_environment
stratum_multisector = _load_module("underreach_29b.stratum_multisector", SRC_DIR / "stratum_multisector.py")
sys.modules["underreach_29b.stratum_multisector"] = stratum_multisector
stratum_live = _load_module("underreach_29b.stratum_live_traversal", SRC_DIR / "stratum_live_traversal.py")


def _vec(payload):
    return unreal.Vector(float(payload["x"]), float(payload["y"]), float(payload.get("z", 0.0)))


def _distance(a, b):
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


def _spawn_cube(actor_subsystem, label, location, size, folder):
    mesh = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if mesh is None:
        raise RuntimeError("Engine Cube mesh unavailable")
    actor = actor_subsystem.spawn_actor_from_class(unreal.StaticMeshActor, _vec(location), unreal.Rotator(), False)
    if actor is None:
        raise RuntimeError(f"Could not spawn {label}")
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    component.set_world_scale3d(unreal.Vector(float(size[0]) / 100.0, float(size[1]) / 100.0, float(size[2]) / 100.0))
    try:
        component.set_collision_enabled(unreal.CollisionEnabled.QUERY_AND_PHYSICS)
    except Exception:
        pass
    return actor


def _cleanup(actor_subsystem):
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        try:
            label = actor.get_actor_label()
        except Exception:
            continue
        if label.startswith("Underreach29B21_"):
            actor_subsystem.destroy_actor(actor)


def _spawn_geometry(actor_subsystem, plan):
    spawned = []
    for room in plan["rooms"]:
        origin = room["world_origin_cm"]
        size = room["room_size_cm"]
        spawned.append(_spawn_cube(
            actor_subsystem,
            f"Underreach29B21_Room_{room['sector_id']}",
            {"x": origin["x"], "y": origin["y"], "z": -15.0},
            (size["x"], size["y"], 30.0),
            "Underreach/29B21/Rooms",
        ))
    for corridor in plan["corridors"]:
        center = corridor["center_cm"]
        horizontal = abs(float(corridor["yaw_degrees"])) < 1.0
        sx = float(corridor["length_cm"]) if horizontal else float(corridor["width_cm"])
        sy = float(corridor["width_cm"]) if horizontal else float(corridor["length_cm"])
        spawned.append(_spawn_cube(
            actor_subsystem,
            f"Underreach29B21_Corridor_{corridor['corridor_id']}",
            {"x": center["x"], "y": center["y"], "z": -15.0},
            (sx, sy, 30.0),
            "Underreach/29B21/Corridors",
        ))
    return spawned


def _spawn_camera(actor_subsystem, label):
    actor = actor_subsystem.spawn_actor_from_class(unreal.CineCameraActor, unreal.Vector(), unreal.Rotator(), False)
    if actor is None:
        raise RuntimeError(f"Could not spawn camera {label}")
    actor.set_actor_label(label)
    actor.set_folder_path("Underreach/29B21/Feed")
    return actor


def _look_at_rotation(camera, target):
    dx = target.x - camera.x
    dy = target.y - camera.y
    dz = target.z - camera.z
    yaw = math.degrees(math.atan2(dy, dx))
    horizontal = max(math.hypot(dx, dy), 1e-6)
    pitch = math.degrees(math.atan2(dz, horizontal))
    return unreal.Rotator(pitch, yaw, 0.0)


def _set_camera(actor, camera_payload, target_payload):
    camera = _vec(camera_payload)
    target = _vec(target_payload)
    actor.set_actor_location(camera, False, False)
    actor.set_actor_rotation(_look_at_rotation(camera, target), False)


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _cleanup(actor_subsystem)

    manifest = stratum_environment.build_stratum_environment_manifest(SEED, 0, sector_count=SECTOR_COUNT)
    plan = stratum_multisector.build_multisector_presentation_plan(manifest)
    stream = stratum_live.build_live_traversal_stream(manifest, plan, descender_id="descender_000")
    geometry = _spawn_geometry(actor_subsystem, plan)

    first = stream["frames"][0]
    descender = _spawn_cube(
        actor_subsystem,
        "Underreach29B21_Descender_descender_000",
        first["transform"],
        (70.0, 70.0, 188.0),
        "Underreach/29B21/Live",
    )
    follow_camera = _spawn_camera(actor_subsystem, "Underreach29B21_Feed_Follow")
    auto_camera = _spawn_camera(actor_subsystem, "Underreach29B21_Feed_Auto")

    frame_records = []
    empty_camera_windows = 0
    stale_target_windows = 0
    max_descender_error_cm = 0.0
    max_follow_camera_error_cm = 0.0
    max_auto_camera_error_cm = 0.0
    sector_transitions = 0
    last_sector = first["sector_id"]
    checkpoint_index = len(stream["frames"]) // 2
    checkpoint = None

    for index, frame in enumerate(stream["frames"]):
        expected_descender = _vec(frame["transform"])
        descender.set_actor_location(expected_descender, False, False)
        actual_descender = descender.get_actor_location()
        descender_error = _distance(actual_descender, expected_descender)
        max_descender_error_cm = max(max_descender_error_cm, descender_error)

        if frame["sector_id"] != last_sector:
            sector_transitions += 1
            last_sector = frame["sector_id"]

        follow = frame["feed"]["follow"]
        auto = frame["feed"]["auto"]
        if follow.get("empty") or auto.get("empty"):
            empty_camera_windows += 1
        if follow.get("stale") or auto.get("stale"):
            stale_target_windows += 1
        if follow.get("target_id") != stream["descender_id"] or auto.get("target_id") != stream["descender_id"]:
            stale_target_windows += 1

        _set_camera(follow_camera, follow["camera"], frame["transform"])
        _set_camera(auto_camera, auto["camera"], frame["transform"])
        follow_error = _distance(follow_camera.get_actor_location(), _vec(follow["camera"]))
        auto_error = _distance(auto_camera.get_actor_location(), _vec(auto["camera"]))
        max_follow_camera_error_cm = max(max_follow_camera_error_cm, follow_error)
        max_auto_camera_error_cm = max(max_auto_camera_error_cm, auto_error)

        if index == checkpoint_index:
            checkpoint = stratum_live.make_checkpoint(stream, index)
            CHECKPOINT_PATH.write_text(json.dumps(checkpoint, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        frame_records.append({
            "sequence": frame["sequence"],
            "sector_id": frame["sector_id"],
            "phase": frame["phase"],
            "descender_error_cm": descender_error,
            "follow_camera_error_cm": follow_error,
            "auto_camera_error_cm": auto_error,
        })

    if checkpoint is None:
        raise RuntimeError("Checkpoint was not created")
    checkpoint_loaded = json.loads(CHECKPOINT_PATH.read_text(encoding="utf-8"))
    resumed = stratum_live.resume_from_checkpoint(stream, checkpoint_loaded)
    resume_first = resumed[0]
    resume_last = resumed[-1]

    validation = {
        "route_started_at_entry": stream["frames"][0]["sector_id"] == manifest["entry_sector_id"],
        "route_finished_at_exit": stream["frames"][-1]["sector_id"] == manifest["exit_sector_id"],
        "visited_all_route_sectors": sector_transitions == len(stream["route_sector_ids"]) - 1,
        "descender_actor_followed_stream": max_descender_error_cm <= 0.01,
        "follow_camera_followed_stream": max_follow_camera_error_cm <= 0.01,
        "auto_camera_followed_stream": max_auto_camera_error_cm <= 0.01,
        "no_empty_camera_windows": empty_camera_windows == 0,
        "no_stale_target_windows": stale_target_windows == 0,
        "checkpoint_stratum_digest_preserved": checkpoint_loaded["stratum_environment_digest"] == manifest["digest"],
        "checkpoint_multisector_digest_preserved": checkpoint_loaded["multisector_digest"] == plan["digest"],
        "checkpoint_current_sector_preserved": checkpoint_loaded["current_sector_id"] == resume_first["sector_id"],
        "resume_reaches_same_exit": resume_last["sector_id"] == manifest["exit_sector_id"],
        "presentation_only": stream["authoritative"] is False and checkpoint_loaded["authoritative"] is False,
    }
    validation["all_pass"] = all(validation.values())

    debug = {
        "protocol": "underreach.live-multisector-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "descender_id": stream["descender_id"],
        "stratum_environment_digest": manifest["digest"],
        "multisector_digest": plan["digest"],
        "live_traversal_digest": stream["digest"],
        "route_sector_ids": stream["route_sector_ids"],
        "frame_count": len(stream["frames"]),
        "sector_transition_count": sector_transitions,
        "geometry_actor_count": len(geometry),
        "spawned_live_actor_count": 3,
        "empty_camera_windows": empty_camera_windows,
        "stale_target_windows": stale_target_windows,
        "max_descender_error_cm": max_descender_error_cm,
        "max_follow_camera_error_cm": max_follow_camera_error_cm,
        "max_auto_camera_error_cm": max_auto_camera_error_cm,
        "checkpoint_frame_index": checkpoint_index,
        "checkpoint_current_sector_id": checkpoint_loaded["current_sector_id"],
        "resume_frame_count": len(resumed),
        "frame_records": frame_records,
        "validation": validation,
    }
    OUTPUT_PATH.write_text(json.dumps(debug, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not validation["all_pass"]:
        raise RuntimeError(f"29B.2.1 validation failed: {validation}")
    unreal.log(
        f"[Underreach29B21] PASS frames={debug['frame_count']} sectors={len(debug['route_sector_ids'])} "
        f"transitions={debug['sector_transition_count']} empty={empty_camera_windows} stale={stale_target_windows}"
    )
    unreal.log(f"[Underreach29B21] Output={OUTPUT_PATH}")


main()
