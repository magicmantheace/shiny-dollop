import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from livingworld.character_factory import CharacterFactory
from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.descender_population import (
    CharacterManifestCache,
    DescenderPopulationGenerator,
    OUTFIT_ASSETS,
    POPULATION_PROTOCOL,
    POPULATION_VERSION,
    STYLE_PROFILES,
    population_diversity,
)
from livingworld.feed_channel_registry import FeedChannelRegistry
from livingworld.live_presentation_bridge import LivePresentationScheduler
from livingworld.runtime_checkpoint import AlphaCheckpointStore


def test_population_digest_is_stable_across_python_processes() -> None:
    repo = Path(__file__).resolve().parents[1]
    code = (
        "from livingworld.descender_population import DescenderPopulationGenerator; "
        "ids=[f'descender-{i:03d}' for i in range(10)]; "
        "print(DescenderPopulationGenerator().generate(ids).population_digest)"
    )
    environment = dict(os.environ)
    first = subprocess.check_output([sys.executable, "-c", code], cwd=repo, env=environment, text=True).strip()
    second = subprocess.check_output([sys.executable, "-c", code], cwd=repo, env=environment, text=True).strip()
    assert first == second


def ids(count=20):
    return [f"population_descender_{index:04d}" for index in range(count)]


def authority(tmp_path, count=12):
    persistence = CrawlPersistence(f"sqlite:///{(tmp_path / 'ledger.sqlite3').as_posix()}")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="underreach-29a2-test-descent",
        crawler_ids=ids(count),
        floor_count=2,
        crawl_id="descent_29a2_tests",
    )
    service.start(descent)
    return persistence, descent


def test_population_protocol_and_version_are_explicit():
    population = DescenderPopulationGenerator().generate(ids(4))
    assert population.protocol == POPULATION_PROTOCOL
    assert population.implementation_version == POPULATION_VERSION


def test_population_seed_is_deterministic():
    assert DescenderPopulationGenerator("seed-a").generate(ids()).model_dump() == DescenderPopulationGenerator("seed-a").generate(ids()).model_dump()


def test_descender_id_binding_is_independent_of_spawn_order():
    forward = DescenderPopulationGenerator("id-binding").generate(ids())
    reverse = DescenderPopulationGenerator("id-binding").generate(reversed(ids()))
    left = {item.descender_id: item.visual_identity_digest for item in forward.entries}
    right = {item.descender_id: item.visual_identity_digest for item in reverse.entries}
    assert left == right


def test_population_order_is_part_of_population_digest():
    generator = DescenderPopulationGenerator("ordered")
    assert generator.generate(ids()).population_digest != generator.generate(reversed(ids())).population_digest


def test_species_weighting_is_deterministic():
    first = [DescenderPopulationGenerator("weights", species_weights={"human": 0.7, "dwarf": 0.3}).species_for(item) for item in ids(200)]
    second = [DescenderPopulationGenerator("weights", species_weights={"human": 7, "dwarf": 3}).species_for(item) for item in ids(200)]
    assert first == second
    assert 110 <= first.count("human") <= 170


@pytest.mark.parametrize("species", ["human", "dwarf"])
def test_one_hundred_species_records_repeat_exactly(species):
    forced = {item: species for item in ids(100)}
    first = DescenderPopulationGenerator("hundred").generate(ids(100), forced_species=forced)
    second = DescenderPopulationGenerator("hundred").generate(ids(100), forced_species=forced)
    assert first.population_digest == second.population_digest
    assert {item.dna.species for item in first.entries} == {species}


def test_one_thousand_record_stress_population_is_unique():
    population = DescenderPopulationGenerator("stress-1000").generate(ids(1000))
    diversity = population_diversity(population)
    assert len(population.entries) == 1000
    assert diversity["exact_dna_duplicate_count"] == 0
    assert diversity["exact_renderer_manifest_duplicate_count"] == 0


@pytest.mark.parametrize("species,low,high", [("human", 150.0, 205.0), ("dwarf", 118.0, 158.0)])
def test_species_profile_bounds(species, low, high):
    forced = {item: species for item in ids(100)}
    population = DescenderPopulationGenerator("bounds").generate(ids(100), forced_species=forced)
    assert all(low <= item.dna.height_cm <= high for item in population.entries)


def test_clothing_uses_only_validated_outfits():
    population = DescenderPopulationGenerator("clothing").generate(ids(100))
    assert all(tuple(item.dna.appearance.clothing_asset_ids) in {(asset,) for asset in OUTFIT_ASSETS} for item in population.entries)
    assert len({tuple(item.dna.appearance.clothing_asset_ids) for item in population.entries}) >= 5


def test_hair_and_facial_hair_remain_species_compatible():
    generator = DescenderPopulationGenerator("hair")
    population = generator.generate(ids(100))
    for item in population.entries:
        generator.factory.registry.validate_selection(item.dna)


def test_equipment_visuals_are_presentation_fixture_only():
    population = DescenderPopulationGenerator("gear").generate(ids(100))
    assert all(item.loadout_authority == "presentation_fixture" for item in population.entries)
    assert all("underreach.weapon.sword.v1" in item.dna.appearance.equipment_visual_ids for item in population.entries)
    assert len({tuple(item.dna.appearance.equipment_visual_ids) for item in population.entries}) >= 3


def test_style_profile_is_deterministic_and_bounded():
    first = DescenderPopulationGenerator("style").generate(ids(100))
    second = DescenderPopulationGenerator("style").generate(ids(100))
    assert [item.style_profile for item in first.entries] == [item.style_profile for item in second.entries]
    assert set(item.style_profile for item in first.entries).issubset(STYLE_PROFILES)


def test_personality_hooks_are_deterministic_but_non_authoritative():
    first = DescenderPopulationGenerator("personality").generate_entry("population_descender_0001")
    second = DescenderPopulationGenerator("personality").generate_entry("population_descender_0001")
    assert first.personality == second.personality
    assert "dialogue" not in first.personality.model_dump()


def test_population_digest_changes_with_versioned_inputs():
    assert DescenderPopulationGenerator("seed-a").generate(ids()).population_digest != DescenderPopulationGenerator("seed-b").generate(ids()).population_digest


def test_cache_key_is_stable():
    generator = DescenderPopulationGenerator("cache-key")
    dna = generator.generate_entry(ids(1)[0]).dna
    assert generator.cache.key_for(dna) == generator.cache.key_for(dna.model_copy(deep=True))


def test_cache_hit_returns_equal_independent_manifest():
    cache = CharacterManifestCache(CharacterFactory())
    generator = DescenderPopulationGenerator("cache-hit", cache=cache, factory=cache.factory)
    dna = generator.generate_entry(ids(1)[0]).dna
    first = cache.get(dna)
    second = cache.get(dna)
    assert first == second and first is not second
    assert cache.hits == 2 and cache.misses == 1


def test_cache_cannot_cross_contaminate_identities():
    generator = DescenderPopulationGenerator("cache-isolation")
    population = generator.generate(ids(2))
    assert population.entries[0].renderer_manifest.descender_id != population.entries[1].renderer_manifest.descender_id
    assert population.entries[0].renderer_manifest.digest() != population.entries[1].renderer_manifest.digest()


def test_detail_tier_promotion_does_not_reroll_identity():
    generator = DescenderPopulationGenerator("detail")
    background = generator.generate_entry(ids(1)[0], detail_tier="background")
    focused = generator.generate_entry(ids(1)[0], detail_tier="focused")
    assert background.dna == focused.dna
    assert background.renderer_manifest == focused.renderer_manifest
    assert background.visual_identity_digest == focused.visual_identity_digest


def test_diversity_report_detects_no_exact_clones():
    report = population_diversity(DescenderPopulationGenerator("diversity").generate(ids(200)))
    assert report["exact_dna_duplicate_count"] == 0
    assert report["exact_renderer_manifest_duplicate_count"] == 0
    assert report["clothing_combination_count"] >= 5
    assert report["minimum_face_nearest_neighbor_distance"] > 0


def test_live_scheduler_bootstraps_six_humans_and_four_dwarfs(tmp_path):
    _, descent = authority(tmp_path)
    presented = ids(10)
    species = {item: "human" if index < 6 else "dwarf" for index, item in enumerate(presented)}
    scheduler = LivePresentationScheduler(
        descent.id, presentation_seed="29a2-live", focus_actor_ids=presented,
        population_seed="29a2-live-population", population_species=species,
    )
    bootstrap = scheduler.bootstrap(descent, environment={"accepted_level_asset": "/Game/Test"})
    manifests = [item["character_renderer_manifest"] for item in bootstrap["actors"]]
    assert len(manifests) == 10
    assert sum(item["species"] == "human" for item in manifests) == 6
    assert sum(item["species"] == "dwarf" for item in manifests) == 4
    assert len({item["visual_identity_digest"] for item in manifests}) == 10


def test_live_population_uses_compact_distinct_formation(tmp_path):
    _, descent = authority(tmp_path)
    scheduler = LivePresentationScheduler(
        descent.id, presentation_seed="formation", focus_actor_ids=ids(10),
        population_seed="formation-population",
    )
    actors = scheduler.bootstrap(descent, environment={"accepted_level_asset": "/Game/Test"})["actors"]
    positions = {(item["transform"]["x"], item["transform"]["y"]) for item in actors}
    assert len(positions) == 10
    assert max(abs(value) for item in positions for value in item) <= 800


def test_feed_projection_exposes_safe_identity_without_raw_dna(tmp_path):
    _, descent = authority(tmp_path)
    registry = FeedChannelRegistry(descent.id)
    registry.register(descent)
    registry.register_presentation_identities({ids(1)[0]: {
        "species": "human", "visual_identity_digest": "digest-a", "visual_variant": "human_average",
        "style_profile": "practical", "raw_dna": {"forbidden": True},
    }})
    row = registry.channel(descent, ids(1)[0])
    assert row["presentation_identity"]["species"] == "human"
    assert row["presentation_identity"]["visual_identity_digest"] == "digest-a"
    assert "raw_dna" not in row["presentation_identity"]


def test_feed_identity_projection_does_not_mutate_simulation(tmp_path):
    _, descent = authority(tmp_path)
    registry = FeedChannelRegistry(descent.id)
    registry.register(descent)
    before = descent.fingerprint()
    registry.register_presentation_identities({ids(1)[0]: {"species": "human", "visual_identity_digest": "x"}})
    registry.directory(descent)
    assert descent.fingerprint() == before


def test_follow_a_b_c_dwarf_then_auto_keeps_correct_targets(tmp_path):
    _, descent = authority(tmp_path)
    registry = FeedChannelRegistry(descent.id, default_viewer_id="population_viewer")
    registry.register(descent)
    registry.update(descent, [], presentation_tick=0, presentation_seconds=0.0, camera_available_ids=ids(10))
    for tick, actor_id in enumerate((ids(10)[0], ids(10)[1], ids(10)[2], ids(10)[8]), start=1):
        registry.latest_presentation_tick = tick
        result = registry.apply_request(descent, {
            "viewer_id": "population_viewer", "action": "follow", "request_id": f"follow-{tick}",
            "requested_at_presentation_tick": tick, "descender_id": actor_id,
        })
        assert result["active_descender_id"] == actor_id
    registry.latest_presentation_tick = 5
    result = registry.apply_request(descent, {
        "viewer_id": "population_viewer", "action": "release", "request_id": "return-auto",
        "requested_at_presentation_tick": 5,
    })
    assert result["focus_mode"] == "automatic"


def test_feed_reconnect_preserves_presentation_identity(tmp_path):
    _, descent = authority(tmp_path)
    first = FeedChannelRegistry(descent.id)
    first.register(descent)
    first.register_presentation_identities({ids(1)[0]: {"species": "dwarf", "visual_identity_digest": "same"}})
    second = FeedChannelRegistry(descent.id)
    second.register(descent)
    second.restore(first.reconnect_snapshot())
    assert second.channel(descent, ids(1)[0])["presentation_identity"] == first.channel(descent, ids(1)[0])["presentation_identity"]


def test_checkpoint_resume_reconstructs_identical_population(tmp_path):
    persistence, descent = authority(tmp_path)
    generator = DescenderPopulationGenerator("checkpoint-population")
    population = generator.generate(ids(12))
    snapshot = {
        "population_seed": population.population_seed,
        "ordered_descender_ids": population.ordered_descender_ids,
        "identity_digests": {item.descender_id: item.visual_identity_digest for item in population.entries},
    }
    store = AlphaCheckpointStore(tmp_path / "checkpoints")
    store.write(
        "runtime-29a2", descent, persistence.replay_events(descent.id),
        simulation_config={"seed": descent.seed}, presentation_snapshot=snapshot,
        reason="population-test", created_at_unix_ms=1000,
    )
    loaded = store.load_latest()
    reconstructed = DescenderPopulationGenerator(loaded.payload["presentation"]["population_seed"]).generate(
        loaded.payload["presentation"]["ordered_descender_ids"]
    )
    assert {item.descender_id: item.visual_identity_digest for item in reconstructed.entries} == snapshot["identity_digests"]
    assert loaded.crawl.fingerprint() == descent.fingerprint()


def test_population_models_do_not_share_mutable_identity_state():
    population = DescenderPopulationGenerator("copy-isolation").generate(ids(2))
    dumped = population.model_dump(mode="json")
    dumped["entries"][0]["dna"]["appearance"]["equipment_visual_ids"].clear()
    assert population.entries[0].dna.appearance.equipment_visual_ids
    assert population.entries[1].dna.appearance.equipment_visual_ids


def test_population_payload_round_trip_is_schema_stable():
    population = DescenderPopulationGenerator("round-trip").generate(ids(12))
    from livingworld.descender_population import DescenderPopulation
    restored = DescenderPopulation.model_validate(json.loads(population.model_dump_json()))
    assert restored == population
