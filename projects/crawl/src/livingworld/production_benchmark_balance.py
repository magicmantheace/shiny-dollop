from __future__ import annotations

from pathlib import Path
from typing import Any

from . import production_benchmark as base
from .domain import ResourceStock, WorldState
from .production_food_balance import GRAIN_NUTRITION


_BASE_PRODUCTION_METRICS = base.production_metrics
_BASE_BALANCE_WARNINGS = base.balance_warnings


def production_metrics_with_strategic_reserves(
    world: WorldState,
    elapsed_seconds: float,
    collector: base.ProductionCollector,
) -> dict[str, Any]:
    metrics = _BASE_PRODUCTION_METRICS(world, elapsed_seconds, collector)

    prepared_quantity = sum(
        kingdom.resource_reserves.get("food", ResourceStock(resource="food")).quantity
        for kingdom in world.kingdoms.values()
    )
    prepared_capacity = sum(
        kingdom.resource_reserves.get("food", ResourceStock(resource="food")).capacity
        for kingdom in world.kingdoms.values()
        if "food" in kingdom.resource_reserves
    )
    grain_quantity = sum(
        kingdom.resource_reserves.get("grain", ResourceStock(resource="grain")).quantity
        for kingdom in world.kingdoms.values()
    )
    grain_capacity = sum(
        kingdom.resource_reserves.get("grain", ResourceStock(resource="grain")).capacity
        for kingdom in world.kingdoms.values()
        if "grain" in kingdom.resource_reserves
    )
    settlement_population = sum(
        max(0, world.settlements[settlement_id].population)
        for kingdom in world.kingdoms.values()
        for settlement_id in kingdom.settlement_ids
        if settlement_id in world.settlements
    )

    nutrition_available = prepared_quantity + grain_quantity * GRAIN_NUTRITION
    strategic_target = max(1.0, settlement_population * 0.45)
    strategic_fill = min(1.0, nutrition_available / strategic_target)

    metrics["prepared_food_reserve_fill"] = prepared_quantity / max(1.0, prepared_capacity)
    metrics["grain_reserve_fill"] = grain_quantity / max(1.0, grain_capacity)
    metrics["strategic_food_reserve_nutrition"] = nutrition_available
    # Keep the existing field name so the report/warning machinery remains backward
    # compatible, but make it represent total strategic food readiness rather than
    # only the legacy prepared-food stock.
    metrics["kingdom_food_reserve_fill"] = strategic_fill
    return metrics


def balance_warnings_with_distribution(annual: list[dict[str, Any]]) -> list[str]:
    warnings = list(_BASE_BALANCE_WARNINGS(annual))
    if not annual:
        return warnings

    final = annual[-1]
    exposure = sum(max(1, int(item.get("settlements", 0))) for item in annual)
    famine_events = int(final.get("famine_events", 0))
    famine_rate = famine_events / max(1, exposure)
    if famine_rate > 0.01:
        warnings.append(
            "Famine events exceeded 1 per 100 settlement-years; food distribution remains chronically unstable."
        )

    severe = int(final.get("severe_food_settlements", 0))
    settlements = max(1, int(final.get("settlements", 0)))
    severe_fraction = severe / settlements
    if severe_fraction > 0.10 and not any(
        "food security below 0.30" in warning for warning in warnings
    ):
        warnings.append(
            "More than 10% of final settlements have food security below 0.30."
        )
    return warnings


def run_production_calibration(
    *,
    years: int,
    seed: str,
    name: str,
    output_dir: Path,
    fail_fast: bool = True,
) -> dict[str, Any]:
    original_metrics = base.production_metrics
    original_warnings = base.balance_warnings
    base.production_metrics = production_metrics_with_strategic_reserves
    base.balance_warnings = balance_warnings_with_distribution
    try:
        return base.run_production_calibration(
            years=years,
            seed=seed,
            name=name,
            output_dir=output_dir,
            fail_fast=fail_fast,
        )
    finally:
        base.production_metrics = original_metrics
        base.balance_warnings = original_warnings


def main() -> int:
    args = base.build_parser().parse_args()
    report = run_production_calibration(
        years=args.years,
        seed=args.seed,
        name=args.name,
        output_dir=Path(args.output),
        fail_fast=not args.no_fail_fast,
    )
    summary = report["summary"]
    final = report["annual"][-1] if report["annual"] else {}
    print("")
    print(f"OVERALL: {'PASS' if summary['passed'] else 'FAIL'}")
    print(f"Years completed: {summary['years_completed']}/{summary['years_requested']}")
    print(f"Average food security: {summary['final_average_food_security']:.3f}")
    print(f"Labor utilization: {summary['final_labor_utilization']:.3f}")
    print(f"Strategic food reserve: {summary['final_kingdom_food_reserve_fill']:.3f}")
    if final:
        print(f"Prepared reserve fill: {final.get('prepared_food_reserve_fill', 0.0):.3f}")
        print(f"Grain reserve fill: {final.get('grain_reserve_fill', 0.0):.3f}")
        print(f"Famine events: {final.get('famine_events', 0)}")
    print(f"Balance warnings: {len(report['balance_warnings'])}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
