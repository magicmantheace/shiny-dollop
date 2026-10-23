"""Headless UE 5.8 presentation proof for Underreach Slice 29C.3.

Consumes canonical tick-by-tick encounter truth generated outside Unreal, replays
actor transforms and Feed focus, and proves the canonical artifact is unchanged.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import unreal

PROJECT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
OUTPUT_DIR = PROJECT_DIR / "Generated" / "underreach-29c3"
CANONICAL_PATH = OUTPUT_DIR / "autonomous-encounter-canonical.json"
DEBUG_PATH = OUTPUT_DIR / "autonomous-encounter-unreal-debug.json"


def _hash_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cleanup(actor_subsystem):
    for actor in list(actor_subsystem.get_all_level_actors()):
        try:
            if actor.get_actor_label().startswith("Underreach29C3_"):
                actor_subsystem.destroy_actor(actor)
        except Exception:
            continue


def _spawn_proxy(actor_subsystem, label, location, scale, tags):
    mesh = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if mesh is None:
        raise RuntimeError("Engine Cube mesh unavailable")
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(float(location[0]), float(location[1]), float(location[2])),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if actor is None:
        raise RuntimeError(f"Could not spawn {label}")
    actor.set_actor_label(label)
    actor.set_folder_path("Underreach/29C3/AutonomousEncounter")
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    component.set_world_scale3d(unreal.Vector(float(scale[0]), float(scale[1]), float(scale[2])))
    actor.tags = [unreal.Name(str(tag)) for tag in tags]
    return actor


def _spawn_camera(actor_subsystem):
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        unreal.Vector(0.0, -700.0, 460.0),
        unreal.Rotator(-18.0, 0.0, 0.0),
        False,
    )
    if actor is None:
        raise RuntimeError("Could not spawn 29C.3 Feed camera")
    actor.set_actor_label("Underreach29C3_FeedCamera")
    actor.set_folder_path("Underreach/29C3/AutonomousEncounter")
    actor.tags = [unreal.Name("underreach_29c3"), unreal.Name("role:feed_camera")]
    return actor


def _error(actor, expected):
    actual = actor.get_actor_location()
    return math.sqrt(
        (actual.x - float(expected[0])) ** 2
        + (actual.y - float(expected[1])) ** 2
        + (actual.z - float(expected[2])) ** 2
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not CANONICAL_PATH.exists():
        raise RuntimeError(f"Canonical 29C.3 artifact missing: {CANONICAL_PATH}")

    file_hash_before = _hash_bytes(CANONICAL_PATH)
    proof = json.loads(CANONICAL_PATH.read_text(encoding="utf-8"))
    if proof.get("protocol") != "underreach.autonomous-encounter-flow.v1" or proof.get("authoritative") is not True:
        raise RuntimeError("29C.3 canonical protocol/authority mismatch")
    presentation = proof.get("presentation") or {}
    if presentation.get("protocol") != "underreach.autonomous-encounter-presentation.v1" or presentation.get("authoritative") is not False:
        raise RuntimeError("29C.3 presentation protocol/authority mismatch")
    if presentation.get("canonical_digest") != proof.get("canonical_digest"):
        raise RuntimeError("29C.3 presentation is not bound to canonical digest")
    if presentation.get("frames") != proof["canonical_truth"].get("frames"):
        raise RuntimeError("29C.3 presentation frames diverged from canonical truth before Unreal")

    truth = proof["canonical_truth"]
    frames = truth["frames"]
    if not frames:
        raise RuntimeError("29C.3 canonical proof contains no frames")

    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _cleanup(actor_subsystem)
    actor_ids = sorted(frames[0]["positions_cm"])
    descenders = set(truth["participant_final"])
    actors = {}
    for actor_id in actor_ids:
        is_descender = actor_id in descenders
        position = frames[0]["positions_cm"][actor_id]
        actors[actor_id] = _spawn_proxy(
            actor_subsystem,
            f"Underreach29C3_{'Descender' if is_descender else 'Monster'}_{actor_id}",
            (position["x"], position["y"], 90.0 if is_descender else 70.0),
            (0.55, 0.55, 1.8) if is_descender else (1.0, 0.9, 1.2),
            [
                "underreach_29c3",
                f"role:{'descender' if is_descender else 'monster'}",
                f"canonical:{proof['canonical_digest']}",
                f"actor:{actor_id}",
            ],
        )
    camera = _spawn_camera(actor_subsystem)

    max_actor_error = 0.0
    max_camera_focus_error = 0.0
    empty_focus_windows = 0
    stale_focus_windows = 0
    attack_frames = 0
    target_frames = 0
    replayed_frames = 0

    for frame in frames:
        positions = frame["positions_cm"]
        for actor_id, position in positions.items():
            z = 90.0 if actor_id in descenders else 70.0
            actors[actor_id].set_actor_location(unreal.Vector(float(position["x"]), float(position["y"]), z), False, False)
            max_actor_error = max(max_actor_error, _error(actors[actor_id], (position["x"], position["y"], z)))

        focus_id = frame.get("feed_focus_actor_id")
        if focus_id is None:
            empty_focus_windows += 1
            continue
        if focus_id not in actors or focus_id not in positions:
            stale_focus_windows += 1
            continue
        focus = positions[focus_id]
        camera_location = (float(focus["x"]) - 420.0, float(focus["y"]) - 520.0, 360.0)
        camera.set_actor_location(unreal.Vector(*camera_location), False, False)
        expected_distance = math.sqrt(420.0 ** 2 + 520.0 ** 2 + (360.0 - (90.0 if focus_id in descenders else 70.0)) ** 2)
        actual_camera = camera.get_actor_location()
        actual_focus = actors[focus_id].get_actor_location()
        actual_distance = math.sqrt(
            (actual_camera.x - actual_focus.x) ** 2
            + (actual_camera.y - actual_focus.y) ** 2
            + (actual_camera.z - actual_focus.z) ** 2
        )
        max_camera_focus_error = max(max_camera_focus_error, abs(actual_distance - expected_distance))
        kinds = {action["kind"] for action in frame.get("actions", [])}
        if "monster_attack" in kinds or "descender_attack" in kinds:
            attack_frames += 1
        if "target_acquired" in kinds:
            target_frames += 1
        replayed_frames += 1

    file_hash_after = _hash_bytes(CANONICAL_PATH)
    validation = {
        "canonical_file_unchanged": file_hash_before == file_hash_after,
        "presentation_non_authoritative": presentation["authoritative"] is False,
        "canonical_digest_exact": presentation["canonical_digest"] == proof["canonical_digest"],
        "frame_count_exact": replayed_frames == len(frames),
        "actor_set_exact": set(actors) == set(actor_ids),
        "actor_motion_exact": max_actor_error <= 0.01,
        "feed_focus_never_empty": empty_focus_windows == 0,
        "feed_focus_never_stale": stale_focus_windows == 0,
        "feed_camera_tracks_focus": max_camera_focus_error <= 0.01,
        "attack_frames_present": attack_frames > 0,
        "target_acquisition_present": target_frames > 0,
        "ledger_identity_exact": presentation["ledger_event_ids"] == [event["id"] for event in truth["ledger_events"]],
        "outcome_exact": presentation["outcome"] == truth["outcome"],
    }
    validation["all_pass"] = all(validation.values())
    debug = {
        "protocol": "underreach.autonomous-encounter-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "canonical_digest": proof["canonical_digest"],
        "canonical_file_sha256_before": file_hash_before,
        "canonical_file_sha256_after": file_hash_after,
        "outcome": truth["outcome"],
        "frame_count": len(frames),
        "replayed_frame_count": replayed_frames,
        "actor_count": len(actors),
        "descender_count": len(descenders),
        "monster_count": len(actors) - len(descenders),
        "attack_frame_count": attack_frames,
        "target_acquisition_frame_count": target_frames,
        "empty_feed_focus_windows": empty_focus_windows,
        "stale_feed_focus_windows": stale_focus_windows,
        "max_actor_location_error_cm": max_actor_error,
        "max_feed_camera_focus_distance_error_cm": max_camera_focus_error,
        "ledger_event_count": len(truth["ledger_events"]),
        "validation": validation,
    }
    DEBUG_PATH.write_text(json.dumps(debug, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not validation["all_pass"]:
        raise RuntimeError(f"29C.3 Unreal autonomous encounter validation failed: {validation}")
    unreal.log(f"[Underreach29C3] PASS outcome={truth['outcome']} frames={len(frames)} actors={len(actors)}")
    unreal.log(f"[Underreach29C3] Output={DEBUG_PATH}")


if __name__ == "__main__":
    main()
