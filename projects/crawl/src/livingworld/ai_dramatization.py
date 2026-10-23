from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from .crawl_domain import CrawlEvent
from .highlight_reels import HighlightPackage


@dataclass(frozen=True)
class DramatizationScene:
    scene_id: str
    source_event_ids: tuple[str, ...]
    prompt: str
    canonical: bool = False

    def as_dict(self) -> dict:
        return {
            "scene_id": self.scene_id,
            "source_event_ids": list(self.source_event_ids),
            "prompt": self.prompt,
            "canonical": self.canonical,
        }


@dataclass(frozen=True)
class DramatizationJob:
    id: str
    highlight_id: str
    crawl_id: str
    relationship_to_canonical_replay: str
    provider: str
    model: str | None
    scenes: tuple[DramatizationScene, ...]
    source_event_ids: tuple[str, ...]
    digest: str
    canonical: bool = False

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "highlight_id": self.highlight_id,
            "crawl_id": self.crawl_id,
            "relationship_to_canonical_replay": self.relationship_to_canonical_replay,
            "provider": self.provider,
            "model": self.model,
            "canonical": self.canonical,
            "source_event_ids": list(self.source_event_ids),
            "digest": self.digest,
            "scenes": [scene.as_dict() for scene in self.scenes],
        }


def _digest(payload: dict) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _scene_prompt(events: list[CrawlEvent], highlight: HighlightPackage) -> str:
    event_bits = []
    for event in events:
        actors = ", ".join(event.actor_ids) if event.actor_ids else "no named crawler"
        event_bits.append(
            f"tick {event.tick}: {event.event_type} involving {actors}; canonical summary: {event.summary}"
        )
    facts = " | ".join(event_bits)
    return (
        "Create a cinematic dramatization of the following canonical Crawl events. "
        "Do not change who participated, the order of events, the outcome, deaths, injuries, items, or floor result. "
        "This is a stylized non-canonical visualization, not authoritative replay. "
        f"Highlight type: {highlight.story_type}. Canonical facts: {facts}"
    )


class DramatizationPlanner:
    """Creates optional non-canonical generation jobs; it does not call a video model."""

    def build_job(
        self,
        highlight: HighlightPackage,
        events: Iterable[CrawlEvent],
        *,
        provider: str = "unassigned",
        model: str | None = None,
        max_events_per_scene: int = 4,
    ) -> DramatizationJob:
        by_id = {event.id: event for event in events}
        missing = set(highlight.authoritative_event_ids) - set(by_id)
        if missing:
            raise ValueError(f"highlight references missing events: {sorted(missing)}")
        ordered = [by_id[event_id] for event_id in highlight.authoritative_event_ids]
        ordered.sort(key=lambda event: (event.tick, event.id))
        scene_size = max(1, max_events_per_scene)
        scenes: list[DramatizationScene] = []
        for index in range(0, len(ordered), scene_size):
            chunk = ordered[index:index + scene_size]
            source_ids = tuple(event.id for event in chunk)
            scene_id = f"drama_scene_{sha256((':'.join(source_ids)).encode('utf-8')).hexdigest()[:16]}"
            scenes.append(
                DramatizationScene(
                    scene_id=scene_id,
                    source_event_ids=source_ids,
                    prompt=_scene_prompt(chunk, highlight),
                    canonical=False,
                )
            )
        job_id = f"drama_{sha256((highlight.id + ':' + provider + ':' + str(model)).encode('utf-8')).hexdigest()[:20]}"
        payload = {
            "id": job_id,
            "highlight_id": highlight.id,
            "crawl_id": highlight.crawl_id,
            "relationship_to_canonical_replay": "optional_stylized_interpretation",
            "provider": provider,
            "model": model,
            "canonical": False,
            "source_event_ids": list(highlight.authoritative_event_ids),
            "scenes": [scene.as_dict() for scene in scenes],
        }
        return DramatizationJob(
            id=job_id,
            highlight_id=highlight.id,
            crawl_id=highlight.crawl_id,
            relationship_to_canonical_replay="optional_stylized_interpretation",
            provider=provider,
            model=model,
            scenes=tuple(scenes),
            source_event_ids=highlight.authoritative_event_ids,
            digest=_digest(payload),
            canonical=False,
        )


def validate_dramatization_job(job: DramatizationJob, authoritative_event_ids: set[str]) -> bool:
    if job.canonical:
        return False
    if job.relationship_to_canonical_replay != "optional_stylized_interpretation":
        return False
    if not set(job.source_event_ids).issubset(authoritative_event_ids):
        return False
    if any(scene.canonical or not set(scene.source_event_ids).issubset(authoritative_event_ids) for scene in job.scenes):
        return False
    return bool(job.scenes)
