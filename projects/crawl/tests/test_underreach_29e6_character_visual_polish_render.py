from copy import deepcopy

import pytest

from livingworld.underreach_character_visual_polish_render import (
    CAMERA_DISTANCES_CM,
    LIGHTING_RIG,
    PROTOCOL,
    RENDER_HEIGHT,
    RENDER_WIDTH,
    build_character_visual_polish_render_manifest,
    rebuild_digest,
    validate_character_visual_polish_render_manifest,
)
from livingworld.underreach_equipment_character_combat_integration import (
    EXPECTED_EQUIPMENT_BINDINGS,
    build_equipment_character_combat_integration_manifest,
)


def test_same_seed_is_exactly_deterministic():
    assert build_character_visual_polish_render_manifest() == build_character_visual_polish_render_manifest()


def test_different_seed_changes_render_identity():
    a = build_character_visual_polish_render_manifest("29e6-a", count=32)
    b = build_character_visual_polish_render_manifest("29e6-b", count=32)
    assert a["digest"] != b["digest"]
    assert a["source_population_digest"] != b["source_population_digest"]


def test_exact_29e5_source_and_authority_boundary_are_preserved():
    source = build_equipment_character_combat_integration_manifest()
    manifest = build_character_visual_polish_render_manifest()
    assert manifest["protocol"] == PROTOCOL
    assert manifest["source_29e5_digest"] == source["digest"]
    assert manifest["source_29e4_digest"] == source["source_29e4_digest"]
    assert manifest["source_29e3_digest"] == source["source_29e3_digest"]
    assert manifest["source_29e2_digest"] == source["source_29e2_digest"]
    assert manifest["source_population_digest"] == source["source_population_digest"]
    assert manifest["authoritative"] is False
    for key in (
        "canonical_inventory_mutation_allowed",
        "character_dna_mutation_allowed",
        "combat_timing_mutation_allowed",
        "combat_outcome_mutation_allowed",
        "animation_asset_mutation_allowed",
        "skeletal_mesh_binding_mutation_allowed",
        "material_identity_mutation_allowed",
    ):
        assert manifest[key] is False


def test_render_contract_has_exact_near_mid_far_camera_distances():
    manifest = build_character_visual_polish_render_manifest()
    assert manifest["camera_distances_cm"] == CAMERA_DISTANCES_CM
    assert manifest["render_width"] == RENDER_WIDTH
    assert manifest["render_height"] == RENDER_HEIGHT
    assert manifest["lighting_rig"] == LIGHTING_RIG
    assert [shot["shot_id"] for shot in manifest["shots"]] == [
        "human_hero_near",
        "dwarf_hero_near",
        "mixed_pair_mid",
        "crowd_far",
    ]
    assert [shot["camera_distance_cm"] for shot in manifest["shots"]] == [750.0, 750.0, 1300.0, 2400.0]


def test_hero_pair_and_crowd_cover_required_species_and_diversity():
    manifest = build_character_visual_polish_render_manifest()
    by_id = {entry["descender_id"]: entry for entry in manifest["entries"]}
    human = [by_id[did] for did in manifest["shots"][0]["descender_ids"]]
    dwarf = [by_id[did] for did in manifest["shots"][1]["descender_ids"]]
    pair = [by_id[did] for did in manifest["shots"][2]["descender_ids"]]
    crowd = [by_id[did] for did in manifest["shots"][3]["descender_ids"]]
    assert {entry["species"] for entry in human} == {"human"}
    assert {entry["species"] for entry in dwarf} == {"dwarf"}
    assert {entry["species"] for entry in pair} == {"human", "dwarf"}
    assert len(crowd) >= 10
    assert {entry["species"] for entry in crowd} == {"human", "dwarf"}
    assert len({entry["visual_variant"] for entry in crowd}) >= 4
    assert len({entry["style_profile"] for entry in crowd}) >= 4
    assert len({entry["character_material_fingerprint"] for entry in crowd}) >= 8
    assert {item["visual_id"] for entry in crowd for item in entry["equipment"]} == set(EXPECTED_EQUIPMENT_BINDINGS)


def test_every_entry_keeps_real_character_material_and_equipment_bindings():
    manifest = build_character_visual_polish_render_manifest()
    for entry in manifest["entries"]:
        assert set(entry["character_material_paths"]) == {"skin", "hair", "eye", "clothing"}
        assert entry["source_body_mesh_path"].startswith("/Game/Underreach29A1/Characters/")
        assert entry["actor_scale"] > 0
        for item in entry["equipment"]:
            expected_slot, expected_bone = EXPECTED_EQUIPMENT_BINDINGS[item["visual_id"]]
            assert item["slot"] == expected_slot
            assert item["attachment_bone"] == expected_bone
            assert item["mesh_asset_path"].startswith("/Game/Underreach29E2/")
            assert item["material_instance_path"].startswith("/Game/Underreach29E3/")


def test_tampered_camera_distance_is_rejected():
    manifest = build_character_visual_polish_render_manifest()
    altered = deepcopy(manifest)
    altered["shots"][0]["camera_distance_cm"] = 751.0
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="camera distance"):
        validate_character_visual_polish_render_manifest(altered)


def test_tampered_character_material_set_is_rejected():
    manifest = build_character_visual_polish_render_manifest()
    altered = deepcopy(manifest)
    altered["entries"][0]["character_material_paths"].pop("skin")
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="material coverage"):
        validate_character_visual_polish_render_manifest(altered)


def test_tampered_equipment_bone_is_rejected():
    manifest = build_character_visual_polish_render_manifest()
    altered = deepcopy(manifest)
    item = next(item for entry in altered["entries"] for item in entry["equipment"])
    item["attachment_bone"] = "root"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="attachment contract"):
        validate_character_visual_polish_render_manifest(altered)


def test_digest_roundtrip_contract():
    manifest = build_character_visual_polish_render_manifest()
    assert manifest["digest"] == rebuild_digest(manifest)
    assert validate_character_visual_polish_render_manifest(manifest)
