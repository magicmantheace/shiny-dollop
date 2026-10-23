from copy import deepcopy

import pytest

from livingworld.underreach_visual_quality import (
    PROTOCOL,
    build_visual_quality_manifest,
    rebuild_digest,
    validate_visual_quality_manifest,
)


def test_same_seed_is_exactly_deterministic():
    assert build_visual_quality_manifest() == build_visual_quality_manifest()


def test_different_seed_changes_digest():
    assert build_visual_quality_manifest("29e1-a")["digest"] != build_visual_quality_manifest("29e1-b")["digest"]


def test_authority_boundary_is_explicit():
    manifest = build_visual_quality_manifest()
    assert manifest["protocol"] == PROTOCOL
    assert manifest["authoritative"] is False
    assert manifest["canonical_inventory_mutation_allowed"] is False
    assert manifest["character_dna_mutation_allowed"] is False
    assert manifest["combat_timing_mutation_allowed"] is False


def test_population_contains_human_and_dwarf_visuals():
    manifest = build_visual_quality_manifest(count=40)
    assert {entry["species"] for entry in manifest["entries"]} == {"human", "dwarf"}


def test_material_variation_is_noncollapsed():
    manifest = build_visual_quality_manifest(count=24)
    variants = {tuple(sorted(entry["material_parameters"].items())) for entry in manifest["entries"]}
    assert len(variants) >= 8


def test_every_equipment_piece_keeps_attachment_and_truthful_proxy_status():
    manifest = build_visual_quality_manifest(count=24)
    items = [item for entry in manifest["entries"] for item in entry["equipment"]]
    assert items
    assert all(item["quality_tier"] == "procedural_proxy" for item in items)
    assert all(item["asset_realization"] == "procedural_attachment_geometry" for item in items)
    assert all(item["unreal_asset_path"] is None for item in items)
    assert all(item["planned_unreal_asset_path"] for item in items)
    assert all(item["source_geometry"] for item in items)
    assert all(item["production_art_required"] is True for item in items)
    assert all(item["attachment_mode"] == "skeletal_skin" for item in items)
    assert all(item["attachment_bone"] in {"head", "spine_03", "hand_r"} for item in items)


def test_dwarf_sword_is_visually_shorter_than_human_sword():
    manifest = build_visual_quality_manifest(count=80)
    human, dwarf = [], []
    for entry in manifest["entries"]:
        for item in entry["equipment"]:
            if item["visual_id"] == "underreach.weapon.sword.v1":
                (human if entry["species"] == "human" else dwarf).append(item["presentation_scale"]["z"])
    assert human and dwarf
    assert max(dwarf) < min(human)


def test_visual_fit_scales_are_bounded():
    manifest = build_visual_quality_manifest(count=100)
    for entry in manifest["entries"]:
        for item in entry["equipment"]:
            assert all(0.70 <= float(item["presentation_scale"][axis]) <= 1.20 for axis in ("x", "y", "z"))


def test_tampered_authority_is_rejected():
    altered = deepcopy(build_visual_quality_manifest())
    altered["canonical_inventory_mutation_allowed"] = True
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="authority boundary"):
        validate_visual_quality_manifest(altered)


def test_false_production_art_claim_is_rejected():
    altered = deepcopy(build_visual_quality_manifest())
    item = next(item for entry in altered["entries"] for item in entry["equipment"])
    item["quality_tier"] = "production"
    item["production_art_required"] = False
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="misrepresented"):
        validate_visual_quality_manifest(altered)


def test_false_loadable_asset_claim_is_rejected():
    altered = deepcopy(build_visual_quality_manifest())
    item = next(item for entry in altered["entries"] for item in entry["equipment"])
    item["unreal_asset_path"] = "/Game/Fake/SM_NotReal.SM_NotReal"
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="falsely claimed"):
        validate_visual_quality_manifest(altered)


def test_duplicate_equipment_slot_is_rejected():
    altered = deepcopy(build_visual_quality_manifest(count=20))
    entry = next(entry for entry in altered["entries"] if len(entry["equipment"]) >= 2)
    entry["equipment"][1]["slot"] = entry["equipment"][0]["slot"]
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="duplicate equipment slot"):
        validate_visual_quality_manifest(altered)


def test_json_digest_roundtrip_contract():
    manifest = build_visual_quality_manifest()
    assert manifest["digest"] == rebuild_digest(manifest)
    assert validate_visual_quality_manifest(manifest)


def test_stress_40_seeds_are_valid_and_bounded():
    for index in range(40):
        manifest = build_visual_quality_manifest(f"underreach-29e1-stress-{index:03d}", count=16)
        assert validate_visual_quality_manifest(manifest)
        assert len(manifest["entries"]) == 16
