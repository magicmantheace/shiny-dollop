from __future__ import annotations

from hashlib import sha256
from random import Random

from .combat_system import CombatResolution, resolve_combat
from .crawl_domain import Crawl, ParticipationStatus
from .crawl_service import CrawlLifecycleService
from .gameplay_domain import (
    DamageType,
    EncounterState,
    EncounterStatus,
    EncounterType,
    EnemyArchetype,
    EnemyState,
    LootPolicy,
)
from .item_system import choose_and_equip, generate_item, item_score, transfer_item_to_crawler
from .progression_system import award_experience, choose_progression


def _stable_id(prefix: str, *parts: object) -> str:
    digest = sha256(":".join(str(part) for part in parts).encode()).hexdigest()[:20]
    return f"{prefix}_{digest}"


def _rng(seed: str, *parts: object) -> Random:
    digest = sha256(":".join([seed, *(str(part) for part in parts)]).encode()).hexdigest()
    return Random(int(digest[:16], 16))


def _enemy(archetype: EnemyArchetype, encounter_id: str, index: int, difficulty: float, floor_number: int) -> EnemyState:
    scale = 1.0 + difficulty * 0.55 + floor_number * 0.035
    templates = {
        EnemyArchetype.BRUTE: (1.30, 0.125, 0.12, 0.64, 0.03, 0.40),
        EnemyArchetype.SKIRMISHER: (0.82, 0.095, 0.07, 0.78, 0.18, 0.82),
        EnemyArchetype.STALKER: (0.72, 0.105, 0.05, 0.82, 0.24, 0.95),
        EnemyArchetype.CASTER: (0.76, 0.125, 0.06, 0.75, 0.10, 0.70),
        EnemyArchetype.GUARDIAN: (1.15, 0.100, 0.18, 0.68, 0.05, 0.48),
    }
    hp, attack, defense, accuracy, evasion, initiative = templates[archetype]
    enemy_id = _stable_id("enemy", encounter_id, index)
    return EnemyState(
        id=enemy_id,
        archetype=archetype,
        name=f"{archetype.value.title()} {index + 1}",
        health=hp * scale,
        max_health=hp * scale,
        attack=attack * scale,
        defense=defense * scale,
        accuracy=min(0.94, accuracy + difficulty * 0.08),
        evasion=min(0.45, evasion + difficulty * 0.05),
        initiative=initiative,
        damage_type=DamageType.ARCANE if archetype == EnemyArchetype.CASTER else DamageType.PHYSICAL,
    )


def seed_floor_encounters(crawl: Crawl, floor_number: int) -> list[str]:
    """Create deterministic reusable encounter records for one generated floor."""

    floor = crawl.floors[floor_number]
    created: list[str] = []
    for location_id, location in sorted(floor.locations.items()):
        if location.encounter_slots <= 0 and not location.hazards:
            continue
        for slot in range(max(location.encounter_slots, 1 if location.hazards else 0)):
            encounter_id = _stable_id("encounter", crawl.seed, floor_number, location_id, slot)
            if encounter_id in crawl.encounters:
                continue
            rng = _rng(floor.seed, location_id, slot)
            difficulty = min(1.75, floor.danger_level * (0.75 + rng.random() * 0.65) + slot * 0.06)
            roll = rng.random()
            if "severe_hazard" in location.hazards and slot == 0:
                encounter_type = EncounterType.HAZARD
            elif "environmental_pressure" in location.hazards and slot == 0 and roll < 0.42:
                encounter_type = EncounterType.TRAP
            elif roll > 0.95 and floor_number >= 3:
                encounter_type = EncounterType.BOSS
            elif roll > 0.78:
                encounter_type = EncounterType.ELITE
            elif roll < 0.15 and location.loot_resource_nodes:
                encounter_type = EncounterType.RESOURCE_DILEMMA
            else:
                encounter_type = EncounterType.HOSTILE

            enemies: dict[str, EnemyState] = {}
            if encounter_type in {EncounterType.HOSTILE, EncounterType.ELITE, EncounterType.BOSS}:
                count = 1 + int(difficulty > 0.42) + int(difficulty > 0.82)
                if encounter_type == EncounterType.ELITE:
                    count = max(1, count - 1)
                    difficulty *= 1.22
                elif encounter_type == EncounterType.BOSS:
                    count = 1
                    difficulty *= 1.55
                archetypes = list(EnemyArchetype)
                for index in range(count):
                    archetype = archetypes[rng.randrange(len(archetypes))]
                    enemy = _enemy(archetype, encounter_id, index, difficulty, floor_number)
                    if encounter_type == EncounterType.ELITE:
                        enemy.max_health *= 1.35
                        enemy.health = enemy.max_health
                        enemy.attack *= 1.18
                    elif encounter_type == EncounterType.BOSS:
                        enemy.name = f"Floor {floor_number} Apex {archetype.value.title()}"
                        enemy.max_health *= 2.20
                        enemy.health = enemy.max_health
                        enemy.attack *= 1.30
                        enemy.defense *= 1.25
                    enemies[enemy.id] = enemy

            encounter = EncounterState(
                id=encounter_id,
                floor_number=floor_number,
                location_id=location_id,
                type=encounter_type,
                difficulty=difficulty,
                trigger={"type": "location_entry", "once": True},
                enemies=enemies,
                possible_outcomes=["victory", "retreat", "death", "avoidance"],
                failure_consequences={"stress": round(min(0.5, 0.08 + difficulty * 0.12), 4)},
            )
            reward_count = 2 if encounter_type in {EncounterType.ELITE, EncounterType.BOSS} else 1
            if encounter_type in {EncounterType.HOSTILE, EncounterType.ELITE, EncounterType.BOSS, EncounterType.RESOURCE_DILEMMA}:
                for index in range(reward_count):
                    item = generate_item(crawl.seed, source_id=encounter.id, index=index, floor_number=floor_number, holder=encounter.id)
                    crawl.items[item.id] = item
                    encounter.reward_item_ids.append(item.id)
            crawl.encounters[encounter.id] = encounter
            created.append(encounter.id)
    return created


def encounter_at(crawl: Crawl, floor_number: int, location_id: str) -> EncounterState | None:
    candidates = [
        encounter
        for encounter in crawl.encounters.values()
        if encounter.floor_number == floor_number
        and encounter.location_id == location_id
        and encounter.status == EncounterStatus.DORMANT
    ]
    return min(candidates, key=lambda value: value.id) if candidates else None


def _participants_at_location(crawl: Crawl, location_id: str) -> list[str]:
    present = [
        npc_id
        for npc_id, participant in crawl.participants.items()
        if participant.status == ParticipationStatus.ACTIVE
        and participant.current_floor == crawl.current_floor
        and participant.current_location_id == location_id
    ]
    return sorted(present)


def _resolve_hazard(crawl: Crawl, lifecycle: CrawlLifecycleService, encounter: EncounterState) -> str:
    encounter.status = EncounterStatus.ACTIVE
    participants = _participants_at_location(crawl, encounter.location_id)
    encounter.participant_npc_ids = participants
    for npc_id in participants:
        participant = crawl.participants[npc_id]
        agent = participant.agent
        mitigation = 0.20
        if agent is not None:
            mitigation += agent.skills.traps * 0.25 + agent.skills.perception * 0.15 + agent.traits.caution * 0.10
        rng = _rng(crawl.seed, encounter.id, npc_id, crawl.current_tick)
        if rng.random() < max(0.08, 0.70 - mitigation):
            damage = min(0.42, 0.035 + encounter.difficulty * (0.08 + rng.random() * 0.08))
            participant.health = max(0.0, participant.health - damage)
            participant.gameplay.damage_taken += damage
            if participant.agent is not None:
                participant.agent.needs.stress = min(1.0, participant.agent.needs.stress + 0.08 + encounter.difficulty * 0.06)
            lifecycle._record(crawl, "HAZARD_HIT", f"Crawler {npc_id} was caught by a floor hazard.", actor_ids=[npc_id], location_id=encounter.location_id, data={"encounter_id": encounter.id, "damage": damage})
            if participant.health <= 0:
                from .item_system import drop_all_on_death

                dropped = drop_all_on_death(crawl, npc_id)
                lifecycle.eliminate(crawl, npc_id, dead=True, summary=f"Crawler {npc_id} was killed by a floor hazard.")
                lifecycle._record(crawl, "ITEMS_DROPPED_ON_DEATH", "A dead crawler's inventory was dropped.", actor_ids=[npc_id], location_id=encounter.location_id, data={"item_ids": dropped})
    encounter.status = EncounterStatus.RESOLVED
    encounter.cleanup_complete = True
    encounter.resolved_tick = crawl.current_tick
    return "hazard_resolved"


def _single_party(crawl: Crawl, living: list[str]):
    party_ids = {crawl.participants[npc_id].current_party_id for npc_id in living}
    if len(party_ids) != 1 or None in party_ids:
        return None
    party = crawl.parties.get(next(iter(party_ids)))
    return party if party is not None and party.active else None


def _choose_reward_recipient(crawl: Crawl, item, living: list[str]) -> tuple[str, str]:
    party = _single_party(crawl, living)
    if party is None:
        return max(living, key=lambda npc_id: (item_score(item, crawl.participants[npc_id]), npc_id)), "individual_need"

    members = [npc_id for npc_id in party.member_npc_ids if npc_id in living]
    if party.loot_policy == LootPolicy.EQUAL_SHARE:
        recipient = min(
            members,
            key=lambda npc_id: (
                len(crawl.participants[npc_id].gameplay.inventory_item_ids),
                -item_score(item, crawl.participants[npc_id]),
                npc_id,
            ),
        )
        return recipient, party.loot_policy.value
    if party.loot_policy == LootPolicy.FINDERS_KEEPERS:
        recipient = max(
            members,
            key=lambda npc_id: (
                (crawl.participants[npc_id].agent.traits.greed if crawl.participants[npc_id].agent else 0.0)
                + (crawl.participants[npc_id].agent.skills.scavenging if crawl.participants[npc_id].agent else 0.0)
                + item_score(item, crawl.participants[npc_id]),
                npc_id,
            ),
        )
        return recipient, party.loot_policy.value
    if party.loot_policy == LootPolicy.LEADER_ASSIGN:
        recipient = max(
            members,
            key=lambda npc_id: (
                item_score(item, crawl.participants[npc_id])
                + (0.04 if npc_id == party.leader_npc_id else 0.0),
                npc_id,
            ),
        )
        return recipient, party.loot_policy.value
    recipient = max(members, key=lambda npc_id: (item_score(item, crawl.participants[npc_id]), npc_id))
    return recipient, party.loot_policy.value


def _distribute_rewards(crawl: Crawl, lifecycle: CrawlLifecycleService, encounter: EncounterState, eligible_ids: list[str]) -> list[str]:
    living = [
        npc_id
        for npc_id in eligible_ids
        if npc_id in crawl.participants and crawl.participants[npc_id].status == ParticipationStatus.ACTIVE
    ]
    transferred: list[str] = []
    if not living:
        for item_id in encounter.reward_item_ids:
            item = crawl.items[item_id]
            item.encounter_id = None
            item.location_id = encounter.location_id
        return transferred

    for item_id in encounter.reward_item_ids:
        item = crawl.items[item_id]
        recipient, policy = _choose_reward_recipient(crawl, item, living)
        transfer_item_to_crawler(crawl, item_id, recipient)
        choose_and_equip(crawl, recipient)
        transferred.append(item_id)
        lifecycle._record(
            crawl,
            "ITEM_ACQUIRED",
            f"Crawler {recipient} acquired {item.name}.",
            actor_ids=[recipient],
            location_id=encounter.location_id,
            data={"encounter_id": encounter.id, "item_id": item.id, "rarity": item.rarity.value, "distribution_policy": policy},
        )
    return transferred


def resolve_encounter(crawl: Crawl, encounter: EncounterState, lifecycle: CrawlLifecycleService) -> dict[str, object]:
    if encounter.status != EncounterStatus.DORMANT:
        return {"encounter_id": encounter.id, "outcome": encounter.status.value, "already_resolved": True}
    participants = _participants_at_location(crawl, encounter.location_id)
    encounter.participant_npc_ids = participants
    if not participants:
        return {"encounter_id": encounter.id, "outcome": "no_participants"}

    lifecycle._record(crawl, "ENCOUNTER_TRIGGERED", f"Encounter {encounter.id} was triggered.", actor_ids=participants, location_id=encounter.location_id, data={"encounter_id": encounter.id, "type": encounter.type.value, "difficulty": encounter.difficulty})

    combat_result: CombatResolution | None = None
    successful_participants = list(participants)
    if encounter.type in {EncounterType.HOSTILE, EncounterType.ELITE, EncounterType.BOSS}:
        combat_result = resolve_combat(crawl, encounter, lifecycle)
        outcome = combat_result.outcome
        successful_participants = [npc_id for npc_id in participants if npc_id not in combat_result.retreated_npc_ids]
    elif encounter.type in {EncounterType.TRAP, EncounterType.HAZARD}:
        outcome = _resolve_hazard(crawl, lifecycle, encounter)
    else:
        encounter.status = EncounterStatus.RESOLVED
        encounter.cleanup_complete = True
        encounter.resolved_tick = crawl.current_tick
        outcome = "opportunity_resolved"

    rewards: list[str] = []
    if encounter.status == EncounterStatus.RESOLVED:
        rewards = _distribute_rewards(crawl, lifecycle, encounter, successful_participants)
        xp = 18.0 + encounter.difficulty * 65.0
        if encounter.type == EncounterType.ELITE:
            xp *= 1.45
        elif encounter.type == EncounterType.BOSS:
            xp *= 2.6
        for npc_id in successful_participants:
            participant = crawl.participants.get(npc_id)
            if participant is None or participant.status != ParticipationStatus.ACTIVE:
                continue
            levels = award_experience(participant, xp)
            choices = choose_progression(participant, crawl_seed=crawl.seed) if levels else []
            if levels:
                lifecycle._record(crawl, "CRAWLER_ADVANCED", f"Crawler {npc_id} gained {levels} level(s).", actor_ids=[npc_id], location_id=encounter.location_id, data={"levels": levels, "choices": choices, "new_level": participant.gameplay.progression.level})

    lifecycle._record(crawl, "ENCOUNTER_RESOLVED", f"Encounter {encounter.id} resolved: {outcome}.", actor_ids=encounter.participant_npc_ids, location_id=encounter.location_id, data={"encounter_id": encounter.id, "outcome": outcome, "reward_item_ids": rewards, "successful_participant_ids": successful_participants})
    return {
        "encounter_id": encounter.id,
        "outcome": outcome,
        "reward_item_ids": rewards,
        "successful_participant_ids": successful_participants,
        "combat": combat_result,
    }
