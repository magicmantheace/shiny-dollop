from copy import deepcopy

import pytest

from livingworld.underreach_character_material_appearance import (
    DEFAULT_SEED,
    build_character_material_appearance_manifest,
)
from livingworld.underreach_equipment_material_wear import build_equipment_material_wear_manifest
from livingworld.underreach_equipment_character_combat_integration import (
    EXPECTED_EQUIPMENT_BINDINGS,
    MAX_ATTACHMENT_DRIFT_CM,
    MAX_ATTACHMENT_ROTATION_DRIFT_DEGREES,
    PROTOCOL,
    SOURCE_COMBAT_PROTOCOL,
    VARIANT_ASSET_STEMS,
    animation_assets_for_variant,
    build_equipment_character_combat_integration_manifest,
    rebuild_digest,
    validate_equipment_character_combat_integration_manifest,
)


def _items(manifest):
    return [item for entry in manifest["entries"] for item in entry["equipment_integrations"]]


def test_same_seed_is_exactly_deterministic():
    assert build_equipment_character_combat_integration_manifest() == build_equipment_character_combat_integration_manifest()


def test_different_seed_changes_integrated_identity():
    a = build_equipment_character_combat_integration_manifest("29e5-a", count=40)
    b = build_equipment_character_combat_integration_manifest("29e5-b", count=40)
    assert a["digest"] != b["digest"]
    assert a["source_population_digest"] != b["source_population_digest"]


def test_authority_boundary_is_explicit_and_closed():
    manifest = build_equipment_character_combat_integration_manifest()
    assert manifest["protocol"] == PROTOCOL
    assert manifest["source_combat_protocol"] == SOURCE_COMBAT_PROTOCOL
    assert manifest["authoritative"] is False
    for key in (
        "canonical_inventory_mutation_allowed",
        "character_dna_mutation_allowed",
        "combat_timing_mutation_allowed",
        "combat_outcome_mutation_allowed",
        "animation_asset_mutation_allowed",
        "skeletal_mesh_binding_mutation_allowed",
    ):
        assert manifest[key] is False


def test_exact_29e4_and_29e3_provenance_is_preserved():
    character = build_character_material_appearance_manifest(seed=DEFAULT_SEED, count=24)
    equipment = build_equipment_material_wear_manifest(seed=DEFAULT_SEED, count=24)
    manifest = build_equipment_character_combat_integration_manifest(seed=DEFAULT_SEED, count=24)
    assert manifest["source_29e4_digest"] == character["digest"]
    assert manifest["source_29e3_digest"] == equipment["digest"]
    assert manifest["source_29e3_digest"] == character["source_29e3_digest"]
    assert manifest["source_population_digest"] == character["source_population_digest"]
    assert manifest["asset_registry_digest"] == character["asset_registry_digest"]


def test_all_variant_native_combat_asset_families_are_exact_and_complete():
    # Population DNA is deterministic and is not required to randomly emit every
    # supported body variant for one seed. Validate the complete six-variant
    # asset contract directly; the Unreal proof loads all six families as well.
    assert set(VARIANT_ASSET_STEMS) == {
        "human_average",
        "human_short_heavy",
        "human_tall_thin",
        "dwarf_average",
        "dwarf_heavy",
        "dwarf_alt",
    }
    for variant, stem in VARIANT_ASSET_STEMS.items():
        expected = {
            "attack": f"/Game/Underreach29A1/Characters/A_{stem}_Attack.A_{stem}_Attack",
            "hit_reaction": f"/Game/Underreach29A1/Characters/A_{stem}_Reaction.A_{stem}_Reaction",
            "death": f"/Game/Underreach29A1/Characters/A_{stem}_Death.A_{stem}_Death",
        }
        assert animation_assets_for_variant(variant) == expected

    manifest = build_equipment_character_combat_integration_manifest(count=100)
    assert {entry["species"] for entry in manifest["entries"]} == {"human", "dwarf"}
    assert {entry["visual_variant"] for entry in manifest["entries"]} <= set(VARIANT_ASSET_STEMS)
    for entry in manifest["entries"]:
        expected = animation_assets_for_variant(entry["visual_variant"])
        assert entry["animation_assets"] == expected
        assert entry["combat_states"]["attack"]["animation_asset_path"] == expected["attack"]
        assert entry["combat_states"]["hit_reaction"]["animation_asset_path"] == expected["hit_reaction"]
        assert entry["combat_states"]["death"]["animation_asset_path"] == expected["death"]


def test_equipment_keeps_exact_accepted_slot_bone_mesh_material_and_scale():
    source = build_equipment_material_wear_manifest(seed=DEFAULT_SEED, count=40)
    manifest = build_equipment_character_combat_integration_manifest(seed=DEFAULT_SEED, count=40)
    source_by_id = {entry["descender_id"]: entry for entry in source["entries"]}
    for entry in manifest["entries"]:
        expected_items = {item["slot"]: item for item in source_by_id[entry["descender_id"]]["equipment_materials"]}
        actual_items = {item["slot"]: item for item in entry["equipment_integrations"]}
        assert set(actual_items) == set(expected_items)
        for slot, actual in actual_items.items():
            expected = expected_items[slot]
            assert actual["mesh_asset_path"] == expected["mesh_asset_path"]
            assert actual["material_instance_path"] == expected["material_instance_path"]
            assert actual["attachment_bone"] == expected["attachment_bone"]
            assert actual["attachment_mode"] == expected["attachment_mode"]
            assert actual["presentation_scale"] == expected["presentation_scale"]


def test_weapon_alignment_and_armor_persistence_contracts_are_explicit():
    manifest = build_equipment_character_combat_integration_manifest(count=40)
    items = _items(manifest)
    assert {item["visual_id"] for item in items} == set(EXPECTED_EQUIPMENT_BINDINGS)
    swords = [item for item in items if item["visual_id"] == "underreach.weapon.sword.v1"]
    armor = [item for item in items if item["visual_id"] != "underreach.weapon.sword.v1"]
    assert swords and armor
    assert all(item["attachment_bone"] == "hand_r" and item["weapon_hand_alignment_required"] is True for item in swords)
    assert all(item["reaction_death_persistence_required"] is True for item in armor)
    assert all(item["runtime_policy"] == "skeletal_bone_follow_no_world_space_detach" for item in items)
    assert all(item["max_relative_translation_drift_cm"] <= MAX_ATTACHMENT_DRIFT_CM for item in items)
    assert all(item["max_relative_rotation_drift_degrees"] <= MAX_ATTACHMENT_ROTATION_DRIFT_DEGREES for item in items)


def test_human_and_dwarf_keep_body_mesh_and_scale_from_29e4():
    character = build_character_material_appearance_manifest(seed=DEFAULT_SEED, count=60)
    manifest = build_equipment_character_combat_integration_manifest(seed=DEFAULT_SEED, count=60)
    by_id = {entry["descender_id"]: entry for entry in character["entries"]}
    for entry in manifest["entries"]:
        source = by_id[entry["descender_id"]]
        assert entry["source_body_mesh_path"] == source["source_body_mesh_path"]
        assert entry["actor_scale"] == source["actor_scale"]
        assert entry["stride_scale"] == source["stride_scale"]
        assert entry["foot_ik_offset_cm"] == source["foot_ik_offset_cm"]


def test_tampered_weapon_bone_is_rejected():
    manifest = build_equipment_character_combat_integration_manifest(count=40)
    altered = deepcopy(manifest)
    sword = next(item for item in _items(altered) if item["visual_id"] == "underreach.weapon.sword.v1")
    sword["attachment_bone"] = "hand_l"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="attachment binding"):
        validate_equipment_character_combat_integration_manifest(altered)


def test_expanded_drift_budget_is_rejected():
    manifest = build_equipment_character_combat_integration_manifest(count=40)
    altered = deepcopy(manifest)
    _items(altered)[0]["max_relative_translation_drift_cm"] = MAX_ATTACHMENT_DRIFT_CM + 1.0
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="drift budget"):
        validate_equipment_character_combat_integration_manifest(altered)


def test_changed_animation_asset_is_rejected():
    manifest = build_equipment_character_combat_integration_manifest(count=40)
    altered = deepcopy(manifest)
    altered["entries"][0]["animation_assets"]["attack"] = "/Game/Fake/A_Wrong.A_Wrong"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="animation binding"):
        validate_equipment_character_combat_integration_manifest(altered)


def test_digest_roundtrip_contract():
    manifest = build_equipment_character_combat_integration_manifest(count=40)
    assert manifest["digest"] == rebuild_digest(manifest)
    assert validate_equipment_character_combat_integration_manifest(manifest)
