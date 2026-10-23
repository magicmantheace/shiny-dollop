import copy
import json

import pytest

from livingworld.stratum_environment import build_stratum_environment_manifest
from livingworld.stratum_theme import (
    THEMES,
    THEME_PROTOCOL,
    build_stratum_theme_manifest,
    rebuild_digest,
    validate_stratum_theme_manifest,
)


def _environment():
    return build_stratum_environment_manifest("underreach-29b3-theme-tests", stratum_index=3, sector_count=12)


def test_same_environment_and_theme_are_identical():
    env = _environment()
    first = build_stratum_theme_manifest(env, "ancient_stoneworks")
    second = build_stratum_theme_manifest(env, "ancient_stoneworks")
    assert first == second
    assert first["digest"] == second["digest"]


def test_theme_protocol_is_presentation_only():
    themed = build_stratum_theme_manifest(_environment())
    assert themed["protocol"] == THEME_PROTOCOL
    assert themed["authoritative"] is False


def test_theme_change_changes_visual_digest_not_topology():
    env = _environment()
    stone = build_stratum_theme_manifest(env, "ancient_stoneworks")
    flooded = build_stratum_theme_manifest(env, "flooded_catacombs")
    assert stone["digest"] != flooded["digest"]
    assert stone["topology_fingerprint"] == flooded["topology_fingerprint"]
    assert stone["entry_sector_id"] == flooded["entry_sector_id"] == env["entry_sector_id"]
    assert stone["exit_sector_id"] == flooded["exit_sector_id"] == env["exit_sector_id"]
    assert stone["refuge_sector_id"] == flooded["refuge_sector_id"] == env["refuge_sector_id"]


def test_all_registered_themes_validate():
    env = _environment()
    for theme in THEMES:
        validate_stratum_theme_manifest(build_stratum_theme_manifest(env, theme), env)


def test_sector_visual_assignments_are_stable_and_complete():
    env = _environment()
    themed = build_stratum_theme_manifest(env, "ember_foundry")
    assert [item["sector_id"] for item in themed["sectors"]] == [item["sector_id"] for item in env["sectors"]]
    for item in themed["sectors"]:
        assert set(item["materials"]) == {"floor", "wall", "ceiling", "trim"}
        assert len(item["props"]) == 3
        assert item["lighting"]


def test_json_round_trip_preserves_digest():
    env = _environment()
    themed = build_stratum_theme_manifest(env, "flooded_catacombs")
    restored = json.loads(json.dumps(themed))
    assert rebuild_digest(restored) == themed["digest"]
    assert validate_stratum_theme_manifest(restored, env)


def test_unknown_theme_is_rejected():
    with pytest.raises(ValueError):
        build_stratum_theme_manifest(_environment(), "not_a_theme")


def test_authoritative_theme_manifest_is_rejected():
    env = _environment()
    themed = build_stratum_theme_manifest(env)
    themed["authoritative"] = True
    with pytest.raises(ValueError):
        validate_stratum_theme_manifest(themed, env)


def test_changed_environment_digest_is_rejected():
    env = _environment()
    themed = build_stratum_theme_manifest(env)
    themed["stratum_environment_digest"] = "wrong"
    with pytest.raises(ValueError):
        validate_stratum_theme_manifest(themed, env)


def test_theme_cannot_move_a_sector():
    env = _environment()
    themed = build_stratum_theme_manifest(env)
    broken = copy.deepcopy(themed)
    broken["sectors"][0]["world_origin_cm"]["x"] += 1.0
    with pytest.raises(ValueError):
        validate_stratum_theme_manifest(broken, env)


def test_theme_cannot_change_connections():
    env = _environment()
    themed = build_stratum_theme_manifest(env)
    broken = copy.deepcopy(themed)
    broken["topology_fingerprint"]["connections"] = broken["topology_fingerprint"]["connections"][:-1]
    with pytest.raises(ValueError):
        validate_stratum_theme_manifest(broken, env)


def test_theme_cannot_use_asset_outside_palette():
    env = _environment()
    themed = build_stratum_theme_manifest(env)
    broken = copy.deepcopy(themed)
    broken["sectors"][0]["materials"]["floor"] = "alien_floor"
    with pytest.raises(ValueError):
        validate_stratum_theme_manifest(broken, env)
