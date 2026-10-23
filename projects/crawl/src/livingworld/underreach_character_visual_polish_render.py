"""Underreach Slice 29E.6 character visual polish and render proof.

This presentation-only layer freezes the final Phase-29 character/equipment
render plan. It consumes the accepted 29E.5 equipment/character combat
integration and 29E.4 character material realization, but never mutates
simulation truth, Character DNA, inventory, combat timing, animation outcomes,
or accepted visual identity.
"""
from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json
from typing import Any

from .underreach_character_material_appearance import (
    DEFAULT_SEED,
    build_character_material_appearance_manifest,
)
from .underreach_equipment_character_combat_integration import (
    EXPECTED_EQUIPMENT_BINDINGS,
    build_equipment_character_combat_integration_manifest,
)

PROTOCOL = "underreach.character-visual-polish-render-proof.v1"
GENERATOR_VERSION = "29e6.1"
RENDER_WIDTH = 1280
RENDER_HEIGHT = 720
CAMERA_DISTANCES_CM = {"near": 750.0, "mid": 1300.0, "far": 2400.0}
MIN_CROWD_DESCENDERS = 10
MIN_CROWD_VARIANTS = 4
MIN_CROWD_STYLES = 4

SHOT_SPECS = (
    {
        "shot_id": "human_hero_near",
        "distance_band": "near",
        "fov_degrees": 38.0,
        "purpose": "full_body_human_material_equipment_evaluation",
    },
    {
        "shot_id": "dwarf_hero_near",
        "distance_band": "near",
        "fov_degrees": 38.0,
        "purpose": "full_body_dwarf_material_equipment_evaluation",
    },
    {
        "shot_id": "mixed_pair_mid",
        "distance_band": "mid",
        "fov_degrees": 46.0,
        "purpose": "human_dwarf_mid_distance_readability",
    },
    {
        "shot_id": "crowd_far",
        "distance_band": "far",
        "fov_degrees": 58.0,
        "purpose": "crowd_distance_diversity_and_silhouette_readability",
    },
)

LIGHTING_RIG = {
    "key": {
        "kind": "point",
        "location_cm": [-320.0, -260.0, 360.0],
        "intensity": 7000.0,
        "attenuation_radius_cm": 2600.0,
        "temperature_k": 5000.0,
    },
    "fill": {
        "kind": "point",
        "location_cm": [-220.0, 360.0, 230.0],
        "intensity": 3800.0,
        "attenuation_radius_cm": 2400.0,
        "temperature_k": 6500.0,
    },
    "rim": {
        "kind": "point",
        "location_cm": [360.0, 0.0, 320.0],
        "intensity": 5200.0,
        "attenuation_radius_cm": 2400.0,
        "temperature_k": 4200.0,
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


def _material_fingerprint(character_entry: dict[str, Any]) -> str:
    payload = []
    for item in sorted(character_entry["character_materials"], key=lambda row: row["category"]):
        params = item["parameters"]
        payload.append(
            {
                "category": item["category"],
                "base_tint": params["base_tint"],
                "secondary_tint": params["secondary_tint"],
                "accent_tint": params["accent_tint"],
                "roughness": params["roughness"],
                "wear_amount": params["wear_amount"],
                "dirt_amount": params["dirt_amount"],
            }
        )
    return _digest(payload)


def _entry_summary(
    integration_entry: dict[str, Any],
    character_entry: dict[str, Any],
) -> dict[str, Any]:
    if integration_entry["descender_id"] != character_entry["descender_id"]:
        raise ValueError("29E.6 source Descender identity mismatch")
    if integration_entry["source_body_mesh_path"] != character_entry["source_body_mesh_path"]:
        raise ValueError("29E.6 source body mesh mismatch")
    materials = {
        item["category"]: item["material_instance_path"]
        for item in character_entry["character_materials"]
    }
    equipment = [
        {
            "visual_id": item["visual_id"],
            "slot": item["slot"],
            "mesh_asset_path": item["mesh_asset_path"],
            "material_instance_path": item["material_instance_path"],
            "attachment_bone": item["attachment_bone"],
            "presentation_scale": deepcopy(item["presentation_scale"]),
        }
        for item in integration_entry["equipment_integrations"]
    ]
    return {
        "descender_id": integration_entry["descender_id"],
        "species": integration_entry["species"],
        "visual_variant": integration_entry["visual_variant"],
        "style_profile": integration_entry["style_profile"],
        "source_body_mesh_path": integration_entry["source_body_mesh_path"],
        "actor_scale": integration_entry["actor_scale"],
        "character_material_paths": materials,
        "character_material_fingerprint": _material_fingerprint(character_entry),
        "equipment": equipment,
    }


def _hero(entries: list[dict[str, Any]], species: str) -> dict[str, Any]:
    candidates = [entry for entry in entries if entry["species"] == species]
    if not candidates:
        raise ValueError(f"29E.6 has no {species} hero candidate")
    return sorted(
        candidates,
        key=lambda entry: (
            -len(entry["equipment"]),
            -len({item["visual_id"] for item in entry["equipment"]}),
            entry["descender_id"],
        ),
    )[0]


def _crowd(entries: list[dict[str, Any]], limit: int = 12) -> list[dict[str, Any]]:
    remaining = list(entries)
    selected: list[dict[str, Any]] = []
    species: set[str] = set()
    variants: set[str] = set()
    styles: set[str] = set()
    visuals: set[str] = set()
    material_fingerprints: set[str] = set()

    while remaining and len(selected) < limit:
        best = None
        best_score = None
        for entry in remaining:
            item_visuals = {item["visual_id"] for item in entry["equipment"]}
            score = (
                50 * int(entry["species"] not in species)
                + 30 * int(entry["visual_variant"] not in variants)
                + 18 * int(entry["style_profile"] not in styles)
                + 14 * len(item_visuals - visuals)
                + 8 * int(entry["character_material_fingerprint"] not in material_fingerprints)
                + len(entry["equipment"])
            )
            key = (score, -int(entry["descender_id"].split("_")[-1]))
            if best_score is None or key > best_score:
                best = entry
                best_score = key
        assert best is not None
        selected.append(best)
        remaining.remove(best)
        species.add(best["species"])
        variants.add(best["visual_variant"])
        styles.add(best["style_profile"])
        visuals.update(item["visual_id"] for item in best["equipment"])
        material_fingerprints.add(best["character_material_fingerprint"])
    return selected


def _shot(
    spec: dict[str, Any],
    descender_ids: list[str],
) -> dict[str, Any]:
    band = spec["distance_band"]
    return {
        **deepcopy(spec),
        "camera_distance_cm": CAMERA_DISTANCES_CM[band],
        "render_width": RENDER_WIDTH,
        "render_height": RENDER_HEIGHT,
        "descender_ids": list(descender_ids),
        "output_file": f"{spec['shot_id']}.png",
    }


def build_character_visual_polish_render_manifest(
    seed: str = DEFAULT_SEED,
    count: int = 24,
) -> dict[str, Any]:
    if count < 12:
        raise ValueError("29E.6 proof requires at least twelve Descenders")

    character = build_character_material_appearance_manifest(seed=seed, count=count)
    integration = build_equipment_character_combat_integration_manifest(seed=seed, count=count)
    if integration["source_29e4_digest"] != character["digest"]:
        raise ValueError("29E.6 does not consume the exact character source used by 29E.5")
    if integration["source_population_digest"] != character["source_population_digest"]:
        raise ValueError("29E.6 source population identity diverged")

    character_by_id = {entry["descender_id"]: entry for entry in character["entries"]}
    entries = [
        _entry_summary(entry, character_by_id[entry["descender_id"]])
        for entry in integration["entries"]
    ]

    human = _hero(entries, "human")
    dwarf = _hero(entries, "dwarf")
    crowd = _crowd(entries, limit=12)
    crowd_ids = [entry["descender_id"] for entry in crowd]
    shots = [
        _shot(SHOT_SPECS[0], [human["descender_id"]]),
        _shot(SHOT_SPECS[1], [dwarf["descender_id"]]),
        _shot(SHOT_SPECS[2], [human["descender_id"], dwarf["descender_id"]]),
        _shot(SHOT_SPECS[3], crowd_ids),
    ]

    manifest = {
        "protocol": PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "canonical_inventory_mutation_allowed": False,
        "character_dna_mutation_allowed": False,
        "combat_timing_mutation_allowed": False,
        "combat_outcome_mutation_allowed": False,
        "animation_asset_mutation_allowed": False,
        "skeletal_mesh_binding_mutation_allowed": False,
        "material_identity_mutation_allowed": False,
        "source_29e5_digest": integration["digest"],
        "source_29e4_digest": character["digest"],
        "source_29e3_digest": integration["source_29e3_digest"],
        "source_29e2_digest": integration["source_29e2_digest"],
        "source_population_digest": integration["source_population_digest"],
        "asset_registry_digest": integration["asset_registry_digest"],
        "population_count": len(entries),
        "render_width": RENDER_WIDTH,
        "render_height": RENDER_HEIGHT,
        "camera_distances_cm": deepcopy(CAMERA_DISTANCES_CM),
        "lighting_rig": deepcopy(LIGHTING_RIG),
        "render_backend": "unreal_scene_capture_2d_offscreen_png",
        "render_authority_policy": "presentation_only_no_canonical_feedback",
        "entries": entries,
        "shots": shots,
        "crowd_descender_count": len(crowd),
        "crowd_unique_species": sorted({entry["species"] for entry in crowd}),
        "crowd_unique_variants": sorted({entry["visual_variant"] for entry in crowd}),
        "crowd_unique_styles": sorted({entry["style_profile"] for entry in crowd}),
        "crowd_unique_material_fingerprint_count": len(
            {entry["character_material_fingerprint"] for entry in crowd}
        ),
        "crowd_equipment_visuals": sorted(
            {item["visual_id"] for entry in crowd for item in entry["equipment"]}
        ),
    }
    manifest["digest"] = _digest(manifest)
    validate_character_visual_polish_render_manifest(manifest)
    return manifest


def validate_character_visual_polish_render_manifest(manifest: dict[str, Any]) -> bool:
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29E.6 protocol/authority invalid")
    for key in (
        "canonical_inventory_mutation_allowed",
        "character_dna_mutation_allowed",
        "combat_timing_mutation_allowed",
        "combat_outcome_mutation_allowed",
        "animation_asset_mutation_allowed",
        "skeletal_mesh_binding_mutation_allowed",
        "material_identity_mutation_allowed",
    ):
        if manifest.get(key) is not False:
            raise ValueError(f"29E.6 authority boundary violated: {key}")

    entries = manifest.get("entries") or []
    if len(entries) != int(manifest.get("population_count", -1)) or len(entries) < 12:
        raise ValueError("29E.6 population coverage invalid")
    if int(manifest.get("render_width", 0)) != RENDER_WIDTH or int(manifest.get("render_height", 0)) != RENDER_HEIGHT:
        raise ValueError("29E.6 render resolution changed")
    if manifest.get("camera_distances_cm") != CAMERA_DISTANCES_CM:
        raise ValueError("29E.6 camera distance contract changed")
    if manifest.get("lighting_rig") != LIGHTING_RIG:
        raise ValueError("29E.6 lighting rig changed")

    by_id = {entry["descender_id"]: entry for entry in entries}
    if len(by_id) != len(entries):
        raise ValueError("29E.6 duplicate Descender identity")
    if {entry["species"] for entry in entries} != {"human", "dwarf"}:
        raise ValueError("29E.6 Human/Dwarf coverage missing")
    for entry in entries:
        if not entry.get("source_body_mesh_path") or float(entry.get("actor_scale", 0.0)) <= 0.0:
            raise ValueError("29E.6 character render binding missing")
        if set(entry.get("character_material_paths") or {}) != {"skin", "hair", "eye", "clothing"}:
            raise ValueError("29E.6 character material coverage incomplete")
        for item in entry.get("equipment") or []:
            expected = EXPECTED_EQUIPMENT_BINDINGS.get(item.get("visual_id"))
            if expected is None:
                raise ValueError("29E.6 unknown equipment visual")
            expected_slot, expected_bone = expected
            if item.get("slot") != expected_slot or item.get("attachment_bone") != expected_bone:
                raise ValueError("29E.6 equipment attachment contract changed")

    shots = manifest.get("shots") or []
    if [shot.get("shot_id") for shot in shots] != [spec["shot_id"] for spec in SHOT_SPECS]:
        raise ValueError("29E.6 render shot set changed")
    for shot, spec in zip(shots, SHOT_SPECS):
        band = spec["distance_band"]
        if shot.get("distance_band") != band or float(shot.get("camera_distance_cm", -1.0)) != CAMERA_DISTANCES_CM[band]:
            raise ValueError("29E.6 camera distance contract changed")
        if int(shot.get("render_width", 0)) != RENDER_WIDTH or int(shot.get("render_height", 0)) != RENDER_HEIGHT:
            raise ValueError("29E.6 per-shot render resolution changed")
        if not shot.get("descender_ids") or any(did not in by_id for did in shot["descender_ids"]):
            raise ValueError("29E.6 shot references unknown Descender")

    human_shot = shots[0]
    dwarf_shot = shots[1]
    pair_shot = shots[2]
    crowd_shot = shots[3]
    if {by_id[did]["species"] for did in human_shot["descender_ids"]} != {"human"}:
        raise ValueError("29E.6 Human hero shot invalid")
    if {by_id[did]["species"] for did in dwarf_shot["descender_ids"]} != {"dwarf"}:
        raise ValueError("29E.6 Dwarf hero shot invalid")
    if {by_id[did]["species"] for did in pair_shot["descender_ids"]} != {"human", "dwarf"}:
        raise ValueError("29E.6 mixed pair shot invalid")

    crowd_entries = [by_id[did] for did in crowd_shot["descender_ids"]]
    if len(crowd_entries) < MIN_CROWD_DESCENDERS:
        raise ValueError("29E.6 crowd render sample too small")
    if {entry["species"] for entry in crowd_entries} != {"human", "dwarf"}:
        raise ValueError("29E.6 crowd species diversity collapsed")
    if len({entry["visual_variant"] for entry in crowd_entries}) < MIN_CROWD_VARIANTS:
        raise ValueError("29E.6 crowd body-variant diversity collapsed")
    if len({entry["style_profile"] for entry in crowd_entries}) < MIN_CROWD_STYLES:
        raise ValueError("29E.6 crowd style diversity collapsed")
    visuals = {item["visual_id"] for entry in crowd_entries for item in entry["equipment"]}
    if visuals != set(EXPECTED_EQUIPMENT_BINDINGS):
        raise ValueError("29E.6 crowd equipment visual coverage incomplete")
    if manifest.get("crowd_equipment_visuals") != sorted(visuals):
        raise ValueError("29E.6 crowd equipment summary mismatch")
    if int(manifest.get("crowd_unique_material_fingerprint_count", 0)) < 8:
        raise ValueError("29E.6 crowd material diversity collapsed")

    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29E.6 digest mismatch")
    return True
