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
from .domain import HistoricalEvent, PoliticalOfficeType, WorldState
from .political_collapse import collapse_diagnostics
from .world_engine import FinalWorldEngine


POLITICAL_EVENT_TYPES = {
    "POLITICAL_ORDER_FORMED",
    "OFFICE_APPOINTED",
    "FACTION_LEADER_CHANGED",
    "RULER_SUCCEEDED",
    "LEADERSHIP_CHANGED",
    "POLITICAL_CRISIS",
    "POLITICAL_CRISIS_EASED",
    "REGIME_OVERTHROWN",
    "GOVERNMENT_REFORMED",
    "REGIONAL_SECESSION",
    "CIVIL_WAR_STARTED",
    "FACTION_REBELLION",
    "REBELLION",
    "KINGDOM_FOUNDED",
    "KINGDOM_DESTROYED",
}


@dataclass
class PoliticalCollector:
    counts: Counter[str] = field(default_factory=Counter)
    events: list[dict[str, Any]] = field(default_factory=list)
    max_events: int = 2_000

    def __call__(self, event: HistoricalEvent) -> None:
        self.counts[event.type] += 1
        if event.type in POLITICAL_EVENT_TYPES and len(self.events) < self.max_events:
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


def validate_politics(world: WorldState) -> list[str]:
    errors: list[str] = []

    for faction in world.political_factions.values():
        if not faction.active:
            continue
        kingdom = world.kingdoms.get(faction.kingdom_id)
        if not kingdom:
            errors.append(f"{faction.id}: active faction references missing kingdom {faction.kingdom_id}")
            continue
        if faction.id not in kingdom.faction_ids:
            errors.append(f"{faction.id}: missing from {kingdom.id} faction list")
        if not math.isfinite(faction.influence) or not 0.0 <= faction.influence <= 1.0:
            errors.append(f"{faction.id}: influence out of range")
        if not math.isfinite(faction.loyalty) or not 0.0 <= faction.loyalty <= 1.0:
            errors.append(f"{faction.id}: loyalty out of range")
        if faction.leader_npc_id:
            leader = world.npcs.get(faction.leader_npc_id)
            if not leader or not leader.alive:
                errors.append(f"{faction.id}: leader missing or dead")
            elif leader.kingdom_id != kingdom.id:
                errors.append(f"{faction.id}: leader belongs to {leader.kingdom_id}, expected {kingdom.id}")
        for npc_id in faction.member_npc_ids:
            member = world.npcs.get(npc_id)
            if not member or not member.alive:
                errors.append(f"{faction.id}: member {npc_id} missing or dead")
            elif member.kingdom_id != kingdom.id:
                errors.append(f"{faction.id}: member {npc_id} belongs to {member.kingdom_id}")
        if faction.regional_base_settlement_id:
            base = world.settlements.get(faction.regional_base_settlement_id)
            if not base:
                errors.append(f"{faction.id}: regional base missing")
            elif base.kingdom_id != kingdom.id:
                errors.append(
                    f"{faction.id}: regional base {base.id} belongs to {base.kingdom_id}, expected {kingdom.id}"
                )

    valid_resolutions = {None, "regime_overthrow", "regional_secession", "civil_war"}
    for kingdom in world.kingdoms.values():
        if not kingdom.politics_initialized:
            errors.append(f"{kingdom.id}: politics not initialized")
        if kingdom.political_crisis_months < 0:
            errors.append(f"{kingdom.id}: political crisis months negative")
        if kingdom.last_political_resolution not in valid_resolutions:
            errors.append(
                f"{kingdom.id}: unknown political resolution {kingdom.last_political_resolution}"
            )
        active_factions = []
        for faction_id in kingdom.faction_ids:
            faction = world.political_factions.get(faction_id)
            if not faction:
                errors.append(f"{kingdom.id}: references missing faction {faction_id}")
                continue
            if faction.kingdom_id != kingdom.id:
                errors.append(f"{kingdom.id}: faction {faction_id} belongs to {faction.kingdom_id}")
            if faction.active:
                active_factions.append(faction)
        if not active_factions:
            errors.append(f"{kingdom.id}: has no active political factions")
        else:
            influence_total = sum(faction.influence for faction in active_factions)
            if abs(influence_total - 1.0) > 0.02:
                errors.append(f"{kingdom.id}: active faction influence totals {influence_total:.4f}, expected about 1.0")

        if not 0.0 <= kingdom.legitimacy <= 1.0:
            errors.append(f"{kingdom.id}: legitimacy out of range")

        ruler = world.npcs.get(kingdom.ruler_npc_id or "")
        if kingdom.ruler_npc_id and (not ruler or not ruler.alive):
            errors.append(f"{kingdom.id}: ruler is missing or dead")
        ruler_office = kingdom.political_offices.get(PoliticalOfficeType.RULER.value)
        if kingdom.ruler_npc_id:
            if not ruler_office:
                errors.append(f"{kingdom.id}: ruler office missing")
            elif ruler_office.holder_npc_id != kingdom.ruler_npc_id:
                errors.append(
                    f"{kingdom.id}: ruler office holder {ruler_office.holder_npc_id} != ruler {kingdom.ruler_npc_id}"
                )

        for office_key, office in kingdom.political_offices.items():
            if office.holder_npc_id is None:
                continue
            holder = world.npcs.get(office.holder_npc_id)
            if not holder or not holder.alive:
                errors.append(f"{kingdom.id}: office {office_key} holder missing or dead")
            elif holder.kingdom_id != kingdom.id:
                errors.append(f"{kingdom.id}: office {office_key} holder belongs to {holder.kingdom_id}")

    return errors


def political_metrics(world: WorldState, elapsed_seconds: float) -> dict[str, Any]:
    factions = [
        faction
        for faction in world.political_factions.values()
        if faction.active and faction.kingdom_id in world.kingdoms
    ]
    kingdoms = list(world.kingdoms.values())
    metrics: dict[str, Any] = {
        "world_year": world.date.year,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "population": world.total_population,
        "kingdoms": len(kingdoms),
        "active_wars": len(world.active_wars()),
        "active_factions": len(factions),
        "average_legitimacy": statistics.fmean(k.legitimacy for k in kingdoms) if kingdoms else 0.0,
        "minimum_legitimacy": min((k.legitimacy for k in kingdoms), default=0.0),
        "low_legitimacy_kingdoms": sum(1 for k in kingdoms if k.legitimacy < 0.35),
        "average_faction_loyalty": statistics.fmean(f.loyalty for f in factions) if factions else 0.0,
        "minimum_faction_loyalty": min((f.loyalty for f in factions), default=0.0),
        "total_grievances": sum(len(f.grievances) for f in factions),
        "filled_offices": sum(
            1
            for kingdom in kingdoms
            for office in kingdom.political_offices.values()
            if office.holder_npc_id
        ),
    }
    metrics.update(collapse_diagnostics(world))
    return metrics


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "# LivingWorld v0.3 Political Calibration",
        "",
        f"- **Seed:** `{report['seed']}`",
        f"- **Years simulated:** {summary['years_completed']}",
        f"- **Overall:** {'PASS' if summary['passed'] else 'FAIL'}",
        f"- **Total wall time:** {summary['total_elapsed_seconds']:.2f} seconds",
        f"- **Average seconds/year:** {summary['average_seconds_per_year']:.3f}",
        f"- **Initial population:** {summary['initial_population']:,}",
        f"- **Final population:** {summary['final_population']:,}",
        f"- **Final kingdoms:** {summary['final_kingdoms']}",
        f"- **Final active factions:** {summary['final_active_factions']}",
        f"- **Final average legitimacy:** {summary['final_average_legitimacy']:.3f}",
        f"- **Final average faction loyalty:** {summary['final_average_faction_loyalty']:.3f}",
        f"- **Final crisis kingdoms:** {summary['final_crisis_kingdoms']}",
        f"- **Final collapse-eligible kingdoms:** {summary['final_collapse_eligible_kingdoms']}",
        "",
        "## Integrity",
        "",
        f"- Base-world invariant failures: **{len(report['base_invariant_errors'])}**",
        f"- Political invariant failures: **{len(report['political_invariant_errors'])}**",
        "",
        "## Annual political state",
        "",
        "| Year | sec/year | Population | Kingdoms | Factions | Avg legitimacy | Min legitimacy | Avg loyalty | Min loyalty | Low-legit | Grievances | Wars | Crisis | Eligible | Max crisis mo | Max pressure |",
        "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for item in report["annual"]:
        lines.append(
            f"| {item['world_year']} | {item['elapsed_seconds']:.3f} | {item['population']:,} | "
            f"{item['kingdoms']} | {item['active_factions']} | {item['average_legitimacy']:.3f} | "
            f"{item['minimum_legitimacy']:.3f} | {item['average_faction_loyalty']:.3f} | "
            f"{item['minimum_faction_loyalty']:.3f} | {item['low_legitimacy_kingdoms']} | "
            f"{item['total_grievances']} | {item['active_wars']} | "
            f"{item['political_crisis_kingdoms']} | {item['collapse_eligible_kingdoms']} | "
            f"{item['max_political_crisis_months']} | {item['max_collapse_pressure']:.3f} |"
        )

    if report["base_invariant_errors"]:
        lines.extend(["", "## Base-world invariant failures", ""])
        lines.extend(f"- {error}" for error in report["base_invariant_errors"])
    if report["political_invariant_errors"]:
        lines.extend(["", "## Political invariant failures", ""])
        lines.extend(f"- {error}" for error in report["political_invariant_errors"])

    lines.extend(["", "## Political event counts", ""])
    for event_type in sorted(POLITICAL_EVENT_TYPES):
        lines.append(f"- `{event_type}`: {report['event_counts'].get(event_type, 0)}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_political_calibration(
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
    collector = PoliticalCollector()
    world = generate_continent_world(seed, name)
    engine = FinalWorldEngine(world, event_sink=collector)
    initial_population = world.total_population

    base_initial = validate_world(world, initial_population)
    politics_initial = validate_politics(world)
    if base_initial.errors or politics_initial:
        raise RuntimeError(
            "initial world failed calibration invariants: "
            + "; ".join((base_initial.errors + politics_initial)[:10])
        )

    annual: list[dict[str, Any]] = []
    base_errors: list[str] = []
    political_errors: list[str] = []
    durations: list[float] = []
    started = time.perf_counter()

    for index in range(1, years + 1):
        year_started = time.perf_counter()
        engine.advance_years(1, ignore_pause=True)
        elapsed = time.perf_counter() - year_started
        durations.append(elapsed)

        base_check = validate_world(world, initial_population)
        political_check = validate_politics(world)
        base_errors.extend(f"Y{world.date.year}: {error}" for error in base_check.errors)
        political_errors.extend(f"Y{world.date.year}: {error}" for error in political_check)
        annual.append(political_metrics(world, elapsed))

        print(
            f"Year {world.date.year} ({index}/{years}) | {elapsed:.3f}s | "
            f"kingdoms {len(world.kingdoms)} | factions {annual[-1]['active_factions']} | "
            f"legitimacy {annual[-1]['average_legitimacy']:.3f} | "
            f"loyalty {annual[-1]['average_faction_loyalty']:.3f} | "
            f"crisis {annual[-1]['political_crisis_kingdoms']} | "
            f"eligible {annual[-1]['collapse_eligible_kingdoms']}",
            flush=True,
        )

        if (base_check.errors or political_check) and fail_fast:
            break

    total_elapsed = time.perf_counter() - started
    final_metrics = political_metrics(world, durations[-1] if durations else 0.0)
    report = {
        "seed": seed,
        "world_name": name,
        "annual": annual,
        "event_counts": dict(collector.counts),
        "political_events": collector.events,
        "base_invariant_errors": base_errors,
        "political_invariant_errors": political_errors,
        "summary": {
            "passed": not base_errors and not political_errors and len(annual) == years,
            "years_requested": years,
            "years_completed": len(annual),
            "total_elapsed_seconds": total_elapsed,
            "average_seconds_per_year": statistics.fmean(durations) if durations else 0.0,
            "initial_population": initial_population,
            "final_population": world.total_population,
            "final_kingdoms": len(world.kingdoms),
            "final_active_factions": final_metrics["active_factions"],
            "final_average_legitimacy": final_metrics["average_legitimacy"],
            "final_average_faction_loyalty": final_metrics["average_faction_loyalty"],
            "final_low_legitimacy_kingdoms": final_metrics["low_legitimacy_kingdoms"],
            "final_grievances": final_metrics["total_grievances"],
            "final_crisis_kingdoms": final_metrics["political_crisis_kingdoms"],
            "final_collapse_eligible_kingdoms": final_metrics["collapse_eligible_kingdoms"],
            "final_max_crisis_months": final_metrics["max_political_crisis_months"],
            "final_max_collapse_pressure": final_metrics["max_collapse_pressure"],
        },
    }

    (output_dir / "politics-calibration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown_report(output_dir / "POLITICS_CALIBRATION.md", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a LivingWorld political calibration simulation.")
    parser.add_argument("--years", type=int, default=25)
    parser.add_argument("--seed", default="politics-calibration-v0.3")
    parser.add_argument("--name", default="Eldara Political Calibration")
    parser.add_argument("--output", default="validation/politics-calibration")
    parser.add_argument("--no-fail-fast", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_political_calibration(
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
    print(f"Average legitimacy: {summary['final_average_legitimacy']:.3f}")
    print(f"Average faction loyalty: {summary['final_average_faction_loyalty']:.3f}")
    print(f"Crisis kingdoms: {summary['final_crisis_kingdoms']}")
    print(f"Collapse eligible: {summary['final_collapse_eligible_kingdoms']}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
