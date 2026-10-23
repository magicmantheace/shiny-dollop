"""Production image policy wrapper for the concrete ComfyUI still provider.

Accepted 30.5.7 image specs may carry reference artifacts without requiring a
reference-capable provider. Production should use a reference graph when one is
configured, but a missing reference graph must not make a valid still job fail;
the ordinary checkpoint graph remains a prompt-only production path.

The live Alpha worker sets ``UNDERREACH_ALPHA_VIEWER_FACING=true``. In that
process only, this wrapper upgrades still rendering to a cinematic SDXL profile:
a photorealistic Juggernaut XL checkpoint, model-recommended DPM++ 2M Karras
sampling, and bounded supersampling before final downscale. Generated pixels
remain non-authoritative presentation state.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
from typing import Any

from .underreach_comfyui_providers import (
    ComfyUIImageProvider,
    ComfyUIProviderError,
    _default_image_workflow,
    _load_workflow,
    _patch_workflow,
)
from .underreach_headless_local_image_production import ImageRenderRequest


ALPHA_VIEWER_FACING_ENV = "UNDERREACH_ALPHA_VIEWER_FACING"
ALPHA_CINEMATIC_CHECKPOINT_ENV = "UNDERREACH_ALPHA_CINEMATIC_CHECKPOINT"
DEFAULT_ALPHA_CINEMATIC_CHECKPOINT = "Juggernaut-XL_v9_RunDiffusionPhoto_v2.safetensors"
ALPHA_CINEMATIC_STEPS = 35
ALPHA_CINEMATIC_CFG = 5.0
ALPHA_CINEMATIC_SAMPLER = "dpmpp_2m"
ALPHA_CINEMATIC_SCHEDULER = "karras"
ALPHA_CINEMATIC_TARGET_PIXELS = 720 * 1280


_CINEMATIC_POSITIVE = (
    "cinematic movie still, photorealistic dark fantasy, hyperdetailed photography, "
    "realistic human anatomy, believable proportions, natural skin texture, physically based materials, "
    "weathered practical medieval equipment, detailed stone and fabric texture, dramatic practical torchlight, "
    "volumetric dust and mist, wet stone reflections, deep natural shadows, subtle film grain, "
    "35mm cinema lens, shallow depth of field, grounded color grading, coherent perspective, believable scale"
)

# Juggernaut generally prefers light negative prompting. Keep this targeted at the
# failure modes visible in Alpha output rather than stacking broad quality tokens.
_CINEMATIC_NEGATIVE = (
    "cartoon, anime, childish drawing, crayon, sketch, watercolor, flat illustration, "
    "plastic skin, doll face, malformed anatomy, extra limbs, duplicated body parts, "
    "bad hands, extra fingers, flat lighting, oversaturated colors, text, watermark, logo, UI"
)


def _alpha_cinematic_enabled() -> bool:
    return os.environ.get(ALPHA_VIEWER_FACING_ENV, "").strip().lower() in {"1", "true", "yes", "on"}


def _cinematic_checkpoint() -> str:
    configured = os.environ.get(ALPHA_CINEMATIC_CHECKPOINT_ENV, "").strip()
    return configured or DEFAULT_ALPHA_CINEMATIC_CHECKPOINT


def _contains_string(value: Any, needle: str) -> bool:
    if isinstance(value, str):
        return value == needle
    if isinstance(value, dict):
        return any(_contains_string(item, needle) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_string(item, needle) for item in value)
    return False


def _cinematic_prompts(prompt: str, negative_prompt: str) -> tuple[str, str]:
    positive = f"{_CINEMATIC_POSITIVE}. {prompt.strip()}"
    existing_negative = negative_prompt.strip().strip(",")
    negative = _CINEMATIC_NEGATIVE
    if existing_negative:
        negative = f"{negative}, {existing_negative}"
    return positive, negative


def _supersampled_dimensions(width: int, height: int) -> tuple[int, int]:
    """Scale a target frame toward ~0.92 MP while preserving aspect ratio.

    432x768 becomes 720x1280. Square 512x512 frames become 960x960. Dimensions
    remain multiples of eight for ordinary SDXL/ComfyUI latent nodes.
    """
    area = max(1, width * height)
    if area >= ALPHA_CINEMATIC_TARGET_PIXELS:
        return width, height
    scale = math.sqrt(ALPHA_CINEMATIC_TARGET_PIXELS / area)
    generation_width = max(width, int(round((width * scale) / 8.0)) * 8)
    generation_height = max(height, int(round((height * scale) / 8.0)) * 8)
    return generation_width, generation_height


def _cinematic_default_workflow(
    *,
    checkpoint: str,
    prompt: str,
    negative_prompt: str,
    seed: int,
    width: int,
    height: int,
    output_prefix: str,
) -> dict[str, Any]:
    """Core-node SDXL graph: supersample, decode, then Lanczos downscale.

    No custom nodes or separate upscaler model are required. This keeps the
    quality pass portable on the existing ComfyUI install and bounded for the
    RTX 3060 12 GB/--lowvram target.
    """
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
        "4": {
            "class_type": "EmptyLatentImage",
            "inputs": {"width": generation_width, "height": generation_height, "batch_size": 1},
        },
        "5": {
            "class_type": "KSampler",
            "inputs": {
                "seed": seed,
                "steps": ALPHA_CINEMATIC_STEPS,
                "cfg": ALPHA_CINEMATIC_CFG,
                "sampler_name": ALPHA_CINEMATIC_SAMPLER,
                "scheduler": ALPHA_CINEMATIC_SCHEDULER,
                "denoise": 1.0,
                "model": ["1", 0],
                "positive": ["2", 0],
                "negative": ["3", 0],
                "latent_image": ["4", 0],
            },
        },
        "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {
            "class_type": "ImageScale",
            "inputs": {
                "image": ["6", 0],
                "upscale_method": "lanczos",
                "width": width,
                "height": height,
                "crop": "disabled",
            },
        },
        "8": {"class_type": "SaveImage", "inputs": {"filename_prefix": output_prefix, "images": ["7", 0]}},
    }


class ProductionComfyUIImageProvider(ComfyUIImageProvider):
    """Choose reference-conditioned, cinematic Alpha, or normal Comfy graphs."""

    def health(self) -> dict[str, Any]:
        status = super().health()
        if not _alpha_cinematic_enabled() or not status.get("ready"):
            return status
        checkpoint = _cinematic_checkpoint()
        try:
            inventory = self.client.object_info()
            checkpoint_ready = _contains_string(inventory.get("CheckpointLoaderSimple", {}), checkpoint)
        except Exception as exc:
            return {
                **status,
                "ready": False,
                "cinematic_checkpoint": checkpoint,
                "cinematic_checkpoint_ready": False,
                "cinematic_inventory_error": f"{type(exc).__name__}: {exc}",
            }
        return {
            **status,
            "ready": bool(status.get("ready")) and checkpoint_ready,
            "cinematic_checkpoint": checkpoint,
            "cinematic_checkpoint_ready": checkpoint_ready,
            "cinematic_quality_profile": "juggernaut_xl_v9_supersampled",
            "cinematic_steps": ALPHA_CINEMATIC_STEPS,
            "cinematic_cfg": ALPHA_CINEMATIC_CFG,
            "cinematic_sampler": ALPHA_CINEMATIC_SAMPLER,
            "cinematic_scheduler": ALPHA_CINEMATIC_SCHEDULER,
        }

    def _workflow(self, request: ImageRenderRequest) -> dict:
        spec = request.spec
        prefix = f"underreach/{spec.spec_id}"
        cinematic = _alpha_cinematic_enabled()
        checkpoint = _cinematic_checkpoint() if cinematic else self.config.image_checkpoint
        prompt, negative_prompt = (
            _cinematic_prompts(spec.prompt, spec.negative_prompt)
            if cinematic
            else (spec.prompt, spec.negative_prompt)
        )

        # A configured custom workflow is reserved for reference-bearing jobs.
        # It may contain LoadImage/IPAdapter/InstantID/etc. The generic static
        # portrait path should not be forced through nodes that require an input.
        if spec.reference_artifact_ids and self.config.image_workflow_path is not None:
            reference_path = self._artifact_path(spec.reference_artifact_ids[0])
            uploaded_reference = self.client.upload_image(reference_path)
            base = _load_workflow(self.config.image_workflow_path)
            generation_width, generation_height = (
                _supersampled_dimensions(spec.width, spec.height)
                if cinematic
                else (spec.width, spec.height)
            )
            return _patch_workflow(
                base,
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=spec.deterministic_seed,
                width=spec.width,
                height=spec.height,
                generation_width=generation_width,
                generation_height=generation_height,
                frames=1,
                fps=1,
                input_image=uploaded_reference,
                output_prefix=prefix,
                checkpoint=checkpoint,
                image_steps=ALPHA_CINEMATIC_STEPS if cinematic else self.config.image_steps,
                image_cfg=ALPHA_CINEMATIC_CFG if cinematic else self.config.image_cfg,
                image_sampler=ALPHA_CINEMATIC_SAMPLER if cinematic else self.config.image_sampler,
                image_scheduler=ALPHA_CINEMATIC_SCHEDULER if cinematic else self.config.image_scheduler,
            )

        # Live Alpha gets a high-detail core-node graph even though the persisted
        # semantic spec remains at the final 432x768/identity target dimensions.
        # The temporary larger latent is presentation-only and is downsampled back
        # to the requested artifact size before persistence.
        if cinematic:
            return _cinematic_default_workflow(
                checkpoint=checkpoint,
                prompt=prompt,
                negative_prompt=negative_prompt,
                seed=spec.deterministic_seed,
                width=spec.width,
                height=spec.height,
                output_prefix=prefix,
            )

        # The ordinary path intentionally ignores optional reference provenance
        # when no reference graph is installed. 30.5.7 did not mark reference
        # conditioning as required, so this is a valid graceful degradation.
        if self.config.image_checkpoint:
            return _default_image_workflow(
                checkpoint=self.config.image_checkpoint,
                prompt=spec.prompt,
                negative_prompt=spec.negative_prompt,
                seed=spec.deterministic_seed,
                width=spec.width,
                height=spec.height,
                steps=self.config.image_steps,
                cfg=self.config.image_cfg,
                sampler=self.config.image_sampler,
                scheduler=self.config.image_scheduler,
                output_prefix=prefix,
            )

        # If the user supplied only a custom workflow, allow it for non-reference
        # jobs as long as it is itself a valid standalone graph.
        if self.config.image_workflow_path is not None and not spec.reference_artifact_ids:
            base = _load_workflow(self.config.image_workflow_path)
            return _patch_workflow(
                base,
                prompt=spec.prompt,
                negative_prompt=spec.negative_prompt,
                seed=spec.deterministic_seed,
                width=spec.width,
                height=spec.height,
                generation_width=spec.width,
                generation_height=spec.height,
                frames=1,
                fps=1,
                input_image=None,
                output_prefix=prefix,
                checkpoint=None,
                image_steps=self.config.image_steps,
                image_cfg=self.config.image_cfg,
                image_sampler=self.config.image_sampler,
                image_scheduler=self.config.image_scheduler,
            )

        raise ComfyUIProviderError("production Comfy image provider requires image_checkpoint or image_workflow_path")


__all__ = [
    "ALPHA_CINEMATIC_CFG",
    "ALPHA_CINEMATIC_SAMPLER",
    "ALPHA_CINEMATIC_SCHEDULER",
    "ALPHA_CINEMATIC_STEPS",
    "DEFAULT_ALPHA_CINEMATIC_CHECKPOINT",
    "ProductionComfyUIImageProvider",
    "_cinematic_default_workflow",
    "_cinematic_prompts",
    "_supersampled_dimensions",
]
