from __future__ import annotations

from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.runtime_checkpoint import AlphaCheckpointStore
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import (
    METADATA_KEY,
    GroupSocialOrchestrationService,
    build_group_social_orchestration_snapshot,
    strategy_for,
    validate_group_social_orchestration,
)
from livingworld.underreach_parties_alliances_leadership import (
    PartiesAlliancesLeadershipService,
    deterministic_leader,
)
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import SocialStateService


def _stack(seed: str = "30c6-group-social-test", *, count: int = 8, strata: int = 3):
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
    return persistence, brain, memory, social, parties, conflict, orchestration, descent, ids


def _accepted_offer(social: SocialIntentExecutionService, descent, source: str, target: str) -> str:
    offered = social.execute(descent, social.propose(descent, source, "recruit", target_descender_id=target))
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
        result = parties.form_from_accepted_recruitment(descent, _accepted_offer(social, descent, source, target))
        party_id = result.party_id
    assert party_id is not None
    return party_id


def _seed_relationship(state: SocialStateService, descent, source: str, target: str, *, positive: bool) -> None:
    if positive:
        values = {"trust": 0.8, "respect": 0.65, "affection": 0.35, "gratitude": 0.35, "familiarity": 0.6}
    else:
        values = {"trust": -0.8, "respect": -0.5, "resentment": 0.85, "rivalry": 0.8, "familiarity": 0.7}
    for dimension, value in values.items():
        state.adjust_dimension(
            descent,
            source,
            target,
            dimension,
            value,
            reason_code="30c6.test_social_basis",
        )


def _seed_grievance(memory: SocialMemoryEvolutionService, descent, offender: str, victim: str, event_type: str) -> str:
    event = memory.lifecycle.record_event(
        descent,
        event_type,
        f"30C.6 canonical grievance source {event_type}.",
        actor_ids=[offender, victim],
        location_id=descent.participants[victim].current_location_id,
        data={"state_changes": {"30c6_test_grievance": event_type}},
    )
    memory.lifecycle.save(descent)
    processed = memory.process_event(descent, event)
    assert processed.processed
    return event.id


def test_strategy_classification_is_deterministic_and_side_effect_free() -> None:
    _, _, _, _, _, _, _, descent, ids = _stack(seed="30c6-strategy")
    before = descent.model_dump(mode="json")
    first = {npc_id: strategy_for(descent, npc_id) for npc_id in ids}
    second = {npc_id: strategy_for(descent, npc_id) for npc_id in ids}
    assert first == second
    assert set(first.values()) <= {"cooperative", "balanced", "selfish"}
    assert descent.model_dump(mode="json") == before


def test_positive_social_basis_forms_party_unattended() -> None:
    persistence, _, _, _, _, _, orchestration, descent, ids = _stack(seed="30c6-auto-party")
    state = SocialStateService(persistence)
    _seed_relationship(state, descent, ids[0], ids[1], positive=True)
    _seed_relationship(state, descent, ids[1], ids[0], positive=True)

    record = orchestration.step(descent)

    party_ids = {descent.participants[ids[0]].current_party_id, descent.participants[ids[1]].current_party_id}
    assert None not in party_ids
    assert len(party_ids) == 1
    party_id = next(iter(party_ids))
    assert descent.parties[party_id].active
    assert ids[0] in descent.parties[party_id].member_npc_ids
    assert ids[1] in descent.parties[party_id].member_npc_ids
    assert any(decision["decision_type"] == "recruitment" and decision["outcome"] == "accepted_materialized" for decision in record["decisions"])
    assert descent.modifiers[METADATA_KEY]["metrics"]["party_formations"] >= 1


def test_leadership_changes_autonomously_to_deterministic_best_member() -> None:
    _, _, _, social, parties, _, orchestration, descent, ids = _stack(seed="30c6-leadership")
    expected = deterministic_leader(descent, ids[:2])
    source = ids[1] if expected == ids[0] else ids[0]
    target = expected
    party_id = _form_party(social, parties, descent, source, [target])
    assert descent.parties[party_id].leader_npc_id == source

    orchestration.step(descent)

    assert descent.parties[party_id].leader_npc_id == expected
    assert descent.modifiers[METADATA_KEY]["metrics"]["leadership_changes"] >= 1


def test_positive_party_leaders_can_form_alliance_without_manual_alliance_command() -> None:
    persistence, _, _, social, parties, _, orchestration, descent, ids = _stack(seed="30c6-alliance")
    left_party = _form_party(social, parties, descent, ids[0], [ids[1]])
    right_party = _form_party(social, parties, descent, ids[2], [ids[3]])
    left_leader = descent.parties[left_party].leader_npc_id
    right_leader = descent.parties[right_party].leader_npc_id
    state = SocialStateService(persistence)
    _seed_relationship(state, descent, left_leader, right_leader, positive=True)
    _seed_relationship(state, descent, right_leader, left_leader, positive=True)

    record = orchestration.step(descent)

    party_metadata = descent.modifiers["_parties_alliances_leadership"]
    active = [value for value in party_metadata["alliances"].values() if value["status"] == "active"]
    assert any(sorted(value["party_ids"]) == sorted([left_party, right_party]) for value in active)
    assert any(decision["decision_type"] == "alliance" and decision["outcome"] == "formed" for decision in record["decisions"])


def test_accumulated_rivalry_can_drive_autonomous_party_conflict() -> None:
    persistence, _, memory, social, parties, _, orchestration, descent, ids = _stack(seed="30c6-rivalry")
    party_id = _form_party(social, parties, descent, ids[0], [ids[1], ids[2]])
    leader = descent.parties[party_id].leader_npc_id
    victim = next(npc_id for npc_id in descent.parties[party_id].member_npc_ids if npc_id != leader)
    state = SocialStateService(persistence)
    _seed_relationship(state, descent, victim, leader, positive=False)
    _seed_grievance(memory, descent, leader, victim, "PROMISE_VIOLATED")
    _seed_grievance(memory, descent, leader, victim, "LOOT_STOLEN")

    record = orchestration.step(descent)

    attempts = [decision for decision in record["decisions"] if decision["decision_type"] == "party_conflict" and decision["actor_id"] == victim]
    assert attempts
    assert descent.modifiers[METADATA_KEY]["metrics"]["conflict_attempts"] >= 1
    # 30C.5 owns the final legality. If executed it must be Ledger bound; if not,
    # the rejection remains side-effect safe and is still a deterministic choice.
    if attempts[0]["outcome"] != "rejected":
        assert attempts[0]["event_id"] in descent.history_event_ids
        assert descent.modifiers[METADATA_KEY]["metrics"]["hostile_conflicts"] >= 1


def test_group_social_run_advances_existing_brain_runtime_without_stealing_gameplay_authority() -> None:
    _, brain, _, _, _, _, orchestration, descent, _ = _stack(seed="30c6-run", count=10, strata=3)
    before_tick = descent.current_tick
    result = orchestration.run(descent, max_gameplay_steps=4)

    assert result.gameplay_steps >= 1
    assert descent.current_tick > before_tick
    assert descent.modifiers["_brain_driven_descent"]["step_count"] == result.gameplay_steps
    assert descent.modifiers[METADATA_KEY]["step_count"] == result.social_steps
    assert validate_group_social_orchestration(descent)


def test_checkpoint_and_persistence_preserve_social_arc_exactly(tmp_path: Path) -> None:
    persistence, brain, _, _, _, _, orchestration, descent, _ = _stack(seed="30c6-checkpoint", count=9, strata=3)
    orchestration.step(descent)
    brain.step(descent)
    orchestration.step(descent)
    expected_state = descent.model_dump(mode="json")
    expected_snapshot = build_group_social_orchestration_snapshot(descent)

    saved = persistence.load_crawl(descent.id)
    assert saved is not None
    assert saved.model_dump(mode="json") == expected_state
    assert build_group_social_orchestration_snapshot(saved) == expected_snapshot

    events = persistence.replay_events(descent.id)
    store = AlphaCheckpointStore(tmp_path / "checkpoint", retention=4)
    store.write(
        "30c6-test-runtime",
        descent,
        events,
        simulation_config={"slice": "30C.6"},
        reason="30c6-test",
        created_at_unix_ms=3006001,
    )
    loaded = store.load_latest().crawl
    assert loaded.model_dump(mode="json") == expected_state
    assert build_group_social_orchestration_snapshot(loaded) == expected_snapshot


def test_independent_identical_social_orchestration_is_deterministic() -> None:
    def run_once():
        _, brain, _, _, _, _, orchestration, descent, _ = _stack(seed="30c6-determinism", count=10, strata=3)
        for _ in range(3):
            orchestration.step(descent)
            if descent.modifiers["_brain_driven_descent"]["run_outcome"] != "running":
                break
            brain.step(descent)
        return descent.model_dump(mode="json"), build_group_social_orchestration_snapshot(descent)

    first_state, first_snapshot = run_once()
    second_state, second_snapshot = run_once()
    assert first_state == second_state
    assert first_snapshot == second_snapshot
