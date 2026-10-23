"""Alpha-only reference-conditioned cinematic ComfyUI image provider.

The generic production image provider stays unchanged. Live Alpha swaps this
subclass in while building the provider stack so stable media-owned delver
references can guide later equipment and scene renders using only core ComfyUI
nodes. Reference images remain non-authoritative presentation state.
"""
from __future__ import annotations

from typing import Any

from .underreach_comfyui_production_image import (
    ALPHA_CINEMATIC_CFG,
    ALPHA_CINEMATIC_SAMPLER,
    ALPHA_CINEMATIC_SCHEDULER,
    ALPHA_CINEMATIC_STEPS,
    ProductionComfyUIImageProvider,
    _alpha_cinematic_enabled,
    _cinematic_checkpoint,
    _cinematic_default_workflow,
    _cinematic_prompts,
    _supersampled_dimensions,
)
from .underreach_headless_local_image_production import ImagePurpose, ImageRenderRequest


ALPHA_EQUIPMENT_REFERENCE_DENOISE = 0.46
ALPHA_SCENE_SETUP_DENOISE = 0.70
ALPHA_SCENE_ACTION_DENOISE = 0.76
ALPHA_SCENE_OUTCOME_DENOISE = 0.73

_ALPHA_IDENTITY_ANCHOR = (
    "stable recurring delver identity reference, neutral three-quarter character portrait, face clearly visible, "
    "uncovered head and unobstructed facial features, no helmet, no mask, readable body silhouette, neutral stance, "
    "plain restrained dungeon backdrop, consistent natural facial geometry and proportions, presentation identity sheet"
)


def _reference_continuity_prompt(prompt: str, *, scene: bool) -> str:
    if scene:
        continuity = (
            "Use the supplied image only as the identity and equipment reference for the exact same recurring character. "
            "Preserve facial structure, age presentation, hair, body proportions, armor silhouette, equipment identity and dominant clothing colors. "
            "Do not copy the reference portrait pose, camera distance, crop or background. Re-stage the character naturally for the requested cinematic scene, "
            "with a visibly different pose and composition while keeping the person recognizably the same"
        )
    else:
        continuity = (
            "Use the supplied image as the exact same recurring character. Preserve facial structure, age presentation, "
            "hair and body proportions while applying only the requested current equipment presentation"
        )
    return f"{continuity}. {prompt}"


def _scene_denoise(prompt: str) -> float:
    lowered = prompt.lower()
    if "alpha presentation beat 1" in lowered or "action beat:" in lowered:
        return ALPHA_SCENE_ACTION_DENOISE
    if "alpha presentation beat 2" in lowered or "outcome beat:" in lowered:
        return ALPHA_SCENE_OUTCOME_DENOISE
    return ALPHA_SCENE_SETUP_DENOISE


def cinematic_reference_workflow(
    *,
    checkpoint: str,
    prompt: str,
    negative_prompt: str,
    seed: int,
    width: int,
    height: int,
    input_image: str,
    output_prefix: str,
    denoise: float,
) -> dict[str, Any]:
    """Core-node img2img workflow for stable Alpha character continuity."""
    generation_width, generation_height = _supersampled_dimensions(width, height)
    return {
        "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": checkpoint}},
        "2": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Positive Prompt"},
            "inputs": {"text": prompt, "clip": ["1", 1]},
        },
        "3": {
            "class_type": "CLIPTextEncode",
            "_meta": {"title": "Negative Prompt"},
            "inputs": {"text": negative_prompt, "clip": ["1", 1]},
        },
        "4": {"class_type": "LoadImage", "inputs": {"image": input_image}},
        "5": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["4", 0],
                "upscale_method": "lanczos",
                "width": generation_width,
                "height": generation_height,
                "crop": "center",
            },
        },
        "6": {"class_type": "VAEEncode", "inputs": {"pixels": ["5", 0], "vae": ["1", 2]}},
        "7": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": ALPHA_CINEMATIC_STEPS,
                "cfg": ALPHA_CINEMATIC_CFG,
                "sampler_name": ALPHA_CINEMATIC_SAMPLER,
                "scheduler": ALPHA_CINEMATIC_SCHEDULER,
                "denoise": denoise,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["6", 0],
            },
        },
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["1", 2]}},
        "9": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["8", 0],
                "upscale_method": "lanczos",
                "width": width,
                "height": height,
                "crop": "disabled",
            },
        },
        "10": {"class_type": "SaveImage", "inputs": {"filename_prefix": output_prefix, "images": ["9", 0]}},
    }


class AlphaContinuityComfyUIImageProvider(ProductionComfyUIImageProvider):
    """Use stable image references for live Alpha when no custom reference graph exists."""

    def _workflow(self, request: ImageRenderRequest) -> dict:
        spec = request.spec
        if not _alpha_cinematic_enabled() or self.config.image_workflow_path is not None:
            return super()._workflow(request)

        if spec.purpose == ImagePurpose.IDENTITY_REFERENCE and not spec.reference_artifact_ids:
            prompt, negative = _cinematic_prompts(_ALPHA_IDENTITY_ANCHOR, spec.negative_prompt)
            negative = f"helmet, mask, face covering, obscured face, cropped head, different people, {negative}"
            return _cinematic_default_workflow(
                checkpoint=_cinematic_checkpoint(),
                prompt=prompt,
                negative_prompt=negative,
                seed=spec.deterministic_seed,
                width=spec.width,
                height=spec.height,
                output_prefix=f"underreach/{spec.spec_id}",
            )

        if not spec.reference_artifact_ids:
            return super()._workflow(request)

        reference_path = self._artifact_path(spec.reference_artifact_ids[0])
        uploaded_reference = self.client.upload_image(reference_path)
        prompt, negative = _cinematic_prompts(spec.prompt, spec.negative_prompt)
        scene = spec.purpose == ImagePurpose.SCENE_STILL
        prompt = _reference_continuity_prompt(prompt, scene=scene)
        negative = f"different person, changed face, changed hair, inconsistent character design, duplicate character, portrait-only framing, static passport pose, {negative}"
        denoise = _scene_denoise(spec.prompt) if scene else ALPHA_EQUIPMENT_REFERENCE_DENOISE
        return cinematic_reference_workflow(
            checkpoint=_cinematic_checkpoint(),
            prompt=prompt,
            negative_prompt=negative,
            seed=spec.deterministic_seed,
            width=spec.width,
            height=spec.height,
            input_image=uploaded_reference,
            output_prefix=f"underreach/{spec.spec_id}",
            denoise=denoise,
        )


__all__ = [
    "ALPHA_EQUIPMENT_REFERENCE_DENOISE",
    "ALPHA_SCENE_SETUP_DENOISE",
    "ALPHA_SCENE_ACTION_DENOISE",
    "ALPHA_SCENE_OUTCOME_DENOISE",
    "AlphaContinuityComfyUIImageProvider",
    "cinematic_reference_workflow",
]
