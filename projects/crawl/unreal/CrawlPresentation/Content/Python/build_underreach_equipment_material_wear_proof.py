import hashlib
import json
from pathlib import Path

import unreal


VECTOR_PARAMETERS = {
    "MetalTint": "metal_tint",
    "LeatherTint": "leather_tint",
    "AccentTint": "accent_tint",
}
SCALAR_PARAMETERS = {
    "Roughness": "roughness",
    "Metallic": "metallic",
    "WearAmount": "wear_amount",
    "DirtAmount": "dirt_amount",
    "EdgeWear": "edge_wear",
    "LeatherMix": "leather_mix",
    "AccentMix": "accent_mix",
    "Saturation": "saturation",
    "ValueVariation": "value_variation",
    "MaterialVariationSeed": "material_variation_seed",
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
    node = mel.create_material_expression(
        material, unreal.MaterialExpressionScalarParameter, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property("default_value", float(default))
    return node


def _vector(material, name, default, x, y):
    mel = unreal.MaterialEditingLibrary
    node = mel.create_material_expression(
        material, unreal.MaterialExpressionVectorParameter, x, y
    )
    node.set_editor_property("parameter_name", name)
    node.set_editor_property(
        "default_value",
        unreal.LinearColor(
            float(default[0]), float(default[1]), float(default[2]), 1.0
        ),
    )
    return node


def _constant(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant, x, y
    )
    node.set_editor_property("r", float(value))
    return node


def _constant3(material, value, x, y):
    node = unreal.MaterialEditingLibrary.create_material_expression(
        material, unreal.MaterialExpressionConstant3Vector, x, y
    )
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
    metal_tint = _vector(material, "MetalTint", (0.42, 0.43, 0.44), -1100, -320)
    leather_tint = _vector(
        material, "LeatherTint", (0.24, 0.13, 0.07), -1100, -200
    )
    accent_tint = _vector(
        material, "AccentTint", (0.28, 0.18, 0.10), -1100, -80
    )
    leather_mix = _scalar(material, "LeatherMix", 0.08, -1100, 60)
    accent_mix = _scalar(material, "AccentMix", 0.10, -1100, 150)
    saturation = _scalar(material, "Saturation", 0.70, -1100, 240)
    value_variation = _scalar(material, "ValueVariation", 1.0, -1100, 330)
    variation_seed = _scalar(
        material, "MaterialVariationSeed", 0.5, -1100, 420
    )
    dirt_amount = _scalar(material, "DirtAmount", 0.10, -1100, 510)
    wear_amount = _scalar(material, "WearAmount", 0.10, -1100, 600)
    edge_wear = _scalar(material, "EdgeWear", 0.15, -1100, 690)
    roughness = _scalar(material, "Roughness", 0.50, -1100, 800)
    metallic = _scalar(material, "Metallic", 0.84, -1100, 890)

    base_mix = mel.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -820, -260
    )
    mel.connect_material_expressions(metal_tint, "", base_mix, "A")
    mel.connect_material_expressions(leather_tint, "", base_mix, "B")
    mel.connect_material_expressions(leather_mix, "", base_mix, "Alpha")

    accent_factor = mel.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -820, -70
    )
    mel.connect_material_expressions(accent_mix, "", accent_factor, "A")
    mel.connect_material_expressions(saturation, "", accent_factor, "B")

    accent_lerp = mel.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -590, -220
    )
    mel.connect_material_expressions(base_mix, "", accent_lerp, "A")
    mel.connect_material_expressions(accent_tint, "", accent_lerp, "B")
    mel.connect_material_expressions(accent_factor, "", accent_lerp, "Alpha")

    seed_amp = mel.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -820, 310
    )
    mel.connect_material_expressions(variation_seed, "", seed_amp, "A")
    mel.connect_material_expressions(
        _constant(material, 0.06, -1000, 350), "", seed_amp, "B"
    )
    seed_scale = mel.create_material_expression(
        material, unreal.MaterialExpressionAdd, -590, 300
    )
    mel.connect_material_expressions(seed_amp, "", seed_scale, "A")
    mel.connect_material_expressions(
        _constant(material, 0.97, -800, 390), "", seed_scale, "B"
    )
    combined_value = mel.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -370, 260
    )
    mel.connect_material_expressions(value_variation, "", combined_value, "A")
    mel.connect_material_expressions(seed_scale, "", combined_value, "B")
    value_color = mel.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -350, -180
    )
    mel.connect_material_expressions(accent_lerp, "", value_color, "A")
    mel.connect_material_expressions(combined_value, "", value_color, "B")

    dirt_factor = mel.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -600, 490
    )
    mel.connect_material_expressions(dirt_amount, "", dirt_factor, "A")
    mel.connect_material_expressions(
        _constant(material, 0.45, -800, 530), "", dirt_factor, "B"
    )
    dirt_lerp = mel.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, -100, -120
    )
    mel.connect_material_expressions(value_color, "", dirt_lerp, "A")
    mel.connect_material_expressions(
        _constant3(material, (0.075, 0.050, 0.030), -360, 10),
        "",
        dirt_lerp,
        "B",
    )
    mel.connect_material_expressions(dirt_factor, "", dirt_lerp, "Alpha")

    wear_factor = mel.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -590, 590
    )
    mel.connect_material_expressions(wear_amount, "", wear_factor, "A")
    mel.connect_material_expressions(
        _constant(material, 0.22, -800, 630), "", wear_factor, "B"
    )
    wear_lerp = mel.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 140, -70
    )
    mel.connect_material_expressions(dirt_lerp, "", wear_lerp, "A")
    mel.connect_material_expressions(
        _constant3(material, (0.58, 0.60, 0.62), -110, 80),
        "",
        wear_lerp,
        "B",
    )
    mel.connect_material_expressions(wear_factor, "", wear_lerp, "Alpha")

    fresnel = mel.create_material_expression(
        material, unreal.MaterialExpressionFresnel, -360, 690
    )
    edge_seed = mel.create_material_expression(
        material, unreal.MaterialExpressionMultiply, -120, 650
    )
    mel.connect_material_expressions(fresnel, "", edge_seed, "A")
    mel.connect_material_expressions(edge_wear, "", edge_seed, "B")
    edge_factor = mel.create_material_expression(
        material, unreal.MaterialExpressionMultiply, 90, 610
    )
    mel.connect_material_expressions(edge_seed, "", edge_factor, "A")
    mel.connect_material_expressions(
        _constant(material, 0.35, -100, 760), "", edge_factor, "B"
    )
    edge_lerp = mel.create_material_expression(
        material, unreal.MaterialExpressionLinearInterpolate, 390, -20
    )
    mel.connect_material_expressions(wear_lerp, "", edge_lerp, "A")
    mel.connect_material_expressions(
        _constant3(material, (0.72, 0.74, 0.76), 130, 120),
        "",
        edge_lerp,
        "B",
    )
    mel.connect_material_expressions(edge_factor, "", edge_lerp, "Alpha")

    mel.connect_material_property(edge_lerp, "", unreal.MaterialProperty.MP_BASE_COLOR)
    mel.connect_material_property(roughness, "", unreal.MaterialProperty.MP_ROUGHNESS)
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
            unreal.LinearColor(
                float(value["r"]),
                float(value["g"]),
                float(value["b"]),
                float(value.get("a", 1.0)),
            ),
        )
    for parameter_name, value in (scalar_values or {}).items():
        mel.set_material_instance_scalar_parameter_value(
            instance, parameter_name, float(value)
        )
    mel.update_material_instance(instance)
    unreal.EditorAssetLibrary.save_loaded_asset(instance)
    return unreal.load_asset(object_path)


def _linear_tuple(value):
    return (float(value.r), float(value.g), float(value.b), float(value.a))


def _parameter_payload(params):
    vectors = {
        unreal_name: params[payload_name]
        for unreal_name, payload_name in VECTOR_PARAMETERS.items()
    }
    scalars = {
        unreal_name: params[payload_name]
        for unreal_name, payload_name in SCALAR_PARAMETERS.items()
    }
    return vectors, scalars


def _select_binding_samples(directives):
    samples = []
    seen_visuals = set()
    seen_descenders = set()
    for item in directives:
        visual_id = item.get("visual_id")
        descender_id = item.get("descender_id")
        if visual_id not in seen_visuals or descender_id not in seen_descenders or len(samples) < 8:
            samples.append(item)
            seen_visuals.add(visual_id)
            seen_descenders.add(descender_id)
        if len(seen_visuals) >= 3 and len(seen_descenders) >= 4 and len(samples) >= 8:
            break
    return samples


def _verify_component_bindings(samples, instances_by_path):
    actor_subsystem = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
    results = []
    errors = []
    spawned = []
    try:
        for index, item in enumerate(samples):
            mesh = unreal.load_asset(item["mesh_asset_path"])
            instance = instances_by_path.get(item["material_instance_path"])
            if mesh is None or instance is None:
                errors.append(
                    {
                        "descender_id": item.get("descender_id"),
                        "visual_id": item.get("visual_id"),
                        "reason": "mesh_or_material_missing",
                    }
                )
                continue
            actor = actor_subsystem.spawn_actor_from_class(
                unreal.StaticMeshActor,
                unreal.Vector(float(index * 120), 0.0, 0.0),
                unreal.Rotator(),
                False,
            )
            if actor is None:
                errors.append(
                    {
                        "descender_id": item.get("descender_id"),
                        "visual_id": item.get("visual_id"),
                        "reason": "spawn_failed",
                    }
                )
                continue
            spawned.append(actor)
            actor.set_actor_label(f"UR29E3_{item['descender_id']}_{index:02d}")
            component = actor.get_component_by_class(unreal.StaticMeshComponent)
            if component is None:
                errors.append(
                    {
                        "descender_id": item.get("descender_id"),
                        "visual_id": item.get("visual_id"),
                        "reason": "static_mesh_component_missing",
                    }
                )
                continue
            component.set_static_mesh(mesh)
            component.set_material(0, instance)
            actual_mesh = component.get_editor_property("static_mesh")
            actual_material = component.get_material(0)
            mesh_ok = _asset_path(actual_mesh) == item["mesh_asset_path"]
            material_ok = _asset_path(actual_material) == item["material_instance_path"]
            results.append(
                {
                    "descender_id": item["descender_id"],
                    "visual_id": item["visual_id"],
                    "mesh_asset_path": item["mesh_asset_path"],
                    "material_instance_path": item["material_instance_path"],
                    "mesh_bound": mesh_ok,
                    "material_override_bound": material_ok,
                }
            )
            if not mesh_ok or not material_ok:
                errors.append(
                    {
                        "descender_id": item.get("descender_id"),
                        "visual_id": item.get("visual_id"),
                        "reason": "component_binding_mismatch",
                        "mesh_bound": mesh_ok,
                        "material_override_bound": material_ok,
                    }
                )
    except Exception as exc:
        errors.append({"reason": repr(exc), "kind": "component_binding_exception"})
    finally:
        for actor in reversed(spawned):
            try:
                actor_subsystem.destroy_actor(actor)
            except Exception:
                pass
    return results, errors


def main():
    root = _project_dir() / "Generated" / "underreach-29e3"
    proof_path = root / "equipment-material-wear-proof.json"
    out = root / "equipment-material-unreal-debug.json"
    before = _sha(proof_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    directives = [
        item
        for entry in (proof.get("entries") or [])
        for item in (entry.get("equipment_materials") or [])
    ]

    errors = []
    missing_meshes = []
    parameter_failures = []
    hierarchy_failures = []
    item_templates = {}
    instances = {}

    # Delete children before parents so repeat validation never leaves stale
    # references that can interfere with rebuilding the reusable hierarchy.
    for item in directives:
        _delete_if_present(item["material_instance_path"])
    for spec in (proof.get("item_material_templates") or {}).values():
        _delete_if_present(spec["material_instance_path"])
    _delete_if_present(proof["base_material_path"])

    parent = None
    try:
        parent = _create_master_material(proof["base_material_path"])
    except Exception as exc:
        errors.append({"kind": "base_material", "reason": repr(exc)})

    if parent is not None:
        for visual_id, spec in sorted((proof.get("item_material_templates") or {}).items()):
            try:
                template = _create_instance(
                    spec["material_instance_path"],
                    parent,
                    scalar_values={
                        "LeatherMix": spec["leather_mix"],
                        "Metallic": spec["metallic"],
                    },
                )
                if template is None:
                    errors.append(
                        {
                            "kind": "item_template",
                            "visual_id": visual_id,
                            "reason": "create_failed",
                        }
                    )
                    continue
                item_templates[visual_id] = template
                if _asset_path(template.get_editor_property("parent")) != proof["base_material_path"]:
                    hierarchy_failures.append(
                        {
                            "kind": "item_template_parent",
                            "visual_id": visual_id,
                            "expected": proof["base_material_path"],
                            "actual": _asset_path(template.get_editor_property("parent")),
                        }
                    )
            except Exception as exc:
                errors.append(
                    {
                        "kind": "item_template",
                        "visual_id": visual_id,
                        "reason": repr(exc),
                    }
                )

    if parent is not None and len(item_templates) == 3:
        for item in directives:
            mesh = unreal.load_asset(item.get("mesh_asset_path"))
            if mesh is None or not isinstance(mesh, unreal.StaticMesh):
                missing_meshes.append(item.get("mesh_asset_path"))
                continue
            template = item_templates.get(item["visual_id"])
            if template is None:
                errors.append(
                    {
                        "kind": "material_instance",
                        "path": item["material_instance_path"],
                        "reason": "item_template_missing",
                    }
                )
                continue
            try:
                vector_values, scalar_values = _parameter_payload(item["parameters"])
                instance = _create_instance(
                    item["material_instance_path"],
                    template,
                    vector_values=vector_values,
                    scalar_values=scalar_values,
                )
                if instance is None:
                    errors.append(
                        {
                            "kind": "material_instance",
                            "path": item["material_instance_path"],
                            "reason": "create_failed",
                        }
                    )
                    continue
                instances[item["material_instance_path"]] = instance
                actual_parent = _asset_path(instance.get_editor_property("parent"))
                if actual_parent != item["item_material_template_path"]:
                    hierarchy_failures.append(
                        {
                            "kind": "descender_instance_parent",
                            "path": item["material_instance_path"],
                            "expected": item["item_material_template_path"],
                            "actual": actual_parent,
                        }
                    )

                expected = item["parameters"]
                mel = unreal.MaterialEditingLibrary
                for unreal_name, payload_name in VECTOR_PARAMETERS.items():
                    actual = mel.get_material_instance_vector_parameter_value(instance, unreal_name)
                    expected_color = expected[payload_name]
                    expected_tuple = (
                        float(expected_color["r"]),
                        float(expected_color["g"]),
                        float(expected_color["b"]),
                        float(expected_color.get("a", 1.0)),
                    )
                    actual_tuple = _linear_tuple(actual)
                    if max(abs(a - b) for a, b in zip(actual_tuple, expected_tuple)) > 0.001:
                        parameter_failures.append(
                            {
                                "path": item["material_instance_path"],
                                "parameter": unreal_name,
                                "expected": expected_tuple,
                                "actual": actual_tuple,
                            }
                        )
                for unreal_name, payload_name in SCALAR_PARAMETERS.items():
                    actual = mel.get_material_instance_scalar_parameter_value(instance, unreal_name)
                    expected_value = float(expected[payload_name])
                    if abs(float(actual) - expected_value) > 0.001:
                        parameter_failures.append(
                            {
                                "path": item["material_instance_path"],
                                "parameter": unreal_name,
                                "expected": expected_value,
                                "actual": float(actual),
                            }
                        )
            except Exception as exc:
                errors.append(
                    {
                        "kind": "material_instance",
                        "path": item.get("material_instance_path"),
                        "reason": repr(exc),
                    }
                )

    binding_samples = _select_binding_samples(directives)
    component_bindings, component_binding_errors = _verify_component_bindings(binding_samples, instances)
    errors.extend(component_binding_errors)

    after = _sha(proof_path)
    parameter_fingerprints = {
        json.dumps(item.get("parameters") or {}, sort_keys=True, separators=(",", ":"))
        for item in directives
    }
    unique_metal_tints = {
        tuple(sorted((item.get("parameters") or {}).get("metal_tint", {}).items()))
        for item in directives
    }
    unique_accent_tints = {
        tuple(sorted((item.get("parameters") or {}).get("accent_tint", {}).items()))
        for item in directives
    }
    unique_roughness = {
        float((item.get("parameters") or {}).get("roughness", -1.0))
        for item in directives
    }
    unique_wear = {
        float((item.get("parameters") or {}).get("wear_amount", -1.0))
        for item in directives
    }
    unique_dirt = {
        float((item.get("parameters") or {}).get("dirt_amount", -1.0))
        for item in directives
    }
    unique_edge_wear = {
        float((item.get("parameters") or {}).get("edge_wear", -1.0))
        for item in directives
    }
    attachment_bones = {str(item.get("attachment_bone", "")) for item in directives}
    fit_scales = [
        float((item.get("presentation_scale") or {}).get(axis, 0.0))
        for item in directives
        for axis in ("x", "y", "z")
    ]
    bound_visuals = {
        item["visual_id"]
        for item in component_bindings
        if item["mesh_bound"] and item["material_override_bound"]
    }
    bound_descenders = {
        item["descender_id"]
        for item in component_bindings
        if item["mesh_bound"] and item["material_override_bound"]
    }

    validation = {
        "master_material_loaded": parent is not None and isinstance(parent, unreal.Material),
        "three_item_material_templates_loaded": len(item_templates) == 3,
        "material_parent_hierarchy_valid": not hierarchy_failures,
        "all_source_meshes_loaded": bool(directives) and not missing_meshes,
        "all_material_instances_created": len(instances) == len(directives) and bool(directives),
        "all_material_parameters_roundtrip": not parameter_failures,
        "wear_dirt_edge_parameters_realized": len(unique_wear) >= 8 and len(unique_dirt) >= 8 and len(unique_edge_wear) >= 8,
        "visible_material_variation_present": len(parameter_fingerprints) >= min(8, len(directives)) and len(unique_accent_tints) >= 4 and len(unique_roughness) >= min(8, len(directives)),
        "style_tone_variation_present": len(unique_metal_tints) >= 2,
        "real_mesh_component_overrides_verified": not component_binding_errors
        and bound_visuals
        == {
            "underreach.weapon.sword.v1",
            "underreach.armor.helmet.v1",
            "underreach.armor.breastplate.v1",
        }
        and len(bound_descenders) >= 4,
        "accepted_attachment_bones_only": bool(attachment_bones) and attachment_bones <= {"head", "spine_03", "hand_r"},
        "fit_scales_bounded": bool(fit_scales) and min(fit_scales) >= 0.70 and max(fit_scales) <= 1.20,
        "runtime_override_contract": all(
            item.get("runtime_application") == "static_mesh_component_material_override"
            for item in directives
        ),
        "presentation_non_authoritative": proof.get("authoritative") is False
        and proof.get("canonical_inventory_mutation_allowed") is False
        and proof.get("character_dna_mutation_allowed") is False
        and proof.get("combat_timing_mutation_allowed") is False
        and proof.get("mesh_binding_mutation_allowed") is False,
        "proof_file_unchanged": before == after,
        "no_errors": not errors,
    }
    validation["all_pass"] = all(validation.values())

    payload = {
        "protocol": "underreach.equipment-material-wear-realization-unreal-debug.v2",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "directive_count": len(directives),
        "master_material_path": proof.get("base_material_path"),
        "item_material_template_count": len(item_templates),
        "material_instance_count": len(instances),
        "unique_parameter_fingerprint_count": len(parameter_fingerprints),
        "unique_metal_tint_count": len(unique_metal_tints),
        "unique_accent_tint_count": len(unique_accent_tints),
        "unique_roughness_count": len(unique_roughness),
        "unique_wear_count": len(unique_wear),
        "unique_dirt_count": len(unique_dirt),
        "unique_edge_wear_count": len(unique_edge_wear),
        "component_binding_sample_count": len(component_bindings),
        "component_bound_visual_ids": sorted(bound_visuals),
        "component_bound_descender_count": len(bound_descenders),
        "attachment_bones": sorted(attachment_bones),
        "min_fit_scale": min(fit_scales) if fit_scales else None,
        "max_fit_scale": max(fit_scales) if fit_scales else None,
        "missing_meshes": sorted(set(missing_meshes)),
        "hierarchy_failures": hierarchy_failures,
        "parameter_failures": parameter_failures,
        "component_bindings": component_bindings,
        "errors": errors,
        "proof_file_sha256_before": before,
        "proof_file_sha256_after": after,
        "validation": validation,
    }
    out.write_text(
        json.dumps(payload, indent=2, sort_keys=True, default=str),
        encoding="utf-8",
    )
    if validation["all_pass"]:
        unreal.log("[29E.3] Unreal equipment material/wear realization PASS")
    else:
        unreal.log_error("[29E.3] Unreal equipment material/wear realization FAILED")
    return out


main()
