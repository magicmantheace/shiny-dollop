from __future__ import annotations

from sqlalchemy import inspect

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_media_foundation import (
    JobStatus,
    MediaPersistence,
    MediaProviderRouter,
    ProviderDescriptor,
    ProviderKind,
    ProviderPolicy,
    ProviderRequest,
)
from livingworld.underreach_parties_alliances_leadership import PartiesAlliancesLeadershipService
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


def _canonical_stack(seed: str = "30-5-2-media-foundation"):
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
    event = CrawlLifecycleService(persistence).record_event(
        descent,
        "RESCUE",
        "30.5.2 canonical media source event.",
        actor_ids=ids[:2],
        location_id=descent.participants[ids[0]].current_location_id,
        data={"danger": 0.82, "state_changes": {"30_5_2_proof": True}},
    )
    envelope = CanonicalMediaEventExporter(persistence).export_event(descent, event.id)
    return persistence, descent, envelope


def _local_narrative(provider_id: str = "local_qwen") -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=provider_id,
        kind=ProviderKind.NARRATIVE,
        local=True,
        paid=False,
        deterministic_seed=True,
        capability_flags=("structured_output",),
        estimated_vram_mb=7000,
        estimated_runtime_seconds=15.0,
        quality_rank=72,
        quality_profile="local_balanced",
    )


def _paid_narrative(provider_id: str = "paid_narrative_api") -> ProviderDescriptor:
    return ProviderDescriptor(
        provider_id=provider_id,
        kind=ProviderKind.NARRATIVE,
        local=False,
        paid=True,
        deterministic_seed=True,
        capability_flags=("structured_output",),
        estimated_runtime_seconds=2.0,
        estimated_cost_microusd=250000,
        quality_rank=95,
        quality_profile="premium",
    )


def test_media_database_is_separate_and_envelope_registration_is_idempotent() -> None:
    canonical, descent, envelope = _canonical_stack(seed="30-5-2-separate")
    before_state = descent.model_dump(mode="json")
    before_events = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    media = MediaPersistence("sqlite://")
    media.initialize()
    first = media.register_envelope(envelope)
    second = media.register_envelope(envelope)

    assert first == second == envelope
    assert len(media.snapshot()["envelopes"]) == 1
    assert descent.model_dump(mode="json") == before_state
    assert [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)] == before_events
    canonical_tables = set(inspect(canonical.engine).get_table_names())
    media_tables = set(inspect(media.engine).get_table_names())
    assert canonical_tables.isdisjoint(media_tables)
    assert media_tables == {
        "media_artifacts",
        "media_envelopes",
        "media_job_attempts",
        "media_job_dependencies",
        "media_jobs",
        "media_provider_executions",
    }


def test_job_enqueue_is_idempotent_and_dependency_gated() -> None:
    _, _, envelope = _canonical_stack(seed="30-5-2-idempotent")
    media = MediaPersistence("sqlite://")
    media.initialize()
    media.register_envelope(envelope)

    first = media.enqueue_job(job_type="chronicle", payload={"chapter": 1}, envelope_id=envelope.envelope_id)
    duplicate = media.enqueue_job(job_type="chronicle", payload={"chapter": 1}, envelope_id=envelope.envelope_id)
    dependent = media.enqueue_job(
        job_type="verification",
        payload={"chapter_job_id": first.job_id},
        envelope_id=envelope.envelope_id,
        dependencies=[first.job_id],
        priority=500,
    )

    assert first == duplicate
    assert len(media.list_jobs()) == 2
    lease = media.claim_next("worker_a")
    assert lease is not None and lease.job.job_id == first.job_id
    media.complete_job(first.job_id)
    next_lease = media.claim_next("worker_b")
    assert next_lease is not None and next_lease.job.job_id == dependent.job_id


def test_interrupted_job_recovers_after_sqlite_reopen_without_duplication(tmp_path) -> None:
    _, _, envelope = _canonical_stack(seed="30-5-2-restart")
    database_url = f"sqlite:///{(tmp_path / 'media.sqlite3').as_posix()}"
    media = MediaPersistence(database_url)
    media.initialize()
    media.register_envelope(envelope)
    job = media.enqueue_job(
        job_type="chronicle",
        payload={"chapter": "restart-proof"},
        envelope_id=envelope.envelope_id,
        max_attempts=4,
    )
    first_lease = media.claim_next("worker_before_restart")
    assert first_lease is not None and first_lease.attempt_number == 1

    reopened = MediaPersistence(database_url)
    reopened.initialize()
    assert reopened.recover_interrupted_jobs() == 1
    recovered = reopened.get_job(job.job_id)
    assert recovered is not None and recovered.status == JobStatus.RETRY
    assert len(reopened.list_jobs()) == 1

    duplicate = reopened.enqueue_job(
        job_type="chronicle",
        payload={"chapter": "restart-proof"},
        envelope_id=envelope.envelope_id,
        max_attempts=4,
    )
    assert duplicate.job_id == job.job_id
    assert len(reopened.list_jobs()) == 1
    second_lease = reopened.claim_next("worker_after_restart")
    assert second_lease is not None
    assert second_lease.job.job_id == job.job_id
    assert second_lease.attempt_number == 2
    completed = reopened.complete_job(job.job_id)
    assert completed.status == JobStatus.COMPLETED
    snapshot = reopened.snapshot()
    assert len(snapshot["attempts"]) == 2
    assert {item["status"] for item in snapshot["attempts"]} == {"interrupted", "completed"}


def test_retryable_failure_requeues_until_attempt_limit() -> None:
    media = MediaPersistence("sqlite://")
    media.initialize()
    job = media.enqueue_job(job_type="image", payload={"shot": 1}, max_attempts=2)
    lease1 = media.claim_next("image_worker")
    assert lease1 is not None
    retry = media.fail_job(job.job_id, reason_code="provider_unavailable", retryable=True)
    assert retry.status == JobStatus.RETRY
    lease2 = media.claim_next("image_worker")
    assert lease2 is not None and lease2.attempt_number == 2
    failed = media.fail_job(job.job_id, reason_code="provider_unavailable", retryable=True)
    assert failed.status == JobStatus.FAILED
    assert media.claim_next("image_worker") is None


def test_default_router_prefers_eligible_local_free_provider() -> None:
    router = MediaProviderRouter()
    router.register(_paid_narrative())
    router.register(_local_narrative())
    request = ProviderRequest(
        kind=ProviderKind.NARRATIVE,
        required_flags=("structured_output",),
        deterministic_seed_required=True,
        max_vram_mb=12000,
    )
    selection = router.select(request)
    assert selection.selected
    assert selection.provider_id == "local_qwen"
    assert selection.paid is False
    assert selection.estimated_cost_microusd == 0


def test_paid_provider_requires_all_explicit_policy_gates() -> None:
    router = MediaProviderRouter()
    router.register(_paid_narrative())

    ordinary = ProviderRequest(kind=ProviderKind.NARRATIVE, paid_allowed=False)
    assert router.select(ordinary).selected is False

    job_allows_paid = ProviderRequest(kind=ProviderKind.NARRATIVE, paid_allowed=True)
    policy_allows_paid = ProviderPolicy(
        local_only=False,
        cloud_allowed=True,
        allow_paid=True,
        require_explicit_paid_policy=True,
        daily_paid_budget_microusd=1000000,
    )
    assert router.select(job_allows_paid, policy_allows_paid).selected is False

    explicit = ProviderRequest(
        kind=ProviderKind.NARRATIVE,
        paid_allowed=True,
        explicit_paid_authorization=True,
        max_estimated_cost_microusd=300000,
    )
    assert router.select(explicit).selected is False

    selected = router.select(explicit, policy_allows_paid, daily_paid_spend_microusd=100000)
    assert selected.selected is True
    assert selected.provider_id == "paid_narrative_api"
    assert selected.paid is True

    over_budget = router.select(explicit, policy_allows_paid, daily_paid_spend_microusd=900000)
    assert over_budget.selected is False


def test_capability_and_vram_constraints_filter_before_ranking() -> None:
    router = MediaProviderRouter()
    router.register(
        ProviderDescriptor(
            provider_id="local_image_large",
            kind=ProviderKind.IMAGE,
            local=True,
            paid=False,
            reference_conditioning=True,
            capability_flags=("identity_reference",),
            estimated_vram_mb=16000,
            quality_rank=95,
        )
    )
    router.register(
        ProviderDescriptor(
            provider_id="local_image_12gb",
            kind=ProviderKind.IMAGE,
            local=True,
            paid=False,
            reference_conditioning=True,
            capability_flags=("identity_reference",),
            estimated_vram_mb=11000,
            quality_rank=80,
        )
    )
    request = ProviderRequest(
        kind=ProviderKind.IMAGE,
        required_flags=("identity_reference",),
        reference_conditioning_required=True,
        max_vram_mb=12000,
    )
    selection = router.select(request, ProviderPolicy(max_vram_mb=12000))
    assert selection.provider_id == "local_image_12gb"


def test_route_job_holds_when_no_eligible_provider_and_does_not_spend() -> None:
    media = MediaPersistence("sqlite://")
    media.initialize()
    request = ProviderRequest(
        kind=ProviderKind.NARRATIVE,
        paid_allowed=True,
        explicit_paid_authorization=True,
    )
    job = media.enqueue_job(job_type="chronicle", payload={"chapter": 1}, provider_request=request)
    router = MediaProviderRouter()
    router.register(_paid_narrative())

    blocked = media.route_job(job.job_id, router)
    assert blocked.selected is False
    held = media.get_job(job.job_id)
    assert held is not None and held.status == JobStatus.HELD
    assert held.selected_provider_id is None

    policy = ProviderPolicy(
        local_only=False,
        cloud_allowed=True,
        allow_paid=True,
        require_explicit_paid_policy=True,
        daily_paid_budget_microusd=1000000,
    )
    allowed = media.route_job(job.job_id, router, policy)
    assert allowed.selected is True
    rerouted = media.get_job(job.job_id)
    assert rerouted is not None and rerouted.status == JobStatus.QUEUED
    assert rerouted.selected_provider_id == "paid_narrative_api"
    assert media.snapshot()["provider_executions"] == []


def test_artifact_and_provider_execution_records_are_idempotent_and_provenanced() -> None:
    media = MediaPersistence("sqlite://")
    media.initialize()
    job = media.enqueue_job(job_type="image", payload={"shot": 2})
    lease = media.claim_next("worker")
    assert lease is not None
    execution_id = media.record_provider_execution(
        job_id=job.job_id,
        attempt_id=lease.attempt_id,
        provider_id="local_image",
        status="completed",
        actual_gpu_ms=4500,
        metadata={"seed": 42},
    )
    same_execution = media.record_provider_execution(
        job_id=job.job_id,
        attempt_id=lease.attempt_id,
        provider_id="local_image",
        status="completed",
        actual_gpu_ms=4500,
        metadata={"seed": 42},
    )
    media.complete_job(job.job_id, resource_usage={"gpu_ms": 4500})
    artifact_id = media.record_artifact(
        job_id=job.job_id,
        artifact_kind="still",
        uri="media://shot-2.png",
        digest="abc123",
        metadata={"width": 1080, "height": 1920},
    )
    same_artifact = media.record_artifact(
        job_id=job.job_id,
        artifact_kind="still",
        uri="media://shot-2.png",
        digest="abc123",
        metadata={"width": 1080, "height": 1920},
    )
    assert execution_id == same_execution
    assert artifact_id == same_artifact
    snapshot = media.snapshot()
    assert len(snapshot["provider_executions"]) == 1
    assert len(snapshot["artifacts"]) == 1
