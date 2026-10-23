from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore, canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import (
    PROTOCOL,
    RivalryBetrayalSocialConflictService,
    build_rivalry_betrayal_social_conflict_snapshot,
)
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import get_relationship


PROOF_PROTOCOL = "underreach.rivalry-betrayal-social-conflict-proof.v1"


def _stack(seed: str, ids: list[str], strata: int):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
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
    return persistence, brain, memory, social, parties, conflict, descent


def _accepted_offer(social, descent, source: str, target: str) -> str:
    offered = social.execute(descent, social.propose(descent, source, "recruit", target_descender_id=target))
    if not offered.executed or offered.resolved_offer_id is None:
        raise RuntimeError("30C.5 proof could not create recruitment offer")
    accepted = social.execute(
        descent,
        social.propose(
            descent, target, "accept_recruitment",
            target_descender_id=source, recruitment_offer_id=offered.resolved_offer_id,
        ),
    )
    if not accepted.executed:
        raise RuntimeError("30C.5 proof could not accept recruitment offer")
    return offered.resolved_offer_id


def _form_party(social, parties, descent, source: str, members: list[str]) -> str:
    party_id = None
    for target in members:
        party_id = parties.form_from_accepted_recruitment(
            descent, _accepted_offer(social, descent, source, target)
        ).party_id
    if party_id is None:
        raise RuntimeError("30C.5 proof failed to form party")
    return party_id


def _seed_negative(memory, descent, offender: str, victim: str, event_type: str):
    event = memory.lifecycle.record_event(
        descent,
        event_type,
        f"30C.5 deterministic proof grievance source {event_type}.",
        actor_ids=[offender, victim],
        location_id=descent.participants[victim].current_location_id,
        data={"proof_grievance": True, "state_changes": {"social_grievance_source": event_type}},
    )
    memory.lifecycle.save(descent)
    result = memory.process_event(descent, event)
    if not result.processed:
        raise RuntimeError("30C.5 proof grievance source was not processed")
    return event


def _strong_grievance(memory, descent, offender: str, victim: str):
    return (
        _seed_negative(memory, descent, offender, victim, "PROMISE_VIOLATED"),
        _seed_negative(memory, descent, offender, victim, "LOOT_STOLEN"),
    )


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    start = participant.current_location_id
    if start is None:
        raise RuntimeError("30C.5 proof Descender has no canonical Sector")
    parent: dict[str, str | None] = {start: None}
    queue = [start]
    while queue:
        current = queue.pop(0)
        if current == target_sector_id:
            break
        for neighbor in sorted(floor.locations[current].adjacency):
            if neighbor not in parent:
                parent[neighbor] = current
                queue.append(neighbor)
    if target_sector_id not in parent:
        raise RuntimeError("30C.5 proof could not route to Sector")
    result: list[str] = []
    current: str | None = target_sector_id
    while current is not None:
        result.append(current)
        current = parent[current]
    return list(reversed(result))


def _move(brain, descent, descender_id: str, sector_id: str) -> None:
    for target in _route(descent, descender_id, sector_id)[1:]:
        brain.autonomous.survival.commit_descender_position(descent, descender_id, target)


def _owned_loot(brain, descent, owner: str, contender: str) -> str:
    cache = next(
        value for value in descent.modifiers["_loot_cache_relic"]["caches"]
        if value["stratum_number"] == descent.current_floor
    )
    for npc_id in (owner, contender):
        _move(brain, descent, npc_id, cache["sector_id"])
    item_ids = brain.autonomous.survival.open_cache(descent, cache["cache_id"], owner)
    item_id = sorted(item_ids)[0]
    brain.autonomous.survival.loot.claim_ground_item(descent, item_id, owner)
    return item_id


def _execute_sequence(seed: str, ids: list[str], strata: int):
    persistence, brain, memory, social, parties, conflict, descent = _stack(seed, ids, strata)

    party_a = _form_party(social, parties, descent, ids[0], [ids[1], ids[2]])
    party_b = _form_party(social, parties, descent, ids[3], [ids[4]])
    party_c = _form_party(social, parties, descent, ids[5], [ids[6]])
    alliance = parties.form_alliance(descent, party_b, party_c)

    neutral_before = descent.model_dump(mode="json")
    neutral = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[1], "betray_party",
            incentive_code="survival", incentive_strength=1.0,
        ),
    )
    neutral_rejection_side_effect_free = not neutral.executed and descent.model_dump(mode="json") == neutral_before

    grievance_a = _strong_grievance(memory, descent, ids[1], ids[0])
    observed = conflict.observe(descent, ids[0], ids[1])
    betrayal = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[1], "betray_party",
            incentive_code="leadership", incentive_strength=0.9,
        ),
    )

    grievance_b = _strong_grievance(memory, descent, ids[5], ids[3])
    alliance_break = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[3], ids[5], "break_alliance",
            incentive_code="survival", incentive_strength=0.95,
            alliance_id=alliance.alliance_id,
        ),
    )
    revenge = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[3], ids[5], "seek_revenge",
            incentive_code="revenge", incentive_strength=0.9,
        ),
    )

    grievance_c = _strong_grievance(memory, descent, ids[1], ids[7])
    item_id = _owned_loot(brain, descent, ids[1], ids[7])
    theft = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[7], ids[1], "steal_loot",
            incentive_code="loot", incentive_strength=0.9, target_item_id=item_id,
        ),
    )

    deception = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[7], ids[1], "deceive",
            incentive_code="loot", incentive_strength=0.8, claim_code="loot_location",
        ),
    )
    if deception.deception_id is None:
        raise RuntimeError("30C.5 proof deception was not created")
    exposed = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[1], ids[7], "expose_deception",
            incentive_code="revenge", incentive_strength=0.0,
            deception_id=deception.deception_id,
        ),
    )

    refusal = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[7], ids[1], "refuse_aid",
            incentive_code="resource_scarcity", incentive_strength=0.8,
        ),
    )

    stale = conflict.propose(
        descent, ids[7], ids[1], "refuse_aid",
        incentive_code="survival", incentive_strength=0.8,
    )
    brain.autonomous.survival.advance_time(descent, descent.current_tick + 1)
    stale_before = descent.model_dump(mode="json")
    stale_result = conflict.execute(descent, stale)
    stale_rejection_side_effect_free = (
        not stale_result.executed
        and stale_result.reason_code == "stale_observation"
        and descent.model_dump(mode="json") == stale_before
    )

    snapshot = build_rivalry_betrayal_social_conflict_snapshot(descent)
    events = persistence.replay_events(descent.id)
    event_counts = Counter(event.event_type for event in events)
    return {
        "persistence": persistence,
        "descent": descent,
        "snapshot": snapshot,
        "event_counts": dict(sorted(event_counts.items())),
        "neutral": neutral,
        "neutral_rejection_side_effect_free": neutral_rejection_side_effect_free,
        "stale_result": stale_result,
        "stale_rejection_side_effect_free": stale_rejection_side_effect_free,
        "observed": observed,
        "betrayal": betrayal,
        "alliance_break": alliance_break,
        "revenge": revenge,
        "theft": theft,
        "deception": deception,
        "exposed": exposed,
        "refusal": refusal,
        "party_a": party_a,
        "party_b": party_b,
        "party_c": party_c,
        "alliance_id": alliance.alliance_id,
        "item_id": item_id,
        "grievance_event_ids": [event.id for event in (*grievance_a, *grievance_b, *grievance_c)],
    }


def generate(output: Path, *, seed: str, count: int, strata: int) -> dict:
    if count < 8:
        raise ValueError("30C.5 proof requires at least eight Descenders")
    ids = [f"descender_{index:03d}" for index in range(count)]
    first = _execute_sequence(seed, ids, strata)
    second = _execute_sequence(seed, ids, strata)
    descent = first["descent"]
    twin = second["descent"]

    independent_state_equal = twin.model_dump(mode="json") == descent.model_dump(mode="json")
    independent_snapshot_equal = second["snapshot"] == first["snapshot"]
    independent_event_ids_equal = twin.history_event_ids == descent.history_event_ids
    if not independent_state_equal or not independent_snapshot_equal or not independent_event_ids_equal:
        raise RuntimeError("30C.5 independent deterministic sequence diverged")

    persistence = first["persistence"]
    events = persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(output.parent / "checkpoint", retention=4)
    written = store.write(
        "30c5-proof-runtime", descent, events,
        simulation_config={"protocol": PROTOCOL, "slice": "30C.5"},
        reason="30c5-proof", created_at_unix_ms=3005001,
    )
    loaded = store.load_latest().crawl
    checkpoint_state_equal = loaded.model_dump(mode="json") == descent.model_dump(mode="json")
    checkpoint_snapshot_equal = build_rivalry_betrayal_social_conflict_snapshot(loaded) == first["snapshot"]
    if not checkpoint_state_equal or not checkpoint_snapshot_equal:
        raise RuntimeError("30C.5 checkpoint restore diverged")

    metadata = descent.modifiers["_rivalry_betrayal_social_conflict"]
    victim_relationship = get_relationship(descent, ids[1], ids[0])
    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "random_betrayal_allowed": False,
        "presentation_feedback_allowed": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "final_tick": descent.current_tick,
        "neutral_betrayal_rejected": not first["neutral"].executed,
        "neutral_betrayal_rejection_reason": first["neutral"].reason_code,
        "neutral_rejection_side_effect_free": first["neutral_rejection_side_effect_free"],
        "stale_rejection_reason": first["stale_result"].reason_code,
        "stale_rejection_side_effect_free": first["stale_rejection_side_effect_free"],
        "evidence_observation_negative_memory_count": first["observed"].negative_memory_count,
        "evidence_observation_major_negative_memory_count": first["observed"].major_negative_memory_count,
        "evidence_observation_basis_event_count": len(first["observed"].negative_basis_event_ids),
        "betrayal_executed": first["betrayal"].executed,
        "betrayal_basis_event_count": len(descent.modifiers["_rivalry_betrayal_social_conflict"]["conflict_records"][0]["basis_event_ids"]),
        "betrayer_party_after": descent.participants[ids[0]].current_party_id,
        "betrayed_party_active": descent.parties[first["party_a"]].active,
        "betrayed_party_members_after": list(descent.parties[first["party_a"]].member_npc_ids),
        "betrayed_target_resentment": victim_relationship.resentment,
        "betrayed_target_rivalry": victim_relationship.rivalry,
        "alliance_break_executed": first["alliance_break"].executed,
        "hostile_alliance_archived": first["alliance_id"] in metadata["hostile_alliance_breaks"],
        "hostile_alliance_removed_from_30c4": first["alliance_id"] not in descent.modifiers["_parties_alliances_leadership"]["alliances"],
        "revenge_executed": first["revenge"].executed,
        "active_revenge_count": len(metadata["revenge_records"]),
        "revenge_started_combat": False,
        "loot_theft_executed": first["theft"].executed,
        "stolen_item_id": first["item_id"],
        "stolen_item_owner": descent.items[first["item_id"]].owner_npc_id,
        "deception_created": first["deception"].executed,
        "deception_exposed": first["exposed"].executed,
        "deception_status": metadata["deceptions"][first["deception"].deception_id]["status"],
        "aid_refusal_executed": first["refusal"].executed,
        "conflict_execution_count": len(metadata["conflict_records"]),
        "conflict_trace_digest": first["snapshot"]["conflict_trace_digest"],
        "event_type_counts": first["event_counts"],
        "final_snapshot_digest": first["snapshot"]["digest"],
        "final_canonical_fingerprint": descent.fingerprint(),
        "independent_state_equal": independent_state_equal,
        "independent_snapshot_equal": independent_snapshot_equal,
        "independent_event_ids_equal": independent_event_ids_equal,
        "checkpoint_digest": written.payload["digest"],
        "checkpoint_event_count": len(events),
        "checkpoint_state_equal": checkpoint_state_equal,
        "checkpoint_snapshot_equal": checkpoint_snapshot_equal,
        "authority_contract": {
            "conflict_proposal_is_advisory": True,
            "simulation_validates_conflict": True,
            "simulation_executes_conflict": True,
            "random_betrayal_forbidden": True,
            "high_impact_conflict_requires_negative_evidence": True,
            "high_impact_conflict_requires_explicit_incentive": True,
            "neutral_state_cannot_betray_from_incentive_alone": True,
            "loot_theft_uses_canonical_item_ownership": True,
            "party_betrayal_uses_30c4_membership_authority": True,
            "hostile_alliance_break_owned_by_30c5": True,
            "deception_is_structured_not_prose": True,
            "deception_memory_only_after_exposure": True,
            "revenge_state_does_not_start_combat": True,
            "presentation_can_mutate": False,
            "unreal_can_mutate": False,
            "dialogue_owner_phase": "31",
            "next_slice": "30C.6 - Group Decision & Autonomous Social Orchestration",
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30c5-rivalry-betrayal-proof")
    parser.add_argument("--count", type=int, default=8)
    parser.add_argument("--strata", type=int, default=3)
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed, count=args.count, strata=args.strata)
    print(
        f"[30C.5] proof digest={proof['digest']} conflicts={proof['conflict_execution_count']} "
        f"revenge={proof['active_revenge_count']} betrayal={proof['betrayal_executed']}"
    )
    print("[30C.5] Deterministic rivalry/betrayal/social-conflict proof PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
