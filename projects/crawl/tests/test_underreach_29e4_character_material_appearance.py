from copy import deepcopy

import pytest

from livingworld.descender_population import DescenderPopulationGenerator
from livingworld.underreach_character_material_appearance import (
    BASE_MATERIAL_PATH,
    BODY_MESHES,
    CHARACTER_MATERIAL_TEMPLATES,
    DEFAULT_SEED,
    PROTOCOL,
    build_character_material_appearance_manifest,
    rebuild_digest,
    validate_character_material_appearance_manifest,
)
from livingworld.underreach_equipment_material_wear import build_equipment_material_wear_manifest
from livingworld.underreach_visual_quality import build_visual_quality_manifest


def _materials(manifest):
    return [item for entry in manifest["entries"] for item in entry["character_materials"]]


def test_same_seed_is_exactly_deterministic():
    assert build_character_material_appearance_manifest() == build_character_material_appearance_manifest()


def test_different_seed_changes_material_identity():
    a = build_character_material_appearance_manifest("29e4-a")
    b = build_character_material_appearance_manifest("29e4-b")
    assert a["digest"] != b["digest"]
    assert [item["parameters"] for item in _materials(a)] != [item["parameters"] for item in _materials(b)]


def test_authority_boundary_is_explicit_and_closed():
    manifest = build_character_material_appearance_manifest()
    assert manifest["protocol"] == PROTOCOL
    assert manifest["authoritative"] is False
    for key in (
        "character_dna_mutation_allowed",
        "canonical_inventory_mutation_allowed",
        "combat_timing_mutation_allowed",
        "animation_binding_mutation_allowed",
        "skeletal_mesh_binding_mutation_allowed",
        "equipment_binding_mutation_allowed",
    ):
        assert manifest[key] is False


def test_master_template_descender_instance_hierarchy():
    manifest = build_character_material_appearance_manifest(count=24)
    materials = _materials(manifest)
    assert manifest["base_material_path"] == BASE_MATERIAL_PATH
    assert manifest["character_material_template_count"] == 4
    assert manifest["character_material_templates"] == CHARACTER_MATERIAL_TEMPLATES
    assert {item["category"] for item in materials} == {"skin", "hair", "eye", "clothing"}
    assert len(materials) == 96
    assert len({item["material_instance_path"] for item in materials}) == 96
    assert all(item["base_material_path"] == BASE_MATERIAL_PATH for item in materials)
    assert all(item["runtime_application"] == "skeletal_mesh_component_material_override_by_slot_category" for item in materials)


def test_skin_hair_eye_and_clothing_parameters_have_visible_variation():
    manifest = build_character_material_appearance_manifest(count=40)
    materials = _materials(manifest)
    required = {
        "base_tint",
        "secondary_tint",
        "accent_tint",
        "roughness",
        "specular",
        "metallic",
        "dirt_amount",
        "wear_amount",
        "saturation",
        "value_variation",
        "material_variation_seed",
        "secondary_mix",
        "accent_mix",
    }
    assert all(required <= set(item["parameters"]) for item in materials)
    assert len({tuple(sorted(item["parameters"]["base_tint"].items())) for item in materials if item["category"] == "skin"}) >= 4
    assert len({tuple(sorted(item["parameters"]["base_tint"].items())) for item in materials if item["category"] == "hair"}) >= 6
    assert len({tuple(sorted(item["parameters"]["base_tint"].items())) for item in materials if item["category"] == "eye"}) >= 3
    assert len({tuple(sorted(item["parameters"]["base_tint"].items())) for item in materials if item["category"] == "clothing"}) >= 5
    assert len({item["parameters"]["roughness"] for item in materials}) >= 8


def test_clothing_consumes_accepted_29e1_wear_dirt_roughness_and_saturation():
    manifest = build_character_material_appearance_manifest(count=40)
    for entry in manifest["entries"]:
        accepted = entry["accepted_visual_material_parameters"]
        clothing = next(item for item in entry["character_materials"] if item["category"] == "clothing")
        params = clothing["parameters"]
        assert params["roughness"] == accepted["cloth_roughness"]
        assert params["dirt_amount"] == accepted["dirt_amount"]
        assert params["wear_amount"] == accepted["cloth_wear"]
        assert params["saturation"] == accepted["saturation"]


def test_skin_and_eye_identity_follow_character_dna_without_mutating_it():
    population = DescenderPopulationGenerator(DEFAULT_SEED).generate([f"descender_{i:03d}" for i in range(40)])
    manifest = build_character_material_appearance_manifest(seed=DEFAULT_SEED, count=40)
    by_id = {entry.descender_id: entry for entry in population.entries}
    for entry in manifest["entries"]:
        source = by_id[entry["descender_id"]]
        assert entry["character_dna_digest"] == source.dna.digest()
        assert entry["visual_identity_digest"] == source.visual_identity_digest
        assert entry["renderer_manifest_digest"] == source.renderer_manifest.digest()
        assert entry["appearance_source"]["skin_variant"] == source.dna.skin_variant
        assert entry["appearance_source"]["eye_variant"] == source.dna.eye_variant
        assert entry["appearance_source"]["hair_asset"] == source.dna.appearance.current_hair_asset
        assert entry["appearance_source"]["facial_hair_asset"] == source.dna.appearance.facial_hair_asset
        assert entry["appearance_source"]["clothing_asset_ids"] == source.dna.appearance.clothing_asset_ids


def test_exact_29e3_29e1_population_provenance_is_preserved():
    visual = build_visual_quality_manifest(seed=DEFAULT_SEED, count=24)
    equipment = build_equipment_material_wear_manifest(seed=DEFAULT_SEED, count=24)
    manifest = build_character_material_appearance_manifest(seed=DEFAULT_SEED, count=24)
    assert manifest["source_29e3_digest"] == equipment["digest"]
    assert manifest["source_29e2_digest"] == equipment["source_29e2_digest"]
    assert manifest["source_29e1_digest"] == visual["digest"]
    assert manifest["source_population_digest"] == equipment["source_population_digest"]
    assert manifest["asset_registry_digest"] == equipment["asset_registry_digest"]


def test_human_dwarf_variants_keep_exact_accepted_skeletal_meshes_and_scales():
    manifest = build_character_material_appearance_manifest(count=100)
    assert {entry["species"] for entry in manifest["entries"]} == {"human", "dwarf"}
    assert len({entry["visual_variant"] for entry in manifest["entries"]}) >= 4
    for entry in manifest["entries"]:
        assert entry["source_body_mesh_path"] == BODY_MESHES[entry["visual_variant"]]
        assert entry["actor_scale"] > 0.0
        assert entry["stride_scale"] > 0.0
        assert len(entry["facial_contract"]) >= 10


def test_materials_are_nonmetallic_and_category_response_is_distinct():
    manifest = build_character_material_appearance_manifest(count=40)
    materials = _materials(manifest)
    assert all(item["parameters"]["metallic"] == 0.0 for item in materials)
    eye_roughness = [item["parameters"]["roughness"] for item in materials if item["category"] == "eye"]
    hair_roughness = [item["parameters"]["roughness"] for item in materials if item["category"] == "hair"]
    assert max(eye_roughness) < min(hair_roughness)
    assert all(item["parameters"]["wear_amount"] == 0.0 for item in materials if item["category"] in {"skin", "hair", "eye"})
    assert any(item["parameters"]["wear_amount"] > 0.0 for item in materials if item["category"] == "clothing")


def test_tampered_authority_is_rejected():
    manifest = build_character_material_appearance_manifest()
    altered = deepcopy(manifest)
    altered["skeletal_mesh_binding_mutation_allowed"] = True
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="authority boundary"):
        validate_character_material_appearance_manifest(altered)


def test_changed_skeletal_mesh_binding_is_rejected():
    manifest = build_character_material_appearance_manifest()
    altered = deepcopy(manifest)
    altered["entries"][0]["source_body_mesh_path"] = "/Game/Fake/SK_Wrong.SK_Wrong"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="skeletal mesh binding"):
        validate_character_material_appearance_manifest(altered)


def test_duplicate_material_instance_is_rejected():
    manifest = build_character_material_appearance_manifest()
    altered = deepcopy(manifest)
    materials = _materials(altered)
    materials[1]["material_instance_path"] = materials[0]["material_instance_path"]
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="identity collision"):
        validate_character_material_appearance_manifest(altered)


def test_out_of_bounds_parameter_is_rejected():
    manifest = build_character_material_appearance_manifest()
    altered = deepcopy(manifest)
    altered["entries"][0]["character_materials"][0]["parameters"]["roughness"] = 2.0
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="out of bounds"):
        validate_character_material_appearance_manifest(altered)


def test_digest_roundtrip_contract():
    manifest = build_character_material_appearance_manifest()
    assert manifest["digest"] == rebuild_digest(manifest)
    assert validate_character_material_appearance_manifest(manifest)


def test_stress_24_seeds_remain_valid():
    for index in range(24):
        manifest = build_character_material_appearance_manifest(f"underreach-29e4-stress-{index:03d}", count=16)
        assert validate_character_material_appearance_manifest(manifest)
        assert manifest["material_directive_count"] == 64
