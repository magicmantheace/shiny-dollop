from __future__ import annotations

from enum import StrEnum
from hashlib import sha256
import json
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .crawler_domain import CrawlerAgentState
from .gameplay_domain import CrawlItem, CrawlParty, CrawlerGameplayState, EncounterState


class CrawlStatus(StrEnum):
    PLANNED = "planned"
    RUNNING = "running"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class FloorStatus(StrEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"


class ParticipationStatus(StrEnum):
    ACTIVE = "active"
    DEAD = "dead"
    ELIMINATED = "eliminated"
    ADVANCED = "advanced"


class LocationKind(StrEnum):
    ENTRANCE = "entrance"
    ZONE = "zone"
    ROOM = "room"
    SAFE_AREA = "safe_area"
    EXIT = "exit"


class CrawlLocation(BaseModel):
    id: str
    floor_number: int = Field(ge=1)
    name: str
    kind: LocationKind = LocationKind.ROOM
    adjacency: dict[str, float] = Field(default_factory=dict)
    visibility: float = Field(default=1.0, ge=0.0, le=1.0)
    hazards: list[str] = Field(default_factory=list)
    exits: list[str] = Field(default_factory=list)
    encounter_slots: int = Field(default=0, ge=0)
    loot_resource_nodes: list[str] = Field(default_factory=list)
    environmental_tags: list[str] = Field(default_factory=list)
    capacity: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def validate_traversal_costs(self) -> "CrawlLocation":
        if any(cost <= 0 for cost in self.adjacency.values()):
            raise ValueError("location traversal costs must be positive")
        return self


class CrawlFloor(BaseModel):
    number: int = Field(ge=1)
    seed: str
    theme: str
    started_at_tick: int | None = Field(default=None, ge=0)
    deadline_tick: int | None = Field(default=None, ge=0)
    completion_rules: dict[str, Any] = Field(default_factory=dict)
    advancement_rules: dict[str, Any] = Field(default_factory=dict)
    locations: dict[str, CrawlLocation] = Field(default_factory=dict)
    entrance_location_id: str
    exit_location_ids: list[str] = Field(default_factory=list)
    safe_area_ids: list[str] = Field(default_factory=list)
    danger_level: float = Field(default=0.25, ge=0.0, le=1.0)
    director_budget: float = Field(default=0.0, ge=0.0)
    encounter_budget: float = Field(default=0.0, ge=0.0)
    active_crawler_count: int = Field(default=0, ge=0)
    status: FloorStatus = FloorStatus.PENDING

    @model_validator(mode="after")
    def validate_graph(self) -> "CrawlFloor":
        if not self.locations:
            raise ValueError("floor must contain at least one location")
        if self.entrance_location_id not in self.locations:
            raise ValueError("floor entrance must reference an existing location")
        if not self.exit_location_ids:
            raise ValueError("floor must contain at least one exit")
        missing_exits = [item for item in self.exit_location_ids if item not in self.locations]
        if missing_exits:
            raise ValueError(f"floor exits reference missing locations: {missing_exits}")
        missing_safe = [item for item in self.safe_area_ids if item not in self.locations]
        if missing_safe:
            raise ValueError(f"safe areas reference missing locations: {missing_safe}")

        location_ids = set(self.locations)
        for key, location in self.locations.items():
            if key != location.id:
                raise ValueError(f"location key {key!r} does not match location id {location.id!r}")
            if location.floor_number != self.number:
                raise ValueError(f"location {location.id!r} belongs to the wrong floor")
            missing_neighbors = set(location.adjacency) - location_ids
            if missing_neighbors:
                raise ValueError(
                    f"location {location.id!r} references missing neighbors: {sorted(missing_neighbors)}"
                )
            missing_declared_exits = set(location.exits) - location_ids
            if missing_declared_exits:
                raise ValueError(
                    f"location {location.id!r} references missing exits: {sorted(missing_declared_exits)}"
                )

        reachable = {self.entrance_location_id}
        frontier = [self.entrance_location_id]
        while frontier:
            current = frontier.pop()
            for neighbor in self.locations[current].adjacency:
                if neighbor not in reachable:
                    reachable.add(neighbor)
                    frontier.append(neighbor)
        if not any(exit_id in reachable for exit_id in self.exit_location_ids):
            raise ValueError("no floor exit is reachable from the entrance")
        return self


class CrawlerParticipation(BaseModel):
    npc_id: str
    crawl_id: str
    current_floor: int = Field(ge=1)
    current_location_id: str | None = None
    status: ParticipationStatus = ParticipationStatus.ACTIVE
    health: float = Field(default=1.0, ge=0.0, le=1.0)
    resources: dict[str, float] = Field(default_factory=dict)
    progression: dict[str, float] = Field(default_factory=dict)
    current_party_id: str | None = None
    current_objective: str | None = None
    floor_statistics: dict[str, float] = Field(default_factory=dict)
    agent: CrawlerAgentState | None = None
    gameplay: CrawlerGameplayState = Field(default_factory=CrawlerGameplayState)


class CrawlEvent(BaseModel):
    id: str
    crawl_id: str
    floor_number: int | None = Field(default=None, ge=1)
    tick: int = Field(ge=0)
    event_type: str
    summary: str
    actor_ids: list[str] = Field(default_factory=list)
    location_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)


class Crawl(BaseModel):
    id: str
    seed: str
    status: CrawlStatus = CrawlStatus.PLANNED
    started_at_tick: int | None = Field(default=None, ge=0)
    current_tick: int = Field(default=0, ge=0)
    current_floor: int = Field(default=1, ge=1)
    ruleset_id: str
    ruleset_version: str
    starting_crawler_count: int = Field(default=0, ge=0)
    surviving_crawler_count: int = Field(default=0, ge=0)
    eliminated_crawler_count: int = Field(default=0, ge=0)
    modifiers: dict[str, Any] = Field(default_factory=dict)
    history_event_ids: list[str] = Field(default_factory=list)
    floors: dict[int, CrawlFloor] = Field(default_factory=dict)
    participants: dict[str, CrawlerParticipation] = Field(default_factory=dict)
    items: dict[str, CrawlItem] = Field(default_factory=dict)
    parties: dict[str, CrawlParty] = Field(default_factory=dict)
    encounters: dict[str, EncounterState] = Field(default_factory=dict)
    archived_at_tick: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_references(self) -> "Crawl":
        if not self.floors:
            raise ValueError("crawl must contain at least one floor")
        expected_numbers = set(range(1, max(self.floors) + 1))
        if set(self.floors) != expected_numbers:
            raise ValueError("crawl floor numbers must be contiguous starting at 1")
        for number, floor_state in self.floors.items():
            if number != floor_state.number:
                raise ValueError("crawl floor key must match floor.number")
        if self.current_floor not in self.floors:
            raise ValueError("current floor does not exist")
        if self.starting_crawler_count != len(self.participants):
            raise ValueError("starting crawler count must match participant count")

        all_locations = {location_id for floor in self.floors.values() for location_id in floor.locations}
        surviving = 0
        eliminated = 0
        inventory_refs: set[str] = set()

        for key, participant in self.participants.items():
            if key != participant.npc_id:
                raise ValueError("participant key must match npc_id")
            if participant.crawl_id != self.id:
                raise ValueError("participant crawl_id must match crawl id")
            if participant.agent is not None and participant.agent.npc_id != participant.npc_id:
                raise ValueError("participant agent npc_id must match participant npc_id")
            if participant.current_floor not in self.floors:
                raise ValueError("participant current floor does not exist")
            if participant.current_location_id is not None:
                floor_state = self.floors[participant.current_floor]
                if participant.current_location_id not in floor_state.locations:
                    raise ValueError("participant location does not exist on current floor")
            if participant.current_party_id is not None:
                party = self.parties.get(participant.current_party_id)
                if party is None or participant.npc_id not in party.member_npc_ids:
                    raise ValueError("participant current party must exist and contain participant")

            for item_id in participant.gameplay.inventory_item_ids:
                if item_id in inventory_refs:
                    raise ValueError("item cannot appear in multiple crawler inventories")
                inventory_refs.add(item_id)
                item = self.items.get(item_id)
                if item is None or item.owner_npc_id != participant.npc_id:
                    raise ValueError("crawler inventory item must exist and be owned by crawler")
            for slot, item_id in participant.gameplay.equipment.items():
                if item_id not in participant.gameplay.inventory_item_ids:
                    raise ValueError(f"equipped item in slot {slot!r} must be in crawler inventory")

            if participant.status in {ParticipationStatus.DEAD, ParticipationStatus.ELIMINATED}:
                eliminated += 1
            else:
                surviving += 1

        if self.surviving_crawler_count != surviving:
            raise ValueError("surviving crawler count does not match participant state")
        if self.eliminated_crawler_count != eliminated:
            raise ValueError("eliminated crawler count does not match participant state")

        for item_id, item in self.items.items():
            if item_id != item.id:
                raise ValueError("item key must match item id")
            if item.owner_npc_id is not None:
                owner = self.participants.get(item.owner_npc_id)
                if owner is None or item.id not in owner.gameplay.inventory_item_ids:
                    raise ValueError("owned item must appear in exactly one owner inventory")
            if item.location_id is not None and item.location_id not in all_locations:
                raise ValueError("ground item location must exist")
            if item.encounter_id is not None:
                encounter = self.encounters.get(item.encounter_id)
                if encounter is None or item.id not in encounter.reward_item_ids:
                    raise ValueError("encounter-held item must reference its encounter reward list")

        for party_id, party in self.parties.items():
            if party_id != party.id:
                raise ValueError("party key must match party id")
            missing_members = set(party.member_npc_ids) - set(self.participants)
            if missing_members:
                raise ValueError("party references missing participants")
            if party.active:
                for npc_id in party.member_npc_ids:
                    if self.participants[npc_id].current_party_id != party.id:
                        raise ValueError("active party membership must be mirrored by participants")

        for encounter_id, encounter in self.encounters.items():
            if encounter_id != encounter.id:
                raise ValueError("encounter key must match encounter id")
            floor = self.floors.get(encounter.floor_number)
            if floor is None or encounter.location_id not in floor.locations:
                raise ValueError("encounter location must exist on encounter floor")
            if set(encounter.participant_npc_ids) - set(self.participants):
                raise ValueError("encounter references missing participants")
            for item_id in encounter.reward_item_ids:
                if item_id not in self.items:
                    raise ValueError("encounter reward item must exist")
        return self

    def fingerprint(self) -> str:
        # Mapping insertion order is not canonical state.  Checkpoint files use
        # sorted JSON keys, so fingerprint the semantic model with the same
        # canonical ordering and remain stable across serialize/restore.
        payload = json.dumps(
            self.model_dump(mode="json", exclude={"history_event_ids"}),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        )
        return sha256(payload.encode("utf-8")).hexdigest()
