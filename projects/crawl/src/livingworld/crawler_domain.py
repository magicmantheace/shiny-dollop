from __future__ import annotations

from hashlib import sha256
from random import Random

from pydantic import BaseModel, Field


class CrawlerTraits(BaseModel):
    courage: float = Field(ge=0.0, le=1.0)
    caution: float = Field(ge=0.0, le=1.0)
    aggression: float = Field(ge=0.0, le=1.0)
    curiosity: float = Field(ge=0.0, le=1.0)
    greed: float = Field(ge=0.0, le=1.0)
    loyalty: float = Field(ge=0.0, le=1.0)
    empathy: float = Field(ge=0.0, le=1.0)
    patience: float = Field(ge=0.0, le=1.0)
    sociability: float = Field(ge=0.0, le=1.0)
    suspicion: float = Field(ge=0.0, le=1.0)
    competitiveness: float = Field(ge=0.0, le=1.0)
    risk_tolerance: float = Field(ge=0.0, le=1.0)


class CrawlerSkills(BaseModel):
    melee: float = Field(ge=0.0, le=1.0)
    ranged: float = Field(ge=0.0, le=1.0)
    defense: float = Field(ge=0.0, le=1.0)
    perception: float = Field(ge=0.0, le=1.0)
    stealth: float = Field(ge=0.0, le=1.0)
    navigation: float = Field(ge=0.0, le=1.0)
    medicine: float = Field(ge=0.0, le=1.0)
    traps: float = Field(ge=0.0, le=1.0)
    negotiation: float = Field(ge=0.0, le=1.0)
    leadership: float = Field(ge=0.0, le=1.0)
    scavenging: float = Field(ge=0.0, le=1.0)
    ability_use: float = Field(ge=0.0, le=1.0)


class CrawlerNeeds(BaseModel):
    stamina: float = Field(default=1.0, ge=0.0, le=1.0)
    hunger: float = Field(default=0.0, ge=0.0, le=1.0)
    stress: float = Field(default=0.0, ge=0.0, le=1.0)
    morale: float = Field(default=0.75, ge=0.0, le=1.0)
    perceived_danger: float = Field(default=0.0, ge=0.0, le=1.0)
    equipment_readiness: float = Field(default=0.5, ge=0.0, le=1.0)


class CrawlerPreferences(BaseModel):
    combat: float = Field(ge=0.0, le=1.0)
    crowds: float = Field(ge=0.0, le=1.0)
    darkness: float = Field(ge=0.0, le=1.0)
    unknown_rooms: float = Field(ge=0.0, le=1.0)
    high_risk_loot: float = Field(ge=0.0, le=1.0)
    magical_hazards: float = Field(ge=0.0, le=1.0)


class LocationKnowledge(BaseModel):
    location_id: str
    last_observed_tick: int = Field(ge=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    known_neighbors: dict[str, float] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    hazard_tags: list[str] = Field(default_factory=list)
    believed_safe: bool = False
    believed_exit: bool = False
    visits: int = Field(default=0, ge=0)


class CrawlerMemory(BaseModel):
    event_id: str
    event_type: str
    subject_id: str | None = None
    emotion: str = "neutral"
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    tick: int = Field(ge=0)
    floor_number: int = Field(ge=1)
    resolved: bool = False


class CrawlerRelationship(BaseModel):
    target_id: str
    trust: float = Field(default=0.0, ge=-1.0, le=1.0)
    affection: float = Field(default=0.0, ge=-1.0, le=1.0)
    respect: float = Field(default=0.0, ge=-1.0, le=1.0)
    fear: float = Field(default=0.0, ge=0.0, le=1.0)
    resentment: float = Field(default=0.0, ge=0.0, le=1.0)
    gratitude: float = Field(default=0.0, ge=0.0, le=1.0)
    rivalry: float = Field(default=0.0, ge=0.0, le=1.0)
    familiarity: float = Field(default=0.0, ge=0.0, le=1.0)
    perceived_reliability: float = Field(default=0.5, ge=0.0, le=1.0)


class CrawlerAgentState(BaseModel):
    npc_id: str
    traits: CrawlerTraits
    skills: CrawlerSkills
    needs: CrawlerNeeds = Field(default_factory=CrawlerNeeds)
    preferences: CrawlerPreferences
    knowledge: dict[str, LocationKnowledge] = Field(default_factory=dict)
    memories: list[CrawlerMemory] = Field(default_factory=list)
    relationships: dict[str, CrawlerRelationship] = Field(default_factory=dict)
    current_goal: str = "survive"
    current_plan: list[str] = Field(default_factory=list)
    last_action: str | None = None
    decision_count: int = Field(default=0, ge=0)


def _rng(seed: str, npc_id: str) -> Random:
    digest = sha256(f"{seed}:crawler:{npc_id}".encode("utf-8")).hexdigest()
    return Random(int(digest[:16], 16))


def build_crawler_agent(seed: str, npc_id: str) -> CrawlerAgentState:
    """Create a deterministic crawler profile from the crawl seed and persistent NPC id."""

    rng = _rng(seed, npc_id)

    def value(low: float = 0.12, high: float = 0.88) -> float:
        return round(low + (high - low) * rng.random(), 4)

    courage = value()
    caution = value()
    risk = max(0.0, min(1.0, round((courage + value() - caution * 0.35) / 1.65, 4)))
    traits = CrawlerTraits(
        courage=courage,
        caution=caution,
        aggression=value(),
        curiosity=value(),
        greed=value(),
        loyalty=value(),
        empathy=value(),
        patience=value(),
        sociability=value(),
        suspicion=value(),
        competitiveness=value(),
        risk_tolerance=risk,
    )
    skills = CrawlerSkills(
        melee=value(0.08, 0.72),
        ranged=value(0.08, 0.72),
        defense=value(0.08, 0.72),
        perception=value(0.12, 0.82),
        stealth=value(0.08, 0.72),
        navigation=value(0.12, 0.82),
        medicine=value(0.04, 0.62),
        traps=value(0.04, 0.62),
        negotiation=value(0.08, 0.76),
        leadership=value(0.08, 0.76),
        scavenging=value(0.12, 0.82),
        ability_use=value(0.06, 0.68),
    )
    preferences = CrawlerPreferences(
        combat=round((traits.aggression + traits.courage) / 2.0, 4),
        crowds=traits.sociability,
        darkness=value(),
        unknown_rooms=round((traits.curiosity + traits.risk_tolerance) / 2.0, 4),
        high_risk_loot=round((traits.greed + traits.risk_tolerance) / 2.0, 4),
        magical_hazards=value(),
    )
    needs = CrawlerNeeds(
        stamina=1.0,
        hunger=0.0,
        stress=round((1.0 - traits.courage) * 0.08, 4),
        morale=round(0.55 + traits.courage * 0.35, 4),
        perceived_danger=0.0,
        equipment_readiness=round(0.35 + skills.defense * 0.35, 4),
    )
    return CrawlerAgentState(
        npc_id=npc_id,
        traits=traits,
        skills=skills,
        needs=needs,
        preferences=preferences,
    )
