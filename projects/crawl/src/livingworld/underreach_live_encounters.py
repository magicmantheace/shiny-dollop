"""Canonical promotion and live-combat proof for Underreach Slice 29C.2.

29C.1 encounter plans are deterministic content scaffolding, but they are not
canonical combat state. This module provides an explicit promotion boundary into
the existing deterministic Crawl combat engine and then derives a presentation
snapshot strictly from the resulting authoritative Ledger.

Internal Crawl/Crawler naming remains for serialization compatibility. Public
29C.2 metadata uses Underreach/Descender terminology.
"""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from typing import Any

from .combat_system import CombatResolution, resolve_combat
from .crawl_domain import Crawl, ParticipationStatus
from .crawl_persistence import CrawlPersistence
from .crawl_service import CrawlLifecycleService
from .gameplay_domain import DamageType, EncounterState, EncounterType, EnemyArchetype, EnemyState
from .monster_encounters import MONSTER_DEFINITIONS, build_encounter_plan
from .stratum_environment import build_stratum_environment_manifest
from .stratum_theme import build_stratum_theme_manifest

CANONICAL_PROTOCOL = "underreach.live-encounter-canonical.v1"
PRESENTATION_PROTOCOL = "underreach.live-encounter-presentation.v1"
GENERATOR_VERSION = "29c2.1"

_FAMILY_ARCHETYPE = {
    "burrower": EnemyArchetype.BRUTE,
    "stalker": EnemyArchetype.STALKER,
    "thrall": EnemyArchetype.SKIRMISHER,
    "hound": EnemyArchetype.SKIRMISHER,
    "construct": EnemyArchetype.GUARDIAN,
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def rebuild_digest(proof: dict[str, Any]) -> str:
    payload = dict(proof)
    payload.pop("digest", None)
    return _digest(payload)


def _enemy_state(member: dict[str, Any]) -> EnemyState:
    monster_id = str(member["monster_id"])
    definition = MONSTER_DEFINITIONS[monster_id]
    threat = int(definition["threat"])
    family = str(definition["family"])
    max_health = round(0.16 + threat * 0.055, 6)
    return EnemyState(
        id=str(member["member_id"]),
        archetype=_FAMILY_ARCHETYPE.get(family, EnemyArchetype.BRUTE),
        name=str(definition["display_name"]),
        health=max_health,
        max_health=max_health,
        attack=round(0.018 + threat * 0.010, 6),
        defense=round(0.008 + threat * 0.006, 6),
        accuracy=min(0.78, round(0.46 + threat * 0.045, 6)),
        evasion=min(0.22, round(0.025 + threat * 0.025, 6)),
        initiative=round(0.30 + threat * 0.08, 6),
        damage_type=DamageType.PHYSICAL,
        alive=True,
    )


def promote_encounter(
    crawl: Crawl,
    encounter_plan: dict[str, Any],
    source_encounter: dict[str, Any],
    *,
    participant_npc_ids: list[str],
) -> EncounterState:
    """Explicitly promote one 29C.1 plan entry into canonical combat state."""
    if encounter_plan.get("protocol") != "underreach.encounter-plan.v1":
        raise ValueError("29C.2 requires an accepted 29C.1 encounter plan")
    if encounter_plan.get("authoritative") is not False:
        raise ValueError("source encounter plan must remain non-authoritative")
    if source_encounter not in encounter_plan.get("encounters", []):
        raise ValueError("source encounter is not part of supplied encounter plan")
    if not participant_npc_ids:
        raise ValueError("live encounter promotion requires at least one Descender")

    active_ids = []
    for npc_id in sorted(set(participant_npc_ids)):
        participant = crawl.participants.get(npc_id)
        if participant is None or participant.status != ParticipationStatus.ACTIVE:
            raise ValueError(f"Descender {npc_id!r} is not active in canonical simulation")
        active_ids.append(npc_id)

    floor = crawl.floors[crawl.current_floor]
    # The Stratum Sector graph is still a presentation/content graph in 29C.2.
    # Bind the source Sector in trigger metadata while using a valid canonical
    # CrawlLocation for combat ownership. A later slice can formally migrate the
    # Stratum graph into canonical traversal state.
    location_id = floor.entrance_location_id
    for npc_id in active_ids:
        crawl.participants[npc_id].current_location_id = location_id
        crawl.participants[npc_id].current_floor = crawl.current_floor

    enemies = {
        str(member["member_id"]): _enemy_state(member)
        for member in source_encounter["members"]
    }
    total_threat = int(source_encounter["total_threat"])
    encounter = EncounterState(
        id=f"underreach_live_{source_encounter['encounter_id']}",
        floor_number=crawl.current_floor,
        location_id=location_id,
        type=EncounterType.ELITE if total_threat >= 6 else EncounterType.HOSTILE,
        difficulty=min(1.0, round(total_threat / 12.0, 6)),
        trigger={
            "source": "underreach_29c1_promotion",
            "source_plan_digest": encounter_plan["digest"],
            "source_encounter_id": source_encounter["encounter_id"],
            "source_sector_id": source_encounter["sector_id"],
            "source_theme": source_encounter["theme"],
            "source_member_ids": [member["member_id"] for member in source_encounter["members"]],
            "promotion_protocol": CANONICAL_PROTOCOL,
        },
        participant_npc_ids=active_ids,
        enemies=enemies,
        possible_outcomes=["victory", "retreat", "death", "timeout"],
    )
    if encounter.id in crawl.encounters:
        raise ValueError("canonical encounter id already exists")
    crawl.encounters[encounter.id] = encounter
    return encounter


def _events_for_encounter(events: list[Any], encounter_id: str) -> list[Any]:
    selected = []
    for event in events:
        if event.data.get("encounter_id") == encounter_id:
            selected.append(event)
        elif event.event_type == "UNDERREACH_ENCOUNTER_PROMOTED" and event.data.get("canonical_encounter_id") == encounter_id:
            selected.append(event)
    return selected


def _presentation_from_truth(
    *,
    canonical_digest: str,
    source_sector: dict[str, Any],
    source_encounter: dict[str, Any],
    resolution: CombatResolution,
    participant_final: dict[str, Any],
    enemy_final: dict[str, Any],
    ledger_events: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a presentation contract that can only repeat canonical outcomes."""
    return {
        "protocol": PRESENTATION_PROTOCOL,
        "authoritative": False,
        "canonical_digest": canonical_digest,
        "sector_id": source_encounter["sector_id"],
        "sector_world_origin_cm": dict(source_sector["world_origin_cm"]),
        "monster_spawns": [
            {
                "member_id": member["member_id"],
                "monster_id": member["monster_id"],
                "local_offset_cm": dict(member["local_offset_cm"]),
            }
            for member in source_encounter["members"]
        ],
        "outcome": resolution.outcome,
        "defeated_enemy_ids": sorted(resolution.defeated_enemy_ids),
        "dead_descender_ids": sorted(resolution.crawler_deaths),
        "retreated_descender_ids": sorted(resolution.retreated_npc_ids),
        "participant_final": participant_final,
        "enemy_final": enemy_final,
        "ledger_event_ids": [event["id"] for event in ledger_events],
    }


def validate_presentation_against_truth(presentation: dict[str, Any], truth: dict[str, Any]) -> bool:
    if presentation.get("protocol") != PRESENTATION_PROTOCOL or presentation.get("authoritative") is not False:
        raise ValueError("29C.2 presentation must remain non-authoritative")
    if presentation.get("canonical_digest") != truth.get("canonical_digest"):
        raise ValueError("presentation is not bound to canonical combat truth")
    resolution = truth["resolution"]
    expected = {
        "outcome": resolution["outcome"],
        "defeated_enemy_ids": sorted(resolution["defeated_enemy_ids"]),
        "dead_descender_ids": sorted(resolution["crawler_deaths"]),
        "retreated_descender_ids": sorted(resolution["retreated_npc_ids"]),
    }
    for key, value in expected.items():
        if presentation.get(key) != value:
            raise ValueError(f"presentation altered canonical {key}")
    if presentation.get("participant_final") != truth["participant_final"]:
        raise ValueError("presentation altered canonical Descender final state")
    if presentation.get("enemy_final") != truth["enemy_final"]:
        raise ValueError("presentation altered canonical monster final state")
    if presentation.get("ledger_event_ids") != [event["id"] for event in truth["ledger_events"]]:
        raise ValueError("presentation changed canonical Ledger event identity/order")
    return True


def build_live_encounter_proof(
    seed: str = "underreach-29c2-live-proof",
    *,
    theme: str = "ancient_stoneworks",
    sector_count: int = 12,
    descender_count: int = 3,
) -> dict[str, Any]:
    """Run one bounded canonical encounter and return a deterministic proof."""
    if descender_count < 1:
        raise ValueError("descender_count must be positive")

    environment = build_stratum_environment_manifest(seed, 0, sector_count=sector_count, theme=theme)
    themed = build_stratum_theme_manifest(environment, theme)
    plan = build_encounter_plan(environment, themed)
    source_encounter = sorted(plan["encounters"], key=lambda item: item["encounter_id"])[0]
    source_sector = next(item for item in environment["sectors"] if item["sector_id"] == source_encounter["sector_id"])

    persistence = CrawlPersistence("sqlite:///:memory:")
    persistence.initialize()
    lifecycle = CrawlLifecycleService(persistence)
    descender_ids = [f"descender_{index:03d}" for index in range(descender_count)]
    crawl = lifecycle.create_seeded_crawl(seed=seed, crawler_ids=descender_ids, floor_count=1)
    lifecycle.start(crawl)

    # Keep this slice's proof focused on encounter integration rather than retreat
    # personality variance. Combat rolls remain deterministic and canonical.
    for participant in crawl.participants.values():
        participant.health = 1.0
        participant.gameplay.stamina = 1.0
        if participant.agent is not None:
            participant.agent.traits.courage = 1.0
            participant.agent.traits.aggression = 1.0
            participant.agent.traits.caution = 0.0

    encounter = promote_encounter(crawl, plan, source_encounter, participant_npc_ids=descender_ids)
    lifecycle._record(
        crawl,
        "UNDERREACH_ENCOUNTER_PROMOTED",
        f"Underreach encounter {source_encounter['encounter_id']} entered canonical simulation.",
        actor_ids=descender_ids + sorted(encounter.enemies),
        location_id=encounter.location_id,
        data={
            "canonical_encounter_id": encounter.id,
            "encounter_id": encounter.id,
            "source_plan_digest": plan["digest"],
            "source_sector_id": source_encounter["sector_id"],
            "source_encounter_id": source_encounter["encounter_id"],
            "state_changes": {"encounter_status": encounter.status.value},
        },
    )
    lifecycle._save(crawl)
    encounter_before = encounter.model_dump(mode="json")
    resolution = resolve_combat(crawl, encounter, lifecycle)
    lifecycle._save(crawl)

    events = persistence.replay_events(crawl.id)
    encounter_events = _events_for_encounter(events, encounter.id)
    ledger_events = [event.model_dump(mode="json") for event in encounter_events]
    participant_final = {
        npc_id: {
            "status": crawl.participants[npc_id].status.value,
            "health": crawl.participants[npc_id].health,
            "stamina": crawl.participants[npc_id].gameplay.stamina,
        }
        for npc_id in sorted(descender_ids)
    }
    enemy_final = {
        enemy_id: {
            "alive": enemy.alive,
            "health": enemy.health,
            "max_health": enemy.max_health,
            "monster_id": next(
                member["monster_id"] for member in source_encounter["members"] if member["member_id"] == enemy_id
            ),
        }
        for enemy_id, enemy in sorted(encounter.enemies.items())
    }

    canonical_truth = {
        "source_environment_digest": environment["digest"],
        "source_theme_digest": themed["digest"],
        "source_encounter_plan_digest": plan["digest"],
        "source_sector": {
            "sector_id": source_sector["sector_id"],
            "world_origin_cm": dict(source_sector["world_origin_cm"]),
            "combat_clearance_cm": dict(source_sector["combat_clearance_cm"]),
        },
        "source_encounter": source_encounter,
        "canonical_encounter_before": encounter_before,
        "canonical_encounter_after": encounter.model_dump(mode="json"),
        "resolution": asdict(resolution),
        "participant_final": participant_final,
        "enemy_final": enemy_final,
        "ledger_events": ledger_events,
        "crawl_fingerprint": crawl.fingerprint(),
    }
    canonical_digest = _digest(canonical_truth)
    truth_for_validation = dict(canonical_truth)
    truth_for_validation["canonical_digest"] = canonical_digest
    presentation = _presentation_from_truth(
        canonical_digest=canonical_digest,
        source_sector=source_sector,
        source_encounter=source_encounter,
        resolution=resolution,
        participant_final=participant_final,
        enemy_final=enemy_final,
        ledger_events=ledger_events,
    )
    validate_presentation_against_truth(presentation, truth_for_validation)

    proof = {
        "protocol": CANONICAL_PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": True,
        "seed": seed,
        "canonical_digest": canonical_digest,
        "canonical_truth": canonical_truth,
        "presentation": presentation,
    }
    proof["digest"] = _digest(proof)
    return proof


def validate_live_encounter_proof(proof: dict[str, Any]) -> bool:
    if proof.get("protocol") != CANONICAL_PROTOCOL or proof.get("authoritative") is not True:
        raise ValueError("29C.2 proof must describe canonical simulation truth")
    truth = proof.get("canonical_truth") or {}
    if proof.get("canonical_digest") != _digest(truth):
        raise ValueError("canonical combat truth digest mismatch")
    truth_for_validation = dict(truth)
    truth_for_validation["canonical_digest"] = proof["canonical_digest"]
    validate_presentation_against_truth(proof.get("presentation") or {}, truth_for_validation)

    events = truth.get("ledger_events") or []
    types = [event.get("event_type") for event in events]
    if "UNDERREACH_ENCOUNTER_PROMOTED" not in types or "COMBAT_STARTED" not in types or "COMBAT_ENDED" not in types:
        raise ValueError("canonical Ledger is missing required encounter lifecycle events")
    if len({event["id"] for event in events}) != len(events):
        raise ValueError("duplicate canonical Ledger event ids")

    resolution = truth["resolution"]
    defeated_from_state = sorted(enemy_id for enemy_id, state in truth["enemy_final"].items() if not state["alive"])
    if sorted(resolution["defeated_enemy_ids"]) != defeated_from_state:
        raise ValueError("resolution defeated monsters disagree with canonical final state")
    dead_from_state = sorted(npc_id for npc_id, state in truth["participant_final"].items() if state["status"] == "dead")
    if sorted(resolution["crawler_deaths"]) != dead_from_state:
        raise ValueError("resolution dead Descenders disagree with canonical final state")
    if proof.get("digest") != rebuild_digest(proof):
        raise ValueError("29C.2 proof digest mismatch")
    return True
