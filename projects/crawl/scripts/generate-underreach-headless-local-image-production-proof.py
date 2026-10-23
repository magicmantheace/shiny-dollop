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
from livingworld.underreach_headless_local_image_production import (
    DeterministicLocalPngProvider,
    HeadlessLocalImageProductionService,
    ImageProductionPolicy,
)
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_loot_cache_relic import METADATA_KEY as LOOT_METADATA_KEY, LootCacheRelicService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import (
    MediaPersistence,
    MediaProviderRouter,
    ProviderDescriptor,
    ProviderKind,
    ProviderPolicy,
    ProviderRequest,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_presentation_identity import PresentationIdentityService, ReferenceKind
from livingworld.underreach_resources_survival import ResourcesSurvivalService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


PROOF_PROTOCOL = "underreach.headless-local-image-production-proof.v1"
IDS = [f"descender_{index:03d}" for index in range(8)]


def _route(descent, descender_id: str, target_sector_id: str) -> list[str]:
    participant = descent.participants[descender_id]
    floor = descent.floors[participant.current_floor]
    start = participant.current_location_id
    if start is None:
        raise RuntimeError("30.5.7 proof Delver lacks canonical location")
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
        raise RuntimeError("30.5.7 proof cache route was not found")
    path: list[str] = []
    current: str | None = target_sector_id
    while current is not None:
        path.append(current)
        current = parent[current]
    return list(reversed(path))


def _event(lifecycle, descent, event_type: str, actors: list[str], *, danger: float = 0.0, data=None):
    payload = {"danger": danger, "state_changes": {"30_5_7_proof": event_type}}
    if data:
        payload.update(data)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.7 canonical proof source {event_type}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data=payload,
    )


def _canonical_snapshot(canonical, descent) -> dict:
    return {
        "state": descent.model_dump(mode="json"),
        "fingerprint": descent.fingerprint(),
        "history": list(descent.history_event_ids),
        "ledger": [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)],
    }


def _same_canonical(left: dict, right: dict) -> bool:
    return (
        canonical_json(left["state"]) == canonical_json(right["state"])
        and left["fingerprint"] == right["fingerprint"]
        and left["history"] == right["history"]
        and left["ledger"] == right["ledger"]
    )


def _build(seed: str, database_url: str):
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

    loot = LootCacheRelicService(canonical)
    survival = ResourcesSurvivalService(canonical)
    cache = next(
        item
        for item in descent.modifiers[LOOT_METADATA_KEY]["caches"]
        if item["stratum_number"] == descent.current_floor
    )
    for sector_id in _route(descent, IDS[0], cache["sector_id"])[1:]:
        survival.commit_descender_position(descent, IDS[0], sector_id)
    survival.open_cache(descent, cache["cache_id"], IDS[0])
    relic_id = next(item["id"] for item in cache["blueprints"] if item["kind"] == "relic")
    loot.claim_ground_item(descent, relic_id, IDS[0])

    prior = _event(lifecycle, descent, "BETRAYAL", IDS[:2], danger=0.6)
    if not memory.process_event(descent, prior).processed:
        raise RuntimeError("30.5.7 proof prior social-memory processing failed")
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
        raise RuntimeError("30.5.7 proof high-signal social-memory processing failed")
    envelope = exporter.export_event(descent, high.id)
    media.register_envelope(envelope)
    evaluation = detector.evaluate(envelope)
    if not evaluation.selected:
        raise RuntimeError("30.5.7 proof high-signal event did not become a highlight")
    chronicle.process(envelope)
    profile = chronicle.get_profile(descent.id, IDS[0])
    if profile is None or not profile.chapter_ids:
        raise RuntimeError("30.5.7 proof did not create media-relevant profile")
    identity_state = identities.ensure_identity(profile)
    chapter = next(
        item
        for item in chronicle.list_chapters(crawl_id=descent.id, delver_id=IDS[0])
        if item.chapter_id in profile.chapter_ids
    )
    return canonical, descent, media, detector, chronicle, identities, profile, identity_state, chapter, relic_id


def _routing_probes() -> dict:
    local_router = MediaProviderRouter()
    local_11 = ProviderDescriptor(
        provider_id="proof_local_11gb",
        kind=ProviderKind.IMAGE,
        local=True,
        paid=False,
        capability_flags=("headless_image", "png_output"),
        deterministic_seed=True,
        max_width=1024,
        max_height=1024,
        estimated_vram_mb=11_000,
        quality_rank=10,
    )
    local_16 = ProviderDescriptor(
        provider_id="proof_local_16gb",
        kind=ProviderKind.IMAGE,
        local=True,
        paid=False,
        capability_flags=("headless_image", "png_output"),
        deterministic_seed=True,
        max_width=1024,
        max_height=1024,
        estimated_vram_mb=16_000,
        quality_rank=100,
    )
    paid = ProviderDescriptor(
        provider_id="proof_remote_paid",
        kind=ProviderKind.IMAGE,
        local=False,
        paid=True,
        capability_flags=("headless_image", "png_output"),
        deterministic_seed=True,
        max_width=1024,
        max_height=1024,
        estimated_cost_microusd=1_000,
        quality_rank=90,
    )
    local_router.register(local_11)
    local_router.register(local_16)

    local_request = ProviderRequest(
        kind=ProviderKind.IMAGE,
        required_flags=("headless_image", "png_output"),
        local_required=True,
        deterministic_seed_required=True,
        min_width=96,
        min_height=96,
        max_vram_mb=12 * 1024,
    )
    local_selection = local_router.select(
        local_request,
        ProviderPolicy(local_only=True, cloud_allowed=False, allow_paid=False, max_vram_mb=12 * 1024),
    )

    paid_request = ProviderRequest(
        kind=ProviderKind.IMAGE,
        required_flags=("headless_image", "png_output"),
        local_required=False,
        paid_allowed=True,
        explicit_paid_authorization=True,
        deterministic_seed_required=True,
        min_width=96,
        min_height=96,
        max_vram_mb=12 * 1024,
    )
    paid_blocked_router = MediaProviderRouter()
    paid_blocked_router.register(paid)
    paid_blocked = paid_blocked_router.select(
        paid_request,
        ProviderPolicy(
            local_only=False,
            cloud_allowed=True,
            allow_paid=False,
            daily_paid_budget_microusd=0,
            max_vram_mb=12 * 1024,
        ),
    )
    paid_allowed_router = MediaProviderRouter()
    paid_allowed_router.register(paid)
    paid_selected = paid_allowed_router.select(
        paid_request,
        ProviderPolicy(
            local_only=False,
            cloud_allowed=True,
            allow_paid=True,
            require_explicit_paid_policy=True,
            daily_paid_budget_microusd=5_000,
            max_vram_mb=12 * 1024,
        ),
    )
    return {
        "local_under_12gb_provider": local_selection.provider_id,
        "oversized_16gb_excluded": local_selection.provider_id == local_11.provider_id,
        "paid_blocked_without_global_permission": not paid_blocked.selected,
        "paid_selected_with_all_gates": paid_selected.provider_id == paid.provider_id,
    }


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    database_path = output.with_suffix(".sqlite3")
    if database_path.exists():
        database_path.unlink()
    database_url = f"sqlite:///{database_path.as_posix()}"
    output_root = output.parent / "image-output"

    canonical, descent, media, detector, chronicle, identities, profile, identity_state, chapter, relic_id = _build(seed, database_url)
    canonical_before = _canonical_snapshot(canonical, descent)

    service = HeadlessLocalImageProductionService(
        media,
        identities=identities,
        providers=[DeterministicLocalPngProvider()],
        output_root=output_root,
        policy=ImageProductionPolicy(default_width=96, default_height=96, scene_width=96, scene_height=128),
    )
    service.initialize()

    portrait_spec = service.plan_reference(profile, ReferenceKind.PORTRAIT)
    equipment_spec = service.plan_reference(profile, ReferenceKind.CURRENT_EQUIPMENT)
    portrait_job = service.enqueue(portrait_spec, priority=120)
    portrait = service.run_next()
    equipment_job = service.enqueue(equipment_spec, priority=110)
    equipment = service.run_next()
    if portrait is None or equipment is None or portrait.artifact_id is None:
        raise RuntimeError("30.5.7 proof failed to complete required reference images")

    scene_spec = service.plan_scene(
        profile,
        chapter,
        reference_artifact_ids=(portrait.artifact_id,),
    )
    scene_job = service.enqueue(scene_spec, priority=100)
    scene = service.run_next()
    if scene is None:
        raise RuntimeError("30.5.7 proof failed to complete Chronicle scene still")

    restart_job = service.enqueue_reference(profile, ReferenceKind.FACE_REFERENCE, priority=90)
    crash_lease = media.claim_next("30-5-7-proof-crashed-worker")
    if crash_lease is None or crash_lease.job.job_id != restart_job.job_id:
        raise RuntimeError("30.5.7 proof failed to claim restart probe job")

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    recovered_count = reopened_media.recover_interrupted_jobs()
    reopened_detector = HighlightStoryArcService(reopened_media)
    reopened_detector.initialize()
    reopened_chronicle = DelverChronicleProfileService(reopened_media, highlights=reopened_detector)
    reopened_chronicle.initialize()
    reopened_identities = PresentationIdentityService(reopened_media, chronicle=reopened_chronicle)
    reopened_identities.initialize()
    reopened_service = HeadlessLocalImageProductionService(
        reopened_media,
        identities=reopened_identities,
        providers=[DeterministicLocalPngProvider()],
        output_root=output_root,
        policy=ImageProductionPolicy(default_width=96, default_height=96, scene_width=96, scene_height=128),
    )
    reopened_service.initialize()
    recovered_result = reopened_service.run_next()
    if recovered_result is None:
        raise RuntimeError("30.5.7 proof restart recovery did not finish image job")

    snapshot_before_repeat = reopened_service.snapshot()
    reopened_profile = reopened_chronicle.get_profile(descent.id, IDS[0])
    if reopened_profile is None:
        raise RuntimeError("30.5.7 proof restart lost profile")
    repeat_job = reopened_service.enqueue_reference(reopened_profile, ReferenceKind.PORTRAIT, priority=120)
    snapshot_after_repeat = reopened_service.snapshot()

    media_snapshot = reopened_media.snapshot()
    image_artifacts = [item for item in media_snapshot["artifacts"] if item["artifact_kind"] == "image/png"]
    sidecars = [item for item in media_snapshot["artifacts"] if item["artifact_kind"] == "application/json"]
    output_records = []
    for artifact in image_artifacts:
        path = output_root / artifact["uri"]
        output_records.append(
            {
                "artifact_id": artifact["artifact_id"],
                "uri": artifact["uri"],
                "digest": artifact["digest"],
                "exists": path.exists(),
                "png_signature": path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") if path.exists() else False,
            }
        )

    final_job = reopened_media.get_job(restart_job.job_id)
    canonical_after = _canonical_snapshot(canonical, descent)
    body = {
        "protocol": PROOF_PROTOCOL,
        "slice_protocol": snapshot_after_repeat["protocol"],
        "implementation_version": snapshot_after_repeat["implementation_version"],
        "phase": snapshot_after_repeat["phase"],
        "seed": seed,
        "authority_contract": {
            "authoritative": snapshot_after_repeat["authoritative"],
            "canonical_owner": snapshot_after_repeat["canonical_owner"],
            "presentation_can_mutate_simulation": snapshot_after_repeat["presentation_can_mutate_simulation"],
            "unreal_dependency": snapshot_after_repeat["unreal_dependency"],
            "required_cloud_api": snapshot_after_repeat["required_cloud_api"],
            "required_paid_provider": snapshot_after_repeat["required_paid_provider"],
        },
        "canonical": {
            "unchanged_during_image_production": _same_canonical(canonical_before, canonical_after),
            "fingerprint": descent.fingerprint(),
            "state_digest": payload_digest(descent.model_dump(mode="json")),
            "ledger_digest": payload_digest([item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]),
        },
        "identity": {
            "profile_id": profile.profile_id,
            "identity_id": identity_state.identity.identity_id,
            "identity_version": identity_state.identity.identity_version,
            "equipment_revision_id": identity_state.equipment_revision.revision_id,
            "relic_id": relic_id,
            "portrait_static_not_equipment_coupled": portrait_spec.equipment_revision_id is None,
            "equipment_spec_has_revision": equipment_spec.equipment_revision_id == identity_state.equipment_revision.revision_id,
        },
        "production": {
            "portrait_job_id": portrait_job.job_id,
            "equipment_job_id": equipment_job.job_id,
            "scene_job_id": scene_job.job_id,
            "restart_job_id": restart_job.job_id,
            "repeat_portrait_reused_job": repeat_job.job_id == portrait_job.job_id,
            "snapshot_equal_after_completed_reenqueue": snapshot_before_repeat == snapshot_after_repeat,
            "job_count": snapshot_after_repeat["job_count"],
            "artifact_count": snapshot_after_repeat["artifact_count"],
            "provider_execution_count": snapshot_after_repeat["provider_execution_count"],
            "image_artifact_count": len(image_artifacts),
            "sidecar_artifact_count": len(sidecars),
            "all_image_files_exist": all(item["exists"] for item in output_records),
            "all_image_files_are_png": all(item["png_signature"] for item in output_records),
            "output_records": output_records,
            "scene_uses_reference_artifact": portrait.artifact_id in scene_spec.reference_artifact_ids,
            "scene_has_chapter_provenance": scene_spec.chapter_id == chapter.chapter_id,
            "local_provider_only": all(
                item["provider_id"] == "local_deterministic_png"
                for item in snapshot_after_repeat["provider_executions"]
            ),
        },
        "restart": {
            "recovered_count": recovered_count,
            "same_job_id": recovered_result.job_id == restart_job.job_id,
            "attempt_count": final_job.attempt_count if final_job is not None else None,
            "completed": final_job.status.value == "completed" if final_job is not None else False,
        },
        "routing": _routing_probes(),
        "media": {
            "snapshot_digest": snapshot_after_repeat["digest"],
            "job_digest": snapshot_after_repeat["job_digest"],
            "artifact_digest": snapshot_after_repeat["artifact_digest"],
            "provider_execution_digest": snapshot_after_repeat["provider_execution_digest"],
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-7-headless-local-image-production-proof")
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed)
    print(
        json.dumps(
            {
                "digest": proof["digest"],
                "jobs": proof["production"]["job_count"],
                "images": proof["production"]["image_artifact_count"],
                "executions": proof["production"]["provider_execution_count"],
                "restart_attempts": proof["restart"]["attempt_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())