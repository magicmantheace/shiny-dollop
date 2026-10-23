from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import (
    ChapterKind,
    ChroniclePolicy,
    DelverChronicleProfileService,
    ProfileStatus,
)
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService
from livingworld.underreach_social_state import SocialStateService


PROOF_PROTOCOL = "underreach.delver-chronicle-profile-proof.v1"


def _stack(seed: str):
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    ids = [f"descender_{index:03d}" for index in range(8)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=3)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(canonical)
    memory.initialize(descent)
    social = SocialIntentExecutionService(canonical)
    social.initialize(descent)
    parties = PartiesAlliancesLeadershipService(canonical)
    parties.initialize(descent)
    conflict = RivalryBetrayalSocialConflictService(canonical)
    conflict.initialize(descent)
    orchestration = GroupSocialOrchestrationService(canonical, brain=brain)
    orchestration.initialize(descent)
    return canonical, descent, ids, memory, social, parties, CrawlLifecycleService(canonical), CanonicalMediaEventExporter(canonical)


def _event(lifecycle, descent, event_type: str, actors: list[str], *, danger: float = 0.0, data=None):
    payload = {"danger": danger, "state_changes": {"30_5_4_proof": event_type}}
    if data:
        payload.update(data)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.4 canonical proof source {event_type}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data=payload,
    )


def _accept_recruitment(social, descent, source: str, target: str) -> str:
    offered = social.execute(descent, social.propose(descent, source, "recruit", target_descender_id=target))
    if not offered.executed or offered.resolved_offer_id is None:
        raise RuntimeError("30.5.4 proof failed recruitment offer")
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
        raise RuntimeError("30.5.4 proof failed recruitment acceptance")
    return offered.resolved_offer_id


def _form_pair(social, parties, descent, source: str, target: str) -> str:
    return parties.form_from_accepted_recruitment(descent, _accept_recruitment(social, descent, source, target)).party_id


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    database_path = output.with_suffix(".sqlite3")
    if database_path.exists():
        database_path.unlink()

    canonical, descent, ids, memory, social, parties, lifecycle, exporter = _stack(seed)
    left_party = _form_pair(social, parties, descent, ids[0], ids[1])
    right_party = _form_pair(social, parties, descent, ids[2], ids[3])
    alliance = parties.form_alliance(descent, left_party, right_party)
    state = SocialStateService(canonical)
    state.adjust_dimension(descent, ids[0], ids[1], "trust", 0.82, reason_code="30_5_4.proof_ally")
    state.adjust_dimension(descent, ids[0], ids[2], "resentment", 0.88, reason_code="30_5_4.proof_rival")

    prior = _event(lifecycle, descent, "BETRAYAL", ids[:2], danger=0.6)
    if not memory.process_event(descent, prior).processed:
        raise RuntimeError("30.5.4 proof failed prior social memory")
    high = _event(
        lifecycle,
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        ids[:2],
        danger=1.0,
        data={
            "social_facts": [
                {
                    "observer_descender_id": ids[1],
                    "subject_descender_id": ids[0],
                    "memory_type": "betrayed",
                }
            ]
        },
    )
    if not memory.process_event(descent, high).processed:
        raise RuntimeError("30.5.4 proof failed current social memory")
    quiet_events = [
        _event(lifecycle, descent, f"STRATUM_NOTE_{index}", ids[2:3], danger=0.0)
        for index in range(3)
    ]
    death = _event(lifecycle, descent, "DEATH", ids[:1], danger=1.0)

    high_envelope = exporter.export_event(descent, high.id)
    quiet_envelopes = [exporter.export_event(descent, item.id) for item in quiet_events]
    death_envelope = exporter.export_event(descent, death.id)
    all_envelopes = [high_envelope, *quiet_envelopes, death_envelope]

    canonical_before = descent.model_dump(mode="json")
    fingerprint_before = descent.fingerprint()
    history_before = list(descent.history_event_ids)
    ledger_before = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    database_url = f"sqlite:///{database_path.as_posix()}"
    media = MediaPersistence(database_url)
    media.initialize()
    for envelope in all_envelopes:
        media.register_envelope(envelope)
    detector = HighlightStoryArcService(media)
    detector.initialize()
    high_eval = detector.evaluate(high_envelope)
    quiet_evals = [detector.evaluate(item) for item in quiet_envelopes]
    death_eval = detector.evaluate(death_envelope)

    policy = ChroniclePolicy(quiet_recap_min_envelopes=3)
    chronicle = DelverChronicleProfileService(media, policy=policy, highlights=detector)
    chronicle.initialize()
    chronicle.process(high_envelope)
    chronicle.process_many(reversed(quiet_envelopes))
    chronicle.process(death_envelope)
    repeat_terminal = chronicle.process(death_envelope)
    snapshot = chronicle.snapshot()

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened = DelverChronicleProfileService(reopened_media, policy=policy, highlights=reopened_detector)
    reopened.initialize()
    reopened_snapshot = reopened.snapshot()
    reopened.process(high_envelope)
    reopened_after_repeat = reopened.snapshot()

    profiles = reopened.list_profiles(crawl_id=descent.id)
    chapters = reopened.list_chapters(crawl_id=descent.id)
    by_delver = {item.delver_id: item for item in profiles}
    delver0 = by_delver[ids[0]]
    delver1 = by_delver[ids[1]]
    delver2 = by_delver[ids[2]]
    terminal_chapters = [item for item in chapters if item.chapter_kind == ChapterKind.TERMINAL]
    quiet_chapters = [item for item in chapters if item.chapter_kind == ChapterKind.QUIET_RECAP]
    highlight_chapters = [item for item in chapters if item.chapter_kind == ChapterKind.HIGHLIGHT]

    canonical_after = descent.model_dump(mode="json")
    ledger_after = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": snapshot["protocol"],
        "implementation_version": snapshot["implementation_version"],
        "phase": snapshot["phase"],
        "seed": seed,
        "authority_contract": {
            "authoritative": snapshot["authoritative"],
            "canonical_owner": snapshot["canonical_owner"],
            "presentation_can_mutate_simulation": snapshot["presentation_can_mutate_simulation"],
            "generated_prose_used": snapshot["generated_prose_used"],
            "claim_verification_required_before_prose": snapshot["claim_verification_required_before_prose"],
            "unreal_dependency": snapshot["unreal_dependency"],
            "provider_invocation_used": snapshot["provider_invocation_used"],
        },
        "canonical": {
            "state_unchanged": canonical_json(canonical_before) == canonical_json(canonical_after),
            "fingerprint_unchanged": fingerprint_before == descent.fingerprint(),
            "history_unchanged": history_before == descent.history_event_ids,
            "ledger_rows_unchanged": ledger_before == ledger_after,
            "fingerprint": descent.fingerprint(),
            "state_digest": payload_digest(canonical_after),
            "ledger_digest": payload_digest(ledger_after),
        },
        "highlight_input": {
            "high_selected": high_eval.selected,
            "high_highlight_id": high_eval.highlight_id,
            "quiet_all_archive_only": all(not item.selected for item in quiet_evals),
            "quiet_all_have_arcs": all(bool(item.arc_ids) for item in quiet_evals),
            "death_selected": death_eval.selected,
        },
        "profiles": {
            "count": len(profiles),
            "delver0_status": delver0.status.value,
            "delver0_closed": delver0.chronicle_closed,
            "delver0_party_id": delver0.current_party_id,
            "delver0_alliance_ids": list(delver0.current_alliance_ids),
            "delver0_has_ally": any(item.delver_id == ids[1] for item in delver0.known_allies),
            "delver0_has_rival": any(item.delver_id == ids[2] for item in delver0.known_rivals),
            "delver1_status": delver1.status.value,
            "delver1_closed": delver1.chronicle_closed,
            "delver2_status": delver2.status.value,
            "delver2_closed": delver2.chronicle_closed,
            "delver2_quiet_pending": len(delver2.pending_quiet_envelope_ids),
            "alliance_id": alliance.alliance_id,
        },
        "chapters": {
            "count": len(chapters),
            "highlight_count": len(highlight_chapters),
            "quiet_recap_count": len(quiet_chapters),
            "terminal_count": len(terminal_chapters),
            "all_structured_only": all(item.structured_only for item in chapters),
            "all_require_claim_verification": all(item.claim_verification_required for item in chapters),
            "none_generated_prose": all(not item.generated_prose_used for item in chapters),
            "all_have_fact_provenance": all(bool(item.allowed_fact_ids) and bool(item.source_event_ids) for item in chapters),
            "terminal_is_death": bool(terminal_chapters) and terminal_chapters[0].title_code == "TERMINAL_DEATH",
            "quiet_source_envelope_count": len(quiet_chapters[0].source_envelope_ids) if quiet_chapters else 0,
        },
        "media": {
            "profile_digest": snapshot["profile_digest"],
            "chapter_digest": snapshot["chapter_digest"],
            "snapshot_digest": snapshot["digest"],
            "snapshot_equal_after_reopen": reopened_snapshot == snapshot,
            "snapshot_equal_after_repeat": reopened_after_repeat == snapshot,
            "media_job_count": len(reopened_media.list_jobs()),
            "repeat_terminal_profile_count": len(repeat_terminal),
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-4-chronicle-proof")
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed)
    print(
        json.dumps(
            {
                "digest": proof["digest"],
                "profiles": proof["profiles"]["count"],
                "chapters": proof["chapters"]["count"],
                "closed": proof["profiles"]["delver0_closed"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
