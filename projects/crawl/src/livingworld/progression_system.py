from __future__ import annotations

from hashlib import sha256

from .crawl_domain import CrawlerParticipation


ABILITY_TREE = {
    "vanguard": ["brace", "counterstrike", "unyielding"],
    "hunter": ["steady_aim", "quickstep", "mark_target"],
    "survivor": ["field_dressing", "second_wind", "resourceful"],
    "mystic": ["channel", "ward", "arcane_surge"],
}


def experience_for_next_level(level: int) -> float:
    return 100.0 + max(0, level - 1) * 65.0


def award_experience(participant: CrawlerParticipation, amount: float) -> int:
    state = participant.gameplay.progression
    state.experience += max(0.0, amount)
    levels = 0
    while state.experience >= experience_for_next_level(state.level):
        state.experience -= experience_for_next_level(state.level)
        state.level += 1
        state.unspent_points += 1
        levels += 1
    return levels


def _specialization_scores(participant: CrawlerParticipation) -> dict[str, float]:
    agent = participant.agent
    if agent is None:
        return {name: 0.0 for name in ABILITY_TREE}
    return {
        "vanguard": agent.skills.defense * 0.50 + agent.skills.melee * 0.25 + agent.traits.loyalty * 0.15 + agent.traits.courage * 0.10,
        "hunter": agent.skills.ranged * 0.35 + agent.skills.perception * 0.25 + agent.skills.stealth * 0.20 + agent.traits.competitiveness * 0.10 + agent.traits.caution * 0.10,
        "survivor": agent.skills.medicine * 0.30 + agent.skills.scavenging * 0.25 + agent.traits.empathy * 0.20 + agent.traits.caution * 0.15 + agent.traits.patience * 0.10,
        "mystic": agent.skills.ability_use * 0.55 + agent.traits.curiosity * 0.20 + agent.traits.risk_tolerance * 0.15 + agent.traits.competitiveness * 0.10,
    }


def choose_progression(participant: CrawlerParticipation, *, crawl_seed: str) -> list[str]:
    """Spend available advancement points deterministically according to personality and experience."""

    state = participant.gameplay.progression
    choices: list[str] = []
    if state.specialization is None:
        scores = _specialization_scores(participant)
        state.specialization = max(
            scores,
            key=lambda name: (
                scores[name],
                sha256(f"{crawl_seed}:{participant.npc_id}:{name}".encode()).hexdigest(),
            ),
        )
        choices.append(f"specialization:{state.specialization}")

    tree = ABILITY_TREE[state.specialization]
    while state.unspent_points > 0:
        remaining = [ability for ability in tree if ability not in state.ability_ids]
        if remaining:
            index = min(len(remaining) - 1, len(state.ability_ids))
            ability = remaining[index]
            state.ability_ids.append(ability)
            state.choices_made.append(ability)
            choices.append(f"ability:{ability}")
        else:
            key = f"{state.specialization}_mastery"
            state.passive_modifiers[key] = round(state.passive_modifiers.get(key, 0.0) + 0.035, 4)
            state.choices_made.append(key)
            choices.append(f"passive:{key}")
        state.unspent_points -= 1
    return choices


def combat_modifiers(participant: CrawlerParticipation) -> dict[str, float]:
    state = participant.gameplay.progression
    abilities = set(state.ability_ids)
    modifiers = {"attack": 0.0, "defense": 0.0, "accuracy": 0.0, "evasion": 0.0, "heal": 0.0}
    if "brace" in abilities:
        modifiers["defense"] += 0.06
    if "counterstrike" in abilities:
        modifiers["attack"] += 0.05
    if "unyielding" in abilities:
        modifiers["defense"] += 0.04
    if "steady_aim" in abilities:
        modifiers["accuracy"] += 0.07
    if "quickstep" in abilities:
        modifiers["evasion"] += 0.06
    if "mark_target" in abilities:
        modifiers["attack"] += 0.045
    if "field_dressing" in abilities:
        modifiers["heal"] += 0.08
    if "second_wind" in abilities:
        modifiers["defense"] += 0.03
    if "resourceful" in abilities:
        modifiers["evasion"] += 0.025
    if "channel" in abilities:
        modifiers["attack"] += 0.055
    if "ward" in abilities:
        modifiers["defense"] += 0.055
    if "arcane_surge" in abilities:
        modifiers["attack"] += 0.08
    mastery = state.passive_modifiers.get(f"{state.specialization}_mastery", 0.0) if state.specialization else 0.0
    modifiers["attack"] += mastery
    modifiers["defense"] += mastery * 0.75
    return modifiers
