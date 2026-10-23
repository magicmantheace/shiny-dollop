import hashlib
import json
import sys
from pathlib import Path


UNREAL_PYTHON = Path(__file__).parents[1] / "unreal" / "CrawlPresentation" / "Content" / "Python"
if str(UNREAL_PYTHON) not in sys.path:
    sys.path.insert(0, str(UNREAL_PYTHON))

import camera_planning
from dungeon_environment import (
    ENVIRONMENT_PROTOCOL,
    build_environment_manifest,
    camera_environment_diagnostics,
    resolve_environment_asset_path,
    validate_environment_manifest,
    write_environment_manifest,
)


def test_same_seed_produces_identical_environment_manifest():
    assert build_environment_manifest("dungeon-seed") == build_environment_manifest("dungeon-seed")


def test_different_seeds_produce_cosmetic_variation():
    first = build_environment_manifest("dungeon-seed-a")
    second = build_environment_manifest("dungeon-seed-b")
    assert first["digest"] != second["digest"]
    assert first["props"] != second["props"] or first["lights"] != second["lights"]


def test_combat_safe_zone_is_clear_of_props():
    manifest = build_environment_manifest("safe-zone")
    safe = manifest["combat_safe_zone_bounds"]
    for prop in manifest["props"]:
        bounds = prop["bounds"]
        assert bounds["max"]["x"] <= safe["min"]["x"] or bounds["min"]["x"] >= safe["max"]["x"] or bounds["max"]["y"] <= safe["min"]["y"] or bounds["min"]["y"] >= safe["max"]["y"]


def test_required_room_modules_and_doorway_exist():
    ids = {item["id"] for item in build_environment_manifest("modules")["modules"]}
    assert {"floor", "wall_west", "wall_east", "wall_south", "ceiling"}.issubset(ids)
    assert {"doorway_left", "doorway_right", "doorway_lintel"}.issubset(ids)


def test_room_bounds_are_valid_and_large_enough_for_accepted_camera():
    manifest = build_environment_manifest("bounds")
    assert validate_environment_manifest(manifest)
    bounds = manifest["room_bounds"]
    assert bounds["max"]["x"] - bounds["min"]["x"] == 2600.0
    assert bounds["max"]["y"] - bounds["min"]["y"] == 3600.0
    assert bounds["max"]["z"] == 700.0
    modules = {item["id"]: item for item in manifest["modules"]}
    assert modules["floor"]["bounds"]["min"]["y"] == bounds["min"]["y"]
    assert modules["floor"]["bounds"]["max"]["y"] == bounds["max"]["y"]
    assert modules["wall_south"]["bounds"]["min"]["y"] == bounds["min"]["y"]
    assert modules["doorway_left"]["bounds"]["max"]["y"] == bounds["max"]["y"]


def test_camera_forbidden_volumes_are_deterministic():
    first = build_environment_manifest("camera-volumes")
    second = build_environment_manifest("camera-volumes")
    assert first["camera_forbidden_volumes"] == second["camera_forbidden_volumes"]
    assert {item["id"] for item in first["camera_forbidden_volumes"]} >= {"wall_west", "wall_east", "ceiling"}


def test_missing_environment_asset_uses_explicit_fallback():
    slots = {"environment.dungeon.pillar": "/Game/Missing/Pillar.Pillar"}
    existing = {"/Engine/BasicShapes/Cylinder.Cylinder"}
    path, fallback = resolve_environment_asset_path(slots, "environment.dungeon.pillar", existing.__contains__)
    assert fallback is True
    assert path == "/Engine/BasicShapes/Cylinder.Cylinder"


def test_environment_manifest_is_non_authoritative_and_digest_is_deterministic():
    first = build_environment_manifest("authority")
    second = build_environment_manifest("authority")
    assert first["protocol"] == ENVIRONMENT_PROTOCOL
    assert first["authoritative"] is False
    assert first["digest"] == second["digest"]


def test_environment_generation_does_not_mutate_stage_manifest(tmp_path):
    stage_path = tmp_path / "stage.json"
    output_path = tmp_path / "environment.json"
    stage_path.write_text(json.dumps({"presentation_seed": "read-only"}, indent=2), encoding="utf-8")
    before = hashlib.sha256(stage_path.read_bytes()).hexdigest()
    write_environment_manifest(stage_path, output_path)
    assert hashlib.sha256(stage_path.read_bytes()).hexdigest() == before
    assert json.loads(output_path.read_text(encoding="utf-8"))["authoritative"] is False


def test_environment_camera_diagnostics_accept_clear_inside_shot():
    manifest = build_environment_manifest("camera-clear")
    debug = {
        "camera_shots": [{
            "seconds": 0.0,
            "camera_position": {"x": -800.0, "y": -1200.0, "z": 380.0},
            "sampled_target_positions": {"actor": {"x": 0.0, "y": 0.0, "z": 90.0}},
        }]
    }
    result = camera_environment_diagnostics(debug, manifest)
    assert result["all_samples_valid"] is True
    assert result["obstruction_hit_count"] == 0
    assert result["minimum_camera_clearance_cm"] == 320.0


def test_environment_camera_diagnostics_reject_outside_camera():
    manifest = build_environment_manifest("camera-outside")
    debug = {
        "camera_shots": [{
            "seconds": 0.0,
            "camera_position": {"x": 0.0, "y": -1900.0, "z": 380.0},
            "sampled_target_positions": {"actor": {"x": 0.0, "y": 0.0, "z": 90.0}},
        }]
    }
    assert camera_environment_diagnostics(debug, manifest)["all_samples_valid"] is False


def test_camera_planner_respects_configured_dungeon_region():
    manifest = build_environment_manifest("configured-camera")
    camera_planning.configure_environment(manifest)
    try:
        assert camera_planning._inside_wall_geometry({"x": 0.0, "y": -1900.0, "z": 380.0})
        assert not camera_planning._inside_wall_geometry({"x": -800.0, "y": -1200.0, "z": 380.0})
    finally:
        camera_planning.configure_environment(None)
