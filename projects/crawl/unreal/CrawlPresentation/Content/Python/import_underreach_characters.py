"""Import and validate deterministic 29A.1 MPFB character assets in UE 5.8."""

from __future__ import annotations

from hashlib import sha256
import json
import os
from pathlib import Path

import unreal


PROTOCOL = "underreach.unreal-character-import.v1"
VERSION = "29a2.1"
PROFILES = {
    "human_average": "Human",
    "human_short_heavy": "HumanShortHeavy",
    "human_tall_thin": "HumanTallThin",
    "dwarf_average": "Dwarf",
    "dwarf_heavy": "DwarfHeavy",
    "dwarf_alt": "DwarfAlt",
}
ROLES = ("idle", "walk", "attack", "reaction", "death")
EXPECTED_FACE_TARGETS = {
    "blink_left", "blink_right", "eye_look_left", "eye_look_right",
    "brow_up", "brow_down", "jaw_open", "lip_pucker", "lip_funnel",
    "lip_stretch", "smile", "frown", "viseme_aa", "viseme_ee",
    "viseme_ih", "viseme_oh", "viseme_ou", "viseme_fv", "viseme_mbp",
}
EXPECTED_BONES = {
    "Root", "pelvis", "spine_01", "spine_02", "spine_03", "neck_01", "head",
    "upperarm_l", "lowerarm_l", "hand_l", "upperarm_r", "lowerarm_r", "hand_r",
    "thigh_l", "calf_l", "foot_l", "ball_l", "thigh_r", "calf_r", "foot_r", "ball_r",
}
EXPECTED_ARM_PARENTS = {
    "upperarm_l": "clavicle_l",
    "lowerarm_l": "upperarm_l",
    "hand_l": "lowerarm_l",
    "upperarm_r": "clavicle_r",
    "lowerarm_r": "upperarm_r",
    "hand_r": "lowerarm_r",
}
EXPECTED_EQUIPMENT_ATTACHMENTS = {
    "underreach.armor.helmet.v1": ("head_armor", "head"),
    "underreach.armor.breastplate.v1": ("chest_armor", "spine_03"),
    "underreach.weapon.sword.v1": ("right_hand", "hand_r"),
}


def project_dir() -> Path:
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def atomic_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(str(temporary), str(path))


def import_mesh(source: Path, destination: str, name: str):
    # The exporter now joins body, clothing, hair, eyes, and proxy gear into a
    # single skinned mesh node. UE 5.8 Interchange retained morph names but
    # produced a render-rigid skin in unattended imports; the mature legacy
    # skeletal importer preserves both the joined node's weights and shapes.
    unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("automated_import_should_detect_type", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_SKELETAL_MESH)
    options.set_editor_property("import_animations", False)
    options.set_editor_property("import_materials", True)
    options.set_editor_property("import_textures", True)
    options.set_editor_property("create_physics_asset", False)
    skeletal = options.get_editor_property("skeletal_mesh_import_data")
    skeletal.set_editor_property("import_morph_targets", True)
    skeletal.set_editor_property("update_skeleton_reference_pose", False)
    options.set_editor_property("skeletal_mesh_import_data", skeletal)
    task.set_editor_property("options", options)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    assets = [unreal.load_asset(path) for path in task.get_editor_property("imported_object_paths")]
    meshes = [asset for asset in assets if isinstance(asset, unreal.SkeletalMesh)]
    if len(meshes) != 1:
        raise RuntimeError(f"Expected one skeletal mesh from {source}, got {task.imported_object_paths}")
    mesh = meshes[0]
    # The legacy FBX task reports the SkeletalMesh but can omit materials from
    # imported_object_paths even though the mesh now references them.  Without
    # an explicit save those packages exist only for the warm import process;
    # a fresh live/render process then logs missing dependencies and loses the
    # authored clothing/skin/equipment materials.
    material_paths = []
    for slot in mesh.get_editor_property("materials"):
        material = slot.get_editor_property("material_interface")
        if material is None:
            # MPFB leaves a small number of intentionally unassigned utility
            # slots. Unreal renders those with its default surface and they do
            # not create a package dependency to persist.
            continue
        path = material.get_path_name()
        if path.startswith(destination + "/"):
            if not unreal.EditorAssetLibrary.save_loaded_asset(material, False):
                raise RuntimeError(f"Could not persist imported material {path}")
            material_paths.append(path)
    if not unreal.EditorAssetLibrary.save_loaded_asset(mesh, False):
        raise RuntimeError(f"Could not persist imported skeletal mesh {mesh.get_path_name()}")
    return mesh, list(task.imported_object_paths), sorted(set(material_paths))


def import_animation(source: Path, destination: str, name: str, skeleton):
    unreal.SystemLibrary.execute_console_command(None, "Interchange.FeatureFlags.Import.FBX 0")
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source))
    task.set_editor_property("destination_path", destination)
    task.set_editor_property("destination_name", name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", False)
    options.set_editor_property("import_as_skeletal", True)
    options.set_editor_property("automated_import_should_detect_type", False)
    options.set_editor_property("mesh_type_to_import", unreal.FBXImportType.FBXIT_ANIMATION)
    options.set_editor_property("import_animations", True)
    options.set_editor_property("import_materials", False)
    options.set_editor_property("import_textures", False)
    options.set_editor_property("skeleton", skeleton)
    task.set_editor_property("options", options)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    assets = [unreal.load_asset(path) for path in task.get_editor_property("imported_object_paths")]
    sequences = [asset for asset in assets if asset is not None]
    if len(sequences) != 1:
        raise RuntimeError(f"Expected one animation from {source}, got {task.imported_object_paths}")
    return sequences[0], list(task.imported_object_paths)


def validate_bones(mesh) -> list[str]:
    """Validate named bones through the UE 5.8 editor subsystem.

    UE 5.8 removed ``Skeleton.get_reference_skeleton`` from Python, while the
    supported skeletal-mesh subsystem still resolves names against the real
    imported reference hierarchy.
    """
    validated = []
    for name in sorted(EXPECTED_BONES):
        try:
            parent = unreal.SkeletalMeshEditorSubsystem.get_bone_parent(mesh, name)
            unreal.SkeletalMeshEditorSubsystem.get_bone_children(mesh, name)
            # UE returns NAME_None rather than throwing for an unknown bone.
            if name == "Root" or str(parent).lower() not in {"", "none"}:
                validated.append(name)
        except Exception:
            continue
    return validated


def validate_arm_chains(mesh) -> dict:
    parents = {
        bone: str(unreal.SkeletalMeshEditorSubsystem.get_bone_parent(mesh, bone))
        for bone in EXPECTED_ARM_PARENTS
    }
    valid = all(parents[bone] == expected for bone, expected in EXPECTED_ARM_PARENTS.items())
    result = {
        "left_arm_chain": ["clavicle_l", "upperarm_l", "lowerarm_l", "hand_l"],
        "right_arm_chain": ["clavicle_r", "upperarm_r", "lowerarm_r", "hand_r"],
        "observed_parents": parents,
        "one_left_arm_chain": valid,
        "one_right_arm_chain": valid,
    }
    if not valid:
        raise RuntimeError(f"Imported skeletal mesh has an invalid or duplicated arm hierarchy: {result}")
    return result


def mutable_probe(destination: str) -> dict:
    names = sorted(name for name in dir(unreal) if "CustomizableObject" in name or name.startswith("Customizable"))
    result = {
        "plugin_enabled": bool(names),
        "python_types": names,
        "asset_created": False,
        "asset_preserved": False,
        "asset_path": None,
        "graph_automation_available": any("Node" in name or "Graph" in name for name in names),
        "error": None,
    }
    object_class = getattr(unreal, "CustomizableObject", None)
    factory_class = getattr(unreal, "CustomizableObjectFactory", None)
    if object_class is None or factory_class is None:
        result["error"] = "Core Mutable runtime is loaded, but no Python asset factory is exposed"
        return result
    path = f"{destination}/CO_UnderreachDescender29A1"
    try:
        asset = unreal.load_asset(path) if unreal.EditorAssetLibrary.does_asset_exist(path) else None
        if asset is not None:
            result["asset_preserved"] = True
        else:
            asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
                path.rsplit("/", 1)[-1], destination, object_class, factory_class()
            )
            result["asset_created"] = asset is not None
        if asset is not None:
            unreal.EditorAssetLibrary.save_loaded_asset(asset, False)
            result["asset_path"] = path
            try:
                source = asset.get_editor_property("source")
                nodes = list(source.get_editor_property("nodes")) if source is not None else []
                result["graph_class"] = source.get_class().get_name() if source is not None else None
                result["graph_node_count"] = len(nodes)
                result["graph_nodes"] = [node.get_class().get_name() for node in nodes]
            except Exception as exc:
                # UE 5.8 exposes node classes but protects CustomizableObject.Source
                # from Python. Preserve the real asset scaffold and report the
                # exact boundary instead of pretending a graph was assembled.
                result["manual_graph_required"] = True
                result["graph_introspection_error"] = f"{type(exc).__name__}: {exc}"
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
    return result


def main() -> None:
    root = project_dir() / "Generated" / "29a1"
    source = root / "fbx"
    if not source.exists():
        raise RuntimeError(f"Generated MPFB exports are missing: {source}")
    source_manifest = json.loads((root / "blender_character_export_manifest.json").read_text(encoding="utf-8"))
    source_records = {record["descender_id"]: record for record in source_manifest["characters"]}
    destination = "/Game/Underreach29A1/Characters"
    # Reimport generated assets in place.  The directory also contains the
    # hand-authored Mutable Customizable Object, whose graph must survive
    # validation.  AssetImportTask.replace_existing refreshes mesh/animation
    # packages without deleting that graph or breaking its mesh references.
    records = []
    for profile_id, asset_suffix in PROFILES.items():
        species = "human" if profile_id.startswith("human_") else "dwarf"
        species_name = species.title()
        mesh, mesh_paths, material_paths = import_mesh(
            source / f"SK_{profile_id}.fbx", destination,
            f"SK_Underreach{asset_suffix}",
        )
        skeleton = mesh.get_editor_property("skeleton")
        if skeleton is None:
            raise RuntimeError(f"{species_name} imported without a skeleton")
        # The legacy importer creates a transient Skeleton alongside the mesh
        # but does not include it in AssetImportTask.imported_object_paths.
        # Persist it before importing any clips or their saved references are
        # silently null on the next editor process.
        if not unreal.EditorAssetLibrary.save_loaded_asset(skeleton, False):
            raise RuntimeError(f"Could not persist {species_name} skeleton {skeleton.get_path_name()}")
        try:
            morphs = sorted(str(name) for name in mesh.get_all_morph_target_names())
        except Exception:
            morphs = []
        missing_morphs = sorted(EXPECTED_FACE_TARGETS.difference(morphs))
        bones = validate_bones(mesh)
        arm_validation = validate_arm_chains(mesh)
        missing_bones = sorted(EXPECTED_BONES.difference(bones))
        source_record = source_records[profile_id]
        body_visibility_masks = source_record.get("body_visibility_masks", {})
        if (
            body_visibility_masks.get("visible_arm_geometry_layers_per_side") != 1
            or body_visibility_masks.get("mechanism")
            != "bake_mpfb_visibility_masks_before_underreach_shape_keys"
            or int(body_visibility_masks.get("removed_hidden_body_vertex_count", 0)) <= 0
            or len(body_visibility_masks.get("applied_masks", [])) < 2
        ):
            raise RuntimeError(
                f"{species_name} source did not bake its hidden body geometry: {body_visibility_masks}"
            )
        equipment_attachments = source_record.get("equipment_attachments", [])
        by_id = {item.get("item_visual_id"): item for item in equipment_attachments}
        if (
            len(by_id) != len(equipment_attachments)
            or not set(by_id).issubset(EXPECTED_EQUIPMENT_ATTACHMENTS)
            or "underreach.weapon.sword.v1" not in by_id
        ):
            raise RuntimeError(f"{species_name} equipment attachments are missing or duplicated: {equipment_attachments}")
        for item_id in by_id:
            slot, socket = EXPECTED_EQUIPMENT_ATTACHMENTS[item_id]
            item = by_id[item_id]
            if (
                item.get("slot") != slot
                or item.get("socket_name") != socket
                or item.get("attachment_mode") != "skeletal_skin"
                or float(item.get("expected_socket_error_cm", 999.0)) > 0.01
                or int(item.get("duplicate_visible_copies", 1)) != 0
            ):
                raise RuntimeError(f"{species_name} has an invalid {item_id} attachment: {item}")
        animations = {}
        for role in ROLES:
            animation, imported = import_animation(
                source / f"A_{profile_id}_{role}.fbx", destination,
                f"A_Underreach{asset_suffix}_{role.title()}", skeleton,
            )
            if animation.get_editor_property("skeleton") is None:
                raise RuntimeError(f"{species_name} {role} animation imported without a skeleton")
            unreal.EditorAssetLibrary.save_loaded_asset(animation, False)
            animations[role] = {
                "asset_path": animation.get_path_name(),
                "duration_seconds": round(float(animation.get_play_length()), 6),
                "imported_paths": imported,
            }
        if missing_morphs or missing_bones:
            raise RuntimeError(
                f"{species_name} contract mismatch: missing morphs={missing_morphs}, missing bones={missing_bones}"
            )
        records.append({
            "profile_id": profile_id,
            "species": species,
            "visual_variant": profile_id,
            "mesh_asset": mesh.get_path_name(),
            "skeleton_asset": skeleton.get_path_name(),
            "mesh_imported_paths": mesh_paths,
            "material_assets": material_paths,
            "skeletal_mesh_asset_count": 1,
            "required_bone_count": len(bones),
            "source_bone_count": int(source_record["bone_count"]),
            "required_bones_present": True,
            "morph_target_count": len(morphs),
            "face_contract_present": True,
            "material_slot_count": len(mesh.get_editor_property("materials")),
            "arm_validation": arm_validation,
            "visible_arm_geometry_layers_per_side": 1,
            "body_visibility_masks": body_visibility_masks,
            "face_identity": source_record.get("face_identity", {}),
            "equipment_attachments": equipment_attachments,
            "animations": animations,
        })
    mutable = mutable_probe(destination)
    if not mutable["plugin_enabled"]:
        raise RuntimeError("Mutable plugin Python runtime is unavailable")
    body = {
        "protocol": PROTOCOL,
        "version": VERSION,
        "unreal_version": unreal.SystemLibrary.get_engine_version(),
        "characters": records,
        "mutable": mutable,
        "source_manifest": str(root / "blender_character_export_manifest.json"),
    }
    body["digest"] = sha256(canonical(body).encode("utf-8")).hexdigest()
    atomic_json(root / "unreal_character_import_report.json", body)
    unreal.log(f"UNDERREACH 29A.1 CHARACTER IMPORT PASS {body['digest']}")


main()
