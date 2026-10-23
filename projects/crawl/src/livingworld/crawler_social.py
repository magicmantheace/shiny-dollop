from __future__ import annotations

from .crawler_domain import CrawlerAgentState, CrawlerMemory, CrawlerRelationship


def relationship(agent: CrawlerAgentState, target_id: str) -> CrawlerRelationship:
    current = agent.relationships.get(target_id)
    if current is None:
        current = CrawlerRelationship(target_id=target_id)
        agent.relationships[target_id] = current
    return current


def remember(
    agent: CrawlerAgentState,
    *,
    event_id: str,
    event_type: str,
    tick: int,
    floor_number: int,
    subject_id: str | None = None,
    emotion: str = "neutral",
    importance: float = 0.5,
    confidence: float = 1.0,
) -> CrawlerMemory:
    existing = next((memory for memory in agent.memories if memory.event_id == event_id), None)
    if existing is not None:
        return existing
    memory = CrawlerMemory(
        event_id=event_id,
        event_type=event_type,
        subject_id=subject_id,
        emotion=emotion,
        importance=max(0.0, min(1.0, importance)),
        confidence=max(0.0, min(1.0, confidence)),
        tick=tick,
        floor_number=floor_number,
    )
    agent.memories.append(memory)
    agent.memories.sort(key=lambda item: (-item.importance, -item.tick, item.event_id))
    del agent.memories[128:]
    return memory


def apply_social_event(
    agent: CrawlerAgentState,
    *,
    target_id: str,
    event_type: str,
    magnitude: float = 0.25,
) -> CrawlerRelationship:
    """Apply bounded relationship consequences from a structured event category."""

    rel = relationship(agent, target_id)
    amount = max(0.0, min(1.0, magnitude))
    rel.familiarity = min(1.0, rel.familiarity + amount * 0.35)

    if event_type in {"rescue", "healed", "shared_resource", "warning_proven_true"}:
        rel.trust = min(1.0, rel.trust + amount * 0.70)
        rel.gratitude = min(1.0, rel.gratitude + amount)
        rel.affection = min(1.0, rel.affection + amount * 0.35)
        rel.respect = min(1.0, rel.respect + amount * 0.45)
        rel.perceived_reliability = min(1.0, rel.perceived_reliability + amount * 0.45)
    elif event_type in {"abandoned", "betrayed", "stole_loot", "warning_proven_false"}:
        rel.trust = max(-1.0, rel.trust - amount * 0.85)
        rel.resentment = min(1.0, rel.resentment + amount)
        rel.affection = max(-1.0, rel.affection - amount * 0.45)
        rel.perceived_reliability = max(0.0, rel.perceived_reliability - amount * 0.55)
    elif event_type in {"rival_success", "competition_loss"}:
        rel.rivalry = min(1.0, rel.rivalry + amount * 0.75)
        rel.respect = min(1.0, rel.respect + amount * 0.25)
    elif event_type in {"threatened", "attacked"}:
        rel.fear = min(1.0, rel.fear + amount * 0.60)
        rel.resentment = min(1.0, rel.resentment + amount * 0.70)
        rel.trust = max(-1.0, rel.trust - amount * 0.65)

    return rel


def willingness_to_help(agent: CrawlerAgentState, target_id: str) -> float:
    rel = relationship(agent, target_id)
    social = (
        0.30 * max(0.0, rel.trust)
        + 0.20 * max(0.0, rel.affection)
        + 0.20 * rel.gratitude
        + 0.10 * max(0.0, rel.respect)
        + 0.10 * agent.traits.loyalty
        + 0.10 * agent.traits.empathy
    )
    penalties = 0.25 * rel.fear + 0.30 * rel.resentment
    return max(0.0, min(1.0, social - penalties))
