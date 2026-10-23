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

from .continent_generation import generate_continent_world
from .domain import CampStatus, HistoricalEvent, SettlementType, WarState, WorldState
from .world_engine import FinalWorldEngine


MAJOR_EVENT_TYPES = {
    "WAR_DECLARED",
    "WAR_ENDED",
    "BORDER_CHANGED",
    "SETTLEMENT_OCCUPIED",
    "KINGDOM_VASSALIZED",
    "SETTLEMENT_FOUNDED",
    "SETTLEMENT_ABANDONED",
    "RULER_SUCCEEDED",
    "REFUGEE_CAMP_FORMED",
}


@dataclass
class EventCollector:
    counts: Counter[str] = field(default_factory=Counter)
    major_events: list[dict[str, Any]] = field(default_factory=list)
    max_major_events: int = 5_000

    def __call__(self, event: HistoricalEvent) -> None:
        self.counts[event.type] += 1
        if event.type in MAJOR_EVENT_TYPES or event.importance >= 0.90:
            if len(self.major_events) < self.max_major_events:
                self.major_events.append({
                    "id": event.id,
                    "type": event.type,
                    "date": event.occurred_at.model_dump(mode="json"),
                    "summary": event.summary,
                    "subject_ids": event.subject_ids,
                    "location_id": event.location_id,
                    "importance": event.importance,
                })


@dataclass
class InvariantResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def _finite(value: float) -> bool:
    return math.isfinite(float(value))


def validate_world(world: WorldState, initial_population: int | None = None) -> InvariantResult:
    """Validate structural invariants without imposing a preferred historical outcome."""
    result = InvariantResult()

    settlement_population = 0
    active_settlements = 0
    for settlement in world.settlements.values():
        if settlement.population < 0:
            result.errors.append(f"{settlement.id}: negative population {settlement.population}")
        ancestry_total = sum(settlement.ancestry_population.values())
        if ancestry_total != settlement.population:
            result.errors.append(
                f"{settlement.id}: ancestry total {ancestry_total} != population {settlement.population}"
            )
        if any(value < 0 for value in settlement.ancestry_population.values()):
            result.errors.append(f"{settlement.id}: negative ancestry population")
        if not 0.0 <= settlement.food_security <= 1.0:
            result.errors.append(f"{settlement.id}: food_security out of range")
        if not 0.0 <= settlement.stability <= 1.0:
            result.errors.append(f"{settlement.id}: stability out of range")
        if not 0.0 <= settlement.health <= 1.0:
            result.errors.append(f"{settlement.id}: health out of range")
        if settlement.occupied_by_kingdom_id and settlement.occupied_by_kingdom_id not in world.kingdoms:
            result.errors.append(f"{settlement.id}: unknown occupying kingdom")
        if settlement.besieged_by_kingdom_id and settlement.besieged_by_kingdom_id not in world.kingdoms:
            result.errors.append(f"{settlement.id}: unknown besieging kingdom")
        if not 0.0 <= settlement.siege_progress <= 1.0:
            result.errors.append(f"{settlement.id}: siege progress out of range")
        settlement_population += settlement.population
        if settlement.population > 0 and settlement.type != SettlementType.RUIN:
            active_settlements += 1
            owner = world.kingdoms.get(settlement.kingdom_id)
            if not owner:
                result.errors.append(f"{settlement.id}: unknown owning kingdom {settlement.kingdom_id}")
            elif settlement.id not in owner.settlement_ids:
                result.errors.append(f"{settlement.id}: missing from owner settlement list")

    camp_population = 0
    for camp in world.refugee_camps.values():
        if camp.people < 0:
            result.errors.append(f"{camp.id}: negative camp population")
        if sum(camp.ancestry_population.values()) != camp.people:
            result.errors.append(f"{camp.id}: ancestry total does not match camp population")
        if camp.host_settlement_id not in world.settlements:
            result.errors.append(f"{camp.id}: unknown host settlement")
        if camp.host_kingdom_id not in world.kingdoms:
            result.errors.append(f"{camp.id}: unknown host kingdom")
        if camp.origin_kingdom_id not in world.kingdoms:
            result.errors.append(f"{camp.id}: unknown origin kingdom")
        if camp.status != CampStatus.CLOSED:
            camp_population += camp.people

    expected_population = settlement_population + camp_population
    if world.total_population != expected_population:
        result.errors.append(
            f"world total_population {world.total_population} != component total {expected_population}"
        )
    if world.total_population <= 0:
        result.errors.append("world population collapsed to zero")
    if active_settlements <= 0:
        result.errors.append("no active settlements remain")

    if initial_population:
        ratio = world.total_population / initial_population
        if ratio < 0.10:
            result.warnings.append(f"population fell below 10% of start ({ratio:.2%})")
        elif ratio > 10.0:
            result.warnings.append(f"population exceeded 10x start ({ratio:.2f}x)")

    for kingdom in world.kingdoms.values():
        if kingdom.capital_settlement_id not in world.settlements:
            result.errors.append(f"{kingdom.id}: capital settlement missing")
        if kingdom.overlord_kingdom_id and kingdom.overlord_kingdom_id not in world.kingdoms:
            result.errors.append(f"{kingdom.id}: unknown overlord")
        for settlement_id in kingdom.settlement_ids:
            settlement = world.settlements.get(settlement_id)
            if not settlement:
                result.errors.append(f"{kingdom.id}: references missing settlement {settlement_id}")
            elif settlement.kingdom_id != kingdom.id:
                result.errors.append(
                    f"{kingdom.id}: lists {settlement_id} owned by {settlement.kingdom_id}"
                )
        for claim_id in kingdom.claims:
            if claim_id not in world.territory_claims:
                result.errors.append(f"{kingdom.id}: references missing claim {claim_id}")

    for npc in world.npcs.values():
        if not npc.alive:
            continue
        if npc.settlement_id not in world.settlements:
            result.errors.append(f"{npc.id}: unknown settlement {npc.settlement_id}")
        if npc.kingdom_id not in world.kingdoms:
            result.errors.append(f"{npc.id}: unknown kingdom {npc.kingdom_id}")
        if not _finite(npc.health) or not 0.0 <= npc.health <= 1.0:
            result.errors.append(f"{npc.id}: invalid health")

    for route in world.trade_routes.values():
        if route.origin_settlement_id not in world.settlements:
            result.errors.append(f"{route.id}: missing origin settlement")
        if route.destination_settlement_id not in world.settlements:
            result.errors.append(f"{route.id}: missing destination settlement")
        if route.capacity < 0 or not _finite(route.capacity):
            result.errors.append(f"{route.id}: invalid capacity")

    for army in world.armies.values():
        if army.kingdom_id not in world.kingdoms:
            result.errors.append(f"{army.id}: unknown kingdom")
        if army.location_settlement_id not in world.settlements:
            result.errors.append(f"{army.id}: unknown location settlement")
        if army.destination_settlement_id and army.destination_settlement_id not in world.settlements:
            result.errors.append(f"{army.id}: unknown destination settlement")
        if army.supply_source_settlement_id and army.supply_source_settlement_id not in world.settlements:
            result.errors.append(f"{army.id}: unknown supply source settlement")
        if army.troop_count < 0:
            result.errors.append(f"{army.id}: negative troop count")
        if not 0.0 <= army.supply_efficiency <= 1.0:
            result.errors.append(f"{army.id}: supply efficiency out of range")

    for war in world.wars.values():
        if war.attacker_kingdom_id not in world.kingdoms or war.defender_kingdom_id not in world.kingdoms:
            result.errors.append(f"{war.id}: missing belligerent kingdom")
        for settlement_id in war.front_settlement_ids:
            if settlement_id not in world.settlements:
                result.errors.append(f"{war.id}: missing front settlement {settlement_id}")
        for settlement_id, progress in war.siege_progress.items():
            if settlement_id not in world.settlements:
                result.errors.append(f"{war.id}: missing siege settlement {settlement_id}")
            if not 0.0 <= progress <= 1.0:
                result.errors.append(f"{war.id}: siege progress out of range")
        for settlement_id, occupier_id in war.occupation_by_settlement.items():
            if settlement_id not in world.settlements:
                result.errors.append(f"{war.id}: missing occupied settlement {settlement_id}")
            if occupier_id not in world.kingdoms:
                result.errors.append(f"{war.id}: missing occupying kingdom {occupier_id}")
        if not 0.0 <= war.attacker_exhaustion <= 1.0 or not 0.0 <= war.defender_exhaustion <= 1.0:
            result.errors.append(f"{war.id}: war exhaustion out of range")
        if war.state == WarState.ENDED and war.ended_at is None:
            result.errors.append(f"{war.id}: ended war missing ended_at")

    for claim_id, claim in world.territory_claims.items():
        settlement_id = claim.get("settlement_id")
        kingdom_id = claim.get("kingdom_id")
        if settlement_id not in world.settlements:
            result.errors.append(f"{claim_id}: missing settlement {settlement_id}")
        if kingdom_id not in world.kingdoms:
            result.errors.append(f"{claim_id}: missing kingdom {kingdom_id}")
        occupying = claim.get("occupying_kingdom_id")
        if occupying and occupying not in world.kingdoms:
            result.errors.append(f"{claim_id}: unknown occupying kingdom {occupying}")
        strength = float(claim.get("strength", 0.0))
        if strength < 0 or not _finite(strength):
            result.errors.append(f"{claim_id}: invalid strength")

    if not world.alive_npcs():
        result.warnings.append("persistent NPC population reached zero")

    return result


def historical_map_snapshot(world: WorldState) -> dict[str, Any]:
    return {
        "date": world.date.model_dump(mode="json"),
        "population": world.total_population,
        "settlements": [
            {
                "id": settlement.id,
                "name": settlement.name,
                "type": settlement.type.value,
                "kingdom_id": settlement.kingdom_id,
                "region_id": settlement.region_id,
                "position": settlement.position.model_dump(mode="json"),
                "population": settlement.population,
                "frontier": settlement.frontier,
                "occupied_by_kingdom_id": settlement.occupied_by_kingdom_id,
                "abandoned_year": settlement.abandoned_year,
            }
            for settlement in sorted(world.settlements.values(), key=lambda item: item.id)
        ],
        "kingdoms": [
            {
                "id": kingdom.id,
                "name": kingdom.name,
                "capital_settlement_id": kingdom.capital_settlement_id,
                "overlord_kingdom_id": kingdom.overlord_kingdom_id,
                "settlement_ids": sorted(kingdom.settlement_ids),
                "claim_ids": sorted(kingdom.claims),
            }
            for kingdom in sorted(world.kingdoms.values(), key=lambda item: item.id)
        ],
        "claims": [
            dict(claim)
            for _, claim in sorted(world.territory_claims.items())
        ],
    }


def annual_metrics(world: WorldState, elapsed_seconds: float, warnings: list[str]) -> dict[str, Any]:
    active_camps = [camp for camp in world.refugee_camps.values() if camp.status != CampStatus.CLOSED]
    active_claims = [claim for claim in world.territory_claims.values() if claim.get("status") != "abandoned"]
    active_frontiers = [
        settlement for settlement in world.settlements.values()
        if settlement.frontier and settlement.population > 0 and settlement.type != SettlementType.RUIN
    ]
    ruins = [settlement for settlement in world.settlements.values() if settlement.type == SettlementType.RUIN]
    return {
        "world_year": world.date.year,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "population": world.total_population,
        "settlements": len(world.settlements),
        "active_settlements": sum(1 for s in world.settlements.values() if s.population > 0 and s.type != SettlementType.RUIN),
        "kingdoms": len(world.kingdoms),
        "vassal_kingdoms": sum(1 for k in world.kingdoms.values() if k.overlord_kingdom_id),
        "living_persistent_npcs": len(world.alive_npcs()),
        "active_wars": len(world.active_wars()),
        "active_fronts": sum(len(war.front_settlement_ids) for war in world.active_wars()),
        "active_sieges": sum(len(war.siege_progress) for war in world.active_wars()),
        "occupied_settlements": sum(len(war.occupation_by_settlement) for war in world.active_wars()),
        "active_refugee_camps": len(active_camps),
        "refugee_camp_population": sum(camp.people for camp in active_camps),
        "active_claims": len(active_claims),
        "active_frontier_settlements": len(active_frontiers),
        "ruins": len(ruins),
        "warnings": warnings,
    }


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(percentile * len(ordered)) - 1))
    return ordered[index]


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "# LivingWorld Long-Horizon Benchmark",
        "",
        f"- **Seed:** `{report['seed']}`",
        f"- **Years simulated:** {summary['years_completed']}",
        f"- **Overall:** {'PASS' if summary['passed'] else 'FAIL'}",
        f"- **Total wall time:** {summary['total_elapsed_seconds']:.2f} seconds",
        f"- **Average seconds/year:** {summary['average_seconds_per_year']:.3f}",
        f"- **Median seconds/year:** {summary['median_seconds_per_year']:.3f}",
        f"- **P95 seconds/year:** {summary['p95_seconds_per_year']:.3f}",
        f"- **Simulated hours/second:** {summary['simulated_hours_per_second']:.2f}",
        f"- **Equivalent unthrottled speed:** {summary['equivalent_speed_multiplier']:.0f}x",
        f"- **Projected 200-year wall time:** {summary['projected_200_year_seconds']:.2f} seconds",
        f"- **Initial population:** {summary['initial_population']:,}",
        f"- **Final population:** {summary['final_population']:,}",
        "",
        "## Structural validation",
        "",
        f"- Invariant failures: **{len(report['invariant_errors'])}**",
        f"- Stability warnings: **{len(report['stability_warnings'])}**",
        "",
        "## Annual timing",
        "",
        "| Year | sec/year | Population | Settlements | Wars | Fronts | Sieges | Occupied | Warnings |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["annual"]:
        lines.append(
            f"| {item['world_year']} | {item['elapsed_seconds']:.3f} | {item['population']:,} | "
            f"{item['active_settlements']} | {item['active_wars']} | {item['active_fronts']} | "
            f"{item['active_sieges']} | {item['occupied_settlements']} | {len(item['warnings'])} |"
        )
    if report["invariant_errors"]:
        lines.extend(["", "## Invariant failures", ""])
        lines.extend(f"- {error}" for error in report["invariant_errors"])
    if report["stability_warnings"]:
        lines.extend(["", "## Stability warnings", ""])
        lines.extend(f"- {warning}" for warning in report["stability_warnings"][-100:])
    lines.extend(["", "## Event counts", ""])
    for event_type, count in sorted(report["event_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{event_type}`: {count}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_long_horizon(
    *,
    years: int,
    seed: str,
    name: str,
    output_dir: Path,
    snapshot_every: int = 10,
    fail_fast: bool = True,
) -> dict[str, Any]:
    if years <= 0:
        raise ValueError("years must be greater than zero")
    if snapshot_every <= 0:
        raise ValueError("snapshot_every must be greater than zero")

    output_dir.mkdir(parents=True, exist_ok=True)
    maps_dir = output_dir / "maps"
    maps_dir.mkdir(parents=True, exist_ok=True)

    collector = EventCollector()
    world = generate_continent_world(seed, name)
    engine = FinalWorldEngine(world, event_sink=collector)
    initial_population = world.total_population
    initial_year = world.date.year

    initial_check = validate_world(world, initial_population)
    if initial_check.errors:
        raise RuntimeError("initial world failed invariants: " + "; ".join(initial_check.errors[:10]))

    annual: list[dict[str, Any]] = []
    invariant_errors: list[str] = []
    stability_warnings: list[str] = []
    year_durations: list[float] = []
    started = time.perf_counter()

    (maps_dir / f"year_{world.date.year:04d}.json").write_text(
        json.dumps(historical_map_snapshot(world), indent=2), encoding="utf-8"
    )

    for index in range(1, years + 1):
        year_started = time.perf_counter()
        engine.advance_years(1, ignore_pause=True)
        elapsed = time.perf_counter() - year_started
        year_durations.append(elapsed)

        check = validate_world(world, initial_population)
        if check.errors:
            invariant_errors.extend(f"Y{world.date.year}: {error}" for error in check.errors)
        if check.warnings:
            stability_warnings.extend(f"Y{world.date.year}: {warning}" for warning in check.warnings)

        metrics = annual_metrics(world, elapsed, check.warnings)
        annual.append(metrics)

        average = statistics.fmean(year_durations)
        remaining = max(0, years - index)
        eta = average * remaining
        print(
            f"Year {world.date.year} ({index}/{years}) | {elapsed:.3f}s | "
            f"pop {world.total_population:,} | wars {len(world.active_wars())} | "
            f"ETA {eta:.1f}s",
            flush=True,
        )

        if index % snapshot_every == 0 or index == years:
            (maps_dir / f"year_{world.date.year:04d}.json").write_text(
                json.dumps(historical_map_snapshot(world), indent=2), encoding="utf-8"
            )
            (output_dir / "checkpoint_world.json").write_text(
                world.model_dump_json(), encoding="utf-8"
            )

        if check.errors and fail_fast:
            break

    total_elapsed = time.perf_counter() - started
    years_completed = len(annual)
    simulated_hours = years_completed * 360 * 24
    sim_hours_per_second = simulated_hours / max(total_elapsed, 1e-9)
    equivalent_speed = sim_hours_per_second * 5.0  # 1x live clock = 1 sim hour / 5 real seconds.
    average_seconds = statistics.fmean(year_durations) if year_durations else 0.0
    median_seconds = statistics.median(year_durations) if year_durations else 0.0
    p95_seconds = _percentile(year_durations, 0.95)

    report = {
        "seed": seed,
        "world_name": name,
        "initial_world_year": initial_year,
        "annual": annual,
        "event_counts": dict(collector.counts),
        "major_events": collector.major_events,
        "invariant_errors": invariant_errors,
        "stability_warnings": stability_warnings,
        "summary": {
            "passed": not invariant_errors and years_completed == years,
            "years_requested": years,
            "years_completed": years_completed,
            "total_elapsed_seconds": total_elapsed,
            "average_seconds_per_year": average_seconds,
            "median_seconds_per_year": median_seconds,
            "p95_seconds_per_year": p95_seconds,
            "simulated_hours_per_second": sim_hours_per_second,
            "equivalent_speed_multiplier": equivalent_speed,
            "projected_200_year_seconds": average_seconds * 200,
            "initial_population": initial_population,
            "final_population": world.total_population,
            "final_world_year": world.date.year,
            "final_settlements": len(world.settlements),
            "final_active_settlements": sum(1 for s in world.settlements.values() if s.population > 0 and s.type != SettlementType.RUIN),
            "final_living_persistent_npcs": len(world.alive_npcs()),
            "final_active_wars": len(world.active_wars()),
        },
    }

    (output_dir / "benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown_report(output_dir / "BENCHMARK.md", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run LivingWorld without wall-clock throttling for long-horizon validation.")
    parser.add_argument("--years", type=int, default=1, help="Number of 360-day world years to simulate.")
    parser.add_argument("--seed", default="long-horizon-benchmark", help="Deterministic continent seed.")
    parser.add_argument("--name", default="Eldara Benchmark", help="Generated world name.")
    parser.add_argument("--output", default="validation/long-horizon", help="Output directory.")
    parser.add_argument("--snapshot-every", type=int, default=10, help="Write compact historical map every N years.")
    parser.add_argument("--no-fail-fast", action="store_true", help="Continue after structural invariant failures.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_long_horizon(
        years=args.years,
        seed=args.seed,
        name=args.name,
        output_dir=Path(args.output),
        snapshot_every=args.snapshot_every,
        fail_fast=not args.no_fail_fast,
    )
    summary = report["summary"]
    print("")
    print(f"OVERALL: {'PASS' if summary['passed'] else 'FAIL'}")
    print(f"Average seconds/year: {summary['average_seconds_per_year']:.3f}")
    print(f"Equivalent unthrottled speed: {summary['equivalent_speed_multiplier']:.0f}x")
    print(f"Projected 200-year wall time: {summary['projected_200_year_seconds']:.1f}s")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
