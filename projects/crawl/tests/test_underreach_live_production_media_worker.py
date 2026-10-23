from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from livingworld.crawl_persistence import CrawlPersistence
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.underreach_group_social_orchestration import METADATA_KEY as GROUP_SOCIAL_METADATA_KEY
from livingworld.underreach_live_production_media_worker import LiveProductionMediaWorker
from livingworld.underreach_live_production_media_worker_alpha import (
    ALPHA_FACT_FALLBACK_PROVIDER_ID,
    AlphaLiveProductionMediaWorker,
)
from livingworld.underreach_media_event_export import CanonicalMediaEventExporter
from livingworld.underreach_narrative_claim_verification import ClaimType


def _base_crawl():
    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    lifecycle = CrawlLifecycleService(persistence)
    crawl = lifecycle.create_seeded_crawl(
        seed="live-media-base-alpha",
        crawler_ids=("descender_a", "descender_b"),
        floor_count=2,
    )
    lifecycle.start(crawl)
    event = lifecycle.record_event(
        crawl,
        "COMBAT_STARTED",
        "A deterministic combat beat began.",
        actor_ids=["descender_a"],
        location_id=crawl.participants["descender_a"].current_location_id,
        data={"state_changes": {"combat_started": True}},
    )
    return persistence, crawl, event


def test_media_export_accepts_base_alpha_without_group_social_metadata() -> None:
    persistence, crawl, event = _base_crawl()
    assert GROUP_SOCIAL_METADATA_KEY not in crawl.modifiers
    before_json = crawl.model_dump_json()
    before_fingerprint = crawl.fingerprint()
    before_history = tuple(crawl.history_event_ids)

    envelope = CanonicalMediaEventExporter(persistence).export_event(crawl, event.id)

    assert envelope.crawl_id == crawl.id
    assert envelope.source_event_ids == (event.id,)
    assert envelope.delver_ids == ("descender_a",)
    assert envelope.presentation_can_mutate_simulation is False
    assert crawl.model_dump_json() == before_json
    assert crawl.fingerprint() == before_fingerprint
    assert tuple(crawl.history_event_ids) == before_history


def test_media_export_still_rejects_malformed_group_social_state() -> None:
    persistence, crawl, event = _base_crawl()
    crawl.modifiers[GROUP_SOCIAL_METADATA_KEY] = {}
    with pytest.raises(Exception):
        CanonicalMediaEventExporter(persistence).export_event(crawl, event.id)


def test_live_worker_requires_exact_production_provider_classes(tmp_path: Path) -> None:
    worker = LiveProductionMediaWorker(repo_root=tmp_path, state_directory=tmp_path / "state")
    descriptors = [
        SimpleNamespace(provider_id="comfyui_local_image"),
        SimpleNamespace(provider_id="kokoro_local_tts"),
        SimpleNamespace(provider_id="comfyui_wan22_ti2v_5b"),
    ]
    ready = SimpleNamespace(
        descriptors=descriptors,
        ollama_writer=object(),
        ollama_verifier=object(),
    )
    missing_wan = SimpleNamespace(
        descriptors=descriptors[:-1],
        ollama_writer=object(),
        ollama_verifier=object(),
    )
    missing_writer = SimpleNamespace(
        descriptors=descriptors,
        ollama_writer=None,
        ollama_verifier=object(),
    )

    assert worker._production_ready(ready) is True
    assert worker._production_ready(missing_wan) is False
    assert worker._production_ready(missing_writer) is False


def test_live_worker_reads_only_checkpointed_tick(tmp_path: Path) -> None:
    state_directory = tmp_path / "alpha"
    runtime_state = state_directory / "state" / "runtime.json"
    runtime_state.parent.mkdir(parents=True)
    runtime_state.write_text(
        json.dumps({"latest_checkpoint": {"tick": 42}}),
        encoding="utf-8",
    )
    worker = LiveProductionMediaWorker(repo_root=tmp_path, state_directory=state_directory)
    assert worker._checkpoint_tick() == 42


def test_live_worker_cursor_is_crawl_scoped_and_durable(tmp_path: Path) -> None:
    state_directory = tmp_path / "alpha"
    worker = LiveProductionMediaWorker(repo_root=tmp_path, state_directory=state_directory)
    worker.media_root.mkdir(parents=True, exist_ok=True)

    worker._save_cursor("crawl-a", 17, "event-17")

    assert worker._load_cursor("crawl-a") == 17
    assert worker._load_cursor("crawl-b") == 0
    payload = json.loads(worker.cursor_path.read_text(encoding="utf-8"))
    assert payload["last_event_id"] == "event-17"


def _factual_claim(*, sentence_index: int = 0, claim_id: str = "claim-fact"):
    return SimpleNamespace(
        claim_id=claim_id,
        claim_type=ClaimType.FACTUAL,
        sentence_index=sentence_index,
        text="descender a is tied to the canonical event COMBAT_STARTED.",
        subject="descender_a",
        predicate="event_type",
        target_or_value="COMBAT_STARTED",
        supporting_allowed_fact_ids=("fact-1",),
        confidence=1.0,
    )


def _style_claim(*, sentence_index: int = 0):
    return SimpleNamespace(
        claim_id="claim-style",
        claim_type=ClaimType.STYLISTIC,
        sentence_index=sentence_index,
        text="The floor trembled with danger.",
        subject=None,
        predicate=None,
        target_or_value=None,
        supporting_allowed_fact_ids=(),
        confidence=1.0,
    )


def _alpha_worker_for_recovery(verifier):
    worker = object.__new__(AlphaLiveProductionMediaWorker)
    worker.verifier = verifier
    worker._alpha_narrative_aux_bypass_count = 0
    worker._alpha_narrative_fact_fallback_count = 0
    return worker


def test_alpha_narrative_recovery_removes_only_auxiliary_assessments_when_claims_pass() -> None:
    claim = _factual_claim()
    manifest = SimpleNamespace(
        manifest_id="manifest-original",
        draft_id="draft-original",
        chapter_id="chapter-1",
        claims=(claim,),
    )

    class Verifier:
        def __init__(self):
            self.registered = []

        def get_manifest(self, manifest_id):
            assert manifest_id == "manifest-original"
            return manifest

        def register_manifest(self, *, draft_id, claim_specs, auxiliary_assessments):
            self.registered.append((draft_id, tuple(claim_specs), tuple(auxiliary_assessments)))
            return SimpleNamespace(manifest_id="manifest-clean")

        def verify(self, manifest_id):
            assert manifest_id == "manifest-clean"
            return SimpleNamespace(verification_id="verification-clean", review_ready=True)

    verifier = Verifier()
    worker = _alpha_worker_for_recovery(verifier)
    result = worker._recover_alpha_narrative_verification(
        SimpleNamespace(manifest_id="manifest-original")
    )

    assert result.review_ready is True
    assert worker._alpha_narrative_aux_bypass_count == 1
    assert worker._alpha_narrative_fact_fallback_count == 0
    assert len(verifier.registered) == 1
    assert verifier.registered[0][0] == "draft-original"
    assert verifier.registered[0][2] == ()
    assert verifier.registered[0][1][0].supporting_allowed_fact_ids == ("fact-1",)


def test_alpha_narrative_recovery_builds_fact_only_draft_if_style_still_rejects() -> None:
    style = _style_claim(sentence_index=0)
    factual = _factual_claim(sentence_index=1)
    manifest = SimpleNamespace(
        manifest_id="manifest-original",
        draft_id="draft-original",
        chapter_id="chapter-2",
        claims=(style, factual),
    )

    class Verifier:
        def __init__(self):
            self.manifest_calls = []
            self.draft_calls = []
            self.verify_count = 0

        def get_manifest(self, manifest_id):
            assert manifest_id == "manifest-original"
            return manifest

        def register_manifest(self, *, draft_id, claim_specs, auxiliary_assessments):
            specs = tuple(claim_specs)
            self.manifest_calls.append((draft_id, specs, tuple(auxiliary_assessments)))
            return SimpleNamespace(manifest_id=f"manifest-{len(self.manifest_calls)}")

        def verify(self, manifest_id):
            self.verify_count += 1
            return SimpleNamespace(
                verification_id=f"verification-{self.verify_count}",
                review_ready=self.verify_count == 2,
            )

        def register_draft(
            self,
            *,
            chapter_id,
            prose,
            writer_provider_id,
            writer_provider_local,
            writer_provider_paid,
        ):
            self.draft_calls.append(
                (
                    chapter_id,
                    prose,
                    writer_provider_id,
                    writer_provider_local,
                    writer_provider_paid,
                )
            )
            return SimpleNamespace(draft_id="draft-fact-only")

    verifier = Verifier()
    worker = _alpha_worker_for_recovery(verifier)
    result = worker._recover_alpha_narrative_verification(
        SimpleNamespace(manifest_id="manifest-original")
    )

    assert result.review_ready is True
    assert worker._alpha_narrative_aux_bypass_count == 0
    assert worker._alpha_narrative_fact_fallback_count == 1
    assert verifier.draft_calls == [
        (
            "chapter-2",
            factual.text,
            ALPHA_FACT_FALLBACK_PROVIDER_ID,
            True,
            False,
        )
    ]
    assert len(verifier.manifest_calls) == 2
    fact_only_specs = verifier.manifest_calls[1][1]
    assert len(fact_only_specs) == 1
    assert fact_only_specs[0].claim_type == ClaimType.FACTUAL
    assert fact_only_specs[0].sentence_index == 0
    assert fact_only_specs[0].supporting_allowed_fact_ids == ("fact-1",)
    assert verifier.manifest_calls[1][2] == ()
