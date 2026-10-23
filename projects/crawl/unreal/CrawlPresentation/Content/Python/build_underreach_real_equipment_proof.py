import hashlib
import json
from pathlib import Path
import unreal


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_path(object_path):
    return object_path.split(".", 1)[0]


def _delete_if_present(object_path):
    package = _package_path(object_path)
    if unreal.EditorAssetLibrary.does_asset_exist(package):
        unreal.EditorAssetLibrary.delete_asset(package)


def _import_static_mesh(source_file, destination_name, expected_object_path):
    _delete_if_present(expected_object_path)
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", str(source_file))
    task.set_editor_property("destination_path", "/Game/Underreach29E2/Equipment")
    task.set_editor_property("destination_name", destination_name)
    task.set_editor_property("automated", True)
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("save", True)

    # Unreal's OBJ importer otherwise creates one StaticMesh per OBJ `o` block.
    # 29E.2 deliberately authors each equipment item from several deterministic
    # sub-parts, but the presentation contract requires one loadable mesh asset
    # per visual ID. Force all OBJ objects to combine into the requested asset.
    options = unreal.FbxImportUI()
    options.set_editor_property("import_mesh", True)
    options.set_editor_property("import_as_skeletal", False)
    options.set_editor_property("import_animations", False)
    static_data = options.get_editor_property("static_mesh_import_data")
    if static_data is not None:
        static_data.set_editor_property("combine_meshes", True)
    task.set_editor_property("options", options)

    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    imported_paths = list(task.get_editor_property("imported_object_paths") or [])
    asset = unreal.load_asset(expected_object_path)

    # Some importer builds honor combine_meshes but retain the source object's
    # name rather than destination_name. If exactly one StaticMesh was imported,
    # rename that real imported asset to the stable contract path instead of
    # falsely reporting a missing mesh.
    if asset is None and len(imported_paths) == 1:
        candidate = unreal.load_asset(imported_paths[0])
        if isinstance(candidate, unreal.StaticMesh):
            expected_package = _package_path(expected_object_path)
            if unreal.EditorAssetLibrary.rename_asset(imported_paths[0].split(".", 1)[0], expected_package):
                unreal.EditorAssetLibrary.save_asset(expected_package, only_if_is_dirty=False)
                asset = unreal.load_asset(expected_object_path)
                imported_paths = [expected_object_path]
    return asset, imported_paths


def _create_material_instance(object_path):
    _delete_if_present(object_path)
    package = _package_path(object_path)
    folder, name = package.rsplit("/", 1)
    parent = unreal.load_asset("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial")
    if parent is None:
        return None
    factory = unreal.MaterialInstanceConstantFactoryNew()
    asset = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=name,
        package_path=folder,
        asset_class=unreal.MaterialInstanceConstant,
        factory=factory,
    )
    if asset is None:
        return None
    asset.set_editor_property("parent", parent)
    unreal.EditorAssetLibrary.save_loaded_asset(asset)
    return unreal.load_asset(object_path)


def main():
    generated_root = _project_dir() / "Generated" / "underreach-29e2"
    proof_path = generated_root / "real-equipment-proof.json"
    source_manifest_path = generated_root / "source-manifest.json"
    source_dir = generated_root / "source"
    out = generated_root / "real-equipment-unreal-debug.json"

    proof_before = _sha(proof_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8"))

    source_hash_failures = []
    imported_assets = {}
    import_paths = {}
    static_mesh_class_failures = []
    material_instances = {}
    material_class_failures = []
    import_errors = []

    source_records = source_manifest.get("records") or []
    for record in source_records:
        source_file = source_dir / record["source_name"]
        actual_hash = _sha(source_file) if source_file.exists() else None
        if actual_hash != record.get("source_sha256"):
            source_hash_failures.append({
                "source_name": record.get("source_name"),
                "expected": record.get("source_sha256"),
                "actual": actual_hash,
            })
            continue
        try:
            asset, paths = _import_static_mesh(source_file, record["asset_name"], record["unreal_asset_path"])
            import_paths[record["visual_id"]] = paths
            if asset is None:
                import_errors.append({"visual_id": record["visual_id"], "reason": "asset_load_failed"})
            else:
                imported_assets[record["visual_id"]] = record["unreal_asset_path"]
                if not isinstance(asset, unreal.StaticMesh):
                    static_mesh_class_failures.append(record["unreal_asset_path"])
        except Exception as exc:
            import_errors.append({"visual_id": record["visual_id"], "reason": repr(exc)})

        try:
            material = _create_material_instance(record["material_instance_path"])
            if material is None:
                import_errors.append({"visual_id": record["visual_id"], "reason": "material_instance_create_failed"})
            else:
                material_instances[record["visual_id"]] = record["material_instance_path"]
                if not isinstance(material, unreal.MaterialInstanceConstant):
                    material_class_failures.append(record["material_instance_path"])
        except Exception as exc:
            import_errors.append({"visual_id": record["visual_id"], "reason": f"material:{repr(exc)}"})

    entries = proof.get("entries") or []
    directives = [item for entry in entries for item in (entry.get("equipment") or [])]
    asset_path_by_visual = {record["visual_id"]: record["unreal_asset_path"] for record in source_records}
    material_path_by_visual = {record["visual_id"]: record["material_instance_path"] for record in source_records}
    directive_binding_failures = []
    fit_scales = []
    attachment_bones = set()
    for item in directives:
        visual_id = item.get("visual_id")
        if item.get("unreal_asset_path") != asset_path_by_visual.get(visual_id):
            directive_binding_failures.append({"visual_id": visual_id, "kind": "mesh"})
        if item.get("material_instance_path") != material_path_by_visual.get(visual_id):
            directive_binding_failures.append({"visual_id": visual_id, "kind": "material"})
        if visual_id not in imported_assets:
            directive_binding_failures.append({"visual_id": visual_id, "kind": "mesh_not_loaded"})
        if visual_id not in material_instances:
            directive_binding_failures.append({"visual_id": visual_id, "kind": "material_not_loaded"})
        fit = item.get("presentation_scale") or {}
        fit_scales.extend(float(fit.get(axis, 0.0)) for axis in ("x", "y", "z"))
        attachment_bones.add(str(item.get("attachment_bone", "")))

    proof_after = _sha(proof_path)
    expected_source_digest = proof.get("source_asset_manifest_digest")
    source_digest_match = expected_source_digest == source_manifest.get("digest")
    validation = {
        "source_manifest_digest_matches": source_digest_match,
        "source_hashes_match": not source_hash_failures,
        "three_real_static_mesh_assets_loaded": len(imported_assets) == 3 and not static_mesh_class_failures,
        "three_material_instances_loaded": len(material_instances) == 3 and not material_class_failures,
        "no_import_errors": not import_errors,
        "all_equipment_directives_resolve_real_assets": bool(directives) and not directive_binding_failures,
        "fit_scales_bounded": bool(fit_scales) and min(fit_scales) >= 0.70 and max(fit_scales) <= 1.20,
        "accepted_attachment_bones_only": bool(attachment_bones) and attachment_bones <= {"head", "spine_03", "hand_r"},
        "production_candidate_status_truthful": all(
            item.get("visual_realization") == "real_static_mesh_asset"
            and item.get("quality_tier") == "production_candidate"
            and item.get("final_art_required") is True
            for item in directives
        ),
        "presentation_non_authoritative": proof.get("authoritative") is False
        and proof.get("canonical_inventory_mutation_allowed") is False
        and proof.get("character_dna_mutation_allowed") is False
        and proof.get("combat_timing_mutation_allowed") is False,
        "proof_file_unchanged": proof_before == proof_after,
    }
    validation["all_pass"] = all(validation.values())

    payload = {
        "protocol": "underreach.real-equipment-asset-integration-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "source_asset_count": len(source_records),
        "real_static_mesh_asset_count": len(imported_assets),
        "material_instance_count": len(material_instances),
        "equipment_directive_count": len(directives),
        "min_fit_scale": min(fit_scales) if fit_scales else None,
        "max_fit_scale": max(fit_scales) if fit_scales else None,
        "attachment_bones": sorted(attachment_bones),
        "imported_assets": imported_assets,
        "material_instances": material_instances,
        "imported_object_paths": import_paths,
        "source_hash_failures": source_hash_failures,
        "static_mesh_class_failures": static_mesh_class_failures,
        "material_class_failures": material_class_failures,
        "directive_binding_failures": directive_binding_failures,
        "import_errors": import_errors,
        "proof_file_sha256_before": proof_before,
        "proof_file_sha256_after": proof_after,
        "validation": validation,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if validation["all_pass"]:
        unreal.log("[29E.2] Unreal real equipment integration PASS")
    else:
        unreal.log_error("[29E.2] Unreal real equipment integration FAILED")
    return out


main()
