import json

import pytest

from livingworld.stratum_environment import build_stratum_environment_manifest
from livingworld.stratum_multisector import build_multisector_presentation_plan
from livingworld.stratum_live_traversal import (
    CHECKPOINT_PROTOCOL,
    LIVE_TRAVERSAL_PROTOCOL,
    build_live_traversal_stream,
    make_checkpoint,
    rebuild_digest,
    resume_from_checkpoint,
)


def _fixture(seed="underreach-29b21-proof", sectors=9):
    manifest = build_stratum_environment_manifest(seed, 0, sector_count=sectors)
    plan = build_multisector_presentation_plan(manifest)
    stream = build_live_traversal_stream(manifest, plan)
    return manifest, plan, stream


def test_same_inputs_produce_identical_stream_and_digest():
    first = _fixture()[2]
    second = _fixture()[2]
    assert first == second
    assert first["digest"] == second["digest"]


def test_protocol_is_presentation_only():
    _, _, stream = _fixture()
    assert stream["protocol"] == LIVE_TRAVERSAL_PROTOCOL
    assert stream["authoritative"] is False


def test_stream_spans_entry_to_exit_in_route_order():
    manifest, plan, stream = _fixture()
    assert stream["route_sector_ids"] == plan["proof_route_sector_ids"]
    assert stream["frames"][0]["sector_id"] == manifest["entry_sector_id"]
    assert stream["frames"][-1]["sector_id"] == manifest["exit_sector_id"]


def test_every_route_hop_has_transition_samples():
    _, _, stream = _fixture()
    transitions = [f for f in stream["frames"] if f["phase"] == "sector_transition"]
    expected = (len(stream["route_sector_ids"]) - 1) * (stream["samples_per_transition"] - 1)
    assert len(transitions) == expected


def test_follow_and_auto_never_lose_target():
    _, _, stream = _fixture()
    for frame in stream["frames"]:
        for mode in ("follow", "auto"):
            channel = frame["feed"][mode]
            assert channel["target_id"] == stream["descender_id"]
            assert channel["empty"] is False
            assert channel["stale"] is False


def test_sequences_are_contiguous():
    _, _, stream = _fixture()
    assert [f["sequence"] for f in stream["frames"]] == list(range(len(stream["frames"])))


def test_transition_positions_reach_next_sector_center():
    manifest, _, stream = _fixture()
    by_id = {s["sector_id"]: s for s in manifest["sectors"]}
    arrivals = [f for f in stream["frames"] if f["phase"] == "sector_arrival"]
    for frame in arrivals:
        origin = by_id[frame["sector_id"]]["world_origin_cm"]
        assert frame["transform"]["x"] == pytest.approx(origin["x"])
        assert frame["transform"]["y"] == pytest.approx(origin["y"])


def test_checkpoint_round_trip_preserves_sector_and_target():
    _, _, stream = _fixture()
    index = len(stream["frames"]) // 2
    checkpoint = make_checkpoint(stream, index)
    loaded = json.loads(json.dumps(checkpoint))
    resumed = resume_from_checkpoint(stream, loaded)
    assert loaded["protocol"] == CHECKPOINT_PROTOCOL
    assert loaded["current_sector_id"] == stream["frames"][index]["sector_id"]
    assert loaded["follow_target_id"] == stream["descender_id"]
    assert resumed[0] == stream["frames"][index]
    assert resumed[-1] == stream["frames"][-1]


def test_resume_preserves_exact_stratum_and_multisector_digests():
    _, _, stream = _fixture()
    checkpoint = make_checkpoint(stream, len(stream["frames"]) // 2)
    resume_from_checkpoint(stream, checkpoint)
    assert checkpoint["stratum_environment_digest"] == stream["stratum_environment_digest"]
    assert checkpoint["multisector_digest"] == stream["multisector_digest"]


def test_tampered_checkpoint_sector_is_rejected():
    _, _, stream = _fixture()
    checkpoint = make_checkpoint(stream, 1)
    checkpoint["current_sector_id"] = "sector_fake"
    with pytest.raises(ValueError, match="current Sector"):
        resume_from_checkpoint(stream, checkpoint)


def test_tampered_stream_digest_is_rejected():
    _, _, stream = _fixture()
    checkpoint = make_checkpoint(stream, 1)
    checkpoint["stream_digest"] = "bad"
    with pytest.raises(ValueError, match="stream digest"):
        resume_from_checkpoint(stream, checkpoint)


def test_digest_rebuild_matches():
    _, _, stream = _fixture()
    assert rebuild_digest(stream) == stream["digest"]


def test_different_seed_changes_live_stream_digest():
    first = _fixture("seed-a")[2]
    second = _fixture("seed-b")[2]
    assert first["digest"] != second["digest"]


def test_250_sector_stream_remains_valid_and_reaches_exit():
    manifest, plan, stream = _fixture("underreach-29b21-stress", sectors=250)
    assert stream["frames"][0]["sector_id"] == manifest["entry_sector_id"]
    assert stream["frames"][-1]["sector_id"] == manifest["exit_sector_id"]
    assert stream["route_sector_ids"] == plan["proof_route_sector_ids"]
    assert all(not f["feed"]["follow"]["stale"] for f in stream["frames"])
