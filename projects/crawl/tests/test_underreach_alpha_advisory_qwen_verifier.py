from __future__ import annotations

from livingworld.underreach_live_production_media_worker_alpha import AlphaLiveProductionMediaWorker


class _EmptyVerifier:
    def list_verifications(self):
        return ()


def test_alpha_editorial_verification_does_not_require_qwen_pipeline(monkeypatch) -> None:
    """Auxiliary Qwen output must never block the deterministic Alpha editorial path."""
    worker = object.__new__(AlphaLiveProductionMediaWorker)
    worker.media = object()
    worker.chronicle = object()
    worker.verifier = _EmptyVerifier()
    worker.stack = None

    expected = object()
    monkeypatch.setattr(worker, "_build_alpha_editorial_verification", lambda _chapter_id: expected)

    assert worker._ensure_alpha_review_ready_verification("chapter_001") is expected


def test_alpha_worker_status_declares_qwen_verifier_non_blocking_and_continuity_enabled(monkeypatch) -> None:
    worker = object.__new__(AlphaLiveProductionMediaWorker)
    worker._alpha_reindexed_highlights = 0
    worker._alpha_narrative_aux_bypass_count = 0
    worker._alpha_narrative_fact_fallback_count = 0

    captured = {}

    def capture(_self, state: str, **extra) -> None:
        captured["state"] = state
        captured.update(extra)

    monkeypatch.setattr(
        "livingworld.underreach_live_production_media_worker.LiveProductionMediaWorker._status",
        capture,
    )

    worker._status("running")

    assert captured["qwen_verifier_blocks_promotion"] is False
    assert captured["editorial_story_beats"] is True
    assert captured["max_story_sentences"] == 3
    assert captured["stable_identity_reference"] is True
    assert captured["equipment_reference_chaining"] is True
    assert captured["reference_conditioned_scenes"] is True
    assert captured["presentation_polish_version"] == "alpha-continuity-v2"
    assert captured["minimum_motion_seconds"] == 9.0
