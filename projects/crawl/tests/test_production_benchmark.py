from pathlib import Path

from livingworld.continent_generation import generate_continent_world
from livingworld.production import validate_production
from livingworld.production_benchmark_balance import (
    balance_warnings_with_distribution,
    run_production_calibration,
)
from livingworld.world_engine import FinalWorldEngine


def test_production_calibration_runs_and_writes_reports(tmp_path: Path) -> None:
    report = run_production_calibration(
        years=1,
        seed="production-calibration-test",
        name="Eldara",
        output_dir=tmp_path,
    )

    assert report["summary"]["passed"] is True
    assert report["summary"]["years_completed"] == 1
    assert report["production_invariant_errors"] == []
    assert report["annual"][0]["production_sites"] > 0
    assert report["annual"][0]["production_throughput_last_day"] > 0
    assert "grain_reserve_fill" in report["annual"][0]
    assert (tmp_path / "PRODUCTION_CALIBRATION.md").exists()
    assert (tmp_path / "production-calibration.json").exists()


def test_production_validation_detects_negative_inventory() -> None:
    world = generate_continent_world("production-validation-test", "Eldara")
    FinalWorldEngine(world)
    settlement = world.settlements[sorted(world.settlements)[0]]
    settlement.resources["food"].quantity = -1.0

    errors = validate_production(world)

    assert any("negative/non-finite inventory" in error for error in errors)


def test_distribution_warning_detects_repeated_famine_even_with_good_averages() -> None:
    annual = [
        {
            "population": 10_000,
            "settlements": 100,
            "average_food_security": 0.80,
            "severe_food_settlements": 0,
            "material_shortage_fraction": 0.20,
            "labor_shortage_fraction": 0.10,
            "labor_utilization": 0.80,
            "kingdom_food_reserve_fill": 0.70,
            "production_throughput_last_day": 100.0,
            "consumption_throughput_last_day": 90.0,
            "inventory_fill": {
                "food": 0.50,
                "tools": 0.50,
                "lumber": 0.50,
                "iron": 0.50,
                "clothing": 0.50,
            },
            "famine_events": 2,
        }
    ]

    warnings = balance_warnings_with_distribution(annual)

    assert any("Famine events exceeded 1 per 100 settlement-years" in warning for warning in warnings)
