"""Underreach Slice 29E.1 character/equipment visual-quality foundation.

This layer is presentation-only. It adds deterministic material, wear, silhouette,
and equipment-fit directives to the accepted Descender population without
changing Character DNA, canonical inventory, combat state, animation timing, or
Ledger truth. Existing 29A equipment remains procedural proxy geometry; this
slice must not claim loadable production meshes that do not exist in the project.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

from .descender_population import DescenderPopulationGenerator

PROTOCOL = "underreach.character-equipment-visual-quality.v1"
GENERATOR_VERSION = "29e1.2"
SOURCE_POPULATION_PROTOCOL = "underreach.descender-population.v1"
DEFAULT_SEED = "underreach-29e1-visual-quality-proof"

EQUIPMENT_PRESENTATION = {
    "underreach.weapon.sword.v1": {"slot": "right_hand", "quality_tier": "procedural_proxy", "planned_unreal_asset_path": "/Game/Underreach29E/Equipment/SM_Sword"},
    "underreach.armor.helmet.v1": {"slot": "head_armor", "quality_tier": "procedural_proxy", "planned_unreal_asset_path": "/Game/Underreach29E/Equipment/SM_Helmet"},
    "underreach.armor.breastplate.v1": {"slot": "chest_armor", "quality_tier": "procedural_proxy", "planned_unreal_asset_path": "/Game/Underreach29E/Equipment/SM_Breastplate"},
}

STYLE_MATERIALS = {
    "earth_survivor": {"cloth_roughness": 0.82, "metal_roughness": 0.54, "leather_roughness": 0.68, "saturation": 0.72},
    "rugged": {"cloth_roughness": 0.88, "metal_roughness": 0.61, "leather_roughness": 0.74, "saturation": 0.62},
    "practical": {"cloth_roughness": 0.76, "metal_roughness": 0.48, "leather_roughness": 0.63, "saturation": 0.68},
    "armored": {"cloth_roughness": 0.70, "metal_roughness": 0.34, "leather_roughness": 0.58, "saturation": 0.60},
    "lightweight": {"cloth_roughness": 0.72, "metal_roughness": 0.44, "leather_roughness": 0.60, "saturation": 0.78},
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def _unit(seed: str, descender_id: str, label: str) -> float:
    raw = sha256(f"{GENERATOR_VERSION}:{seed}:{descender_id}:{label}".encode()).digest()
    return int.from_bytes(raw[:8], "big") / float(2**64 - 1)


def rebuild_digest(manifest: dict[str, Any]) -> str:
    value = dict(manifest)
    value.pop("digest", None)
    return _digest(value)


def _equipment_scale(species: str, visual_id: str, body_morphs: dict[str, float]) -> dict[str, float]:
    mass = float(body_morphs.get("mass", 0.5))
    shoulders = float(body_morphs.get("shoulder_width", 0.5))
    if visual_id.endswith("helmet.v1"):
        s = 1.08 if species == "dwarf" else 1.0
        return {"x": round(s, 4), "y": round(s, 4), "z": round(s, 4)}
    if visual_id.endswith("breastplate.v1"):
        return {"x": round(0.94 + shoulders * 0.14, 4), "y": round(0.94 + mass * 0.10, 4), "z": round(0.94 if species == "dwarf" else 1.0, 4)}
    if visual_id.endswith("sword.v1"):
        return {"x": 1.0, "y": 1.0, "z": 0.82 if species == "dwarf" else 1.0}
    return {"x": 1.0, "y": 1.0, "z": 1.0}


def build_visual_quality_manifest(seed: str = DEFAULT_SEED, count: int = 12) -> dict[str, Any]:
    if count < 4:
        raise ValueError("29E.1 visual proof requires at least four Descenders")
    ids = [f"descender_{index:03d}" for index in range(count)]
    population = DescenderPopulationGenerator(seed).generate(ids)
    entries: list[dict[str, Any]] = []
    for entry in population.entries:
        style = entry.style_profile
        material = deepcopy(STYLE_MATERIALS[style])
        material.update({
            "cloth_wear": round(0.08 + _unit(seed, entry.descender_id, "cloth_wear") * 0.42, 4),
            "metal_wear": round(0.05 + _unit(seed, entry.descender_id, "metal_wear") * 0.38, 4),
            "dirt_amount": round(0.06 + _unit(seed, entry.descender_id, "dirt") * 0.44, 4),
            "accent_index": int(_unit(seed, entry.descender_id, "accent") * 8.0) % 8,
        })
        equipment = []
        attachment_by_id = {item["item_visual_id"]: item for item in entry.renderer_manifest.equipment_attachments}
        for visual_id in entry.dna.appearance.equipment_visual_ids:
            spec = EQUIPMENT_PRESENTATION.get(visual_id)
            if spec is None:
                raise ValueError(f"29E.1 has no visual-quality rule for {visual_id}")
            attachment = attachment_by_id.get(visual_id)
            if attachment is None:
                raise ValueError(f"29E.1 missing accepted attachment for {visual_id}")
            equipment.append({
                "visual_id": visual_id,
                "slot": spec["slot"],
                "quality_tier": spec["quality_tier"],
                "asset_realization": "procedural_attachment_geometry",
                "unreal_asset_path": None,
                "planned_unreal_asset_path": spec["planned_unreal_asset_path"],
                "presentation_scale": _equipment_scale(entry.dna.species, visual_id, entry.renderer_manifest.body_morphs),
                "attachment_bone": attachment["socket_name"],
                "attachment_mode": attachment["attachment_mode"],
                "source_attachment": deepcopy(attachment),
                "source_geometry": deepcopy(attachment["geometry"]),
                "production_art_required": True,
            })
        entries.append({
            "descender_id": entry.descender_id,
            "species": entry.dna.species,
            "style_profile": style,
            "visual_identity_digest": entry.visual_identity_digest,
            "renderer_manifest_digest": entry.renderer_manifest.digest(),
            "material_parameters": material,
            "equipment": equipment,
            "facial_contract_preserved": list(entry.renderer_manifest.facial_contract),
            "actor_scale": entry.renderer_manifest.actor_scale,
            "stride_scale": entry.renderer_manifest.stride_scale,
            "foot_ik_offset_cm": entry.renderer_manifest.foot_ik_offset_cm,
        })
    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "canonical_inventory_mutation_allowed": False,
        "character_dna_mutation_allowed": False,
        "combat_timing_mutation_allowed": False,
        "source_population_protocol": SOURCE_POPULATION_PROTOCOL,
        "source_population_digest": population.population_digest,
        "asset_registry_digest": population.asset_registry_digest,
        "population_count": len(entries),
        "production_art_policy": "29A equipment is procedural proxy geometry; no loadable production mesh may be claimed until one exists and is validated",
        "entries": entries,
    }
    manifest["digest"] = _digest(manifest)
    validate_visual_quality_manifest(manifest)
    return manifest


def validate_visual_quality_manifest(manifest: dict[str, Any]) -> bool:
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29E.1 protocol/authority invalid")
    for key in ("canonical_inventory_mutation_allowed", "character_dna_mutation_allowed", "combat_timing_mutation_allowed"):
        if manifest.get(key) is not False:
            raise ValueError(f"29E.1 authority boundary violated: {key}")
    entries = manifest.get("entries") or []
    if len(entries) != int(manifest.get("population_count", -1)) or len(entries) < 4:
        raise ValueError("29E.1 population count invalid")
    ids: set[str] = set()
    material_fingerprints: set[str] = set()
    for entry in entries:
        did = str(entry.get("descender_id", ""))
        if not did or did in ids:
            raise ValueError("29E.1 duplicate/empty Descender visual identity")
        ids.add(did)
        material = entry.get("material_parameters") or {}
        for name in ("cloth_roughness", "metal_roughness", "leather_roughness", "saturation", "cloth_wear", "metal_wear", "dirt_amount"):
            if not 0.0 <= float(material.get(name, -1.0)) <= 1.0:
                raise ValueError(f"29E.1 material parameter out of bounds: {name}")
        material_fingerprints.add(_digest(material))
        slots: set[str] = set()
        for item in entry.get("equipment") or []:
            if item.get("quality_tier") != "procedural_proxy" or item.get("production_art_required") is not True:
                raise ValueError("29E.1 proxy provenance/quality status was misrepresented")
            if item.get("asset_realization") != "procedural_attachment_geometry" or item.get("unreal_asset_path") is not None:
                raise ValueError("29E.1 falsely claimed a loadable proxy asset")
            if not item.get("planned_unreal_asset_path") or not item.get("attachment_bone") or not item.get("source_geometry"):
                raise ValueError("29E.1 equipment lacks procedural geometry or attachment binding")
            slot = str(item.get("slot", ""))
            if not slot or slot in slots:
                raise ValueError("29E.1 duplicate equipment slot")
            slots.add(slot)
            scale = item.get("presentation_scale") or {}
            if any(not 0.70 <= float(scale.get(axis, 0.0)) <= 1.20 for axis in ("x", "y", "z")):
                raise ValueError("29E.1 equipment fit scale exceeded presentation bounds")
    if len(material_fingerprints) < min(4, len(entries)):
        raise ValueError("29E.1 material variation collapsed")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29E.1 digest mismatch")
    return True
