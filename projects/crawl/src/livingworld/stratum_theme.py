"""Deterministic, presentation-only Stratum theming for Underreach 29B.3.

Theme selection consumes an accepted Stratum environment manifest and assigns
visual materials/props per Sector without changing topology, traversal, or
canonical simulation state.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

THEME_PROTOCOL = "underreach.stratum-theme.v1"
GENERATOR_VERSION = "29b3.1"

THEMES: dict[str, dict[str, Any]] = {
    "ancient_stoneworks": {
        "materials": {
            "floor": ["stone_floor_worn", "stone_floor_block", "stone_floor_dusty"],
            "wall": ["stone_wall_cut", "stone_wall_cracked", "stone_wall_mossed"],
            "ceiling": ["stone_ceiling_arch", "stone_ceiling_rough"],
            "trim": ["iron_trim_dark", "bronze_trim_aged"],
        },
        "props": ["broken_pillar", "rubble_small", "iron_brazier", "chain_cluster", "stone_urn"],
        "lighting": ["warm_brazier", "cold_ambient", "amber_sconce"],
    },
    "flooded_catacombs": {
        "materials": {
            "floor": ["wet_stone", "shallow_water_stone", "silted_tile"],
            "wall": ["damp_block", "mineral_streak_wall", "rooted_stone"],
            "ceiling": ["dripping_vault", "rooted_ceiling"],
            "trim": ["verdigris_metal", "dark_iron_wet"],
        },
        "props": ["water_pool", "broken_grate", "root_cluster", "driftwood", "moss_stone"],
        "lighting": ["blue_reflection", "green_mineral_glow", "dim_sconce"],
    },
    "ember_foundry": {
        "materials": {
            "floor": ["black_iron_plate", "slag_stone", "scorched_brick"],
            "wall": ["soot_brick", "iron_ribbed_wall", "heat_cracked_stone"],
            "ceiling": ["iron_beam_ceiling", "soot_vault"],
            "trim": ["hot_iron_trim", "blackened_bronze"],
        },
        "props": ["slag_heap", "pipe_cluster", "anvil_ruin", "coal_cart", "vent_stack"],
        "lighting": ["ember_glow", "hot_vent", "orange_worklight"],
    },
}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _choice(seed: str, category: str, options: list[str]) -> str:
    token = hashlib.sha256(f"{seed}:{category}".encode("utf-8")).hexdigest()
    return options[int(token[:16], 16) % len(options)]


def _prop_choices(seed: str, options: list[str], count: int = 3) -> list[str]:
    ranked = sorted(options, key=lambda item: hashlib.sha256(f"{seed}:prop:{item}".encode("utf-8")).hexdigest())
    return ranked[: min(count, len(ranked))]


def build_stratum_theme_manifest(environment: dict, theme: str | None = None) -> dict:
    """Build stable visual assignments while preserving environment identity."""
    selected_theme = theme or str(environment.get("theme") or "ancient_stoneworks")
    if selected_theme not in THEMES:
        raise ValueError(f"unknown Underreach Stratum theme: {selected_theme}")
    spec = THEMES[selected_theme]

    sectors = []
    for sector in environment["sectors"]:
        seed = str(sector["presentation_room_seed"])
        materials = {
            surface: _choice(seed, surface, list(options))
            for surface, options in spec["materials"].items()
        }
        sectors.append({
            "sector_id": sector["sector_id"],
            "role": sector["role"],
            "presentation_room_seed": seed,
            "world_origin_cm": dict(sector["world_origin_cm"]),
            "materials": materials,
            "props": _prop_choices(seed, list(spec["props"])),
            "lighting": _choice(seed, "lighting", list(spec["lighting"])),
        })

    manifest = {
        "protocol": THEME_PROTOCOL,
        "generator_version": GENERATOR_VERSION,
        "authoritative": False,
        "theme": selected_theme,
        "stratum_environment_digest": environment["digest"],
        "stratum_index": environment["stratum_index"],
        "entry_sector_id": environment["entry_sector_id"],
        "exit_sector_id": environment["exit_sector_id"],
        "refuge_sector_id": environment.get("refuge_sector_id"),
        "topology_fingerprint": {
            "sector_ids": [sector["sector_id"] for sector in environment["sectors"]],
            "connections": [dict(edge) for edge in environment["connections"]],
            "world_origins_cm": [dict(sector["world_origin_cm"]) for sector in environment["sectors"]],
        },
        "sectors": sectors,
    }
    validate_stratum_theme_manifest(manifest, environment)
    manifest["digest"] = _digest(manifest)
    return manifest


def validate_stratum_theme_manifest(manifest: dict, environment: dict) -> bool:
    if manifest.get("protocol") != THEME_PROTOCOL or manifest.get("authoritative") is not False:
        raise ValueError("29B.3 theme manifest must be presentation-only")
    if manifest.get("theme") not in THEMES:
        raise ValueError("theme manifest references unknown theme")
    if manifest.get("stratum_environment_digest") != environment.get("digest"):
        raise ValueError("theme manifest does not bind to supplied Stratum environment")
    if manifest.get("entry_sector_id") != environment.get("entry_sector_id"):
        raise ValueError("theme changed Entry Sector")
    if manifest.get("exit_sector_id") != environment.get("exit_sector_id"):
        raise ValueError("theme changed Exit Sector")
    if manifest.get("refuge_sector_id") != environment.get("refuge_sector_id"):
        raise ValueError("theme changed Refuge Sector")

    expected_ids = [sector["sector_id"] for sector in environment["sectors"]]
    actual_ids = [sector["sector_id"] for sector in manifest.get("sectors", [])]
    if actual_ids != expected_ids:
        raise ValueError("theme Sector coverage/order differs from environment")

    fingerprint = manifest.get("topology_fingerprint") or {}
    if fingerprint.get("sector_ids") != expected_ids:
        raise ValueError("theme topology fingerprint changed Sector ids")
    if fingerprint.get("connections") != environment.get("connections"):
        raise ValueError("theme topology fingerprint changed connections")
    expected_origins = [sector["world_origin_cm"] for sector in environment["sectors"]]
    if fingerprint.get("world_origins_cm") != expected_origins:
        raise ValueError("theme topology fingerprint changed world origins")

    spec = THEMES[manifest["theme"]]
    by_id = {sector["sector_id"]: sector for sector in environment["sectors"]}
    for themed in manifest["sectors"]:
        source = by_id[themed["sector_id"]]
        if themed.get("presentation_room_seed") != source.get("presentation_room_seed"):
            raise ValueError("theme changed presentation room seed")
        if themed.get("world_origin_cm") != source.get("world_origin_cm"):
            raise ValueError("theme changed Sector origin")
        if themed.get("role") != source.get("role"):
            raise ValueError("theme changed Sector role")
        for surface, choice in themed.get("materials", {}).items():
            if surface not in spec["materials"] or choice not in spec["materials"][surface]:
                raise ValueError("theme material assignment is outside theme palette")
        if set(themed.get("props", [])) - set(spec["props"]):
            raise ValueError("theme prop assignment is outside theme palette")
        if themed.get("lighting") not in spec["lighting"]:
            raise ValueError("theme lighting assignment is outside theme palette")
    return True


def rebuild_digest(manifest: dict) -> str:
    payload = dict(manifest)
    payload.pop("digest", None)
    return _digest(payload)
