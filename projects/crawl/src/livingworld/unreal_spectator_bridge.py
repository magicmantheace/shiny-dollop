from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from .crawl_domain import Crawl, CrawlEvent, ParticipationStatus
from .spectator_state import public_event, public_floor, visible_encounters


BRIDGE_PROTOCOL = "crawl.unreal-spectator.v1"


@dataclass(frozen=True)
class UnrealBridgeFrame:
    protocol: str
    crawl_id: str
    tick: int
    floor_number: int
    crawlers: list[dict]
    encounters: list[dict]
    events: list[dict]

    def as_dict(self) -> dict:
        return {
            "protocol": self.protocol,
            "crawl_id": self.crawl_id,
            "tick": self.tick,
            "floor_number": self.floor_number,
            "crawlers": self.crawlers,
            "encounters": self.encounters,
            "events": self.events,
        }


def bridge_bootstrap(crawl: Crawl) -> dict:
    """Describe the current renderable floor without giving Unreal authority."""

    return {
        "protocol": BRIDGE_PROTOCOL,
        "authority": "backend",
        "crawl_id": crawl.id,
        "tick": crawl.current_tick,
        "floor": public_floor(crawl),
        "contracts": {
            "unreal_may": [
                "spawn_visual_representations",
                "interpolate_between_authoritative_frames",
                "select_cameras",
                "play_presentational_animation",
            ],
            "unreal_must_not": [
                "resolve_combat",
                "change_health",
                "change_inventory",
                "change_progression",
                "teleport_authoritative_crawlers",
                "create_canonical_events",
            ],
        },
    }


def build_bridge_frame(
    crawl: Crawl,
    events: Iterable[CrawlEvent] = (),
    *,
    since_tick: int | None = None,
) -> UnrealBridgeFrame:
    crawlers: list[dict] = []
    for npc_id, participant in sorted(crawl.participants.items()):
        if participant.current_floor != crawl.current_floor:
            continue
        if participant.status in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED}:
            continue
        crawlers.append(
            {
                "npc_id": npc_id,
                "status": participant.status.value,
                "location_id": participant.current_location_id,
                "health": participant.health,
                "objective": participant.current_objective,
                "party_id": participant.current_party_id,
                "presentation_action": participant.agent.last_action if participant.agent else None,
            }
        )

    filtered_events = [
        event for event in events
        if (since_tick is None or event.tick > since_tick) and event.tick <= crawl.current_tick
    ]
    filtered_events.sort(key=lambda event: (event.tick, event.id))

    return UnrealBridgeFrame(
        protocol=BRIDGE_PROTOCOL,
        crawl_id=crawl.id,
        tick=crawl.current_tick,
        floor_number=crawl.current_floor,
        crawlers=crawlers,
        encounters=visible_encounters(crawl),
        events=[public_event(event) for event in filtered_events],
    )
