from copy import deepcopy
from hashlib import sha256

import pytest

from livingworld.underreach_equipment_asset_integration import (
    PROTOCOL,
    build_real_equipment_integration_manifest,
    equipment_source_manifest,
    equipment_source_texts,
    rebuild_digest,
    validate_real_equipment_integration_manifest,
)


def test_same_seed_is_exactly_deterministic():
    assert build_real_equipment_integration_manifest() == build_real_equipment_integration_manifest()


def test_different_population_seed_changes_integration_digest():
    assert build_real_equipment_integration_manifest("29e2-a")["digest"] != build_real_equipment_integration_manifest("29e2-b")["digest"]


def test_authority_boundary_is_explicit():
    manifest = build_real_equipment_integration_manifest()
    assert manifest["protocol"] == PROTOCOL
    assert manifest["authoritative"] is False
    assert manifest["canonical_inventory_mutation_allowed"] is False
    assert manifest["character_dna_mutation_allowed"] is False
    assert manifest["combat_timing_mutation_allowed"] is False


def test_three_project_authored_mesh_sources_are_stable_and_nonempty():
    texts = equipment_source_texts()
    source = equipment_source_manifest()
    assert set(texts) == {"UR_Sword_01.obj", "UR_Helmet_01.obj", "UR_Breastplate_01.obj"}
    assert len(source["records"]) == 3
    for record in source["records"]:
        text = texts[record["source_name"]]
        assert text.count("\nv ") >= 24
        assert text.count("\nf ") >= 18
        assert record["source_sha256"] == sha256(text.encode("utf-8")).hexdigest()
        assert record["source_kind"] == "project_authored_deterministic_obj"
        assert record["art_status"] == "production_candidate"
        assert record["final_art_required"] is True


def test_every_29e1_equipment_directive_becomes_a_real_static_mesh_binding():
    manifest = build_real_equipment_integration_manifest(count=24)
    items = [item for entry in manifest["entries"] for item in entry["equipment"]]
    assert len(items) == manifest["replacement_count"]
    assert items
    assert all(item["source_29e1_realization"] == "procedural_attachment_geometry" for item in items)
    assert all(item["source_29e1_quality_tier"] == "procedural_proxy" for item in items)
    assert all(item["visual_realization"] == "real_static_mesh_asset" for item in items)
    assert all(item["replaces_procedural_proxy"] is True for item in items)
    assert all(item["quality_tier"] == "production_candidate" for item in items)
    assert all(item["final_art_required"] is True for item in items)
    assert len({item["unreal_asset_path"] for item in items}) == 3
    assert len({item["material_instance_path"] for item in items}) == 3


def test_attachment_and_fit_contracts_remain_bounded_for_humans_and_dwarfs():
    manifest = build_real_equipment_integration_manifest(count=80)
    assert {entry["species"] for entry in manifest["entries"]} == {"human", "dwarf"}
    for entry in manifest["entries"]:
        slots = set()
        for item in entry["equipment"]:
            assert item["attachment_bone"] in {"head", "spine_03", "hand_r"}
            assert item["attachment_mode"] == "skeletal_skin"
            assert item["slot"] not in slots
            slots.add(item["slot"])
            assert all(0.70 <= float(item["presentation_scale"][axis]) <= 1.20 for axis in ("x", "y", "z"))


def test_dwarf_sword_fit_remains_shorter_than_human_sword_fit():
    manifest = build_real_equipment_integration_manifest(count=100)
    human = []
    dwarf = []
    for entry in manifest["entries"]:
        for item in entry["equipment"]:
            if item["visual_id"] == "underreach.weapon.sword.v1":
                (human if entry["species"] == "human" else dwarf).append(float(item["presentation_scale"]["z"]))
    assert human and dwarf
    assert max(dwarf) < min(human)


def test_tampered_authority_is_rejected():
    manifest = build_real_equipment_integration_manifest()
    altered = deepcopy(manifest)
    altered["canonical_inventory_mutation_allowed"] = True
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="authority boundary"):
        validate_real_equipment_integration_manifest(altered)


def test_false_final_art_claim_is_rejected():
    manifest = build_real_equipment_integration_manifest()
    altered = deepcopy(manifest)
    altered["source_assets"][0]["art_status"] = "final_production"
    altered["source_assets"][0]["final_art_required"] = False
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="art maturity"):
        validate_real_equipment_integration_manifest(altered)


def test_tampered_source_hash_is_rejected():
    manifest = build_real_equipment_integration_manifest()
    altered = deepcopy(manifest)
    altered["source_assets"][0]["source_sha256"] = "0" * 64
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="source mesh hash"):
        validate_real_equipment_integration_manifest(altered)


def test_changed_attachment_bone_is_rejected():
    manifest = build_real_equipment_integration_manifest()
    altered = deepcopy(manifest)
    item = next(item for entry in altered["entries"] for item in entry["equipment"])
    item["attachment_bone"] = "root"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="attachment bone"):
        validate_real_equipment_integration_manifest(altered)


def test_json_digest_roundtrip_contract():
    manifest = build_real_equipment_integration_manifest()
    assert manifest["digest"] == rebuild_digest(manifest)
    assert validate_real_equipment_integration_manifest(manifest)


def test_stress_30_seeds_remain_valid():
    for index in range(30):
        manifest = build_real_equipment_integration_manifest(f"underreach-29e2-stress-{index:03d}", count=16)
        assert validate_real_equipment_integration_manifest(manifest)
        assert manifest["unique_real_mesh_asset_count"] == 3
        assert manifest["unique_material_instance_count"] == 3
