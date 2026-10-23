from pathlib import Path

from livingworld.continent_generation import generate_continent_world
from livingworld.politics_benchmark import run_political_calibration, validate_politics
from livingworld.world_engine import FinalWorldEngine


def test_political_validator_accepts_initialized_continent() -> None:
    world = generate_continent_world("politics-benchmark-valid", "Eldara")
    FinalWorldEngine(world)

    assert validate_politics(world) == []


def test_political_validator_catches_foreign_faction_member() -> None:
    world = generate_continent_world("politics-benchmark-invalid", "Eldara")
    FinalWorldEngine(world)
    kingdoms = [world.kingdoms[key] for key in sorted(world.kingdoms)[:2]]
    faction = world.political_factions[kingdoms[0].faction_ids[0]]
    foreign = next(npc for npc in world.npcs.values() if npc.kingdom_id == kingdoms[1].id and npc.alive)
    faction.member_npc_ids = [foreign.id]

    errors = validate_politics(world)

    assert any("member" in error and kingdoms[1].id in error for error in errors)


def test_short_political_calibration_runs_cleanly(tmp_path: Path) -> None:
    report = run_political_calibration(
        years=1,
        seed="politics-benchmark-short",
        name="Eldara",
        output_dir=tmp_path,
    )

    assert report["summary"]["passed"]
    assert report["summary"]["years_completed"] == 1
    assert report["base_invariant_errors"] == []
    assert report["political_invariant_errors"] == []
    assert report["annual"][0]["active_factions"] > 0
    assert (tmp_path / "POLITICS_CALIBRATION.md").exists()
