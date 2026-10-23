from __future__ import annotations

from livingworld.underreach_comfyui_production_image import (
    ALPHA_CINEMATIC_CFG,
    ALPHA_CINEMATIC_SAMPLER,
    ALPHA_CINEMATIC_SCHEDULER,
    ALPHA_CINEMATIC_STEPS,
    DEFAULT_ALPHA_CINEMATIC_CHECKPOINT,
    _cinematic_default_workflow,
    _cinematic_prompts,
    _supersampled_dimensions,
)


def test_alpha_cinematic_profile_uses_juggernaut_recommended_sampling() -> None:
    assert DEFAULT_ALPHA_CINEMATIC_CHECKPOINT == "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
    assert ALPHA_CINEMATIC_STEPS == 35
    assert ALPHA_CINEMATIC_CFG == 5.0
    assert ALPHA_CINEMATIC_SAMPLER == "dpmpp_2m"
    assert ALPHA_CINEMATIC_SCHEDULER == "karras"


def test_cinematic_prompt_targets_photoreal_dark_fantasy_and_visible_failure_modes() -> None:
    positive, negative = _cinematic_prompts(
        "Underreach presentation-only Chronicle scene still.",
        "unsupported gameplay claims",
    )

    lowered = positive.lower()
    assert "cinematic movie still" in lowered
    assert "photorealistic dark fantasy" in lowered
    assert "realistic human anatomy" in lowered
    assert "physically based materials" in lowered
    assert "35mm cinema lens" in lowered

    negative_lower = negative.lower()
    assert "cartoon" in negative_lower
    assert "childish drawing" in negative_lower
    assert "malformed anatomy" in negative_lower
    assert "bad hands" in negative_lower
    assert "unsupported gameplay claims" in negative_lower


def test_cinematic_supersampling_lifts_live_vertical_frame_to_near_one_megapixel() -> None:
    assert _supersampled_dimensions(432, 768) == (720, 1280)
    width, height = _supersampled_dimensions(512, 512)
    assert width == height
    assert width >= 952
    assert width % 8 == 0


def test_cinematic_core_workflow_supersamples_then_lanczos_downscales() -> None:
    workflow = _cinematic_default_workflow(
        checkpoint=DEFAULT_ALPHA_CINEMATIC_CHECKPOINT,
        prompt="cinematic test",
        negative_prompt="cartoon",
        seed=123,
        width=432,
        height=768,
        output_prefix="underreach/test",
    )

    assert workflow["1"]["inputs"]["ckpt_name"] == DEFAULT_ALPHA_CINEMATIC_CHECKPOINT
    assert workflow["4"]["inputs"]["width"] == 720
    assert workflow["4"]["inputs"]["height"] == 1280

    sampler = workflow["5"]["inputs"]
    assert sampler["steps"] == 35
    assert sampler["cfg"] == 5.0
    assert sampler["sampler_name"] == "dpmpp_2m"
    assert sampler["scheduler"] == "karras"

    scale = workflow["7"]
    assert scale["class_type"] == "ImageScale"
    assert scale["inputs"]["upscale_method"] == "lanczos"
    assert scale["inputs"]["width"] == 432
    assert scale["inputs"]["height"] == 768
    assert scale["inputs"]["crop"] == "disabled"
