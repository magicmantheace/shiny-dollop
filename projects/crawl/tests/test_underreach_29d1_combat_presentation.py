from copy import deepcopy
import json

import pytest

from livingworld.underreach_combat_presentation import (
    PROTOCOL,
    build_combat_presentation,
    build_combat_presentation_proof,
    rebuild_digest,
    validate_combat_presentation,
)


def _proof(seed="underreach-29d1-tests"):
    return build_combat_presentation_proof(seed)


def test_same_input_reproduces_source_and_presentation_digests():
    first = _proof()
    second = _proof()
    assert first["source"]["canonical_digest"] == second["source"]["canonical_digest"]
    assert first["presentation"]["digest"] == second["presentation"]["digest"]
    assert first == second


def test_presentation_authority_boundary_is_explicit():
    proof = _proof()
    manifest = proof["presentation"]
    assert manifest["protocol"] == PROTOCOL
    assert manifest["authoritative"] is False
    assert manifest["simulation_time_independent"] is True
    assert manifest["canonical_state_mutation_allowed"] is False
    assert manifest["source_canonical_digest"] == proof["source"]["canonical_digest"]


def test_every_window_points_to_real_canonical_action():
    proof = _proof()
    frames = proof["source"]["canonical_truth"]["frames"]
    for window in proof["presentation"]["windows"]:
        action = frames[window["source_frame_index"]]["actions"][window["source_action_index"]]
        assert window["source_tick"] == frames[window["source_frame_index"]]["tick"]
        assert window["source_action_kind"] == action["kind"]


def test_attacks_have_windup_contact_and_recovery_order():
    manifest = _proof()["presentation"]
    attacks = [window for window in manifest["windows"] if window["presentation_kind"] == "attack"]
    assert attacks
    for window in attacks:
        assert window["start_seconds"] < window["windup_end_seconds"] < window["contact_seconds"] < window["end_seconds"]
        assert window["animation_slot"].endswith("combat.attack.default")


def test_canonical_misses_never_generate_hit_reactions():
    proof = _proof()
    source_frames = proof["source"]["canonical_truth"]["frames"]
    reactions = proof["presentation"]["windows"]
    reactions = [window for window in reactions if window["presentation_kind"] == "hit_reaction"]
    reaction_sources = {(window["source_frame_index"], window["source_action_index"]) for window in reactions}
    for frame_index, frame in enumerate(source_frames):
        for action_index, action in enumerate(frame["actions"]):
            if action["kind"] in {"descender_attack", "monster_attack"} and not action.get("hit", False):
                assert (frame_index, action_index) not in reaction_sources


def test_every_canonical_hit_gets_one_reaction():
    proof = _proof()
    frames = proof["source"]["canonical_truth"]["frames"]
    windows = proof["presentation"]["windows"]
    hits = []
    for fi, frame in enumerate(frames):
        for ai, action in enumerate(frame["actions"]):
            if action["kind"] in {"descender_attack", "monster_attack"} and action.get("hit", False):
                hits.append((fi, ai, action["target_id"]))
    reactions = [(w["source_frame_index"], w["source_action_index"], w["actor_id"]) for w in windows if w["presentation_kind"] == "hit_reaction"]
    assert sorted(hits) == sorted(reactions)


def test_death_windows_only_follow_canonical_death_state():
    proof = _proof()
    frames = proof["source"]["canonical_truth"]["frames"]
    for window in proof["presentation"]["windows"]:
        if window["presentation_kind"] != "death":
            continue
        frame = frames[window["source_frame_index"]]
        actor_id = window["actor_id"]
        if actor_id.startswith("descender_"):
            assert frame["descender_state"][actor_id] == "dead"
        else:
            assert frame["enemy_state"][actor_id]["alive"] is False
        assert window["canonical_death"] is True


def test_facing_yaw_is_bounded_and_present_for_pair_actions():
    for window in _proof()["presentation"]["windows"]:
        if window["target_id"] is not None and window["canonical_position_cm"] is not None and window["canonical_target_position_cm"] is not None:
            assert window["facing_yaw_degrees"] is not None
            assert -180.0 <= window["facing_yaw_degrees"] <= 180.0


def test_actor_tracks_reference_existing_windows_only():
    manifest = _proof()["presentation"]
    ids = {window["window_id"] for window in manifest["windows"]}
    assert ids
    for actor_id, track in manifest["actor_tracks"].items():
        assert track
        assert set(track) <= ids
        assert all(next(w for w in manifest["windows"] if w["window_id"] == window_id)["actor_id"] == actor_id for window_id in track)


def test_presentation_tamper_cannot_change_canonical_source():
    proof = _proof()
    source_before = deepcopy(proof["source"])
    proof["presentation"]["windows"][0]["start_seconds"] += 99.0
    assert proof["source"] == source_before


def test_invented_reaction_for_miss_is_rejected():
    proof = _proof()
    source = proof["source"]
    manifest = deepcopy(proof["presentation"])
    miss = None
    for fi, frame in enumerate(source["canonical_truth"]["frames"]):
        for ai, action in enumerate(frame["actions"]):
            if action["kind"] in {"descender_attack", "monster_attack"} and not action.get("hit", False):
                miss = (fi, ai, action)
                break
        if miss:
            break
    if miss is None:
        pytest.skip("deterministic proof contains no miss")
    fi, ai, action = miss
    fake = deepcopy(manifest["windows"][0])
    fake.update({
        "window_id": "invented_reaction",
        "source_frame_index": fi,
        "source_action_index": ai,
        "source_action_kind": action["kind"],
        "actor_id": action["target_id"],
        "presentation_kind": "hit_reaction",
    })
    manifest["windows"].append(fake)
    manifest["digest"] = rebuild_digest(manifest)
    with pytest.raises(ValueError, match="invented hit reaction"):
        validate_combat_presentation(manifest, source)


def test_wrong_canonical_binding_is_rejected():
    proof = _proof()
    altered = deepcopy(proof["presentation"])
    altered["source_canonical_digest"] = "0" * 64
    altered["digest"] = rebuild_digest(altered)
    with pytest.raises(ValueError, match="wrong canonical digest"):
        validate_combat_presentation(altered, proof["source"])


def test_json_roundtrip_preserves_digest_and_validity():
    proof = _proof()
    restored_source = json.loads(json.dumps(proof["source"], sort_keys=True))
    restored_manifest = json.loads(json.dumps(proof["presentation"], sort_keys=True))
    assert restored_manifest["digest"] == proof["presentation"]["digest"]
    assert validate_combat_presentation(restored_manifest, restored_source)


def test_stress_40_presentations_are_deterministic_and_bounded():
    for index in range(40):
        proof = build_combat_presentation_proof(f"underreach-29d1-stress-{index:03d}")
        manifest = proof["presentation"]
        assert validate_combat_presentation(manifest, proof["source"])
        assert manifest["presentation_duration_seconds"] >= 0.0
        assert len(manifest["windows"]) < 2000
