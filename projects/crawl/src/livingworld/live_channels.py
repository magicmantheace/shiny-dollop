from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from .camera_director import AutomatedCameraDirector
from .crawl_domain import Crawl, CrawlEvent
from .detail_tiers import SimulationDetailTier
from .spectator_state import public_crawler, public_event, public_party, visible_encounters


@dataclass
class ViewerChannelRegistry:
    """Presentation-session state kept outside authoritative Crawl state."""

    viewers: dict[str, str] = field(default_factory=dict)

    def follow(self, viewer_id: str, npc_id: str, crawl: Crawl) -> None:
        if npc_id not in crawl.participants:
            raise KeyError(npc_id)
        self.viewers[viewer_id] = npc_id

    def unfollow(self, viewer_id: str) -> None:
        self.viewers.pop(viewer_id, None)

    def crawler_for(self, viewer_id: str) -> str | None:
        return self.viewers.get(viewer_id)

    def focused_ids(self) -> set[str]:
        return set(self.viewers.values())


def _stored_tier_without_initializing(crawl: Crawl, npc_id: str) -> str:
    """Read existing detail-tier metadata without invoking lazy state creation."""

    state = crawl.modifiers.get("_detail_tiers", {})
    if not isinstance(state, dict):
        return SimulationDetailTier.ACTIVE.value
    crawlers = state.get("crawlers", {})
    if not isinstance(crawlers, dict):
        return SimulationDetailTier.ACTIVE.value
    record = crawlers.get(npc_id, {})
    if not isinstance(record, dict):
        return SimulationDetailTier.ACTIVE.value
    value = record.get("tier", SimulationDetailTier.ACTIVE.value)
    try:
        return SimulationDetailTier(value).value
    except ValueError:
        return SimulationDetailTier.ACTIVE.value


def channel_focus_plan(crawl: Crawl, focused_ids: Iterable[str]) -> dict:
    """Return a pure scheduling request for watched crawlers and their local context.

    The plan deliberately does not call ``tier_for``/``set_tier`` or mutate
    ``crawl.modifiers``. A runtime scheduler may consume this request when
    detail-tier execution becomes authoritative; spectator requests themselves
    never change simulation truth or the Crawl fingerprint.
    """

    focused = {npc_id for npc_id in focused_ids if npc_id in crawl.participants}
    focused_locations = {
        crawl.participants[npc_id].current_location_id
        for npc_id in focused
        if crawl.participants[npc_id].current_location_id is not None
    }
    focused_parties = {
        crawl.participants[npc_id].current_party_id
        for npc_id in focused
        if crawl.participants[npc_id].current_party_id is not None
    }

    local_active: set[str] = set()
    effective: dict[str, str] = {}
    for npc_id, participant in sorted(crawl.participants.items()):
        if npc_id in focused:
            effective[npc_id] = SimulationDetailTier.FOCUSED.value
            continue
        nearby = (
            participant.current_location_id is not None
            and participant.current_location_id in focused_locations
        ) or (
            participant.current_party_id is not None
            and participant.current_party_id in focused_parties
        )
        if nearby:
            local_active.add(npc_id)
            effective[npc_id] = SimulationDetailTier.ACTIVE.value
        else:
            effective[npc_id] = _stored_tier_without_initializing(crawl, npc_id)

    return {
        "focused_ids": sorted(focused),
        "local_active_ids": sorted(local_active),
        "effective_tiers": effective,
        "mutates_authoritative_state": False,
        "scheduler_contract": "presentation_focus_request_v1",
    }


def build_crawler_channel(
    crawl: Crawl,
    events: Iterable[CrawlEvent],
    npc_id: str,
    *,
    recent_event_limit: int = 12,
    camera_director: AutomatedCameraDirector | None = None,
) -> dict:
    if npc_id not in crawl.participants:
        raise KeyError(npc_id)

    ordered = sorted(events, key=lambda event: (event.tick, event.id))
    participant = crawl.participants[npc_id]
    actor_events = [event for event in ordered if npc_id in event.actor_ids]
    recent = actor_events[-max(1, recent_event_limit):]
    party = (
        public_party(crawl, participant.current_party_id)
        if participant.current_party_id and participant.current_party_id in crawl.parties
        else None
    )
    nearby_encounters = [
        encounter
        for encounter in visible_encounters(crawl)
        if encounter["location_id"] == participant.current_location_id
    ]

    director = camera_director or AutomatedCameraDirector()
    start_tick = max(0, crawl.current_tick - 20)
    plan = director.plan(
        crawl,
        ordered,
        start_tick=start_tick,
        end_tick=crawl.current_tick,
        focus_actor_id=npc_id,
        max_shots=8,
    )

    return {
        "channel_id": f"crawler:{npc_id}",
        "crawl_id": crawl.id,
        "tick": crawl.current_tick,
        "crawler": public_crawler(crawl, npc_id, include_social=False),
        "party": party,
        "nearby_visible_encounters": nearby_encounters,
        "recent_events": [public_event(event) for event in recent],
        "camera": plan.as_dict(),
        "focus_request": channel_focus_plan(crawl, [npc_id]),
        "authoritative": False,
        "source": "spectator_projection",
    }


def build_viewer_channels(
    crawl: Crawl,
    events: Iterable[CrawlEvent],
    registry: ViewerChannelRegistry,
) -> dict[str, dict]:
    ordered = tuple(events)
    return {
        viewer_id: build_crawler_channel(crawl, ordered, npc_id)
        for viewer_id, npc_id in sorted(registry.viewers.items())
    }
