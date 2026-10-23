import hashlib
import json
from pathlib import Path

import unreal


VECTOR_PARAMETERS = {
    "BaseTint": "base_tint",
    "SecondaryTint": "secondary_tint",
    "AccentTint": "accent_tint",
}
SCALAR_PARAMETERS = {
    "Roughness": "roughness",
    "Specular": "specular",
    "Metallic": "metallic",
    "DirtAmount": "dirt_amount",
    "WearAmount": "wear_amount",
    "Saturation": "saturation",
    "ValueVariation": "value_variation",
    "MaterialVariationSeed": "material_variation_seed",
    "SecondaryMix": "secondary_mix",
    "AccentMix": "accent_mix",
}


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _package_path(object_path):
    return object_path.split(".", 1)[0]


def _asset_path(asset):
    if asset is None:
        return None
    try:
        return str(asset.get_path_name())
    except Exception:
        return str(asset)


def _delete_if_present(object_path):
    package = _package_path(object_path)
    if unreal.EditorAssetLibrary.does_asset_exist(package):
        unreal.EditorAssetLibrary.delete_asset(package)


def _scalar(material, name, default, x, y):
    mel = unreal.MaterialEditingLibrary
    node = mel.create_material_expression(material, unreal.MaterialExpressionScalarParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", float(default))
    return node


def _vector(material, name, default, x, y):
    mel = unreal.MaterialEditingLibrary
    node = mel.create_material_expression(material, unreal.MaterialExpressionVectorParameter, x, y)
    node.set_editor_property("parameter_name", name)
    node.set_editor_property(
        "default_value",
        unreal.LinearColor(float(default[0]), float(default[1]), float(default[2]), 1.0),
    )
    return node


def _constant(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant, x, y)
    node.set_editor_property("r", float(value))
    return node


def _constant3(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(material, unreal.MaterialExpressionConstant3Vector, x, y)
    node.set_editor_property(
        "constant",
        unreal.LinearColor(float(value[0]), float(value[1]), float(value[2]), 1.0),
    )
    return node


def _create_master_material(object_path):
    package = _package_path(object_path)
    folder, name = package.rsplit("/", 1)
    material = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=name,
        package_path=folder,
        asset_class=unreal.Material,
        factory=unreal.MaterialFactoryNew(),
    )
    if material is None:
        return None

    mel = unreal.MaterialEditingLibrary
    base_tint = _vector(material, "BaseTint", (0.50, 0.34, 0.24), -1160, -330)
    secondary_tint = _vector(material, "SecondaryTint", (0.42, 0.28, 0.19), -1160, -220)
    accent_tint = _vector(material, "AccentTint", (0.24, 0.15, 0.10), -1160, -110)
    secondary_mix = _scalar(material, "SecondaryMix", 0.10, -1160, 20)
    accent_mix = _scalar(material, "AccentMix", 0.08, -1160, 110)
    saturation = _scalar(material, "Saturation", 0.72, -1160, 200)
    value_variation = _scalar(material, "ValueVariation", 1.0, -1160, 290)
    variation_seed = _scalar(material, "MaterialVariationSeed", 0.5, -1160, 380)
    dirt_amount = _scalar(material, "DirtAmount", 0.08, -1160, 470)
    wear_amount = _scalar(material, "WearAmount", 0.05, -1160, 560)
    roughness = _scalar(material, "Roughness", 0.55, -1160, 680)
    specular = _scalar(material, "Specular", 0.35, -1160, 770)
    metallic = _scalar(material, "Metallic", 0.0, -1160, 860)

    secondary_lerp = mel.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -870, -270)
    mel.connect_material_expressions(base_tint, "", secondary_lerp, "A")
    mel.connect_material_expressions(secondary_tint, "", secondary_lerp, "B")
    mel.connect_material_expressions(secondary_mix, "", secondary_lerp, "Alpha")

    accent_factor = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -870, -80)
    mel.connect_material_expressions(accent_mix, "", accent_factor, "A")
    mel.connect_material_expressions(saturation, "", accent_factor, "B")

    accent_lerp = mel.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -620, -220)
    mel.connect_material_expressions(secondary_lerp, "", accent_lerp, "A")
    mel.connect_material_expressions(accent_tint, "", accent_lerp, "B")
    mel.connect_material_expressions(accent_factor, "", accent_lerp, "Alpha")

    seed_amp = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -850, 280)
    mel.connect_material_expressions(variation_seed, "", seed_amp, "A")
    mel.connect_material_expressions(_constant(material, 0.05, -1020, 330), "", seed_amp, "B")
    seed_scale = mel.create_material_expression(material, unreal.MaterialExpressionAdd, -620, 280)
    mel.connect_material_expressions(seed_amp, "", seed_scale, "A")
    mel.connect_material_expressions(_constant(material, 0.975, -820, 390), "", seed_scale, "B")
    combined_value = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -390, 250)
    mel.connect_material_expressions(value_variation, "", combined_value, "A")
    mel.connect_material_expressions(seed_scale, "", combined_value, "B")
    value_color = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -380, -170)
    mel.connect_material_expressions(accent_lerp, "", value_color, "A")
    mel.connect_material_expressions(combined_value, "", value_color, "B")

    dirt_factor = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -620, 455)
    mel.connect_material_expressions(dirt_amount, "", dirt_factor, "A")
    mel.connect_material_expressions(_constant(material, 0.40, -810, 500), "", dirt_factor, "B")
    dirt_lerp = mel.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, -120, -120)
    mel.connect_material_expressions(value_color, "", dirt_lerp, "A")
    mel.connect_material_expressions(_constant3(material, (0.055, 0.038, 0.025), -360, 10), "", dirt_lerp, "B")
    mel.connect_material_expressions(dirt_factor, "", dirt_lerp, "Alpha")

    wear_factor = mel.create_material_expression(material, unreal.MaterialExpressionMultiply, -610, 555)
    mel.connect_material_expressions(wear_amount, "", wear_factor, "A")
    mel.connect_material_expressions(_constant(material, 0.18, -820, 610), "", wear_factor, "B")
    wear_lerp = mel.create_material_expression(material, unreal.MaterialExpressionLinearInterpolate, 130, -80)
    mel.connect_material_expressions(dirt_lerp, "", wear_lerp, "A")
    mel.connect_material_expressions(_constant3(material, (0.55, 0.50, 0.42), -100, 70), "", wear_lerp, "B")
    mel.connect_material_expressions(wear_factor, "", wear_lerp, "Alpha")

    mel.connect_material_property(wear_lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
    mel.connect_material_property(specular, "", unreal.MaterialProperty.MP_SPECULAR)
    mel.connect_material_property(metallic, "", unreal.MaterialProperty.MP_METALLIC)
    mel.recompile_material(material)
    unreal.EditorAssetLibrary.save_loaded_asset(material)
    return unreal.load_asset(object_path)


def _create_instance(object_path, parent, vector_values=None, scalar_values=None):
    package = _package_path(object_path)
    folder, name = package.rsplit("/", 1)
    instance = unreal.AssetToolsHelpers.get_asset_tools().create_asset(
        asset_name=name,
        package_path=folder,
        asset_class=unreal.MaterialInstanceConstant,
        factory=unreal.MaterialInstanceConstantFactoryNew(),
    )
    if instance is None:
        return None
    instance.set_editor_property("parent", parent)
    mel = unreal.MaterialEditingLibrary
    for parameter_name, value in (vector_values or {}).items():
        mel.set_material_instance_vector_parameter_value(
            instance,
            parameter_name,
            unreal.LinearColor(float(value["r"]), float(value["g"]), float(value["b"]), float(value.get("a", 1.0))),
        )
    for parameter_name, value in (scalar_values or {}).items():
        mel.set_material_instance_scalar_parameter_value(instance, parameter_name, float(value))
    mel.update_material_instance(instance)
    unreal.EditorAssetLibrary.save_loaded_asset(instance)
    return unreal.load_asset(object_path)


def _parameter_payload(params):
    vectors = {unreal_name: params[payload_name] for unreal_name, payload_name in VECTOR_PARAMETERS.items()}
    scalars = {unreal_name: params[payload_name] for unreal_name, payload_name in SCALAR_PARAMETERS.items()}
    return vectors, scalars


def _linear_tuple(value):
    return (float(value.r), float(value.g), float(value.b), float(value.a))


def _slot_text(slot):
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
    # The accepted MPFB 29A imports preserve asset-family names rather than
    # semantic material names for two surface families.  The hair asset slots
    # arrive as e.g. braid01/short02, while the MakeHuman eye proxy arrives as
    # low-poly.  Classify those exact accepted semantics before the generic
    # joined-mesh body prefix can make them look like skin.
    if any(token in text for token in ("hair", "beard", "brow", "lash", "braid", "short01", "short02")):
        return "hair"
    if any(token in text for token in ("eye", "iris", "cornea", "pupil", "low-poly", "low_poly")):
        return "eye"
    if any(token in text for token in ("cloth", "shirt", "pants", "trouser", "boot", "shoe", "suit", "casual", "worksuit", "tunic", "outfit", "clothes")):
        return "clothing"
    if any(token in text for token in ("skin", "body", "face", "head")):
        return "skin"
    return None


def _select_binding_samples(entries):
    samples = []
    seen_variants = set()
    seen_species = set()
    for entry in entries:
        if entry["visual_variant"] not in seen_variants or entry["species"] not in seen_species or len(samples) < 8:
            samples.append(entry)
            seen_variants.add(entry["visual_variant"])
            seen_species.add(entry["species"])
        if len(samples) >= 8 and seen_species == {"human", "dwarf"} and len(seen_variants) >= 4:
            break
    return samples


def _verify_component_bindings(entries, instances_by_path):
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    results = []
    errors = []
    spawned = []
    observed_categories = set()
    bound_descenders = set()
    bound_species = set()
    try:
        for index, entry in enumerate(entries):
            mesh = unreal.load_asset(entry["source_body_mesh_path"])
            if mesh is None or not isinstance(mesh, unreal.SkeletalMesh):
                errors.append({"descender_id": entry["descender_id"], "reason": "skeletal_mesh_missing"})
                continue
            actor = actor_subsystem.spawn_actor_from_class(
                unreal.SkeletalMeshActor,
                unreal.Vector(float(index * 180), 0.0, 0.0),
                unreal.Rotator(),
                False,
            )
            if actor is None:
                errors.append({"descender_id": entry["descender_id"], "reason": "spawn_failed"})
                continue
            spawned.append(actor)
            actor.set_actor_label(f"UR29E4_{entry['descender_id']}_{index:02d}")
            component = actor.get_component_by_class(unreal.SkeletalMeshComponent)
            if component is None:
                errors.append({"descender_id": entry["descender_id"], "reason": "skeletal_component_missing"})
                continue
            component.set_skeletal_mesh_asset(mesh)
            material_by_category = {
                item["category"]: instances_by_path.get(item["material_instance_path"])
                for item in entry["character_materials"]
            }
            slots = list(mesh.get_editor_property("materials"))
            slot_results = []
            for slot_index, slot in enumerate(slots):
                category = _classify_slot(slot)
                if category is None:
                    continue
                instance = material_by_category.get(category)
                if instance is None:
                    errors.append({"descender_id": entry["descender_id"], "slot": slot_index, "category": category, "reason": "material_instance_missing"})
                    continue
                component.set_material(slot_index, instance)
                actual = component.get_material(slot_index)
                expected_path = next(item["material_instance_path"] for item in entry["character_materials"] if item["category"] == category)
                bound = _asset_path(actual) == expected_path
                slot_results.append({
                    "slot_index": slot_index,
                    "slot_text": _slot_text(slot),
                    "category": category,
                    "material_instance_path": expected_path,
                    "bound": bound,
                })
                if bound:
                    observed_categories.add(category)
                    bound_descenders.add(entry["descender_id"])
                    bound_species.add(entry["species"])
                else:
                    errors.append({"descender_id": entry["descender_id"], "slot": slot_index, "category": category, "reason": "material_override_mismatch"})
            actual_mesh = component.get_skeletal_mesh_asset()
            if _asset_path(actual_mesh) != entry["source_body_mesh_path"]:
                errors.append({"descender_id": entry["descender_id"], "reason": "skeletal_mesh_binding_mismatch"})
            if not slot_results:
                errors.append({"descender_id": entry["descender_id"], "reason": "no_character_material_slots_classified"})
            results.append({
                "descender_id": entry["descender_id"],
                "species": entry["species"],
                "visual_variant": entry["visual_variant"],
                "skeletal_mesh_path": entry["source_body_mesh_path"],
                "classified_slot_count": len(slot_results),
                "slots": slot_results,
            })
    except Exception as exc:
        errors.append({"kind": "component_binding_exception", "reason": repr(exc)})
    finally:
        for actor in reversed(spawned):
            try:
                actor_subsystem.destroy_actor(actor)
            except Exception:
                pass
    return results, errors, observed_categories, bound_descenders, bound_species


def main():
    root = _project_dir() / "Generated" / "underreach-29e4"
    proof_path = root / "character-material-appearance-proof.json"
    out = root / "character-material-unreal-debug.json"
    before = _sha(proof_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    entries = proof.get("entries") or []
    directives = [item for entry in entries for item in (entry.get("character_materials") or [])]

    errors = []
    missing_meshes = []
    hierarchy_failures = []
    parameter_failures = []
    templates = {}
    instances = {}

    for item in directives:
        _delete_if_present(item["material_instance_path"])
    for spec in (proof.get("character_material_templates") or {}).values():
        _delete_if_present(spec["material_instance_path"])
    _delete_if_present(proof["base_material_path"])

    parent = None
    try:
        parent = _create_master_material(proof["base_material_path"])
    except Exception as exc:
        errors.append({"kind": "base_material", "reason": repr(exc)})

    if parent is not None:
        for category, spec in sorted((proof.get("character_material_templates") or {}).items()):
            try:
                template = _create_instance(
                    spec["material_instance_path"],
                    parent,
                    scalar_values={"SecondaryMix": spec["secondary_mix"], "AccentMix": spec["accent_mix"]},
                )
                if template is None:
                    errors.append({"kind": "template", "category": category, "reason": "create_failed"})
                    continue
                templates[category] = template
                if _asset_path(template.get_editor_property("parent")) != proof["base_material_path"]:
                    hierarchy_failures.append({"kind": "template_parent", "category": category})
            except Exception as exc:
                errors.append({"kind": "template", "category": category, "reason": repr(exc)})

    loaded_mesh_paths = set()
    if parent is not None and len(templates) == 4:
        for entry in entries:
            mesh = unreal.load_asset(entry.get("source_body_mesh_path"))
            if mesh is None or not isinstance(mesh, unreal.SkeletalMesh):
                missing_meshes.append(entry.get("source_body_mesh_path"))
                continue
            loaded_mesh_paths.add(entry["source_body_mesh_path"])
            for item in entry["character_materials"]:
                template = templates.get(item["category"])
                if template is None:
                    errors.append({"kind": "material_instance", "path": item["material_instance_path"], "reason": "template_missing"})
                    continue
                try:
                    vector_values, scalar_values = _parameter_payload(item["parameters"])
                    instance = _create_instance(item["material_instance_path"], template, vector_values, scalar_values)
                    if instance is None:
                        errors.append({"kind": "material_instance", "path": item["material_instance_path"], "reason": "create_failed"})
                        continue
                    instances[item["material_instance_path"]] = instance
                    if _asset_path(instance.get_editor_property("parent")) != item["template_material_path"]:
                        hierarchy_failures.append({"kind": "descender_instance_parent", "path": item["material_instance_path"]})
                    mel = unreal.MaterialEditingLibrary
                    expected = item["parameters"]
                    for unreal_name, payload_name in VECTOR_PARAMETERS.items():
                        actual = mel.get_material_instance_vector_parameter_value(instance, unreal_name)
                        target = expected[payload_name]
                        expected_tuple = (float(target["r"]), float(target["g"]), float(target["b"]), float(target.get("a", 1.0)))
                        actual_tuple = _linear_tuple(actual)
                        if max(abs(a - b) for a, b in zip(actual_tuple, expected_tuple)) > 0.001:
                            parameter_failures.append({"path": item["material_instance_path"], "parameter": unreal_name, "expected": expected_tuple, "actual": actual_tuple})
                    for unreal_name, payload_name in SCALAR_PARAMETERS.items():
                        actual = mel.get_material_instance_scalar_parameter_value(instance, unreal_name)
                        expected_value = float(expected[payload_name])
                        if abs(float(actual) - expected_value) > 0.001:
                            parameter_failures.append({"path": item["material_instance_path"], "parameter": unreal_name, "expected": expected_value, "actual": float(actual)})
                except Exception as exc:
                    errors.append({"kind": "material_instance", "path": item.get("material_instance_path"), "reason": repr(exc)})

    binding_samples = _select_binding_samples(entries)
    bindings, binding_errors, observed_categories, bound_descenders, bound_species = _verify_component_bindings(binding_samples, instances)
    errors.extend(binding_errors)

    after = _sha(proof_path)
    parameter_fingerprints = {
        json.dumps(item.get("parameters") or {}, sort_keys=True, separators=(",", ":"))
        for item in directives
    }
    skin_tints = {
        tuple(sorted(item["parameters"]["base_tint"].items()))
        for item in directives if item["category"] == "skin"
    }
    hair_tints = {
        tuple(sorted(item["parameters"]["base_tint"].items()))
        for item in directives if item["category"] == "hair"
    }
    eye_tints = {
        tuple(sorted(item["parameters"]["base_tint"].items()))
        for item in directives if item["category"] == "eye"
    }
    clothing_tints = {
        tuple(sorted(item["parameters"]["base_tint"].items()))
        for item in directives if item["category"] == "clothing"
    }
    clothing_wear = {
        float(item["parameters"]["wear_amount"])
        for item in directives if item["category"] == "clothing"
    }
    clothing_dirt = {
        float(item["parameters"]["dirt_amount"])
        for item in directives if item["category"] == "clothing"
    }
    species = {entry["species"] for entry in entries}
    variants = {entry["visual_variant"] for entry in entries}

    validation = {
        "master_material_loaded": parent is not None and isinstance(parent, unreal.Material),
        "four_character_material_templates_loaded": len(templates) == 4,
        "material_parent_hierarchy_valid": not hierarchy_failures,
        "all_source_skeletal_meshes_loaded": bool(entries) and not missing_meshes,
        "human_and_dwarf_meshes_present": species == {"human", "dwarf"} and len(loaded_mesh_paths) >= 2,
        "multiple_body_variants_preserved": len(variants) >= 4,
        "all_material_instances_created": len(instances) == len(directives) and bool(directives),
        "all_material_parameters_roundtrip": not parameter_failures,
        "skin_hair_eye_clothing_variation_present": len(skin_tints) >= 3 and len(hair_tints) >= 4 and len(eye_tints) >= 2 and len(clothing_tints) >= 4,
        "clothing_wear_and_dirt_realized": len(clothing_wear) >= 8 and len(clothing_dirt) >= 8,
        "overall_material_variation_present": len(parameter_fingerprints) >= min(16, len(directives)),
        "real_skeletal_component_overrides_verified": not binding_errors
        and observed_categories == {"skin", "hair", "eye", "clothing"}
        and len(bound_descenders) >= 4
        and bound_species == {"human", "dwarf"},
        "runtime_override_contract": all(item.get("runtime_application") == "skeletal_mesh_component_material_override_by_slot_category" for item in directives),
        "presentation_non_authoritative": proof.get("authoritative") is False
        and proof.get("character_dna_mutation_allowed") is False
        and proof.get("canonical_inventory_mutation_allowed") is False
        and proof.get("combat_timing_mutation_allowed") is False
        and proof.get("animation_binding_mutation_allowed") is False
        and proof.get("skeletal_mesh_binding_mutation_allowed") is False
        and proof.get("equipment_binding_mutation_allowed") is False,
        "proof_file_unchanged": before == after,
        "no_errors": not errors,
    }
    validation["all_pass"] = all(validation.values())

    payload = {
        "protocol": "underreach.character-material-appearance-realization-unreal-debug.v1",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "population_count": len(entries),
        "directive_count": len(directives),
        "master_material_path": proof.get("base_material_path"),
        "material_template_count": len(templates),
        "material_instance_count": len(instances),
        "loaded_skeletal_mesh_count": len(loaded_mesh_paths),
        "loaded_skeletal_meshes": sorted(loaded_mesh_paths),
        "species": sorted(species),
        "visual_variants": sorted(variants),
        "unique_parameter_fingerprint_count": len(parameter_fingerprints),
        "unique_skin_tint_count": len(skin_tints),
        "unique_hair_tint_count": len(hair_tints),
        "unique_eye_tint_count": len(eye_tints),
        "unique_clothing_tint_count": len(clothing_tints),
        "unique_clothing_wear_count": len(clothing_wear),
        "unique_clothing_dirt_count": len(clothing_dirt),
        "component_binding_sample_count": len(bindings),
        "component_bound_descender_count": len(bound_descenders),
        "component_bound_species": sorted(bound_species),
        "observed_slot_categories": sorted(observed_categories),
        "component_bindings": bindings,
        "missing_meshes": sorted(set(missing_meshes)),
        "hierarchy_failures": hierarchy_failures,
        "parameter_failures": parameter_failures,
        "errors": errors,
        "proof_file_sha256_before": before,
        "proof_file_sha256_after": after,
        "validation": validation,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    if validation["all_pass"]:
        unreal.log("[29E.4] Unreal character material/appearance realization PASS")
    else:
        unreal.log_error("[29E.4] Unreal character material/appearance realization FAILED")
    return out


main()