import hashlib
import json
from pathlib import Path
import unreal


def _project_dir():
    return Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir()))


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _geometry_valid(item):
    geometry = item.get("source_geometry") or {}
    kind = str(geometry.get("kind", ""))
    required = {"helmet": "depth_cm", "breastplate": "width_cm", "sword": "blade_length_cm"}
    key = required.get(kind)
    return key is not None and float(geometry.get(key, 0.0)) > 0.0


def main():
    root = _project_dir() / "Generated" / "underreach-29e1"
    proof_path = root / "visual-quality-proof.json"
    out = root / "visual-quality-unreal-debug.json"
    before = _sha(proof_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    entries = proof.get("entries") or []
    scales = []
    attachment_bones = set()
    material_variants = set()
    procedural = []
    loadable = []
    missing_loadable = []
    invalid_geometry = []
    planned_paths = set()
    for entry in entries:
        material = entry.get("material_parameters") or {}
        material_variants.add(tuple(sorted(material.items())))
        for item in entry.get("equipment") or []:
            if item.get("asset_realization") == "procedural_attachment_geometry":
                procedural.append(item.get("visual_id"))
                planned = item.get("planned_unreal_asset_path")
                if planned:
                    planned_paths.add(str(planned))
                if not _geometry_valid(item):
                    invalid_geometry.append(item.get("visual_id"))
            else:
                path = item.get("unreal_asset_path")
                asset = unreal.load_asset(path) if path else None
                if asset is None:
                    missing_loadable.append(path)
                else:
                    loadable.append(path)
            scale = item.get("presentation_scale") or {}
            scales.extend(float(scale.get(axis, 0.0)) for axis in ("x", "y", "z"))
            attachment_bones.add(str(item.get("attachment_bone", "")))
    after = _sha(proof_path)
    all_items = [item for entry in entries for item in entry.get("equipment") or []]
    validation = {
        "equipment_realization_truthful": bool(all_items) and all(
            item.get("quality_tier") == "procedural_proxy"
            and item.get("asset_realization") == "procedural_attachment_geometry"
            and item.get("unreal_asset_path") is None
            and item.get("production_art_required") is True
            for item in all_items
        ),
        "procedural_geometry_complete": bool(procedural) and not invalid_geometry,
        "no_missing_claimed_loadable_assets": not missing_loadable,
        "production_replacement_paths_reserved": len(planned_paths) >= 3,
        "population_present": len(entries) >= 4,
        "material_variation_present": len(material_variants) >= min(4, len(entries)),
        "fit_scales_bounded": bool(scales) and min(scales) >= 0.70 and max(scales) <= 1.20,
        "accepted_attachment_bones_only": attachment_bones <= {"head", "spine_03", "hand_r"} and bool(attachment_bones),
        "presentation_non_authoritative": proof.get("authoritative") is False and proof.get("canonical_inventory_mutation_allowed") is False and proof.get("character_dna_mutation_allowed") is False and proof.get("combat_timing_mutation_allowed") is False,
        "proof_file_unchanged": before == after,
    }
    validation["all_pass"] = all(validation.values())
    payload = {
        "protocol": "underreach.character-equipment-visual-quality-unreal-debug.v2",
        "authoritative": False,
        "engine_version": unreal.SystemLibrary.get_engine_version(),
        "population_count": len(entries),
        "equipment_directive_count": len(all_items),
        "procedural_proxy_directive_count": len(procedural),
        "loadable_equipment_asset_count": len(loadable),
        "planned_production_asset_count": len(planned_paths),
        "material_variant_count": len(material_variants),
        "min_fit_scale": min(scales) if scales else None,
        "max_fit_scale": max(scales) if scales else None,
        "attachment_bones": sorted(attachment_bones),
        "invalid_geometry": invalid_geometry,
        "missing_claimed_loadable_assets": missing_loadable,
        "proof_file_sha256_before": before,
        "proof_file_sha256_after": after,
        "validation": validation,
    }
    out.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if validation["all_pass"]:
        unreal.log("[29E.1] Unreal visual quality proof PASS")
    else:
        unreal.log_error("[29E.1] Unreal visual quality proof FAILED")
    return out


main()
