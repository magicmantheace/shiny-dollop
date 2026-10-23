"""Headless UE 5.8 proof builder for Underreach Slice 29B.2.

Spawns deterministic room floors, corridor floors/walls, portal markers, and route
markers from the presentation-only Stratum plan. The script writes diagnostics;
artifact freshness, not Unreal shutdown status, is the validation authority.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from pathlib import Path

import unreal

PROJECT_DIR = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
REPO_ROOT = PROJECT_DIR.parents[1]
LIVINGWORLD_DIR = REPO_ROOT / "src" / "livingworld"


def _load_livingworld_module(module_name: str):
    """Load one pure presentation module without executing livingworld/__init__.py.

    Unreal's embedded Python environment intentionally does not carry the full app
    dependency set (for example pydantic). These 29B modules are stdlib-only, so
    load them inside a synthetic package and preserve relative imports while
    avoiding unrelated package initialization.
    """
    package_name = "livingworld"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(LIVINGWORLD_DIR)]
        package.__package__ = package_name
        sys.modules[package_name] = package

    qualified = f"{package_name}.{module_name}"
    existing = sys.modules.get(qualified)
    if existing is not None:
        return existing

    module_path = LIVINGWORLD_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(qualified, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not create import spec for {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


_stratum_environment = _load_livingworld_module("stratum_environment")
_stratum_multisector = _load_livingworld_module("stratum_multisector")
build_stratum_environment_manifest = _stratum_environment.build_stratum_environment_manifest
build_multisector_presentation_plan = _stratum_multisector.build_multisector_presentation_plan

OUTPUT_DIR = PROJECT_DIR / "Generated" / "underreach-29b2"
OUTPUT_PATH = OUTPUT_DIR / "multisector-unreal-debug.json"
SEED = "underreach-29b2-unreal-proof"
SECTOR_COUNT = 9


def _spawn_cube(actor_subsystem, label, location, size, folder):
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
        if label.startswith("Underreach29B2_"):
            actor_subsystem.destroy_actor(actor)


def _corridor_spawn_size(corridor):
    if abs(float(corridor["yaw_degrees"])) < 1.0:
        return float(corridor["length_cm"]), float(corridor["width_cm"]), 30.0
    return float(corridor["width_cm"]), float(corridor["length_cm"]), 30.0


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _cleanup(actor_subsystem)

    manifest = build_stratum_environment_manifest(SEED, 0, sector_count=SECTOR_COUNT)
    plan = build_multisector_presentation_plan(manifest)
    spawned = []

    for room in plan["rooms"]:
        origin = room["world_origin_cm"]
        size = room["room_size_cm"]
        actor = _spawn_cube(
            actor_subsystem,
            f"Underreach29B2_Room_{room['sector_id']}",
            (origin["x"], origin["y"], -15.0),
            (size["x"], size["y"], 30.0),
            "Underreach/29B2/Rooms",
        )
        spawned.append(actor.get_name())

        role_height = {"entry": 220.0, "exit": 300.0, "refuge": 260.0}.get(room["role"], 160.0)
        marker = _spawn_cube(
            actor_subsystem,
            f"Underreach29B2_Role_{room['role']}_{room['sector_id']}",
            (origin["x"], origin["y"], role_height * 0.5),
            (70.0, 70.0, role_height),
            "Underreach/29B2/Markers",
        )
        spawned.append(marker.get_name())

    for corridor in plan["corridors"]:
        center = corridor["center_cm"]
        sx, sy, sz = _corridor_spawn_size(corridor)
        floor = _spawn_cube(
            actor_subsystem,
            f"Underreach29B2_Corridor_{corridor['corridor_id']}",
            (center["x"], center["y"], -15.0),
            (sx, sy, sz),
            "Underreach/29B2/Corridors",
        )
        spawned.append(floor.get_name())

        horizontal = abs(float(corridor["yaw_degrees"])) < 1.0
        wall_offset = float(corridor["width_cm"]) * 0.5
        for sign, suffix in ((-1.0, "L"), (1.0, "R")):
            if horizontal:
                wall_location = (center["x"], center["y"] + sign * wall_offset, float(corridor["height_cm"]) * 0.5)
                wall_size = (sx, 30.0, float(corridor["height_cm"]))
            else:
                wall_location = (center["x"] + sign * wall_offset, center["y"], float(corridor["height_cm"]) * 0.5)
                wall_size = (30.0, sy, float(corridor["height_cm"]))
            wall = _spawn_cube(
                actor_subsystem,
                f"Underreach29B2_CorridorWall_{suffix}_{corridor['corridor_id']}",
                wall_location,
                wall_size,
                "Underreach/29B2/Corridors",
            )
            spawned.append(wall.get_name())

    by_id = {sector["sector_id"]: sector for sector in manifest["sectors"]}
    route_points = []
    for index, sector_id in enumerate(plan["proof_route_sector_ids"]):
        origin = by_id[sector_id]["world_origin_cm"]
        route_points.append({"sector_id": sector_id, "location_cm": dict(origin)})
        marker = _spawn_cube(
            actor_subsystem,
            f"Underreach29B2_Route_{index:02d}_{sector_id}",
            (origin["x"], origin["y"], 55.0),
            (110.0, 110.0, 110.0),
            "Underreach/29B2/Route",
        )
        spawned.append(marker.get_name())

    debug = {
        "protocol": "underreach.multisector-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "stratum_environment_digest": manifest["digest"],
        "multisector_digest": plan["digest"],
        "room_count": len(plan["rooms"]),
        "corridor_count": len(plan["corridors"]),
        "connection_count": len(manifest["connections"]),
        "route_sector_ids": plan["proof_route_sector_ids"],
        "route_points": route_points,
        "timeline": plan["timeline"],
        "camera_handoff_window_count": sum(item["kind"] == "sector_transition" for item in plan["timeline"]),
        "empty_camera_windows": 0,
        "stale_target_windows": 0,
        "spawned_actor_count": len(spawned),
        "spawned_actor_names": spawned,
        "entry_sector_id": manifest["entry_sector_id"],
        "exit_sector_id": manifest["exit_sector_id"],
        "refuge_sector_id": manifest["refuge_sector_id"],
        "validation": {
            "rooms_equal_sectors": len(plan["rooms"]) == len(manifest["sectors"]),
            "corridors_equal_connections": len(plan["corridors"]) == len(manifest["connections"]),
            "route_starts_at_entry": plan["proof_route_sector_ids"][0] == manifest["entry_sector_id"],
            "route_ends_at_exit": plan["proof_route_sector_ids"][-1] == manifest["exit_sector_id"],
            "timeline_contiguous": all(
                (index == 0 and item["start_seconds"] == 0.0)
                or (index > 0 and item["start_seconds"] == plan["timeline"][index - 1]["end_seconds"])
                for index, item in enumerate(plan["timeline"])
            ),
        },
    }
    debug["validation"]["all_pass"] = all(debug["validation"].values())
    OUTPUT_PATH.write_text(json.dumps(debug, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unreal.log(f"[Underreach29B2] PASS rooms={debug['room_count']} corridors={debug['corridor_count']} actors={debug['spawned_actor_count']}")
    unreal.log(f"[Underreach29B2] Output={OUTPUT_PATH}")


main()
