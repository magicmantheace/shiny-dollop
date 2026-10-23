from __future__ import annotations

import json
import math
from dataclasses import dataclass
from hashlib import sha256
from typing import Iterable

from .camera_director import CameraPlan
from .crawl_domain import Crawl, CrawlEvent

STAGING_PROTOCOL = "crawl.presentation-stage.v1"

_DIRECT_INTERACTION_TYPES = {
    "COMBAT_HIT",
    "CRAWLER_DAMAGED",
    "CRAWLER_INJURED",
    "ENEMY_DEFEATED",
    "CRAWLER_DIED",
    "CRAWLER_ELIMINATED",
    "CRAWLER_RETREATED",
    "RESCUE",
    "NEAR_DEATH",
}


@dataclass(frozen=True)
class Transform3D:
    x: float
    y: float
    z: float = 90.0
    yaw: float = 0.0

    def as_dict(self) -> dict:
        return {
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "z": round(self.z, 3),
            "yaw": round(self.yaw, 3),
        }


@dataclass(frozen=True)
class StagedActor:
    actor_id: str
    actor_kind: str
    display_name: str
    initial_transform: Transform3D
    scale: float
    visual_key: str

    def as_dict(self) -> dict:
        return {
            "actor_id": self.actor_id,
            "actor_kind": self.actor_kind,
            "display_name": self.display_name,
            "initial_transform": self.initial_transform.as_dict(),
            "scale": round(self.scale, 3),
            "visual_key": self.visual_key,
        }


@dataclass(frozen=True)
class PresentationBeat:
    id: str
    event_id: str
    event_type: str
    canonical_tick: int
    start_seconds: float
    duration_seconds: float
    action: str
    actor_ids: tuple[str, ...]
    performer_id: str | None
    target_id: str | None
    location_id: str | None
    canonical_summary: str

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "canonical_tick": self.canonical_tick,
            "start_seconds": round(self.start_seconds, 3),
            "duration_seconds": round(self.duration_seconds, 3),
            "action": self.action,
            "actor_ids": list(self.actor_ids),
            "performer_id": self.performer_id,
            "target_id": self.target_id,
            "location_id": self.location_id,
            "canonical_summary": self.canonical_summary,
        }


@dataclass(frozen=True)
class PresentationCameraCue:
    mode: str
    start_seconds: float
    end_seconds: float
    target_actor_ids: tuple[str, ...]
    reason_event_ids: tuple[str, ...]

    def as_dict(self) -> dict:
        return {
            "mode": self.mode,
            "start_seconds": round(self.start_seconds, 3),
            "end_seconds": round(self.end_seconds, 3),
            "target_actor_ids": list(self.target_actor_ids),
            "reason_event_ids": list(self.reason_event_ids),
        }


@dataclass(frozen=True)
class PresentationStagingManifest:
    protocol: str
    crawl_id: str
    floor_number: int
    presentation_seed: str
    source_event_ids: tuple[str, ...]
    source_fingerprint: str
    actors: tuple[StagedActor, ...]
    beats: tuple[PresentationBeat, ...]
    camera_cues: tuple[PresentationCameraCue, ...]
    duration_seconds: float
    digest: str
    authoritative: bool = False

    def as_dict(self) -> dict:
        return {
            "protocol": self.protocol,
            "crawl_id": self.crawl_id,
            "floor_number": self.floor_number,
            "presentation_seed": self.presentation_seed,
            "authoritative": self.authoritative,
            "authority_contract": {
                "canonical_source": "crawl_event_ledger",
                "presentation_may": [
                    "choose_stage_coordinates",
                    "choose_animation_duration",
                    "interpolate_motion",
                    "choose_camera_placement",
                    "render_non_authoritative_geometry",
                ],
                "presentation_must_not": [
                    "change_event_order",
                    "change_event_outcome",
                    "change_participants",
                    "change_health",
                    "create_canonical_events",
                ],
            },
            "source_event_ids": list(self.source_event_ids),
            "source_fingerprint": self.source_fingerprint,
            "actors": [actor.as_dict() for actor in self.actors],
            "beats": [beat.as_dict() for beat in self.beats],
            "camera_cues": [cue.as_dict() for cue in self.camera_cues],
            "duration_seconds": round(self.duration_seconds, 3),
            "digest": self.digest,
        }


def _digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


def _canonical_order(crawl: Crawl, events: Iterable[CrawlEvent]) -> list[CrawlEvent]:
    history_order = {event_id: index for index, event_id in enumerate(crawl.history_event_ids)}
    return sorted(
        events,
        key=lambda event: (
            event.tick,
            history_order.get(event.id, len(history_order) + 1),
            event.id,
        ),
    )


def _duration(event_type: str) -> float:
    event_type = event_type.upper()
    if event_type in {"COMBAT_STARTED", "COMBAT_ENDED", "ENCOUNTER_RESOLVED"}:
        return 1.4
    if event_type in {"COMBAT_HIT", "CRAWLER_DAMAGED"}:
        return 0.75
    if event_type in {"CRAWLER_INJURED", "NEAR_DEATH"}:
        return 1.0
    if event_type in {"ENEMY_DEFEATED", "CRAWLER_DIED", "CRAWLER_ELIMINATED"}:
        return 1.25
    if event_type in {"CRAWLER_RETREATED", "RESCUE"}:
        return 1.35
    if "MOVED" in event_type or "ADVANCED" in event_type:
        return 1.1
    return 0.9


def _action_and_roles(event: CrawlEvent) -> tuple[str, str | None, str | None]:
    event_type = event.event_type.upper()
    actor_ids = tuple(str(actor_id) for actor_id in event.actor_ids)

    if event_type == "COMBAT_HIT":
        return "attack_hit", actor_ids[0] if actor_ids else None, actor_ids[1] if len(actor_ids) > 1 else None
    if event_type == "CRAWLER_DAMAGED":
        return "attack_hit", actor_ids[1] if len(actor_ids) > 1 else None, actor_ids[0] if actor_ids else None
    if event_type == "CRAWLER_INJURED":
        return "injury_reaction", actor_ids[1] if len(actor_ids) > 1 else None, actor_ids[0] if actor_ids else None
    if event_type == "ENEMY_DEFEATED":
        return "defeat", actor_ids[0] if actor_ids else None, actor_ids[1] if len(actor_ids) > 1 else None
    if event_type in {"CRAWLER_DIED", "CRAWLER_ELIMINATED"}:
        return "death", None, actor_ids[0] if actor_ids else None
    if event_type == "CRAWLER_RETREATED":
        return "retreat", actor_ids[0] if actor_ids else None, None
    if event_type == "RESCUE":
        return "rescue", actor_ids[1] if len(actor_ids) > 1 else (actor_ids[0] if actor_ids else None), actor_ids[0] if actor_ids else None
    if event_type == "NEAR_DEATH":
        return "near_death", None, actor_ids[0] if actor_ids else None
    if event_type == "COMBAT_STARTED":
        return "combat_start", actor_ids[0] if actor_ids else None, None
    if event_type == "COMBAT_ENDED":
        return "combat_end", actor_ids[0] if actor_ids else None, None
    if "MOVED" in event_type or "ADVANCED" in event_type:
        return "move", actor_ids[0] if actor_ids else None, None
    return "observe", actor_ids[0] if actor_ids else None, actor_ids[1] if len(actor_ids) > 1 else None


def _stage_transform(index: int, count: int, actor_kind: str, token: str) -> Transform3D:
    count = max(1, count)
    phase = (int(sha256(token.encode("utf-8")).hexdigest()[:8], 16) % 1000) / 1000.0
    angle = (2.0 * math.pi * index / count) + phase * 0.35
    radius = 340.0 if actor_kind == "crawler" else 230.0
    x = math.cos(angle) * radius
    y = math.sin(angle) * radius
    yaw = math.degrees(math.atan2(-y, -x))
    return Transform3D(x=x, y=y, z=90.0, yaw=yaw)


def _append_unique(candidate_ids: list[str], actor_ids: Iterable[str], max_actors: int) -> bool:
    for actor_id in actor_ids:
        actor_id = str(actor_id)
        if actor_id not in candidate_ids:
            candidate_ids.append(actor_id)
        if len(candidate_ids) >= max_actors:
            return True
    return False


class PresentationStagingResolver:
    """Turn canonical Crawl events into deterministic, presentation-only 3D staging.

    The resolver owns coordinates and animation timing only. Event participants,
    order, outcomes, and summaries remain sourced from the authoritative ledger.
    """

    def __init__(self, *, pre_roll_seconds: float = 2.0, post_roll_seconds: float = 2.0, max_actors: int = 8) -> None:
        self.pre_roll_seconds = max(0.0, pre_roll_seconds)
        self.post_roll_seconds = max(0.0, post_roll_seconds)
        self.max_actors = max(2, max_actors)

    def resolve(
        self,
        crawl: Crawl,
        events: Iterable[CrawlEvent],
        *,
        focus_actor_ids: Iterable[str] = (),
        camera_plan: CameraPlan | None = None,
        presentation_seed: str | None = None,
    ) -> PresentationStagingManifest:
        ordered = _canonical_order(crawl, events)
        if not ordered:
            raise ValueError("at least one canonical event is required for staging")

        focus = tuple(dict.fromkeys(str(actor_id) for actor_id in focus_actor_ids))
        candidate_ids: list[str] = list(focus[: self.max_actors])
        focus_set = set(focus)

        # First pass: direct action/reaction partners. This prevents a broad
        # COMBAT_STARTED event from filling a personal replay with background
        # crawlers before the actual attacker/target is considered.
        if len(candidate_ids) < self.max_actors:
            for event in ordered:
                event_ids = [str(actor_id) for actor_id in event.actor_ids]
                if event.event_type.upper() not in _DIRECT_INTERACTION_TYPES:
                    continue
                if focus_set and not set(event_ids).intersection(focus_set):
                    continue
                if _append_unique(candidate_ids, event_ids, self.max_actors):
                    break

        # Second pass: fill remaining presentation slots with contextual actors
        # involved in events that also contain a focus subject.
        if len(candidate_ids) < self.max_actors:
            for event in ordered:
                event_ids = [str(actor_id) for actor_id in event.actor_ids]
                if focus_set and not set(event_ids).intersection(focus_set):
                    continue
                if _append_unique(candidate_ids, event_ids, self.max_actors):
                    break

        # If there is no explicit focus, or no focus-related actors were found,
        # take the first canonical actors in stable event order.
        if not candidate_ids:
            for event in ordered:
                if _append_unique(candidate_ids, (str(actor_id) for actor_id in event.actor_ids), self.max_actors):
                    break

        stage_actor_ids = tuple(candidate_ids[: self.max_actors])
        stage_actor_set = set(stage_actor_ids)
        seed = presentation_seed or f"{crawl.seed}:{ordered[0].id}:{ordered[-1].id}"

        actors: list[StagedActor] = []
        for index, actor_id in enumerate(stage_actor_ids):
            actor_kind = "crawler" if actor_id in crawl.participants else "enemy"
            actors.append(
                StagedActor(
                    actor_id=actor_id,
                    actor_kind=actor_kind,
                    display_name=actor_id,
                    initial_transform=_stage_transform(index, len(stage_actor_ids), actor_kind, f"{seed}:{actor_id}"),
                    scale=1.0 if actor_kind == "crawler" else 1.18,
                    visual_key="crawler" if actor_kind == "crawler" else "enemy",
                )
            )

        selected_events = [
            event
            for event in ordered
            if set(str(actor_id) for actor_id in event.actor_ids).intersection(stage_actor_set)
            or event.event_type.upper() in {"COMBAT_STARTED", "COMBAT_ENDED", "ENCOUNTER_RESOLVED"}
        ]
        if not selected_events:
            selected_events = ordered[:1]

        beats: list[PresentationBeat] = []
        cursor = self.pre_roll_seconds
        for event in selected_events:
            action, performer_id, target_id = _action_and_roles(event)
            visible_ids = tuple(str(actor_id) for actor_id in event.actor_ids if str(actor_id) in stage_actor_set)
            performer_id = performer_id if performer_id in stage_actor_set else None
            target_id = target_id if target_id in stage_actor_set else None
            duration = _duration(event.event_type)
            beat_id = "beat_" + sha256(f"{event.id}:{action}".encode("utf-8")).hexdigest()[:16]
            beats.append(
                PresentationBeat(
                    id=beat_id,
                    event_id=event.id,
                    event_type=event.event_type,
                    canonical_tick=event.tick,
                    start_seconds=cursor,
                    duration_seconds=duration,
                    action=action,
                    actor_ids=visible_ids,
                    performer_id=performer_id,
                    target_id=target_id,
                    location_id=event.location_id,
                    canonical_summary=event.summary,
                )
            )
            cursor += duration + 0.12

        duration_seconds = cursor + self.post_roll_seconds
        beat_by_event = {beat.event_id: beat for beat in beats}

        camera_cues: list[PresentationCameraCue] = []
        if camera_plan is not None:
            for shot in camera_plan.shots:
                related = [beat_by_event[event_id] for event_id in shot.reason_event_ids if event_id in beat_by_event]
                if related:
                    start_seconds = min(beat.start_seconds for beat in related)
                    end_seconds = max(beat.start_seconds + beat.duration_seconds for beat in related)
                else:
                    tick_span = max(1, camera_plan.end_tick - camera_plan.start_tick + 1)
                    start_ratio = max(0.0, min(1.0, (shot.start_tick - camera_plan.start_tick) / tick_span))
                    end_ratio = max(start_ratio, min(1.0, (shot.end_tick - camera_plan.start_tick + 1) / tick_span))
                    usable = max(0.1, duration_seconds - self.pre_roll_seconds - self.post_roll_seconds)
                    start_seconds = self.pre_roll_seconds + usable * start_ratio
                    end_seconds = self.pre_roll_seconds + usable * end_ratio
                targets = tuple(actor_id for actor_id in shot.target_actor_ids if actor_id in stage_actor_set)
                if not targets:
                    targets = tuple(actor_id for actor_id in focus if actor_id in stage_actor_set)[:2]
                camera_cues.append(
                    PresentationCameraCue(
                        mode=shot.mode.value,
                        start_seconds=start_seconds,
                        end_seconds=max(start_seconds + 0.25, end_seconds),
                        target_actor_ids=targets,
                        reason_event_ids=tuple(event_id for event_id in shot.reason_event_ids if event_id in beat_by_event),
                    )
                )

        source_event_ids = tuple(event.id for event in selected_events)
        payload = {
            "protocol": STAGING_PROTOCOL,
            "crawl_id": crawl.id,
            "floor_number": selected_events[0].floor_number or crawl.current_floor,
            "presentation_seed": seed,
            "source_event_ids": list(source_event_ids),
            "source_fingerprint": crawl.fingerprint(),
            "actors": [actor.as_dict() for actor in actors],
            "beats": [beat.as_dict() for beat in beats],
            "camera_cues": [cue.as_dict() for cue in camera_cues],
            "duration_seconds": round(duration_seconds, 3),
            "authoritative": False,
        }
        return PresentationStagingManifest(
            protocol=STAGING_PROTOCOL,
            crawl_id=crawl.id,
            floor_number=int(selected_events[0].floor_number or crawl.current_floor),
            presentation_seed=seed,
            source_event_ids=source_event_ids,
            source_fingerprint=crawl.fingerprint(),
            actors=tuple(actors),
            beats=tuple(beats),
            camera_cues=tuple(camera_cues),
            duration_seconds=duration_seconds,
            digest=_digest(payload),
            authoritative=False,
        )


def validate_staging_manifest(manifest: PresentationStagingManifest, authoritative_event_ids: set[str]) -> bool:
    source_ids = set(manifest.source_event_ids)
    actor_ids = {actor.actor_id for actor in manifest.actors}
    if manifest.protocol != STAGING_PROTOCOL or manifest.authoritative:
        return False
    if not source_ids or not source_ids.issubset(authoritative_event_ids):
        return False
    if not manifest.actors or not manifest.beats or manifest.duration_seconds <= 0:
        return False
    for beat in manifest.beats:
        if beat.event_id not in source_ids:
            return False
        if not set(beat.actor_ids).issubset(actor_ids):
            return False
        if beat.performer_id is not None and beat.performer_id not in actor_ids:
            return False
        if beat.target_id is not None and beat.target_id not in actor_ids:
            return False
    return True
