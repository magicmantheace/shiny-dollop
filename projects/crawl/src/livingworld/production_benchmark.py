from __future__ import annotations

import argparse
import json
import math
import statistics
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .benchmark import validate_world
from .continent_generation import generate_continent_world
from .domain import HistoricalEvent, ResourceStock, SettlementType, WorldState
from .institution_benchmark import validate_institutions
from .politics_benchmark import validate_politics
from .production import validate_production
from .world_engine import FinalWorldEngine


PRODUCTION_EVENT_TYPES = {
    "FAMINE",
    "SETTLEMENT_FOUNDED",
    "SETTLEMENT_ABANDONED",
    "WAR_DECLARED",
    "WAR_ENDED",
    "REGIONAL_SECESSION",
    "KINGDOM_FOUNDED",
    "KINGDOM_DESTROYED",
}

TRACKED_RESOURCES = (
    "grain",
    "flour",
    "food",
    "livestock",
    "meat",
    "leather",
    "logs",
    "lumber",
    "stone",
    "masonry",
    "iron_ore",
    "iron",
    "tools",
    "weapons",
    "fiber",
    "cloth",
    "clothing",
    "mana_crystal",
    "refined_mana",
    "magical_goods",
)


@dataclass
class ProductionCollector:
    counts: Counter[str] = field(default_factory=Counter)
    events: list[dict[str, Any]] = field(default_factory=list)
    max_events: int = 3000

    def __call__(self, event: HistoricalEvent) -> None:
        self.counts[event.type] += 1
        if event.type in PRODUCTION_EVENT_TYPES and len(self.events) < self.max_events:
            self.events.append(
                {
                    "id": event.id,
                    "type": event.type,
                    "date": event.occurred_at.model_dump(mode="json"),
                    "summary": event.summary,
                    "subject_ids": event.subject_ids,
                    "location_id": event.location_id,
                    "data": event.data,
                }
            )


def _active_settlements(world: WorldState):
    return [
        settlement
        for settlement in world.settlements.values()
        if settlement.population > 0 and settlement.type != SettlementType.RUIN
    ]


def _resource_quantity(world: WorldState, resource: str) -> float:
    return sum(
        settlement.resources.get(resource, ResourceStock(resource=resource)).quantity
        for settlement in _active_settlements(world)
    )


def _resource_capacity(world: WorldState, resource: str) -> float:
    return sum(
        settlement.resources.get(resource, ResourceStock(resource=resource)).capacity
        for settlement in _active_settlements(world)
        if resource in settlement.resources
    )


def _resource_fill(world: WorldState, resource: str) -> float:
    capacity = _resource_capacity(world, resource)
    if capacity <= 0:
        return 0.0
    return _resource_quantity(world, resource) / capacity


def production_metrics(
    world: WorldState,
    elapsed_seconds: float,
    collector: ProductionCollector,
) -> dict[str, Any]:
    settlements = _active_settlements(world)
    sites = [
        site
        for settlement in settlements
        for site in settlement.production_sites.values()
        if site.active
    ]
    worker_capacity = sum(site.worker_capacity for site in sites)
    assigned_workers = sum(site.assigned_workers for site in sites)
    material_shortage_settlements = sum(
        1 for settlement in settlements if settlement.production_shortages
    )
    labor_shortage_settlements = sum(
        1
        for settlement in settlements
        if any(key.startswith("labor:") for key in settlement.production_shortages)
    )
    severe_food_settlements = sum(1 for settlement in settlements if settlement.food_security < 0.30)
    low_food_settlements = sum(1 for settlement in settlements if settlement.food_security < 0.55)
    production_throughput = sum(
        sum(settlement.production_last_day.values()) for settlement in settlements
    )
    consumption_throughput = sum(
        sum(settlement.consumption_last_day.values()) for settlement in settlements
    )
    reserve_food = sum(
        kingdom.resource_reserves.get("food", ResourceStock(resource="food")).quantity
        for kingdom in world.kingdoms.values()
    )
    reserve_food_capacity = sum(
        kingdom.resource_reserves.get("food", ResourceStock(resource="food")).capacity
        for kingdom in world.kingdoms.values()
        if "food" in kingdom.resource_reserves
    )

    inventories = {resource: _resource_quantity(world, resource) for resource in TRACKED_RESOURCES}
    fills = {resource: _resource_fill(world, resource) for resource in TRACKED_RESOURCES}

    return {
        "world_year": world.date.year,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "population": world.total_population,
        "kingdoms": len(world.kingdoms),
        "settlements": len(settlements),
        "production_sites": len(sites),
        "labor_utilization": assigned_workers / max(1, worker_capacity),
        "material_shortage_settlements": material_shortage_settlements,
        "material_shortage_fraction": material_shortage_settlements / max(1, len(settlements)),
        "labor_shortage_settlements": labor_shortage_settlements,
        "labor_shortage_fraction": labor_shortage_settlements / max(1, len(settlements)),
        "average_food_security": statistics.fmean(s.food_security for s in settlements) if settlements else 0.0,
        "minimum_food_security": min((s.food_security for s in settlements), default=0.0),
        "low_food_settlements": low_food_settlements,
        "severe_food_settlements": severe_food_settlements,
        "average_health": statistics.fmean(s.health for s in settlements) if settlements else 0.0,
        "average_stability": statistics.fmean(s.stability for s in settlements) if settlements else 0.0,
        "production_throughput_last_day": production_throughput,
        "consumption_throughput_last_day": consumption_throughput,
        "kingdom_food_reserve": reserve_food,
        "kingdom_food_reserve_fill": reserve_food / max(1.0, reserve_food_capacity),
        "famine_events": collector.counts.get("FAMINE", 0),
        "active_wars": len(world.active_wars()),
        "inventories": inventories,
        "inventory_fill": fills,
    }


def balance_warnings(annual: list[dict[str, Any]]) -> list[str]:
    if not annual:
        return []

    warnings: list[str] = []
    final = annual[-1]
    recent = annual[-min(10, len(annual)):]

    if final["average_food_security"] < 0.45:
        warnings.append("Final average food security is below 0.45.")
    if final["severe_food_settlements"] > final["settlements"] * 0.25:
        warnings.append("More than 25% of final settlements have food security below 0.30.")
    if statistics.fmean(item["material_shortage_fraction"] for item in recent) > 0.80:
        warnings.append("More than 80% of settlements report a material shortage on average over the final decade.")
    if statistics.fmean(item["labor_shortage_fraction"] for item in recent) > 0.80:
        warnings.append("More than 80% of settlements report a labor shortage on average over the final decade.")
    if statistics.fmean(item["labor_utilization"] for item in recent) < 0.25:
        warnings.append("Production-site labor utilization averages below 0.25 over the final decade.")
    if final["kingdom_food_reserve_fill"] < 0.05:
        warnings.append("Explicit kingdom food reserves finish below 5% of capacity.")
    if final["production_throughput_last_day"] <= 0.0:
        warnings.append("Final daily production throughput is zero.")
    if final["consumption_throughput_last_day"] <= 0.0:
        warnings.append("Final daily material consumption is zero.")

    essential = ("food", "tools", "lumber", "iron", "clothing")
    for resource in essential:
        if statistics.fmean(item["inventory_fill"][resource] for item in recent) < 0.002:
            warnings.append(
                f"{resource} inventory averages below 0.2% of capacity over the final decade."
            )

    population_ratio = final["population"] / max(1, annual[0]["population"])
    if population_ratio < 0.25:
        warnings.append("Population fell below 25% of the first annual snapshot.")
    return warnings


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "# LivingWorld v0.3 Slice 3 Production Calibration",
        "",
        f"- **Seed:** `{report['seed']}`",
        f"- **Years simulated:** {summary['years_completed']}",
        f"- **Overall:** {'PASS' if summary['passed'] else 'FAIL'}",
        f"- **Total wall time:** {summary['total_elapsed_seconds']:.2f} seconds",
        f"- **Average seconds/year:** {summary['average_seconds_per_year']:.3f}",
        f"- **Initial population:** {summary['initial_population']:,}",
        f"- **Final population:** {summary['final_population']:,}",
        f"- **Final kingdoms:** {summary['final_kingdoms']}",
        f"- **Final settlements:** {summary['final_settlements']}",
        f"- **Final average food security:** {summary['final_average_food_security']:.3f}",
        f"- **Final labor utilization:** {summary['final_labor_utilization']:.3f}",
        f"- **Final material-shortage settlements:** {summary['final_material_shortage_settlements']}",
        f"- **Final labor-shortage settlements:** {summary['final_labor_shortage_settlements']}",
        f"- **Final kingdom food reserve fill:** {summary['final_kingdom_food_reserve_fill']:.3f}",
        "",
        "## Integrity",
        "",
        f"- Base-world invariant failures: **{len(report['base_invariant_errors'])}**",
        f"- Political invariant failures: **{len(report['political_invariant_errors'])}**",
        f"- Institutional invariant failures: **{len(report['institutional_invariant_errors'])}**",
        f"- Production invariant failures: **{len(report['production_invariant_errors'])}**",
        "",
        "## Balance warnings",
        "",
    ]
    if report["balance_warnings"]:
        lines.extend(f"- {warning}" for warning in report["balance_warnings"])
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Annual production state",
            "",
            "| Year | sec | Pop | K | S | Sites | Labor util | Material shortage S | Labor shortage S | Avg food | Min food | Severe food S | Prod/day | Cons/day | Kingdom reserve fill | Famines | Food fill | Tools fill | Lumber fill | Iron fill | Clothing fill |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in report["annual"]:
        lines.append(
            f"| {item['world_year']} | {item['elapsed_seconds']:.3f} | {item['population']:,} | {item['kingdoms']} | {item['settlements']} | "
            f"{item['production_sites']} | {item['labor_utilization']:.3f} | {item['material_shortage_settlements']} | "
            f"{item['labor_shortage_settlements']} | {item['average_food_security']:.3f} | {item['minimum_food_security']:.3f} | "
            f"{item['severe_food_settlements']} | {item['production_throughput_last_day']:.2f} | {item['consumption_throughput_last_day']:.2f} | "
            f"{item['kingdom_food_reserve_fill']:.3f} | {item['famine_events']} | {item['inventory_fill']['food']:.3f} | "
            f"{item['inventory_fill']['tools']:.3f} | {item['inventory_fill']['lumber']:.3f} | {item['inventory_fill']['iron']:.3f} | "
            f"{item['inventory_fill']['clothing']:.3f} |"
        )

    lines.extend(["", "## Final inventory quantities", ""])
    final = report["annual"][-1] if report["annual"] else None
    if final:
        for resource in TRACKED_RESOURCES:
            lines.append(
                f"- `{resource}`: {final['inventories'][resource]:.3f} "
                f"({final['inventory_fill'][resource]:.3%} of settlement capacity)"
            )

    for heading, errors in (
        ("Base-world invariant failures", report["base_invariant_errors"]),
        ("Political invariant failures", report["political_invariant_errors"]),
        ("Institutional invariant failures", report["institutional_invariant_errors"]),
        ("Production invariant failures", report["production_invariant_errors"]),
    ):
        if errors:
            lines.extend(["", f"## {heading}", ""])
            lines.extend(f"- {error}" for error in errors)

    lines.extend(["", "## Event counts", ""])
    for event_type in sorted(PRODUCTION_EVENT_TYPES):
        lines.append(f"- `{event_type}`: {report['event_counts'].get(event_type, 0)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_production_calibration(
    *,
    years: int,
    seed: str,
    name: str,
    output_dir: Path,
    fail_fast: bool = True,
) -> dict[str, Any]:
    if years <= 0:
        raise ValueError("years must be greater than zero")

    output_dir.mkdir(parents=True, exist_ok=True)
    collector = ProductionCollector()
    world = generate_continent_world(seed, name)
    engine = FinalWorldEngine(world, event_sink=collector)
    initial_population = world.total_population

    base_initial = validate_world(world, initial_population)
    politics_initial = validate_politics(world)
    institutions_initial = validate_institutions(world)
    production_initial = validate_production(world)
    initial_errors = base_initial.errors + politics_initial + institutions_initial + production_initial
    if initial_errors:
        raise RuntimeError(
            "initial world failed calibration invariants: " + "; ".join(initial_errors[:10])
        )

    annual: list[dict[str, Any]] = []
    base_errors: list[str] = []
    political_errors: list[str] = []
    institution_errors: list[str] = []
    production_errors: list[str] = []
    durations: list[float] = []
    started = time.perf_counter()

    for index in range(1, years + 1):
        year_started = time.perf_counter()
        engine.advance_years(1, ignore_pause=True)
        elapsed = time.perf_counter() - year_started
        durations.append(elapsed)

        base_check = validate_world(world, initial_population)
        politics_check = validate_politics(world)
        institutions_check = validate_institutions(world)
        production_check = validate_production(world)

        base_errors.extend(f"Y{world.date.year}: {error}" for error in base_check.errors)
        political_errors.extend(f"Y{world.date.year}: {error}" for error in politics_check)
        institution_errors.extend(f"Y{world.date.year}: {error}" for error in institutions_check)
        production_errors.extend(f"Y{world.date.year}: {error}" for error in production_check)

        metrics = production_metrics(world, elapsed, collector)
        annual.append(metrics)
        print(
            f"Year {world.date.year} ({index}/{years}) | {elapsed:.3f}s | pop {metrics['population']:,} | "
            f"settlements {metrics['settlements']} | labor {metrics['labor_utilization']:.3f} | "
            f"food {metrics['average_food_security']:.3f} | material shortages {metrics['material_shortage_settlements']} | "
            f"reserve {metrics['kingdom_food_reserve_fill']:.3f}",
            flush=True,
        )

        if (
            base_check.errors
            or politics_check
            or institutions_check
            or production_check
        ) and fail_fast:
            break

    total_elapsed = time.perf_counter() - started
    final = annual[-1] if annual else production_metrics(world, 0.0, collector)
    warnings = balance_warnings(annual)
    passed = (
        not base_errors
        and not political_errors
        and not institution_errors
        and not production_errors
        and len(annual) == years
    )
    report = {
        "seed": seed,
        "world_name": name,
        "annual": annual,
        "event_counts": dict(collector.counts),
        "production_events": collector.events,
        "base_invariant_errors": base_errors,
        "political_invariant_errors": political_errors,
        "institutional_invariant_errors": institution_errors,
        "production_invariant_errors": production_errors,
        "balance_warnings": warnings,
        "summary": {
            "passed": passed,
            "years_requested": years,
            "years_completed": len(annual),
            "total_elapsed_seconds": total_elapsed,
            "average_seconds_per_year": statistics.fmean(durations) if durations else 0.0,
            "initial_population": initial_population,
            "final_population": world.total_population,
            "final_kingdoms": len(world.kingdoms),
            "final_settlements": final["settlements"],
            "final_production_sites": final["production_sites"],
            "final_average_food_security": final["average_food_security"],
            "final_minimum_food_security": final["minimum_food_security"],
            "final_labor_utilization": final["labor_utilization"],
            "final_material_shortage_settlements": final["material_shortage_settlements"],
            "final_labor_shortage_settlements": final["labor_shortage_settlements"],
            "final_kingdom_food_reserve_fill": final["kingdom_food_reserve_fill"],
            "final_production_throughput": final["production_throughput_last_day"],
            "famine_events": final["famine_events"],
        },
    }

    (output_dir / "production-calibration.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    write_markdown_report(output_dir / "PRODUCTION_CALIBRATION.md", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a LivingWorld v0.3 Slice 3 production/labor calibration simulation."
    )
    parser.add_argument("--years", type=int, default=100)
    parser.add_argument("--seed", default="production-calibration-v0.3")
    parser.add_argument("--name", default="Eldara Production Calibration")
    parser.add_argument("--output", default="validation/production-calibration")
    parser.add_argument("--no-fail-fast", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_production_calibration(
        years=args.years,
        seed=args.seed,
        name=args.name,
        output_dir=Path(args.output),
        fail_fast=not args.no_fail_fast,
    )
    summary = report["summary"]
    print("")
    print(f"OVERALL: {'PASS' if summary['passed'] else 'FAIL'}")
    print(f"Years completed: {summary['years_completed']}/{summary['years_requested']}")
    print(f"Population: {summary['initial_population']:,} -> {summary['final_population']:,}")
    print(f"Average food security: {summary['final_average_food_security']:.3f}")
    print(f"Labor utilization: {summary['final_labor_utilization']:.3f}")
    print(f"Material-shortage settlements: {summary['final_material_shortage_settlements']}")
    print(f"Kingdom food reserve fill: {summary['final_kingdom_food_reserve_fill']:.3f}")
    print(f"Balance warnings: {len(report['balance_warnings'])}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
