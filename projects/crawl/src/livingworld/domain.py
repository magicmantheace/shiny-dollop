from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class EntityType(StrEnum):
    WORLD = "world"
    CONTINENT = "continent"
    REGION = "region"
    KINGDOM = "kingdom"
    SETTLEMENT = "settlement"
    NPC = "npc"
    ARMY = "army"
    WAR = "war"
    TRADE_ROUTE = "trade_route"
    RELIGION = "religion"
    REFUGEE_CAMP = "refugee_camp"
    FRONTIER_CLAIM = "frontier_claim"
    POLITICAL_FACTION = "political_faction"
    PRODUCTION_SITE = "production_site"


class SettlementType(StrEnum):
    CITY = "city"
    TOWN = "town"
    VILLAGE = "village"
    HAMLET = "hamlet"
    FORT = "fort"
    MINE = "mine"
    MONASTERY = "monastery"
    PORT = "port"
    RUIN = "ruin"
    TRADE_POST = "trade_post"


class Ancestry(StrEnum):
    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    GNOME = "gnome"
    HALFLING = "halfling"
    ORC = "orc"
    GOBLIN = "goblin"


class GovernmentType(StrEnum):
    MONARCHY = "monarchy"
    ELECTIVE_MONARCHY = "elective_monarchy"
    COUNCIL = "council"
    CLAN_CONFEDERACY = "clan_confederacy"
    THEOCRACY = "theocracy"
    MERCHANT_OLIGARCHY = "merchant_oligarchy"
    MILITARY_REGIME = "military_regime"


class PoliticalOfficeType(StrEnum):
    RULER = "ruler"
    HEIR = "heir"
    CHANCELLOR = "chancellor"
    TREASURER = "treasurer"
    MARSHAL = "marshal"
    HIGH_PRIEST = "high_priest"
    GOVERNOR = "governor"
    MAYOR = "mayor"
    COUNCILOR = "councilor"
    GUILD_REPRESENTATIVE = "guild_representative"


class PoliticalFactionType(StrEnum):
    NOBILITY = "nobility"
    MERCHANTS = "merchants"
    MILITARY = "military"
    PRIESTHOOD = "priesthood"
    GUILDS = "guilds"
    FRONTIER = "frontier"
    COMMONERS = "commoners"


class LaborCategory(StrEnum):
    AGRICULTURE = "agriculture"
    EXTRACTION = "extraction"
    CRAFTS = "crafts"
    TRADE = "trade"
    ADMINISTRATION = "administration"
    RELIGION = "religion"
    MILITARY = "military"
    SERVICES = "services"
    DEPENDENT = "dependent"


class BorderPolicy(StrEnum):
    OPEN = "open"
    CONTROLLED = "controlled"
    CLOSED = "closed"


class RefugeePolicy(StrEnum):
    WELCOME = "welcome"
    LIMITED = "limited"
    REJECT = "reject"


class CampStatus(StrEnum):
    ACTIVE = "active"
    RESETTLING = "resettling"
    CLOSED = "closed"


class WarState(StrEnum):
    ACTIVE = "active"
    TRUCE = "truce"
    ENDED = "ended"


class CommandStatus(StrEnum):
    QUEUED = "queued"
    ACCEPTED = "accepted"
    EXECUTING = "executing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    FAILED = "failed"


class WorldDate(BaseModel):
    year: int = 1
    month: int = 1
    day: int = 1
    hour: int = 0

    def ordinal_hour(self) -> int:
        return (((self.year - 1) * 12 + (self.month - 1)) * 30 + (self.day - 1)) * 24 + self.hour

    @classmethod
    def from_ordinal_hour(cls, total: int) -> "WorldDate":
        total = max(0, total)
        hour = total % 24
        total //= 24
        day = total % 30 + 1
        total //= 30
        month = total % 12 + 1
        year = total // 12 + 1
        return cls(year=year, month=month, day=day, hour=hour)

    def plus_hours(self, hours: int) -> "WorldDate":
        return self.from_ordinal_hour(self.ordinal_hour() + hours)

    def label(self) -> str:
        return f"Y{self.year:04d}-M{self.month:02d}-D{self.day:02d} {self.hour:02d}:00"


class Position(BaseModel):
    x: float
    y: float
    elevation: float = 0.0


class ResourceStock(BaseModel):
    resource: str
    quantity: float = 0.0
    capacity: float = 1_000.0
    base_price: float = 1.0
    price: float = 1.0
    production_per_day: float = 0.0
    consumption_per_day: float = 0.0

    def clamp(self) -> None:
        self.quantity = max(0.0, min(self.quantity, self.capacity))


class ProductionSite(BaseModel):
    """Persistent material-production capacity embedded in one settlement."""

    id: str
    settlement_id: str
    kind: str
    labor_category: LaborCategory
    worker_capacity: int
    assigned_workers: int = 0
    inputs: dict[str, float] = Field(default_factory=dict)
    outputs: dict[str, float] = Field(default_factory=dict)
    base_throughput: float = 1.0
    efficiency: float = 1.0
    active: bool = True


class Culture(BaseModel):
    id: str
    name: str
    dominant_ancestry: Ancestry
    honor: float = 0.5
    collectivism: float = 0.5
    militarism: float = 0.5
    devotion: float = 0.5
    trade_orientation: float = 0.5
    expansionism: float = 0.5
    tolerance: float = 0.5
    magic_acceptance: float = 0.5
    tradition: float = 0.5


class Religion(BaseModel):
    id: str
    name: str
    deity: str
    domains: list[str]
    doctrine: list[str]
    holy_sites: list[str] = Field(default_factory=list)


class Memory(BaseModel):
    event_id: str
    summary: str
    subject_id: str | None = None
    emotion: str = "neutral"
    importance: float = 0.5
    confidence: float = 1.0
    decay_per_year: float = 0.05
    created_at: WorldDate


class Relationship(BaseModel):
    target_id: str
    affinity: float = 0.0
    trust: float = 0.0
    fear: float = 0.0
    debt: float = 0.0
    tags: list[str] = Field(default_factory=list)


class NPC(BaseModel):
    id: str
    name: str
    ancestry: Ancestry
    culture_id: str
    religion_id: str | None = None
    settlement_id: str
    kingdom_id: str
    age: int
    sex: Literal["female", "male"]
    alive: bool = True
    health: float = 1.0
    wealth: float = 20.0
    occupation: str
    social_status: str = "commoner"
    traits: dict[str, float] = Field(default_factory=dict)
    values: dict[str, float] = Field(default_factory=dict)
    goals: list[str] = Field(default_factory=list)
    reputation: dict[str, float] = Field(default_factory=dict)
    relationships: dict[str, Relationship] = Field(default_factory=dict)
    memories: list[Memory] = Field(default_factory=list)
    spouse_id: str | None = None
    parent_ids: list[str] = Field(default_factory=list)
    child_ids: list[str] = Field(default_factory=list)
    title: str | None = None
    goal_progress: dict[str, float] = Field(default_factory=dict)


class Settlement(BaseModel):
    id: str
    name: str
    type: SettlementType
    kingdom_id: str
    region_id: str
    position: Position
    biome: str
    population: int
    ancestry_population: dict[Ancestry, int]
    food_security: float = 0.75
    wealth: float = 1_000.0
    housing_capacity: int = 0
    stability: float = 0.75
    crime: float = 0.1
    health: float = 0.8
    magic_intensity: float = 0.2
    infrastructure: dict[str, float] = Field(default_factory=dict)
    resources: dict[str, ResourceStock] = Field(default_factory=dict)
    production_sites: dict[str, ProductionSite] = Field(default_factory=dict)
    labor_allocation: dict[str, int] = Field(default_factory=dict)
    production_initialized: bool = False
    production_shortages: dict[str, float] = Field(default_factory=dict)
    production_last_day: dict[str, float] = Field(default_factory=dict)
    consumption_last_day: dict[str, float] = Field(default_factory=dict)
    buildings: dict[str, int] = Field(default_factory=dict)
    local_factions: list[str] = Field(default_factory=list)
    founded_year: int = 1
    frontier: bool = False
    origin_settlement_id: str | None = None
    frontier_stress_months: int = 0
    abandoned_year: int | None = None
    occupied_by_kingdom_id: str | None = None
    occupation_months: int = 0
    besieged_by_kingdom_id: str | None = None
    siege_progress: float = 0.0

    @model_validator(mode="after")
    def set_capacity(self) -> "Settlement":
        if self.housing_capacity <= 0:
            self.housing_capacity = max(self.population + 50, int(self.population * 1.25))
        return self


class DiplomaticRelation(BaseModel):
    target_kingdom_id: str
    opinion: float = 0.0
    trade_access: bool = True
    alliance: bool = False
    truce_until_year: int | None = None
    grievances: list[str] = Field(default_factory=list)


class StrategicDecision(BaseModel):
    action: str
    score: float
    reasons: dict[str, float]
    target_id: str | None = None
    created_at: WorldDate


class PoliticalOffice(BaseModel):
    role: PoliticalOfficeType
    title: str
    holder_npc_id: str | None = None
    appointed_at: WorldDate


class PoliticalFaction(BaseModel):
    id: str
    kingdom_id: str
    name: str
    kind: PoliticalFactionType
    leader_npc_id: str | None = None
    member_npc_ids: list[str] = Field(default_factory=list)
    ideology: dict[str, float] = Field(default_factory=dict)
    economic_interests: dict[str, float] = Field(default_factory=dict)
    religious_interests: dict[str, float] = Field(default_factory=dict)
    influence: float = 0.25
    loyalty: float = 0.6
    grievances: list[str] = Field(default_factory=list)
    preferred_policies: dict[str, float] = Field(default_factory=dict)
    rival_faction_ids: list[str] = Field(default_factory=list)
    allied_faction_ids: list[str] = Field(default_factory=list)
    regional_base_settlement_id: str | None = None
    created_at: WorldDate
    active: bool = True


class LawPolicy(BaseModel):
    """Persistent law and policy choices. Numeric values are bounded policy intensity."""

    tax_rate: float = 0.12
    conscription: float = 0.35
    religious_tolerance: float = 0.55
    guild_privileges: float = 0.45
    land_rights: float = 0.45
    inheritance_equality: float = 0.35
    trade_tariff: float = 0.08
    anti_bandit_spending: float = 0.35
    military_spending: float = 0.45
    grain_reserve: float = 0.45
    magic_regulation: float = 0.45
    revision: int = 0


class InstitutionalCapacity(BaseModel):
    """The machinery that turns nominal law into actual compliance."""

    administrative_reach: float = 0.55
    tax_efficiency: float = 0.60
    corruption: float = 0.20
    record_keeping: float = 0.50
    communication_quality: float = 0.50
    local_autonomy: float = 0.35
    enforcement_capability: float = 0.55


class Kingdom(BaseModel):
    id: str
    name: str
    capital_settlement_id: str
    government: GovernmentType
    dominant_ancestry: Ancestry
    culture_id: str
    religion_id: str | None = None
    ruler_npc_id: str | None = None
    treasury: float = 10_000.0
    tax_rate: float = 0.12
    stability: float = 0.75
    legitimacy: float = 0.7
    military_readiness: float = 0.5
    food_reserve: float = 0.75
    border_policy: BorderPolicy = BorderPolicy.OPEN
    refugee_policy: RefugeePolicy = RefugeePolicy.LIMITED
    goals: dict[str, float] = Field(default_factory=dict)
    settlement_ids: list[str] = Field(default_factory=list)
    army_ids: list[str] = Field(default_factory=list)
    relations: dict[str, DiplomaticRelation] = Field(default_factory=dict)
    claims: list[str] = Field(default_factory=list)
    overlord_kingdom_id: str | None = None
    last_decision: StrategicDecision | None = None
    political_offices: dict[str, PoliticalOffice] = Field(default_factory=dict)
    faction_ids: list[str] = Field(default_factory=list)
    politics_initialized: bool = False
    last_leadership_review_year: int = 1
    political_crisis_months: int = 0
    last_political_resolution_year: int | None = None
    last_political_resolution: str | None = None
    laws: LawPolicy = Field(default_factory=LawPolicy)
    institutions: InstitutionalCapacity = Field(default_factory=InstitutionalCapacity)
    institutions_initialized: bool = False
    policy_compliance: dict[str, float] = Field(default_factory=dict)
    effective_policies: dict[str, float] = Field(default_factory=dict)
    last_policy_review_year: int = 1
    institutional_revenue_last_month: float = 0.0
    institutional_spending_last_month: float = 0.0
    resource_reserves: dict[str, ResourceStock] = Field(default_factory=dict)


class TradeRoute(BaseModel):
    id: str
    origin_settlement_id: str
    destination_settlement_id: str
    distance: float
    safety: float = 0.8
    capacity: float = 100.0
    active: bool = True
    commodities: list[str] = Field(default_factory=list)
    volume_last_day: float = 0.0


class Army(BaseModel):
    id: str
    kingdom_id: str
    name: str
    troop_count: int
    location_settlement_id: str
    destination_settlement_id: str | None = None
    morale: float = 0.75
    supply_days: float = 30.0
    readiness: float = 0.6
    commander_npc_id: str | None = None
    active: bool = True
    supply_efficiency: float = 1.0
    supply_source_settlement_id: str | None = None


class War(BaseModel):
    id: str
    attacker_kingdom_id: str
    defender_kingdom_id: str
    goal: str
    state: WarState = WarState.ACTIVE
    started_at: WorldDate
    ended_at: WorldDate | None = None
    attacker_score: float = 0.0
    defender_score: float = 0.0
    casualties: dict[str, int] = Field(default_factory=dict)
    occupied_settlement_ids: list[str] = Field(default_factory=list)
    front_settlement_ids: list[str] = Field(default_factory=list)
    siege_progress: dict[str, float] = Field(default_factory=dict)
    occupation_by_settlement: dict[str, str] = Field(default_factory=dict)
    attacker_exhaustion: float = 0.0
    defender_exhaustion: float = 0.0
    months_active: int = 0
    peace_terms: dict[str, Any] = Field(default_factory=dict)


class Landmark(BaseModel):
    id: str
    name: str
    kind: str
    position: Position
    description: str
    magic_intensity: float = 0.0


class Region(BaseModel):
    id: str
    name: str
    seed: str
    climate: str
    biome_mix: dict[str, float]
    magic_intensity: float
    bounds: dict[str, float]
    settlement_ids: list[str] = Field(default_factory=list)
    kingdom_ids: list[str] = Field(default_factory=list)
    landmarks: list[Landmark] = Field(default_factory=list)
    resource_distribution: dict[str, float] = Field(default_factory=dict)


class Continent(BaseModel):
    id: str
    name: str
    seed: str
    bounds: dict[str, float]
    region_ids: list[str] = Field(default_factory=list)
    climate_bands: list[str] = Field(default_factory=list)
    ocean_fraction: float = 0.35
    generation_version: str = "0.3"


class RefugeeCamp(BaseModel):
    id: str
    host_settlement_id: str
    host_kingdom_id: str
    origin_kingdom_id: str
    people: int
    ancestry_population: dict[Ancestry, int] = Field(default_factory=dict)
    created_at: WorldDate
    last_arrival_at: WorldDate
    status: CampStatus = CampStatus.ACTIVE
    food_security: float = 0.55
    health: float = 0.72
    months_active: int = 0


class HistoricalEvent(BaseModel):
    id: str
    type: str
    occurred_at: WorldDate
    summary: str
    subject_ids: list[str] = Field(default_factory=list)
    location_id: str | None = None
    data: dict[str, Any] = Field(default_factory=dict)
    source: str = "simulation"
    importance: float = 0.5


class WorldState(BaseModel):
    id: str = "world_0001"
    name: str
    seed: str
    date: WorldDate = Field(default_factory=WorldDate)
    paused: bool = False
    speed_multiplier: float = 1.0
    region: Region
    continent: Continent | None = None
    regions: dict[str, Region] = Field(default_factory=dict)
    cultures: dict[str, Culture]
    religions: dict[str, Religion]
    kingdoms: dict[str, Kingdom]
    settlements: dict[str, Settlement]
    npcs: dict[str, NPC]
    trade_routes: dict[str, TradeRoute]
    armies: dict[str, Army]
    wars: dict[str, War] = Field(default_factory=dict)
    refugee_camps: dict[str, RefugeeCamp] = Field(default_factory=dict)
    territory_claims: dict[str, dict[str, Any]] = Field(default_factory=dict)
    political_factions: dict[str, PoliticalFaction] = Field(default_factory=dict)
    recent_events: list[HistoricalEvent] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    next_event_sequence: int = 1
    next_entity_sequence: int = 10_000

    @model_validator(mode="after")
    def ensure_regions(self) -> "WorldState":
        if not self.regions:
            self.regions = {self.region.id: self.region}
        return self

    def new_event_id(self) -> str:
        event_id = f"event_{self.next_event_sequence:09d}"
        self.next_event_sequence += 1
        return event_id

    def new_entity_id(self, prefix: str) -> str:
        entity_id = f"{prefix}_{self.next_entity_sequence:07d}"
        self.next_entity_sequence += 1
        return entity_id

    @property
    def total_population(self) -> int:
        settlement_population = sum(settlement.population for settlement in self.settlements.values())
        camp_population = sum(camp.people for camp in self.refugee_camps.values() if camp.status != CampStatus.CLOSED)
        return settlement_population + camp_population

    def alive_npcs(self) -> list[NPC]:
        return [npc for npc in self.npcs.values() if npc.alive]

    def active_wars(self) -> list[War]:
        return [war for war in self.wars.values() if war.state == WarState.ACTIVE]


class CommandEnvelope(BaseModel):
    type: str
    target_id: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)
    issuer: str = "admin"


class CommandRecord(BaseModel):
    id: str
    command: CommandEnvelope
    status: CommandStatus = CommandStatus.QUEUED
    created_at: WorldDate
    completed_at: WorldDate | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
