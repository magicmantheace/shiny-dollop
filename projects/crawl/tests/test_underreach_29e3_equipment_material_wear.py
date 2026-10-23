from copy import deepcopy

import pytest

from livingworld.underreach_equipment_asset_integration import (
    EQUIPMENT_ASSETS,
    build_real_equipment_integration_manifest,
)
from livingworld.underreach_equipment_material_wear import (
    BASE_MATERIAL_PATH,
    DEFAULT_SEED,
    EXPECTED_BONES,
    ITEM_MATERIAL_TEMPLATES,
    PROTOCOL,
    STYLE_TONES,
    build_equipment_material_wear_manifest,
    rebuild_digest,
    validate_equipment_material_wear_manifest,
)


def _items(manifest):
    return [
        item
        for entry in manifest["entries"]
        for item in entry["equipment_materials"]
    ]


def test_same_seed_is_exactly_deterministic():
    assert (
        build_equipment_material_wear_manifest()
        == build_equipment_material_wear_manifest()
    )


def test_different_seed_changes_digest_and_material_parameters():
    a = build_equipment_material_wear_manifest("29e3-a")
    b = build_equipment_material_wear_manifest("29e3-b")
    assert a["digest"] != b["digest"]
    assert [item["parameters"] for item in _items(a)] != [
        item["parameters"] for item in _items(b)
    ]


def test_authority_boundary_is_explicit():
    manifest = build_equipment_material_wear_manifest()
    assert manifest["protocol"] == PROTOCOL
    assert manifest["authoritative"] is False
    assert manifest["canonical_inventory_mutation_allowed"] is False
    assert manifest["character_dna_mutation_allowed"] is False
    assert manifest["combat_timing_mutation_allowed"] is False
    assert manifest["mesh_binding_mutation_allowed"] is False


def test_reusable_master_item_template_descender_instance_hierarchy():
    manifest = build_equipment_material_wear_manifest(count=24)
    items = _items(manifest)
    assert manifest["base_material_path"] == BASE_MATERIAL_PATH
    assert manifest["item_material_template_count"] == 3
    assert manifest["item_material_templates"] == ITEM_MATERIAL_TEMPLATES
    assert len({item["item_material_template_path"] for item in items}) == 3
    assert len({item["material_instance_path"] for item in items}) == len(items)
    assert all(item["base_material_path"] == BASE_MATERIAL_PATH for item in items)
    assert all(
        item["runtime_application"] == "static_mesh_component_material_override"
        for item in items
    )


def test_material_parameters_realize_29e1_wear_dirt_tones_and_variation():
    manifest = build_equipment_material_wear_manifest(count=40)
    items = _items(manifest)
    required = {
        "metal_tint",
        "leather_tint",
        "accent_tint",
        "roughness",
        "metallic",
        "wear_amount",
        "dirt_amount",
        "edge_wear",
        "leather_mix",
        "accent_mix",
        "saturation",
        "value_variation",
        "material_variation_seed",
        "accent_index",
    }
    assert all(required <= set(item["parameters"]) for item in items)
    assert len({item["parameters"]["roughness"] for item in items}) >= 8
    assert len({item["parameters"]["wear_amount"] for item in items}) >= 8
    assert len({item["parameters"]["dirt_amount"] for item in items}) >= 8
    assert len({item["parameters"]["edge_wear"] for item in items}) >= 8
    assert len({item["parameters"]["value_variation"] for item in items}) >= 8
    assert len(
        {
            tuple(sorted(item["parameters"]["accent_tint"].items()))
            for item in items
        }
    ) >= 4


def test_multiple_descenders_do_not_collapse_to_flat_grey():
    manifest = build_equipment_material_wear_manifest(count=40)
    items = _items(manifest)
    fingerprints = {
        (
            tuple(sorted(item["parameters"]["metal_tint"].items())),
            tuple(sorted(item["parameters"]["accent_tint"].items())),
            item["parameters"]["roughness"],
            item["parameters"]["dirt_amount"],
            item["parameters"]["edge_wear"],
        )
        for item in items
    }
    chromatic = [
        item
        for item in items
        if max(
            item["parameters"]["accent_tint"][channel]
            for channel in ("r", "g", "b")
        )
        - min(
            item["parameters"]["accent_tint"][channel]
            for channel in ("r", "g", "b")
        )
        >= 0.04
    ]
    assert len(fingerprints) >= 8
    assert len(chromatic) >= 8


def test_style_profile_drives_bounded_metal_and_leather_tones():
    manifest = build_equipment_material_wear_manifest(count=80)
    items = _items(manifest)
    styles = {item["style_profile"] for item in items}
    assert styles <= set(STYLE_TONES)
    assert len(styles) >= 2
    by_style = {}
    for item in items:
        by_style.setdefault(
            item["style_profile"],
            (
                tuple(sorted(item["parameters"]["metal_tint"].items())),
                tuple(sorted(item["parameters"]["leather_tint"].items())),
            ),
        )
    assert len(set(by_style.values())) == len(by_style)


def test_real_29e2_mesh_binding_attachment_and_fit_are_preserved_exactly():
    source = build_real_equipment_integration_manifest(seed=DEFAULT_SEED, count=80)
    manifest = build_equipment_material_wear_manifest(seed=DEFAULT_SEED, count=80)
    source_by_id = {entry["descender_id"]: entry for entry in source["entries"]}

    assert manifest["source_29e2_digest"] == source["digest"]
    assert manifest["source_29e1_digest"] == source["source_29e1_digest"]
    assert manifest["source_population_digest"] == source["source_population_digest"]
    assert manifest["asset_registry_digest"] == source["asset_registry_digest"]
    assert {entry["species"] for entry in manifest["entries"]} == {"human", "dwarf"}

    for entry in manifest["entries"]:
        source_entry = source_by_id[entry["descender_id"]]
        assert entry["species"] == source_entry["species"]
        assert entry["style_profile"] == source_entry["style_profile"]
        assert entry["visual_identity_digest"] == source_entry["visual_identity_digest"]
        assert entry["renderer_manifest_digest"] == source_entry["renderer_manifest_digest"]
        source_items = {
            item["visual_id"]: item for item in source_entry["equipment"]
        }
        for item in entry["equipment_materials"]:
            original = source_items[item["visual_id"]]
            assert item["mesh_asset_path"] == original["unreal_asset_path"]
            assert item["source_29e2_material_instance_path"] == original[
                "material_instance_path"
            ]
            assert item["attachment_bone"] == original["attachment_bone"]
            assert item["attachment_mode"] == original["attachment_mode"]
            assert item["presentation_scale"] == original["presentation_scale"]


def test_visual_ids_use_exact_29e2_static_meshes_and_accepted_bones():
    manifest = build_equipment_material_wear_manifest(count=40)
    items = _items(manifest)
    for item in items:
        visual_id = item["visual_id"]
        assert item["mesh_asset_path"] == EQUIPMENT_ASSETS[visual_id][
            "unreal_asset_path"
        ]
        assert item["attachment_bone"] == EXPECTED_BONES[visual_id]


def test_human_dwarf_fit_contract_remains_unchanged():
    manifest = build_equipment_material_wear_manifest(count=100)
    swords = [
        item
        for item in _items(manifest)
        if item["visual_id"] == "underreach.weapon.sword.v1"
    ]
    human = [
        float(item["presentation_scale"]["z"])
        for item in swords
        if item["species"] == "human"
    ]
    dwarf = [
        float(item["presentation_scale"]["z"])
        for item in swords
        if item["species"] == "dwarf"
    ]
    assert human and dwarf
    assert max(dwarf) < min(human)
    assert all(
        0.70 <= float(item["presentation_scale"][axis]) <= 1.20
        for item in _items(manifest)
        for axis in ("x", "y", "z")
    )


def test_tampered_authority_is_rejected():
    manifest = build_equipment_material_wear_manifest()
    altered = deepcopy(manifest)
    altered["mesh_binding_mutation_allowed"] = True
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="authority boundary"):
        validate_equipment_material_wear_manifest(altered)


def test_changed_real_mesh_binding_is_rejected():
    manifest = build_equipment_material_wear_manifest()
    altered = deepcopy(manifest)
    item = next(
        item
        for entry in altered["entries"]
        for item in entry["equipment_materials"]
    )
    item["mesh_asset_path"] = "/Game/Fake/SM_Wrong.SM_Wrong"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="real mesh binding"):
        validate_equipment_material_wear_manifest(altered)


def test_changed_attachment_bone_is_rejected():
    manifest = build_equipment_material_wear_manifest()
    altered = deepcopy(manifest)
    item = next(
        item
        for entry in altered["entries"]
        for item in entry["equipment_materials"]
    )
    item["attachment_bone"] = "root"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="attachment bone"):
        validate_equipment_material_wear_manifest(altered)


def test_duplicate_material_instance_identity_is_rejected():
    manifest = build_equipment_material_wear_manifest()
    altered = deepcopy(manifest)
    items = [
        item
        for entry in altered["entries"]
        for item in entry["equipment_materials"]
    ]
    items[1]["material_instance_path"] = items[0]["material_instance_path"]
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="identity collision"):
        validate_equipment_material_wear_manifest(altered)


def test_out_of_bounds_parameter_is_rejected():
    manifest = build_equipment_material_wear_manifest()
    altered = deepcopy(manifest)
    item = next(
        item
        for entry in altered["entries"]
        for item in entry["equipment_materials"]
    )
    item["parameters"]["edge_wear"] = 1.5
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="out of bounds"):
        validate_equipment_material_wear_manifest(altered)


def test_digest_roundtrip_contract():
    manifest = build_equipment_material_wear_manifest()
    assert manifest["digest"] == rebuild_digest(manifest)
    assert validate_equipment_material_wear_manifest(manifest)


def test_stress_30_seeds_remain_valid():
    for index in range(30):
        manifest = build_equipment_material_wear_manifest(
            f"underreach-29e3-stress-{index:03d}", count=16
        )
        assert validate_equipment_material_wear_manifest(manifest)
        assert manifest["material_directive_count"] > 0
        assert manifest["item_material_template_count"] == 3
