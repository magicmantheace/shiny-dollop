from __future__ import annotations

from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import (
    ALLIANCE_BETRAYAL_EVENT,
    DECEPTION_CREATED_EVENT,
    METADATA_KEY,
    REVENGE_STARTED_EVENT,
    RivalryBetrayalSocialConflictService,
    build_rivalry_betrayal_social_conflict_snapshot,
    validate_rivalry_betrayal_social_conflict,
)
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import get_relationship


def _stack(seed: str = "30c5-conflict-test", *, count: int = 8, strata: int = 3):
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
    return persistence, brain, memory, social, parties, conflict, descent, ids


def _accepted_offer(social: SocialIntentExecutionService, descent, source: str, target: str) -> str:
    offered = social.execute(
        descent,
        social.propose(descent, source, "recruit", target_descender_id=target),
    )
    assert offered.executed and offered.resolved_offer_id is not None
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
    assert accepted.executed
    return offered.resolved_offer_id


def _form_party(social, parties, descent, source: str, members: list[str]) -> str:
    party_id = None
    for target in members:
        offer_id = _accepted_offer(social, descent, source, target)
        result = parties.form_from_accepted_recruitment(descent, offer_id)
        party_id = result.party_id
    assert party_id is not None
    return party_id


def _seed_negative(memory: SocialMemoryEvolutionService, descent, offender: str, victim: str, event_type: str):
    event = memory.lifecycle.record_event(
        descent,
        event_type,
        f"30C.5 test grievance source {event_type}.",
        actor_ids=[offender, victim],
        location_id=descent.participants[victim].current_location_id,
        data={"state_changes": {"test_social_grievance": event_type}},
    )
    memory.lifecycle.save(descent)
    result = memory.process_event(descent, event)
    assert result.processed
    return event


def _strong_grievance(memory, descent, offender: str, victim: str):
    first = _seed_negative(memory, descent, offender, victim, "PROMISE_VIOLATED")
    second = _seed_negative(memory, descent, offender, victim, "LOOT_STOLEN")
    return first, second


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    start = participant.current_location_id
    assert start is not None
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
    assert target_sector_id in parent
    result: list[str] = []
    current: str | None = target_sector_id
    while current is not None:
        result.append(current)
        current = parent[current]
    return list(reversed(result))


def _move(brain: BrainDrivenDescentService, descent, descender_id: str, target_sector_id: str) -> None:
    for sector_id in _route(descent, descender_id, target_sector_id)[1:]:
        brain.autonomous.survival.commit_descender_position(descent, descender_id, sector_id)


def _owned_loot(brain: BrainDrivenDescentService, descent, owner_id: str, other_id: str) -> str:
    cache = next(
        value for value in descent.modifiers["_loot_cache_relic"]["caches"]
        if value["stratum_number"] == descent.current_floor
    )
    for npc_id in (owner_id, other_id):
        _move(brain, descent, npc_id, cache["sector_id"])
    item_ids = brain.autonomous.survival.open_cache(descent, cache["cache_id"], owner_id)
    item_id = sorted(item_ids)[0]
    brain.autonomous.survival.loot.claim_ground_item(descent, item_id, owner_id)
    return item_id


def test_neutral_state_cannot_betray_from_incentive_alone() -> None:
    _, _, _, social, parties, conflict, descent, ids = _stack(seed="30c5-neutral-reject")
    _form_party(social, parties, descent, ids[0], [ids[1], ids[2]])
    before = descent.model_dump(mode="json")
    intent = conflict.propose(
        descent, ids[0], ids[1], "betray_party",
        incentive_code="survival", incentive_strength=1.0,
    )
    result = conflict.execute(descent, intent)
    assert not result.executed
    assert result.reason_code in {"insufficient_accumulated_conflict", "high_impact_negative_evidence_required"}
    assert descent.model_dump(mode="json") == before


def test_refuse_aid_is_ledger_bound_and_creates_target_grievance() -> None:
    persistence, _, memory, _, _, conflict, descent, ids = _stack(seed="30c5-refuse-aid")
    _strong_grievance(memory, descent, ids[1], ids[0])
    before = get_relationship(descent, ids[1], ids[0])
    result = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[1], "refuse_aid",
            incentive_code="resource_scarcity", incentive_strength=0.8,
        ),
    )
    assert result.executed and result.memory_event_ids
    target_memory = memory.get_memory(descent, ids[1], ids[0], "refused_aid")
    assert target_memory is not None
    after = get_relationship(descent, ids[1], ids[0])
    assert after.trust < before.trust
    assert after.resentment > before.resentment
    event = persistence.events_by_ids([result.source_event_id])[0]
    assert event.event_type == "AID_REFUSED"


def test_loot_conflict_transfers_real_item_and_escalates_rivalry() -> None:
    persistence, brain, memory, _, _, conflict, descent, ids = _stack(seed="30c5-loot-theft")
    item_id = _owned_loot(brain, descent, ids[1], ids[0])
    _strong_grievance(memory, descent, ids[1], ids[0])
    result = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[1], "steal_loot",
            incentive_code="loot", incentive_strength=0.9, target_item_id=item_id,
        ),
    )
    assert result.executed
    assert descent.items[item_id].owner_npc_id == ids[0]
    assert result.source_event_id in descent.items[item_id].provenance_event_ids
    victim_memory = memory.get_memory(descent, ids[1], ids[0], "stole_loot")
    assert victim_memory is not None
    assert get_relationship(descent, ids[1], ids[0]).rivalry > 0.0
    assert persistence.events_by_ids([result.source_event_id])[0].event_type == "LOOT_STOLEN"


def test_structured_deception_creates_no_false_memory_until_exposed() -> None:
    persistence, _, memory, _, _, conflict, descent, ids = _stack(seed="30c5-deception")
    _strong_grievance(memory, descent, ids[1], ids[0])
    created = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[1], "deceive",
            incentive_code="loot", incentive_strength=0.75, claim_code="loot_location",
        ),
    )
    assert created.executed and created.deception_id is not None
    assert memory.get_memory(descent, ids[1], ids[0], "violated_promise") is None
    created_event = persistence.events_by_ids([created.source_event_id])[0]
    assert created_event.event_type == DECEPTION_CREATED_EVENT

    exposed = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[1], ids[0], "expose_deception",
            incentive_code="revenge", incentive_strength=0.0,
            deception_id=created.deception_id,
        ),
    )
    assert exposed.executed
    assert memory.get_memory(descent, ids[1], ids[0], "violated_promise") is not None
    record = descent.modifiers[METADATA_KEY]["deceptions"][created.deception_id]
    assert record["status"] == "exposed"


def test_party_betrayal_requires_evidence_and_preserves_party_domain_invariants() -> None:
    _, _, memory, social, parties, conflict, descent, ids = _stack(seed="30c5-party-betrayal")
    party_id = _form_party(social, parties, descent, ids[0], [ids[1], ids[2]])
    _strong_grievance(memory, descent, ids[1], ids[0])
    result = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[1], "betray_party",
            incentive_code="leadership", incentive_strength=0.9,
        ),
    )
    assert result.executed and result.affected_party_id == party_id
    assert descent.participants[ids[0]].current_party_id is None
    assert descent.parties[party_id].active
    assert sorted(descent.parties[party_id].member_npc_ids) == sorted([ids[1], ids[2]])
    assert memory.get_memory(descent, ids[1], ids[0], "betrayed") is not None
    assert memory.get_memory(descent, ids[2], ids[0], "betrayed") is not None
    assert validate_rivalry_betrayal_social_conflict(descent)


def test_abandonment_is_distinct_from_betrayal() -> None:
    _, _, memory, social, parties, conflict, descent, ids = _stack(seed="30c5-abandon")
    _form_party(social, parties, descent, ids[0], [ids[1], ids[2]])
    _strong_grievance(memory, descent, ids[1], ids[0])
    result = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[1], "abandon_party",
            incentive_code="escape", incentive_strength=0.7,
        ),
    )
    assert result.executed
    assert memory.get_memory(descent, ids[1], ids[0], "abandoned") is not None
    assert memory.get_memory(descent, ids[1], ids[0], "betrayed") is None


def test_hostile_alliance_break_is_owned_by_30c5_and_archived() -> None:
    persistence, _, memory, social, parties, conflict, descent, ids = _stack(seed="30c5-alliance-break")
    left = _form_party(social, parties, descent, ids[0], [ids[1]])
    right = _form_party(social, parties, descent, ids[2], [ids[3]])
    alliance = parties.form_alliance(descent, left, right)
    _strong_grievance(memory, descent, ids[2], ids[0])

    result = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[2], "break_alliance",
            incentive_code="survival", incentive_strength=0.95,
            alliance_id=alliance.alliance_id,
        ),
    )
    assert result.executed
    assert alliance.alliance_id not in descent.modifiers["_parties_alliances_leadership"]["alliances"]
    archived = descent.modifiers[METADATA_KEY]["hostile_alliance_breaks"][alliance.alliance_id]
    assert archived["break_event_id"] == result.source_event_id
    assert memory.get_memory(descent, ids[2], ids[0], "betrayed") is not None
    assert memory.get_memory(descent, ids[3], ids[0], "betrayed") is not None
    assert persistence.events_by_ids([result.source_event_id])[0].event_type == ALLIANCE_BETRAYAL_EVENT


def test_revenge_seeking_is_persistent_but_does_not_start_combat() -> None:
    persistence, _, memory, _, _, conflict, descent, ids = _stack(seed="30c5-revenge")
    first, second = _strong_grievance(memory, descent, ids[1], ids[0])
    result = conflict.execute(
        descent,
        conflict.propose(
            descent, ids[0], ids[1], "seek_revenge",
            incentive_code="revenge", incentive_strength=0.9,
        ),
    )
    assert result.executed and result.revenge_id is not None
    revenge = descent.modifiers[METADATA_KEY]["revenge_records"][result.revenge_id]
    assert revenge["status"] == "active"
    assert set(revenge["basis_event_ids"]) == {first.id, second.id}
    event = persistence.events_by_ids([result.source_event_id])[0]
    assert event.event_type == REVENGE_STARTED_EVENT
    assert event.data["combat_started"] is False


def test_stale_conflict_proposal_is_rejected_without_mutation() -> None:
    _, brain, memory, _, _, conflict, descent, ids = _stack(seed="30c5-stale")
    _strong_grievance(memory, descent, ids[1], ids[0])
    intent = conflict.propose(
        descent, ids[0], ids[1], "refuse_aid",
        incentive_code="survival", incentive_strength=0.8,
    )
    brain.autonomous.survival.advance_time(descent, descent.current_tick + 1)
    before = descent.model_dump(mode="json")
    result = conflict.execute(descent, intent)
    assert not result.executed
    assert result.reason_code == "stale_observation"
    assert descent.model_dump(mode="json") == before


def test_persistence_checkpoint_and_independent_reproduction_are_exact(tmp_path: Path) -> None:
    def run_once(seed: str):
        persistence, _, memory, _, _, conflict, descent, ids = _stack(seed=seed)
        _strong_grievance(memory, descent, ids[1], ids[0])
        conflict.execute(
            descent,
            conflict.propose(
                descent, ids[0], ids[1], "refuse_aid",
                incentive_code="resource_scarcity", incentive_strength=0.8,
            ),
        )
        conflict.execute(
            descent,
            conflict.propose(
                descent, ids[0], ids[1], "seek_revenge",
                incentive_code="revenge", incentive_strength=0.9,
            ),
        )
        return persistence, descent, build_rivalry_betrayal_social_conflict_snapshot(descent)

    persistence, descent, snapshot = run_once("30c5-persistence")
    _, twin, twin_snapshot = run_once("30c5-persistence")
    assert twin.model_dump(mode="json") == descent.model_dump(mode="json")
    assert twin_snapshot == snapshot

    loaded = persistence.load_crawl(descent.id)
    assert loaded is not None
    assert loaded.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_rivalry_betrayal_social_conflict_snapshot(loaded) == snapshot

    events = persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoint", retention=4)
    store.write(
        "30c5-test-runtime", descent, events,
        simulation_config={"slice": "30C.5"}, reason="30c5-test", created_at_unix_ms=3005001,
    )
    restored = store.load_latest().crawl
    assert restored.model_dump(mode="json") == descent.model_dump(mode="json")
    assert build_rivalry_betrayal_social_conflict_snapshot(restored) == snapshot
