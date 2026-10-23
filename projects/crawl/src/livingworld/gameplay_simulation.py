from __future__ import annotations

from dataclasses import dataclass

from .crawl_domain import Crawl, CrawlStatus, ParticipationStatus
from .crawl_service import CrawlLifecycleService
from .crawler_decision import choose_action
from .crawler_navigation import choose_destination, perceive, recover, traverse
from .crawler_social import apply_social_event, remember, relationship
from .encounter_system import encounter_at, resolve_encounter, seed_floor_encounters
from .item_system import choose_and_equip, consume_best_healing_item, item_score, transfer_item_to_crawler
from .party_system import maybe_form_party, update_party_stability


@dataclass
class GameplayStepSummary:
    tick: int
    moved: int = 0
    rested: int = 0
    discovered: int = 0
    parties_formed: int = 0
    encounters_resolved: int = 0
    deaths: int = 0
    items_looted: int = 0
    advancement_ready: bool = False
    floor_completed: bool = False


class GameplayCrawlSimulator:
    """Integrated headless simulator for v0.4 Slices 7-11.

    Movement remains crawler-local and knowledge constrained. Once everyone has
    moved for a tick, co-located crawlers may form parties and trigger one dormant
    encounter at that location. Combat, loot, XP and social consequences are then
    applied to the same authoritative Crawl state.

    ``auto_complete_floors`` defaults to True for Batch 2 compatibility. Batch 3
    disables it so the deadline/intermission service owns advancement timing.
    """

    def __init__(self, lifecycle: CrawlLifecycleService, *, auto_complete_floors: bool = True) -> None:
        self.lifecycle = lifecycle
        self.auto_complete_floors = auto_complete_floors

    def prepare(self, crawl: Crawl) -> None:
        for floor_number in sorted(crawl.floors):
            seed_floor_encounters(crawl, floor_number)
        self.lifecycle.save(crawl)

    def step(self, crawl: Crawl) -> GameplayStepSummary:
        if crawl.status != CrawlStatus.RUNNING:
            raise ValueError("gameplay step requires a running crawl")
        if not crawl.encounters:
            self.prepare(crawl)

        crawl.current_tick += 1
        floor = crawl.floors[crawl.current_floor]
        summary = GameplayStepSummary(tick=crawl.current_tick)
        intended_destinations: dict[str, str | None] = {}

        for npc_id in sorted(crawl.participants):
            participant = crawl.participants[npc_id]
            if participant.status != ParticipationStatus.ACTIVE:
                continue
            if participant.current_floor != crawl.current_floor or participant.agent is None:
                continue
            if participant.current_location_id in floor.exit_location_ids:
                participant.current_objective = "await_floor_completion"
                intended_destinations[npc_id] = participant.current_location_id
                continue

            if participant.health < 0.48:
                consumed = consume_best_healing_item(crawl, npc_id)
                if consumed:
                    summary.items_looted += 1
                    self.lifecycle._record(
                        crawl,
                        "ITEM_CONSUMED",
                        f"Crawler {npc_id} used a healing item.",
                        actor_ids=[npc_id],
                        location_id=participant.current_location_id,
                        data={"item_id": consumed, "health": participant.health},
                    )

            discoveries = perceive(participant, floor, crawl.current_tick)
            summary.discovered += len(discoveries)
            for location_id in discoveries:
                event = self.lifecycle._record(
                    crawl,
                    "LOCATION_DISCOVERED",
                    f"Crawler {npc_id} discovered a reachable location.",
                    actor_ids=[npc_id],
                    location_id=location_id,
                    data={"discovered_location_id": location_id},
                )
                remember(
                    participant.agent,
                    event_id=event.id,
                    event_type=event.event_type,
                    tick=crawl.current_tick,
                    floor_number=crawl.current_floor,
                    emotion="curious",
                    importance=0.18,
                )

            decision = choose_action(participant.agent, health=participant.health, seed=floor.seed)
            participant.current_objective = decision.action
            intended_destinations[npc_id] = choose_destination(participant, floor, decision)

        self._apply_party_route_choices(crawl, intended_destinations)

        for npc_id in sorted(intended_destinations):
            participant = crawl.participants[npc_id]
            if participant.status != ParticipationStatus.ACTIVE:
                continue
            destination = intended_destinations[npc_id]
            if destination is None or destination == participant.current_location_id:
                recover(participant, floor)
                participant.gameplay.stamina = participant.agent.needs.stamina if participant.agent else participant.gameplay.stamina
                summary.rested += 1
                continue
            origin = participant.current_location_id
            cost = traverse(participant, floor, destination)
            if participant.agent is not None:
                participant.gameplay.stamina = participant.agent.needs.stamina
            perceive(participant, floor, crawl.current_tick)
            summary.moved += 1
            event = self.lifecycle._record(
                crawl,
                "CRAWLER_MOVED",
                f"Crawler {npc_id} moved between crawl locations.",
                actor_ids=[npc_id],
                location_id=destination,
                data={"from": origin, "to": destination, "cost": cost, "objective": participant.current_objective},
            )
            remember(
                participant.agent,
                event_id=event.id,
                event_type=event.event_type,
                tick=crawl.current_tick,
                floor_number=crawl.current_floor,
                emotion="alert" if floor.locations[destination].hazards else "neutral",
                importance=0.14,
            )

        summary.parties_formed += self._form_parties(crawl)
        self._update_colocation_social_state(crawl)
        summary.items_looted += self._collect_ground_loot(crawl)

        occupied = sorted(
            {
                participant.current_location_id
                for participant in crawl.participants.values()
                if participant.status == ParticipationStatus.ACTIVE
                and participant.current_floor == crawl.current_floor
                and participant.current_location_id is not None
            }
        )
        for location_id in occupied:
            if location_id in floor.exit_location_ids:
                continue
            encounter = encounter_at(crawl, crawl.current_floor, location_id)
            if encounter is None:
                continue
            before_dead = crawl.eliminated_crawler_count
            result = resolve_encounter(crawl, encounter, self.lifecycle)
            summary.encounters_resolved += 1
            summary.deaths += crawl.eliminated_crawler_count - before_dead
            summary.items_looted += len(result.get("reward_item_ids", []))
            self._apply_encounter_social_consequences(crawl, encounter.participant_npc_ids, result.get("outcome", ""))

        for party_id in sorted(list(crawl.parties)):
            if crawl.parties[party_id].active:
                update_party_stability(crawl, party_id)

        self._reconcile_agent_stamina(crawl)
        active = [
            item
            for item in crawl.participants.values()
            if item.status == ParticipationStatus.ACTIVE and item.current_floor == crawl.current_floor
        ]
        if not active:
            floor.status = floor.status.FAILED
            crawl.status = CrawlStatus.COMPLETED
            self.lifecycle._record(crawl, "CRAWL_ENDED_NO_SURVIVORS", "The crawl ended with no surviving contestants.")
            self.lifecycle.save(crawl)
            return summary

        if all(item.current_location_id in floor.exit_location_ids for item in active):
            summary.advancement_ready = True
            if self.auto_complete_floors:
                self.lifecycle.complete_current_floor(crawl, advance_ticks=0)
                summary.floor_completed = True
                if crawl.status == CrawlStatus.RUNNING:
                    self._recover_between_floors(crawl)
            else:
                self.lifecycle.save(crawl)
        else:
            self.lifecycle.save(crawl)
        return summary

    def run(self, crawl: Crawl, *, max_steps: int = 10_000) -> list[GameplayStepSummary]:
        if max_steps < 1:
            raise ValueError("max_steps must be positive")
        if not crawl.encounters:
            self.prepare(crawl)
        summaries: list[GameplayStepSummary] = []
        for _ in range(max_steps):
            if crawl.status != CrawlStatus.RUNNING:
                break
            summaries.append(self.step(crawl))
        return summaries

    def _apply_party_route_choices(self, crawl: Crawl, destinations: dict[str, str | None]) -> None:
        for party in sorted(crawl.parties.values(), key=lambda value: value.id):
            if not party.active or party.leader_npc_id not in destinations:
                continue
            leader = crawl.participants[party.leader_npc_id]
            leader_destination = destinations[party.leader_npc_id]
            if leader_destination is None or leader.current_location_id is None:
                continue
            for npc_id in party.member_npc_ids:
                if npc_id == party.leader_npc_id or npc_id not in destinations:
                    continue
                participant = crawl.participants[npc_id]
                if participant.current_location_id != leader.current_location_id or participant.agent is None:
                    continue
                knowledge = participant.agent.knowledge.get(participant.current_location_id)
                if knowledge is not None and leader_destination in knowledge.known_neighbors and party.cohesion >= 0.38:
                    destinations[npc_id] = leader_destination
                    participant.current_objective = "follow_party_leader"

    def _form_parties(self, crawl: Crawl) -> int:
        groups: dict[str, list[str]] = {}
        for npc_id, participant in crawl.participants.items():
            if participant.status == ParticipationStatus.ACTIVE and participant.current_location_id:
                groups.setdefault(participant.current_location_id, []).append(npc_id)
        formed = 0
        for members in groups.values():
            while True:
                party = maybe_form_party(crawl, members)
                if party is None:
                    break
                formed += 1
                self.lifecycle._record(
                    crawl,
                    "PARTY_FORMED",
                    f"Party {party.id} formed under crawler {party.leader_npc_id}.",
                    actor_ids=party.member_npc_ids,
                    location_id=crawl.participants[party.leader_npc_id].current_location_id,
                    data={"party_id": party.id, "leader": party.leader_npc_id, "loot_policy": party.loot_policy.value},
                )
        return formed

    def _collect_ground_loot(self, crawl: Crawl) -> int:
        count = 0
        ground = [item for item in crawl.items.values() if item.location_id is not None]
        for item in sorted(ground, key=lambda value: value.id):
            candidates = [
                npc_id
                for npc_id, participant in crawl.participants.items()
                if participant.status == ParticipationStatus.ACTIVE and participant.current_location_id == item.location_id
            ]
            if not candidates:
                continue
            winner = max(candidates, key=lambda npc_id: (item_score(item, crawl.participants[npc_id]), npc_id))
            transfer_item_to_crawler(crawl, item.id, winner)
            choose_and_equip(crawl, winner)
            count += 1
            self.lifecycle._record(crawl, "GROUND_LOOT_ACQUIRED", f"Crawler {winner} recovered dropped loot.", actor_ids=[winner], location_id=crawl.participants[winner].current_location_id, data={"item_id": item.id})
        return count

    def _update_colocation_social_state(self, crawl: Crawl) -> None:
        groups: dict[str, list[str]] = {}
        for npc_id, participant in crawl.participants.items():
            if participant.status == ParticipationStatus.ACTIVE and participant.current_location_id:
                groups.setdefault(participant.current_location_id, []).append(npc_id)
        for members in groups.values():
            ordered = sorted(members)
            for npc_id in ordered:
                agent = crawl.participants[npc_id].agent
                if agent is None:
                    continue
                for other_id in ordered:
                    if other_id != npc_id:
                        rel = relationship(agent, other_id)
                        rel.familiarity = min(1.0, rel.familiarity + 0.003)

    def _apply_encounter_social_consequences(self, crawl: Crawl, members: list[str], outcome: object) -> None:
        active = [npc_id for npc_id in members if npc_id in crawl.participants and crawl.participants[npc_id].status == ParticipationStatus.ACTIVE]
        if len(active) < 2:
            return
        magnitude = 0.12 if str(outcome).startswith("victory") else 0.06
        for npc_id in active:
            agent = crawl.participants[npc_id].agent
            if agent is None:
                continue
            for other_id in active:
                if other_id != npc_id:
                    apply_social_event(agent, target_id=other_id, event_type="shared_resource", magnitude=magnitude)

    def _reconcile_agent_stamina(self, crawl: Crawl) -> None:
        for participant in crawl.participants.values():
            if participant.agent is not None:
                value = min(participant.agent.needs.stamina, participant.gameplay.stamina)
                participant.agent.needs.stamina = value
                participant.gameplay.stamina = value

    def _recover_between_floors(self, crawl: Crawl) -> None:
        for participant in crawl.participants.values():
            if participant.status != ParticipationStatus.ACTIVE:
                continue
            participant.health = min(1.0, participant.health + 0.18)
            participant.gameplay.stamina = min(1.0, participant.gameplay.stamina + 0.35)
            if participant.agent is not None:
                participant.agent.needs.stamina = participant.gameplay.stamina
                participant.agent.needs.stress = max(0.0, participant.agent.needs.stress - 0.18)
