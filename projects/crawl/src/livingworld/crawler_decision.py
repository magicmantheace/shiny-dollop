from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

from .crawler_domain import CrawlerAgentState


@dataclass(frozen=True)
class CrawlerDecision:
    action: str
    score: float
    reasons: dict[str, float]


ACTIONS = ("seek_exit", "seek_safety", "explore", "recover", "wait")


def _tie_break(seed: str, npc_id: str, decision_count: int, action: str) -> float:
    payload = f"{seed}:{npc_id}:{decision_count}:{action}".encode("utf-8")
    raw = int(sha256(payload).hexdigest()[:8], 16) / 0xFFFFFFFF
    return raw * 0.0001


def score_actions(agent: CrawlerAgentState, *, health: float, seed: str) -> list[CrawlerDecision]:
    """Score bounded non-combat actions using only authoritative crawler state.

    Slice 3 intentionally avoids unrestricted planning or LLM calls. The returned
    reasons are exposed for tests, observability, and future broadcast explanation.
    """

    t = agent.traits
    n = agent.needs
    p = agent.preferences

    health_pressure = 1.0 - max(0.0, min(1.0, health))
    fatigue = 1.0 - n.stamina
    danger = n.perceived_danger
    unknown_interest = (t.curiosity + p.unknown_rooms + t.risk_tolerance) / 3.0

    raw: dict[str, tuple[float, dict[str, float]]] = {
        "seek_exit": (
            0.28
            + 0.36 * t.caution
            + 0.24 * danger
            + 0.18 * health_pressure
            + 0.08 * (1.0 - t.curiosity),
            {
                "caution": t.caution,
                "danger": danger,
                "health_pressure": health_pressure,
            },
        ),
        "seek_safety": (
            0.10
            + 0.42 * health_pressure
            + 0.35 * fatigue
            + 0.30 * danger
            + 0.18 * t.caution,
            {
                "health_pressure": health_pressure,
                "fatigue": fatigue,
                "danger": danger,
            },
        ),
        "explore": (
            0.12
            + 0.48 * unknown_interest
            + 0.12 * agent.skills.navigation
            + 0.10 * agent.skills.perception
            - 0.25 * danger * t.caution
            - 0.20 * health_pressure,
            {
                "curiosity": t.curiosity,
                "risk_tolerance": t.risk_tolerance,
                "unknown_interest": unknown_interest,
            },
        ),
        "recover": (
            0.05
            + 0.50 * fatigue
            + 0.38 * health_pressure
            + 0.18 * n.stress
            + 0.12 * t.patience,
            {
                "fatigue": fatigue,
                "health_pressure": health_pressure,
                "stress": n.stress,
            },
        ),
        "wait": (
            0.02
            + 0.22 * t.patience
            + 0.12 * t.caution
            - 0.15 * t.competitiveness
            - 0.15 * t.curiosity,
            {
                "patience": t.patience,
                "caution": t.caution,
            },
        ),
    }

    decisions: list[CrawlerDecision] = []
    for action in ACTIONS:
        score, reasons = raw[action]
        score += _tie_break(seed, agent.npc_id, agent.decision_count, action)
        decisions.append(CrawlerDecision(action=action, score=score, reasons=reasons))
    decisions.sort(key=lambda item: (-item.score, item.action))
    return decisions


def choose_action(agent: CrawlerAgentState, *, health: float, seed: str) -> CrawlerDecision:
    decision = score_actions(agent, health=health, seed=seed)[0]
    agent.current_goal = decision.action
    agent.last_action = decision.action
    agent.decision_count += 1
    return decision
