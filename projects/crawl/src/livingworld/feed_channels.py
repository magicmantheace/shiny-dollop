"""Read-only per-Descender channel projections for The Feed."""

from __future__ import annotations

from typing import Iterable

from .camera_director import AutomatedCameraDirector
from .crawl_domain import Crawl, CrawlEvent
from .feed_state import public_descender, public_ledger_event, public_party, visible_encounters
from .live_channels import channel_focus_plan


def build_descender_channel(
    descent: Crawl,
    events: Iterable[CrawlEvent],
    descender_id: str,
    *,
    recent_event_limit: int = 12,
    camera_director: AutomatedCameraDirector | None = None,
) -> dict:
    """Build a Feed channel without mutating authoritative Descent state."""

    if descender_id not in descent.participants:
        raise KeyError(descender_id)

    ordered = sorted(events, key=lambda event: (event.tick, event.id))
    participant = descent.participants[descender_id]
    actor_events = [event for event in ordered if descender_id in event.actor_ids]
    recent = actor_events[-max(1, recent_event_limit):]
    party = (
        public_party(descent, participant.current_party_id)
        if participant.current_party_id and participant.current_party_id in descent.parties
        else None
    )
    nearby_encounters = [
        encounter
        for encounter in visible_encounters(descent)
        if encounter["sector_id"] == participant.current_location_id
    ]

    director = camera_director or AutomatedCameraDirector()
    start_tick = max(0, descent.current_tick - 20)
    plan = director.plan(
        descent,
        ordered,
        start_tick=start_tick,
        end_tick=descent.current_tick,
        focus_actor_id=descender_id,
        max_shots=8,
    )

    return {
        "channel_id": f"feed:descender:{descender_id}",
        "descent_id": descent.id,
        "tick": descent.current_tick,
        "descender": public_descender(descent, descender_id, include_social=False),
        "party": party,
        "nearby_visible_encounters": nearby_encounters,
        "recent_ledger_events": [public_ledger_event(event) for event in recent],
        "camera": plan.as_dict(),
        "focus_request": channel_focus_plan(descent, [descender_id]),
        "authoritative": False,
        "source": "underreach_feed_projection",
    }
