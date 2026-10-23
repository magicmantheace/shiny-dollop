"""Deterministic monster definitions and presentation encounter plans for Underreach 29C.1.

This slice deliberately stops short of canonical combat execution.  The generated
encounter plan is presentation/content scaffolding bound to a deterministic
Stratum environment.  Future simulation integration must explicitly promote
validated encounter intents into authoritative simulation state and Ledger events.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

MONSTER_PROTOCOL = "underreach.monster-definition.v1"
ENCOUNTER_PROTOCOL = "underreach.encounter-plan.v1"
GENERATOR_VERSION = "29c1.1"

MONSTER_DEFINITIONS: dict[str, dict[str, Any]] = {
    "stone_maw": {
        "protocol": MONSTER_PROTOCOL,
        "display_name": "Stone Maw",
        "family": "burrower",
        "threat": 2,
        "preferred_themes": ["ancient_stoneworks", "flooded_catacombs"],
        "proxy_shape": "cube",
        "proxy_size_cm": {"x": 145.0, "y": 110.0, "z": 95.0},
        "presentation_tags": ["low", "heavy", "ambush"],
    },
    "vault_stalker": {
        "protocol": MONSTER_PROTOCOL,
        "display_name": "Vault Stalker",
        "family": "stalker",
        "threat": 3,
        "preferred_themes": ["ancient_stoneworks", "flooded_catacombs"],
        "proxy_shape": "cube",
        "proxy_size_cm": {"x": 85.0, "y": 85.0, "z": 205.0},
        "presentation_tags": ["tall", "fast", "hunter"],
    },
    "drowned_thrall": {
        "protocol": MONSTER_PROTOCOL,
        "display_name": "Drowned Thrall",
        "family": "thrall",
        "threat": 1,
        "preferred_themes": ["flooded_catacombs"],
        "proxy_shape": "cube",
        "proxy_size_cm": {"x": 75.0, "y": 75.0, "z": 185.0},
        "presentation_tags": ["humanoid", "slow", "swarm"],
    },
    "ember_hound": {
        "protocol": MONSTER_PROTOCOL,
        "display_name": "Ember Hound",
        "family": "hound",
        "threat": 2,
        "preferred_themes": ["ember_foundry"],
        "proxy_shape": "cube",
        "proxy_size_cm": {"x": 125.0, "y": 65.0, "z": 90.0},
        "presentation_tags": ["low", "fast", "pack"],
    },
    "forge_brute": {
        "protocol": MONSTER_PROTOCOL,
        "display_name": "Forge Brute",
        "family": "construct",
        "threat": 4,
        "preferred_themes": ["ember_foundry", "ancient_stoneworks"],
        "proxy_shape": "cube",
        "proxy_size_cm": {"x": 135.0, "y": 105.0, "z": 245.0},
        "presentation_tags": ["large", "heavy", "elite"],
    },
}

SAFE_SECTOR_ROLES = {"entry", "refuge"}
ELIGIBLE_SECTOR_ROLES = {"combat", "transit", "exit"}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _rank(seed: str, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def _theme_candidates(theme: str) -> list[str]:
    preferred = [
        monster_id
        for monster_id, definition in MONSTER_DEFINITIONS.items()
        if theme in definition["preferred_themes"]
    ]
    return preferred or sorted(MONSTER_DEFINITIONS)


def _choose_monster(seed: str, theme: str, slot: int) -> str:
    candidates = _theme_candidates(theme)
    return min(candidates, key=lambda monster_id: _rank(seed, f"monster:{slot}:{monster_id}"))


def _encounter_count(seed: str, role: str) -> int:
    if role == "exit":
        return 1
    token = int(_rank(seed, "encounter-count")[:8], 16)
    return 1 + (token % 2)


def _spawn_offsets(seed: str, count: int, clearance: dict[str, Any]) -> list[dict[str, float]]:
    half_x = max(120.0, float(clearance["x"]) * 0.5 - 180.0)
    half_y = max(120.0, float(clearance["y"]) * 0.5 - 180.0)
    anchors = [
        (-0.52, -0.28),
        (0.48, 0.32),
        (-0.12, 0.52),
        (0.18, -0.55),
    ]
    rotation = int(_rank(seed, "offset-rotation")[:8], 16) % len(anchors)
    ordered = anchors[rotation:] + anchors[:rotation]
    return [
        {"x": round(ordered[index][0] * half_x, 3), "y": round(ordered[index][1] * half_y, 3), "z": 0.0}
        for index in range(count)
    ]


def build_encounter_plan(environment: dict[str, Any], theme_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build deterministic non-authoritative encounter content for one Stratum."""
    theme_by_sector = {}
    if theme_manifest is not None:
        if theme_manifest.get("stratum_environment_digest") != environment.get("digest"):
            raise ValueError("encounter theme manifest does not bind to supplied Stratum")
        theme_by_sector = {sector["sector_id"]: theme_manifest["theme"] for sector in theme_manifest["sectors"]}

    encounters: list[dict[str, Any]] = []
    for sector in environment["sectors"]:
        role = str(sector["role"])
        if role in SAFE_SECTOR_ROLES or role not in ELIGIBLE_SECTOR_ROLES:
            continue
        sector_id = str(sector["sector_id"])
        seed = str(sector["presentation_room_seed"])
        theme = theme_by_sector.get(sector_id, str(environment.get("theme") or "ancient_stoneworks"))
        count = _encounter_count(seed, role)
        offsets = _spawn_offsets(seed, count, sector["combat_clearance_cm"])
        members = []
        for index in range(count):
            monster_id = _choose_monster(seed, theme, index)
            members.append({
                "member_id": f"{sector_id}_monster_{index:02d}",
                "monster_id": monster_id,
                "local_offset_cm": offsets[index],
                "threat": MONSTER_DEFINITIONS[monster_id]["threat"],
            })
        encounters.append({
            "encounter_id": f"encounter_{sector_id}",
            "sector_id": sector_id,
            "sector_role": role,
            "theme": theme,
            "members": members,
            "total_threat": sum(member["threat"] for member in members),
        })

    plan = {
        "protocol": ENCOUNTER_PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "promotion_required_for_canonical_combat": True,
        "stratum_environment_digest": environment["digest"],
        "stratum_index": environment["stratum_index"],
        "entry_sector_id": environment["entry_sector_id"],
        "exit_sector_id": environment["exit_sector_id"],
        "refuge_sector_id": environment.get("refuge_sector_id"),
        "topology_fingerprint": {
            "sector_ids": [sector["sector_id"] for sector in environment["sectors"]],
            "connections": [dict(connection) for connection in environment["connections"]],
            "world_origins_cm": [dict(sector["world_origin_cm"]) for sector in environment["sectors"]],
        },
        "monster_definition_digest": _digest(MONSTER_DEFINITIONS),
        "encounters": encounters,
    }
    validate_encounter_plan(plan, environment)
    plan["digest"] = _digest(plan)
    return plan


def validate_encounter_plan(plan: dict[str, Any], environment: dict[str, Any]) -> bool:
    if plan.get("protocol") != ENCOUNTER_PROTOCOL:
        raise ValueError("unexpected encounter protocol")
    if plan.get("authoritative") is not False or plan.get("promotion_required_for_canonical_combat") is not True:
        raise ValueError("29C.1 encounter plan must remain non-authoritative")
    if plan.get("stratum_environment_digest") != environment.get("digest"):
        raise ValueError("encounter plan does not bind to supplied Stratum")
    if plan.get("entry_sector_id") != environment.get("entry_sector_id") or plan.get("exit_sector_id") != environment.get("exit_sector_id"):
        raise ValueError("encounter plan changed Entry/Exit")
    if plan.get("refuge_sector_id") != environment.get("refuge_sector_id"):
        raise ValueError("encounter plan changed Refuge")

    fingerprint = plan.get("topology_fingerprint") or {}
    if fingerprint.get("sector_ids") != [sector["sector_id"] for sector in environment["sectors"]]:
        raise ValueError("encounter plan changed Sector identity/order")
    if fingerprint.get("connections") != environment.get("connections"):
        raise ValueError("encounter plan changed topology")
    if fingerprint.get("world_origins_cm") != [sector["world_origin_cm"] for sector in environment["sectors"]]:
        raise ValueError("encounter plan changed Sector origins")

    by_id = {sector["sector_id"]: sector for sector in environment["sectors"]}
    seen_sector_ids: set[str] = set()
    seen_member_ids: set[str] = set()
    for encounter in plan.get("encounters", []):
        sector_id = encounter.get("sector_id")
        if sector_id not in by_id or sector_id in seen_sector_ids:
            raise ValueError("invalid or duplicate encounter Sector")
        seen_sector_ids.add(sector_id)
        source = by_id[sector_id]
        if source["role"] in SAFE_SECTOR_ROLES:
            raise ValueError("safe Sector received monster encounter")
        if encounter.get("sector_role") != source["role"]:
            raise ValueError("encounter changed Sector role")
        if not encounter.get("members"):
            raise ValueError("encounter contains no monsters")
        clearance = source["combat_clearance_cm"]
        max_x = float(clearance["x"]) * 0.5
        max_y = float(clearance["y"]) * 0.5
        computed_threat = 0
        for member in encounter["members"]:
            member_id = member.get("member_id")
            monster_id = member.get("monster_id")
            if member_id in seen_member_ids:
                raise ValueError("duplicate monster member id")
            seen_member_ids.add(member_id)
            if monster_id not in MONSTER_DEFINITIONS:
                raise ValueError("encounter references unknown monster")
            offset = member.get("local_offset_cm") or {}
            if abs(float(offset.get("x", 0.0))) > max_x or abs(float(offset.get("y", 0.0))) > max_y:
                raise ValueError("monster spawn falls outside combat clearance")
            if float(offset.get("z", 0.0)) != 0.0:
                raise ValueError("29C.1 proxy monsters must spawn on Sector floor")
            expected_threat = MONSTER_DEFINITIONS[monster_id]["threat"]
            if member.get("threat") != expected_threat:
                raise ValueError("monster threat differs from definition")
            computed_threat += expected_threat
        if encounter.get("total_threat") != computed_threat:
            raise ValueError("encounter total threat is inconsistent")
    return True


def rebuild_digest(plan: dict[str, Any]) -> str:
    payload = dict(plan)
    payload.pop("digest", None)
    return _digest(payload)
