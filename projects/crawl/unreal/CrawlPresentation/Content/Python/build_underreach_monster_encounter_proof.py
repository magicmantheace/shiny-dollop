"""Headless UE 5.8 proof builder for Underreach Slice 29C.1 monster encounters."""

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
OUTPUT_DIR = PROJECT_DIR / "Generated" / "underreach-29c1"
OUTPUT_PATH = OUTPUT_DIR / "monster-encounter-unreal-debug.json"
SEED = "underreach-29c1-unreal-proof"
SECTOR_COUNT = 12
THEME = "ancient_stoneworks"


def _load(module_name: str):
    package_name = "livingworld"
    if package_name not in sys.modules:
        package = types.ModuleType(package_name)
        package.__path__ = [str(LIVINGWORLD_DIR)]
        package.__package__ = package_name
        sys.modules[package_name] = package
    qualified = f"{package_name}.{module_name}"
    if qualified in sys.modules:
        return sys.modules[qualified]
    path = LIVINGWORLD_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


_env = _load("stratum_environment")
_theme = _load("stratum_theme")
_encounters = _load("monster_encounters")


def _cleanup(actor_subsystem):
    for actor in list(actor_subsystem.get_all_level_actors()):
        try:
            if actor.get_actor_label().startswith("Underreach29C1_"):
                actor_subsystem.destroy_actor(actor)
        except Exception:
            continue


def _spawn_proxy(actor_subsystem, label, location, size, tags):
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
    actor.set_folder_path("Underreach/29C1/Monsters")
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    component.set_world_scale3d(unreal.Vector(float(size["x"]) / 100.0, float(size["y"]) / 100.0, float(size["z"]) / 100.0))
    actor.tags = [unreal.Name(str(tag)) for tag in tags]
    return actor


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _cleanup(actor_subsystem)

    environment = _env.build_stratum_environment_manifest(SEED, 0, sector_count=SECTOR_COUNT, theme=THEME)
    theme_manifest = _theme.build_stratum_theme_manifest(environment, THEME)
    encounter_plan = _encounters.build_encounter_plan(environment, theme_manifest)
    by_sector = {sector["sector_id"]: sector for sector in environment["sectors"]}

    spawned = []
    safe_sector_spawn_count = 0
    max_spawn_clearance_ratio = 0.0
    for encounter in encounter_plan["encounters"]:
        sector = by_sector[encounter["sector_id"]]
        origin = sector["world_origin_cm"]
        if sector["role"] in _encounters.SAFE_SECTOR_ROLES:
            safe_sector_spawn_count += len(encounter["members"])
        for member in encounter["members"]:
            definition = _encounters.MONSTER_DEFINITIONS[member["monster_id"]]
            offset = member["local_offset_cm"]
            location = (
                float(origin["x"]) + float(offset["x"]),
                float(origin["y"]) + float(offset["y"]),
                float(definition["proxy_size_cm"]["z"]) * 0.5,
            )
            actor = _spawn_proxy(
                actor_subsystem,
                f"Underreach29C1_{member['member_id']}_{member['monster_id']}",
                location,
                definition["proxy_size_cm"],
                [
                    "underreach_29c1",
                    f"monster:{member['monster_id']}",
                    f"sector:{encounter['sector_id']}",
                    f"encounter:{encounter['encounter_id']}",
                    f"theme:{encounter['theme']}",
                ],
            )
            actual = actor.get_actor_location()
            error = ((actual.x - location[0]) ** 2 + (actual.y - location[1]) ** 2 + (actual.z - location[2]) ** 2) ** 0.5
            clearance = sector["combat_clearance_cm"]
            half_x = float(clearance["x"]) * 0.5
            half_y = float(clearance["y"]) * 0.5
            ratio = max(abs(float(offset["x"])) / half_x, abs(float(offset["y"])) / half_y)
            max_spawn_clearance_ratio = max(max_spawn_clearance_ratio, ratio)
            spawned.append({
                "actor_name": actor.get_name(),
                "member_id": member["member_id"],
                "monster_id": member["monster_id"],
                "sector_id": encounter["sector_id"],
                "location_error_cm": error,
            })

    topology_preserved = encounter_plan["topology_fingerprint"] == {
        "sector_ids": [sector["sector_id"] for sector in environment["sectors"]],
        "connections": [dict(connection) for connection in environment["connections"]],
        "world_origins_cm": [dict(sector["world_origin_cm"]) for sector in environment["sectors"]],
    }
    max_actor_error = max((item["location_error_cm"] for item in spawned), default=0.0)
    validation = {
        "topology_preserved": topology_preserved,
        "safe_sectors_empty": safe_sector_spawn_count == 0,
        "all_members_spawned": len(spawned) == sum(len(item["members"]) for item in encounter_plan["encounters"]),
        "all_actor_locations_match": max_actor_error <= 0.01,
        "all_spawns_inside_combat_clearance": max_spawn_clearance_ratio <= 1.0,
        "encounter_plan_non_authoritative": encounter_plan["authoritative"] is False,
        "promotion_required_for_canonical_combat": encounter_plan["promotion_required_for_canonical_combat"] is True,
    }
    validation["all_pass"] = all(validation.values())

    debug = {
        "protocol": "underreach.monster-encounter-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "stratum_environment_digest": environment["digest"],
        "theme_digest": theme_manifest["digest"],
        "encounter_plan_digest": encounter_plan["digest"],
        "monster_definition_digest": encounter_plan["monster_definition_digest"],
        "sector_count": len(environment["sectors"]),
        "encounter_count": len(encounter_plan["encounters"]),
        "monster_count": len(spawned),
        "monster_archetype_count": len({item["monster_id"] for item in spawned}),
        "safe_sector_spawn_count": safe_sector_spawn_count,
        "max_actor_location_error_cm": max_actor_error,
        "max_spawn_clearance_ratio": max_spawn_clearance_ratio,
        "entry_sector_id": environment["entry_sector_id"],
        "exit_sector_id": environment["exit_sector_id"],
        "refuge_sector_id": environment["refuge_sector_id"],
        "spawned": spawned,
        "validation": validation,
    }
    OUTPUT_PATH.write_text(json.dumps(debug, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unreal.log(f"[Underreach29C1] PASS encounters={debug['encounter_count']} monsters={debug['monster_count']} archetypes={debug['monster_archetype_count']}")
    unreal.log(f"[Underreach29C1] Output={OUTPUT_PATH}")


main()
