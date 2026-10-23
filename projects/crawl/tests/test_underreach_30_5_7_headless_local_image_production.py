from __future__ import annotations

import json
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_delver_chronicle_profile import DelverChronicleProfileService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_headless_local_image_production import (
    DeterministicLocalPngProvider,
    HeadlessLocalImageProductionService,
    ImageProductionPolicy,
    ImagePurpose,
)
from livingworld.underreach_highlight_story_arc import HighlightStoryArcService
from livingworld.underreach_loot_cache_relic import METADATA_KEY as LOOT_METADATA_KEY, LootCacheRelicService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import (
    JobStatus,
    MediaPersistence,
    ProviderDescriptor,
    ProviderKind,
    ProviderPolicy,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_presentation_identity import PresentationIdentityService, ReferenceKind
from livingworld.underreach_resources_survival import ResourcesSurvivalService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


IDS = [f"descender_{index:03d}" for index in range(8)]


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
    path: list[str] = []
    current: str | None = target_sector_id
    while current is not None:
        path.append(current)
        current = parent[current]
    return list(reversed(path))


def _event(lifecycle, descent, event_type: str, actors: list[str], *, danger: float = 0.0, data=None):
    payload = {"danger": danger, "state_changes": {"30_5_7_test": event_type}}
    if data:
        payload.update(data)
    return lifecycle.record_event(
        descent,
        event_type,
        f"30.5.7 canonical source {event_type}.",
        actor_ids=actors,
        location_id=descent.participants[actors[0]].current_location_id if actors else None,
        data=payload,
    )


def _register(media, exporter, descent, event):
    envelope = exporter.export_event(descent, event.id)
    media.register_envelope(envelope)
    return envelope


def _betrayal_fact():
    return {
        "social_facts": [
            {
                "observer_descender_id": IDS[1],
                "subject_descender_id": IDS[0],
                "memory_type": "betrayed",
            }
        ]
    }


def _claim_relic(canonical, descent, delver_id: str) -> tuple[LootCacheRelicService, str]:
    loot = LootCacheRelicService(canonical)
    survival = ResourcesSurvivalService(canonical)
    cache = next(
        item
        for item in descent.modifiers[LOOT_METADATA_KEY]["caches"]
        if item["stratum_number"] == descent.current_floor
    )
    for sector_id in _route(descent, delver_id, cache["sector_id"])[1:]:
        survival.commit_descender_position(descent, delver_id, sector_id)
    survival.open_cache(descent, cache["cache_id"], delver_id)
    relic_id = next(item["id"] for item in cache["blueprints"] if item["kind"] == "relic")
    loot.claim_ground_item(descent, relic_id, delver_id)
    return loot, relic_id


def _stack(
    *,
    seed: str,
    database_url: str = "sqlite://",
    with_relic: bool = False,
):
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

    loot = None
    relic_id = None
    if with_relic:
        loot, relic_id = _claim_relic(canonical, descent, IDS[0])

    prior = _event(lifecycle, descent, "BETRAYAL", IDS[:2], danger=0.6)
    assert memory.process_event(descent, prior).processed
    data = _betrayal_fact()
    if relic_id is not None:
        data["item_id"] = relic_id
    high = _event(
        lifecycle,
        descent,
        "NEAR_DEATH_BETRAYAL_RELIC_COMEBACK",
        IDS[:2],
        danger=1.0,
        data=data,
    )
    assert memory.process_event(descent, high).processed
    envelope = _register(media, exporter, descent, high)
    evaluation = detector.evaluate(envelope)
    assert evaluation.selected
    chronicle.process(envelope)
    profile = chronicle.get_profile(descent.id, IDS[0])
    assert profile is not None and profile.chapter_ids
    identity_state = identities.ensure_identity(profile)
    chapters = chronicle.list_chapters(crawl_id=descent.id, delver_id=IDS[0])
    chapter = next(item for item in chapters if item.chapter_id in profile.chapter_ids)
    return {
        "canonical": canonical,
        "descent": descent,
        "memory": memory,
        "lifecycle": lifecycle,
        "exporter": exporter,
        "media": media,
        "detector": detector,
        "chronicle": chronicle,
        "identities": identities,
        "profile": profile,
        "identity_state": identity_state,
        "chapter": chapter,
        "loot": loot,
        "relic_id": relic_id,
    }


def _service(stack, output_root: Path, *, providers=None, policy=None, provider_policy=None):
    value = HeadlessLocalImageProductionService(
        stack["media"],
        identities=stack["identities"],
        providers=providers or [DeterministicLocalPngProvider()],
        output_root=output_root,
        policy=policy,
        provider_policy=provider_policy,
    )
    value.initialize()
    return value


def _canonical_snapshot(stack) -> tuple[dict, str, list[dict]]:
    descent = stack["descent"]
    canonical = stack["canonical"]
    return (
        descent.model_dump(mode="json"),
        descent.fingerprint(),
        [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)],
    )


def test_static_reference_spec_is_deterministic_and_not_equipment_coupled(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-7-static")
    service = _service(stack, tmp_path)

    first = service.plan_reference(stack["profile"], ReferenceKind.PORTRAIT, width=96, height=96)
    second = service.plan_reference(stack["profile"], ReferenceKind.PORTRAIT, width=96, height=96)

    assert first == second
    assert first.purpose == ImagePurpose.IDENTITY_REFERENCE
    assert first.equipment_revision_id is None
    assert first.reference_kind == ReferenceKind.PORTRAIT
    assert first.provider_request.local_required is True
    assert first.provider_request.paid_allowed is False
    assert first.provider_request.max_vram_mb == 12 * 1024


def test_local_provider_writes_real_png_sidecar_and_provenance_without_canonical_mutation(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-7-local")
    service = _service(stack, tmp_path)
    before = _canonical_snapshot(stack)

    job = service.enqueue_reference(stack["profile"], ReferenceKind.PORTRAIT, width=96, height=96)
    assert job.status == JobStatus.QUEUED
    assert job.selected_provider_id == "local_deterministic_png"
    result = service.run_next()

    assert result is not None and result.status == JobStatus.COMPLETED
    assert result.provider_id == "local_deterministic_png"
    assert result.output_uri is not None and result.sidecar_uri is not None
    image_path = tmp_path / result.output_uri
    sidecar_path = tmp_path / result.sidecar_uri
    assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))
    assert sidecar["output_sha256"] == result.output_digest
    assert sidecar["canonical_authority"] is False
    assert sidecar["presentation_can_mutate_simulation"] is False
    snapshot = service.snapshot()
    assert snapshot["artifact_count"] == 2
    assert snapshot["provider_execution_count"] == 1
    assert _canonical_snapshot(stack) == before


def test_completed_reference_reenqueue_reuses_same_durable_job_and_artifacts(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-7-reuse")
    service = _service(stack, tmp_path)
    first_job = service.enqueue_reference(stack["profile"], ReferenceKind.FACE_REFERENCE, width=96, height=96)
    first_result = service.run_next()
    assert first_result is not None and first_result.status == JobStatus.COMPLETED
    before = service.snapshot()

    second_job = service.enqueue_reference(stack["profile"], ReferenceKind.FACE_REFERENCE, width=96, height=96)
    after_enqueue = service.snapshot()

    assert second_job.job_id == first_job.job_id
    assert second_job.status == JobStatus.COMPLETED
    assert after_enqueue == before
    assert service.run_next() is None


def test_same_identity_equipment_change_only_changes_equipment_and_scene_specs(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-7-equipment", with_relic=True)
    service = _service(stack, tmp_path)
    profile = stack["profile"]
    relic_id = stack["relic_id"]
    loot = stack["loot"]
    assert relic_id is not None and loot is not None

    portrait_before = service.plan_reference(profile, ReferenceKind.PORTRAIT, width=96, height=96)
    equipment_before = service.plan_reference(profile, ReferenceKind.CURRENT_EQUIPMENT, width=96, height=96)

    loot.drop_owned_item(stack["descent"], relic_id, IDS[0])
    update = _event(
        stack["lifecycle"],
        stack["descent"],
        "EQUIPMENT_REFERENCE_UPDATE",
        IDS[:1],
        data={"item_id": relic_id},
    )
    update_envelope = _register(stack["media"], stack["exporter"], stack["descent"], update)
    stack["detector"].evaluate(update_envelope)
    stack["chronicle"].process(update_envelope)
    updated_profile = stack["chronicle"].get_profile(stack["descent"].id, IDS[0])
    assert updated_profile is not None
    updated_identity = stack["identities"].ensure_identity(updated_profile)
    assert updated_identity.identity.identity_id == stack["identity_state"].identity.identity_id

    portrait_after = service.plan_reference(updated_profile, ReferenceKind.PORTRAIT, width=96, height=96)
    equipment_after = service.plan_reference(updated_profile, ReferenceKind.CURRENT_EQUIPMENT, width=96, height=96)

    assert portrait_after.spec_id == portrait_before.spec_id
    assert portrait_after.digest == portrait_before.digest
    assert equipment_after.spec_id != equipment_before.spec_id
    assert equipment_after.equipment_revision_id != equipment_before.equipment_revision_id


def test_router_enforces_12gb_vram_bound_before_quality_rank(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-7-vram")
    good = DeterministicLocalPngProvider(
        ProviderDescriptor(
            provider_id="local_11gb",
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
    )
    too_large = DeterministicLocalPngProvider(
        ProviderDescriptor(
            provider_id="local_16gb",
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
    )
    service = _service(stack, tmp_path, providers=[too_large, good])

    job = service.enqueue_reference(stack["profile"], ReferenceKind.THREE_QUARTER, width=96, height=96)

    assert job.selected_provider_id == "local_11gb"


def test_paid_remote_provider_is_held_by_default_and_requires_all_explicit_gates(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-7-paid")
    remote = DeterministicLocalPngProvider(
        ProviderDescriptor(
            provider_id="remote_paid_image",
            kind=ProviderKind.IMAGE,
            local=False,
            paid=True,
            capability_flags=("headless_image", "png_output"),
            deterministic_seed=True,
            max_width=1024,
            max_height=1024,
            estimated_cost_microusd=1_000,
            quality_rank=80,
        )
    )
    blocked = _service(
        stack,
        tmp_path / "blocked",
        providers=[remote],
        policy=ImageProductionPolicy(local_required=False, paid_allowed=False),
        provider_policy=ProviderPolicy(
            local_only=False,
            cloud_allowed=True,
            allow_paid=False,
            daily_paid_budget_microusd=0,
            max_vram_mb=12 * 1024,
        ),
    )
    blocked_job = blocked.enqueue_reference(stack["profile"], ReferenceKind.FULL_BODY_FRONT, width=96, height=96)
    assert blocked_job.status == JobStatus.HELD
    assert blocked_job.selected_provider_id is None
    assert blocked.snapshot()["provider_execution_count"] == 0

    allowed = _service(
        stack,
        tmp_path / "allowed",
        providers=[remote],
        policy=ImageProductionPolicy(
            local_required=False,
            paid_allowed=True,
            explicit_paid_authorization=True,
        ),
        provider_policy=ProviderPolicy(
            local_only=False,
            cloud_allowed=True,
            allow_paid=True,
            require_explicit_paid_policy=True,
            daily_paid_budget_microusd=5_000,
            max_vram_mb=12 * 1024,
        ),
    )
    allowed_job = allowed.enqueue_reference(stack["profile"], ReferenceKind.FULL_BODY_FRONT, width=96, height=96)
    assert allowed_job.status == JobStatus.QUEUED
    assert allowed_job.selected_provider_id == "remote_paid_image"


def test_file_backed_restart_recovers_same_job_without_duplicate_export(tmp_path: Path) -> None:
    database_url = f"sqlite:///{(tmp_path / 'media.sqlite3').as_posix()}"
    stack = _stack(seed="30-5-7-restart", database_url=database_url)
    output_root = tmp_path / "output"
    service = _service(stack, output_root)
    job = service.enqueue_reference(stack["profile"], ReferenceKind.FULL_BODY_SIDE, width=96, height=96)
    lease = stack["media"].claim_next("crashed-image-worker")
    assert lease is not None and lease.job.job_id == job.job_id

    reopened_media = MediaPersistence(database_url)
    reopened_media.initialize()
    assert reopened_media.recover_interrupted_jobs() == 1
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
    )
    reopened_service.initialize()

    result = reopened_service.run_next()
    final_job = reopened_media.get_job(job.job_id)

    assert result is not None and result.status == JobStatus.COMPLETED
    assert final_job is not None and final_job.job_id == job.job_id
    assert final_job.attempt_count == 2
    assert reopened_service.snapshot()["artifact_count"] == 2


def test_scene_still_uses_persisted_chapter_and_generated_reference_provenance(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-7-scene")
    service = _service(stack, tmp_path)
    before = _canonical_snapshot(stack)

    portrait_job = service.enqueue_reference(stack["profile"], ReferenceKind.COMBAT_REFERENCE, width=96, height=96)
    portrait = service.run_next()
    assert portrait is not None and portrait.status == JobStatus.COMPLETED and portrait.artifact_id is not None
    scene_spec = service.plan_scene(
        stack["profile"],
        stack["chapter"],
        reference_artifact_ids=(portrait.artifact_id,),
        width=96,
        height=128,
    )
    assert scene_spec.purpose == ImagePurpose.SCENE_STILL
    assert scene_spec.chapter_id == stack["chapter"].chapter_id
    assert scene_spec.reference_artifact_ids == (portrait.artifact_id,)
    scene_job = service.enqueue(scene_spec)
    assert scene_job.job_id != portrait_job.job_id
    scene = service.run_next()

    assert scene is not None and scene.status == JobStatus.COMPLETED
    assert service.snapshot()["artifact_count"] == 4
    assert _canonical_snapshot(stack) == before


def test_provider_failure_retries_then_fails_without_artifact_or_canonical_mutation(tmp_path: Path) -> None:
    stack = _stack(seed="30-5-7-failure")
    descriptor = ProviderDescriptor(
        provider_id="local_failing_image",
        kind=ProviderKind.IMAGE,
        local=True,
        paid=False,
        capability_flags=("headless_image", "png_output"),
        deterministic_seed=True,
        max_width=1024,
        max_height=1024,
        estimated_vram_mb=1_000,
        quality_rank=5,
    )

    class FailingProvider:
        @property
        def descriptor(self):
            return descriptor

        def render(self, request):
            raise RuntimeError("injected local image failure")

    service = _service(
        stack,
        tmp_path,
        providers=[FailingProvider()],
        policy=ImageProductionPolicy(max_attempts=2),
    )
    before = _canonical_snapshot(stack)
    service.enqueue_reference(stack["profile"], ReferenceKind.PORTRAIT, width=96, height=96)

    first = service.run_next()
    second = service.run_next()

    assert first is not None and first.status == JobStatus.RETRY
    assert second is not None and second.status == JobStatus.FAILED
    snapshot = service.snapshot()
    assert snapshot["artifact_count"] == 0
    assert snapshot["provider_execution_count"] == 2
    assert _canonical_snapshot(stack) == before
