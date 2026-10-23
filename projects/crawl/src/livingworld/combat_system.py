from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import sha256

from .crawl_domain import Crawl, ParticipationStatus
from .crawl_service import CrawlLifecycleService
from .gameplay_domain import EncounterState, EncounterStatus, Injury, InjuryKind
from .item_system import drop_all_on_death
from .progression_system import combat_modifiers


@dataclass
class CombatResolution:
    encounter_id: str
    rounds: int = 0
    outcome: str = "unresolved"
    crawler_deaths: list[str] = field(default_factory=list)
    defeated_enemy_ids: list[str] = field(default_factory=list)
    retreated_npc_ids: list[str] = field(default_factory=list)
    damage_events: int = 0


def _roll(crawl: Crawl, encounter: EncounterState, round_number: int, actor_id: str, target_id: str, channel: str) -> float:
    payload = f"{crawl.seed}:{encounter.id}:{round_number}:{actor_id}:{target_id}:{channel}"
    return int(sha256(payload.encode()).hexdigest()[:12], 16) / float(0xFFFFFFFFFFFF)


def _equipped_stats(crawl: Crawl, npc_id: str) -> dict[str, float]:
    participant = crawl.participants[npc_id]
    totals: dict[str, float] = {}
    for item_id in participant.gameplay.equipment.values():
        item = crawl.items.get(item_id)
        if item is None:
            continue
        for key, value in item.stats.items():
            totals[key] = totals.get(key, 0.0) + value * item.durability
    return totals


def _injury_penalties(crawl: Crawl, npc_id: str) -> dict[str, float]:
    participant = crawl.participants[npc_id]
    result = {"accuracy": 0.0, "defense": 0.0, "stamina": 0.0, "movement": 0.0}
    for injury in participant.gameplay.injuries:
        if injury.kind == InjuryKind.REDUCED_ACCURACY:
            result["accuracy"] += injury.severity * 0.22
        elif injury.kind == InjuryKind.IMPAIRED_MOVEMENT:
            result["defense"] += injury.severity * 0.15
            result["movement"] += injury.severity * 0.30
        elif injury.kind == InjuryKind.REDUCED_STAMINA:
            result["stamina"] += injury.severity * 0.25
        elif injury.kind == InjuryKind.INCAPACITATED:
            result["accuracy"] += 0.50
            result["defense"] += 0.40
    return result


def crawler_combat_stats(crawl: Crawl, npc_id: str) -> dict[str, float]:
    participant = crawl.participants[npc_id]
    agent = participant.agent
    if agent is None:
        return {"attack": 0.1, "defense": 0.1, "accuracy": 0.55, "evasion": 0.05}
    equipped = _equipped_stats(crawl, npc_id)
    progression = combat_modifiers(participant)
    penalties = _injury_penalties(crawl, npc_id)
    stamina = participant.gameplay.stamina
    attack_skill = max(agent.skills.melee, agent.skills.ranged * 0.90, agent.skills.ability_use * 0.75)
    return {
        "attack": max(0.02, 0.075 + attack_skill * 0.12 + equipped.get("attack", 0.0) + progression["attack"]) * (0.65 + stamina * 0.35),
        "defense": max(0.0, 0.04 + agent.skills.defense * 0.16 + equipped.get("armor", 0.0) + equipped.get("defense", 0.0) + progression["defense"] - penalties["defense"]),
        "accuracy": max(0.12, min(0.97, 0.48 + attack_skill * 0.35 + equipped.get("accuracy", 0.0) + progression["accuracy"] - penalties["accuracy"])),
        "evasion": max(0.0, min(0.72, 0.04 + agent.skills.defense * 0.14 + agent.skills.stealth * 0.10 + equipped.get("evasion", 0.0) + progression["evasion"])),
    }


def _should_retreat(crawl: Crawl, npc_id: str, encounter: EncounterState, round_number: int) -> bool:
    participant = crawl.participants[npc_id]
    agent = participant.agent
    if agent is None or participant.health <= 0:
        return False
    pressure = (1.0 - participant.health) * 0.60 + (1.0 - participant.gameplay.stamina) * 0.20 + encounter.difficulty * 0.20
    resolve = agent.traits.courage * 0.35 + agent.traits.aggression * 0.25 + agent.traits.loyalty * (0.15 if participant.current_party_id else 0.0)
    caution = agent.traits.caution * 0.35
    threshold = max(0.08, min(0.90, pressure + caution - resolve))
    return _roll(crawl, encounter, round_number, npc_id, "retreat", "retreat") < threshold


def _apply_injury(
    crawl: Crawl,
    lifecycle: CrawlLifecycleService,
    npc_id: str,
    source_id: str,
    damage: float,
    encounter: EncounterState,
    round_number: int,
) -> None:
    participant = crawl.participants[npc_id]
    if participant.status != ParticipationStatus.ACTIVE or damage < 0.055:
        return
    roll = _roll(crawl, encounter, round_number, source_id, npc_id, "injury")
    chance = min(0.82, damage * 2.2 + (1.0 - participant.health) * 0.35)
    if roll >= chance:
        return
    kinds = [InjuryKind.BLEEDING, InjuryKind.IMPAIRED_MOVEMENT, InjuryKind.REDUCED_ACCURACY, InjuryKind.REDUCED_STAMINA]
    kind = kinds[int(_roll(crawl, encounter, round_number, npc_id, source_id, "injury_kind") * len(kinds)) % len(kinds)]
    severity = max(0.1, min(0.9, damage * 1.8 + (1.0 - participant.health) * 0.25))
    injury = Injury(kind=kind, severity=severity, applied_tick=crawl.current_tick, source_id=source_id)
    participant.gameplay.injuries.append(injury)
    lifecycle._record(
        crawl,
        "CRAWLER_INJURED",
        f"Crawler {npc_id} suffered {kind.value}.",
        actor_ids=[npc_id, source_id],
        location_id=participant.current_location_id,
        data={"encounter_id": encounter.id, "injury": kind.value, "severity": severity},
    )


def _apply_bleeding(crawl: Crawl, lifecycle: CrawlLifecycleService, npc_id: str, encounter: EncounterState) -> bool:
    participant = crawl.participants[npc_id]
    bleed = sum(injury.severity for injury in participant.gameplay.injuries if injury.kind == InjuryKind.BLEEDING)
    if bleed <= 0:
        return False
    damage = min(0.08, bleed * 0.012)
    participant.health = max(0.0, participant.health - damage)
    participant.gameplay.damage_taken += damage
    if participant.health <= 0:
        dropped = drop_all_on_death(crawl, npc_id)
        lifecycle.eliminate(crawl, npc_id, dead=True, summary=f"Crawler {npc_id} died from injuries during encounter {encounter.id}.")
        lifecycle._record(crawl, "ITEMS_DROPPED_ON_DEATH", "A dead crawler's inventory was dropped.", actor_ids=[npc_id], location_id=participant.current_location_id, data={"item_ids": dropped})
        return True
    return False


def resolve_combat(
    crawl: Crawl,
    encounter: EncounterState,
    lifecycle: CrawlLifecycleService,
    *,
    max_rounds: int = 40,
) -> CombatResolution:
    """Resolve one deterministic individual/small-group combat encounter."""

    encounter.status = EncounterStatus.ACTIVE
    resolution = CombatResolution(encounter_id=encounter.id)
    crawler_ids = [
        npc_id
        for npc_id in sorted(set(encounter.participant_npc_ids))
        if npc_id in crawl.participants and crawl.participants[npc_id].status == ParticipationStatus.ACTIVE
    ]
    active_crawlers = set(crawler_ids)

    lifecycle._record(
        crawl,
        "COMBAT_STARTED",
        f"Combat began in encounter {encounter.id}.",
        actor_ids=crawler_ids,
        location_id=encounter.location_id,
        data={"encounter_id": encounter.id, "enemy_ids": sorted(encounter.enemies)},
    )

    for round_number in range(1, max_rounds + 1):
        resolution.rounds = round_number
        living_enemies = [enemy for enemy in encounter.enemies.values() if enemy.alive and enemy.health > 0]
        active_crawlers = {npc_id for npc_id in active_crawlers if crawl.participants[npc_id].status == ParticipationStatus.ACTIVE}
        if not living_enemies or not active_crawlers:
            break

        for npc_id in sorted(active_crawlers):
            participant = crawl.participants[npc_id]
            if _apply_bleeding(crawl, lifecycle, npc_id, encounter):
                resolution.crawler_deaths.append(npc_id)
                continue
            if _should_retreat(crawl, npc_id, encounter, round_number):
                resolution.retreated_npc_ids.append(npc_id)
                active_crawlers.discard(npc_id)
                lifecycle._record(crawl, "CRAWLER_RETREATED", f"Crawler {npc_id} retreated from combat.", actor_ids=[npc_id], location_id=encounter.location_id, data={"encounter_id": encounter.id})
                continue
            living_enemies = [enemy for enemy in encounter.enemies.values() if enemy.alive and enemy.health > 0]
            if not living_enemies:
                break
            target = min(living_enemies, key=lambda enemy: (enemy.health / enemy.max_health, enemy.id))
            stats = crawler_combat_stats(crawl, npc_id)
            hit_roll = _roll(crawl, encounter, round_number, npc_id, target.id, "hit")
            hit_chance = max(0.08, min(0.96, stats["accuracy"] - target.evasion * 0.45))
            participant.gameplay.stamina = max(0.0, participant.gameplay.stamina - 0.025)
            if hit_roll <= hit_chance:
                variance = 0.82 + _roll(crawl, encounter, round_number, npc_id, target.id, "damage") * 0.36
                damage = max(0.01, stats["attack"] * variance - target.defense * 0.30)
                target.health = max(0.0, target.health - damage)
                participant.gameplay.damage_dealt += damage
                resolution.damage_events += 1
                lifecycle._record(crawl, "COMBAT_HIT", f"Crawler {npc_id} hit {target.id}.", actor_ids=[npc_id, target.id], location_id=encounter.location_id, data={"encounter_id": encounter.id, "damage": damage, "target_health": target.health})
                if target.health <= 0 and target.alive:
                    target.alive = False
                    participant.gameplay.kills += 1
                    resolution.defeated_enemy_ids.append(target.id)
                    lifecycle._record(crawl, "ENEMY_DEFEATED", f"Crawler {npc_id} defeated {target.name}.", actor_ids=[npc_id, target.id], location_id=encounter.location_id, data={"encounter_id": encounter.id})

        living_enemies = [enemy for enemy in encounter.enemies.values() if enemy.alive and enemy.health > 0]
        active_crawlers = {npc_id for npc_id in active_crawlers if crawl.participants[npc_id].status == ParticipationStatus.ACTIVE}
        if not living_enemies or not active_crawlers:
            continue

        for enemy in sorted(living_enemies, key=lambda value: (-value.initiative, value.id)):
            targets = [npc_id for npc_id in active_crawlers if crawl.participants[npc_id].status == ParticipationStatus.ACTIVE]
            if not targets:
                break
            target_id = min(targets, key=lambda npc_id: (crawl.participants[npc_id].health, npc_id))
            target = crawl.participants[target_id]
            stats = crawler_combat_stats(crawl, target_id)
            hit_roll = _roll(crawl, encounter, round_number, enemy.id, target_id, "enemy_hit")
            hit_chance = max(0.08, min(0.94, enemy.accuracy - stats["evasion"] * 0.55))
            if hit_roll > hit_chance:
                continue
            variance = 0.82 + _roll(crawl, encounter, round_number, enemy.id, target_id, "enemy_damage") * 0.36
            damage = max(0.008, enemy.attack * variance - stats["defense"] * 0.28)
            target.health = max(0.0, target.health - damage)
            target.gameplay.damage_taken += damage
            target.gameplay.stamina = max(0.0, target.gameplay.stamina - 0.018)
            resolution.damage_events += 1
            lifecycle._record(crawl, "CRAWLER_DAMAGED", f"Crawler {target_id} was hit by {enemy.name}.", actor_ids=[target_id, enemy.id], location_id=encounter.location_id, data={"encounter_id": encounter.id, "damage": damage, "health": target.health})
            _apply_injury(crawl, lifecycle, target_id, enemy.id, damage, encounter, round_number)
            if target.health <= 0:
                dropped = drop_all_on_death(crawl, target_id)
                lifecycle.eliminate(crawl, target_id, dead=True, summary=f"Crawler {target_id} was killed during encounter {encounter.id}.")
                lifecycle._record(crawl, "ITEMS_DROPPED_ON_DEATH", "A dead crawler's inventory was dropped.", actor_ids=[target_id], location_id=target.current_location_id, data={"item_ids": dropped})
                resolution.crawler_deaths.append(target_id)
                active_crawlers.discard(target_id)

    living_enemies = [enemy for enemy in encounter.enemies.values() if enemy.alive and enemy.health > 0]
    living_crawlers = [npc_id for npc_id in crawler_ids if crawl.participants[npc_id].status == ParticipationStatus.ACTIVE and npc_id not in resolution.retreated_npc_ids]
    if not living_enemies:
        encounter.status = EncounterStatus.RESOLVED
        encounter.cleanup_complete = True
        resolution.outcome = "victory"
        for npc_id in living_crawlers:
            crawl.participants[npc_id].gameplay.encounters_survived += 1
    elif not living_crawlers:
        encounter.status = EncounterStatus.FAILED
        encounter.cleanup_complete = True
        resolution.outcome = "defeat_or_retreat"
    else:
        encounter.status = EncounterStatus.FAILED
        encounter.cleanup_complete = True
        resolution.outcome = "timeout"
    encounter.resolved_tick = crawl.current_tick

    lifecycle._record(
        crawl,
        "COMBAT_ENDED",
        f"Combat encounter {encounter.id} ended with {resolution.outcome}.",
        actor_ids=crawler_ids,
        location_id=encounter.location_id,
        data={
            "encounter_id": encounter.id,
            "outcome": resolution.outcome,
            "rounds": resolution.rounds,
            "crawler_deaths": resolution.crawler_deaths,
            "defeated_enemy_ids": resolution.defeated_enemy_ids,
            "retreated_npc_ids": resolution.retreated_npc_ids,
        },
    )
    return resolution
