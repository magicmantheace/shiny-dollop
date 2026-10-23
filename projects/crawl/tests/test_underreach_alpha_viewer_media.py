from __future__ import annotations

from hashlib import sha256
import json

import httpx

from livingworld.runtime_checkpoint import payload_digest
from livingworld.underreach_alpha_presentation_polish import alpha_scene_variant_spec
from livingworld.underreach_delver_chronicle_profile import ChapterKind, ChronicleChapter
from livingworld.underreach_headless_local_image_production import ImageProductionSpec, ImagePurpose
from livingworld.underreach_live_production_media_worker_alpha import (
    _alpha_caption_style,
    _select_alpha_editorial_facts,
)
from livingworld.underreach_media_event_export import AllowedFact
from livingworld.underreach_media_foundation import ProviderKind, ProviderRequest
from livingworld.underreach_ollama_providers import (
    ALPHA_VIEWER_FACING_ENV,
    OllamaNarrativeProvider,
    OllamaProviderConfig,
)


def _stable_id(prefix: str, *parts: object) -> str:
    text = ":".join(str(part) for part in parts)
    return f"{prefix}_{sha256(text.encode('utf-8')).hexdigest()[:24]}"


def _chapter() -> ChronicleChapter:
    profile_id = "profile_001"
    envelope_id = "envelope_001"
    chapter_id = _stable_id("chronicle_chapter", profile_id, ChapterKind.HIGHLIGHT.value, "none", envelope_id)
    body = {
        "protocol": "underreach.delver-chronicle-profile.v1",
        "implementation_version": "30.5.4",
        "phase": "30.5",
        "chapter_id": chapter_id,
        "profile_id": profile_id,
        "crawl_id": "crawl_001",
        "delver_id": "descender_001",
        "chapter_kind": ChapterKind.HIGHLIGHT.value,
        "title_code": "HIGHLIGHT_COMBAT_ENDED",
        "canonical_tick": 10,
        "source_envelope_ids": [envelope_id],
        "source_event_ids": ["event_001"],
        "allowed_fact_ids": ["fact_001", "fact_002"],
        "highlight_id": None,
        "arc_ids": [],
        "trigger_codes": ["chapter:highlight", "event:COMBAT_ENDED"],
        "terminal": False,
        "structured_only": True,
        "claim_verification_required": True,
        "generated_prose_used": False,
        "presentation_can_mutate_simulation": False,
    }
    return ChronicleChapter.model_validate({**body, "digest": payload_digest(body)})


def _facts() -> tuple[AllowedFact, ...]:
    return (
        AllowedFact(
            fact_id="fact_001",
            scope="event",
            subject="descender_001",
            predicate="event_type",
            value="COMBAT_ENDED",
            source_event_ids=("event_001",),
        ),
        AllowedFact(
            fact_id="fact_002",
            scope="event",
            subject="descender_001",
            predicate="stratum",
            value=2,
            source_event_ids=("event_001",),
        ),
    )


def _mock_client(payload: dict) -> httpx.Client:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": json.dumps(payload)}})

    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test")


def test_alpha_viewer_mode_filters_unknown_fact_ids_but_preserves_valid_model_order(monkeypatch) -> None:
    monkeypatch.setenv(ALPHA_VIEWER_FACING_ENV, "true")
    client = _mock_client(
        {
            "fact_ids": ["invented_fact", "fact_002", "fact_001"],
            "style_line": None,
            "tone": "cinematic",
        }
    )
    try:
        provider = OllamaNarrativeProvider(OllamaProviderConfig(), client=client)
        selection = provider.select(_chapter(), _facts())
    finally:
        client.close()

    assert selection.fact_ids == ("fact_002", "fact_001")


def test_alpha_viewer_mode_uses_deterministic_allowlisted_fallback_and_keeps_exact_claim_metadata(monkeypatch) -> None:
    monkeypatch.setenv(ALPHA_VIEWER_FACING_ENV, "true")
    client = _mock_client(
        {
            "fact_ids": ["invented_fact"],
            "style_line": None,
            "tone": "cinematic",
        }
    )
    try:
        provider = OllamaNarrativeProvider(OllamaProviderConfig(max_selected_facts=2), client=client)
        prose, claims, selected = provider.build_prose_and_claims(_chapter(), _facts())
    finally:
        client.close()

    assert selected == ("fact_001", "fact_002")
    assert "The fight came to an end." in prose
    assert "A delver pushed deeper into the crawl." in prose
    assert "descender_001" not in prose
    assert "event_001" not in prose
    assert "fact_001" not in prose
    assert "Canonical record:" not in prose
    assert "canonical stratum" not in prose.lower()

    assert len(claims) == 2
    assert claims[0].subject == "descender_001"
    assert claims[0].predicate == "event_type"
    assert claims[0].target_or_value == "COMBAT_ENDED"
    assert claims[0].supporting_allowed_fact_ids == ("fact_001",)
    assert claims[1].subject == "descender_001"
    assert claims[1].predicate == "stratum"
    assert claims[1].target_or_value == 2
    assert claims[1].supporting_allowed_fact_ids == ("fact_002",)


def test_alpha_caption_style_is_compact_and_bottom_anchored_for_live_vertical_output() -> None:
    style = _alpha_caption_style(768)

    assert "FontSize=17" in style
    assert "Alignment=2" in style
    assert "MarginV=42" in style
    assert "Outline=1" in style
    assert "Shadow=1" in style
    assert "WrapStyle=0" in style
    assert "MarginL=38" in style
    assert "MarginR=38" in style


def test_alpha_editorial_selection_prefers_setup_action_outcome_and_reward(monkeypatch) -> None:
    monkeypatch.setenv(ALPHA_VIEWER_FACING_ENV, "true")
    facts = (
        AllowedFact(fact_id="a", scope="event", subject="descender_001", predicate="event_type", value="CRAWLER_MOVED", source_event_ids=("e",)),
        AllowedFact(fact_id="b", scope="event", subject="descender_001", predicate="event_type", value="ENCOUNTER_TRIGGERED", source_event_ids=("e",)),
        AllowedFact(fact_id="c", scope="event", subject="descender_001", predicate="event_type", value="COMBAT_HIT", source_event_ids=("e",)),
        AllowedFact(fact_id="d", scope="event", subject="descender_001", predicate="event_type", value="ENEMY_DEFEATED", source_event_ids=("e",)),
        AllowedFact(fact_id="e", scope="event", subject="descender_001", predicate="event_type", value="ITEM_ACQUIRED", source_event_ids=("e",)),
        AllowedFact(fact_id="f", scope="event", subject="descender_001", predicate="stratum", value=3, source_event_ids=("e",)),
    )

    selected = _select_alpha_editorial_facts(facts, limit=4)

    assert [fact.fact_id for fact in selected] == ["b", "c", "d", "e"]


def test_alpha_editorial_selection_deduplicates_equivalent_progression_sentences(monkeypatch) -> None:
    monkeypatch.setenv(ALPHA_VIEWER_FACING_ENV, "true")
    facts = (
        AllowedFact(fact_id="a", scope="event", subject="descender_001", predicate="event_type", value="CRAWLER_ADVANCED", source_event_ids=("e",)),
        AllowedFact(fact_id="b", scope="event", subject="descender_001", predicate="stratum", value=4, source_event_ids=("e",)),
        AllowedFact(fact_id="c", scope="event", subject="descender_001", predicate="event_type", value="COMBAT_ENDED", source_event_ids=("e",)),
    )

    selected = _select_alpha_editorial_facts(facts, limit=4)

    assert [fact.fact_id for fact in selected] == ["c", "a"]


def test_alpha_scene_variant_changes_seed_prompt_and_deterministic_identity() -> None:
    base = ImageProductionSpec(
        spec_id="image_spec_base",
        purpose=ImagePurpose.SCENE_STILL,
        crawl_id="crawl_001",
        profile_id="profile_001",
        delver_id="descender_001",
        identity_id="identity_001",
        identity_version=1,
        equipment_revision_id="equipment_001",
        source_envelope_id="envelope_001",
        source_event_ids=("event_001",),
        reference_id=None,
        reference_kind=None,
        chapter_id="chapter_001",
        reference_artifact_ids=("artifact_identity",),
        deterministic_seed=42,
        width=432,
        height=768,
        prompt_template_version="underreach.image-prompt.v1",
        prompt="Base scene prompt.",
        negative_prompt="text",
        provider_request=ProviderRequest(
            kind=ProviderKind.IMAGE,
            required_flags=("headless_image", "png_output"),
            local_required=True,
            deterministic_seed_required=True,
            min_width=432,
            min_height=768,
        ),
        policy_digest="policy",
        digest="placeholder",
    )

    variant = alpha_scene_variant_spec(base, 1, "Establishing view.")

    assert variant.deterministic_seed != base.deterministic_seed
    assert variant.spec_id != base.spec_id
    assert "Establishing view." in variant.prompt
    assert variant.reference_artifact_ids == ("artifact_identity",)
    assert variant.chapter_id == base.chapter_id
    assert variant.source_event_ids == base.source_event_ids
    assert variant.canonical_authority is False
