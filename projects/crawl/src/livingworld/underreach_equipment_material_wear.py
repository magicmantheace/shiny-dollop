"""Underreach Slice 29E.3 equipment material and wear realization.

Presentation-only layer that converts the accepted 29E.1 material identity data
and accepted 29E.2 real equipment mesh bindings into deterministic per-Descender
Unreal material-instance directives. It does not alter Character DNA, canonical
inventory, combat timing, mesh attachment contracts, or Ledger truth.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

from .underreach_equipment_asset_integration import (
    EQUIPMENT_ASSETS,
    build_real_equipment_integration_manifest,
)

PROTOCOL = "underreach.equipment-material-wear-realization.v1"
GENERATOR_VERSION = "29e3.2"
SOURCE_PROTOCOL = "underreach.real-equipment-asset-integration.v1"
DEFAULT_SEED = "underreach-29e3-equipment-material-wear-proof"
MATERIAL_ROOT = "/Game/Underreach29E3/Materials"
BASE_MATERIAL_PATH = f"{MATERIAL_ROOT}/M_UR_Equipment_Master.M_UR_Equipment_Master"

ACCENT_PALETTE: tuple[tuple[float, float, float], ...] = (
    (0.32, 0.16, 0.08),
    (0.12, 0.22, 0.34),
    (0.26, 0.28, 0.16),
    (0.34, 0.22, 0.12),
    (0.22, 0.14, 0.28),
    (0.16, 0.30, 0.28),
    (0.34, 0.30, 0.20),
    (0.24, 0.24, 0.26),
)

STYLE_TONES: dict[str, dict[str, tuple[float, float, float]]] = {
    "earth_survivor": {
        "metal": (0.38, 0.34, 0.28),
        "leather": (0.25, 0.13, 0.07),
    },
    "rugged": {
        "metal": (0.30, 0.28, 0.25),
        "leather": (0.19, 0.09, 0.05),
    },
    "practical": {
        "metal": (0.42, 0.43, 0.44),
        "leather": (0.27, 0.16, 0.09),
    },
    "armored": {
        "metal": (0.48, 0.50, 0.52),
        "leather": (0.21, 0.12, 0.08),
    },
    "lightweight": {
        "metal": (0.37, 0.40, 0.43),
        "leather": (0.29, 0.18, 0.10),
    },
}

ITEM_MATERIAL_TEMPLATES: dict[str, dict[str, Any]] = {
    "underreach.weapon.sword.v1": {
        "material_instance_path": f"{MATERIAL_ROOT}/Items/MI_UR_Sword_01.MI_UR_Sword_01",
        "leather_mix": 0.18,
        "metallic": 0.90,
    },
    "underreach.armor.helmet.v1": {
        "material_instance_path": f"{MATERIAL_ROOT}/Items/MI_UR_Helmet_01.MI_UR_Helmet_01",
        "leather_mix": 0.04,
        "metallic": 0.84,
    },
    "underreach.armor.breastplate.v1": {
        "material_instance_path": f"{MATERIAL_ROOT}/Items/MI_UR_Breastplate_01.MI_UR_Breastplate_01",
        "leather_mix": 0.06,
        "metallic": 0.86,
    },
}

EXPECTED_BONES = {
    "underreach.weapon.sword.v1": "hand_r",
    "underreach.armor.helmet.v1": "head",
    "underreach.armor.breastplate.v1": "spine_03",
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(manifest: dict[str, Any]) -> str:
    value = deepcopy(manifest)
    value.pop("digest", None)
    return _digest(value)


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() else "_" for ch in value)


def _unit(seed: str, descender_id: str, visual_id: str, label: str) -> float:
    raw = sha256(
        f"{GENERATOR_VERSION}:{seed}:{descender_id}:{visual_id}:{label}".encode("utf-8")
    ).digest()
    return int.from_bytes(raw[:8], "big") / float(2**64 - 1)


def _color_payload(color: tuple[float, float, float]) -> dict[str, float]:
    return {
        "r": round(max(0.0, min(1.0, color[0])), 4),
        "g": round(max(0.0, min(1.0, color[1])), 4),
        "b": round(max(0.0, min(1.0, color[2])), 4),
        "a": 1.0,
    }


def _apply_saturation(
    color: tuple[float, float, float], saturation: float
) -> tuple[float, float, float]:
    saturation = max(0.0, min(1.0, saturation))
    gray = sum(color) / 3.0
    return tuple(gray + (channel - gray) * saturation for channel in color)


def _material_values(
    *,
    seed: str,
    descender_id: str,
    style_profile: str,
    material: dict[str, Any],
    visual_id: str,
) -> dict[str, Any]:
    if style_profile not in STYLE_TONES:
        raise ValueError(f"29E.3 unknown style profile: {style_profile}")
    template = ITEM_MATERIAL_TEMPLATES.get(visual_id)
    if template is None:
        raise ValueError(f"29E.3 has no item material template for {visual_id}")

    accent_index = int(material.get("accent_index", 0)) % len(ACCENT_PALETTE)
    saturation = max(0.0, min(1.0, float(material.get("saturation", 0.7))))
    tones = STYLE_TONES[style_profile]
    accent = _apply_saturation(ACCENT_PALETTE[accent_index], saturation)

    dirt = max(0.0, min(1.0, float(material.get("dirt_amount", 0.0))))
    wear = max(0.0, min(1.0, float(material.get("metal_wear", 0.0))))
    metal_roughness = max(0.0, min(1.0, float(material.get("metal_roughness", 0.5))))
    leather_roughness = max(0.0, min(1.0, float(material.get("leather_roughness", 0.65))))
    leather_mix = float(template["leather_mix"])

    material_variation_seed = _unit(
        seed, descender_id, visual_id, "material_variation_seed"
    )
    value_variation = 0.92 + _unit(
        seed, descender_id, visual_id, "value_variation"
    ) * 0.16
    edge_wear = max(
        0.03,
        min(
            0.78,
            0.08
            + wear * 0.70
            + _unit(seed, descender_id, visual_id, "edge_wear") * 0.16,
        ),
    )

    roughness = metal_roughness * (1.0 - leather_mix) + leather_roughness * leather_mix
    roughness = max(0.16, min(0.90, roughness + dirt * 0.12 + wear * 0.06))
    accent_mix = max(0.04, min(0.20, 0.05 + saturation * 0.10))
    metallic = float(template["metallic"])

    return {
        "metal_tint": _color_payload(tones["metal"]),
        "leather_tint": _color_payload(tones["leather"]),
        "accent_tint": _color_payload(accent),
        "roughness": round(roughness, 4),
        "metallic": round(metallic, 4),
        "wear_amount": round(wear, 4),
        "dirt_amount": round(dirt, 4),
        "edge_wear": round(edge_wear, 4),
        "leather_mix": round(leather_mix, 4),
        "accent_mix": round(accent_mix, 4),
        "saturation": round(saturation, 4),
        "value_variation": round(value_variation, 4),
        "material_variation_seed": round(material_variation_seed, 6),
        "accent_index": accent_index,
    }


def build_equipment_material_wear_manifest(
    seed: str = DEFAULT_SEED, count: int = 24
) -> dict[str, Any]:
    source = build_real_equipment_integration_manifest(seed=seed, count=count)
    entries: list[dict[str, Any]] = []
    directive_count = 0

    for source_entry in source["entries"]:
        directives = []
        material = deepcopy(source_entry["material_parameters"])
        style_profile = str(source_entry["style_profile"])
        for item in source_entry["equipment"]:
            slot = str(item["slot"])
            visual_id = str(item["visual_id"])
            instance_name = (
                f"MI_UR_{_safe_name(source_entry['descender_id'])}_{_safe_name(slot)}"
            )
            values = _material_values(
                seed=seed,
                descender_id=str(source_entry["descender_id"]),
                style_profile=style_profile,
                material=material,
                visual_id=visual_id,
            )
            template = ITEM_MATERIAL_TEMPLATES[visual_id]
            directives.append(
                {
                    "descender_id": source_entry["descender_id"],
                    "species": source_entry["species"],
                    "style_profile": style_profile,
                    "visual_id": visual_id,
                    "slot": slot,
                    "attachment_bone": item["attachment_bone"],
                    "attachment_mode": item["attachment_mode"],
                    "presentation_scale": deepcopy(item["presentation_scale"]),
                    "mesh_asset_path": item["unreal_asset_path"],
                    "source_29e2_material_instance_path": item[
                        "material_instance_path"
                    ],
                    "item_material_template_path": template[
                        "material_instance_path"
                    ],
                    "material_instance_path": (
                        f"{MATERIAL_ROOT}/Descenders/{instance_name}.{instance_name}"
                    ),
                    "base_material_path": BASE_MATERIAL_PATH,
                    "runtime_application": "static_mesh_component_material_override",
                    "parameters": values,
                    "source_material_parameters": deepcopy(material),
                    "quality_tier": "production_candidate",
                    "final_art_required": True,
                    "authoritative": False,
                }
            )
            directive_count += 1

        entries.append(
            {
                "descender_id": source_entry["descender_id"],
                "species": source_entry["species"],
                "style_profile": style_profile,
                "visual_identity_digest": source_entry["visual_identity_digest"],
                "renderer_manifest_digest": source_entry["renderer_manifest_digest"],
                "equipment_materials": directives,
            }
        )

    item_templates = {
        visual_id: deepcopy(spec)
        for visual_id, spec in sorted(ITEM_MATERIAL_TEMPLATES.items())
    }
    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "canonical_inventory_mutation_allowed": False,
        "character_dna_mutation_allowed": False,
        "combat_timing_mutation_allowed": False,
        "mesh_binding_mutation_allowed": False,
        "source_protocol": SOURCE_PROTOCOL,
        "source_29e2_digest": source["digest"],
        "source_29e1_digest": source["source_29e1_digest"],
        "source_population_digest": source["source_population_digest"],
        "asset_registry_digest": source["asset_registry_digest"],
        "population_count": len(entries),
        "material_directive_count": directive_count,
        "base_material_path": BASE_MATERIAL_PATH,
        "item_material_template_count": len(item_templates),
        "item_material_templates": item_templates,
        "runtime_policy": (
            "master material -> item template -> per-Descender MaterialInstanceConstant; "
            "all application is a presentation-only StaticMeshComponent override and "
            "shared 29E.2 StaticMesh assets remain immutable"
        ),
        "entries": entries,
    }
    manifest["digest"] = _digest(manifest)
    validate_equipment_material_wear_manifest(manifest)
    return manifest


def validate_equipment_material_wear_manifest(manifest: dict[str, Any]) -> bool:
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29E.3 protocol/authority invalid")
    for key in (
        "canonical_inventory_mutation_allowed",
        "character_dna_mutation_allowed",
        "combat_timing_mutation_allowed",
        "mesh_binding_mutation_allowed",
    ):
        if manifest.get(key) is not False:
            raise ValueError(f"29E.3 authority boundary violated: {key}")

    if manifest.get("base_material_path") != BASE_MATERIAL_PATH:
        raise ValueError("29E.3 base material path changed")
    templates = manifest.get("item_material_templates") or {}
    if (
        int(manifest.get("item_material_template_count", -1)) != 3
        or set(templates) != set(ITEM_MATERIAL_TEMPLATES)
    ):
        raise ValueError("29E.3 item material template contract invalid")
    for visual_id, expected in ITEM_MATERIAL_TEMPLATES.items():
        actual = templates.get(visual_id) or {}
        if actual != expected:
            raise ValueError("29E.3 item material template binding changed")

    entries = manifest.get("entries") or []
    if len(entries) != int(manifest.get("population_count", -1)) or len(entries) < 4:
        raise ValueError("29E.3 population count invalid")

    directives = [
        item for entry in entries for item in (entry.get("equipment_materials") or [])
    ]
    if (
        len(directives) != int(manifest.get("material_directive_count", -1))
        or not directives
    ):
        raise ValueError("29E.3 material directive count mismatch")

    instance_paths: set[str] = set()
    fingerprints: set[str] = set()
    style_profiles: set[str] = set()
    expected_mesh_paths = {
        visual_id: spec["unreal_asset_path"]
        for visual_id, spec in EQUIPMENT_ASSETS.items()
    }

    for item in directives:
        if (
            item.get("authoritative") is not False
            or item.get("quality_tier") != "production_candidate"
            or item.get("final_art_required") is not True
        ):
            raise ValueError("29E.3 material maturity/authority invalid")
        if item.get("runtime_application") != "static_mesh_component_material_override":
            raise ValueError("29E.3 runtime material application contract changed")

        visual_id = str(item.get("visual_id", ""))
        if item.get("attachment_bone") != EXPECTED_BONES.get(visual_id):
            raise ValueError("29E.3 attachment bone changed")
        if item.get("mesh_asset_path") != expected_mesh_paths.get(visual_id):
            raise ValueError("29E.3 real mesh binding changed")
        if (
            item.get("item_material_template_path")
            != ITEM_MATERIAL_TEMPLATES.get(visual_id, {}).get(
                "material_instance_path"
            )
        ):
            raise ValueError("29E.3 item material template binding changed")
        if not item.get("source_29e2_material_instance_path"):
            raise ValueError("29E.3 lost accepted 29E.2 material provenance")

        scale = item.get("presentation_scale") or {}
        if any(
            not 0.70 <= float(scale.get(axis, 0.0)) <= 1.20
            for axis in ("x", "y", "z")
        ):
            raise ValueError("29E.3 presentation fit scale exceeded accepted bounds")

        style_profile = str(item.get("style_profile", ""))
        if style_profile not in STYLE_TONES:
            raise ValueError("29E.3 style profile lost or unknown")
        style_profiles.add(style_profile)

        path = str(item.get("material_instance_path", ""))
        if not path or path in instance_paths:
            raise ValueError("29E.3 material instance identity collision")
        instance_paths.add(path)

        params = item.get("parameters") or {}
        for color_name in ("metal_tint", "leather_tint", "accent_tint"):
            color = params.get(color_name) or {}
            for channel in ("r", "g", "b", "a"):
                if not 0.0 <= float(color.get(channel, -1.0)) <= 1.0:
                    raise ValueError(f"29E.3 {color_name} out of bounds")

        for key in (
            "roughness",
            "metallic",
            "wear_amount",
            "dirt_amount",
            "edge_wear",
            "leather_mix",
            "accent_mix",
            "saturation",
            "material_variation_seed",
        ):
            if not 0.0 <= float(params.get(key, -1.0)) <= 1.0:
                raise ValueError(f"29E.3 parameter out of bounds: {key}")
        if not 0.88 <= float(params.get("value_variation", 0.0)) <= 1.12:
            raise ValueError("29E.3 value variation out of bounds")
        if float(params["roughness"]) < 0.12 or float(params["roughness"]) > 0.92:
            raise ValueError("29E.3 roughness left stylistic bounds")
        if float(params["metallic"]) < 0.70:
            raise ValueError("29E.3 metal equipment became implausibly non-metallic")
        fingerprints.add(_digest(params))

    if len(fingerprints) < min(8, len(directives)):
        raise ValueError("29E.3 material/wear variation collapsed")
    if len(style_profiles) < 2:
        raise ValueError("29E.3 style/archetype variation collapsed")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29E.3 digest mismatch")
    return True
