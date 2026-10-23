"""Underreach Slice 29E.4 character material and appearance realization.

This layer converts already-accepted deterministic Descender identity into
presentation-only Unreal material directives. It MUST NOT mutate Character DNA,
canonical inventory, combat timing, animation bindings, skeletal-mesh identity,
equipment bindings, or Ledger truth.
"""
from __future__ import annotations

from hashlib import sha256
import json
from typing import Any

from .descender_population import DescenderPopulationGenerator
from .underreach_equipment_material_wear import (
    build_equipment_material_wear_manifest,
)
from .underreach_visual_quality import build_visual_quality_manifest

PROTOCOL = "underreach.character-material-appearance-realization.v1"
GENERATOR_VERSION = "29e4.1"
DEFAULT_SEED = "underreach-29e2-real-equipment-proof"
BASE_MATERIAL_PATH = "/Game/Underreach29E4/Materials/M_UR_Character_Master.M_UR_Character_Master"

CHARACTER_MATERIAL_TEMPLATES = {
    "skin": {
        "material_instance_path": "/Game/Underreach29E4/Materials/Templates/MI_UR_Skin_Template.MI_UR_Skin_Template",
        "secondary_mix": 0.08,
        "accent_mix": 0.02,
    },
    "hair": {
        "material_instance_path": "/Game/Underreach29E4/Materials/Templates/MI_UR_Hair_Template.MI_UR_Hair_Template",
        "secondary_mix": 0.14,
        "accent_mix": 0.03,
    },
    "eye": {
        "material_instance_path": "/Game/Underreach29E4/Materials/Templates/MI_UR_Eye_Template.MI_UR_Eye_Template",
        "secondary_mix": 0.16,
        "accent_mix": 0.08,
    },
    "clothing": {
        "material_instance_path": "/Game/Underreach29E4/Materials/Templates/MI_UR_Clothing_Template.MI_UR_Clothing_Template",
        "secondary_mix": 0.12,
        "accent_mix": 0.22,
    },
}

BODY_MESHES = {
    "human_average": "/Game/Underreach29A1/Characters/SK_UnderreachHuman.SK_UnderreachHuman",
    "human_short_heavy": "/Game/Underreach29A1/Characters/SK_UnderreachHumanShortHeavy.SK_UnderreachHumanShortHeavy",
    "human_tall_thin": "/Game/Underreach29A1/Characters/SK_UnderreachHumanTallThin.SK_UnderreachHumanTallThin",
    "dwarf_average": "/Game/Underreach29A1/Characters/SK_UnderreachDwarf.SK_UnderreachDwarf",
    "dwarf_heavy": "/Game/Underreach29A1/Characters/SK_UnderreachDwarfHeavy.SK_UnderreachDwarfHeavy",
    "dwarf_alt": "/Game/Underreach29A1/Characters/SK_UnderreachDwarfAlt.SK_UnderreachDwarfAlt",
}

SKIN_TONES = {
    "skin_001": (0.82, 0.60, 0.47),
    "skin_002": (0.70, 0.48, 0.34),
    "skin_003": (0.55, 0.35, 0.24),
    "skin_004": (0.39, 0.23, 0.15),
    "skin_005": (0.24, 0.13, 0.085),
}

EYE_TONES = {
    "eye_001": (0.20, 0.32, 0.42),
    "eye_002": (0.24, 0.39, 0.25),
    "eye_003": (0.36, 0.25, 0.15),
    "eye_004": (0.42, 0.38, 0.25),
}

HAIR_TONES = (
    (0.035, 0.025, 0.020),
    (0.085, 0.045, 0.025),
    (0.16, 0.075, 0.035),
    (0.24, 0.12, 0.055),
    (0.34, 0.22, 0.11),
    (0.46, 0.34, 0.18),
    (0.26, 0.095, 0.045),
    (0.40, 0.40, 0.39),
)

STYLE_CLOTHING_TONES = {
    "earth_survivor": ((0.22, 0.15, 0.09), (0.34, 0.25, 0.14)),
    "rugged": ((0.14, 0.12, 0.10), (0.26, 0.20, 0.14)),
    "practical": ((0.19, 0.22, 0.23), (0.31, 0.34, 0.34)),
    "armored": ((0.16, 0.18, 0.20), (0.30, 0.32, 0.34)),
    "lightweight": ((0.22, 0.25, 0.22), (0.37, 0.39, 0.31)),
}

ACCENT_TONES = (
    (0.42, 0.12, 0.08),
    (0.12, 0.25, 0.42),
    (0.18, 0.36, 0.20),
    (0.42, 0.31, 0.08),
    (0.31, 0.16, 0.38),
    (0.08, 0.34, 0.36),
    (0.36, 0.20, 0.11),
    (0.28, 0.28, 0.27),
)


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(manifest: dict[str, Any]) -> str:
    value = dict(manifest)
    value.pop("digest", None)
    return _digest(value)


def _unit(seed: str, descender_id: str, label: str) -> float:
    raw = sha256(f"{GENERATOR_VERSION}:{seed}:{descender_id}:{label}".encode("utf-8")).digest()
    return int.from_bytes(raw[:8], "big") / float(2**64 - 1)


def _color(value: tuple[float, float, float], multiplier: float = 1.0) -> dict[str, float]:
    return {
        "r": round(min(1.0, max(0.0, value[0] * multiplier)), 4),
        "g": round(min(1.0, max(0.0, value[1] * multiplier)), 4),
        "b": round(min(1.0, max(0.0, value[2] * multiplier)), 4),
        "a": 1.0,
    }


def _instance_path(descender_id: str, category: str) -> str:
    safe = "".join(char if char.isalnum() else "_" for char in descender_id)
    name = f"MI_UR_{safe}_{category.title()}"
    return f"/Game/Underreach29E4/Materials/Descenders/{name}.{name}"


def _hair_tone(seed: str, descender_id: str) -> tuple[float, float, float]:
    index = min(len(HAIR_TONES) - 1, int(_unit(seed, descender_id, "hair_tone") * len(HAIR_TONES)))
    return HAIR_TONES[index]


def _accent_tone(index: int) -> tuple[float, float, float]:
    return ACCENT_TONES[int(index) % len(ACCENT_TONES)]


def _parameters(
    *,
    seed: str,
    descender_id: str,
    category: str,
    base: tuple[float, float, float],
    secondary: tuple[float, float, float],
    accent: tuple[float, float, float],
    roughness: float,
    specular: float,
    dirt: float,
    wear: float,
    saturation: float,
) -> dict[str, Any]:
    template = CHARACTER_MATERIAL_TEMPLATES[category]
    value_variation = 0.94 + _unit(seed, descender_id, f"{category}:value") * 0.12
    return {
        "base_tint": _color(base, value_variation),
        "secondary_tint": _color(secondary, value_variation),
        "accent_tint": _color(accent, value_variation),
        "roughness": round(min(1.0, max(0.0, roughness)), 4),
        "specular": round(min(1.0, max(0.0, specular)), 4),
        "metallic": 0.0,
        "dirt_amount": round(min(1.0, max(0.0, dirt)), 4),
        "wear_amount": round(min(1.0, max(0.0, wear)), 4),
        "saturation": round(min(1.0, max(0.0, saturation)), 4),
        "value_variation": round(value_variation, 4),
        "material_variation_seed": round(_unit(seed, descender_id, f"{category}:seed"), 4),
        "secondary_mix": float(template["secondary_mix"]),
        "accent_mix": float(template["accent_mix"]),
    }


def build_character_material_appearance_manifest(
    seed: str = DEFAULT_SEED,
    count: int = 24,
) -> dict[str, Any]:
    if count < 8:
        raise ValueError("29E.4 proof requires at least eight Descenders")

    ids = [f"descender_{index:03d}" for index in range(count)]
    population = DescenderPopulationGenerator(seed).generate(ids)
    visual = build_visual_quality_manifest(seed=seed, count=count)
    equipment = build_equipment_material_wear_manifest(seed=seed, count=count)

    if visual["source_population_digest"] != population.population_digest:
        raise ValueError("29E.4 visual-quality source population does not match Descender population")
    if equipment["source_population_digest"] != population.population_digest:
        raise ValueError("29E.4 equipment source population does not match Descender population")
    if equipment["source_29e1_digest"] != visual["digest"]:
        raise ValueError("29E.4 source chain does not preserve the accepted 29E.1 manifest")

    visual_by_id = {entry["descender_id"]: entry for entry in visual["entries"]}
    equipment_by_id = {entry["descender_id"]: entry for entry in equipment["entries"]}
    entries: list[dict[str, Any]] = []

    for source in population.entries:
        visual_entry = visual_by_id[source.descender_id]
        equipment_entry = equipment_by_id[source.descender_id]
        dna = source.dna
        style = source.style_profile
        if style not in STYLE_CLOTHING_TONES:
            raise ValueError(f"29E.4 has no clothing tone family for style {style}")
        if dna.skin_variant not in SKIN_TONES or dna.eye_variant not in EYE_TONES:
            raise ValueError("29E.4 received an unknown deterministic skin/eye variant")
        body_mesh = BODY_MESHES.get(source.visual_variant)
        if body_mesh is None:
            raise ValueError(f"29E.4 has no accepted body mesh for {source.visual_variant}")

        accepted_material = visual_entry["material_parameters"]
        accent = _accent_tone(int(accepted_material["accent_index"]))
        clothing_base, clothing_secondary = STYLE_CLOTHING_TONES[style]
        hair = _hair_tone(seed, source.descender_id)
        skin = SKIN_TONES[dna.skin_variant]
        eyes = EYE_TONES[dna.eye_variant]

        categories = {
            "skin": _parameters(
                seed=seed,
                descender_id=source.descender_id,
                category="skin",
                base=skin,
                secondary=(min(1.0, skin[0] * 1.05), min(1.0, skin[1] * 0.94), min(1.0, skin[2] * 0.90)),
                accent=accent,
                roughness=0.46 + _unit(seed, source.descender_id, "skin:roughness") * 0.12,
                specular=0.36 + _unit(seed, source.descender_id, "skin:specular") * 0.12,
                dirt=float(accepted_material["dirt_amount"]) * 0.35,
                wear=0.0,
                saturation=float(accepted_material["saturation"]),
            ),
            "hair": _parameters(
                seed=seed,
                descender_id=source.descender_id,
                category="hair",
                base=hair,
                secondary=(min(1.0, hair[0] * 1.22), min(1.0, hair[1] * 1.18), min(1.0, hair[2] * 1.12)),
                accent=accent,
                roughness=0.56 + _unit(seed, source.descender_id, "hair:roughness") * 0.14,
                specular=0.24 + _unit(seed, source.descender_id, "hair:specular") * 0.12,
                dirt=float(accepted_material["dirt_amount"]) * 0.28,
                wear=0.0,
                saturation=min(1.0, float(accepted_material["saturation"]) + 0.08),
            ),
            "eye": _parameters(
                seed=seed,
                descender_id=source.descender_id,
                category="eye",
                base=eyes,
                secondary=(min(1.0, eyes[0] * 1.35), min(1.0, eyes[1] * 1.35), min(1.0, eyes[2] * 1.35)),
                accent=accent,
                roughness=0.10 + _unit(seed, source.descender_id, "eye:roughness") * 0.10,
                specular=0.70 + _unit(seed, source.descender_id, "eye:specular") * 0.18,
                dirt=0.0,
                wear=0.0,
                saturation=min(1.0, float(accepted_material["saturation"]) + 0.16),
            ),
            "clothing": _parameters(
                seed=seed,
                descender_id=source.descender_id,
                category="clothing",
                base=clothing_base,
                secondary=clothing_secondary,
                accent=accent,
                roughness=float(accepted_material["cloth_roughness"]),
                specular=0.14 + _unit(seed, source.descender_id, "clothing:specular") * 0.10,
                dirt=float(accepted_material["dirt_amount"]),
                wear=float(accepted_material["cloth_wear"]),
                saturation=float(accepted_material["saturation"]),
            ),
        }

        materials = []
        for category in ("skin", "hair", "eye", "clothing"):
            template = CHARACTER_MATERIAL_TEMPLATES[category]
            materials.append({
                "descender_id": source.descender_id,
                "species": dna.species,
                "category": category,
                "base_material_path": BASE_MATERIAL_PATH,
                "template_material_path": template["material_instance_path"],
                "material_instance_path": _instance_path(source.descender_id, category),
                "runtime_application": "skeletal_mesh_component_material_override_by_slot_category",
                "parameters": categories[category],
            })

        entries.append({
            "descender_id": source.descender_id,
            "species": dna.species,
            "visual_variant": source.visual_variant,
            "style_profile": style,
            "character_dna_digest": dna.digest(),
            "visual_identity_digest": source.visual_identity_digest,
            "renderer_manifest_digest": source.renderer_manifest.digest(),
            "source_body_mesh_path": body_mesh,
            "actor_scale": source.renderer_manifest.actor_scale,
            "stride_scale": source.renderer_manifest.stride_scale,
            "foot_ik_offset_cm": source.renderer_manifest.foot_ik_offset_cm,
            "facial_contract": list(source.renderer_manifest.facial_contract),
            "appearance_source": {
                "skin_variant": dna.skin_variant,
                "eye_variant": dna.eye_variant,
                "hair_asset": dna.appearance.current_hair_asset,
                "facial_hair_asset": dna.appearance.facial_hair_asset,
                "clothing_asset_ids": list(dna.appearance.clothing_asset_ids),
            },
            "accepted_visual_material_parameters": dict(accepted_material),
            "source_29e3_equipment_digest": _digest(equipment_entry),
            "character_materials": materials,
        })

    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "character_dna_mutation_allowed": False,
        "canonical_inventory_mutation_allowed": False,
        "combat_timing_mutation_allowed": False,
        "animation_binding_mutation_allowed": False,
        "skeletal_mesh_binding_mutation_allowed": False,
        "equipment_binding_mutation_allowed": False,
        "base_material_path": BASE_MATERIAL_PATH,
        "character_material_templates": CHARACTER_MATERIAL_TEMPLATES,
        "character_material_template_count": len(CHARACTER_MATERIAL_TEMPLATES),
        "source_29e3_digest": equipment["digest"],
        "source_29e2_digest": equipment["source_29e2_digest"],
        "source_29e1_digest": visual["digest"],
        "source_population_digest": population.population_digest,
        "asset_registry_digest": population.asset_registry_digest,
        "population_count": len(entries),
        "material_directive_count": sum(len(entry["character_materials"]) for entry in entries),
        "entries": entries,
    }
    manifest["digest"] = _digest(manifest)
    validate_character_material_appearance_manifest(manifest)
    return manifest


def validate_character_material_appearance_manifest(manifest: dict[str, Any]) -> bool:
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29E.4 protocol/authority invalid")
    for key in (
        "character_dna_mutation_allowed",
        "canonical_inventory_mutation_allowed",
        "combat_timing_mutation_allowed",
        "animation_binding_mutation_allowed",
        "skeletal_mesh_binding_mutation_allowed",
        "equipment_binding_mutation_allowed",
    ):
        if manifest.get(key) is not False:
            raise ValueError(f"29E.4 authority boundary violated: {key}")
    if manifest.get("base_material_path") != BASE_MATERIAL_PATH:
        raise ValueError("29E.4 base material path changed")
    if manifest.get("character_material_templates") != CHARACTER_MATERIAL_TEMPLATES:
        raise ValueError("29E.4 material template hierarchy changed")
    if int(manifest.get("character_material_template_count", -1)) != 4:
        raise ValueError("29E.4 requires exactly four material templates")

    entries = manifest.get("entries") or []
    if len(entries) != int(manifest.get("population_count", -1)) or len(entries) < 8:
        raise ValueError("29E.4 population count invalid")
    if int(manifest.get("material_directive_count", -1)) != len(entries) * 4:
        raise ValueError("29E.4 requires four material directives per Descender")

    ids: set[str] = set()
    instances: set[str] = set()
    species: set[str] = set()
    skin_variants: set[str] = set()
    eye_variants: set[str] = set()
    hair_fingerprints: set[str] = set()
    clothing_fingerprints: set[str] = set()
    all_fingerprints: set[str] = set()

    for entry in entries:
        did = str(entry.get("descender_id", ""))
        if not did or did in ids:
            raise ValueError("29E.4 duplicate/empty Descender identity")
        ids.add(did)
        species.add(str(entry.get("species", "")))
        variant = str(entry.get("visual_variant", ""))
        if entry.get("source_body_mesh_path") != BODY_MESHES.get(variant):
            raise ValueError("29E.4 accepted skeletal mesh binding changed")
        if not entry.get("character_dna_digest") or not entry.get("visual_identity_digest") or not entry.get("renderer_manifest_digest"):
            raise ValueError("29E.4 identity provenance incomplete")
        if float(entry.get("actor_scale", 0.0)) <= 0.0 or float(entry.get("stride_scale", 0.0)) <= 0.0:
            raise ValueError("29E.4 accepted body/stride scale invalid")
        if len(entry.get("facial_contract") or []) < 10:
            raise ValueError("29E.4 facial contract was not preserved")

        appearance = entry.get("appearance_source") or {}
        skin_variants.add(str(appearance.get("skin_variant", "")))
        eye_variants.add(str(appearance.get("eye_variant", "")))
        if appearance.get("skin_variant") not in SKIN_TONES or appearance.get("eye_variant") not in EYE_TONES:
            raise ValueError("29E.4 appearance source variant invalid")
        if not appearance.get("hair_asset") or not appearance.get("clothing_asset_ids"):
            raise ValueError("29E.4 hair/clothing source identity missing")

        materials = entry.get("character_materials") or []
        if {item.get("category") for item in materials} != {"skin", "hair", "eye", "clothing"}:
            raise ValueError("29E.4 material category coverage incomplete")
        for item in materials:
            category = str(item.get("category"))
            if item.get("base_material_path") != BASE_MATERIAL_PATH:
                raise ValueError("29E.4 material directive changed master material")
            if item.get("template_material_path") != CHARACTER_MATERIAL_TEMPLATES[category]["material_instance_path"]:
                raise ValueError("29E.4 material directive changed template parent")
            instance = str(item.get("material_instance_path", ""))
            if not instance or instance in instances:
                raise ValueError("29E.4 material instance identity collision")
            instances.add(instance)
            if item.get("runtime_application") != "skeletal_mesh_component_material_override_by_slot_category":
                raise ValueError("29E.4 runtime material application contract changed")
            params = item.get("parameters") or {}
            for color_name in ("base_tint", "secondary_tint", "accent_tint"):
                color = params.get(color_name) or {}
                for channel in ("r", "g", "b", "a"):
                    if not 0.0 <= float(color.get(channel, -1.0)) <= 1.0:
                        raise ValueError(f"29E.4 color parameter out of bounds: {color_name}.{channel}")
            for name in (
                "roughness", "specular", "metallic", "dirt_amount", "wear_amount",
                "saturation", "material_variation_seed", "secondary_mix", "accent_mix",
            ):
                if not 0.0 <= float(params.get(name, -1.0)) <= 1.0:
                    raise ValueError(f"29E.4 material parameter out of bounds: {name}")
            if not 0.90 <= float(params.get("value_variation", 0.0)) <= 1.10:
                raise ValueError("29E.4 value variation out of bounds")
            if float(params.get("metallic", -1.0)) != 0.0:
                raise ValueError("29E.4 organic/cloth materials must remain non-metallic")
            fingerprint = _digest(params)
            all_fingerprints.add(fingerprint)
            if category == "hair":
                hair_fingerprints.add(fingerprint)
            if category == "clothing":
                clothing_fingerprints.add(fingerprint)

    if species != {"human", "dwarf"}:
        raise ValueError("29E.4 proof must cover Human and Dwarf Descenders")
    if len(skin_variants) < 3 or len(eye_variants) < 2:
        raise ValueError("29E.4 skin/eye deterministic variation collapsed")
    if len(hair_fingerprints) < min(4, len(entries)):
        raise ValueError("29E.4 hair material variation collapsed")
    if len(clothing_fingerprints) < min(4, len(entries)):
        raise ValueError("29E.4 clothing material variation collapsed")
    if len(all_fingerprints) < min(12, len(entries) * 2):
        raise ValueError("29E.4 overall material variation collapsed")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29E.4 digest mismatch")
    return True