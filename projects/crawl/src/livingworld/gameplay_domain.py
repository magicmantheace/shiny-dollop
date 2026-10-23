from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, model_validator


class DamageType(StrEnum):
    PHYSICAL = "physical"
    FIRE = "fire"
    COLD = "cold"
    ARCANE = "arcane"
    POISON = "poison"


class InjuryKind(StrEnum):
    BLEEDING = "bleeding"
    IMPAIRED_MOVEMENT = "impaired_movement"
    REDUCED_ACCURACY = "reduced_accuracy"
    REDUCED_STAMINA = "reduced_stamina"
    INCAPACITATED = "incapacitated"


class ItemCategory(StrEnum):
    WEAPON = "weapon"
    ARMOR = "armor"
    CONSUMABLE = "consumable"
    TRINKET = "trinket"
    RESOURCE = "resource"


class ItemRarity(StrEnum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"


class EquipmentSlot(StrEnum):
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    ARMOR = "armor"
    TRINKET = "trinket"


class EncounterType(StrEnum):
    HOSTILE = "hostile"
    ELITE = "elite"
    BOSS = "boss"
    TRAP = "trap"
    HAZARD = "hazard"
    RESOURCE_DILEMMA = "resource_dilemma"
    SOCIAL_DILEMMA = "social_dilemma"
    TIMED_THREAT = "timed_threat"
    PURSUIT = "pursuit"
    RESCUE = "rescue"


class EncounterStatus(StrEnum):
    DORMANT = "dormant"
    ACTIVE = "active"
    RESOLVED = "resolved"
    FAILED = "failed"


class EnemyArchetype(StrEnum):
    BRUTE = "brute"
    SKIRMISHER = "skirmisher"
    STALKER = "stalker"
    CASTER = "caster"
    GUARDIAN = "guardian"


class LootPolicy(StrEnum):
    FINDERS_KEEPERS = "finders_keepers"
    NEED_BEFORE_GREED = "need_before_greed"
    LEADER_ASSIGN = "leader_assign"
    EQUAL_SHARE = "equal_share"


class Injury(BaseModel):
    kind: InjuryKind
    severity: float = Field(ge=0.0, le=1.0)
    applied_tick: int = Field(ge=0)
    source_id: str | None = None


class CrawlItem(BaseModel):
    id: str
    name: str
    category: ItemCategory
    rarity: ItemRarity = ItemRarity.COMMON
    slot: EquipmentSlot | None = None
    stats: dict[str, float] = Field(default_factory=dict)
    effects: dict[str, float] = Field(default_factory=dict)
    durability: float = Field(default=1.0, ge=0.0, le=1.0)
    requirements: dict[str, float] = Field(default_factory=dict)
    owner_npc_id: str | None = None
    location_id: str | None = None
    encounter_id: str | None = None
    provenance_event_ids: list[str] = Field(default_factory=list)
    important: bool = False

    @model_validator(mode="after")
    def validate_authoritative_location(self) -> "CrawlItem":
        holders = sum(value is not None for value in (self.owner_npc_id, self.location_id, self.encounter_id))
        if holders != 1:
            raise ValueError("item must have exactly one authoritative owner/location/encounter")
        if self.category in {ItemCategory.WEAPON, ItemCategory.ARMOR, ItemCategory.TRINKET} and self.slot is None:
            raise ValueError("equippable items require an equipment slot")
        return self


class CrawlerProgression(BaseModel):
    level: int = Field(default=1, ge=1)
    experience: float = Field(default=0.0, ge=0.0)
    unspent_points: int = Field(default=0, ge=0)
    specialization: str | None = None
    ability_ids: list[str] = Field(default_factory=list)
    passive_modifiers: dict[str, float] = Field(default_factory=dict)
    choices_made: list[str] = Field(default_factory=list)


class CrawlerGameplayState(BaseModel):
    stamina: float = Field(default=1.0, ge=0.0, le=1.0)
    injuries: list[Injury] = Field(default_factory=list)
    status_effects: dict[str, float] = Field(default_factory=dict)
    inventory_item_ids: list[str] = Field(default_factory=list)
    equipment: dict[str, str] = Field(default_factory=dict)
    progression: CrawlerProgression = Field(default_factory=CrawlerProgression)
    kills: int = Field(default=0, ge=0)
    damage_dealt: float = Field(default=0.0, ge=0.0)
    damage_taken: float = Field(default=0.0, ge=0.0)
    encounters_survived: int = Field(default=0, ge=0)
    incapacitated: bool = False


class CrawlParty(BaseModel):
    id: str
    leader_npc_id: str
    member_npc_ids: list[str]
    loot_policy: LootPolicy = LootPolicy.NEED_BEFORE_GREED
    cohesion: float = Field(default=0.5, ge=0.0, le=1.0)
    formed_tick: int = Field(ge=0)
    active: bool = True
    shared_goal: str = "survive"
    disagreement: float = Field(default=0.0, ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_membership(self) -> "CrawlParty":
        if not self.member_npc_ids:
            raise ValueError("party must contain at least one member")
        if len(self.member_npc_ids) != len(set(self.member_npc_ids)):
            raise ValueError("party members must be unique")
        if self.leader_npc_id not in self.member_npc_ids:
            raise ValueError("party leader must be a member")
        return self


class EnemyState(BaseModel):
    id: str
    archetype: EnemyArchetype
    name: str
    health: float = Field(ge=0.0)
    max_health: float = Field(gt=0.0)
    attack: float = Field(ge=0.0)
    defense: float = Field(ge=0.0)
    accuracy: float = Field(ge=0.0, le=1.0)
    evasion: float = Field(ge=0.0, le=1.0)
    initiative: float = Field(ge=0.0)
    damage_type: DamageType = DamageType.PHYSICAL
    alive: bool = True


class EncounterState(BaseModel):
    id: str
    floor_number: int = Field(ge=1)
    location_id: str
    type: EncounterType
    status: EncounterStatus = EncounterStatus.DORMANT
    difficulty: float = Field(default=0.25, ge=0.0)
    trigger: dict[str, Any] = Field(default_factory=dict)
    participant_npc_ids: list[str] = Field(default_factory=list)
    enemies: dict[str, EnemyState] = Field(default_factory=dict)
    reward_item_ids: list[str] = Field(default_factory=list)
    possible_outcomes: list[str] = Field(default_factory=lambda: ["victory", "retreat", "death"])
    failure_consequences: dict[str, Any] = Field(default_factory=dict)
    cleanup_complete: bool = False
    resolved_tick: int | None = Field(default=None, ge=0)
