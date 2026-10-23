import json

import pytest
from pydantic import ValidationError

from livingworld.character_dna import (
    CHARACTER_DNA_PROTOCOL,
    CharacterDNA,
    CharacterDNAGenerator,
    CharacterDNAStore,
    deterministic_digest,
    migrate_character_dna,
)
from livingworld.character_factory import (
    AppearanceAsset,
    AssetProvenance,
    CharacterAssetRegistry,
    CharacterFactory,
    HUMANOID_SKELETON_CONTRACT,
    default_character_asset_registry,
)


@pytest.fixture
def generator():
    return CharacterDNAGenerator("29a1-test-population")


@pytest.mark.parametrize("species", ["human", "dwarf"])
def test_character_dna_schema_and_seed_repeatability(generator, species):
    first = generator.generate("descender_004", species)
    second = generator.generate("descender_004", species)
    assert first == second
    assert first.protocol == CHARACTER_DNA_PROTOCOL
    assert first.schema_version == 1
    assert first.digest() == second.digest()


def test_same_descender_different_species_has_different_identity(generator):
    human = generator.generate("descender_004", "human")
    dwarf = generator.generate("descender_004", "dwarf")
    assert human.master_seed != dwarf.master_seed
    assert human.digest() != dwarf.digest()


def test_human_profile_bounds_and_correlated_mass(generator):
    population = generator.population("human", 100)
    assert all(150 <= item.height_cm <= 205 for item in population)
    assert all(45 <= item.mass_kg <= 160 for item in population)
    assert all(item.mass_kg / (item.height_cm / 100) ** 2 >= 20 for item in population)
    assert len({item.digest() for item in population}) == 100


def test_dwarf_profile_is_broad_short_and_not_uniform_human(generator):
    population = generator.population("dwarf", 100)
    assert all(118 <= item.height_cm <= 158 for item in population)
    assert all(item.shoulder_width >= 0.5 and item.head_scale >= 0.55 for item in population)
    assert all(item.leg_length < 0.4 and item.arm_length < 0.5 for item in population)
    assert len({item.digest() for item in population}) == 100


def test_named_body_extremes_are_deterministic_and_distinct(generator):
    average = generator.generate("human_average", "human", body_profile="average")
    short_heavy = generator.generate("human_short_heavy", "human", body_profile="short_heavy")
    tall_thin = generator.generate("human_tall_thin", "human", body_profile="tall_thin")
    assert short_heavy.height_cm < average.height_cm < tall_thin.height_cm
    assert short_heavy.body_fat > tall_thin.body_fat
    assert short_heavy.shoulder_width > tall_thin.shoulder_width


def test_deterministic_serialization_is_key_order_independent(generator):
    dna = generator.generate("descender_004", "human")
    value = dna.model_dump(mode="json")
    reversed_value = dict(reversed(list(value.items())))
    assert deterministic_digest(value) == deterministic_digest(reversed_value)


def test_dna_save_load_round_trip_is_identical(tmp_path, generator):
    dna = generator.generate("descender_004", "human")
    store = CharacterDNAStore(tmp_path)
    store.save(dna)
    loaded = store.load(dna.descender_id)
    assert loaded == dna
    assert loaded.digest() == dna.digest()
    assert not list(tmp_path.glob("*.tmp"))


def test_unknown_schema_requires_explicit_migration(generator):
    value = generator.generate("descender_004", "human").model_dump(mode="json")
    value["schema_version"] = 0
    with pytest.raises(ValueError, match="no Character DNA migration"):
        migrate_character_dna(value)


def test_renderer_transient_state_is_rejected_from_dna(generator):
    value = generator.generate("descender_004", "human").model_dump(mode="json")
    value["base_hair_asset"] = "/Game/Transient/SkeletalMeshActor_4"
    with pytest.raises(ValidationError, match="transient"):
        CharacterDNA.model_validate(value)


@pytest.mark.parametrize("species", ["human", "dwarf"])
def test_renderer_mapping_is_deterministic_and_humanoid_compatible(generator, species):
    dna = generator.generate(f"{species}_actor", species)
    factory = CharacterFactory()
    first = factory.map(dna)
    second = factory.map(dna)
    assert first == second
    assert first.digest() == second.digest()
    assert first.skeleton_contract == HUMANOID_SKELETON_CONTRACT
    assert first.animation_family == "humanoid.standard"
    assert len(first.body_morphs) == 10
    assert len(first.face_morphs) == 8


def test_dwarf_renderer_mapping_is_not_just_uniform_scale(generator):
    human = CharacterFactory().map(generator.generate("human", "human"))
    dwarf = CharacterFactory().map(generator.generate("dwarf", "dwarf"))
    differing_shape_controls = [key for key in dwarf.body_morphs if dwarf.body_morphs[key] != human.body_morphs[key]]
    assert {"shoulder_width", "torso_length", "leg_length", "arm_length", "head_scale"}.issubset(differing_shape_controls)
    assert dwarf.foot_ik_offset_cm < human.foot_ik_offset_cm


def test_default_assets_are_provenanced_and_compatible(generator):
    registry = default_character_asset_registry()
    for asset in registry.assets.values():
        assert asset.provenance.source_url
        assert asset.provenance.license
        assert asset.provenance.project_path
    registry.validate_selection(generator.generate("human", "human"))
    registry.validate_selection(generator.generate("dwarf", "dwarf"))


def test_species_incompatible_asset_is_rejected(generator):
    provenance = AssetProvenance(
        title="Human only", creator="test", source_url="internal://test", license="test",
        date_acquired="2026-08-24", local_source_path="internal://test", project_path="/Game/Test",
    )
    registry = default_character_asset_registry()
    registry.assets["mpfb.system.hair.short02"] = AppearanceAsset(
        asset_id="mpfb.system.hair.short02", kind="hair", slot="hair",
        species_compatibility={"human"}, source_asset="internal://test", unreal_asset="/Game/Test",
        provenance=provenance,
    )
    dwarf = generator.generate("dwarf", "dwarf")
    dwarf.appearance.current_hair_asset = "mpfb.system.hair.short02"
    with pytest.raises(ValueError, match="not compatible"):
        registry.validate_selection(dwarf)


def test_slot_conflicts_are_rejected(generator):
    registry = default_character_asset_registry()
    dna = generator.generate("human", "human")
    dna.appearance.clothing_asset_ids.append("underreach.clothing.tunic.v1")
    with pytest.raises(ValueError, match="slot conflict"):
        registry.validate_selection(dna)


def test_gameplay_item_remains_separate_from_visual_binding():
    gameplay = {"id": "item_sword_1", "category": "weapon", "damage": 17, "durability": 0.8}
    before = json.loads(json.dumps(gameplay))
    binding = CharacterFactory.gameplay_visual_binding(gameplay, "underreach.weapon.sword.v1")
    assert gameplay == before
    assert binding["authoritative"] is False
    assert "damage" not in binding


def test_persistent_overlay_changes_manifest_but_not_base_identity(generator):
    dna = generator.generate("human", "human")
    base_seed = dna.master_seed
    first = CharacterFactory().map(dna)
    dna.appearance.dirt_level = 0.75
    dna.appearance.persistent_marks.append("scar_left_brow")
    second = CharacterFactory().map(dna)
    assert dna.master_seed == base_seed
    assert first.dna_digest != second.dna_digest


def test_render_instance_is_disposable_and_terminal_state_is_preserved(generator):
    dna = generator.generate("descender_004", "human")
    factory = CharacterFactory()
    living = factory.instantiate(dna, terminal=False, unreal_object_path="/Engine/Transient.Actor_1")
    fallen = factory.instantiate(dna, terminal=True, unreal_object_path="/Engine/Transient.Actor_2")
    assert living.manifest_digest == fallen.manifest_digest
    assert living.cache_key != fallen.cache_key
    assert fallen.terminal is True
    assert "/Engine/Transient" not in dna.model_dump_json()


def test_population_digest_repeats_for_100_humans_and_dwarves():
    def build():
        generator = CharacterDNAGenerator("population-acceptance")
        population = generator.population("human", 100) + generator.population("dwarf", 100)
        return deterministic_digest([item.model_dump(mode="json") for item in population])

    assert build() == build()
