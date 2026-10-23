"""Unreal offscreen render proof for Underreach Slice 29E.6.

Stages accepted 29E.4 character materials and 29E.5 real equipment on the
repository-backed Human/Dwarf skeletal meshes, lights them with a deterministic
studio rig, and exports four real PNG proof frames through SceneCapture2D.
Everything in this file is presentation-only and disposable.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import unreal


SWORD_GRIP_LOCAL_ANCHOR_CM = (0.0, 0.0, -8.5)
ALL_BODY_MESHES = {
    "human_average": "/Game/Underreach29A1/Characters/SK_UnderreachHuman.SK_UnderreachHuman",
    "human_short_heavy": "/Game/Underreach29A1/Characters/SK_UnderreachHumanShortHeavy.SK_UnderreachHumanShortHeavy",
    "human_tall_thin": "/Game/Underreach29A1/Characters/SK_UnderreachHumanTallThin.SK_UnderreachHumanTallThin",
    "dwarf_average": "/Game/Underreach29A1/Characters/SK_UnderreachDwarf.SK_UnderreachDwarf",
    "dwarf_heavy": "/Game/Underreach29A1/Characters/SK_UnderreachDwarfHeavy.SK_UnderreachDwarfHeavy",
    "dwarf_alt": "/Game/Underreach29A1/Characters/SK_UnderreachDwarfAlt.SK_UnderreachDwarfAlt",
}
STAGE_ORIGIN = (100000.0, 100000.0, 1000.0)
CHARACTER_HALF_WIDTH_CM = 70.0
CHARACTER_HALF_HEIGHT_CM = 112.5
SAFE_FRAME = 0.92


def _project_dir() -> Path:
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _asset_path(asset):
    if asset is None:
        return None
    try:
        return str(asset.get_path_name())
    except Exception:
        return str(asset)


def _slot_text(slot) -> str:
    pieces = []
    for property_name in ("material_slot_name", "imported_material_slot_name"):
        try:
            pieces.append(str(slot.get_editor_property(property_name)))
        except Exception:
            pass
    try:
        material = slot.get_editor_property("material_interface")
        if material is not None:
            pieces.append(str(material.get_name()))
            pieces.append(str(material.get_path_name()))
    except Exception:
        pass
    return " ".join(pieces).lower()


def _classify_slot(slot):
    text = _slot_text(slot)
    if any(token in text for token in ("hair", "beard", "brow", "lash", "braid", "short01", "short02")):
        return "hair"
    if any(token in text for token in ("eye", "iris", "cornea", "pupil", "low-poly", "low_poly")):
        return "eye"
    if any(token in text for token in ("cloth", "shirt", "pants", "trouser", "boot", "shoe", "suit", "casual", "worksuit", "tunic", "outfit", "clothes")):
        return "clothing"
    if any(token in text for token in ("skin", "body", "face", "head")):
        return "skin"
    return None


def _relative_stage(x=0.0, y=0.0, z=0.0):
    return unreal.Vector(STAGE_ORIGIN[0] + float(x), STAGE_ORIGIN[1] + float(y), STAGE_ORIGIN[2] + float(z))


def _layout(count: int):
    if count <= 1:
        return [(0.0, 0.0, 0.0)]
    if count == 2:
        return [(0.0, -105.0, 0.0), (0.0, 105.0, 0.0)]
    positions = []
    columns = 4
    y_values = (-270.0, -90.0, 90.0, 270.0)
    for index in range(count):
        row = index // columns
        col = index % columns
        x = float(row * 165.0)
        y = y_values[col] + (45.0 if row % 2 else 0.0)
        positions.append((x, y, 0.0))
    return positions


def _shot_target(positions):
    xs = [item[0] for item in positions]
    ys = [item[1] for item in positions]
    return (
        (min(xs) + max(xs)) * 0.5,
        (min(ys) + max(ys)) * 0.5,
        15.0,
    )


def _look_at_rotation(camera, target):
    dx = float(target.x - camera.x)
    dy = float(target.y - camera.y)
    dz = float(target.z - camera.z)
    horizontal = max(1.0e-6, math.sqrt(dx * dx + dy * dy))
    return unreal.Rotator(
        pitch=math.degrees(math.atan2(dz, horizontal)),
        yaw=math.degrees(math.atan2(dy, dx)),
        roll=0.0,
    )


def _bind_character_materials(component, mesh, entry):
    results = []
    errors = []
    expected_paths = entry["character_material_paths"]
    loaded = {category: unreal.load_asset(path) for category, path in expected_paths.items()}
    if any(asset is None for asset in loaded.values()):
        return results, [{"descender_id": entry["descender_id"], "reason": "character_material_missing"}]
    observed = set()
    for slot_index, slot in enumerate(list(mesh.get_editor_property("materials"))):
        category = _classify_slot(slot)
        if category is None:
            continue
        material = loaded.get(category)
        if material is None:
            continue
        component.set_material(slot_index, material)
        actual = component.get_material(slot_index)
        bound = _asset_path(actual) == expected_paths[category]
        results.append({
            "slot_index": slot_index,
            "category": category,
            "material_instance_path": expected_paths[category],
            "bound": bound,
        })
        if bound:
            observed.add(category)
        else:
            errors.append({
                "descender_id": entry["descender_id"],
                "category": category,
                "reason": "character_material_override_mismatch",
            })
    if observed != {"skin", "hair", "eye", "clothing"}:
        errors.append({
            "descender_id": entry["descender_id"],
            "reason": "character_material_category_coverage_incomplete",
            "observed": sorted(observed),
        })
    return results, errors


def _spawn_character(actor_subsystem, entry, position, spawned):
    errors = []
    mesh = unreal.load_asset(entry["source_body_mesh_path"])
    if mesh is None or not isinstance(mesh, unreal.SkeletalMesh):
        return None, [], [], [{"descender_id": entry["descender_id"], "reason": "skeletal_mesh_missing"}]
    actor = actor_subsystem.spawn_actor_from_class(
        unreal.SkeletalMeshActor,
        _relative_stage(*position),
        unreal.Rotator(pitch=0.0, yaw=180.0, roll=0.0),
        False,
    )
    if actor is None:
        return None, [], [], [{"descender_id": entry["descender_id"], "reason": "character_spawn_failed"}]
    spawned.append(actor)
    component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
    if component is None:
        return actor, [], [], [{"descender_id": entry["descender_id"], "reason": "skeletal_component_missing"}]
    component.set_skeletal_mesh_asset(mesh)
    component.set_mobility(unreal.ComponentMobility.MOVABLE)
    actor.set_actor_scale3d(unreal.Vector(float(entry["actor_scale"]), float(entry["actor_scale"]), float(entry["actor_scale"])))
    material_results, material_errors = _bind_character_materials(component, mesh, entry)
    errors.extend(material_errors)

    equipment_results = []
    for item_index, item in enumerate(entry.get("equipment") or []):
        bone = item["attachment_bone"]
        if not component.does_socket_exist(bone):
            errors.append({"descender_id": entry["descender_id"], "visual_id": item["visual_id"], "reason": "attachment_bone_missing"})
            continue
        eq_mesh = unreal.load_asset(item["mesh_asset_path"])
        eq_material = unreal.load_asset(item["material_instance_path"])
        if eq_mesh is None or not isinstance(eq_mesh, unreal.StaticMesh) or eq_material is None:
            errors.append({"descender_id": entry["descender_id"], "visual_id": item["visual_id"], "reason": "equipment_mesh_or_material_missing"})
            continue
        eq_actor = actor_subsystem.spawn_actor_from_class(
            unreal.StaticMeshActor,
            _relative_stage(position[0], position[1] + 25.0 + item_index * 15.0, position[2]),
            unreal.Rotator(),
            False,
        )
        if eq_actor is None:
            errors.append({"descender_id": entry["descender_id"], "visual_id": item["visual_id"], "reason": "equipment_spawn_failed"})
            continue
        spawned.append(eq_actor)
        eq_component = eq_actor.get_component_by_class(unreal.StaticMeshComponent)
        eq_component.set_mobility(unreal.ComponentMobility.MOVABLE)
        eq_component.set_static_mesh(eq_mesh)
        eq_component.set_material(0, eq_material)
        attached = eq_component.attach_to_component(
            component,
            bone,
            unreal.AttachmentRule.SNAP_TO_TARGET,
            unreal.AttachmentRule.SNAP_TO_TARGET,
            unreal.AttachmentRule.KEEP_RELATIVE,
            False,
        )
        scale = item["presentation_scale"]
        eq_component.set_relative_scale3d(unreal.Vector(float(scale["x"]), float(scale["y"]), float(scale["z"])))
        grip_error = None
        if item["visual_id"] == "underreach.weapon.sword.v1":
            grip_offset_z = -SWORD_GRIP_LOCAL_ANCHOR_CM[2] * float(scale["z"])
            eq_component.set_relative_location(unreal.Vector(0.0, 0.0, grip_offset_z), False, True)
            relative = eq_component.get_relative_transform()
            location = relative.translation
            grip_error = math.sqrt(
                float(location.x) ** 2
                + float(location.y) ** 2
                + (float(location.z) + SWORD_GRIP_LOCAL_ANCHOR_CM[2] * float(scale["z"])) ** 2
            )
        parent_ok = eq_component.get_attach_parent() == component
        socket_ok = str(eq_component.get_attach_socket_name()) == bone
        mesh_ok = _asset_path(eq_component.get_editor_property("static_mesh")) == item["mesh_asset_path"]
        material_ok = _asset_path(eq_component.get_material(0)) == item["material_instance_path"]
        bound = bool(attached and parent_ok and socket_ok and mesh_ok and material_ok and (grip_error is None or grip_error <= 0.05))
        equipment_results.append({
            "descender_id": entry["descender_id"],
            "visual_id": item["visual_id"],
            "attachment_bone": bone,
            "attached": bool(attached),
            "parent_verified": parent_ok,
            "socket_verified": socket_ok,
            "mesh_verified": mesh_ok,
            "material_verified": material_ok,
            "weapon_grip_alignment_error_cm": grip_error,
            "bound": bound,
        })
        if not bound:
            errors.append({"descender_id": entry["descender_id"], "visual_id": item["visual_id"], "reason": "render_equipment_binding_failed"})

    return actor, material_results, equipment_results, errors


def _spawn_stage(actor_subsystem, proof, spawned):
    stage = []
    cube = unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube is None:
        return stage, [{"reason": "engine_cube_missing"}]
    for label, location, scale in (
        ("floor", (150.0, 0.0, -115.0), (10.0, 10.0, 0.08)),
        ("backdrop", (620.0, 0.0, 260.0), (0.08, 10.0, 7.0)),
    ):
        actor = actor_subsystem.spawn_actor_from_class(unreal.StaticMeshActor, _relative_stage(*location), unreal.Rotator(), False)
        if actor is None:
            return stage, [{"reason": f"{label}_spawn_failed"}]
        spawned.append(actor)
        component = actor.get_component_by_class(unreal.StaticMeshComponent)
        component.set_static_mesh(cube)
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        actor.set_actor_scale3d(unreal.Vector(*scale))
        stage.append(actor)

    for name, config in proof["lighting_rig"].items():
        local = config["location_cm"]
        light = actor_subsystem.spawn_actor_from_class(
            unreal.PointLight,
            _relative_stage(local[0], local[1], local[2]),
            unreal.Rotator(),
            False,
        )
        if light is None:
            return stage, [{"reason": f"{name}_light_spawn_failed"}]
        spawned.append(light)
        component = light.get_component_by_class(unreal.PointLightComponent)
        component.set_mobility(unreal.ComponentMobility.MOVABLE)
        component.set_intensity(float(config["intensity"]))
        component.set_editor_property("attenuation_radius", float(config["attenuation_radius_cm"]))
        component.set_editor_property("use_temperature", True)
        component.set_editor_property("temperature", float(config["temperature_k"]))
        stage.append(light)
    return stage, []


def _framing_metrics(shot, entries, positions, target):
    fov_h = math.radians(float(shot["fov_degrees"]))
    aspect = float(shot["render_width"]) / float(shot["render_height"])
    tan_h = math.tan(fov_h * 0.5)
    tan_v = tan_h / aspect
    distance = float(shot["camera_distance_cm"])
    max_x = 0.0
    max_y = 0.0
    for entry, position in zip(entries, positions):
        scale = float(entry["actor_scale"])
        depth = max(1.0, distance + float(position[0]) - float(target[0]))
        lateral = abs(float(position[1]) - float(target[1])) + CHARACTER_HALF_WIDTH_CM * scale
        vertical_center = 0.0 - float(target[2])
        vertical = abs(vertical_center) + CHARACTER_HALF_HEIGHT_CM * scale
        max_x = max(max_x, lateral / (depth * tan_h))
        max_y = max(max_y, vertical / (depth * tan_v))
    return {
        "max_abs_projected_x": max_x,
        "max_abs_projected_y": max_y,
        "safe_frame": SAFE_FRAME,
        "fits_safe_frame": max_x <= SAFE_FRAME and max_y <= SAFE_FRAME,
    }


def _pixel_metrics(world, render_target, width, height):
    coords = set()
    for ix in range(1, 12):
        x = int(round(ix * (width - 1) / 12.0))
        for iy in range(1, 8):
            y = int(round(iy * (height - 1) / 8.0))
            coords.add((x, y))
    colors = []
    lumas = []
    bins = set()
    for x, y in sorted(coords):
        color = unreal.RenderingLibrary.read_render_target_pixel(world, render_target, x, y)
        rgb = (int(color.r), int(color.g), int(color.b))
        colors.append({"x": x, "y": y, "rgb": rgb})
        luma = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255.0
        lumas.append(luma)
        bins.add((rgb[0] // 16, rgb[1] // 16, rgb[2] // 16))
    non_black = sum(value > 0.02 for value in lumas)
    return {
        "sample_count": len(colors),
        "non_black_sample_count": non_black,
        "luma_min": min(lumas) if lumas else 0.0,
        "luma_max": max(lumas) if lumas else 0.0,
        "luma_range": (max(lumas) - min(lumas)) if lumas else 0.0,
        "unique_quantized_color_bins": len(bins),
        "nonblank": non_black >= 4 and len(bins) >= 3 and ((max(lumas) - min(lumas)) if lumas else 0.0) >= 0.01,
    }


def _render_shot(actor_subsystem, world, proof, shot, entries_by_id, render_dir):
    spawned = []
    errors = []
    character_bindings = []
    equipment_bindings = []
    positions = _layout(len(shot["descender_ids"]))
    target_local = _shot_target(positions)
    selected = [entries_by_id[did] for did in shot["descender_ids"]]

    try:
        stage, stage_errors = _spawn_stage(actor_subsystem, proof, spawned)
        errors.extend(stage_errors)
        for entry, position in zip(selected, positions):
            actor, mats, equipment, spawn_errors = _spawn_character(actor_subsystem, entry, position, spawned)
            character_bindings.extend(mats)
            equipment_bindings.extend(equipment)
            errors.extend(spawn_errors)

        target = _relative_stage(*target_local)
        distance = float(shot["camera_distance_cm"])
        camera_location = _relative_stage(target_local[0] - distance, target_local[1], target_local[2] + 35.0)
        capture_actor = actor_subsystem.spawn_actor_from_class(unreal.SceneCapture2D, camera_location, unreal.Rotator(), False)
        if capture_actor is None:
            raise RuntimeError("SceneCapture2D spawn failed")
        spawned.append(capture_actor)
        capture_actor.set_actor_rotation(_look_at_rotation(camera_location, target), False)
        capture = capture_actor.get_component_by_class(unreal.SceneCaptureComponent2D)
        if capture is None:
            raise RuntimeError("SceneCaptureComponent2D missing from SceneCapture2D actor")
        render_target = unreal.RenderingLibrary.create_render_target2d(
            world,
            int(shot["render_width"]),
            int(shot["render_height"]),
            unreal.TextureRenderTargetFormat.RTF_RGBA8,
            unreal.LinearColor(0.012, 0.016, 0.024, 1.0),
            False,
            False,
        )
        if render_target is None:
            raise RuntimeError("render target creation failed")
        capture.set_editor_property("texture_target", render_target)
        capture.set_editor_property("capture_every_frame", False)
        capture.set_editor_property("capture_on_movement", False)
        capture.set_editor_property("capture_source", unreal.SceneCaptureSource.SCS_FINAL_COLOR_LDR)
        capture.set_editor_property("fov_angle", float(shot["fov_degrees"]))
        capture.capture_scene()

        pixel_metrics = _pixel_metrics(world, render_target, int(shot["render_width"]), int(shot["render_height"]))
        unreal.RenderingLibrary.export_render_target(world, render_target, str(render_dir), shot["output_file"])
        output = render_dir / shot["output_file"]
        file_exists = output.exists()
        file_bytes = output.stat().st_size if file_exists else 0
        file_sha = _sha(output) if file_exists else None
        framing = _framing_metrics(shot, selected, positions, target_local)
        all_character_materials_bound = bool(character_bindings) and all(item["bound"] for item in character_bindings)
        all_equipment_bound = bool(equipment_bindings) and all(item["bound"] for item in equipment_bindings)
        return {
            "shot_id": shot["shot_id"],
            "distance_band": shot["distance_band"],
            "camera_distance_cm": distance,
            "fov_degrees": float(shot["fov_degrees"]),
            "descender_ids": list(shot["descender_ids"]),
            "species": sorted({entry["species"] for entry in selected}),
            "visual_variants": sorted({entry["visual_variant"] for entry in selected}),
            "style_profiles": sorted({entry["style_profile"] for entry in selected}),
            "material_fingerprint_count": len({entry["character_material_fingerprint"] for entry in selected}),
            "equipment_visuals": sorted({item["visual_id"] for entry in selected for item in entry["equipment"]}),
            "character_material_binding_count": len(character_bindings),
            "equipment_binding_count": len(equipment_bindings),
            "all_character_materials_bound": all_character_materials_bound,
            "all_equipment_bound": all_equipment_bound,
            "framing": framing,
            "pixel_metrics": pixel_metrics,
            "output_file": str(output),
            "file_exists": file_exists,
            "file_bytes": file_bytes,
            "file_sha256": file_sha,
            "render_valid": file_exists and file_bytes >= 4096 and pixel_metrics["nonblank"] and framing["fits_safe_frame"] and all_character_materials_bound and all_equipment_bound and not errors,
            "errors": errors,
        }
    except Exception as exc:
        errors.append({"kind": "render_exception", "reason": repr(exc)})
        return {
            "shot_id": shot["shot_id"],
            "distance_band": shot["distance_band"],
            "descender_ids": list(shot["descender_ids"]),
            "render_valid": False,
            "errors": errors,
        }
    finally:
        for actor in reversed(spawned):
            try:
                actor_subsystem.destroy_actor(actor)
            except Exception:
                pass


def main():
    root = _project_dir() / "Generated" / "underreach-29e6"
    proof_path = root / "character-visual-polish-render-proof.json"
    debug_path = root / "character-visual-polish-render-unreal-debug.json"
    render_dir = root / "renders"
    render_dir.mkdir(parents=True, exist_ok=True)
    for old in render_dir.glob("*.png"):
        old.unlink()

    before = _sha(proof_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    entries_by_id = {entry["descender_id"]: entry for entry in proof.get("entries") or []}
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    world = unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).get_editor_world()
    if world is None:
        raise RuntimeError("29E.6 could not resolve editor world")

    variant_assets = {
        variant: _asset_path(unreal.load_asset(path)) == path
        for variant, path in ALL_BODY_MESHES.items()
    }
    shot_results = [
        _render_shot(actor_subsystem, world, proof, shot, entries_by_id, render_dir)
        for shot in proof["shots"]
    ]
    after = _sha(proof_path)
    errors = [error for shot in shot_results for error in shot.get("errors", [])]
    all_rendered_visuals = sorted({visual for shot in shot_results for visual in shot.get("equipment_visuals", [])})
    validation = {
        "all_six_body_mesh_assets_load": all(variant_assets.values()) and len(variant_assets) == 6,
        "character_materials_bound": all(shot.get("all_character_materials_bound") is True for shot in shot_results),
        "real_equipment_bound": all(shot.get("all_equipment_bound") is True for shot in shot_results),
        "all_equipment_visuals_rendered": all_rendered_visuals == [
            "underreach.armor.breastplate.v1",
            "underreach.armor.helmet.v1",
            "underreach.weapon.sword.v1",
        ],
        "human_dwarf_hero_rendered": shot_results[0].get("species") == ["human"] and shot_results[1].get("species") == ["dwarf"],
        "near_mid_far_rendered": [shot.get("distance_band") for shot in shot_results] == ["near", "near", "mid", "far"],
        "camera_distance_safe_frames": all((shot.get("framing") or {}).get("fits_safe_frame") is True for shot in shot_results),
        "lighting_rig_realized": len(proof.get("lighting_rig") or {}) == 3,
        "render_files_exported": all(shot.get("file_exists") is True and int(shot.get("file_bytes", 0)) >= 4096 for shot in shot_results),
        "render_pixels_nonblank": all((shot.get("pixel_metrics") or {}).get("nonblank") is True for shot in shot_results),
        "crowd_diversity_preserved": len(shot_results[3].get("descender_ids") or []) >= 10
        and set(shot_results[3].get("species") or []) == {"human", "dwarf"}
        and len(shot_results[3].get("visual_variants") or []) >= 4
        and len(shot_results[3].get("style_profiles") or []) >= 4
        and int(shot_results[3].get("material_fingerprint_count", 0)) >= 8,
        "presentation_non_authoritative": proof.get("authoritative") is False
        and proof.get("canonical_inventory_mutation_allowed") is False
        and proof.get("character_dna_mutation_allowed") is False
        and proof.get("combat_timing_mutation_allowed") is False
        and proof.get("combat_outcome_mutation_allowed") is False
        and proof.get("animation_asset_mutation_allowed") is False
        and proof.get("skeletal_mesh_binding_mutation_allowed") is False
        and proof.get("material_identity_mutation_allowed") is False,
        "proof_file_unchanged": before == after,
        "no_errors": not errors,
        "all_shots_valid": all(shot.get("render_valid") is True for shot in shot_results),
    }
    validation["all_pass"] = all(validation.values())
    payload = {
        "protocol": "underreach.character-visual-polish-render-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "source_29e6_digest": proof.get("digest"),
        "population_count": proof.get("population_count"),
        "variant_asset_loads": variant_assets,
        "shot_results": shot_results,
        "render_count": len(shot_results),
        "render_directory": str(render_dir),
        "observed_equipment_visuals": all_rendered_visuals,
        "proof_file_sha256_before": before,
        "proof_file_sha256_after": after,
        "errors": errors,
        "validation": validation,
    }
    debug_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    if validation["all_pass"]:
        unreal.log("[29E.6] Character visual polish/render proof PASS")
    else:
        unreal.log_error("[29E.6] Character visual polish/render proof FAILED")
    return debug_path


main()
