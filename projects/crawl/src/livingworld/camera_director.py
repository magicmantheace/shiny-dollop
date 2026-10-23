from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from .crawl_domain import Crawl, CrawlEvent
from .semantic_event_ledger import semantic_score


class CameraMode(StrEnum):
    CRAWLER_FOLLOW = "crawler_follow"
    OVER_SHOULDER = "over_the_shoulder"
    COMBAT_TRACKING = "combat_tracking"
    WIDE_ESTABLISHING = "wide_establishing"
    OVERHEAD_TACTICAL = "overhead_tactical"
    PARTY_SHOT = "party_shot"
    ENEMY_REVEAL = "enemy_reveal"
    REACTION_CLOSEUP = "reaction_closeup"
    SLOW_MOTION_REPLAY = "slow_motion_replay"


@dataclass(frozen=True)
class CameraShot:
    start_tick: int
    end_tick: int
    mode: CameraMode
    target_actor_ids: tuple[str, ...]
    location_id: str | None
    score: float
    reason_event_ids: tuple[str, ...]
    reason: str

    def as_dict(self) -> dict:
        return {
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "duration_ticks": max(1, self.end_tick - self.start_tick + 1),
            "mode": self.mode.value,
            "target_actor_ids": list(self.target_actor_ids),
            "location_id": self.location_id,
            "score": round(self.score, 4),
            "reason_event_ids": list(self.reason_event_ids),
            "reason": self.reason,
        }


@dataclass(frozen=True)
class CameraPlan:
    crawl_id: str
    start_tick: int
    end_tick: int
    focus_actor_id: str | None
    shots: tuple[CameraShot, ...]
    digest: str

    def as_dict(self) -> dict:
        return {
            "crawl_id": self.crawl_id,
            "start_tick": self.start_tick,
            "end_tick": self.end_tick,
            "focus_actor_id": self.focus_actor_id,
            "shot_count": len(self.shots),
            "digest": self.digest,
            "shots": [shot.as_dict() for shot in self.shots],
        }


def _semantic(event: CrawlEvent) -> dict:
    if not isinstance(event.data, dict):
        return {}
    semantic = event.data.get("semantic", {})
    return semantic if isinstance(semantic, dict) else {}


def _tags(event: CrawlEvent) -> set[str]:
    return {str(tag) for tag in _semantic(event).get("audience_interest_tags", [])}


def _event_score(event: CrawlEvent, *, focus_actor_id: str | None = None) -> float:
    semantic = _semantic(event)
    importance = semantic_score(event)
    danger = float(semantic.get("danger_level", 0.0) or 0.0)
    rarity = float(semantic.get("rarity_score", 0.0) or 0.0)
    reversal = 1.0 if semantic.get("reversal") else 0.0
    actor_weight = min(1.0, len(event.actor_ids) / 5.0)
    focus_bonus = 0.16 if focus_actor_id and focus_actor_id in event.actor_ids else 0.0
    score = (
        importance * 0.54
        + danger * 0.16
        + rarity * 0.08
        + reversal * 0.10
        + actor_weight * 0.06
        + focus_bonus
    )
    return max(0.0, min(1.0, score))


def _mode_for_event(event: CrawlEvent) -> CameraMode:
    event_type = event.event_type.upper()
    tags = _tags(event)
    if "death" in tags or "DIED" in event_type or "ELIMINATED" in event_type:
        return CameraMode.REACTION_CLOSEUP
    if "BOSS" in event_type or "boss" in tags:
        return CameraMode.ENEMY_REVEAL
    if "COMBAT" in event_type or "action" in tags:
        return CameraMode.COMBAT_TRACKING
    if event_type in {"RESCUE", "BETRAYAL", "NEAR_DEATH"}:
        return CameraMode.SLOW_MOTION_REPLAY
    if "PARTY" in event_type or "relationship" in tags or "social_drama" in tags:
        return CameraMode.PARTY_SHOT
    if len(event.actor_ids) >= 4:
        return CameraMode.OVERHEAD_TACTICAL
    if len(event.actor_ids) == 1:
        return CameraMode.CRAWLER_FOLLOW
    return CameraMode.WIDE_ESTABLISHING


def _duration_for(mode: CameraMode, score: float) -> int:
    base = {
        CameraMode.CRAWLER_FOLLOW: 6,
        CameraMode.OVER_SHOULDER: 6,
        CameraMode.COMBAT_TRACKING: 8,
        CameraMode.WIDE_ESTABLISHING: 5,
        CameraMode.OVERHEAD_TACTICAL: 7,
        CameraMode.PARTY_SHOT: 7,
        CameraMode.ENEMY_REVEAL: 7,
        CameraMode.REACTION_CLOSEUP: 5,
        CameraMode.SLOW_MOTION_REPLAY: 8,
    }[mode]
    return base + (2 if score >= 0.82 else 0)


def _plan_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


class AutomatedCameraDirector:
    """Deterministic presentation-only camera planner.

    It consumes canonical CrawlEvent history and spectator-visible crawl structure.
    It never calls lifecycle/gameplay services and never mutates ``crawl``.
    """

    def __init__(self, *, minimum_score: float = 0.24, switch_margin: float = 0.16, min_hold_ticks: int = 4) -> None:
        self.minimum_score = minimum_score
        self.switch_margin = switch_margin
        self.min_hold_ticks = max(1, min_hold_ticks)

    def plan(
        self,
        crawl: Crawl,
        events: Iterable[CrawlEvent],
        *,
        start_tick: int | None = None,
        end_tick: int | None = None,
        focus_actor_id: str | None = None,
        max_shots: int = 32,
    ) -> CameraPlan:
        ordered = sorted(events, key=lambda event: (event.tick, event.id))
        if start_tick is None:
            start_tick = ordered[0].tick if ordered else 0
        if end_tick is None:
            end_tick = ordered[-1].tick if ordered else max(start_tick, crawl.current_tick)
        if end_tick < start_tick:
            raise ValueError("end_tick must be greater than or equal to start_tick")

        candidates: list[tuple[CrawlEvent, float, CameraMode]] = []
        for event in ordered:
            if event.tick < start_tick or event.tick > end_tick:
                continue
            score = _event_score(event, focus_actor_id=focus_actor_id)
            if score >= self.minimum_score or (focus_actor_id and focus_actor_id in event.actor_ids):
                candidates.append((event, score, _mode_for_event(event)))

        mutable_shots: list[dict] = []
        for event, raw_score, mode in candidates:
            actors = tuple(sorted(event.actor_ids))
            score = raw_score
            if mutable_shots:
                previous = mutable_shots[-1]
                previous_actors = set(previous["target_actor_ids"])
                if previous_actors.intersection(actors):
                    score = min(1.0, score + 0.08)
                if previous["location_id"] and previous["location_id"] == event.location_id:
                    score = min(1.0, score + 0.05)

                same_subject = bool(previous_actors.intersection(actors)) and previous["location_id"] == event.location_id
                if same_subject and mode == previous["mode"] and event.tick <= previous["end_tick"] + 2:
                    previous["end_tick"] = max(previous["end_tick"], event.tick + _duration_for(mode, score) - 1)
                    previous["score"] = max(previous["score"], score)
                    previous["reason_event_ids"].append(event.id)
                    continue

                held_ticks = max(1, event.tick - previous["start_tick"])
                if event.tick <= previous["end_tick"] and held_ticks < self.min_hold_ticks:
                    if score < previous["score"] + self.switch_margin:
                        previous["reason_event_ids"].append(event.id)
                        continue
                elif event.tick <= previous["end_tick"] and score < previous["score"] + self.switch_margin:
                    previous["reason_event_ids"].append(event.id)
                    continue

            duration = _duration_for(mode, score)
            mutable_shots.append(
                {
                    "start_tick": event.tick,
                    "end_tick": min(end_tick, event.tick + duration - 1),
                    "mode": mode,
                    "target_actor_ids": actors,
                    "location_id": event.location_id,
                    "score": score,
                    "reason_event_ids": [event.id],
                    "reason": f"{event.event_type.lower()} scored as presentation-worthy",
                }
            )
            if len(mutable_shots) >= max(1, max_shots):
                break

        if not mutable_shots:
            floor = crawl.floors.get(crawl.current_floor)
            fallback_location = floor.entrance_location_id if floor is not None else None
            mutable_shots.append(
                {
                    "start_tick": start_tick,
                    "end_tick": min(end_tick, start_tick + 5),
                    "mode": CameraMode.WIDE_ESTABLISHING,
                    "target_actor_ids": (focus_actor_id,) if focus_actor_id else (),
                    "location_id": fallback_location,
                    "score": 0.1,
                    "reason_event_ids": [],
                    "reason": "establishing coverage fallback",
                }
            )

        shots = tuple(
            CameraShot(
                start_tick=item["start_tick"],
                end_tick=max(item["start_tick"], item["end_tick"]),
                mode=item["mode"],
                target_actor_ids=tuple(item["target_actor_ids"]),
                location_id=item["location_id"],
                score=round(float(item["score"]), 4),
                reason_event_ids=tuple(dict.fromkeys(item["reason_event_ids"])),
                reason=item["reason"],
            )
            for item in mutable_shots
        )
        digest_payload = {
            "crawl_id": crawl.id,
            "start_tick": start_tick,
            "end_tick": end_tick,
            "focus_actor_id": focus_actor_id,
            "shots": [shot.as_dict() for shot in shots],
        }
        return CameraPlan(
            crawl_id=crawl.id,
            start_tick=start_tick,
            end_tick=end_tick,
            focus_actor_id=focus_actor_id,
            shots=shots,
            digest=_plan_digest(digest_payload),
        )
