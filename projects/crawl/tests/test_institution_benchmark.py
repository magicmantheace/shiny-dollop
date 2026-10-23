from pathlib import Path

from livingworld.continent_generation import generate_continent_world
from livingworld.institution_benchmark import run_institution_calibration, validate_institutions
from livingworld.world_engine import FinalWorldEngine


def test_institution_calibration_runs_and_writes_reports(tmp_path: Path) -> None:
    report = run_institution_calibration(
        years=1,
        seed="institution-calibration-test",
        name="Eldara",
        output_dir=tmp_path,
    )

    assert report["summary"]["passed"] is True
    assert report["summary"]["years_completed"] == 1
    assert report["institutional_invariant_errors"] == []
    assert (tmp_path / "INSTITUTION_CALIBRATION.md").exists()
    assert (tmp_path / "institution-calibration.json").exists()


def test_institution_validation_detects_missing_compliance() -> None:
    world = generate_continent_world("institution-validation-test", "Eldara")
    FinalWorldEngine(world)
    kingdom = world.kingdoms[sorted(world.kingdoms)[0]]
    settlement_id = kingdom.settlement_ids[0]
    kingdom.policy_compliance.pop(settlement_id)

    errors = validate_institutions(world)

    assert any("compliance settlement mismatch" in error for error in errors)
