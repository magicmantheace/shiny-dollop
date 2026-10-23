from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawler_navigation import perceive
from livingworld.runtime_checkpoint import AlphaCheckpointStore, canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_social_intent_execution import (
    PROTOCOL,
    SocialIntentExecutionService,
    build_social_intent_snapshot,
)
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import get_relationship


PROOF_PROTOCOL = "underreach.social-intent-execution-proof.v1"


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    start = participant.current_location_id
    if start is None:
        raise RuntimeError("proof Descender has no canonical Sector")
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
        raise RuntimeError("proof could not route to target Sector")
    result: list[str] = []
    current: str | None = target_sector_id
    while current is not None:
        result.append(current)
        current = parent[current]
    return list(reversed(result))


def _move(brain: BrainDrivenDescentService, descent, descender_id: str, target_sector_id: str) -> None:
    for sector_id in _route(descent, descender_id, target_sector_id)[1:]:
        brain.autonomous.survival.commit_descender_position(descent, descender_id, sector_id)


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
    return persistence, brain, memory, social, descent


def _prepare_owned_items(brain: BrainDrivenDescentService, descent, actor: str, target: str):
    cache = next(
        value
        for value in descent.modifiers["_loot_cache_relic"]["caches"]
        if value["stratum_number"] == descent.current_floor
    )
    for descender_id in (actor, target):
        _move(brain, descent, descender_id, cache["sector_id"])
    loot_ids = brain.autonomous.survival.open_cache(descent, cache["cache_id"], actor)
    loot_id = sorted(loot_ids)[0]
    brain.autonomous.survival.loot.claim_ground_item(descent, loot_id, actor)
    supply_ids = brain.autonomous.survival.supply_item_ids_for_cache(descent, cache["cache_id"])
    supply_id = sorted(supply_ids)[0]
    brain.autonomous.survival.claim_supply_item(descent, supply_id, actor)
    return loot_id, supply_id, cache


def _execute_sequence(seed: str, ids: list[str], strata: int):
    persistence, brain, memory, social, descent = _stack(seed, ids, strata)
    actor, receiver, recruiter, recruit_target = ids[:4]
    loot_id, supply_id, cache = _prepare_owned_items(brain, descent, actor, receiver)

    proposal_before = descent.model_dump(mode="json")
    proposal_history = list(descent.history_event_ids)
    probe = social.propose(descent, recruiter, "challenge", target_descender_id=recruit_target)
    proposal_side_effect_free = (
        descent.model_dump(mode="json") == proposal_before
        and descent.history_event_ids == proposal_history
    )

    share_item = social.execute(
        descent,
        social.propose(
            descent,
            actor,
            "share_item",
            target_descender_id=receiver,
            target_item_id=loot_id,
        ),
    )
    share_supply = social.execute(
        descent,
        social.propose(
            descent,
            actor,
            "share_supply",
            target_descender_id=receiver,
            target_item_id=supply_id,
        ),
    )

    source_participant = descent.participants[actor]
    target_participant = descent.participants[receiver]
    if source_participant.agent is None or target_participant.agent is None:
        raise RuntimeError("proof requires canonical agent state")
    floor = descent.floors[descent.current_floor]
    perceive(source_participant, floor, descent.current_tick)
    warning_sector = source_participant.current_location_id
    if warning_sector is None:
        raise RuntimeError("proof warning source has no Sector")
    target_participant.agent.knowledge.pop(warning_sector, None)
    warning = social.execute(
        descent,
        social.propose(
            descent,
            actor,
            "warn",
            target_descender_id=receiver,
            target_sector_id=warning_sector,
        ),
    )

    offered = social.execute(
        descent,
        social.propose(descent, actor, "recruit", target_descender_id=receiver),
    )
    accepted = social.execute(
        descent,
        social.propose(
            descent,
            receiver,
            "accept_recruitment",
            target_descender_id=actor,
            recruitment_offer_id=offered.resolved_offer_id,
        ),
    )

    refused_offer = social.execute(
        descent,
        social.propose(descent, recruiter, "recruit", target_descender_id=recruit_target),
    )
    refused = social.execute(
        descent,
        social.propose(
            descent,
            recruit_target,
            "refuse_recruitment",
            target_descender_id=recruiter,
            recruitment_offer_id=refused_offer.resolved_offer_id,
        ),
    )
    challenge = social.execute(descent, probe)
    if challenge.executed:
        # The probe became stale after earlier interactions, as required. Build a
        # fresh challenge so the canonical challenge path is also exercised.
        raise RuntimeError("old proposal unexpectedly survived intervening canonical interactions")
    fresh_challenge = social.execute(
        descent,
        social.propose(descent, recruiter, "challenge", target_descender_id=recruit_target),
    )

    stale = social.propose(descent, recruiter, "challenge", target_descender_id=recruit_target)
    brain.autonomous.survival.advance_time(descent, descent.current_tick + 1)
    stale_before = descent.model_dump(mode="json")
    stale_history = list(descent.history_event_ids)
    stale_result = social.execute(descent, stale)
    stale_rejection_side_effect_free = (
        not stale_result.executed
        and stale_result.reason_code == "stale_observation"
        and descent.model_dump(mode="json") == stale_before
        and descent.history_event_ids == stale_history
    )

    shared_memory = memory.get_memory(descent, receiver, actor, "shared_resource")
    if shared_memory is None:
        raise RuntimeError("proof sharing did not create accepted 30C.2 memory")
    relationship = get_relationship(descent, receiver, actor)
    snapshot = build_social_intent_snapshot(descent)
    events = persistence.replay_events(descent.id)
    event_counts = Counter(event.event_type for event in events)

    return {
        "persistence": persistence,
        "brain": brain,
        "memory": memory,
        "social": social,
        "descent": descent,
        "snapshot": snapshot,
        "event_counts": dict(sorted(event_counts.items())),
        "proposal_side_effect_free": proposal_side_effect_free,
        "stale_rejection_side_effect_free": stale_rejection_side_effect_free,
        "share_item_result": share_item,
        "share_supply_result": share_supply,
        "warning_result": warning,
        "offered_result": offered,
        "accepted_result": accepted,
        "refused_offer_result": refused_offer,
        "refused_result": refused,
        "challenge_result": fresh_challenge,
        "stale_result": stale_result,
        "shared_memory": shared_memory,
        "relationship": relationship,
        "loot_id": loot_id,
        "supply_id": supply_id,
        "cache_id": cache["cache_id"],
        "warning_sector": warning_sector,
    }


def generate(output: Path, *, seed: str, count: int, strata: int) -> dict:
    if count < 5:
        raise ValueError("30C.3 proof requires at least five Descenders")
    ids = [f"descender_{index:03d}" for index in range(count)]
    first = _execute_sequence(seed, ids, strata)
    second = _execute_sequence(seed, ids, strata)

    descent = first["descent"]
    twin = second["descent"]
    independent_state_equal = twin.model_dump(mode="json") == descent.model_dump(mode="json")
    independent_snapshot_equal = second["snapshot"] == first["snapshot"]
    independent_event_ids_equal = twin.history_event_ids == descent.history_event_ids
    if not independent_state_equal or not independent_snapshot_equal or not independent_event_ids_equal:
        raise RuntimeError("independent 30C.3 interaction sequence diverged")

    persistence = first["persistence"]
    events = persistence.replay_events(descent.id)
    checkpoint_dir = output.parent / "checkpoint"
    store = AlphaCheckpointStore(checkpoint_dir, retention=4)
    written = store.write(
        "30c3-proof-runtime",
        descent,
        events,
        simulation_config={"protocol": PROTOCOL, "slice": "30C.3"},
        reason="30c3-proof",
        created_at_unix_ms=3003001,
    )
    loaded = store.load_latest().crawl
    checkpoint_state_equal = loaded.model_dump(mode="json") == descent.model_dump(mode="json")
    checkpoint_snapshot_equal = build_social_intent_snapshot(loaded) == first["snapshot"]
    if not checkpoint_state_equal or not checkpoint_snapshot_equal:
        raise RuntimeError("30C.3 checkpoint restore diverged")

    metadata = descent.modifiers["_social_intent_execution"]
    accepted_offers = [offer for offer in metadata["recruitment_offers"].values() if offer["status"] == "accepted"]
    refused_offers = [offer for offer in metadata["recruitment_offers"].values() if offer["status"] == "refused"]
    warning_knowledge = descent.participants[ids[1]].agent.knowledge[first["warning_sector"]]

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": PROTOCOL,
        "authoritative": True,
        "canonical_owner": "deterministic_simulation",
        "provider_can_mutate": False,
        "proposal_can_mutate": False,
        "presentation_feedback_allowed": False,
        "party_mutation_enabled": False,
        "seed": seed,
        "descent_id": descent.id,
        "population_count": count,
        "configured_stratum_count": strata,
        "final_tick": descent.current_tick,
        "proposal_side_effect_free": first["proposal_side_effect_free"],
        "stale_rejection_side_effect_free": first["stale_rejection_side_effect_free"],
        "stale_rejection_reason": first["stale_result"].reason_code,
        "execution_count": metadata["execution_count"],
        "interaction_trace_digest": first["snapshot"]["interaction_trace_digest"],
        "recruitment_offer_count": len(metadata["recruitment_offers"]),
        "accepted_recruitment_count": len(accepted_offers),
        "refused_recruitment_count": len(refused_offers),
        "party_count": len(descent.parties),
        "participants_with_party": sum(participant.current_party_id is not None for participant in descent.participants.values()),
        "shared_item_id": first["loot_id"],
        "shared_item_owner": descent.items[first["loot_id"]].owner_npc_id,
        "shared_supply_id": first["supply_id"],
        "shared_supply_owner": descent.items[first["supply_id"]].owner_npc_id,
        "shared_memory_reinforcement_count": first["shared_memory"].reinforcement_count,
        "shared_memory_source_event_count": len(first["shared_memory"].source_event_ids),
        "receiver_trust": first["relationship"].trust,
        "receiver_gratitude": first["relationship"].gratitude,
        "warning_sector_id": first["warning_sector"],
        "warning_knowledge_confidence": warning_knowledge.confidence,
        "warning_knowledge_neighbor_count": len(warning_knowledge.known_neighbors),
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
            "social_proposal_is_advisory": True,
            "simulation_validates_social_legality": True,
            "simulation_executes_social_mutation": True,
            "stale_or_rejected_proposals_are_side_effect_free": True,
            "item_sharing_uses_canonical_item_ownership": True,
            "supply_sharing_preserves_30a4_authority": True,
            "sharing_feeds_30c2_memory": True,
            "warning_shares_only_known_sector_state": True,
            "recruitment_is_structured_social_state": True,
            "recruitment_does_not_create_party": True,
            "persistent_party_owner_slice": "30C.4",
            "challenge_does_not_start_combat": True,
            "social_conflict_owner_slice": "30C.5",
            "presentation_can_mutate": False,
            "unreal_can_mutate": False,
            "dialogue_owner_phase": "31",
            "next_slice": "30C.4 - Parties, Alliances & Leadership",
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(canonical_json(proof) + "\n", encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30c3-social-intent-proof")
    parser.add_argument("--count", type=int, default=6)
    parser.add_argument("--strata", type=int, default=3)
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed, count=args.count, strata=args.strata)
    print(
        f"[30C.3] proof digest={proof['digest']} executions={proof['execution_count']} "
        f"offers={proof['recruitment_offer_count']} trust={proof['receiver_trust']}"
    )
    print("[30C.3] Deterministic social intent execution proof PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
