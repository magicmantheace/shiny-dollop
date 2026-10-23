"""Headless UE 5.8 consumer proof for Underreach Slice 29D.1.

Unreal consumes canonical 29C.3 truth plus the non-authoritative 29D.1 schedule.
It applies actor position/facing, semantic action tags, and action-aware Feed camera
placement without running or changing simulation state.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import unreal

PROJECT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
OUTPUT_DIR = PROJECT_DIR / "Generated" / "underreach-29d1"
PROOF_PATH = OUTPUT_DIR / "combat-presentation-proof.json"
DEBUG_PATH = OUTPUT_DIR / "combat-presentation-unreal-debug.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _cleanup(actor_subsystem):
    for actor in list(actor_subsystem.get_all_level_actors()):
        try:
            if actor.get_actor_label().startswith("Underreach29D1_"):
                actor_subsystem.destroy_actor(actor)
        except Exception:
            continue


def _spawn_proxy(actor_subsystem, label: str, position: dict, scale):
    mesh = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if mesh is None:
        raise RuntimeError("Engine Cube mesh unavailable")
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(float(position["x"]), float(position["y"]), 90.0),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if actor is None:
        raise RuntimeError(f"Could not spawn {label}")
    actor.set_actor_label(label)
    actor.set_folder_path("Underreach/29D1/CombatPresentation")
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    component.set_world_scale3d(unreal.Vector(float(scale[0]), float(scale[1]), float(scale[2])))
    return actor


def _distance(actual, expected) -> float:
    return math.sqrt(
        (actual.x - float(expected["x"])) ** 2
        + (actual.y - float(expected["y"])) ** 2
        + (actual.z - 90.0) ** 2
    )


def _camera_location(shot: str, actor_pos: dict, target_pos: dict | None):
    if shot == "combat_pair" and target_pos is not None:
        cx = (float(actor_pos["x"]) + float(target_pos["x"])) * 0.5
        cy = (float(actor_pos["y"]) + float(target_pos["y"])) * 0.5
        return unreal.Vector(cx - 420.0, cy - 420.0, 300.0)
    if shot == "threat_reveal":
        return unreal.Vector(float(actor_pos["x"]) - 320.0, float(actor_pos["y"]) + 360.0, 250.0)
    if shot == "aftermath_hold":
        return unreal.Vector(float(actor_pos["x"]) - 360.0, float(actor_pos["y"]) - 280.0, 240.0)
    if shot == "wide_context":
        return unreal.Vector(float(actor_pos["x"]) - 620.0, float(actor_pos["y"]) - 620.0, 430.0)
    return unreal.Vector(float(actor_pos["x"]) - 360.0, float(actor_pos["y"]) - 360.0, 260.0)


def _yaw_rotator(yaw_degrees: float):
    """Build a yaw-only Rotator without relying on UE Python positional ordering."""
    rotation = unreal.Rotator()
    rotation.pitch = 0.0
    rotation.yaw = float(yaw_degrees)
    rotation.roll = 0.0
    return rotation


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    if not PROOF_PATH.exists():
        raise RuntimeError(f"29D.1 proof missing: {PROOF_PATH}")

    file_hash_before = _sha(PROOF_PATH)
    proof = json.loads(PROOF_PATH.read_text(encoding="utf-8"))
    source = proof["source"]
    presentation = proof["presentation"]
    if source.get("protocol") != "underreach.autonomous-encounter-flow.v1" or source.get("authoritative") is not True:
        raise RuntimeError("29D.1 source canonical contract invalid")
    if presentation.get("protocol") != "underreach.combat-presentation.v1" or presentation.get("authoritative") is not False:
        raise RuntimeError("29D.1 presentation contract invalid")
    if presentation.get("source_canonical_digest") != source.get("canonical_digest"):
        raise RuntimeError("29D.1 presentation/source canonical binding mismatch")

    frames = source["canonical_truth"]["frames"]
    actor_ids = sorted({actor_id for frame in frames for actor_id in frame["positions_cm"]})
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _cleanup(actor_subsystem)

    actors = {}
    first_positions = frames[0]["positions_cm"]
    for actor_id in actor_ids:
        position = first_positions.get(actor_id)
        if position is None:
            position = next(frame["positions_cm"][actor_id] for frame in frames if actor_id in frame["positions_cm"])
        is_descender = actor_id.startswith("descender_")
        actor = _spawn_proxy(
            actor_subsystem,
            f"Underreach29D1_{'Descender' if is_descender else 'Monster'}_{actor_id}",
            position,
            (0.55, 0.55, 1.8) if is_descender else (1.0, 0.8, 1.3),
        )
        actor.tags = [unreal.Name("underreach_29d1"), unreal.Name(f"actor:{actor_id}")]
        actors[actor_id] = actor

    camera = actor_subsystem.spawn_actor_from_class(
        unreal.CameraActor,
        unreal.Vector(-500.0, -500.0, 300.0),
        unreal.Rotator(-12.0, 45.0, 0.0),
        False,
    )
    if camera is None:
        raise RuntimeError("Could not spawn 29D.1 Feed camera")
    camera.set_actor_label("Underreach29D1_FeedCamera")
    camera.set_folder_path("Underreach/29D1/CombatPresentation")

    max_actor_error = 0.0
    max_yaw_error = 0.0
    stale_focus = 0
    empty_focus = 0
    applied_slots = 0
    attack_windows = 0
    reaction_windows = 0
    death_windows = 0
    camera_shots = set()

    for window in presentation["windows"]:
        frame = frames[int(window["source_frame_index"])]
        positions = frame["positions_cm"]
        actor_id = window["actor_id"]
        actor = actors.get(actor_id)
        expected = positions.get(actor_id)
        if actor is None or expected is None:
            raise RuntimeError(f"29D.1 window references actor without canonical position: {actor_id}")

        actor.set_actor_location(unreal.Vector(float(expected["x"]), float(expected["y"]), 90.0), False, False)
        actual = actor.get_actor_location()
        max_actor_error = max(max_actor_error, _distance(actual, expected))

        yaw = window.get("facing_yaw_degrees")
        if yaw is not None:
            actor.set_actor_rotation(_yaw_rotator(float(yaw)), False)
            rotation = actor.get_actor_rotation()
            yaw_error = abs(((float(rotation.yaw) - float(yaw) + 180.0) % 360.0) - 180.0)
            max_yaw_error = max(max_yaw_error, yaw_error)

        slot = window.get("animation_slot")
        if slot:
            applied_slots += 1
            actor.tags = [
                unreal.Name("underreach_29d1"),
                unreal.Name(f"actor:{actor_id}"),
                unreal.Name(f"semantic_slot:{slot}"),
                unreal.Name(f"presentation_kind:{window['presentation_kind']}"),
            ]

        kind = window["presentation_kind"]
        attack_windows += int(kind == "attack")
        reaction_windows += int(kind == "hit_reaction")
        death_windows += int(kind == "death")

        focus_id = window.get("feed_focus_actor_id")
        if focus_id is None:
            empty_focus += 1
        elif focus_id not in positions or focus_id not in actors:
            stale_focus += 1

        target_id = window.get("target_id")
        target_pos = positions.get(target_id) if target_id else None
        shot = window["camera_shot"]
        camera_shots.add(shot)
        camera.set_actor_location(_camera_location(shot, expected, target_pos), False, False)

    file_hash_after = _sha(PROOF_PATH)
    validation = {
        "proof_file_unchanged": file_hash_before == file_hash_after,
        "source_authoritative": source["authoritative"] is True,
        "presentation_non_authoritative": presentation["authoritative"] is False,
        "canonical_binding_exact": presentation["source_canonical_digest"] == source["canonical_digest"],
        "all_windows_applied": len(presentation["windows"]) > 0,
        "actor_positions_exact": max_actor_error <= 0.01,
        "facing_exact": max_yaw_error <= 0.01,
        "feed_focus_valid": empty_focus == 0 and stale_focus == 0,
        "attack_presented": attack_windows > 0,
        "reaction_presented": reaction_windows > 0,
        "camera_variety_present": len(camera_shots) >= 2,
    }
    validation["all_pass"] = all(validation.values())

    debug = {
        "protocol": "underreach.combat-presentation-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "source_canonical_digest": source["canonical_digest"],
        "presentation_digest": presentation["digest"],
        "outcome": source["canonical_truth"]["outcome"],
        "proof_file_sha256_before": file_hash_before,
        "proof_file_sha256_after": file_hash_after,
        "actor_count": len(actors),
        "window_count": len(presentation["windows"]),
        "attack_window_count": attack_windows,
        "reaction_window_count": reaction_windows,
        "death_window_count": death_windows,
        "semantic_slots_applied": applied_slots,
        "camera_shots": sorted(camera_shots),
        "empty_feed_focus_windows": empty_focus,
        "stale_feed_focus_windows": stale_focus,
        "max_actor_location_error_cm": max_actor_error,
        "max_facing_yaw_error_degrees": max_yaw_error,
        "validation": validation,
    }
    DEBUG_PATH.write_text(json.dumps(debug, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not validation["all_pass"]:
        raise RuntimeError(f"29D.1 Unreal combat presentation validation failed: {validation}")
    unreal.log(
        f"[Underreach29D1] PASS windows={debug['window_count']} attacks={attack_windows} "
        f"reactions={reaction_windows} shots={len(camera_shots)}"
    )
    unreal.log(f"[Underreach29D1] Output={DEBUG_PATH}")


main()
