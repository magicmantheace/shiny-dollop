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
from .domain import HistoricalEvent, LawPolicy, WorldState
from .politics_benchmark import validate_politics
from .world_engine import FinalWorldEngine


INSTITUTION_EVENT_TYPES = {
    "LAW_CHANGED",
    "POLITICAL_CRISIS",
    "POLITICAL_CRISIS_EASED",
    "REGIME_OVERTHROWN",
    "REGIONAL_SECESSION",
    "CIVIL_WAR_STARTED",
    "FACTION_REBELLION",
    "KINGDOM_FOUNDED",
    "KINGDOM_DESTROYED",
}

POLICY_FIELDS = tuple(key for key in LawPolicy.model_fields if key != "revision")


@dataclass
class InstitutionCollector:
    counts: Counter[str] = field(default_factory=Counter)
    events: list[dict[str, Any]] = field(default_factory=list)
    max_events: int = 3000

    def __call__(self, event: HistoricalEvent) -> None:
        self.counts[event.type] += 1
        if event.type in INSTITUTION_EVENT_TYPES and len(self.events) < self.max_events:
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


def _finite_unit(value: float) -> bool:
    return math.isfinite(value) and 0.0 <= value <= 1.0


def validate_institutions(world: WorldState) -> list[str]:
    errors: list[str] = []
    for kingdom in world.kingdoms.values():
        if not kingdom.institutions_initialized:
            errors.append(f"{kingdom.id}: institutions not initialized")
            continue

        expected_settlements = {
            sid for sid in kingdom.settlement_ids if sid in world.settlements
        }
        actual_compliance = set(kingdom.policy_compliance)
        if actual_compliance != expected_settlements:
            missing = sorted(expected_settlements - actual_compliance)
            extra = sorted(actual_compliance - expected_settlements)
            errors.append(
                f"{kingdom.id}: compliance settlement mismatch missing={missing[:4]} extra={extra[:4]}"
            )

        for settlement_id, value in kingdom.policy_compliance.items():
            if not _finite_unit(value):
                errors.append(f"{kingdom.id}: compliance {settlement_id} out of range: {value}")

        law_values = kingdom.laws.model_dump()
        if not math.isfinite(kingdom.laws.tax_rate) or not 0.04 <= kingdom.laws.tax_rate <= 0.24:
            errors.append(f"{kingdom.id}: tax law out of range: {kingdom.laws.tax_rate}")
        if not math.isfinite(kingdom.laws.trade_tariff) or not 0.0 <= kingdom.laws.trade_tariff <= 0.20:
            errors.append(f"{kingdom.id}: tariff law out of range: {kingdom.laws.trade_tariff}")
        for key in POLICY_FIELDS:
            if key in {"tax_rate", "trade_tariff"}:
                continue
            value = float(law_values[key])
            if not _finite_unit(value):
                errors.append(f"{kingdom.id}: law {key} out of range: {value}")
        if kingdom.laws.revision < 0:
            errors.append(f"{kingdom.id}: negative law revision")
        if abs(kingdom.tax_rate - kingdom.laws.tax_rate) > 1e-8:
            errors.append(
                f"{kingdom.id}: legacy tax_rate {kingdom.tax_rate:.6f} != law tax_rate {kingdom.laws.tax_rate:.6f}"
            )

        institution_values = kingdom.institutions.model_dump()
        for key, value in institution_values.items():
            if not _finite_unit(float(value)):
                errors.append(f"{kingdom.id}: institution {key} out of range: {value}")

        expected_effective = set(POLICY_FIELDS)
        actual_effective = set(kingdom.effective_policies)
        if actual_effective != expected_effective:
            errors.append(
                f"{kingdom.id}: effective policy keys mismatch missing={sorted(expected_effective - actual_effective)} "
                f"extra={sorted(actual_effective - expected_effective)}"
            )
        for key, value in kingdom.effective_policies.items():
            if not math.isfinite(value):
                errors.append(f"{kingdom.id}: effective policy {key} is not finite")
            elif key == "tax_rate" and not 0.0 <= value <= 0.24:
                errors.append(f"{kingdom.id}: effective tax rate out of range: {value}")
            elif key != "tax_rate" and not 0.0 <= value <= 1.0:
                errors.append(f"{kingdom.id}: effective policy {key} out of range: {value}")

        for label, value in {
            "institutional revenue": kingdom.institutional_revenue_last_month,
            "institutional spending": kingdom.institutional_spending_last_month,
            "treasury": kingdom.treasury,
        }.items():
            if not math.isfinite(value) or value < 0.0:
                errors.append(f"{kingdom.id}: invalid {label}: {value}")

    return errors


def institution_metrics(world: WorldState, elapsed_seconds: float, collector: InstitutionCollector) -> dict[str, Any]:
    kingdoms = list(world.kingdoms.values())
    settlements = list(world.settlements.values())
    factions = [
        faction
        for faction in world.political_factions.values()
        if faction.active and faction.kingdom_id in world.kingdoms
    ]
    compliance = [
        value
        for kingdom in kingdoms
        for value in kingdom.policy_compliance.values()
    ]
    population = max(1, world.total_population)
    total_revenue = sum(k.institutional_revenue_last_month for k in kingdoms)
    total_spending = sum(k.institutional_spending_last_month for k in kingdoms)
    policy_conflict_factions = sum(
        1
        for faction in factions
        if any(g.startswith("Policy conflict: ") for g in faction.grievances)
    )
    return {
        "world_year": world.date.year,
        "elapsed_seconds": round(elapsed_seconds, 6),
        "population": world.total_population,
        "kingdoms": len(kingdoms),
        "settlements": len(settlements),
        "active_factions": len(factions),
        "average_administrative_reach": statistics.fmean(k.institutions.administrative_reach for k in kingdoms) if kingdoms else 0.0,
        "average_tax_efficiency": statistics.fmean(k.institutions.tax_efficiency for k in kingdoms) if kingdoms else 0.0,
        "average_corruption": statistics.fmean(k.institutions.corruption for k in kingdoms) if kingdoms else 0.0,
        "max_corruption": max((k.institutions.corruption for k in kingdoms), default=0.0),
        "average_compliance": statistics.fmean(compliance) if compliance else 0.0,
        "min_compliance": min(compliance, default=0.0),
        "max_compliance": max(compliance, default=0.0),
        "average_tax_rate": statistics.fmean(k.laws.tax_rate for k in kingdoms) if kingdoms else 0.0,
        "average_tariff": statistics.fmean(k.laws.trade_tariff for k in kingdoms) if kingdoms else 0.0,
        "average_law_revision": statistics.fmean(k.laws.revision for k in kingdoms) if kingdoms else 0.0,
        "law_change_events": collector.counts.get("LAW_CHANGED", 0),
        "total_monthly_revenue": total_revenue,
        "total_monthly_spending": total_spending,
        "spending_to_revenue": total_spending / max(0.000001, total_revenue),
        "total_treasury": sum(k.treasury for k in kingdoms),
        "treasury_per_capita": sum(k.treasury for k in kingdoms) / population,
        "depleted_treasuries": sum(1 for k in kingdoms if k.treasury <= 1.0),
        "average_crime": statistics.fmean(s.crime for s in settlements) if settlements else 0.0,
        "average_food_security": statistics.fmean(s.food_security for s in settlements) if settlements else 0.0,
        "average_military_readiness": statistics.fmean(k.military_readiness for k in kingdoms) if kingdoms else 0.0,
        "average_faction_loyalty": statistics.fmean(f.loyalty for f in factions) if factions else 0.0,
        "policy_conflict_factions": policy_conflict_factions,
        "policy_conflict_fraction": policy_conflict_factions / max(1, len(factions)),
        "active_wars": len(world.active_wars()),
    }


def balance_warnings(annual: list[dict[str, Any]]) -> list[str]:
    if not annual:
        return []
    warnings: list[str] = []
    final = annual[-1]
    if min(item["average_compliance"] for item in annual) < 0.30:
        warnings.append("Average policy compliance fell below 0.30 during the run.")
    if max(item["average_compliance"] for item in annual) > 0.92:
        warnings.append("Average policy compliance exceeded 0.92; regional implementation may be too uniform.")
    if max(item["average_corruption"] for item in annual) > 0.55:
        warnings.append("Average institutional corruption exceeded 0.55.")
    if final["depleted_treasuries"] > final["kingdoms"] / 2:
        warnings.append("More than half of final kingdoms have effectively depleted treasuries.")
    if final["policy_conflict_fraction"] > 0.75:
        warnings.append("More than 75% of active factions end with a policy-conflict grievance.")
    if final["average_faction_loyalty"] < 0.35:
        warnings.append("Final average faction loyalty is below 0.35.")
    if len(annual) >= 10:
        recent = annual[-10:]
        if statistics.fmean(item["spending_to_revenue"] for item in recent) > 2.5:
            warnings.append("Policy spending averaged more than 2.5x monthly institutional revenue over the final decade.")
    final_change_rate = final["law_change_events"] / max(1, final["kingdoms"] * len(annual))
    if final_change_rate > 0.90:
        warnings.append("Law changes occurred at nearly one revision per kingdom per year; policy review may be too restless.")
    return warnings


def write_markdown_report(path: Path, report: dict[str, Any]) -> None:
    summary = report["summary"]
    lines = [
        "# LivingWorld v0.3 Slice 2 Institutional Calibration",
        "",
        f"- **Seed:** `{report['seed']}`",
        f"- **Years simulated:** {summary['years_completed']}",
        f"- **Overall:** {'PASS' if summary['passed'] else 'FAIL'}",
        f"- **Total wall time:** {summary['total_elapsed_seconds']:.2f} seconds",
        f"- **Average seconds/year:** {summary['average_seconds_per_year']:.3f}",
        f"- **Initial population:** {summary['initial_population']:,}",
        f"- **Final population:** {summary['final_population']:,}",
        f"- **Final kingdoms:** {summary['final_kingdoms']}",
        f"- **Final average compliance:** {summary['final_average_compliance']:.3f}",
        f"- **Final average corruption:** {summary['final_average_corruption']:.3f}",
        f"- **Final treasury/capita:** {summary['final_treasury_per_capita']:.3f}",
        f"- **Final policy-conflict factions:** {summary['final_policy_conflict_factions']}",
        "",
        "## Integrity",
        "",
        f"- Base-world invariant failures: **{len(report['base_invariant_errors'])}**",
        f"- Political invariant failures: **{len(report['political_invariant_errors'])}**",
        f"- Institutional invariant failures: **{len(report['institutional_invariant_errors'])}**",
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
            "## Annual institutional state",
            "",
            "| Year | sec | Pop | K | S | Admin | Tax eff | Corr | Compliance | Min comp | Tax | Rev/mo | Spend/mo | Spend/Rev | Treasury/cap | Crime | Food | Readiness | Loyalty | Policy conflicts | Law changes |",
            "|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for item in report["annual"]:
        lines.append(
            f"| {item['world_year']} | {item['elapsed_seconds']:.3f} | {item['population']:,} | {item['kingdoms']} | {item['settlements']} | "
            f"{item['average_administrative_reach']:.3f} | {item['average_tax_efficiency']:.3f} | {item['average_corruption']:.3f} | "
            f"{item['average_compliance']:.3f} | {item['min_compliance']:.3f} | {item['average_tax_rate']:.3f} | "
            f"{item['total_monthly_revenue']:.2f} | {item['total_monthly_spending']:.2f} | {item['spending_to_revenue']:.2f} | "
            f"{item['treasury_per_capita']:.3f} | {item['average_crime']:.3f} | {item['average_food_security']:.3f} | "
            f"{item['average_military_readiness']:.3f} | {item['average_faction_loyalty']:.3f} | {item['policy_conflict_factions']} | {item['law_change_events']} |"
        )

    for heading, errors in (
        ("Base-world invariant failures", report["base_invariant_errors"]),
        ("Political invariant failures", report["political_invariant_errors"]),
        ("Institutional invariant failures", report["institutional_invariant_errors"]),
    ):
        if errors:
            lines.extend(["", f"## {heading}", ""])
            lines.extend(f"- {error}" for error in errors)

    lines.extend(["", "## Event counts", ""])
    for event_type in sorted(INSTITUTION_EVENT_TYPES):
        lines.append(f"- `{event_type}`: {report['event_counts'].get(event_type, 0)}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_institution_calibration(
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
    collector = InstitutionCollector()
    world = generate_continent_world(seed, name)
    engine = FinalWorldEngine(world, event_sink=collector)
    initial_population = world.total_population

    base_initial = validate_world(world, initial_population)
    politics_initial = validate_politics(world)
    institutions_initial = validate_institutions(world)
    if base_initial.errors or politics_initial or institutions_initial:
        raise RuntimeError(
            "initial world failed calibration invariants: "
            + "; ".join((base_initial.errors + politics_initial + institutions_initial)[:10])
        )

    annual: list[dict[str, Any]] = []
    base_errors: list[str] = []
    political_errors: list[str] = []
    institution_errors: list[str] = []
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
        base_errors.extend(f"Y{world.date.year}: {error}" for error in base_check.errors)
        political_errors.extend(f"Y{world.date.year}: {error}" for error in politics_check)
        institution_errors.extend(f"Y{world.date.year}: {error}" for error in institutions_check)
        metrics = institution_metrics(world, elapsed, collector)
        annual.append(metrics)

        print(
            f"Year {world.date.year} ({index}/{years}) | {elapsed:.3f}s | "
            f"kingdoms {metrics['kingdoms']} | compliance {metrics['average_compliance']:.3f} | "
            f"corruption {metrics['average_corruption']:.3f} | treasury/cap {metrics['treasury_per_capita']:.3f} | "
            f"policy conflicts {metrics['policy_conflict_factions']}",
            flush=True,
        )
        if (base_check.errors or politics_check or institutions_check) and fail_fast:
            break

    total_elapsed = time.perf_counter() - started
    final = annual[-1] if annual else institution_metrics(world, 0.0, collector)
    warnings = balance_warnings(annual)
    report = {
        "seed": seed,
        "world_name": name,
        "annual": annual,
        "event_counts": dict(collector.counts),
        "institution_events": collector.events,
        "base_invariant_errors": base_errors,
        "political_invariant_errors": political_errors,
        "institutional_invariant_errors": institution_errors,
        "balance_warnings": warnings,
        "summary": {
            "passed": not base_errors and not political_errors and not institution_errors and len(annual) == years,
            "years_requested": years,
            "years_completed": len(annual),
            "total_elapsed_seconds": total_elapsed,
            "average_seconds_per_year": statistics.fmean(durations) if durations else 0.0,
            "initial_population": initial_population,
            "final_population": world.total_population,
            "final_kingdoms": len(world.kingdoms),
            "final_average_compliance": final["average_compliance"],
            "final_average_corruption": final["average_corruption"],
            "final_average_administrative_reach": final["average_administrative_reach"],
            "final_average_tax_efficiency": final["average_tax_efficiency"],
            "final_treasury_per_capita": final["treasury_per_capita"],
            "final_depleted_treasuries": final["depleted_treasuries"],
            "final_average_crime": final["average_crime"],
            "final_average_food_security": final["average_food_security"],
            "final_average_military_readiness": final["average_military_readiness"],
            "final_average_faction_loyalty": final["average_faction_loyalty"],
            "final_policy_conflict_factions": final["policy_conflict_factions"],
            "law_change_events": final["law_change_events"],
        },
    }

    (output_dir / "institution-calibration.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    write_markdown_report(output_dir / "INSTITUTION_CALIBRATION.md", report)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a LivingWorld Slice 2 institutional calibration simulation.")
    parser.add_argument("--years", type=int, default=100)
    parser.add_argument("--seed", default="institutions-calibration-v0.3")
    parser.add_argument("--name", default="Eldara Institutional Calibration")
    parser.add_argument("--output", default="validation/institution-calibration")
    parser.add_argument("--no-fail-fast", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_institution_calibration(
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
    print(f"Average compliance: {summary['final_average_compliance']:.3f}")
    print(f"Average corruption: {summary['final_average_corruption']:.3f}")
    print(f"Treasury/capita: {summary['final_treasury_per_capita']:.3f}")
    print(f"Balance warnings: {len(report['balance_warnings'])}")
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
