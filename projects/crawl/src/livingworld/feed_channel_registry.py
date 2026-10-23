"""Deterministic multi-channel Feed focus state for Underreach Slice 28B.3.

This module owns presentation/session state only.  It reads authoritative
Descent and Ledger values, but never writes to either object.  The registry is
therefore safe to query, reconnect, and drive from viewer follow requests
without changing the simulation fingerprint.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from hashlib import sha256
import json
import math
import re
from time import perf_counter
from typing import Any, Iterable

from .crawl_domain import Crawl, CrawlEvent, ParticipationStatus
from .feed_state import public_descender, public_ledger_event, visible_encounters
from .live_channels import channel_focus_plan


FEED_CHANNEL_PROTOCOL = "underreach.feed-channels.v1"
FEED_CHANNEL_REGISTRY_VERSION = "29a2.1"
AUTOMATIC_FOCUS_VERSION = "28b3.1"
AUTO_CHANNEL_ID = "feed:auto"
TERMINAL_EVENT_TYPES = {"ENEMY_DEFEATED", "CRAWLER_DIED", "CRAWLER_ELIMINATED"}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.:-]{1,96}$")


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return sha256(_canonical(value).encode("utf-8")).hexdigest()


def descender_channel_id(descender_id: str) -> str:
    return f"feed:descender:{descender_id}"


@dataclass(frozen=True)
class AutomaticFocusConfig:
    recent_window_ticks: int = 12
    minimum_focus_seconds: float = 2.5
    switch_cooldown_seconds: float = 1.8
    switch_threshold: float = 0.30
    terminal_hold_seconds: float = 2.5
    continuity_bonus: float = 0.14
    inactivity_penalty: float = 0.18

    def __post_init__(self) -> None:
        if self.recent_window_ticks < 1:
            raise ValueError("recent_window_ticks must be positive")
        if min(self.minimum_focus_seconds, self.switch_cooldown_seconds, self.terminal_hold_seconds) < 0:
            raise ValueError("focus timing cannot be negative")
        if self.switch_threshold < 0:
            raise ValueError("switch_threshold cannot be negative")


@dataclass(frozen=True)
class AutomaticFocusDecision:
    descender_id: str | None
    scores: dict[str, float]
    switched: bool
    reason: str
    evaluated_event_count: int
    decision_ms: float


class AutomaticFeedDirector:
    """Choose one useful live Descender from a bounded recent Ledger window."""

    EVENT_WEIGHTS = {
        "COMBAT_HIT": 1.00,
        "COMBAT_MISS": 0.52,
        "COMBAT_STARTED": 0.72,
        "ENCOUNTER_STARTED": 0.70,
        "CRAWLER_INJURED": 0.76,
        "CRAWLER_NEAR_DEATH": 0.94,
        "CRAWLER_DIED": 1.20,
        "CRAWLER_ELIMINATED": 1.20,
        "FLOOR_COMPLETED": 0.82,
        "CRAWLER_ADVANCED": 0.76,
        "CRAWLER_MOVED": 0.28,
        "PARTY_FORMED": 0.48,
        "RELATIONSHIP_CHANGED": 0.44,
    }

    def __init__(self, config: AutomaticFocusConfig | None = None) -> None:
        self.config = config or AutomaticFocusConfig()
        self.decision_times_ms: list[float] = []

    @staticmethod
    def _terminal(participant: Any) -> bool:
        return participant.status in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED}

    def decide(
        self,
        descent: Crawl,
        events: Iterable[CrawlEvent],
        *,
        presentation_seconds: float,
        current_descender_id: str | None,
        current_focus_started_seconds: float,
        last_switch_seconds: float,
        terminal_seen_seconds: dict[str, float],
        camera_available_ids: Iterable[str] = (),
        force: bool = False,
    ) -> AutomaticFocusDecision:
        started = perf_counter()
        available = set(camera_available_ids)
        latest_tick = int(descent.current_tick)
        lower_tick = max(0, latest_tick - self.config.recent_window_ticks)
        bounded = [
            event for event in events
            if lower_tick <= int(event.tick) <= latest_tick
        ]
        scores: dict[str, float] = {}
        last_activity: dict[str, int] = {}
        for descender_id, participant in sorted(descent.participants.items()):
            terminal = self._terminal(participant)
            terminal_age = presentation_seconds - terminal_seen_seconds.get(descender_id, -math.inf)
            if terminal and terminal_age >= self.config.terminal_hold_seconds:
                continue
            if available and descender_id not in available:
                continue
            score = 0.08
            if not terminal:
                score += max(0.0, 1.0 - float(participant.health)) * 0.34
            else:
                # A fresh canonical death gets a bounded presentation hold,
                # independent of noisy recent combat scores.  Once the hold
                # expires, the candidate is removed above and auto mode moves
                # to the best available living subject.
                score += 10.0
            if descender_id == current_descender_id:
                score += self.config.continuity_bonus
            scores[descender_id] = score

        for event in bounded:
            age = max(0, latest_tick - int(event.tick))
            recency = max(0.05, 1.0 - age / float(self.config.recent_window_ticks + 1))
            semantic = event.data.get("semantic", {}) if isinstance(event.data, dict) else {}
            semantic_boost = min(0.45, max(
                float(semantic.get("importance_score", 0.0) or 0.0),
                float(semantic.get("danger_level", 0.0) or 0.0),
            ) * 0.45)
            base = self.EVENT_WEIGHTS.get(event.event_type, 0.18) + semantic_boost
            for actor_id in event.actor_ids:
                if actor_id in scores:
                    scores[actor_id] += base * recency
                    last_activity[actor_id] = max(last_activity.get(actor_id, -1), int(event.tick))

        for descender_id in list(scores):
            if descender_id not in last_activity:
                scores[descender_id] -= self.config.inactivity_penalty
            scores[descender_id] = round(scores[descender_id], 6)

        if not scores:
            chosen = None
        else:
            # Stable ID is the final tie-break.  Avoid relying on dict order or
            # wall clock timing, so the same truth always selects the same Feed.
            chosen = min(scores, key=lambda item: (-scores[item], item))

        switched = chosen != current_descender_id
        reason = "initial_auto_focus" if current_descender_id is None else "auto_interest"
        if switched and current_descender_id in scores and not force:
            focus_age = presentation_seconds - current_focus_started_seconds
            since_switch = presentation_seconds - last_switch_seconds
            improvement = scores.get(chosen, -math.inf) - scores[current_descender_id]
            if (
                focus_age < self.config.minimum_focus_seconds
                or since_switch < self.config.switch_cooldown_seconds
                or improvement < self.config.switch_threshold
            ):
                chosen = current_descender_id
                switched = False
                reason = "auto_hysteresis_hold"
        if current_descender_id not in scores and current_descender_id is not None:
            reason = "auto_terminal_release"

        elapsed = (perf_counter() - started) * 1000.0
        self.decision_times_ms.append(elapsed)
        return AutomaticFocusDecision(
            descender_id=chosen,
            scores=scores,
            switched=switched,
            reason=reason,
            evaluated_event_count=len(bounded),
            decision_ms=elapsed,
        )


@dataclass
class ViewerFocusState:
    viewer_id: str
    focus_mode: str = "automatic"
    active_channel_id: str = AUTO_CHANNEL_ID
    manual_follow_descender_id: str | None = None
    automatic_focus_descender_id: str | None = None
    focus_started_presentation_tick: int = 0
    focus_started_seconds: float = 0.0
    last_switch_presentation_tick: int = 0
    last_switch_seconds: float = 0.0
    last_request_presentation_tick: int = -1
    last_seen_frame_id: str | None = None

    @property
    def active_descender_id(self) -> str | None:
        return self.manual_follow_descender_id or self.automatic_focus_descender_id


@dataclass(frozen=True)
class FocusTransition:
    transition_id: str
    viewer_id: str
    presentation_tick: int
    presentation_seconds: float
    from_channel: str | None
    to_channel: str
    from_descender_id: str | None
    to_descender_id: str | None
    mode: str
    reason: str
    request_id: str | None = None
    camera_shot_id: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class FeedChannelRegistry:
    """Register logical Feed channels and viewer follow state outside truth."""

    def __init__(
        self,
        descent_id: str,
        *,
        automatic_director: AutomaticFeedDirector | None = None,
        default_viewer_id: str = "default_viewer",
    ) -> None:
        if not _IDENTIFIER.fullmatch(default_viewer_id):
            raise ValueError("invalid default viewer ID")
        self.descent_id = descent_id
        self.default_viewer_id = default_viewer_id
        self.automatic_director = automatic_director or AutomaticFeedDirector()
        self.viewers: dict[str, ViewerFocusState] = {}
        self.channel_ids: tuple[str, ...] = ()
        self.recent_events: list[CrawlEvent] = []
        self.terminal_seen_seconds: dict[str, float] = {}
        self.latest_authoritative_tick = -1
        self.latest_buffered_tick = -1
        self.latest_presentation_tick = 0
        self.latest_presentation_seconds = 0.0
        self.latest_frame_id: str | None = None
        self.last_relevant_event_id: str | None = None
        self.camera_available_ids: set[str] = set()
        self.camera_state: dict[str, Any] | None = None
        self.presentation_identities: dict[str, dict[str, Any]] = {}
        self.transitions: list[FocusTransition] = []
        self._processed_requests: dict[str, dict[str, Any]] = {}
        self.follow_requests = 0
        self.release_requests = 0
        self.successful_switches = 0
        self.duplicate_requests_ignored = 0
        self.invalid_requests: list[dict[str, Any]] = []
        self.auto_switches = 0
        self.terminal_releases = 0
        self.reconnect_restores = 0
        self.switch_times_ms: list[float] = []
        self.channel_projection_times_ms: list[float] = []
        self.maximum_transient_history = 1024

    def _viewer(self, viewer_id: str | None = None) -> ViewerFocusState:
        value = viewer_id or self.default_viewer_id
        if not _IDENTIFIER.fullmatch(value):
            raise ValueError("invalid viewer ID")
        if value not in self.viewers:
            self.viewers[value] = ViewerFocusState(viewer_id=value)
        return self.viewers[value]

    def register(self, descent: Crawl) -> None:
        if descent.id != self.descent_id:
            raise ValueError("Feed registry belongs to a different Descent")
        self.channel_ids = tuple(descender_channel_id(item) for item in sorted(descent.participants))
        self._viewer()

    def register_presentation_identities(self, values: dict[str, dict[str, Any]]) -> None:
        """Attach safe visual identity metadata without touching canonical truth."""
        allowed = {"species", "visual_identity_digest", "visual_variant", "style_profile", "detail_tier"}
        self.presentation_identities = {
            str(descender_id): {
                key: json.loads(_canonical(value))
                for key, value in identity.items() if key in allowed
            }
            for descender_id, identity in sorted(values.items())
        }

    def _transition(
        self,
        state: ViewerFocusState,
        *,
        descender_id: str | None,
        mode: str,
        reason: str,
        request_id: str | None,
    ) -> FocusTransition | None:
        from_descender = state.active_descender_id
        from_channel = descender_channel_id(from_descender) if from_descender else None
        to_channel = descender_channel_id(descender_id) if descender_id else AUTO_CHANNEL_ID
        if from_descender == descender_id and state.focus_mode == mode:
            return None
        body = {
            "viewer_id": state.viewer_id,
            "presentation_tick": self.latest_presentation_tick,
            "presentation_seconds": round(self.latest_presentation_seconds, 6),
            "from_channel": from_channel,
            "to_channel": to_channel,
            "from_descender_id": from_descender,
            "to_descender_id": descender_id,
            "mode": mode,
            "reason": reason,
            "request_id": request_id,
        }
        transition = FocusTransition(
            transition_id=f"focus_{_digest(body)[:20]}",
            camera_shot_id=None,
            **body,
        )
        state.focus_mode = mode
        state.active_channel_id = to_channel
        state.focus_started_presentation_tick = self.latest_presentation_tick
        state.focus_started_seconds = self.latest_presentation_seconds
        state.last_switch_presentation_tick = self.latest_presentation_tick
        state.last_switch_seconds = self.latest_presentation_seconds
        if mode == "manual":
            state.manual_follow_descender_id = descender_id
        else:
            state.manual_follow_descender_id = None
            state.automatic_focus_descender_id = descender_id
        self.transitions.append(transition)
        if len(self.transitions) > self.maximum_transient_history:
            del self.transitions[:-self.maximum_transient_history]
        self.successful_switches += 1
        return transition

    def update(
        self,
        descent: Crawl,
        events: Iterable[CrawlEvent],
        *,
        presentation_tick: int,
        presentation_seconds: float,
        buffered_tick: int | None = None,
        frame_id: str | None = None,
        camera_available_ids: Iterable[str] = (),
        camera_state: dict[str, Any] | None = None,
    ) -> list[FocusTransition]:
        if not self.channel_ids:
            self.register(descent)
        if presentation_tick < self.latest_presentation_tick:
            raise ValueError("Feed presentation cursor cannot rewind")
        ordered = sorted(events, key=lambda item: (item.tick, item.id))
        by_id = {event.id: event for event in self.recent_events}
        by_id.update({event.id: event.model_copy(deep=True) for event in ordered})
        lower = max(0, int(descent.current_tick) - self.automatic_director.config.recent_window_ticks)
        self.recent_events = sorted(
            (event for event in by_id.values() if int(event.tick) >= lower),
            key=lambda item: (item.tick, item.id),
        )
        self.latest_authoritative_tick = int(descent.current_tick)
        self.latest_buffered_tick = int(buffered_tick if buffered_tick is not None else descent.current_tick)
        self.latest_presentation_tick = int(presentation_tick)
        self.latest_presentation_seconds = float(presentation_seconds)
        self.latest_frame_id = frame_id or self.latest_frame_id
        self.camera_available_ids = set(camera_available_ids)
        self.camera_state = json.loads(_canonical(camera_state)) if camera_state is not None else self.camera_state
        if ordered:
            self.last_relevant_event_id = ordered[-1].id
        for event in ordered:
            if event.event_type in {"CRAWLER_DIED", "CRAWLER_ELIMINATED"}:
                for actor_id in event.actor_ids:
                    if actor_id in descent.participants:
                        self.terminal_seen_seconds.setdefault(actor_id, self.latest_presentation_seconds)

        emitted: list[FocusTransition] = []
        for state in self.viewers.values():
            state.last_seen_frame_id = self.latest_frame_id
            if state.focus_mode == "manual":
                continue
            decision = self.automatic_director.decide(
                descent,
                self.recent_events,
                presentation_seconds=self.latest_presentation_seconds,
                current_descender_id=state.automatic_focus_descender_id,
                current_focus_started_seconds=state.focus_started_seconds,
                last_switch_seconds=state.last_switch_seconds,
                terminal_seen_seconds=self.terminal_seen_seconds,
                camera_available_ids=self.camera_available_ids,
                force=state.automatic_focus_descender_id is None,
            )
            if decision.switched or state.automatic_focus_descender_id is None:
                transition = self._transition(
                    state,
                    descender_id=decision.descender_id,
                    mode="automatic",
                    reason=decision.reason,
                    request_id=None,
                )
                if transition:
                    emitted.append(transition)
                    self.auto_switches += 1
                    if decision.reason == "auto_terminal_release":
                        self.terminal_releases += 1
        return emitted

    def apply_request(self, descent: Crawl, request: dict[str, Any]) -> dict[str, Any]:
        started = perf_counter()
        request_id = request.get("request_id")
        viewer_id = request.get("viewer_id")
        action = request.get("action")
        requested_tick = request.get("requested_at_presentation_tick")
        if not isinstance(request_id, str) or not _IDENTIFIER.fullmatch(request_id):
            return self._reject(request, "invalid_request_id")
        if request_id in self._processed_requests:
            self.duplicate_requests_ignored += 1
            return {**json.loads(_canonical(self._processed_requests[request_id])), "duplicate": True}
        if not isinstance(viewer_id, str) or not _IDENTIFIER.fullmatch(viewer_id):
            return self._reject(request, "invalid_viewer_id")
        if action not in {"follow", "release"}:
            return self._reject(request, "unsupported_action")
        if not isinstance(requested_tick, int) or requested_tick < 0:
            return self._reject(request, "invalid_presentation_tick")
        state = self._viewer(viewer_id)
        if requested_tick < state.last_request_presentation_tick or requested_tick < self.latest_presentation_tick:
            return self._reject(request, "stale_request")

        state.last_request_presentation_tick = requested_tick
        transition: FocusTransition | None
        if action == "follow":
            self.follow_requests += 1
            descender_id = request.get("descender_id")
            if not isinstance(descender_id, str) or descender_id not in descent.participants:
                return self._reject(request, "unknown_descender")
            reason = "manual_switch" if state.active_descender_id and state.active_descender_id != descender_id else "manual_follow"
            transition = self._transition(
                state,
                descender_id=descender_id,
                mode="manual",
                reason=reason,
                request_id=request_id,
            )
        else:
            self.release_requests += 1
            decision = self.automatic_director.decide(
                descent,
                self.recent_events,
                presentation_seconds=self.latest_presentation_seconds,
                current_descender_id=None,
                current_focus_started_seconds=self.latest_presentation_seconds,
                last_switch_seconds=-math.inf,
                terminal_seen_seconds=self.terminal_seen_seconds,
                camera_available_ids=self.camera_available_ids,
                force=True,
            )
            transition = self._transition(
                state,
                descender_id=decision.descender_id,
                mode="automatic",
                reason="manual_release",
                request_id=request_id,
            )
        response = {
            "status": "accepted",
            "request_id": request_id,
            "viewer_id": viewer_id,
            "focus_mode": state.focus_mode,
            "active_channel_id": state.active_channel_id,
            "active_descender_id": state.active_descender_id,
            "transition": transition.as_dict() if transition else None,
            "duplicate": False,
            "authoritative": False,
        }
        self._processed_requests[request_id] = json.loads(_canonical(response))
        while len(self._processed_requests) > self.maximum_transient_history:
            self._processed_requests.pop(next(iter(self._processed_requests)))
        self.switch_times_ms.append((perf_counter() - started) * 1000.0)
        self.switch_times_ms = self.switch_times_ms[-self.maximum_transient_history :]
        return response

    def _reject(self, request: dict[str, Any], reason: str) -> dict[str, Any]:
        item = {
            "status": "rejected",
            "request_id": request.get("request_id"),
            "reason": reason,
            "authoritative": False,
        }
        self.invalid_requests.append(json.loads(_canonical(item)))
        self.invalid_requests = self.invalid_requests[-self.maximum_transient_history :]
        return item

    def active_focus(self, viewer_id: str | None = None) -> dict[str, Any]:
        state = self._viewer(viewer_id)
        return {
            "protocol": FEED_CHANNEL_PROTOCOL,
            "registry_version": FEED_CHANNEL_REGISTRY_VERSION,
            "descent_id": self.descent_id,
            "viewer_id": state.viewer_id,
            "focus_mode": state.focus_mode,
            "active_channel_id": state.active_channel_id,
            "active_descender_id": state.active_descender_id,
            "manual_follow_descender_id": state.manual_follow_descender_id,
            "automatic_focus_descender_id": state.automatic_focus_descender_id,
            "presentation_tick": self.latest_presentation_tick,
            "presentation_seconds": round(self.latest_presentation_seconds, 6),
            "last_seen_frame_id": state.last_seen_frame_id,
            "camera_state": json.loads(_canonical(self.camera_state)) if self.camera_state else None,
            "authoritative": False,
        }

    def channel(self, descent: Crawl, descender_id: str, *, viewer_id: str | None = None) -> dict[str, Any]:
        started = perf_counter()
        if descender_id not in descent.participants:
            raise KeyError(descender_id)
        state = self._viewer(viewer_id)
        participant = descent.participants[descender_id]
        recent = [event for event in self.recent_events if descender_id in event.actor_ids][-12:]
        active_encounters = [
            encounter for encounter in visible_encounters(descent)
            if descender_id in encounter["participant_descender_ids"]
            or encounter["sector_id"] == participant.current_location_id
        ]
        scores = self.automatic_director.decide(
            descent,
            self.recent_events,
            presentation_seconds=self.latest_presentation_seconds,
            current_descender_id=state.automatic_focus_descender_id,
            current_focus_started_seconds=state.focus_started_seconds,
            last_switch_seconds=state.last_switch_seconds,
            terminal_seen_seconds=self.terminal_seen_seconds,
            camera_available_ids=self.camera_available_ids,
            force=False,
        ).scores
        stale = self.latest_buffered_tick < self.latest_authoritative_tick
        body = {
            "channel_id": descender_channel_id(descender_id),
            "descent_id": descent.id,
            "focus_descender_id": descender_id,
            "descender": public_descender(descent, descender_id, include_social=False),
            "presentation_identity": json.loads(_canonical(self.presentation_identities.get(descender_id, {}))),
            "current_stratum": participant.current_floor,
            "current_sector_id": participant.current_location_id,
            "status": public_descender(descent, descender_id)["status"],
            "health": participant.health,
            "party_id": participant.current_party_id,
            "terminal": participant.status in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED},
            "recent_interest_score": scores.get(descender_id, 0.0),
            "currently_manually_followed": state.manual_follow_descender_id == descender_id,
            "currently_automatic_focus": state.focus_mode == "automatic" and state.automatic_focus_descender_id == descender_id,
            "active_encounter": active_encounters[0] if active_encounters else None,
            "recent_ledger_events": [public_ledger_event(event) for event in recent],
            "camera_available": not self.camera_available_ids or descender_id in self.camera_available_ids,
            "current_camera_state": json.loads(_canonical(self.camera_state)) if state.active_descender_id == descender_id and self.camera_state else None,
            "latest_authoritative_tick": self.latest_authoritative_tick,
            "latest_buffered_tick": self.latest_buffered_tick,
            "latest_presentation_tick": self.latest_presentation_tick,
            "latest_frame_id": self.latest_frame_id,
            "last_relevant_event_id": recent[-1].id if recent else None,
            "stale": stale,
            "presentation_freshness_ticks": max(0, self.latest_authoritative_tick - self.latest_buffered_tick),
            "focus_request": channel_focus_plan(descent, [descender_id]),
            "authoritative": False,
            "source": "underreach_live_feed_projection",
        }
        body["presentation_digest"] = _digest(body)
        self.channel_projection_times_ms.append((perf_counter() - started) * 1000.0)
        return body

    def directory(self, descent: Crawl, *, viewer_id: str | None = None) -> list[dict[str, Any]]:
        return [self.channel(descent, item, viewer_id=viewer_id) for item in sorted(descent.participants)]

    def reconnect_snapshot(self) -> dict[str, Any]:
        body = {
            "protocol": FEED_CHANNEL_PROTOCOL,
            "registry_version": FEED_CHANNEL_REGISTRY_VERSION,
            "descent_id": self.descent_id,
            "latest_authoritative_tick": self.latest_authoritative_tick,
            "latest_buffered_tick": self.latest_buffered_tick,
            "latest_presentation_tick": self.latest_presentation_tick,
            "latest_presentation_seconds": self.latest_presentation_seconds,
            "latest_frame_id": self.latest_frame_id,
            "last_relevant_event_id": self.last_relevant_event_id,
            "camera_available_ids": sorted(self.camera_available_ids),
            "camera_state": json.loads(_canonical(self.camera_state)) if self.camera_state else None,
            "viewers": {key: asdict(value) for key, value in sorted(self.viewers.items())},
            "terminal_seen_seconds": dict(sorted(self.terminal_seen_seconds.items())),
            "presentation_identities": json.loads(_canonical(self.presentation_identities)),
        }
        return {**body, "digest": _digest(body)}

    def restore(self, snapshot: dict[str, Any]) -> None:
        body = {key: value for key, value in snapshot.items() if key != "digest"}
        if snapshot.get("digest") != _digest(body):
            raise ValueError("invalid Feed channel reconnect digest")
        if snapshot.get("protocol") != FEED_CHANNEL_PROTOCOL or snapshot.get("descent_id") != self.descent_id:
            raise ValueError("invalid Feed channel reconnect snapshot")
        self.latest_authoritative_tick = int(snapshot["latest_authoritative_tick"])
        self.latest_buffered_tick = int(snapshot["latest_buffered_tick"])
        self.latest_presentation_tick = int(snapshot["latest_presentation_tick"])
        self.latest_presentation_seconds = float(snapshot["latest_presentation_seconds"])
        self.latest_frame_id = snapshot.get("latest_frame_id")
        self.last_relevant_event_id = snapshot.get("last_relevant_event_id")
        self.camera_available_ids = set(snapshot.get("camera_available_ids", []))
        self.camera_state = json.loads(_canonical(snapshot.get("camera_state"))) if snapshot.get("camera_state") else None
        self.viewers = {key: ViewerFocusState(**value) for key, value in snapshot.get("viewers", {}).items()}
        self.terminal_seen_seconds = {key: float(value) for key, value in snapshot.get("terminal_seen_seconds", {}).items()}
        self.presentation_identities = json.loads(_canonical(snapshot.get("presentation_identities", {})))
        self.reconnect_restores += 1

    def diagnostics(self) -> dict[str, Any]:
        state = self._viewer()
        projection = self.channel_projection_times_ms or [0.0]
        decision = self.automatic_director.decision_times_ms or [0.0]
        switches = self.switch_times_ms or [0.0]
        transitions = [item.as_dict() for item in self.transitions]
        channel_body = {
            "descent_id": self.descent_id,
            "channel_ids": list(self.channel_ids),
            "latest_authoritative_tick": self.latest_authoritative_tick,
            "latest_buffered_tick": self.latest_buffered_tick,
        }
        body = {
            "protocol": FEED_CHANNEL_PROTOCOL,
            "registry_version": FEED_CHANNEL_REGISTRY_VERSION,
            "automatic_focus_version": AUTOMATIC_FOCUS_VERSION,
            "descent_id": self.descent_id,
            "available_channel_count": len(self.channel_ids) + 1,
            "active_descender_channel_count": len(self.channel_ids),
            "current_focus_mode": state.focus_mode,
            "current_channel_id": state.active_channel_id,
            "current_descender_id": state.active_descender_id,
            "automatic_focus_id": state.automatic_focus_descender_id,
            "manual_follow_id": state.manual_follow_descender_id,
            "follow_requests": self.follow_requests,
            "release_requests": self.release_requests,
            "successful_switches": self.successful_switches,
            "duplicate_requests_ignored": self.duplicate_requests_ignored,
            "invalid_requests": list(self.invalid_requests),
            "auto_switches": self.auto_switches,
            "terminal_releases": self.terminal_releases,
            "reconnect_restores": self.reconnect_restores,
            "average_channel_projection_ms": sum(projection) / len(projection),
            "maximum_channel_projection_ms": max(projection),
            "average_automatic_focus_decision_ms": sum(decision) / len(decision),
            "maximum_automatic_focus_decision_ms": max(decision),
            "average_switch_processing_ms": sum(switches) / len(switches),
            "maximum_switch_processing_ms": max(switches),
            "channel_digest": _digest(channel_body),
            "focus_sequence_digest": _digest(transitions),
            "channel_freshness_monotonic": self.latest_buffered_tick <= self.latest_authoritative_tick,
            "transitions": transitions,
            "presentation_identity_count": len(self.presentation_identities),
        }
        return {**body, "digest": _digest(body)}
