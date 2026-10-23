"""Generate deterministic Slice 29A.2 population/checkpoint/performance proof."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
from time import perf_counter
import tracemalloc

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.descender_population import DescenderPopulationGenerator, population_diversity
from livingworld.feed_channel_registry import FeedChannelRegistry
from livingworld.headless_mvp_simulation import HeadlessCrawlMVP
from livingworld.runtime_checkpoint import AlphaCheckpointStore


SEED = "underreach-29a2-population-proof"
LIVE_IDS = tuple(f"live_descender_{index:03d}" for index in range(10))
LIVE_SPECIES = {item: ("human" if index < 6 else "dwarf") for index, item in enumerate(LIVE_IDS)}
LIVE_VARIANTS = {
    item: (("human_average", "human_short_heavy", "human_tall_thin")[index % 3]
           if index < 6 else ("dwarf_average", "dwarf_heavy", "dwarf_alt")[(index - 6) % 3])
    for index, item in enumerate(LIVE_IDS)
}


def write_json(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def identities(population) -> dict:
    return {
        item.descender_id: {
            "character_dna_digest": item.dna.digest(),
            "renderer_manifest_digest": item.renderer_manifest.digest(),
            "visual_identity_digest": item.visual_identity_digest,
            "species": item.dna.species,
            "body_parameters": item.renderer_manifest.body_morphs,
            "face_parameters": item.renderer_manifest.face_morphs,
            "hair": item.dna.appearance.current_hair_asset,
            "materials": item.renderer_manifest.material_variants,
            "clothing": item.dna.appearance.clothing_asset_ids,
            "equipment": item.dna.appearance.equipment_visual_ids,
            "visual_variant": item.visual_variant,
            "style_profile": item.style_profile,
        }
        for item in population.entries
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    tracemalloc.start()
    total_started = perf_counter()
    generator = DescenderPopulationGenerator(SEED, species_weights={"human": 0.6, "dwarf": 0.4})

    human_ids = [f"population_human_{index:03d}" for index in range(100)]
    dwarf_ids = [f"population_dwarf_{index:03d}" for index in range(100)]
    data_started = perf_counter()
    data_population = generator.generate(
        [*human_ids, *dwarf_ids],
        forced_species={**{item: "human" for item in human_ids}, **{item: "dwarf" for item in dwarf_ids}},
    )
    data_generation_seconds = perf_counter() - data_started
    diversity = population_diversity(data_population)

    stress_started = perf_counter()
    stress_generator = DescenderPopulationGenerator(f"{SEED}:stress")
    stress = stress_generator.generate(f"stress_descender_{index:04d}" for index in range(1000))
    stress_seconds = perf_counter() - stress_started
    stress_diversity = population_diversity(stress)

    live_started = perf_counter()
    live_population = generator.generate(LIVE_IDS, forced_species=LIVE_SPECIES, forced_variants=LIVE_VARIANTS)
    live_generation_seconds = perf_counter() - live_started
    pre = identities(live_population)
    warm_started = perf_counter()
    warm_population = generator.generate(LIVE_IDS, forced_species=LIVE_SPECIES, forced_variants=LIVE_VARIANTS)
    warm_seconds = perf_counter() - warm_started
    post_direct = identities(warm_population)

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    service = CrawlLifecycleService(persistence)
    descent = service.create_seeded_crawl(
        seed="crawl-v09-death-persistence",
        crawler_ids=[*LIVE_IDS, "live_descender_010", "live_descender_011"],
        floor_count=8,
        crawl_id="descent_underreach_29a2_population",
    )
    service.start(descent)
    simulation = HeadlessCrawlMVP(service, intermission_ticks=2, director_interval=5)
    simulation.prepare(descent)
    for _ in range(90):
        if descent.status.value != "running":
            break
        simulation.step(descent)
    before_fingerprint = descent.fingerprint()

    registry = FeedChannelRegistry(descent.id, default_viewer_id="population_qa")
    registry.register(descent)
    registry.register_presentation_identities({
        key: {
            "species": value["species"], "visual_identity_digest": value["visual_identity_digest"],
            "visual_variant": value["visual_variant"], "style_profile": value["style_profile"],
            "detail_tier": "focused",
        }
        for key, value in pre.items()
    })
    registry.update(
        descent, persistence.replay_events(descent.id), presentation_tick=90,
        presentation_seconds=40.5, buffered_tick=descent.current_tick, camera_available_ids=LIVE_IDS,
    )
    channels = registry.directory(descent, viewer_id="population_qa")
    feed_payload_bytes = len(json.dumps(channels, sort_keys=True).encode("utf-8"))
    if descent.fingerprint() != before_fingerprint:
        raise RuntimeError("Population/Feed projection mutated simulation truth")

    checkpoint = AlphaCheckpointStore(output / "checkpoints")
    snapshot = {
        "population_seed": SEED,
        "ordered_descender_ids": list(LIVE_IDS),
        "forced_species": LIVE_SPECIES,
        "forced_variants": LIVE_VARIANTS,
        "population_digest": live_population.population_digest,
        "identities": pre,
        "terminal_statuses": {
            actor_id: descent.participants[actor_id].status.value for actor_id in LIVE_IDS
        },
        "channel_mapping": {item["focus_descender_id"]: item["channel_id"] for item in channels},
    }
    written = checkpoint.write(
        "underreach-29a2-population-qa", descent, persistence.replay_events(descent.id),
        simulation_config={"seed": descent.seed, "floor_count": 8},
        presentation_snapshot=snapshot,
        feed_snapshot=registry.reconnect_snapshot(), reason="29a2_population_qa",
        created_at_unix_ms=1_787_696_000_000,
    )
    loaded = checkpoint.load_latest()
    persisted = loaded.payload["presentation"]
    reconstructed = DescenderPopulationGenerator(persisted["population_seed"]).generate(
        persisted["ordered_descender_ids"], forced_species=persisted["forced_species"],
        forced_variants=persisted["forced_variants"]
    )
    post = identities(reconstructed)
    loaded_ids = list(loaded.crawl.history_event_ids)
    source_ids = list(descent.history_event_ids)
    duplicate_events = len(loaded_ids) - len(set(loaded_ids))
    skipped_events = len(set(source_ids) - set(loaded_ids))
    if pre != post or persisted["identities"] != post:
        raise RuntimeError("Checkpoint reconstruction rerolled one or more identities")
    if loaded.crawl.fingerprint() != before_fingerprint or duplicate_events or skipped_events:
        raise RuntimeError("Checkpoint reconstruction changed canonical truth")

    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    terminal_ids = [key for key, value in snapshot["terminal_statuses"].items() if value in {"dead", "eliminated"}]
    population_debug = {
        "protocol": "underreach.descender-population-debug.v1",
        "implementation_version": "29a2.1",
        "population_seed": SEED,
        "species_weights": generator.species_weights,
        "data_population_count": len(data_population.entries),
        "data_species_counts": diversity["species_counts"],
        "live_descender_ids": list(LIVE_IDS),
        "live_species_counts": dict(sorted(Counter(item.dna.species for item in live_population.entries).items())),
        "live_population_digest": live_population.population_digest,
        "visual_identity_digests": {key: value["visual_identity_digest"] for key, value in pre.items()},
        "asset_registry_digest": live_population.asset_registry_digest,
        "cache": generator.cache.diagnostics(),
        "detail_tiers": {item.descender_id: item.detail_tier for item in live_population.entries},
        "loadout_authority": "presentation_fixture",
        "simulation_fingerprint_before": before_fingerprint,
        "simulation_fingerprint_after": descent.fingerprint(),
        "simulation_fingerprint_immutable": descent.fingerprint() == before_fingerprint,
    }
    diversity_report = {
        **diversity,
        "human_count": 100,
        "dwarf_count": 100,
        "stress_population_count": len(stress.entries),
        "stress_generation_seconds": round(stress_seconds, 6),
        "stress_exact_dna_duplicate_count": stress_diversity["exact_dna_duplicate_count"],
        "stress_exact_renderer_manifest_duplicate_count": stress_diversity["exact_renderer_manifest_duplicate_count"],
        "stress_population_digest": stress.population_digest,
    }
    reconstruction_report = {
        "protocol": "underreach.population-reconstruction.v1",
        "checkpoint_path": str(written.path),
        "checkpoint_digest": written.payload["digest"],
        "canonical_fingerprint_equal": loaded.crawl.fingerprint() == before_fingerprint,
        "population_digest_equal": reconstructed.population_digest == persisted["population_digest"],
        "all_identity_fields_equal": pre == post,
        "direct_warm_reconstruction_equal": pre == post_direct,
        "pre_resume_identities": pre,
        "post_resume_identities": post,
        "terminal_actor_ids": terminal_ids,
        "terminal_statuses_equal": {
            key: loaded.crawl.participants[key].status.value == value
            for key, value in persisted["terminal_statuses"].items()
        },
        "channel_mapping_equal": persisted["channel_mapping"] == {item["focus_descender_id"]: item["channel_id"] for item in channels},
        "ledger_duplicate_canonical_events": duplicate_events,
        "ledger_skipped_canonical_events": skipped_events,
    }
    performance_report = {
        "protocol": "underreach.population-performance.v1",
        "data_population_generation_seconds": round(data_generation_seconds, 6),
        "live_population_cold_generation_seconds": round(live_generation_seconds, 6),
        "live_population_warm_reconstruction_seconds": round(warm_seconds, 6),
        "stress_1000_generation_seconds": round(stress_seconds, 6),
        "total_population_setup_seconds": round(perf_counter() - total_started, 6),
        "python_traced_current_bytes": current_bytes,
        "python_traced_peak_bytes": peak_bytes,
        "estimated_identity_bytes_per_live_actor": round(len(json.dumps(pre, sort_keys=True).encode("utf-8")) / len(pre), 2),
        "feed_payload_bytes": feed_payload_bytes,
        "feed_payload_bytes_per_channel": round(feed_payload_bytes / len(channels), 2),
        "feed_channel_count": len(channels),
        "channel_registry_memory_bytes": len(json.dumps(registry.reconnect_snapshot(), sort_keys=True).encode("utf-8")),
        "average_feed_projection_ms": registry.diagnostics()["average_channel_projection_ms"],
        "maximum_feed_projection_ms": registry.diagnostics()["maximum_channel_projection_ms"],
        "average_camera_decision_ms": registry.diagnostics()["average_automatic_focus_decision_ms"],
        "maximum_camera_decision_ms": registry.diagnostics()["maximum_automatic_focus_decision_ms"],
        "cache": generator.cache.diagnostics(),
    }
    write_json(output / "population_debug.json", population_debug)
    write_json(output / "diversity_report.json", diversity_report)
    write_json(output / "reconstruction_report.json", reconstruction_report)
    write_json(output / "performance_report.json", performance_report)
    print(json.dumps({
        "population_digest": live_population.population_digest,
        "data_humans": 100, "data_dwarfs": 100, "stress_count": 1000,
        "stress_duplicate_dna": stress_diversity["exact_dna_duplicate_count"],
        "reconstruction_equal": pre == post,
        "output": str(output),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
