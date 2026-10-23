from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
from typing import Iterable

from .crawl_domain import Crawl, ParticipationStatus
from .crawl_service import CrawlLifecycleService


class SimulationDetailTier(StrEnum):
    FOCUSED = "A"
    ACTIVE = "B"
    REMOTE = "C"
    BACKGROUND = "D"


TIER_INTERVALS: dict[SimulationDetailTier, int] = {
    SimulationDetailTier.FOCUSED: 1,
    SimulationDetailTier.ACTIVE: 2,
    SimulationDetailTier.REMOTE: 4,
    SimulationDetailTier.BACKGROUND: 8,
}

_STATE_KEY = "_detail_tiers"


def _stable_bucket(*parts: object, modulo: int = 1000) -> int:
    payload = ":".join(str(part) for part in parts).encode("utf-8")
    return int(sha256(payload).hexdigest()[:12], 16) % modulo


def _state(crawl: Crawl) -> dict:
    state = crawl.modifiers.setdefault(
        _STATE_KEY,
        {
            "version": 1,
            "focused_ids": [],
            "crawlers": {},
            "transitions": 0,
            "last_rebalance_tick": None,
        },
    )
    state.setdefault("focused_ids", [])
    state.setdefault("crawlers", {})
    state.setdefault("transitions", 0)
    state.setdefault("last_rebalance_tick", None)
    return state


def tier_for(crawl: Crawl, npc_id: str) -> SimulationDetailTier:
    record = _state(crawl)["crawlers"].get(npc_id)
    if record is None:
        return SimulationDetailTier.ACTIVE
    return SimulationDetailTier(record["tier"])


def tier_distribution(crawl: Crawl) -> dict[str, int]:
    counts = {tier.value: 0 for tier in SimulationDetailTier}
    for npc_id in crawl.participants:
        counts[tier_for(crawl, npc_id).value] += 1
    return counts


def update_interval(crawl: Crawl, npc_id: str) -> int:
    return TIER_INTERVALS[tier_for(crawl, npc_id)]


def due_crawlers(crawl: Crawl, tick: int | None = None) -> set[str]:
    """Return crawlers whose cognition/update slot is due at ``tick``.

    This scheduler is deterministic and does not mutate authoritative crawler state.
    The Batch 4 performance harness uses it to estimate/validate how many expensive
    crawler updates would be required after promotion/demotion. Existing Batch 3
    simulation remains the compatibility path until later slices consume this set
    directly.
    """

    current_tick = crawl.current_tick if tick is None else tick
    due: set[str] = set()
    state = _state(crawl)
    for npc_id, participant in crawl.participants.items():
        if participant.status != ParticipationStatus.ACTIVE:
            continue
        record = state["crawlers"].get(npc_id)
        tier = SimulationDetailTier(record["tier"]) if record else SimulationDetailTier.ACTIVE
        interval = TIER_INTERVALS[tier]
        offset = _stable_bucket(crawl.seed, npc_id, tier.value, modulo=interval)
        if (current_tick - offset) % interval == 0:
            due.add(npc_id)
    return due


def set_tier(
    crawl: Crawl,
    npc_id: str,
    tier: SimulationDetailTier,
    *,
    reason: str,
    lifecycle: CrawlLifecycleService | None = None,
) -> bool:
    if npc_id not in crawl.participants:
        raise KeyError(npc_id)
    participant = crawl.participants[npc_id]
    before = participant.model_dump(mode="json")
    state = _state(crawl)
    record = state["crawlers"].setdefault(
        npc_id,
        {"tier": SimulationDetailTier.ACTIVE.value, "last_transition_tick": crawl.current_tick, "reason": "default"},
    )
    previous = SimulationDetailTier(record["tier"])
    if previous == tier:
        record["reason"] = reason
        return False

    record.update({"tier": tier.value, "last_transition_tick": crawl.current_tick, "reason": reason})
    state["transitions"] += 1

    # Tier transitions are scheduling metadata only. Authoritative crawler state must
    # be byte-for-byte equivalent across the transition.
    after = participant.model_dump(mode="json")
    if before != after:
        raise RuntimeError("detail-tier transition mutated authoritative crawler state")

    if lifecycle is not None:
        lifecycle.record_event(
            crawl,
            "DETAIL_TIER_CHANGED",
            f"Crawler {npc_id} changed simulation detail tier {previous.value}->{tier.value}.",
            actor_ids=[npc_id],
            location_id=participant.current_location_id,
            data={
                "from_tier": previous.value,
                "to_tier": tier.value,
                "reason": reason,
                "state_changes": {"simulation_detail_tier": tier.value},
            },
        )
    return True


def rebalance_detail_tiers(
    crawl: Crawl,
    *,
    focused_ids: Iterable[str] = (),
    lifecycle: CrawlLifecycleService | None = None,
) -> dict[str, int]:
    """Deterministically assign A-D detail tiers without changing simulation truth."""

    focused = {npc_id for npc_id in focused_ids if npc_id in crawl.participants}
    state = _state(crawl)
    state["focused_ids"] = sorted(focused)

    active_encounter_locations = {
        encounter.location_id
        for encounter in crawl.encounters.values()
        if encounter.floor_number == crawl.current_floor and encounter.status.value == "active"
    }

    for npc_id in sorted(crawl.participants):
        participant = crawl.participants[npc_id]
        if participant.status != ParticipationStatus.ACTIVE:
            target = SimulationDetailTier.BACKGROUND
            reason = "inactive"
        elif npc_id in focused:
            target = SimulationDetailTier.FOCUSED
            reason = "focused"
        elif participant.health <= 0.45 or participant.current_location_id in active_encounter_locations:
            target = SimulationDetailTier.ACTIVE
            reason = "immediate_risk"
        elif participant.current_party_id is not None:
            target = SimulationDetailTier.ACTIVE
            reason = "party_relevant"
        elif participant.current_location_id in crawl.floors[participant.current_floor].exit_location_ids:
            target = SimulationDetailTier.BACKGROUND
            reason = "awaiting_advancement"
        elif _stable_bucket(crawl.seed, npc_id, crawl.current_floor, modulo=5) == 0:
            target = SimulationDetailTier.BACKGROUND
            reason = "background_sample"
        else:
            target = SimulationDetailTier.REMOTE
            reason = "remote"
        set_tier(crawl, npc_id, target, reason=reason, lifecycle=lifecycle)

    state["last_rebalance_tick"] = crawl.current_tick
    return tier_distribution(crawl)


def scheduler_load(crawl: Crawl, *, horizon_ticks: int = 32) -> dict[str, float | int]:
    if horizon_ticks < 1:
        raise ValueError("horizon_ticks must be positive")
    full_updates = 0
    scheduled_updates = 0
    active_count = sum(1 for p in crawl.participants.values() if p.status == ParticipationStatus.ACTIVE)
    for tick in range(crawl.current_tick, crawl.current_tick + horizon_ticks):
        full_updates += active_count
        scheduled_updates += len(due_crawlers(crawl, tick))
    ratio = (scheduled_updates / full_updates) if full_updates else 0.0
    return {
        "horizon_ticks": horizon_ticks,
        "full_frequency_updates": full_updates,
        "scheduled_updates": scheduled_updates,
        "scheduled_ratio": round(ratio, 6),
        "estimated_update_reduction": round(1.0 - ratio, 6),
    }
