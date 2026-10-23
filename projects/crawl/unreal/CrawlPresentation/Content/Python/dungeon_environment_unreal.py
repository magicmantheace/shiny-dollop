"""UE 5.8 spawning and validation for the deterministic dungeon manifest."""

from __future__ import annotations

import json
import os
from pathlib import Path

import unreal

from dungeon_environment import (
    ENVIRONMENT_PROTOCOL,
    camera_environment_diagnostics,
    resolve_environment_asset_path,
    validate_environment_manifest,
)


FALLBACK_MESHES = {
    "floor": "/Engine/BasicShapes/Cube.Cube",
    "wall": "/Engine/BasicShapes/Cube.Cube",
    "ceiling": "/Engine/BasicShapes/Cube.Cube",
    "pillar": "/Engine/BasicShapes/Cylinder.Cylinder",
    "arch": "/Engine/BasicShapes/Cube.Cube",
    "doorway": "/Engine/BasicShapes/Cube.Cube",
    "crate": "/Engine/BasicShapes/Cube.Cube",
    "barrel": "/Engine/BasicShapes/Cylinder.Cylinder",
    "rubble": "/Engine/BasicShapes/Sphere.Sphere",
    "torch": "/Engine/BasicShapes/Cylinder.Cylinder",
}


def load_environment_manifest():
    configured = os.environ.get("CRAWL_ENVIRONMENT_MANIFEST")
    if not configured:
        raise RuntimeError("CRAWL_ENVIRONMENT_MANIFEST is required for the dungeon build")
    path = Path(configured).resolve()
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_environment_manifest(payload)
    if payload.get("protocol") != ENVIRONMENT_PROTOCOL:
        raise RuntimeError(f"Unsupported environment protocol: {payload.get('protocol')}")
    return path, payload


def _slot_asset(slots, slot, profile, diagnostics):
    requested = slots.get(slot)
    resolved, fallback = resolve_environment_asset_path(
        slots,
        slot,
        lambda path: unreal.load_asset(path) is not None,
    )
    asset = unreal.load_asset(resolved)
    if asset is None:
        raise RuntimeError(f"Could not load environment slot or fallback: {slot} -> {resolved}")
    if fallback:
        if requested:
            diagnostics["missing_asset_slots"].add(slot)
        diagnostics["fallback_asset_slots"].add(slot)
    else:
        diagnostics["resolved_asset_slots"].add(slot)
    return asset, resolved, fallback


def _import_texture(source_path, destination_name):
    destination_path = "/Game/CrawlGenerated/DungeonMaterials"
    object_path = f"{destination_path}/{destination_name}.{destination_name}"
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source_path))
    task.set_editor_property("destination_path", destination_path)
    task.set_editor_property("destination_name", destination_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = unreal.load_asset(object_path)
    if texture is None:
        raise RuntimeError(f"Dungeon texture import failed: {source_path} -> {object_path}")
    try:
        texture.set_editor_property("srgb", True)
    except Exception:
        pass
    unreal.EditorAssetLibrary.save_loaded_asset(texture, False)
    return texture


def _create_surface_material(name, texture, tiling, roughness, tint):
    package_path = "/Game/CrawlGenerated/DungeonMaterials"
    object_path = f"{package_path}/{name}.{name}"
    existing = unreal.load_asset(object_path)
    if existing is not None:
        unreal.EditorAssetLibrary.delete_asset(f"{package_path}/{name}")
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        name,
        package_path,
        unreal.Material,
        unreal.MaterialFactoryNew(),
    )
    if material is None:
        raise RuntimeError(f"Could not create dungeon material {name}")
    texture_node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureSample, -160, 0
    )
    texture_node.set_editor_property("texture", texture)
    coordinate = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionTextureCoordinate, -420, 0
    )
    coordinate.set_editor_property("u_tiling", float(tiling))
    coordinate.set_editor_property("v_tiling", float(tiling))
    unreal.MaterialEditingLibrary.connect_material_expressions(coordinate, "", texture_node, "UVs")
    tint_node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, -160, 80
    )
    tint_node.set_editor_property("constant", unreal.LinearColor(float(tint[0]), float(tint[1]), float(tint[2]), 1.0))
    multiply = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 80, 0
    )
    unreal.MaterialEditingLibrary.connect_material_expressions(texture_node, "RGB", multiply, "A")
    unreal.MaterialEditingLibrary.connect_material_expressions(tint_node, "", multiply, "B")
    unreal.MaterialEditingLibrary.connect_material_property(multiply, "", unreal.MaterialProperty.MP_BASE_COLOR)
    rough = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, -160, 180
    )
    rough.set_editor_property("r", float(roughness))
    unreal.MaterialEditingLibrary.connect_material_property(
        rough, "", unreal.MaterialProperty.MP_ROUGHNESS
    )
    unreal.MaterialEditingLibrary.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material, False)
    return material


def _prepare_materials(environment_path, manifest):
    project_dir = Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))
    wall_source = project_dir / manifest["source_textures"]["wall"]
    floor_source = project_dir / manifest["source_textures"]["floor"]
    if not wall_source.is_file() or not floor_source.is_file():
        raise RuntimeError(f"Dungeon source textures missing beside {environment_path}: {wall_source}, {floor_source}")
    wall_texture = _import_texture(wall_source, "T_DungeonWallStone")
    floor_texture = _import_texture(floor_source, "T_DungeonFloorFlagstone")
    return {
        "wall": _create_surface_material("M_DungeonWallStone", wall_texture, 2.0, 0.92, (0.62, 0.49, 0.36)),
        "floor": _create_surface_material("M_DungeonFloorFlagstone", floor_texture, 4.0, 0.96, (0.52, 0.45, 0.38)),
        "prop": _create_surface_material("M_DungeonPropStone", wall_texture, 1.0, 0.94, (0.48, 0.38, 0.28)),
    }


def _vector(payload):
    return unreal.Vector(float(payload["x"]), float(payload["y"]), float(payload["z"]))


def _rotator(payload):
    return unreal.Rotator(float(payload.get("pitch", 0.0)), float(payload.get("yaw", 0.0)), float(payload.get("roll", 0.0)))


def _mesh_profile(slot):
    return str(slot).rsplit(".", 1)[-1]


def _spawn_manifest_mesh(actor_subsystem, payload, slots, materials, diagnostics, folder):
    transform = payload["transform"]
    profile = _mesh_profile(payload["asset_slot"])
    mesh, resolved_path, fallback = _slot_asset(slots, payload["asset_slot"], profile, diagnostics)
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.StaticMeshActor,
        _vector(transform["location"]),
        _rotator(transform["rotation"]),
        False,
    )
    if actor is None:
        raise RuntimeError(f"Could not spawn dungeon module {payload['id']}")
    actor.set_actor_label(f"CrawlDungeon_{payload['id']}")
    actor.set_folder_path(folder)
    component = actor.get_component_by_class(unreal.StaticMeshComponent)
    if component is None:
        raise RuntimeError(f"Dungeon module has no StaticMeshComponent: {payload['id']}")
    component.set_static_mesh(mesh)
    size = transform["size"]
    component.set_world_scale3d(unreal.Vector(float(size["x"]) / 100.0, float(size["y"]) / 100.0, float(size["z"]) / 100.0))
    component.set_material(0, materials[payload.get("material_profile", "wall")])
    try:
        component.set_collision_enabled(unreal.CollisionEnabled.NO_COLLISION)
    except Exception:
        pass
    component.set_editor_property("cast_shadow", True)
    diagnostics["spawned"].append({
        "id": payload["id"],
        "asset_slot": payload["asset_slot"],
        "resolved_asset": resolved_path,
        "fallback": fallback,
        "actor": actor.get_name(),
    })
    return actor


def _spawn_lighting(actor_subsystem, lights, slots, materials, diagnostics):
    for light in lights:
        location = _vector(light["location"])
        if light["type"] == "sky":
            actor = actor_subsystem.spawn_actor_from_class(unreal.SkyLight, location, unreal.Rotator(), False)
            component = actor.get_component_by_class(unreal.SkyLightComponent)
            component.set_editor_property("intensity", float(light["intensity"]))
            color = light["color"]
            component.set_editor_property("light_color", unreal.Color(int(color["r"]), int(color["g"]), int(color["b"]), 255))
        else:
            actor = actor_subsystem.spawn_actor_from_class(unreal.PointLight, location, unreal.Rotator(), False)
            component = actor.get_component_by_class(unreal.PointLightComponent)
            component.set_editor_property("intensity", float(light["intensity"]))
            component.set_editor_property("attenuation_radius", float(light["attenuation_radius"]))
            component.set_editor_property("use_temperature", True)
            component.set_editor_property("temperature", 3200.0)
            color = light["color"]
            component.set_editor_property("light_color", unreal.Color(int(color["r"]), int(color["g"]), int(color["b"]), 255))
            fixture = {
                "id": light["id"] + "_fixture",
                "asset_slot": light["asset_slot"],
                "transform": {
                    "location": {"x": light["location"]["x"], "y": light["location"]["y"], "z": light["location"]["z"] - 90.0},
                    "rotation": {"roll": 0.0, "pitch": 0.0, "yaw": 0.0},
                    "size": {"x": 16.0, "y": 16.0, "z": 100.0},
                },
                "material_profile": "prop",
            }
            _spawn_manifest_mesh(actor_subsystem, fixture, slots, materials, diagnostics, "Crawl/Dungeon/Lighting")
        actor.set_actor_label(f"CrawlDungeon_{light['id']}")
        actor.set_folder_path("Crawl/Dungeon/Lighting")
        diagnostics["spawned_lights"].append(actor.get_name())


def spawn_dungeon_environment(actor_subsystem, environment_path, manifest, slots):
    materials = _prepare_materials(environment_path, manifest)
    diagnostics = {
        "resolved_asset_slots": set(),
        "missing_asset_slots": set(),
        "fallback_asset_slots": set(),
        "spawned": [],
        "spawned_lights": [],
    }
    for module in manifest["modules"]:
        _spawn_manifest_mesh(actor_subsystem, module, slots, materials, diagnostics, "Crawl/Dungeon/Modules")
    for prop in manifest["props"]:
        _spawn_manifest_mesh(actor_subsystem, prop, slots, materials, diagnostics, "Crawl/Dungeon/Props")
    _spawn_lighting(actor_subsystem, manifest["lights"], slots, materials, diagnostics)
    diagnostics["resolved_asset_slots"] = sorted(diagnostics["resolved_asset_slots"])
    diagnostics["missing_asset_slots"] = sorted(diagnostics["missing_asset_slots"])
    diagnostics["fallback_asset_slots"] = sorted(diagnostics["fallback_asset_slots"])
    return diagnostics


def finalize_environment_debug(manifest, spawn_debug, camera_debug, stage_manifest, death_debug):
    camera_validation = camera_environment_diagnostics(camera_debug, manifest)
    if not camera_validation["all_samples_valid"]:
        invalid = [sample for sample in camera_validation["samples"] if not sample["valid"]]
        raise RuntimeError(f"Dungeon camera obstruction/containment validation failed: {invalid[:3]}")
    floor_z = float(manifest["room_bounds"]["min"]["z"])
    terminal_by_actor = {actor["actor_id"]: actor for actor in death_debug.get("actors", [])}
    actor_floor_checks = []
    for actor in stage_manifest.get("actors", []):
        actor_id = actor["actor_id"]
        terminal = terminal_by_actor.get(actor_id)
        if terminal:
            bones = terminal["settled_pose"]["bones"]
            lowest = min(float(bones[bone]["location"]["z"]) for bone in ("foot_l", "foot_r", "hand_l", "hand_r"))
            actor_floor_checks.append({
                "actor_id": actor_id,
                "mode": "settled_corpse_bones",
                "floor_z": floor_z,
                "lowest_contact_bone_z": lowest,
                "clearance_cm": lowest - floor_z,
                "valid": -5.0 <= lowest - floor_z <= 25.0,
            })
        else:
            root_z = float(actor["initial_transform"]["z"])
            actor_floor_checks.append({
                "actor_id": actor_id,
                "mode": "standing_presentation_root",
                "floor_z": floor_z,
                "presentation_root_z": root_z,
                "expected_root_height_cm": 90.0,
                "clearance_error_cm": abs(root_z - floor_z - 90.0),
                "valid": abs(root_z - floor_z - 90.0) <= 2.0,
            })
    if not all(item["valid"] for item in actor_floor_checks):
        raise RuntimeError(f"Dungeon actor-floor validation failed: {actor_floor_checks}")
    return {
        "protocol": manifest["protocol"],
        "authoritative": False,
        "presentation_seed": manifest["presentation_seed"],
        "room_id": manifest["room_id"],
        "archetype": manifest["archetype"],
        "room_bounds": manifest["room_bounds"],
        "combat_safe_zone_bounds": manifest["combat_safe_zone_bounds"],
        "environment_digest": manifest["digest"],
        "module_count": len(manifest["modules"]),
        "prop_count": len(manifest["props"]),
        "light_count": len(manifest["lights"]),
        "resolved_asset_slots": spawn_debug["resolved_asset_slots"],
        "missing_asset_slots": spawn_debug["missing_asset_slots"],
        "fallback_asset_slots": spawn_debug["fallback_asset_slots"],
        "fallback_use_count": sum(bool(item["fallback"]) for item in spawn_debug["spawned"]),
        "spawned_modules_and_props": spawn_debug["spawned"],
        "camera_forbidden_volumes": manifest["camera_forbidden_volumes"],
        "collision_critical_modules": [item["id"] for item in manifest["modules"] if item["collision_critical"]],
        "actor_floor_checks": actor_floor_checks,
        "camera_obstruction_checks": camera_validation,
    }
