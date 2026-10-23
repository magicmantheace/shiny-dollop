from __future__ import annotations

import argparse
import json
from pathlib import Path

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.runtime_checkpoint import canonical_json, payload_digest
from livingworld.underreach_brain_driven_descent import BrainDrivenDescentService
from livingworld.underreach_group_social_orchestration import GroupSocialOrchestrationService
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
from livingworld.underreach_rivalry_betrayal_social_conflict import RivalryBetrayalSocialConflictService
from livingworld.underreach_social_intent_execution import SocialIntentExecutionService
from livingworld.underreach_social_memory_evolution import SocialMemoryEvolutionService


PROOF_PROTOCOL = "underreach.media-foundation-proof.v1"


def _canonical_stack(seed: str):
    persistence = CrawlPersistence("sqlite://")
    persistence.initialize()
    brain = BrainDrivenDescentService(persistence)
    ids = [f"descender_{index:03d}" for index in range(8)]
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
    lifecycle = CrawlLifecycleService(persistence)
    event = lifecycle.record_event(
        descent,
        "RESCUE",
        "30.5.2 durable media foundation proof source.",
        actor_ids=ids[:2],
        location_id=descent.participants[ids[0]].current_location_id,
        data={
            "danger": 0.87,
            "state_changes": {"30_5_2_media_foundation": True},
            "media_proof": {"supported": True, "tier": "foundation"},
        },
    )
    envelope = CanonicalMediaEventExporter(persistence).export_event(descent, event.id)
    return persistence, descent, envelope


def _providers() -> MediaProviderRouter:
    router = MediaProviderRouter()
    router.register(
        ProviderDescriptor(
            provider_id="local_qwen",
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
    )
    router.register(
        ProviderDescriptor(
            provider_id="paid_narrative_api",
            kind=ProviderKind.NARRATIVE,
            local=False,
            paid=True,
            deterministic_seed=True,
            capability_flags=("structured_output", "premium_quality"),
            estimated_runtime_seconds=2.0,
            estimated_cost_microusd=250000,
            quality_rank=95,
            quality_profile="premium",
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
            estimated_runtime_seconds=45.0,
            quality_rank=80,
            quality_profile="local_12gb",
        )
    )
    router.register(
        ProviderDescriptor(
            provider_id="local_image_too_large",
            kind=ProviderKind.IMAGE,
            local=True,
            paid=False,
            reference_conditioning=True,
            capability_flags=("identity_reference",),
            estimated_vram_mb=16000,
            estimated_runtime_seconds=25.0,
            quality_rank=96,
            quality_profile="oversized",
        )
    )
    return router


def generate(output: Path, *, seed: str) -> dict:
    output.parent.mkdir(parents=True, exist_ok=True)
    db_path = output.with_suffix(".sqlite3")
    if db_path.exists():
        db_path.unlink()

    canonical, descent, envelope = _canonical_stack(seed)
    canonical_before = descent.model_dump(mode="json")
    fingerprint_before = descent.fingerprint()
    history_before = list(descent.history_event_ids)
    ledger_before = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]

    media = MediaPersistence(f"sqlite:///{db_path.as_posix()}")
    media.initialize()
    media.register_envelope(envelope)
    media.register_envelope(envelope)

    router = _providers()
    local_request = ProviderRequest(
        kind=ProviderKind.NARRATIVE,
        required_flags=("structured_output",),
        deterministic_seed_required=True,
        max_vram_mb=12000,
    )
    primary = media.enqueue_job(
        job_type="chronicle",
        payload={"chapter": 1, "envelope_digest": envelope.digest},
        envelope_id=envelope.envelope_id,
        provider_request=local_request,
        max_attempts=4,
    )
    duplicate_primary = media.enqueue_job(
        job_type="chronicle",
        payload={"chapter": 1, "envelope_digest": envelope.digest},
        envelope_id=envelope.envelope_id,
        provider_request=local_request,
        max_attempts=4,
    )
    dependent = media.enqueue_job(
        job_type="verification",
        payload={"source_job_id": primary.job_id},
        envelope_id=envelope.envelope_id,
        dependencies=[primary.job_id],
        priority=500,
    )

    local_selection = media.route_job(primary.job_id, router)
    first_lease = media.claim_next("proof_worker")
    if first_lease is None or first_lease.job.job_id != primary.job_id:
        raise RuntimeError("30.5.2 proof failed initial durable job claim")

    restarted = MediaPersistence(f"sqlite:///{db_path.as_posix()}")
    restarted.initialize()
    recovered_count = restarted.recover_interrupted_jobs()
    recovered_job = restarted.get_job(primary.job_id)
    second_lease = restarted.claim_next("proof_worker")
    if second_lease is None or second_lease.job.job_id != primary.job_id:
        raise RuntimeError("30.5.2 proof failed resumed durable job claim")
    restarted.complete_job(primary.job_id, resource_usage={"cpu_ms": 1200})

    dependency_lease = restarted.claim_next("verification_worker")
    if dependency_lease is None or dependency_lease.job.job_id != dependent.job_id:
        raise RuntimeError("30.5.2 proof failed dependency release after completion")
    restarted.complete_job(dependent.job_id)

    image_request = ProviderRequest(
        kind=ProviderKind.IMAGE,
        required_flags=("identity_reference",),
        reference_conditioning_required=True,
        max_vram_mb=12000,
    )
    image_selection = router.select(image_request, ProviderPolicy(max_vram_mb=12000))

    paid_request = ProviderRequest(
        kind=ProviderKind.NARRATIVE,
        required_flags=("premium_quality",),
        paid_allowed=True,
        explicit_paid_authorization=True,
        max_estimated_cost_microusd=300000,
    )
    paid_job = restarted.enqueue_job(
        job_type="premium_narrative_probe",
        payload={"purpose": "optional-provider-routing-proof"},
        envelope_id=envelope.envelope_id,
        provider_request=paid_request,
    )
    paid_blocked = restarted.route_job(paid_job.job_id, router)
    paid_policy = ProviderPolicy(
        local_only=False,
        cloud_allowed=True,
        allow_paid=True,
        require_explicit_paid_policy=True,
        daily_paid_budget_microusd=1000000,
    )
    paid_allowed = restarted.route_job(
        paid_job.job_id,
        router,
        paid_policy,
        daily_paid_spend_microusd=100000,
    )
    paid_over_budget = router.select(
        paid_request,
        paid_policy,
        daily_paid_spend_microusd=900000,
    )

    restarted.record_artifact(
        job_id=primary.job_id,
        artifact_kind="foundation_probe",
        uri="media://foundation/probe.json",
        digest=payload_digest({"job_id": primary.job_id, "kind": "foundation_probe"}),
        metadata={"generated_media": False, "purpose": "schema_provenance_probe"},
    )

    snapshot = restarted.snapshot()
    reopened_again = MediaPersistence(f"sqlite:///{db_path.as_posix()}")
    reopened_again.initialize()
    snapshot_after_reopen = reopened_again.snapshot()

    canonical_after = descent.model_dump(mode="json")
    ledger_after = [item.model_dump(mode="json") for item in canonical.replay_events(descent.id)]
    canonical_unchanged = canonical_json(canonical_before) == canonical_json(canonical_after)
    ledger_unchanged = ledger_before == ledger_after

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
            "unreal_dependency": snapshot["unreal_dependency"],
            "required_cloud_api": snapshot["required_cloud_api"],
            "required_paid_provider": snapshot["required_paid_provider"],
        },
        "canonical": {
            "state_unchanged": canonical_unchanged,
            "fingerprint_unchanged": descent.fingerprint() == fingerprint_before,
            "history_unchanged": descent.history_event_ids == history_before,
            "ledger_rows_unchanged": ledger_unchanged,
            "fingerprint": descent.fingerprint(),
            "state_digest": payload_digest(canonical_after),
            "ledger_digest": payload_digest(ledger_after),
        },
        "media": {
            "database_backend": "sqlite",
            "envelope_id": envelope.envelope_id,
            "envelope_count": len(snapshot["envelopes"]),
            "job_count": len(snapshot["jobs"]),
            "attempt_count": len(snapshot["attempts"]),
            "artifact_count": len(snapshot["artifacts"]),
            "provider_execution_count": len(snapshot["provider_executions"]),
            "snapshot_digest": snapshot["digest"],
            "snapshot_equal_after_reopen": snapshot_after_reopen == snapshot,
        },
        "queue": {
            "duplicate_primary_same_job": duplicate_primary.job_id == primary.job_id,
            "recovered_interrupted_count": recovered_count,
            "recovered_status": recovered_job.status.value if recovered_job else None,
            "first_attempt_id": first_lease.attempt_id,
            "second_attempt_id": second_lease.attempt_id,
            "first_attempt_number": first_lease.attempt_number,
            "second_attempt_number": second_lease.attempt_number,
            "dependency_completed": restarted.get_job(dependent.job_id).status.value == "completed",
            "attempt_statuses": sorted(item["status"] for item in snapshot["attempts"]),
        },
        "providers": {
            "registered_provider_ids": [item.provider_id for item in router.providers()],
            "default_local_selected": local_selection.selected and local_selection.provider_id == "local_qwen",
            "image_vram_filter_selected": image_selection.selected and image_selection.provider_id == "local_image_12gb",
            "paid_blocked_by_default": paid_blocked.selected is False,
            "paid_selected_only_with_explicit_policy": paid_allowed.selected and paid_allowed.provider_id == "paid_narrative_api",
            "paid_over_budget_blocked": paid_over_budget.selected is False,
            "paid_selection_cost_microusd": paid_allowed.estimated_cost_microusd,
            "routing_invoked_provider": False,
        },
    }
    proof = {**body, "digest": payload_digest(body)}
    output.write_text(json.dumps(proof, indent=2, sort_keys=True), encoding="utf-8")
    return proof


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--seed", default="underreach-30-5-2-media-foundation-proof")
    args = parser.parse_args()
    proof = generate(Path(args.output), seed=args.seed)
    print(json.dumps({"digest": proof["digest"], "snapshot": proof["media"]["snapshot_digest"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
