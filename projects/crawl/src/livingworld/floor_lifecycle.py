from __future__ import annotations

from typing import Any

from .crawl_domain import Crawl, CrawlStatus, FloorStatus, ParticipationStatus
from .crawl_service import CrawlLifecycleService
from .item_system import choose_and_equip
from .party_system import update_party_stability
from .progression_system import choose_progression


FLOOR_CYCLE_STATE_KEY = "_floor_cycle"


def _cycle_state(crawl: Crawl) -> dict[str, Any]:
    state = crawl.modifiers.setdefault(FLOOR_CYCLE_STATE_KEY, {})
    state.setdefault("phase", "active")
    state.setdefault("warnings_emitted", {})
    state.setdefault("intermission_end_tick", None)
    state.setdefault("intermission_floor", None)
    state.setdefault("closed_floor", None)
    return state


def floor_phase(crawl: Crawl) -> str:
    return str(_cycle_state(crawl).get("phase", "active"))


def _warning_thresholds(duration: int) -> list[int]:
    values = {
        max(1, int(duration * 0.20)),
        max(1, int(duration * 0.10)),
        max(1, int(duration * 0.05)),
    }
    return sorted(values, reverse=True)


class FloorLifecycleService:
    """Own floor deadlines, advancement resolution, and bounded intermissions."""

    def __init__(self, lifecycle: CrawlLifecycleService, *, intermission_ticks: int = 5) -> None:
        self.lifecycle = lifecycle
        self.intermission_ticks = max(1, intermission_ticks)

    def synchronize(self, crawl: Crawl) -> None:
        state = _cycle_state(crawl)
        if crawl.status != CrawlStatus.RUNNING:
            return
        floor = crawl.floors[crawl.current_floor]
        if floor.status == FloorStatus.ACTIVE and state.get("phase") not in {"intermission", "closing"}:
            state["phase"] = "active"
            state["warnings_emitted"].setdefault(str(crawl.current_floor), [])

    def tick_intermission(self, crawl: Crawl) -> bool:
        state = _cycle_state(crawl)
        if state.get("phase") != "intermission":
            return False
        end_tick = int(state.get("intermission_end_tick") or crawl.current_tick)
        if crawl.current_tick < end_tick:
            crawl.current_tick += 1
            self.lifecycle.save(crawl)
            return True

        self.lifecycle.activate_floor(crawl, crawl.current_floor)
        state["phase"] = "active"
        state["intermission_end_tick"] = None
        state["intermission_floor"] = None
        self.lifecycle._record(
            crawl,
            "INTERMISSION_ENDED",
            f"Intermission ended; Floor {crawl.current_floor} opened.",
            floor_number=crawl.current_floor,
            data={"state_changes": {"phase": "active"}},
        )
        self.lifecycle.save(crawl)
        return True

    def evaluate(self, crawl: Crawl) -> dict[str, Any] | None:
        if crawl.status != CrawlStatus.RUNNING:
            return None
        state = _cycle_state(crawl)
        if state.get("phase") == "intermission":
            self.tick_intermission(crawl)
            return {"phase": "intermission", "tick": crawl.current_tick}

        floor = crawl.floors[crawl.current_floor]
        if floor.status != FloorStatus.ACTIVE:
            return None

        active = [
            participant
            for participant in crawl.participants.values()
            if participant.status == ParticipationStatus.ACTIVE and participant.current_floor == crawl.current_floor
        ]
        if not active:
            self._end_without_survivors(crawl)
            return {"phase": "complete", "reason": "no_survivors"}

        if all(participant.current_location_id in floor.exit_location_ids for participant in active):
            return self.close_floor(crawl, reason="all_survivors_reached_exit")

        deadline = floor.deadline_tick
        if deadline is None:
            return None
        remaining = deadline - crawl.current_tick
        duration = max(1, deadline - int(floor.started_at_tick or 0))
        self._emit_due_warnings(crawl, remaining, duration)
        if remaining <= 0:
            return self.close_floor(crawl, reason="deadline")
        return None

    def _emit_due_warnings(self, crawl: Crawl, remaining: int, duration: int) -> None:
        state = _cycle_state(crawl)
        key = str(crawl.current_floor)
        emitted = set(int(value) for value in state["warnings_emitted"].setdefault(key, []))
        for threshold in _warning_thresholds(duration):
            if remaining <= threshold and threshold not in emitted and remaining > 0:
                self.lifecycle._record(
                    crawl,
                    "FLOOR_DEADLINE_WARNING",
                    f"Floor {crawl.current_floor} deadline approaching: {remaining} ticks remain.",
                    floor_number=crawl.current_floor,
                    data={
                        "remaining_ticks": remaining,
                        "threshold_ticks": threshold,
                        "danger": crawl.floors[crawl.current_floor].danger_level,
                    },
                )
                emitted.add(threshold)
        state["warnings_emitted"][key] = sorted(emitted, reverse=True)

    def close_floor(self, crawl: Crawl, *, reason: str) -> dict[str, Any]:
        floor_number = crawl.current_floor
        floor = crawl.floors[floor_number]
        state = _cycle_state(crawl)
        state["phase"] = "closing"

        active_ids = [
            npc_id
            for npc_id, participant in crawl.participants.items()
            if participant.status == ParticipationStatus.ACTIVE and participant.current_floor == floor_number
        ]
        advancing = [
            npc_id
            for npc_id in active_ids
            if crawl.participants[npc_id].current_location_id in floor.exit_location_ids
        ]
        advancing_set = set(advancing)
        eliminated = [npc_id for npc_id in active_ids if npc_id not in advancing_set]

        if reason != "deadline" and not advancing:
            advancing = list(active_ids)
            eliminated = []

        for npc_id in eliminated:
            participant = crawl.participants[npc_id]
            self.lifecycle.eliminate(
                crawl,
                npc_id,
                dead=False,
                summary=f"Crawler {npc_id} failed to advance before Floor {floor_number} closed.",
            )
            self.lifecycle._record(
                crawl,
                "FLOOR_DEADLINE_ELIMINATION",
                f"Crawler {npc_id} was eliminated by the floor deadline.",
                floor_number=floor_number,
                actor_ids=[npc_id],
                location_id=participant.current_location_id,
                data={
                    "reason": reason,
                    "state_changes": {"participation_status": "eliminated"},
                    "danger": floor.danger_level,
                },
            )

        for party_id in sorted(crawl.parties):
            party = crawl.parties[party_id]
            if not party.active:
                continue
            was_active = party.active
            remained_active = update_party_stability(crawl, party_id)
            if was_active and not remained_active:
                self.lifecycle._record(
                    crawl,
                    "PARTY_DISSOLVED",
                    f"Party {party_id} dissolved after floor closure.",
                    floor_number=floor_number,
                    actor_ids=list(party.member_npc_ids),
                    data={
                        "party_id": party_id,
                        "reason": "membership_loss_or_low_cohesion",
                        "state_changes": {"party_active": False},
                    },
                )

        if crawl.surviving_crawler_count <= 0:
            self._end_without_survivors(crawl)
            return {
                "phase": "complete",
                "floor": floor_number,
                "reason": "no_survivors",
                "advanced": 0,
                "eliminated": len(eliminated),
            }

        self.lifecycle._record(
            crawl,
            "FLOOR_CLOSED",
            f"Floor {floor_number} closed.",
            floor_number=floor_number,
            actor_ids=sorted(advancing),
            data={
                "reason": reason,
                "advanced_count": len(advancing),
                "eliminated_count": len(eliminated),
                "state_changes": {"floor_phase": "closed"},
            },
        )

        self.lifecycle.complete_current_floor(crawl, advance_ticks=0, activate_next=False)
        state["closed_floor"] = floor_number
        if crawl.status == CrawlStatus.COMPLETED:
            state["phase"] = "complete"
            return {
                "phase": "complete",
                "floor": floor_number,
                "reason": reason,
                "advanced": len(advancing),
                "eliminated": len(eliminated),
            }

        self._begin_intermission(crawl, previous_floor=floor_number)
        return {
            "phase": "intermission",
            "floor": floor_number,
            "next_floor": crawl.current_floor,
            "reason": reason,
            "advanced": len(advancing),
            "eliminated": len(eliminated),
        }

    def _begin_intermission(self, crawl: Crawl, *, previous_floor: int) -> None:
        state = _cycle_state(crawl)
        state["phase"] = "intermission"
        state["intermission_floor"] = previous_floor
        state["intermission_end_tick"] = crawl.current_tick + self.intermission_ticks

        choices: dict[str, list[str]] = {}
        for npc_id, participant in sorted(crawl.participants.items()):
            if participant.status != ParticipationStatus.ACTIVE:
                continue
            participant.health = min(1.0, participant.health + 0.18)
            participant.gameplay.stamina = min(1.0, participant.gameplay.stamina + 0.35)
            participant.gameplay.incapacitated = False
            if participant.agent is not None:
                participant.agent.needs.stamina = participant.gameplay.stamina
                participant.agent.needs.stress = max(0.0, participant.agent.needs.stress - 0.20)
                participant.agent.current_plan = []
            choose_and_equip(crawl, npc_id)
            spent = choose_progression(participant, crawl_seed=crawl.seed)
            if spent:
                choices[npc_id] = spent

        self.lifecycle._record(
            crawl,
            "INTERMISSION_STARTED",
            f"Intermission began before Floor {crawl.current_floor}.",
            floor_number=crawl.current_floor,
            actor_ids=sorted(
                npc_id
                for npc_id, participant in crawl.participants.items()
                if participant.status == ParticipationStatus.ACTIVE
            ),
            data={
                "previous_floor": previous_floor,
                "next_floor": crawl.current_floor,
                "ends_at_tick": state["intermission_end_tick"],
                "progression_choices": choices,
                "state_changes": {"phase": "intermission"},
            },
        )
        self.lifecycle.save(crawl)

    def _end_without_survivors(self, crawl: Crawl) -> None:
        floor = crawl.floors[crawl.current_floor]
        floor.status = FloorStatus.FAILED
        crawl.status = CrawlStatus.COMPLETED
        state = _cycle_state(crawl)
        state["phase"] = "complete"
        self.lifecycle._record(
            crawl,
            "CRAWL_ENDED_NO_SURVIVORS",
            "The crawl ended because no contestants remained eligible to advance.",
            floor_number=crawl.current_floor,
            data={"state_changes": {"crawl_status": "completed", "floor_status": "failed"}},
        )
        self.lifecycle.save(crawl)
