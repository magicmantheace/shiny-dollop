from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import (
    HighlightStoryArcService,
    StoryArcStatus,
    StoryArcType,
    tier_for_score,
)
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


PROOF_PROTOCOL = "underreach.highlight-story-arc-proof.v1"


def _canonical_stack(seed: str):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(6)]
    descent = brain.create(seed=seed, descender_ids=ids, stratum_count=3)
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
    return persistence, descent, ids, memory, CrawlLifecycleService(persistence), CanonicalMediaEventExporter(persistence)


def _record(lifecycle, descent, event_type: str, actors: list[str], *, danger: float, extra=None):
    data = {
        "danger": danger,
        "state_changes": {"30_5_3_proof": event_type},
        "media_proof": {"event_type": event_type, "supported": True},
    }
    if extra:
        data.update(extra)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.3 canonical proof source {event_type}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data=data,
    )


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    database_path = output.with_suffix(".sqlite3")
    if database_path.exists():
        database_path.unlink()

    canonical, descent, ids, memory, lifecycle, exporter = _canonical_stack(seed)

    prior = _record(lifecycle, descent, "BETRAYAL", ids[:2], danger=0.60)
    if not memory.process_event(descent, prior).processed:
        raise RuntimeError("30.5.3 proof failed to seed canonical social-memory thread")
    high = _record(
        lifecycle,
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        ids[:2],
        danger=1.0,
        extra={
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
        raise RuntimeError("30.5.3 proof failed to reinforce canonical social-memory thread")
    low = _record(lifecycle, descent, "CAMP_NOTE", ids[2:3], danger=0.0)
    death = _record(lifecycle, descent, "DEATH", ids[:1], danger=1.0)

    high_envelope = exporter.export_event(descent, high.id)
    low_envelope = exporter.export_event(descent, low.id)
    death_envelope = exporter.export_event(descent, death.id)

    canonical_before = descent.model_dump(mode="json")
    fingerprint_before = descent.fingerprint()
    history_before = list(descent.history_event_ids)
    ledger_before = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    media = MediaPersistence(f"sqlite:///{database_path.as_posix()}")
    media.initialize()
    for envelope in (high_envelope, low_envelope, death_envelope):
        media.register_envelope(envelope)

    detector = HighlightStoryArcService(media)
    detector.initialize()
    evaluations = detector.evaluate_many([death_envelope, low_envelope, high_envelope])
    by_envelope = {item.envelope_id: item for item in evaluations}
    high_eval = by_envelope[high_envelope.envelope_id]
    low_eval = by_envelope[low_envelope.envelope_id]
    death_eval = by_envelope[death_envelope.envelope_id]
    repeat_high = detector.evaluate(high_envelope)
    snapshot = detector.snapshot()

    reopened_media = MediaPersistence(f"sqlite:///{database_path.as_posix()}")
    reopened_media.initialize()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened_snapshot = reopened_detector.snapshot()
    reopened_repeat = reopened_detector.evaluate(high_envelope)
    reopened_after_repeat = reopened_detector.snapshot()

    arcs = reopened_detector.list_story_arcs(crawl_id=descent.id)
    survival = [arc for arc in arcs if arc.arc_type == StoryArcType.SURVIVAL and ids[0] in arc.subject_ids]
    conflict = [arc for arc in arcs if arc.arc_type == StoryArcType.SOCIAL_CONFLICT]
    loot = [arc for arc in arcs if arc.arc_type == StoryArcType.LOOT_PROGRESSION]

    canonical_after = descent.model_dump(mode="json")
    ledger_after = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]
    tier_boundaries = {
        str(value): tier_for_score(value).value
        for value in (49, 50, 69, 70, 79, 80, 89, 90, 94, 95, 100)
    }

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
            "llm_decision_used": snapshot["llm_decision_used"],
            "unreal_dependency": snapshot["unreal_dependency"],
            "provider_invocation_used": snapshot["provider_invocation_used"],
            "highlight_detection_is_deterministic_python": True,
            "highlight_detection_enqueues_generation_jobs": False,
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
        "tier_boundaries": tier_boundaries,
        "high_signal": {
            "selected": high_eval.selected,
            "total_score": high_eval.score.total,
            "danger": high_eval.score.danger,
            "rarity": high_eval.score.rarity,
            "social_stakes": high_eval.score.social_stakes,
            "character_significance": high_eval.score.character_significance,
            "outcome_reversal": high_eval.score.outcome_reversal,
            "continuity": high_eval.score.continuity,
            "visual_potential": high_eval.score.visual_potential,
            "tier": high_eval.output_tier.value,
            "highlight_id": high_eval.highlight_id,
            "arc_ids": list(high_eval.arc_ids),
            "reason_codes": list(high_eval.reason_codes),
            "repeat_equal": repeat_high == high_eval,
            "reopen_repeat_equal": reopened_repeat == high_eval,
        },
        "low_signal": {
            "selected": low_eval.selected,
            "total_score": low_eval.score.total,
            "tier": low_eval.output_tier.value,
            "highlight_id": low_eval.highlight_id,
        },
        "death_signal": {
            "selected": death_eval.selected,
            "total_score": death_eval.score.total,
            "tier": death_eval.output_tier.value,
        },
        "story_arcs": {
            "count": len(arcs),
            "types": sorted(set(arc.arc_type.value for arc in arcs)),
            "survival_arc_count": len(survival),
            "survival_closed": bool(survival) and all(arc.status == StoryArcStatus.CLOSED for arc in survival),
            "social_conflict_arc_count": len(conflict),
            "loot_progression_arc_count": len(loot),
            "all_have_provenance": all(bool(arc.envelope_ids) and bool(arc.source_event_ids) for arc in arcs),
        },
        "media": {
            "highlight_count": snapshot["highlight_count"],
            "story_arc_count": snapshot["story_arc_count"],
            "highlight_digest": snapshot["highlight_digest"],
            "story_arc_digest": snapshot["story_arc_digest"],
            "snapshot_digest": snapshot["digest"],
            "snapshot_equal_after_reopen": reopened_snapshot == snapshot,
            "snapshot_equal_after_repeat": reopened_after_repeat == snapshot,
            "media_job_count": len(reopened_media.list_jobs()),
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-3-highlight-proof")
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed)
    print(
        json.dumps(
            {
                "digest": proof["digest"],
                "high_score": proof["high_signal"]["total_score"],
                "high_tier": proof["high_signal"]["tier"],
                "arcs": proof["story_arcs"]["count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
