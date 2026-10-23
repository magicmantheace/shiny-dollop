from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from livingworld.underreach_unattended_promotion_soak import (
    PHASE,
    PROTOCOL,
    REVIEW_QUEUE_SCHEMA,
    UnattendedPromotionSoakPolicy,
    UnattendedPromotionSoakService,
    validate_soak_result,
)


SEED = "underreach-30-5-12-focused-soak"


def _require_ffmpeg() -> None:
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("30.5.12 focused soak requires local ffmpeg and ffprobe")


@pytest.fixture(scope="module")
def completed_soak(tmp_path_factory):
    _require_ffmpeg()
    base = tmp_path_factory.mktemp("underreach-30_5_12")
    canonical_db = base / "canonical.sqlite3"
    media_db = base / "media.sqlite3"
    media_root = base / "media"
    policy = UnattendedPromotionSoakPolicy(
        population_count=20,
        stratum_count=3,
        max_simulation_steps=2000,
        required_social_events=4,
        portrait_width=192,
        portrait_height=192,
        scene_width=270,
        scene_height=480,
        promo_fps=12,
        promo_minimum_seconds=6.0,
        promo_maximum_seconds=24.0,
    )
    service = UnattendedPromotionSoakService(
        canonical_database_url=f"sqlite:///{canonical_db.as_posix()}",
        media_database_url=f"sqlite:///{media_db.as_posix()}",
        media_root=media_root,
        seed=SEED,
        policy=policy,
    )
    result = service.run()
    return result, media_root


def test_policy_freezes_meaningful_unattended_acceptance_floor() -> None:
    policy = UnattendedPromotionSoakPolicy()
    assert policy.population_count >= 20
    assert policy.stratum_count >= 3
    assert policy.required_social_events >= 4
    assert policy.scene_width * 16 == policy.scene_height * 9
    assert policy.digest

    with pytest.raises(Exception):
        UnattendedPromotionSoakPolicy(population_count=19)
    with pytest.raises(Exception):
        UnattendedPromotionSoakPolicy(scene_width=360, scene_height=639)


def test_full_soak_runs_20_plus_delvers_with_real_combat_social_and_progression(completed_soak) -> None:
    result, _ = completed_soak
    provenance = result.event_provenance
    assert result.protocol == PROTOCOL
    assert result.phase == PHASE == "30.5"
    assert result.canonical["population_count"] == 20
    assert result.canonical["outcome"] == "completed"
    assert result.canonical["encounters_resolved"] > 0
    assert result.canonical["strata_advanced"] >= 2
    assert result.canonical["final_stratum"] == 3

    # The acceptance social beat is canonical, deterministic, and entirely
    # accepted-service driven: recruit -> accept -> party -> four reinforced
    # promise violations -> evidence-backed 30C.5 betrayal.
    assert len(provenance["social_pair_ids"]) == 2
    assert provenance["social_party_id"]
    assert provenance["recruitment_offer_id"]
    assert len(provenance["promise_violation_event_ids"]) >= 4
    assert provenance["betrayal_event_id"]
    assert provenance["betrayal_conflict_score"] >= 0.58
    assert len(provenance["social_event_ids"]) >= 5

    composite_sources = set(provenance["composite_source_event_ids"])
    assert set(provenance["promise_violation_event_ids"]).issubset(composite_sources)
    assert provenance["betrayal_event_id"] in composite_sources
    assert provenance["combat_event_ids"]
    assert provenance["progression_event_ids"]

    components = provenance["composite_highlight_components"]
    assert provenance["composite_highlight_floor"] == 50
    assert components["danger"] >= 10
    assert components["social_stakes"] >= 20
    assert components["continuity"] >= 15
    assert components["visual_potential"] >= 5
    assert components["total"] >= 50
    assert provenance["composite_highlight_score"] == components["total"]
    assert provenance["composite_foreign_actor_ids"] == []

    assert set(provenance["encounter_retreat_event_ids"]).isdisjoint(
        provenance["terminal_media_event_ids"]
    )


def test_read_only_media_builds_profiles_chronicle_and_verified_story(completed_soak) -> None:
    result, _ = completed_soak
    assert result.canonical["bootstrap_export_unchanged"] is True
    assert result.canonical["unchanged_during_downstream_media"] is True
    assert result.media["profile_count"] >= 20
    assert result.media["envelope_count"] >= 6
    assert result.chronicle["chapter_count"] >= 1
    assert result.chronicle["highlight_count"] >= 1
    assert result.chronicle["source_event_ids"]
    assert result.verification["status"] == "review_ready"
    assert result.verification["review_ready"] is True
    assert result.verification["deterministic_contradiction_count"] == 0
    assert result.verification["unsupported_claim_count"] == 0
    assert result.verification["writer_provider_local"] is True
    assert result.verification["writer_provider_paid"] is False


def test_local_media_restart_recovers_same_scene_job_and_remains_idempotent(completed_soak) -> None:
    result, _ = completed_soak
    assert result.restart["injected_worker"] == "image_scene"
    assert result.restart["recovered_job_count"] == 1
    assert result.restart["same_scene_job"] is True
    assert result.restart["scene_attempt_count"] == 2
    assert result.idempotency["envelope_reregistration_stable"] is True
    assert result.idempotency["scene_completed_reenqueue_reused_job"] is True
    assert result.idempotency["review_queue_completed_reenqueue_reused_job"] is True


def test_local_visual_audio_ffmpeg_path_reaches_pending_review_without_video_diffusion(completed_soak) -> None:
    result, media_root = completed_soak
    assert result.presentation["image_provider_id"] == "local_deterministic_png"
    assert result.presentation["portrait_artifact_id"]
    assert result.presentation["scene_artifact_id"]
    assert result.audio["package_status"] == "completed"
    assert result.audio["caption_only_ready"] is True
    assert result.audio["voice_status"] == "completed"
    assert result.audio["voice_provider_id"] == "local_deterministic_wav"

    promo = result.promotion
    assert promo["status"] == "completed"
    assert promo["width"] * 16 == promo["height"] * 9
    assert promo["audio_stream_present"] is True
    assert promo["motion_story_fallback_guaranteed"] is True
    assert promo["video_diffusion_required"] is False
    assert promo["ffmpeg_local"] is True
    promo_path = media_root / promo["output_uri"]
    assert promo_path.is_file() and promo_path.stat().st_size > 1000

    review = result.review_queue
    assert review["review_status"] == "pending"
    assert review["published"] is False
    assert review["review_ready"] is True
    assert review["human_intervention_required_before_review"] is False
    assert review["human_review_required_before_publication"] is True
    review_manifest = media_root / review["review_manifest_uri"]
    assert review_manifest.is_file()
    assert REVIEW_QUEUE_SCHEMA in review_manifest.read_text(encoding="utf-8")


def test_static_site_and_mandatory_zeroes_close_phase_30_5(completed_soak) -> None:
    result, media_root = completed_soak
    website = result.website
    assert website["status"] == "completed"
    assert website["profile_count"] >= 20
    assert website["verified_narrative_count"] >= 1
    assert website["highlight_count"] >= 1
    assert website["static_only"] is True
    assert website["live_database_required_after_build"] is False
    assert website["published_video_count"] == 0  # pending review is deliberately not public yet
    assert (media_root / website["public_root"] / "index.html").is_file()

    assert all(result.mandatory_zeroes.values())
    assert result.media["paid_execution_count"] == 0
    assert result.media["nonlocal_provider_ids"] == []
    assert result.authority_contract["canonical_owner"] == "deterministic_simulation"
    assert result.authority_contract["presentation_can_mutate_simulation"] is False
    assert result.authority_contract["review_queue_can_publish_automatically"] is False
    assert result.authority_contract["optional_video_enhancement_required_for_acceptance"] is False
    assert result.authority_contract["next_phase"] == "31 - Dialogue / Commentary"
    assert validate_soak_result(result)
