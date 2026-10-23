"""Underreach Slice 29E.5 equipment/character combat integration.

This presentation-only layer combines the accepted 29E.4 character appearance
state with the accepted 29E.3 real equipment/material state and binds both to
the existing variant-native Underreach combat clips. It never changes Character
DNA, canonical inventory, combat timing, damage, death, animation outcomes, or
Ledger truth.
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
from .underreach_equipment_material_wear import build_equipment_material_wear_manifest

PROTOCOL = "underreach.equipment-character-combat-integration.v1"
GENERATOR_VERSION = "29e5.1"
SOURCE_COMBAT_PROTOCOL = "underreach.combat-motion-polish.v1"
MAX_ATTACHMENT_DRIFT_CM = 0.05
MAX_ATTACHMENT_ROTATION_DRIFT_DEGREES = 0.25

VARIANT_ASSET_STEMS = {
    "human_average": "UnderreachHuman",
    "human_short_heavy": "UnderreachHumanShortHeavy",
    "human_tall_thin": "UnderreachHumanTallThin",
    "dwarf_average": "UnderreachDwarf",
    "dwarf_heavy": "UnderreachDwarfHeavy",
    "dwarf_alt": "UnderreachDwarfAlt",
}

EXPECTED_EQUIPMENT_BINDINGS = {
    "underreach.weapon.sword.v1": ("right_hand", "hand_r"),
    "underreach.armor.helmet.v1": ("head_armor", "head"),
    "underreach.armor.breastplate.v1": ("chest_armor", "spine_03"),
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(manifest: dict[str, Any]) -> str:
    value = deepcopy(manifest)
    value.pop("digest", None)
    return _digest(value)


def animation_assets_for_variant(variant: str) -> dict[str, str]:
    stem = VARIANT_ASSET_STEMS.get(variant)
    if stem is None:
        raise ValueError(f"29E.5 has no accepted animation family for {variant}")
    root = "/Game/Underreach29A1/Characters"
    return {
        "attack": f"{root}/A_{stem}_Attack.A_{stem}_Attack",
        "hit_reaction": f"{root}/A_{stem}_Reaction.A_{stem}_Reaction",
        "death": f"{root}/A_{stem}_Death.A_{stem}_Death",
    }


def build_equipment_character_combat_integration_manifest(
    seed: str = DEFAULT_SEED,
    count: int = 24,
) -> dict[str, Any]:
    if count < 8:
        raise ValueError("29E.5 proof requires at least eight Descenders")

    character = build_character_material_appearance_manifest(seed=seed, count=count)
    equipment = build_equipment_material_wear_manifest(seed=seed, count=count)
    if character["source_29e3_digest"] != equipment["digest"]:
        raise ValueError("29E.5 character/equipment source chain diverged")
    if character["source_population_digest"] != equipment["source_population_digest"]:
        raise ValueError("29E.5 character/equipment population diverged")

    equipment_by_id = {entry["descender_id"]: entry for entry in equipment["entries"]}
    entries: list[dict[str, Any]] = []
    directive_count = 0

    for char in character["entries"]:
        eq_entry = equipment_by_id[char["descender_id"]]
        animation_assets = animation_assets_for_variant(char["visual_variant"])
        integrations = []
        persistent_armor_slots = []
        weapon_slots = []

        for item in eq_entry["equipment_materials"]:
            expected = EXPECTED_EQUIPMENT_BINDINGS.get(item["visual_id"])
            if expected is None:
                raise ValueError(f"29E.5 unknown equipment visual ID {item['visual_id']}")
            expected_slot, expected_bone = expected
            if item["slot"] != expected_slot or item["attachment_bone"] != expected_bone:
                raise ValueError("29E.5 accepted equipment slot/bone binding changed")
            is_weapon = item["visual_id"] == "underreach.weapon.sword.v1"
            is_armor = item["visual_id"] in {
                "underreach.armor.helmet.v1",
                "underreach.armor.breastplate.v1",
            }
            if is_weapon:
                weapon_slots.append(item["slot"])
            if is_armor:
                persistent_armor_slots.append(item["slot"])
            integrations.append({
                "visual_id": item["visual_id"],
                "slot": item["slot"],
                "mesh_asset_path": item["mesh_asset_path"],
                "material_instance_path": item["material_instance_path"],
                "attachment_bone": item["attachment_bone"],
                "attachment_mode": item["attachment_mode"],
                "presentation_scale": deepcopy(item["presentation_scale"]),
                "runtime_policy": "skeletal_bone_follow_no_world_space_detach",
                "weapon_hand_alignment_required": is_weapon,
                "reaction_death_persistence_required": is_armor,
                "max_relative_translation_drift_cm": MAX_ATTACHMENT_DRIFT_CM,
                "max_relative_rotation_drift_degrees": MAX_ATTACHMENT_ROTATION_DRIFT_DEGREES,
            })
            directive_count += 1

        entries.append({
            "descender_id": char["descender_id"],
            "species": char["species"],
            "visual_variant": char["visual_variant"],
            "style_profile": char["style_profile"],
            "character_dna_digest": char["character_dna_digest"],
            "visual_identity_digest": char["visual_identity_digest"],
            "renderer_manifest_digest": char["renderer_manifest_digest"],
            "source_body_mesh_path": char["source_body_mesh_path"],
            "actor_scale": char["actor_scale"],
            "stride_scale": char["stride_scale"],
            "foot_ik_offset_cm": char["foot_ik_offset_cm"],
            "animation_assets": animation_assets,
            "combat_states": {
                "attack": {
                    "animation_asset_path": animation_assets["attack"],
                    "weapon_slots": weapon_slots,
                    "weapon_attachment_bone": "hand_r",
                    "alignment_policy": "weapon_component_follows_animated_hand_r_bone",
                },
                "hit_reaction": {
                    "animation_asset_path": animation_assets["hit_reaction"],
                    "persistent_armor_slots": persistent_armor_slots,
                    "attachment_policy": "armor_remains_bone_attached_through_reaction",
                },
                "death": {
                    "animation_asset_path": animation_assets["death"],
                    "persistent_armor_slots": persistent_armor_slots,
                    "attachment_policy": "armor_remains_bone_attached_through_terminal_pose",
                },
            },
            "equipment_integrations": integrations,
        })

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
        "source_29e4_digest": character["digest"],
        "source_29e3_digest": equipment["digest"],
        "source_29e2_digest": character["source_29e2_digest"],
        "source_29e1_digest": character["source_29e1_digest"],
        "source_population_digest": character["source_population_digest"],
        "asset_registry_digest": character["asset_registry_digest"],
        "source_combat_protocol": SOURCE_COMBAT_PROTOCOL,
        "combat_integration_policy": (
            "29E.5 consumes accepted combat presentation semantics and validates "
            "variant-native Underreach Attack/Reaction/Death clips; presentation "
            "may never alter simulation timing or outcomes"
        ),
        "max_attachment_drift_cm": MAX_ATTACHMENT_DRIFT_CM,
        "max_attachment_rotation_drift_degrees": MAX_ATTACHMENT_ROTATION_DRIFT_DEGREES,
        "population_count": len(entries),
        "equipment_integration_directive_count": directive_count,
        "entries": entries,
    }
    manifest["digest"] = _digest(manifest)
    validate_equipment_character_combat_integration_manifest(manifest)
    return manifest


def validate_equipment_character_combat_integration_manifest(manifest: dict[str, Any]) -> bool:
    if manifest.get("protocol") != PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29E.5 protocol/authority invalid")
    for key in (
        "canonical_inventory_mutation_allowed",
        "character_dna_mutation_allowed",
        "combat_timing_mutation_allowed",
        "combat_outcome_mutation_allowed",
        "animation_asset_mutation_allowed",
        "skeletal_mesh_binding_mutation_allowed",
    ):
        if manifest.get(key) is not False:
            raise ValueError(f"29E.5 authority boundary violated: {key}")
    if manifest.get("source_combat_protocol") != SOURCE_COMBAT_PROTOCOL:
        raise ValueError("29E.5 combat presentation contract changed")

    entries = manifest.get("entries") or []
    if len(entries) != int(manifest.get("population_count", -1)) or len(entries) < 8:
        raise ValueError("29E.5 population count invalid")
    ids: set[str] = set()
    species: set[str] = set()
    variants: set[str] = set()
    visuals: set[str] = set()
    directive_count = 0

    for entry in entries:
        did = str(entry.get("descender_id", ""))
        if not did or did in ids:
            raise ValueError("29E.5 duplicate/empty Descender identity")
        ids.add(did)
        species.add(str(entry.get("species", "")))
        variant = str(entry.get("visual_variant", ""))
        variants.add(variant)
        expected_animations = animation_assets_for_variant(variant)
        if entry.get("animation_assets") != expected_animations:
            raise ValueError("29E.5 variant-native combat animation binding changed")
        if not entry.get("source_body_mesh_path") or float(entry.get("actor_scale", 0.0)) <= 0.0:
            raise ValueError("29E.5 character mesh/scale provenance missing")

        states = entry.get("combat_states") or {}
        if set(states) != {"attack", "hit_reaction", "death"}:
            raise ValueError("29E.5 combat state coverage incomplete")
        for state, path_key in (("attack", "attack"), ("hit_reaction", "hit_reaction"), ("death", "death")):
            if states[state].get("animation_asset_path") != expected_animations[path_key]:
                raise ValueError("29E.5 combat state animation mismatch")

        slots: set[str] = set()
        for item in entry.get("equipment_integrations") or []:
            directive_count += 1
            visuals.add(str(item.get("visual_id", "")))
            expected = EXPECTED_EQUIPMENT_BINDINGS.get(item.get("visual_id"))
            if expected is None:
                raise ValueError("29E.5 unknown integrated equipment")
            expected_slot, expected_bone = expected
            if item.get("slot") != expected_slot or item.get("attachment_bone") != expected_bone:
                raise ValueError("29E.5 equipment attachment binding changed")
            if expected_slot in slots:
                raise ValueError("29E.5 duplicate equipment slot")
            slots.add(expected_slot)
            if not item.get("mesh_asset_path") or not item.get("material_instance_path"):
                raise ValueError("29E.5 equipment mesh/material binding missing")
            if item.get("runtime_policy") != "skeletal_bone_follow_no_world_space_detach":
                raise ValueError("29E.5 equipment runtime attachment policy changed")
            scale = item.get("presentation_scale") or {}
            if any(not 0.70 <= float(scale.get(axis, 0.0)) <= 1.20 for axis in ("x", "y", "z")):
                raise ValueError("29E.5 equipment fit scale out of bounds")
            if float(item.get("max_relative_translation_drift_cm", 99.0)) > MAX_ATTACHMENT_DRIFT_CM:
                raise ValueError("29E.5 attachment translation drift budget expanded")
            if float(item.get("max_relative_rotation_drift_degrees", 99.0)) > MAX_ATTACHMENT_ROTATION_DRIFT_DEGREES:
                raise ValueError("29E.5 attachment rotation drift budget expanded")
            if item["visual_id"] == "underreach.weapon.sword.v1" and item.get("weapon_hand_alignment_required") is not True:
                raise ValueError("29E.5 weapon-hand alignment requirement missing")
            if item["visual_id"] in {"underreach.armor.helmet.v1", "underreach.armor.breastplate.v1"} and item.get("reaction_death_persistence_required") is not True:
                raise ValueError("29E.5 armor reaction/death persistence requirement missing")

    if directive_count != int(manifest.get("equipment_integration_directive_count", -1)) or directive_count <= 0:
        raise ValueError("29E.5 equipment integration directive count mismatch")
    if species != {"human", "dwarf"} or len(variants) < 4:
        raise ValueError("29E.5 Human/Dwarf body-variant coverage collapsed")
    if visuals != set(EXPECTED_EQUIPMENT_BINDINGS):
        raise ValueError("29E.5 proof must cover sword, helmet, and breastplate")
    if manifest.get("digest") != rebuild_digest(manifest):
        raise ValueError("29E.5 digest mismatch")
    return True
