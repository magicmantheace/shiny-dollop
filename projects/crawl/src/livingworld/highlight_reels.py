from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from .camera_director import AutomatedCameraDirector, CameraPlan
from .commentary_system import CommentaryMode, CommentaryScript, GroundedCommentaryGenerator
from .crawl_domain import Crawl, CrawlEvent
from .story_highlights import StoryArc


class HighlightOutput(StrEnum):
    SHORT_VERTICAL = "short_vertical"
    STANDARD_HORIZONTAL = "standard_horizontal"
    DEEP_STORY = "deep_story"


@dataclass(frozen=True)
class ReplayWindow:
    start_tick: int
    end_tick: int
    source_event_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "source_event_ids": list(self.source_event_ids),
        }


@dataclass(frozen=True)
class EditSegment:
    start_tick: int
    end_tick: int
    camera_mode: str
    target_actor_ids: tuple[str, ...]
    reason_event_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "camera_mode": self.camera_mode,
            "target_actor_ids": list(self.target_actor_ids),
            "reason_event_ids": list(self.reason_event_ids),
        }


@dataclass(frozen=True)
class HighlightPackage:
    id: str
    crawl_id: str
    story_id: str
    story_type: str
    score: float
    replay_window: ReplayWindow
    camera_plan: CameraPlan
    commentary: CommentaryScript
    timeline: tuple[EditSegment, ...]
    outputs: tuple[HighlightOutput, ...]
    render_source: str
    authoritative_event_ids: tuple[str, ...]
    final_state_fingerprint: str
    package_digest: str
    canonical: bool = True

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "crawl_id": self.crawl_id,
            "story_id": self.story_id,
            "story_type": self.story_type,
            "score": round(self.score, 4),
            "canonical": self.canonical,
            "replay_window": self.replay_window.as_dict(),
            "camera_plan": self.camera_plan.as_dict(),
            "commentary": self.commentary.as_dict(),
            "timeline": [segment.as_dict() for segment in self.timeline],
            "outputs": [output.value for output in self.outputs],
            "render_source": self.render_source,
            "authoritative_event_ids": list(self.authoritative_event_ids),
            "final_state_fingerprint": self.final_state_fingerprint,
            "package_digest": self.package_digest,
        }


def _digest(payload: dict) -> str:
    return sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _camera_events_for_story(
    window_events: list[CrawlEvent],
    story: StoryArc,
) -> list[CrawlEvent]:
    """Return presentation-scoped event projections for the camera director.

    The authoritative CrawlEvent objects remain untouched. For highlight-specific
    camera planning, unrelated actors are removed from the *camera target view* so
    broad floor-wide events do not pull the edit away from the story subjects.
    Canonical event IDs, ticks, types, summaries, locations and semantic data are
    preserved, and story events are always retained.
    """

    story_ids = set(story.event_ids)
    participants = set(story.participant_ids)
    if not participants:
        return list(window_events)

    scoped: list[CrawlEvent] = []
    for event in window_events:
        actors = set(event.actor_ids)
        overlap = tuple(sorted(actors.intersection(participants)))
        if event.id not in story_ids and not overlap:
            continue

        # Keep the canonical event envelope while constraining only camera-facing
        # subjects to the actual story participants. This is a presentation
        # projection, not a replacement authoritative event.
        scoped.append(event.model_copy(update={"actor_ids": list(overlap)}))

    return scoped


class HighlightReelAssembler:
    """Build a renderer-neutral highlight package from canonical replay data.

    The package is an edit/render manifest. Unreal or another renderer may consume
    it later; this layer never fabricates footage or changes simulation outcomes.
    """

    def __init__(self, *, pre_roll_ticks: int = 8, post_roll_ticks: int = 8) -> None:
        self.pre_roll_ticks = max(0, pre_roll_ticks)
        self.post_roll_ticks = max(0, post_roll_ticks)
        self.camera_director = AutomatedCameraDirector()
        self.commentary = GroundedCommentaryGenerator()

    def assemble(
        self,
        crawl: Crawl,
        events: Iterable[CrawlEvent],
        story: StoryArc,
        *,
        commentary_mode: CommentaryMode = CommentaryMode.DOCUMENTARY,
        outputs: tuple[HighlightOutput, ...] = (
            HighlightOutput.SHORT_VERTICAL,
            HighlightOutput.STANDARD_HORIZONTAL,
        ),
    ) -> HighlightPackage:
        ordered = sorted(events, key=lambda event: (event.tick, event.id))
        by_id = {event.id: event for event in ordered}
        missing = set(story.event_ids) - set(by_id)
        if missing:
            raise ValueError(f"story references missing authoritative events: {sorted(missing)}")

        start_tick = max(0, story.start_tick - self.pre_roll_ticks)
        end_tick = max(start_tick, story.end_tick + self.post_roll_ticks)
        window_events = [event for event in ordered if start_tick <= event.tick <= end_tick]
        camera_events = _camera_events_for_story(window_events, story)
        primary_actor = story.participant_ids[0] if story.participant_ids else None
        camera = self.camera_director.plan(
            crawl,
            camera_events,
            start_tick=start_tick,
            end_tick=end_tick,
            focus_actor_id=primary_actor,
            max_shots=24,
        )
        commentary = self.commentary.generate(
            ordered,
            story=story,
            mode=commentary_mode,
            max_lines=10,
        )
        timeline = tuple(
            EditSegment(
                start_tick=shot.start_tick,
                end_tick=shot.end_tick,
                camera_mode=shot.mode.value,
                target_actor_ids=shot.target_actor_ids,
                reason_event_ids=shot.reason_event_ids,
            )
            for shot in camera.shots
        )
        authoritative_ids = tuple(story.event_ids)
        render_source = (
            f"replay://{crawl.id}?start_tick={start_tick}&end_tick={end_tick}"
            f"&fingerprint={crawl.fingerprint()}"
        )
        package_id = f"highlight_{sha256((crawl.id + ':' + story.id).encode('utf-8')).hexdigest()[:20]}"
        payload = {
            "id": package_id,
            "crawl_id": crawl.id,
            "story_id": story.id,
            "story_type": story.story_type,
            "score": round(story.score, 4),
            "replay_window": ReplayWindow(start_tick, end_tick, authoritative_ids).as_dict(),
            "camera_digest": camera.digest,
            "commentary_digest": commentary.digest,
            "timeline": [segment.as_dict() for segment in timeline],
            "outputs": [output.value for output in outputs],
            "render_source": render_source,
            "authoritative_event_ids": list(authoritative_ids),
            "final_state_fingerprint": crawl.fingerprint(),
            "canonical": True,
        }
        return HighlightPackage(
            id=package_id,
            crawl_id=crawl.id,
            story_id=story.id,
            story_type=story.story_type,
            score=story.score,
            replay_window=ReplayWindow(start_tick, end_tick, authoritative_ids),
            camera_plan=camera,
            commentary=commentary,
            timeline=timeline,
            outputs=outputs,
            render_source=render_source,
            authoritative_event_ids=authoritative_ids,
            final_state_fingerprint=crawl.fingerprint(),
            package_digest=_digest(payload),
            canonical=True,
        )


def validate_highlight_package(package: HighlightPackage, authoritative_event_ids: set[str]) -> bool:
    package_ids = set(package.authoritative_event_ids)
    if not package_ids or not package_ids.issubset(authoritative_event_ids):
        return False
    if not set(package.commentary.source_event_ids).issubset(package_ids):
        return False
    if any(not set(segment.reason_event_ids).issubset(authoritative_event_ids) for segment in package.timeline):
        return False
    return package.canonical and package.render_source.startswith("replay://")
