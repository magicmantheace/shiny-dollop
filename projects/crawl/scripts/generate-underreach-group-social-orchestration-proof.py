from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore, canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import (
    PROTOCOL,
    GroupSocialOrchestrationService,
    build_group_social_orchestration_snapshot,
)
from livingworld.underreach_parties_alliances_leadership import (
    PartiesAlliancesLeadershipService,
    deterministic_leader,
)
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import SocialStateService


PROOF_PROTOCOL = "underreach.group-social-orchestration-proof.v1"


def _stack(seed: str, count: int, strata: int):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(count)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=strata)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(persistence)
    memory.initialize(descent)
    social = SocialIntentExecutionService(persistence)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(persistence)
    parties.initialize(descent)
    conflict = RivalryBetrayalSocialConflictService(persistence)
    conflict.initialize(descent)
    orchestration = GroupSocialOrchestrationService(persistence, brain=brain)
    orchestration.initialize(descent)
    state = SocialStateService(persistence)
    return persistence, brain, memory, social, parties, conflict, orchestration, state, descent, ids


def _accepted_offer(social: SocialIntentExecutionService, descent, source: str, target: str) -> str:
    offered = social.execute(descent, social.propose(descent, source, "recruit", target_descender_id=target))
    if not offered.executed or offered.resolved_offer_id is None:
        raise RuntimeError("30C.6 proof could not create recruitment offer")
    accepted = social.execute(
        descent,
        social.propose(
            descent,
            target,
            "accept_recruitment",
            target_descender_id=source,
            recruitment_offer_id=offered.resolved_offer_id,
        ),
    )
    if not accepted.executed:
        raise RuntimeError("30C.6 proof could not accept recruitment offer")
    return offered.resolved_offer_id


def _form_wrong_leader_party(social, parties, descent, left: str, right: str) -> tuple[str, str]:
    expected = deterministic_leader(descent, [left, right])
    source = right if expected == left else left
    target = expected
    result = parties.form_from_accepted_recruitment(descent, _accepted_offer(social, descent, source, target))
    if descent.parties[result.party_id].leader_npc_id != source:
        raise RuntimeError("30C.6 proof failed to establish pre-orchestration leadership mismatch")
    return result.party_id, expected


def _seed_positive(state: SocialStateService, descent, left: str, right: str) -> None:
    for source, target in ((left, right), (right, left)):
        for dimension, delta in (
            ("trust", 0.82),
            ("respect", 0.68),
            ("affection", 0.36),
            ("gratitude", 0.34),
            ("familiarity", 0.62),
        ):
            state.adjust_dimension(
                descent,
                source,
                target,
                dimension,
                delta,
                reason_code="30c6.proof_cooperation_basis",
            )


def _seed_negative(state: SocialStateService, memory: SocialMemoryEvolutionService, descent, source: str, target: str) -> list[str]:
    # Move any previously positive trust/respect all the way into a strong
    # grievance while remaining inside the accepted 30C.1 delta bound.
    relation = state.get(descent, source, target)
    desired = {
        "trust": -0.95,
        "respect": -0.75,
        "resentment": 0.92,
        "rivalry": 0.90,
        "familiarity": 0.82,
    }
    for dimension, target_value in desired.items():
        current = float(getattr(relation, dimension))
        delta = round(target_value - current, 6)
        if delta:
            state.adjust_dimension(
                descent,
                source,
                target,
                dimension,
                delta,
                reason_code="30c6.proof_conflict_basis",
            )
            relation = state.get(descent, source, target)

    source_event_ids: list[str] = []
    for event_type in ("PROMISE_VIOLATED", "LOOT_STOLEN"):
        event = memory.lifecycle.record_event(
            descent,
            event_type,
            f"30C.6 proof canonical grievance {event_type}.",
            actor_ids=[target, source],
            location_id=descent.participants[source].current_location_id,
            data={"state_changes": {"30c6_proof_grievance": event_type}},
        )
        memory.lifecycle.save(descent)
        processed = memory.process_event(descent, event)
        if not processed.processed:
            raise RuntimeError("30C.6 proof grievance was not processed by accepted 30C.2")
        source_event_ids.append(event.id)
    return source_event_ids


def _run_seed(seed: str, count: int, strata: int, gameplay_steps: int, checkpoint_root: Path, index: int) -> dict:
    if count < 10:
        raise ValueError("30C.6 proof requires at least ten Descenders")
    persistence, brain, memory, social, parties, _, orchestration, state, descent, ids = _stack(seed, count, strata)

    # Two deliberately mis-led parties guarantee that 30C.6 must perform real
    # deterministic leadership transitions rather than merely observe leaders.
    left_party, left_expected_leader = _form_wrong_leader_party(social, parties, descent, ids[2], ids[3])
    right_party, right_expected_leader = _form_wrong_leader_party(social, parties, descent, ids[4], ids[5])

    # Positive canonical history between the future leaders guarantees an
    # alliance opportunity. A separate positive pair remains unpartied so the
    # orchestrator itself must perform recruitment/materialization.
    _seed_positive(state, descent, left_expected_leader, right_expected_leader)
    _seed_positive(state, descent, ids[0], ids[1])

    first = orchestration.step(descent)
    if descent.participants[ids[0]].current_party_id is None or descent.participants[ids[0]].current_party_id != descent.participants[ids[1]].current_party_id:
        raise RuntimeError("30C.6 proof failed unattended party formation")
    if descent.parties[left_party].leader_npc_id != left_expected_leader or descent.parties[right_party].leader_npc_id != right_expected_leader:
        raise RuntimeError("30C.6 proof failed unattended deterministic leadership transition")

    party_metadata = descent.modifiers["_parties_alliances_leadership"]
    active_alliances = [value for value in party_metadata["alliances"].values() if value["status"] == "active"]
    matching = [value for value in active_alliances if sorted(value["party_ids"]) == sorted([left_party, right_party])]
    if not matching:
        raise RuntimeError("30C.6 proof failed unattended alliance formation")
    alliance_id = matching[0]["alliance_id"]

    # Create two real social arcs before the next autonomous social pass:
    # one party-member grievance that should dissolve a two-member party, and
    # one leader-to-leader grievance that should make alliance breaking eligible.
    auto_party_id = descent.participants[ids[0]].current_party_id
    auto_party = descent.parties[auto_party_id]
    auto_victim = next(npc_id for npc_id in auto_party.member_npc_ids if npc_id != auto_party.leader_npc_id)
    party_grievance_events = _seed_negative(state, memory, descent, auto_victim, auto_party.leader_npc_id)
    alliance_grievance_events = _seed_negative(state, memory, descent, left_expected_leader, right_expected_leader)

    second = orchestration.step(descent)
    if descent.parties[auto_party_id].active:
        raise RuntimeError("30C.6 proof failed unattended party dissolution after canonical grievance")
    if alliance_id in party_metadata["alliances"] and party_metadata["alliances"][alliance_id]["status"] == "active":
        raise RuntimeError("30C.6 proof failed evidence-gated autonomous alliance conflict")

    gameplay_executed = 0
    for _ in range(gameplay_steps):
        brain_metadata = descent.modifiers["_brain_driven_descent"]
        if brain_metadata["run_outcome"] != "running":
            break
        brain.step(descent)
        gameplay_executed += 1
        if descent.modifiers["_brain_driven_descent"]["run_outcome"] != "running":
            break
        orchestration.step(descent)

    snapshot = build_group_social_orchestration_snapshot(descent)
    events = persistence.replay_events(descent.id)
    event_counts = Counter(event.event_type for event in events)

    checkpoint_dir = checkpoint_root / f"seed-{index:02d}"
    store = AlphaCheckpointStore(checkpoint_dir, retention=4)
    written = store.write(
        f"30c6-proof-runtime-{index}",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL, "slice": "30C.6", "seed": seed},
        reason="30c6-proof",
        created_at_unix_ms=3006001 + index,
    )
    loaded = store.load_latest().crawl
    checkpoint_state_equal = loaded.model_dump(mode="json") == descent.model_dump(mode="json")
    checkpoint_snapshot_equal = build_group_social_orchestration_snapshot(loaded) == snapshot
    if not checkpoint_state_equal or not checkpoint_snapshot_equal:
        raise RuntimeError("30C.6 checkpoint restore diverged")

    strategy_counts = Counter()
    for record in descent.modifiers["_group_social_orchestration"]["step_records"]:
        strategy_counts.update(record["strategies"].values())

    metrics = dict(descent.modifiers["_group_social_orchestration"]["metrics"])
    return {
        "seed": seed,
        "descent_id": descent.id,
        "final_tick": descent.current_tick,
        "final_stratum_number": descent.current_floor,
        "social_step_count": descent.modifiers["_group_social_orchestration"]["step_count"],
        "gameplay_steps_executed": gameplay_executed,
        "metrics": metrics,
        "strategy_counts": dict(sorted(strategy_counts.items())),
        "active_party_count": snapshot["active_party_count"],
        "active_alliance_count": snapshot["active_alliance_count"],
        "first_step_decision_count": len(first["decisions"]),
        "second_step_decision_count": len(second["decisions"]),
        "party_grievance_event_ids": party_grievance_events,
        "alliance_grievance_event_ids": alliance_grievance_events,
        "hostile_alliance_break_recorded": alliance_id in descent.modifiers["_rivalry_betrayal_social_conflict"]["hostile_alliance_breaks"],
        "event_type_counts": dict(sorted(event_counts.items())),
        "snapshot_digest": snapshot["digest"],
        "canonical_fingerprint": descent.fingerprint(),
        "checkpoint_digest": written.payload["digest"],
        "checkpoint_event_count": len(events),
        "checkpoint_state_equal": checkpoint_state_equal,
        "checkpoint_snapshot_equal": checkpoint_snapshot_equal,
    }


def generate(output: Path, *, seed_base: str, seed_count: int, count: int, strata: int, gameplay_steps: int) -> dict:
    if seed_count < 3:
        raise ValueError("30C.6 acceptance proof requires at least three deterministic seeds")
    seeds = [f"{seed_base}-{index:02d}" for index in range(seed_count)]
    runs = [
        _run_seed(seed, count, strata, gameplay_steps, output.parent / "checkpoints", index)
        for index, seed in enumerate(seeds)
    ]

    aggregate_metrics = Counter()
    aggregate_strategies = Counter()
    aggregate_events = Counter()
    for run in runs:
        aggregate_metrics.update(run["metrics"])
        aggregate_strategies.update(run["strategy_counts"])
        aggregate_events.update(run["event_type_counts"])

    if aggregate_metrics["party_formations"] < seed_count:
        raise RuntimeError("30C.6 multi-seed proof did not form parties autonomously")
    if aggregate_metrics["party_dissolutions"] < seed_count:
        raise RuntimeError("30C.6 multi-seed proof did not dissolve grievance-damaged parties")
    if aggregate_metrics["leadership_changes"] < seed_count * 2:
        raise RuntimeError("30C.6 multi-seed proof did not perform deterministic leadership shifts")
    if aggregate_metrics["alliance_formations"] < seed_count:
        raise RuntimeError("30C.6 multi-seed proof did not form alliances")
    if aggregate_metrics["hostile_conflicts"] < seed_count * 2:
        raise RuntimeError("30C.6 multi-seed proof did not exercise party and alliance conflict")
    if sum(aggregate_strategies.values()) < seed_count:
        raise RuntimeError("30C.6 multi-seed proof did not record social strategies")
    if any(not run["hostile_alliance_break_recorded"] for run in runs):
        raise RuntimeError("30C.6 multi-seed proof lost hostile alliance-break provenance")
    if any(not run["checkpoint_state_equal"] or not run["checkpoint_snapshot_equal"] for run in runs):
        raise RuntimeError("30C.6 multi-seed checkpoint proof failed")

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "presentation_feedback_allowed": False,
        "dialogue_enabled": False,
        "random_social_actions_allowed": False,
        "seed_base": seed_base,
        "seed_count": seed_count,
        "seeds": seeds,
        "population_count": count,
        "configured_stratum_count": strata,
        "requested_gameplay_steps_per_seed": gameplay_steps,
        "runs": runs,
        "run_digest": payload_digest(runs),
        "total_social_steps": sum(run["social_step_count"] for run in runs),
        "total_gameplay_steps": sum(run["gameplay_steps_executed"] for run in runs),
        "aggregate_metrics": dict(sorted(aggregate_metrics.items())),
        "aggregate_strategy_counts": dict(sorted(aggregate_strategies.items())),
        "aggregate_event_type_counts": dict(sorted(aggregate_events.items())),
        "all_checkpoint_roundtrips_equal": all(run["checkpoint_state_equal"] and run["checkpoint_snapshot_equal"] for run in runs),
        "all_hostile_alliance_breaks_proven": all(run["hostile_alliance_break_recorded"] for run in runs),
        "authority_contract": {
            "social_strategy_is_deterministic": True,
            "orchestrator_composes_existing_mutation_services": True,
            "recruitment_uses_30c3": True,
            "parties_and_alliances_use_30c4": True,
            "betrayal_and_hostile_conflict_use_30c5": True,
            "random_betrayal_allowed": False,
            "brain_gameplay_authority_remains_30b3": True,
            "social_history_survives_checkpoint_replay": True,
            "presentation_can_mutate": False,
            "unreal_can_mutate": False,
            "dialogue_owner_phase": "31",
            "phase_30c_complete": True,
            "next_phase": "31 - Dialogue / Commentary",
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed-base", default="underreach-30c6-group-social-proof")
    parser.add_argument("--seed-count", type=int, default=3)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--strata", type=int, default=3)
    parser.add_argument("--gameplay-steps", type=int, default=4)
    args = parser.parse_args()
    proof = generate(
        Path(args.output),
        seed_base=args.seed_base,
        seed_count=args.seed_count,
        count=args.count,
        strata=args.strata,
        gameplay_steps=args.gameplay_steps,
    )
    metrics = proof["aggregate_metrics"]
    print(
        f"[30C.6] proof digest={proof['digest']} seeds={proof['seed_count']} "
        f"parties={metrics.get('party_formations', 0)} dissolutions={metrics.get('party_dissolutions', 0)} "
        f"leaders={metrics.get('leadership_changes', 0)} conflicts={metrics.get('hostile_conflicts', 0)}"
    )
    print("[30C.6] Deterministic multi-seed group-social orchestration proof PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
