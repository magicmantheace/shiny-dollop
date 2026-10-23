import json

import pytest

from livingworld.stratum_environment import build_stratum_environment_manifest
from livingworld.stratum_multisector import (
    MULTISECTOR_PROTOCOL,
    build_multisector_presentation_plan,
    rebuild_digest,
    shortest_sector_route,
    validate_multisector_presentation_plan,
)


def _manifest(seed="29b2-proof", sectors=12):
    return build_stratum_environment_manifest(seed, 0, sector_count=sectors)


def test_same_manifest_produces_identical_plan_and_digest():
    manifest = _manifest()
    first = build_multisector_presentation_plan(manifest)
    second = build_multisector_presentation_plan(manifest)
    assert first == second
    assert first["digest"] == rebuild_digest(first)


def test_plan_is_presentation_only_and_bound_to_stratum_digest():
    manifest = _manifest()
    plan = build_multisector_presentation_plan(manifest)
    assert plan["protocol"] == MULTISECTOR_PROTOCOL
    assert plan["authoritative"] is False
    assert plan["stratum_environment_digest"] == manifest["digest"]


def test_rooms_cover_all_sectors_without_reordering():
    manifest = _manifest(sectors=20)
    plan = build_multisector_presentation_plan(manifest)
    assert [room["sector_id"] for room in plan["rooms"]] == [sector["sector_id"] for sector in manifest["sectors"]]


def test_corridors_cover_every_manifest_connection_exactly_once():
    manifest = _manifest(sectors=18)
    plan = build_multisector_presentation_plan(manifest)
    actual = {frozenset((item["sector_a"], item["sector_b"])) for item in plan["corridors"]}
    expected = {frozenset((edge["a"], edge["b"])) for edge in manifest["connections"]}
    assert actual == expected
    assert len(actual) == len(plan["corridors"])


def test_portals_are_opposed_and_corridors_are_positive_size():
    plan = build_multisector_presentation_plan(_manifest(sectors=24))
    opposites = {("east", "west"), ("west", "east"), ("north", "south"), ("south", "north")}
    for corridor in plan["corridors"]:
        assert (corridor["portal_a"]["side"], corridor["portal_b"]["side"]) in opposites
        assert corridor["length_cm"] > 0
        assert corridor["width_cm"] >= corridor["portal_a"]["width_cm"]


def test_proof_route_runs_from_entry_to_exit_through_valid_edges():
    manifest = _manifest(sectors=30)
    route = shortest_sector_route(manifest)
    assert route[0] == manifest["entry_sector_id"]
    assert route[-1] == manifest["exit_sector_id"]
    edges = {frozenset((edge["a"], edge["b"])) for edge in manifest["connections"]}
    assert all(frozenset((left, right)) in edges for left, right in zip(route, route[1:]))


def test_timeline_has_sector_hold_and_transition_for_every_route_hop():
    manifest = _manifest(sectors=15)
    plan = build_multisector_presentation_plan(manifest)
    route = plan["proof_route_sector_ids"]
    holds = [item for item in plan["timeline"] if item["kind"] == "sector_hold"]
    transitions = [item for item in plan["timeline"] if item["kind"] == "sector_transition"]
    assert len(holds) == len(route)
    assert len(transitions) == len(route) - 1
    assert holds[0]["sector_id"] == manifest["entry_sector_id"]
    assert holds[-1]["sector_id"] == manifest["exit_sector_id"]


def test_timeline_is_contiguous_without_empty_handoff_windows():
    plan = build_multisector_presentation_plan(_manifest(sectors=22))
    assert plan["timeline"][0]["start_seconds"] == 0.0
    previous_end = 0.0
    for item in plan["timeline"]:
        assert item["start_seconds"] == previous_end
        assert item["end_seconds"] > item["start_seconds"]
        previous_end = item["end_seconds"]
    assert previous_end == plan["duration_seconds"]


def test_json_checkpoint_round_trip_preserves_plan_identity():
    manifest = _manifest(seed="checkpoint", sectors=25)
    plan = build_multisector_presentation_plan(manifest)
    restored = json.loads(json.dumps(plan))
    assert restored == plan
    assert rebuild_digest(restored) == plan["digest"]


def test_validation_rejects_wrong_stratum_digest():
    manifest = _manifest()
    plan = build_multisector_presentation_plan(manifest)
    plan["stratum_environment_digest"] = "wrong"
    with pytest.raises(ValueError, match="digest"):
        validate_multisector_presentation_plan(plan, manifest)


def test_validation_rejects_missing_corridor():
    manifest = _manifest(sectors=12)
    plan = build_multisector_presentation_plan(manifest)
    plan["corridors"] = plan["corridors"][:-1]
    with pytest.raises(ValueError, match="corridors"):
        validate_multisector_presentation_plan(plan, manifest)


def test_large_plan_is_deterministic_and_valid():
    manifest = _manifest(seed="stress", sectors=250)
    first = build_multisector_presentation_plan(manifest)
    second = build_multisector_presentation_plan(manifest)
    assert first["digest"] == second["digest"]
    assert validate_multisector_presentation_plan(first, manifest)
