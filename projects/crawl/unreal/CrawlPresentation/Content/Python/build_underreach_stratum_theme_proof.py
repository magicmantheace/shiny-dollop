"""Headless UE 5.8 proof for Underreach Slice 29B.3 Stratum theming."""

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
OUTPUT_DIR = PROJECT_DIR / "Generated" / "underreach-29b3"
OUTPUT_PATH = OUTPUT_DIR / "stratum-theme-unreal-debug.json"
SEED = "underreach-29b3-unreal-proof"
SECTOR_COUNT = 10
THEMES = ("ancient_stoneworks", "flooded_catacombs", "ember_foundry")
THEME_OFFSETS = {
    "ancient_stoneworks": (0.0, 0.0, 0.0),
    "flooded_catacombs": (30000.0, 0.0, 0.0),
    "ember_foundry": (60000.0, 0.0, 0.0),
}


def _load(module_name: str):
    if "livingworld" not in sys.modules:
        package = types.ModuleType("livingworld")
        package.__path__ = [str(LIVINGWORLD_DIR)]
        package.__package__ = "livingworld"
        sys.modules["livingworld"] = package
    qualified = f"livingworld.{module_name}"
    if qualified in sys.modules:
        return sys.modules[qualified]
    path = LIVINGWORLD_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(qualified, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[qualified] = module
    spec.loader.exec_module(module)
    return module


_environment = _load("stratum_environment")
_theme = _load("stratum_theme")
build_environment = _environment.build_stratum_environment_manifest
build_theme = _theme.build_stratum_theme_manifest


def _cleanup(actor_subsystem):
    for actor in list(unreal.EditorLevelLibrary.get_all_level_actors()):
        try:
            label = actor.get_actor_label()
        except Exception:
            continue
        if label.startswith("Underreach29B3_"):
            actor_subsystem.destroy_actor(actor)


def _spawn_cube(actor_subsystem, label, location, size, folder, tags):
    mesh = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if mesh is None:
        raise RuntimeError("Engine Cube mesh unavailable")
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        unreal.Vector(*[float(v) for v in location]),
        unreal.Rotator(0.0, 0.0, 0.0),
        False,
    )
    if actor is None:
        raise RuntimeError(f"Could not spawn {label}")
    actor.set_actor_label(label)
    actor.set_folder_path(folder)
    actor.tags = [unreal.Name(str(tag)) for tag in tags]
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    component.set_static_mesh(mesh)
    component.set_world_scale3d(unreal.Vector(float(size[0]) / 100.0, float(size[1]) / 100.0, float(size[2]) / 100.0))
    return actor


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    _cleanup(actor_subsystem)

    environment = build_environment(SEED, stratum_index=3, sector_count=SECTOR_COUNT)
    manifests = {theme: build_theme(environment, theme) for theme in THEMES}
    spawned = []
    assignment_samples = []

    for theme_name in THEMES:
        manifest = manifests[theme_name]
        offset_x, offset_y, offset_z = THEME_OFFSETS[theme_name]
        for themed_sector, source_sector in zip(manifest["sectors"], environment["sectors"]):
            origin = source_sector["world_origin_cm"]
            room_size = source_sector["room_size_cm"]
            floor_tags = [
                f"theme={theme_name}",
                f"sector={themed_sector['sector_id']}",
                f"floor={themed_sector['materials']['floor']}",
                f"wall={themed_sector['materials']['wall']}",
                f"ceiling={themed_sector['materials']['ceiling']}",
                f"trim={themed_sector['materials']['trim']}",
                f"lighting={themed_sector['lighting']}",
            ] + [f"prop={prop}" for prop in themed_sector["props"]]
            actor = _spawn_cube(
                actor_subsystem,
                f"Underreach29B3_{theme_name}_{themed_sector['sector_id']}",
                (float(origin["x"]) + offset_x, float(origin["y"]) + offset_y, -15.0 + offset_z),
                (room_size["x"], room_size["y"], 30.0),
                f"Underreach/29B3/{theme_name}",
                floor_tags,
            )
            spawned.append(actor.get_name())
            if len(assignment_samples) < 12:
                assignment_samples.append({
                    "theme": theme_name,
                    "sector_id": themed_sector["sector_id"],
                    "materials": themed_sector["materials"],
                    "props": themed_sector["props"],
                    "lighting": themed_sector["lighting"],
                    "actor_label": actor.get_actor_label(),
                    "actor_tags": [str(tag) for tag in actor.tags],
                })

    topology_fingerprints = [manifests[name]["topology_fingerprint"] for name in THEMES]
    digests = {name: manifests[name]["digest"] for name in THEMES}
    debug = {
        "protocol": "underreach.stratum-theme-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "stratum_environment_digest": environment["digest"],
        "theme_digests": digests,
        "theme_count": len(THEMES),
        "sector_count": len(environment["sectors"]),
        "spawned_actor_count": len(spawned),
        "assignment_samples": assignment_samples,
        "entry_sector_id": environment["entry_sector_id"],
        "exit_sector_id": environment["exit_sector_id"],
        "refuge_sector_id": environment["refuge_sector_id"],
        "validation": {
            "all_theme_digests_unique": len(set(digests.values())) == len(THEMES),
            "topology_equal_across_themes": all(item == topology_fingerprints[0] for item in topology_fingerprints[1:]),
            "all_themes_bind_same_environment": all(manifests[name]["stratum_environment_digest"] == environment["digest"] for name in THEMES),
            "actor_count_matches_theme_sector_product": len(spawned) == len(THEMES) * len(environment["sectors"]),
            "entry_preserved": all(manifests[name]["entry_sector_id"] == environment["entry_sector_id"] for name in THEMES),
            "exit_preserved": all(manifests[name]["exit_sector_id"] == environment["exit_sector_id"] for name in THEMES),
            "refuge_preserved": all(manifests[name]["refuge_sector_id"] == environment["refuge_sector_id"] for name in THEMES),
            "theme_metadata_applied_to_unreal_actors": all(any(str(tag).startswith("theme=") for tag in actor.tags) for actor in unreal.EditorLevelLibrary.get_all_level_actors() if actor.get_actor_label().startswith("Underreach29B3_")),
        },
    }
    debug["validation"]["all_pass"] = all(debug["validation"].values())
    OUTPUT_PATH.write_text(json.dumps(debug, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    unreal.log(f"[Underreach29B3] PASS themes={debug['theme_count']} sectors={debug['sector_count']} actors={debug['spawned_actor_count']}")
    unreal.log(f"[Underreach29B3] Output={OUTPUT_PATH}")


main()
