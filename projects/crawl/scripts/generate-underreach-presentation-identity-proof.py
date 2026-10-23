from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import DelverChronicleProfileService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_loot_cache_relic import METADATA_KEY as LOOT_METADATA_KEY, LootCacheRelicService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import MediaPersistence
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_presentation_identity import PresentationIdentityService
from livingworld.underreach_resources_survival import ResourcesSurvivalService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


PROOF_PROTOCOL = "underreach.presentation-identity-proof.v1"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _stack(seed: str, database_url: str):
    canonical = CrawlPersistence("sqlite://")
    canonical.initialize()
    brain = BrainDrivenDescentService(canonical)
    descent = brain.create(seed=seed, descender_ids=IDS, stratum_count=3)
    brain.start(descent)
    memory = SocialMemoryEvolutionService(canonical)
    memory.initialize(descent)
    SocialIntentExecutionService(canonical).initialize(descent)
    PartiesAlliancesLeadershipService(canonical).initialize(descent)
    RivalryBetrayalSocialConflictService(canonical).initialize(descent)
    GroupSocialOrchestrationService(canonical, brain=brain).initialize(descent)
    lifecycle = CrawlLifecycleService(canonical)
    exporter = CanonicalMediaEventExporter(canonical)
    media = MediaPersistence(database_url)
    media.initialize()
    detector = HighlightStoryArcService(media)
    detector.initialize()
    chronicle = DelverChronicleProfileService(media, highlights=detector)
    chronicle.initialize()
    identities = PresentationIdentityService(media, chronicle=chronicle)
    identities.initialize()
    return canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, identities


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    start = participant.current_location_id
    if start is None:
        raise RuntimeError("proof Delver lacks location")
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
        raise RuntimeError("proof cache route was not found")
    path = []
    current: str | None = target_sector_id
    while current is not None:
        path.append(current)
        current = parent[current]
    return list(reversed(path))


def _event(lifecycle, descent, event_type: str, actors: list[str], *, danger: float = 0.0, data=None):
    payload = {"danger": danger, "state_changes": {"30_5_6_proof": event_type}}
    if data:
        payload.update(data)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.6 canonical proof source {event_type}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data=payload,
    )


def _register(media, exporter, descent, event):
    envelope = exporter.export_event(descent, event.id)
    media.register_envelope(envelope)
    return envelope


def _canonical_snapshot(canonical, descent) -> dict:
    ledger = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]
    return {
        "state": descent.model_dump(mode="json"),
        "fingerprint": descent.fingerprint(),
        "history": list(descent.history_event_ids),
        "ledger": ledger,
    }


def _same_canonical(left: dict, right: dict) -> bool:
    return (
        canonical_json(left["state"]) == canonical_json(right["state"])
        and left["fingerprint"] == right["fingerprint"]
        and left["history"] == right["history"]
        and left["ledger"] == right["ledger"]
    )


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    database_path = output.with_suffix(".sqlite3")
    if database_path.exists():
        database_path.unlink()
    database_url = f"sqlite:///{database_path.as_posix()}"

    canonical, descent, memory, lifecycle, exporter, media, detector, chronicle, identities = _stack(seed, database_url)

    loot = LootCacheRelicService(canonical)
    survival = ResourcesSurvivalService(canonical)
    cache = next(
        item
        for item in descent.modifiers[LOOT_METADATA_KEY]["caches"]
        if item["stratum_number"] == descent.current_floor
    )
    for sector_id in _route(descent, IDS[0], cache["sector_id"])[1:]:
        loot.commit_descender_position(descent, IDS[0], sector_id)
    survival.open_cache(descent, cache["cache_id"], IDS[0])
    relic_id = next(item["id"] for item in cache["blueprints"] if item["kind"] == "relic")
    loot.claim_ground_item(descent, relic_id, IDS[0])

    high = _event(
        lifecycle,
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        IDS[:2],
        danger=1.0,
        data={
            "item_id": relic_id,
            "social_facts": [
                {
                    "observer_descender_id": IDS[1],
                    "subject_descender_id": IDS[0],
                    "memory_type": "betrayed",
                }
            ],
        },
    )
    if not memory.process_event(descent, high).processed:
        raise RuntimeError("30.5.6 proof social memory processing failed")
    first_envelope = _register(media, exporter, descent, high)
    high_eval = detector.evaluate(first_envelope)
    if not high_eval.selected:
        raise RuntimeError("30.5.6 proof high-signal input did not become a highlight")
    chronicle.process(first_envelope)
    first_profile = chronicle.get_profile(descent.id, IDS[0])
    if first_profile is None or not first_profile.chapter_ids:
        raise RuntimeError("30.5.6 proof did not create media-relevant profile")
    if not any(item.item_id == relic_id for item in first_profile.notable_equipment):
        raise RuntimeError("30.5.6 proof initial profile lost Relic equipment context")

    before_first_identity = _canonical_snapshot(canonical, descent)
    first_state = identities.ensure_identity(first_profile)
    after_first_identity = _canonical_snapshot(canonical, descent)

    loot.drop_owned_item(descent, relic_id, IDS[0])
    update_event = _event(
        lifecycle,
        descent,
        "EQUIPMENT_REFERENCE_UPDATE",
        IDS[:1],
        data={"item_id": relic_id},
    )
    second_envelope = _register(media, exporter, descent, update_event)
    detector.evaluate(second_envelope)
    chronicle.process(second_envelope)
    second_profile = chronicle.get_profile(descent.id, IDS[0])
    if second_profile is None:
        raise RuntimeError("30.5.6 proof lost profile after equipment update")

    before_equipment_sync = _canonical_snapshot(canonical, descent)
    second_state = identities.ensure_identity(second_profile)
    after_equipment_sync = _canonical_snapshot(canonical, descent)
    if second_state.equipment_revision.source_envelope_id != second_envelope.envelope_id:
        raise RuntimeError("30.5.6 proof equipment revision did not follow canonical Ledger-prefix order")
    if second_state.equipment_revision.equipment:
        raise RuntimeError("30.5.6 proof dropped Relic remained in current equipment revision")

    before_version_switch = _canonical_snapshot(canonical, descent)
    third_state = identities.ensure_identity(
        second_profile,
        renderer_profile="capability:image_reference_conditioning_v2",
    )
    after_version_switch = _canonical_snapshot(canonical, descent)
    snapshot = identities.snapshot()
    repeated = identities.ensure_identity(
        second_profile,
        renderer_profile="capability:image_reference_conditioning_v2",
    )
    snapshot_after_repeat = identities.snapshot()

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened_chronicle = DelverChronicleProfileService(reopened_media, highlights=reopened_detector)
    reopened_chronicle.initialize()
    reopened_identities = PresentationIdentityService(reopened_media, chronicle=reopened_chronicle)
    reopened_identities.initialize()
    reopened_profile = reopened_chronicle.get_profile(descent.id, IDS[0])
    if reopened_profile is None:
        raise RuntimeError("30.5.6 proof restart lost Delver profile")
    reopened_snapshot = reopened_identities.snapshot()
    reopened_repeat = reopened_identities.ensure_identity(
        reopened_profile,
        renderer_profile="capability:image_reference_conditioning_v2",
    )
    reopened_after_repeat = reopened_identities.snapshot()

    first_identity_revisions = reopened_identities.list_equipment_revisions(identity_id=first_state.identity.identity_id)
    all_identities = reopened_identities.list_identities(profile_id=first_profile.profile_id)
    binding = reopened_identities.get_binding(first_profile.profile_id)
    if binding is None:
        raise RuntimeError("30.5.6 proof restart lost active identity binding")

    media_snapshot = reopened_media.snapshot()
    all_slots = [slot for identity in all_identities for slot in identity.reference_slots]
    all_equipment_slots = [item.reference_slot for item in reopened_identities.list_equipment_revisions()]

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
            "canonical_identity_fields_added": snapshot["canonical_identity_fields_added"],
            "generated_visuals_used": snapshot["generated_visuals_used"],
            "provider_invocation_used": snapshot["provider_invocation_used"],
            "generation_jobs_created": snapshot["generation_jobs_created"],
            "unreal_dependency": snapshot["unreal_dependency"],
            "cloud_api_required": snapshot["cloud_api_required"],
            "paid_provider_required": snapshot["paid_provider_required"],
        },
        "canonical": {
            "first_identity_step_unchanged": _same_canonical(before_first_identity, after_first_identity),
            "equipment_sync_step_unchanged": _same_canonical(before_equipment_sync, after_equipment_sync),
            "version_switch_step_unchanged": _same_canonical(before_version_switch, after_version_switch),
            "final_fingerprint": descent.fingerprint(),
            "final_state_digest": payload_digest(descent.model_dump(mode="json")),
            "final_ledger_digest": payload_digest([item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]),
        },
        "identity": {
            "first_identity_id": first_state.identity.identity_id,
            "first_version": first_state.identity.identity_version,
            "first_seed": first_state.identity.deterministic_seed,
            "second_same_identity": second_state.identity.identity_id == first_state.identity.identity_id,
            "second_version": second_state.identity.identity_version,
            "renderer_switch_identity_id": third_state.identity.identity_id,
            "renderer_switch_version": third_state.identity.identity_version,
            "renderer_switch_seed": third_state.identity.deterministic_seed,
            "identity_count": len(all_identities),
            "active_identity_id": binding.active_identity_id,
            "identity_version_count": binding.identity_version_count,
            "static_slot_count_per_identity": [len(item.reference_slots) for item in all_identities],
            "all_static_slots_pending": all(not slot.generated and slot.status.value == "pending_generation" for slot in all_slots),
            "all_traits_empty": all(not item.presentation_traits for item in all_identities),
        },
        "equipment": {
            "relic_id": relic_id,
            "first_revision_id": first_state.equipment_revision.revision_id,
            "second_revision_id": second_state.equipment_revision.revision_id,
            "changed_revision": first_state.equipment_revision.revision_id != second_state.equipment_revision.revision_id,
            "identity_unchanged_on_equipment_change": first_state.identity.identity_id == second_state.identity.identity_id,
            "first_identity_revision_count": len(first_identity_revisions),
            "first_revision_has_relic": any(item.item_id == relic_id for item in first_state.equipment_revision.equipment),
            "second_revision_empty": not second_state.equipment_revision.equipment,
            "second_revision_source_envelope_id": second_state.equipment_revision.source_envelope_id,
            "second_revision_uses_latest_ledger_prefix": second_state.equipment_revision.source_envelope_id == second_envelope.envelope_id,
            "all_equipment_slots_pending": all(not slot.generated and slot.status.value == "pending_generation" for slot in all_equipment_slots),
            "active_equipment_revision_id": binding.current_equipment_revision_id,
        },
        "media": {
            "snapshot_digest": snapshot["digest"],
            "identity_digest": snapshot["identity_digest"],
            "equipment_revision_digest": snapshot["equipment_revision_digest"],
            "binding_digest": snapshot["binding_digest"],
            "snapshot_equal_after_repeat": snapshot_after_repeat == snapshot,
            "snapshot_equal_after_reopen": reopened_snapshot == snapshot,
            "snapshot_equal_after_reopen_repeat": reopened_after_repeat == snapshot,
            "repeat_state_equal": repeated == third_state,
            "reopen_repeat_state_equal": reopened_repeat == third_state,
            "media_job_count": len(reopened_media.list_jobs()),
            "provider_execution_count": len(media_snapshot["provider_executions"]),
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-6-presentation-identity-proof")
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed)
    print(
        json.dumps(
            {
                "digest": proof["digest"],
                "identities": proof["identity"]["identity_count"],
                "equipment_changed": proof["equipment"]["changed_revision"],
                "version": proof["identity"]["renderer_switch_version"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
