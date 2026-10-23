from __future__ import annotations

from livingworld.underreach_alpha_cinematic_reference_image import (
    ALPHA_EQUIPMENT_REFERENCE_DENOISE,
    ALPHA_SCENE_ACTION_DENOISE,
    ALPHA_SCENE_OUTCOME_DENOISE,
    ALPHA_SCENE_SETUP_DENOISE,
    cinematic_reference_workflow,
)
from livingworld.underreach_alpha_presentation_polish import (
    MAX_VIEWER_SENTENCE_CHARS,
    alpha_scene_variant_spec,
    find_reference_artifact,
    render_alpha_viewer_sentence,
    with_reference_artifacts,
)
from livingworld.underreach_headless_local_image_production import ImageProductionSpec, ImagePurpose
from livingworld.underreach_media_event_export import AllowedFact
from livingworld.underreach_media_foundation import ProviderKind, ProviderRequest


def _fact(fact_id: str, value: str) -> AllowedFact:
    return AllowedFact(
        fact_id=fact_id,
        scope="event",
        subject="descender_001",
        predicate="event_type",
        value=value,
        source_event_ids=("event_001",),
    )


def _scene_spec() -> ImageProductionSpec:
    return ImageProductionSpec(
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
        reference_artifact_ids=(),
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


def test_viewer_combat_beats_are_specific_distinct_short_and_fact_bounded() -> None:
    sentences = [
        render_alpha_viewer_sentence(_fact("a", "COMBAT_STARTED")),
        render_alpha_viewer_sentence(_fact("b", "COMBAT_HIT")),
        render_alpha_viewer_sentence(_fact("c", "ENEMY_DEFEATED")),
    ]

    assert len(set(sentences)) == 3
    assert all(len(sentence) <= MAX_VIEWER_SENTENCE_CHARS for sentence in sentences)
    assert all("descender_001" not in sentence for sentence in sentences)
    assert sentences == [
        "Combat began in the dungeon.",
        "A hit landed during the fight.",
        "An enemy was defeated in the battle.",
    ]


def test_reference_img2img_workflow_preserves_bounded_cinematic_profile() -> None:
    graph = cinematic_reference_workflow(
        checkpoint="Juggernaut.safetensors",
        prompt="Same delver in a dungeon.",
        negative_prompt="different person",
        seed=123,
        width=432,
        height=768,
        input_image="underreach/reference.png",
        output_prefix="underreach/test",
        denoise=ALPHA_SCENE_ACTION_DENOISE,
    )

    assert graph["4"]["class_type"] == "LoadImage"
    assert graph["4"]["inputs"]["image"] == "underreach/reference.png"
    assert graph["5"]["inputs"]["width"] == 720
    assert graph["5"]["inputs"]["height"] == 1280
    assert graph["6"]["class_type"] == "VAEEncode"
    assert graph["7"]["class_type"] == "KSampler"
    assert graph["7"]["inputs"]["denoise"] == ALPHA_SCENE_ACTION_DENOISE
    assert 0.0 < ALPHA_EQUIPMENT_REFERENCE_DENOISE < ALPHA_SCENE_SETUP_DENOISE < ALPHA_SCENE_OUTCOME_DENOISE < ALPHA_SCENE_ACTION_DENOISE < 1.0
    assert graph["9"]["inputs"]["width"] == 432
    assert graph["9"]["inputs"]["height"] == 768


def test_reference_provenance_survives_scene_variants_and_uses_new_seed_namespace() -> None:
    referenced = with_reference_artifacts(_scene_spec(), ("artifact_equipment",))
    variant = alpha_scene_variant_spec(referenced, 1, "Action beat.")
    other = alpha_scene_variant_spec(referenced, 2, "Outcome beat.")

    assert referenced.reference_artifact_ids == ("artifact_equipment",)
    assert variant.reference_artifact_ids == ("artifact_equipment",)
    assert other.reference_artifact_ids == ("artifact_equipment",)
    assert variant.spec_id != other.spec_id
    assert variant.deterministic_seed != other.deterministic_seed
    assert variant.chapter_id == referenced.chapter_id
    assert variant.source_event_ids == referenced.source_event_ids
    assert variant.canonical_authority is False
    assert variant.presentation_can_mutate_simulation is False


def test_reference_lookup_is_scoped_to_identity_and_reference_slot() -> None:
    snapshot = {
        "artifacts": [
            {
                "artifact_id": "wrong_identity",
                "artifact_kind": "image/png",
                "metadata": {"identity_id": "identity_999", "reference_id": "reference_001"},
            },
            {
                "artifact_id": "wrong_slot",
                "artifact_kind": "image/png",
                "metadata": {"identity_id": "identity_001", "reference_id": "reference_999"},
            },
            {
                "artifact_id": "correct",
                "artifact_kind": "image/png",
                "metadata": {"identity_id": "identity_001", "reference_id": "reference_001"},
            },
        ]
    }

    assert find_reference_artifact(
        snapshot,
        identity_id="identity_001",
        reference_id="reference_001",
    ) == "correct"
