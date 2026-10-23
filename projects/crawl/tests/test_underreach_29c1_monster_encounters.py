import copy
import json

import pytest

from livingworld.monster_encounters import (
    ENCOUNTER_PROTOCOL,
    MONSTER_DEFINITIONS,
    build_encounter_plan,
    rebuild_digest,
    validate_encounter_plan,
)
from livingworld.stratum_environment import build_stratum_environment_manifest
from livingworld.stratum_theme import build_stratum_theme_manifest


def _fixture(theme="ancient_stoneworks", sectors=12):
    environment = build_stratum_environment_manifest("underreach-29c1-tests", 0, sector_count=sectors, theme=theme)
    themed = build_stratum_theme_manifest(environment, theme)
    return environment, themed


def test_same_inputs_reproduce_exact_plan_and_digest():
    environment, themed = _fixture()
    first = build_encounter_plan(environment, themed)
    second = build_encounter_plan(environment, themed)
    assert first == second
    assert first["digest"] == rebuild_digest(first)


def test_protocol_and_non_authoritative_boundary_are_explicit():
    environment, themed = _fixture()
    plan = build_encounter_plan(environment, themed)
    assert plan["protocol"] == ENCOUNTER_PROTOCOL
    assert plan["authoritative"] is False
    assert plan["promotion_required_for_canonical_combat"] is True


def test_entry_and_refuge_never_receive_encounters():
    environment, themed = _fixture()
    plan = build_encounter_plan(environment, themed)
    encountered = {item["sector_id"] for item in plan["encounters"]}
    assert environment["entry_sector_id"] not in encountered
    if environment["refuge_sector_id"]:
        assert environment["refuge_sector_id"] not in encountered


def test_all_members_reference_known_definitions_and_unique_ids():
    environment, themed = _fixture()
    plan = build_encounter_plan(environment, themed)
    member_ids = []
    for encounter in plan["encounters"]:
        for member in encounter["members"]:
            assert member["monster_id"] in MONSTER_DEFINITIONS
            member_ids.append(member["member_id"])
    assert len(member_ids) == len(set(member_ids))


def test_spawn_offsets_stay_inside_combat_clearance():
    environment, themed = _fixture()
    plan = build_encounter_plan(environment, themed)
    by_id = {sector["sector_id"]: sector for sector in environment["sectors"]}
    for encounter in plan["encounters"]:
        clearance = by_id[encounter["sector_id"]]["combat_clearance_cm"]
        max_x = clearance["x"] / 2
        max_y = clearance["y"] / 2
        for member in encounter["members"]:
            assert abs(member["local_offset_cm"]["x"]) <= max_x
            assert abs(member["local_offset_cm"]["y"]) <= max_y
            assert member["local_offset_cm"]["z"] == 0.0


def test_theme_selection_changes_content_not_topology():
    environment = build_stratum_environment_manifest("underreach-29c1-theme-proof", 0, sector_count=12)
    stone = build_encounter_plan(environment, build_stratum_theme_manifest(environment, "ancient_stoneworks"))
    flooded = build_encounter_plan(environment, build_stratum_theme_manifest(environment, "flooded_catacombs"))
    ember = build_encounter_plan(environment, build_stratum_theme_manifest(environment, "ember_foundry"))
    assert stone["topology_fingerprint"] == flooded["topology_fingerprint"] == ember["topology_fingerprint"]
    assert len({stone["digest"], flooded["digest"], ember["digest"]}) == 3


def test_theme_preference_is_respected_for_every_member():
    for theme in ("ancient_stoneworks", "flooded_catacombs", "ember_foundry"):
        environment, themed = _fixture(theme)
        plan = build_encounter_plan(environment, themed)
        for encounter in plan["encounters"]:
            for member in encounter["members"]:
                assert theme in MONSTER_DEFINITIONS[member["monster_id"]]["preferred_themes"]


def test_json_round_trip_preserves_digest():
    environment, themed = _fixture()
    plan = build_encounter_plan(environment, themed)
    restored = json.loads(json.dumps(plan))
    assert restored["digest"] == rebuild_digest(restored)
    assert validate_encounter_plan(restored, environment)


def test_wrong_stratum_binding_is_rejected():
    environment, themed = _fixture()
    plan = build_encounter_plan(environment, themed)
    damaged = copy.deepcopy(plan)
    damaged["stratum_environment_digest"] = "wrong"
    with pytest.raises(ValueError):
        validate_encounter_plan(damaged, environment)


def test_safe_sector_injection_is_rejected():
    environment, themed = _fixture()
    plan = build_encounter_plan(environment, themed)
    damaged = copy.deepcopy(plan)
    entry = next(item for item in environment["sectors"] if item["sector_id"] == environment["entry_sector_id"])
    source_member = copy.deepcopy(damaged["encounters"][0]["members"][0])
    source_member["member_id"] = "illegal_entry_monster"
    damaged["encounters"].append({
        "encounter_id": "illegal",
        "sector_id": entry["sector_id"],
        "sector_role": entry["role"],
        "theme": themed["theme"],
        "members": [source_member],
        "total_threat": source_member["threat"],
    })
    with pytest.raises(ValueError):
        validate_encounter_plan(damaged, environment)


def test_unknown_monster_is_rejected():
    environment, themed = _fixture()
    plan = build_encounter_plan(environment, themed)
    damaged = copy.deepcopy(plan)
    damaged["encounters"][0]["members"][0]["monster_id"] = "not_real"
    with pytest.raises(ValueError):
        validate_encounter_plan(damaged, environment)


def test_250_sector_stress_plan_is_deterministic_and_valid():
    environment = build_stratum_environment_manifest("underreach-29c1-stress", 3, sector_count=250, theme="ember_foundry")
    themed = build_stratum_theme_manifest(environment, "ember_foundry")
    first = build_encounter_plan(environment, themed)
    second = build_encounter_plan(environment, themed)
    assert first == second
    assert validate_encounter_plan(first, environment)
    assert len(first["encounters"]) > 0
