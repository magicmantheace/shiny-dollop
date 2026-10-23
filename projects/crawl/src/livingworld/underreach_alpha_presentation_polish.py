"""Alpha-only viewer presentation helpers.

These helpers transform accepted media-owned facts and image specs into a more
coherent viewer presentation. They never alter canonical Crawl state and never
change the exact ClaimSpec values used by deterministic narrative verification.
"""
from __future__ import annotations

from hashlib import sha256
import re
from typing import Any

from .runtime_checkpoint import payload_digest
from .underreach_headless_local_image_production import ImageProductionSpec
from .underreach_media_event_export import AllowedFact


MAX_VIEWER_SENTENCE_CHARS = 68
ALPHA_SCENE_STAGING = (
    "Setup beat: wide environmental three-quarter shot, show the same delver from roughly knees-up or full body inside the surrounding dungeon; place the face away from the exact center, reveal architecture and spatial danger, use a clearly different camera distance from the identity portrait, restrained tension, no new event.",
    "Action beat: dynamic medium-wide combat composition of the exact same delver; change pose, body angle and camera position substantially from the setup shot, show active movement around the canonical action, keep face recognizable when visible, preserve armor silhouette and colors, do not copy the reference portrait framing.",
    "Outcome beat: distinct aftermath composition of the exact same delver; use a different camera angle and distance from both prior shots, calmer posture and lowered tension, reveal changed surrounding staging implied by the completed event, preserve face/equipment identity, no invented reward or injury.",
)

_INTERNAL_ID = re.compile(
    r"\b(?:live_descender|descender|crawler|event|fact|envelope|sector|location|party|alliance|"
    r"profile|chapter|highlight|identity|reference|crawl)_[A-Za-z0-9_-]+\b",
    re.IGNORECASE,
)
_INTERNAL_HASH = re.compile(r"\b[a-f0-9]{16,}\b", re.IGNORECASE)
_DEBUG_WORD = re.compile(r"\b(?:id|digest|hash|flag|predicate|payload|semantic|canonical record)\b", re.IGNORECASE)


def _compact_sentence(text: str) -> str:
    value = " ".join(text.split()).strip()
    if not value:
        return "The crawl recorded another development."
    if not value.endswith((".", "!", "?")):
        value += "."
    if len(value) <= MAX_VIEWER_SENTENCE_CHARS:
        return value
    return "The crawl recorded another development."


def _scrub_summary(text: str) -> str:
    value = text.replace("Canonical record:", "").replace("canonical record:", "")
    value = _INTERNAL_ID.sub("", value)
    value = _INTERNAL_HASH.sub("", value)
    value = re.sub(r"\s+([,.;:!?])", r"\1", value)
    value = re.sub(r"\s{2,}", " ", value).strip(" -,:;")
    return value


def render_alpha_viewer_sentence(fact: AllowedFact) -> str:
    """Return short viewer prose whose wording never exceeds its AllowedFact."""
    predicate = fact.predicate.lower().strip()
    value = str(fact.value).upper() if isinstance(fact.value, str) else ""
    if predicate == "event_type":
        mapping = {
            "COMBAT_STARTED": "Combat began in the dungeon.",
            "COMBAT_HIT": "A hit landed during the fight.",
            "COMBAT_ENDED": "The fighting came to an end.",
            "ENEMY_DEFEATED": "An enemy was defeated in the battle.",
            "ENCOUNTER_TRIGGERED": "An encounter began in the dungeon.",
            "ENCOUNTER_RESOLVED": "The encounter came to an end.",
            "ITEM_ACQUIRED": "The delver acquired a new item.",
            "GROUND_LOOT_ACQUIRED": "The delver recovered an item from the dungeon floor.",
            "ITEM_CONSUMED": "The delver consumed a carried item.",
            "PARTY_FORMED": "A new party formed.",
            "ALLIANCE_FORMED": "A new alliance formed.",
            "CRAWLER_ADVANCED": "The delver advanced through the crawl.",
            "CRAWLER_MOVED": "The delver moved through the dungeon.",
            "LOCATION_DISCOVERED": "The delver discovered a new location.",
            "LEVEL_GAINED": "The delver gained a level.",
            "ABILITY_UNLOCKED": "The delver unlocked a new ability.",
            "FLOOR_ADVANCED": "The delver advanced to another floor.",
            "STRATUM_ADVANCED": "The delver advanced to another stratum.",
            "VICTORY": "The delver recorded a victory.",
            "ATTACK": "An attack was made during the fight.",
            "DAMAGE": "Damage was dealt during the fight.",
        }
        return mapping.get(value, "The crawl recorded another development.")
    if predicate in {"summary", "event_summary"} and isinstance(fact.value, str):
        summary = _scrub_summary(fact.value)
        if summary and len(summary) <= 62 and not _DEBUG_WORD.search(summary):
            return _compact_sentence(summary)
        return "The crawl recorded another development."
    if predicate in {"stratum", "floor"}:
        return "The delver advanced through the crawl."
    if predicate in {"sector", "location_id", "location"}:
        return "The delver entered another recorded location."
    if predicate in {"item", "item_name", "loot", "equipment"}:
        return "The delver acquired recorded equipment."
    if predicate in {"party", "party_status", "party_id", "alliance"}:
        return "The delver's group status changed."
    if predicate in {"level", "rank", "advancement", "progression"}:
        return "The delver recorded new progression."
    return "The crawl recorded another development."


def alpha_scene_variant_spec(base: ImageProductionSpec, variant_index: int, staging: str) -> ImageProductionSpec:
    """Create a deterministic scene beat while retaining reference provenance."""
    seed_material = f"{base.deterministic_seed}:alpha-continuity-scene-v3:{variant_index}"
    seed = int(sha256(seed_material.encode("utf-8")).hexdigest()[:15], 16)
    identity_material = ":".join(
        str(part)
        for part in (
            base.purpose.value,
            base.identity_id,
            base.equipment_revision_id or "identity-static",
            base.reference_id or base.chapter_id or "none",
            seed,
            base.width,
            base.height,
            base.prompt_template_version,
            base.policy_digest,
        )
    )
    spec_id = f"image_spec_{sha256(identity_material.encode('utf-8')).hexdigest()[:24]}"
    body = base.model_dump(mode="json", exclude={"digest"})
    body["spec_id"] = spec_id
    body["deterministic_seed"] = seed
    body["prompt"] = f"{base.prompt} Alpha presentation beat {variant_index}: {staging}"
    return ImageProductionSpec.model_validate({**body, "digest": payload_digest(body)})


def with_reference_artifacts(spec: ImageProductionSpec, artifact_ids: tuple[str, ...]) -> ImageProductionSpec:
    """Attach normalized media reference provenance without changing gameplay facts."""
    body = spec.model_dump(mode="json", exclude={"digest"})
    body["reference_artifact_ids"] = list(sorted(set(artifact_ids)))
    return ImageProductionSpec.model_validate({**body, "digest": payload_digest(body)})


def find_reference_artifact(
    snapshot: dict[str, Any], *, identity_id: str, reference_id: str
) -> str | None:
    matches = [
        artifact
        for artifact in snapshot.get("artifacts", ())
        if artifact.get("artifact_kind") == "image/png"
        and (artifact.get("metadata") or {}).get("identity_id") == identity_id
        and (artifact.get("metadata") or {}).get("reference_id") == reference_id
    ]
    if not matches:
        return None
    return sorted(matches, key=lambda item: item["artifact_id"])[-1]["artifact_id"]


def reorder_motion_story_shots(spec, ordered_image_ids: tuple[str, ...]):
    """Keep normalized inputs but present shots in semantic setup/action/outcome order."""
    ordered = tuple(dict.fromkeys(ordered_image_ids))
    allowed = {item.artifact_id for item in spec.image_inputs}
    if not ordered or not set(ordered).issubset(allowed):
        return spec
    rewritten = []
    for index, shot in enumerate(spec.shots):
        body = shot.model_dump(mode="json", exclude={"digest"})
        body["source_image_artifact_id"] = ordered[index % len(ordered)]
        rewritten.append(shot.__class__.model_validate({**body, "digest": payload_digest(body)}))
    body = spec.model_dump(mode="json", exclude={"digest"})
    body["shots"] = [item.model_dump(mode="json") for item in rewritten]
    return spec.__class__.model_validate({**body, "digest": payload_digest(body)})


__all__ = [
    "ALPHA_SCENE_STAGING",
    "MAX_VIEWER_SENTENCE_CHARS",
    "alpha_scene_variant_spec",
    "find_reference_artifact",
    "render_alpha_viewer_sentence",
    "reorder_motion_story_shots",
    "with_reference_artifacts",
]
