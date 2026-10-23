import json

import pytest

from livingworld.stratum_environment import (
    STRATUM_ENVIRONMENT_PROTOCOL,
    build_stratum_environment_manifest,
    rebuild_digest,
    validate_stratum_environment_manifest,
)


def test_same_seed_is_identical():
    first = build_stratum_environment_manifest("descent-proof", 0)
    second = build_stratum_environment_manifest("descent-proof", 0)
    assert first == second
    assert first["digest"] == rebuild_digest(first)


def test_different_seed_changes_layout_digest():
    first = build_stratum_environment_manifest("descent-a", 0)
    second = build_stratum_environment_manifest("descent-b", 0)
    assert first["digest"] != second["digest"]
    assert [(s["grid"]["x"], s["grid"]["y"]) for s in first["sectors"]] != [(s["grid"]["x"], s["grid"]["y"]) for s in second["sectors"]]


def test_manifest_is_non_authoritative_underreach_protocol():
    manifest = build_stratum_environment_manifest("authority", 2)
    assert manifest["protocol"] == STRATUM_ENVIRONMENT_PROTOCOL
    assert manifest["authoritative"] is False
    assert manifest["stratum_index"] == 2


def test_all_sectors_have_unique_cells_and_ids():
    manifest = build_stratum_environment_manifest("unique", sector_count=24)
    ids = [sector["sector_id"] for sector in manifest["sectors"]]
    cells = [(sector["grid"]["x"], sector["grid"]["y"]) for sector in manifest["sectors"]]
    assert len(ids) == len(set(ids)) == 24
    assert len(cells) == len(set(cells)) == 24


def test_all_sectors_are_reachable_from_entry():
    manifest = build_stratum_environment_manifest("reachable", sector_count=30)
    assert validate_stratum_environment_manifest(manifest)
    adjacency = {sector["sector_id"]: set() for sector in manifest["sectors"]}
    for edge in manifest["connections"]:
        adjacency[edge["a"]].add(edge["b"])
        adjacency[edge["b"]].add(edge["a"])
    visited = {manifest["entry_sector_id"]}
    frontier = list(visited)
    while frontier:
        current = frontier.pop()
        for neighbor in adjacency[current] - visited:
            visited.add(neighbor)
            frontier.append(neighbor)
    assert visited == set(adjacency)


def test_entry_exit_and_refuge_roles_are_consistent():
    manifest = build_stratum_environment_manifest("roles", sector_count=12)
    by_id = {sector["sector_id"]: sector for sector in manifest["sectors"]}
    assert by_id[manifest["entry_sector_id"]]["role"] == "entry"
    assert by_id[manifest["exit_sector_id"]]["role"] == "exit"
    assert manifest["entry_sector_id"] != manifest["exit_sector_id"]
    if manifest["refuge_sector_id"]:
        assert by_id[manifest["refuge_sector_id"]]["role"] == "refuge"


def test_combat_clearance_fits_every_sector():
    manifest = build_stratum_environment_manifest("clearance", sector_count=16)
    for sector in manifest["sectors"]:
        for axis in ("x", "y", "z"):
            assert sector["combat_clearance_cm"][axis] <= sector["room_size_cm"][axis]


def test_world_origins_are_spaced_and_non_overlapping():
    manifest = build_stratum_environment_manifest("spacing", sector_count=20)
    origins = [(s["world_origin_cm"]["x"], s["world_origin_cm"]["y"]) for s in manifest["sectors"]]
    assert len(origins) == len(set(origins))
    for sector in manifest["sectors"]:
        assert sector["world_origin_cm"]["x"] == sector["grid"]["x"] * manifest["grid_spacing_cm"]
        assert sector["world_origin_cm"]["y"] == sector["grid"]["y"] * manifest["grid_spacing_cm"]


def test_manifest_survives_json_checkpoint_round_trip():
    manifest = build_stratum_environment_manifest("checkpoint", 4, sector_count=18)
    restored = json.loads(json.dumps(manifest))
    assert restored == manifest
    assert rebuild_digest(restored) == manifest["digest"]


def test_validation_rejects_disconnected_sector():
    manifest = build_stratum_environment_manifest("disconnect", sector_count=8)
    isolated = manifest["sectors"][-1]["sector_id"]
    manifest["connections"] = [edge for edge in manifest["connections"] if isolated not in (edge["a"], edge["b"])]
    with pytest.raises(ValueError, match="reachable"):
        validate_stratum_environment_manifest(manifest)


def test_validation_rejects_authoritative_environment():
    manifest = build_stratum_environment_manifest("authority-reject")
    manifest["authoritative"] = True
    with pytest.raises(ValueError, match="presentation-only"):
        validate_stratum_environment_manifest(manifest)


def test_large_generation_is_deterministic_and_valid():
    first = build_stratum_environment_manifest("stress", 7, sector_count=250)
    second = build_stratum_environment_manifest("stress", 7, sector_count=250)
    assert first["digest"] == second["digest"]
    assert validate_stratum_environment_manifest(first)
