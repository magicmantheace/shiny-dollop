from __future__ import annotations

from livingworld.benchmark import EventCollector, annual_metrics, historical_map_snapshot, validate_world
from livingworld.continent_generation import generate_continent_world
from livingworld.world_engine import FinalWorldEngine


def test_generated_continent_passes_long_horizon_invariants() -> None:
    world = generate_continent_world("benchmark-invariants", "Benchmark")
    result = validate_world(world, world.total_population)

    assert result.ok
    assert result.errors == []


def test_short_exact_simulation_stays_structurally_valid() -> None:
    world = generate_continent_world("benchmark-short-run", "Benchmark")
    initial_population = world.total_population
    collector = EventCollector()
    engine = FinalWorldEngine(world, event_sink=collector)

    engine.advance_days(2, ignore_pause=True)
    result = validate_world(world, initial_population)

    assert result.ok
    assert world.date.ordinal_hour() == 48
    assert sum(collector.counts.values()) >= 0


def test_invariant_checker_detects_population_accounting_error() -> None:
    world = generate_continent_world("benchmark-detects-corruption", "Benchmark")
    settlement = next(iter(world.settlements.values()))
    settlement.population += 1

    result = validate_world(world)

    assert not result.ok
    assert any("ancestry total" in error for error in result.errors)


def test_historical_map_snapshot_captures_control_state() -> None:
    world = generate_continent_world("benchmark-map", "Benchmark")
    snapshot = historical_map_snapshot(world)

    assert snapshot["population"] == world.total_population
    assert len(snapshot["settlements"]) == len(world.settlements)
    assert len(snapshot["kingdoms"]) == len(world.kingdoms)
    assert snapshot["date"] == world.date.model_dump(mode="json")


def test_annual_metrics_include_warfare_and_frontier_counts() -> None:
    world = generate_continent_world("benchmark-metrics", "Benchmark")
    metrics = annual_metrics(world, 1.25, [])

    assert metrics["elapsed_seconds"] == 1.25
    assert metrics["population"] == world.total_population
    assert metrics["kingdoms"] == len(world.kingdoms)
    assert "active_fronts" in metrics
    assert "active_claims" in metrics
