"""Underreach Slice 29E.2 real equipment asset integration.

This presentation-only layer replaces the accepted 29E.1 procedural equipment
proxy realization with deterministic, project-authored mesh-source candidates
that Unreal can import as real StaticMesh assets.  It preserves the accepted
slot, socket, fit scale, Character DNA, canonical inventory, combat timing, and
Ledger authority boundaries.

The generated meshes are deliberately classified as production candidates, not
final production art.  They prove the real-asset replacement path without
misrepresenting their artistic maturity.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

from .underreach_visual_quality import build_visual_quality_manifest

PROTOCOL = "underreach.real-equipment-asset-integration.v1"
GENERATOR_VERSION = "29e2.2"
SOURCE_PROTOCOL = "underreach.character-equipment-visual-quality.v1"
DEFAULT_SEED = "underreach-29e2-real-equipment-proof"

ASSET_ROOT = "/Game/Underreach29E2"

EQUIPMENT_ASSETS: dict[str, dict[str, str]] = {
    "underreach.weapon.sword.v1": {
        "source_name": "UR_Sword_01.obj",
        "asset_name": "SM_UR_Sword_01",
        "unreal_asset_path": f"{ASSET_ROOT}/Equipment/SM_UR_Sword_01.SM_UR_Sword_01",
        "material_instance_path": f"{ASSET_ROOT}/Materials/MI_UR_Sword_01.MI_UR_Sword_01",
        "material_family": "worked_steel_leather",
    },
    "underreach.armor.helmet.v1": {
        "source_name": "UR_Helmet_01.obj",
        "asset_name": "SM_UR_Helmet_01",
        "unreal_asset_path": f"{ASSET_ROOT}/Equipment/SM_UR_Helmet_01.SM_UR_Helmet_01",
        "material_instance_path": f"{ASSET_ROOT}/Materials/MI_UR_Helmet_01.MI_UR_Helmet_01",
        "material_family": "worked_steel_leather",
    },
    "underreach.armor.breastplate.v1": {
        "source_name": "UR_Breastplate_01.obj",
        "asset_name": "SM_UR_Breastplate_01",
        "unreal_asset_path": f"{ASSET_ROOT}/Equipment/SM_UR_Breastplate_01.SM_UR_Breastplate_01",
        "material_instance_path": f"{ASSET_ROOT}/Materials/MI_UR_Breastplate_01.MI_UR_Breastplate_01",
        "material_family": "worked_steel_leather",
    },
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(manifest: dict[str, Any]) -> str:
    value = deepcopy(manifest)
    value.pop("digest", None)
    return _digest(value)


def _box(name: str, minimum: tuple[float, float, float], maximum: tuple[float, float, float], start: int) -> tuple[list[str], list[str], int]:
    x0, y0, z0 = minimum
    x1, y1, z1 = maximum
    verts = [
        (x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
        (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1),
    ]
    vertex_lines = [f"v {x:.4f} {y:.4f} {z:.4f}" for x, y, z in verts]
    a = start
    faces = [
        (a, a + 1, a + 2, a + 3),
        (a + 4, a + 7, a + 6, a + 5),
        (a, a + 4, a + 5, a + 1),
        (a + 1, a + 5, a + 6, a + 2),
        (a + 2, a + 6, a + 7, a + 3),
        (a + 4, a, a + 3, a + 7),
    ]
    face_lines = [f"f {' '.join(str(v) for v in face)}" for face in faces]
    return [f"o {name}", *vertex_lines], face_lines, start + 8


def _mesh_obj(name: str, boxes: list[tuple[str, tuple[float, float, float], tuple[float, float, float]]]) -> str:
    lines = ["# Underreach project-authored deterministic equipment mesh", f"# generator={GENERATOR_VERSION}", "s off"]
    index = 1
    for box_name, minimum, maximum in boxes:
        vertices, faces, index = _box(f"{name}_{box_name}", minimum, maximum, index)
        lines.extend(vertices)
        lines.extend(faces)
    return "\n".join(lines) + "\n"


def equipment_source_texts() -> dict[str, str]:
    """Return deterministic OBJ sources in Unreal-centimeter scale."""
    sword = _mesh_obj("UR_Sword_01", [
        ("blade", (-2.8, -0.35, 0.0), (2.8, 0.35, 64.0)),
        ("blade_tip", (-1.7, -0.32, 64.0), (1.7, 0.32, 69.0)),
        ("guard", (-9.0, -1.0, -2.0), (9.0, 1.0, 1.0)),
        ("grip", (-1.7, -1.7, -15.0), (1.7, 1.7, -2.0)),
        ("pommel", (-2.6, -2.6, -18.0), (2.6, 2.6, -15.0)),
    ])
    helmet = _mesh_obj("UR_Helmet_01", [
        ("brow", (-11.0, -9.5, -2.0), (11.0, 9.5, 2.0)),
        ("crown", (-9.5, -8.5, 2.0), (9.5, 8.5, 10.0)),
        ("left_cheek", (-11.0, -8.0, -11.0), (-7.2, 8.0, -1.0)),
        ("right_cheek", (7.2, -8.0, -11.0), (11.0, 8.0, -1.0)),
        ("nose_guard", (-1.4, -10.5, -9.0), (1.4, -7.0, 1.0)),
        ("rear_guard", (-9.0, 6.5, -8.0), (9.0, 9.0, 2.0)),
    ])
    breastplate = _mesh_obj("UR_Breastplate_01", [
        ("front_core", (-18.0, -4.0, -12.0), (18.0, 1.0, 12.0)),
        ("front_ridge", (-14.0, -6.0, -8.0), (14.0, -4.0, 9.0)),
        ("back_core", (-17.0, 2.0, -11.0), (17.0, 5.0, 11.0)),
        ("left_flange", (-21.0, -2.5, -8.0), (-18.0, 3.5, 10.0)),
        ("right_flange", (18.0, -2.5, -8.0), (21.0, 3.5, 10.0)),
        ("left_shoulder", (-23.0, -2.0, 10.0), (-9.0, 3.0, 14.0)),
        ("right_shoulder", (9.0, -2.0, 10.0), (23.0, 3.0, 14.0)),
    ])
    return {
        "UR_Sword_01.obj": sword,
        "UR_Helmet_01.obj": helmet,
        "UR_Breastplate_01.obj": breastplate,
    }


def equipment_source_manifest() -> dict[str, Any]:
    sources = equipment_source_texts()
    records = []
    for visual_id, spec in sorted(EQUIPMENT_ASSETS.items()):
        text = sources[spec["source_name"]]
        records.append({
            "visual_id": visual_id,
            "source_name": spec["source_name"],
            "asset_name": spec["asset_name"],
            "unreal_asset_path": spec["unreal_asset_path"],
            "material_instance_path": spec["material_instance_path"],
            "material_family": spec["material_family"],
            "source_sha256": sha256(text.encode("utf-8")).hexdigest(),
            "source_bytes": len(text.encode("utf-8")),
            "source_kind": "project_authored_deterministic_obj",
            "license": "Underreach project-authored",
            "art_status": "production_candidate",
            "final_art_required": True,
        })
    body = {
        "protocol": "underreach.real-equipment-source-manifest.v1",
        "generator_version": GENERATOR_VERSION,
        "records": records,
    }
    body["digest"] = _digest(body)
    return body


def build_real_equipment_integration_manifest(seed: str = DEFAULT_SEED, count: int = 24) -> dict[str, Any]:
    source = build_visual_quality_manifest(seed=seed, count=count)
    source_assets = equipment_source_manifest()
    source_by_id = {item["visual_id"]: item for item in source_assets["records"]}
    entries: list[dict[str, Any]] = []
    replacement_count = 0
    for source_entry in source["entries"]:
        equipment = []
        for item in source_entry["equipment"]:
            asset = source_by_id[item["visual_id"]]
            equipment.append({
                "visual_id": item["visual_id"],
                "slot": item["slot"],
                "attachment_bone": item["attachment_bone"],
                "attachment_mode": item["attachment_mode"],
                "presentation_scale": deepcopy(item["presentation_scale"]),
                "source_attachment": deepcopy(item["source_attachment"]),
                "source_29e1_realization": item["asset_realization"],
                "source_29e1_quality_tier": item["quality_tier"],
                "source_29e1_planned_unreal_asset_path": item["planned_unreal_asset_path"],
                "visual_realization": "real_static_mesh_asset",
                "quality_tier": "production_candidate",
                "unreal_asset_path": asset["unreal_asset_path"],
                "material_instance_path": asset["material_instance_path"],
                "material_family": asset["material_family"],
                "source_name": asset["source_name"],
                "source_sha256": asset["source_sha256"],
                "source_kind": asset["source_kind"],
                "final_art_required": True,
                "replaces_procedural_proxy": True,
            })
            replacement_count += 1
        entries.append({
            "descender_id": source_entry["descender_id"],
            "species": source_entry["species"],
            "style_profile": source_entry["style_profile"],
            "visual_identity_digest": source_entry["visual_identity_digest"],
            "renderer_manifest_digest": source_entry["renderer_manifest_digest"],
            "material_parameters": deepcopy(source_entry["material_parameters"]),
            "equipment": equipment,
            "facial_contract_preserved": deepcopy(source_entry["facial_contract_preserved"]),
            "actor_scale": source_entry["actor_scale"],
            "stride_scale": source_entry["stride_scale"],
            "foot_ik_offset_cm": source_entry["foot_ik_offset_cm"],
        })
    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "canonical_inventory_mutation_allowed": False,
        "character_dna_mutation_allowed": False,
        "combat_timing_mutation_allowed": False,
        "source_protocol": SOURCE_PROTOCOL,
        "source_29e1_digest": source["digest"],
        "source_population_digest": source["source_population_digest"],
        "asset_registry_digest": source["asset_registry_digest"],
        "source_asset_manifest_digest": source_assets["digest"],
        "population_count": len(entries),
        "replacement_count": replacement_count,
        "unique_real_mesh_asset_count": len(source_assets["records"]),
        "unique_material_instance_count": len({item["material_instance_path"] for item in source_assets["records"]}),
        "art_policy": "29E.2 proves loadable real mesh replacement; project-authored candidates remain explicitly non-final",
        "entries": entries,
        "source_assets": source_assets["records"],
    }
    manifest["digest"] = _digest(manifest)
    validate_real_equipment_integration_manifest(manifest)
    return manifest


def validate_real_equipment_integration_manifest(manifest: dict[str, Any]) -> bool:
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29E.2 protocol/authority invalid")
    for key in ("canonical_inventory_mutation_allowed", "character_dna_mutation_allowed", "combat_timing_mutation_allowed"):
        if manifest.get(key) is not False:
            raise ValueError(f"29E.2 authority boundary violated: {key}")
    entries = manifest.get("entries") or []
    if len(entries) != int(manifest.get("population_count", -1)) or len(entries) < 4:
        raise ValueError("29E.2 population count invalid")
    assets = manifest.get("source_assets") or []
    if len(assets) != 3 or int(manifest.get("unique_real_mesh_asset_count", -1)) != 3:
        raise ValueError("29E.2 requires exactly three real equipment mesh candidates")
    source_names = equipment_source_texts()
    expected_by_id = {item["visual_id"]: item for item in assets}
    for item in assets:
        text = source_names.get(item.get("source_name"))
        if text is None or sha256(text.encode("utf-8")).hexdigest() != item.get("source_sha256"):
            raise ValueError("29E.2 source mesh hash mismatch")
        if item.get("art_status") != "production_candidate" or item.get("final_art_required") is not True:
            raise ValueError("29E.2 art maturity was misrepresented")
    replacement_count = 0
    for entry in entries:
        slots: set[str] = set()
        for item in entry.get("equipment") or []:
            replacement_count += 1
            if item.get("visual_realization") != "real_static_mesh_asset" or item.get("replaces_procedural_proxy") is not True:
                raise ValueError("29E.2 equipment was not marked as a real proxy replacement")
            if item.get("quality_tier") != "production_candidate" or item.get("final_art_required") is not True:
                raise ValueError("29E.2 equipment art maturity was misrepresented")
            if item.get("source_29e1_realization") != "procedural_attachment_geometry" or item.get("source_29e1_quality_tier") != "procedural_proxy":
                raise ValueError("29E.2 lost accepted 29E.1 replacement provenance")
            expected = expected_by_id.get(item.get("visual_id"))
            if expected is None:
                raise ValueError("29E.2 unknown equipment visual ID")
            for key in ("unreal_asset_path", "material_instance_path", "source_name", "source_sha256"):
                if item.get(key) != expected.get(key):
                    raise ValueError(f"29E.2 equipment asset binding mismatch: {key}")
            slot = str(item.get("slot", ""))
            if not slot or slot in slots:
                raise ValueError("29E.2 duplicate equipment slot")
            slots.add(slot)
            if item.get("attachment_bone") not in {"head", "spine_03", "hand_r"}:
                raise ValueError("29E.2 attachment bone changed")
            scale = item.get("presentation_scale") or {}
            if any(not 0.70 <= float(scale.get(axis, 0.0)) <= 1.20 for axis in ("x", "y", "z")):
                raise ValueError("29E.2 presentation fit scale exceeded accepted bounds")
    if replacement_count != int(manifest.get("replacement_count", -1)) or replacement_count <= 0:
        raise ValueError("29E.2 replacement count mismatch")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29E.2 digest mismatch")
    return True
