from copy import deepcopy
import pytest

from livingworld.underreach_animation_binding import ATTACK_ASSET_ORDER, PROFILE_PROTOCOL as ATTACK_PROFILE_PROTOCOL
from livingworld.underreach_reaction_death_binding import (
    PROFILE_PROTOCOL, PROTOCOL, build_reaction_death_binding_proof,
    rebuild_digest, validate_reaction_death_binding,
)


def _attack_profile(name, i):
    return {
        "asset_name": name, "asset_path": f"/Game/Test/{name}.{name}",
        "source_duration_seconds": 1.0 + i * .1,
        "contact_effector": ("hand_r","hand_l","foot_r","hand_r")[i],
        "target_torso_bone": "spine_05",
        "candidate_contact_phase": (.4083,.4708,.3167,.6083)[i],
        "candidate_contact_seconds": (.4083,.4708,.3167,.6083)[i] * (1.0 + i*.1),
        "candidate_forward_reach_cm": (93.75,97.77,124.53,98.03)[i],
        "candidate_contact_height_cm": 120+i,
        "pose_variation": {"unique_forward":100,"unique_lateral":80,"unique_height":60},
    }


def _attacks():
    return {"protocol":ATTACK_PROFILE_PROTOCOL,"authoritative":False,
            "evaluation_mode":"anim_pose_component_space_root_locked","sample_count_per_asset":241,
            "profiles":[_attack_profile(n,i) for i,n in enumerate(ATTACK_ASSET_ORDER)],"missing_assets":[]}


def _reactions():
    return {"protocol":PROFILE_PROTOCOL,"authoritative":False,
            "evaluation_mode":"anim_pose_component_space_root_locked",
            "profiles":[
                {"kind":"hit_reaction","asset_name":"MM_HitReact_Test","asset_path":"/Game/Test/MM_HitReact_Test.MM_HitReact_Test","source_duration_seconds":.8,"pose_variation":{"unique_pelvis":6,"unique_spine":6,"unique_head":6},"terminal_pelvis_delta_cm":4.0},
                {"kind":"death","asset_name":"MM_Death_Test","asset_path":"/Game/Test/MM_Death_Test.MM_Death_Test","source_duration_seconds":1.5,"pose_variation":{"unique_pelvis":6,"unique_spine":6,"unique_head":6},"terminal_pelvis_delta_cm":75.0},
            ]}


def _proof(seed="underreach-29d3-tests"):
    return build_reaction_death_binding_proof(_attacks(), _reactions(), seed)


def test_same_input_is_deterministic(): assert _proof() == _proof()

def test_authority_boundary_and_protocol():
    b=_proof()["reaction_death_binding"]
    assert b["protocol"]==PROTOCOL and b["authoritative"] is False
    assert b["canonical_state_mutation_allowed"] is False and b["simulation_time_independent"] is True

def test_all_reactions_and_deaths_are_real_assets():
    b=_proof()["reaction_death_binding"]["bindings"]
    target=[x for x in b if x["presentation_kind"] in {"hit_reaction","death"}]
    assert target and all(x["binding_status"]=="measured_real_asset" and x["asset_path"] for x in target)

def test_reactions_are_exactly_contact_synced():
    for x in _proof()["reaction_death_binding"]["bindings"]:
        if x["presentation_kind"]=="hit_reaction": assert x["contact_sync_error_seconds"] <= .001

def test_deaths_require_canonical_death_and_terminal_pose():
    deaths=[x for x in _proof()["reaction_death_binding"]["bindings"] if x["presentation_kind"]=="death"]
    assert deaths and all(x["canonical_death"] is True and x["terminal_pose_required"] is True for x in deaths)

def test_non_reaction_bindings_are_unchanged_from_29d2():
    p=_proof(); old={x["binding_id"]:x for x in p["animation_binding_proof"]["binding"]["bindings"]}
    for x in p["reaction_death_binding"]["bindings"]:
        if x["presentation_kind"] not in {"hit_reaction","death"}: assert x==old[x["binding_id"]]

def test_missing_reaction_asset_rejected():
    m=_reactions(); m["profiles"]=[p for p in m["profiles"] if p["kind"]!="hit_reaction"]
    with pytest.raises(ValueError, match="no measured real hit_reaction"): build_reaction_death_binding_proof(_attacks(),m)

def test_missing_death_asset_rejected():
    m=_reactions(); m["profiles"]=[p for p in m["profiles"] if p["kind"]!="death"]
    with pytest.raises(ValueError, match="no measured real death"): build_reaction_death_binding_proof(_attacks(),m)

def test_frozen_profile_rejected():
    m=_reactions(); m["profiles"][0]["pose_variation"]={"unique_pelvis":1,"unique_spine":1,"unique_head":1}
    with pytest.raises(ValueError, match="frozen measured profile"): build_reaction_death_binding_proof(_attacks(),m)

def test_tamper_canonical_digest_rejected():
    p=_proof(); altered=deepcopy(p["reaction_death_binding"]); altered["source_canonical_digest"]="0"*64; altered["digest"]=rebuild_digest(altered)
    with pytest.raises(ValueError, match="wrong canonical digest"): validate_reaction_death_binding(altered,p["animation_binding_proof"],_attacks(),_reactions())

def test_stress_40_sources_valid():
    for i in range(40):
        p=build_reaction_death_binding_proof(_attacks(),_reactions(),f"underreach-29d3-stress-{i:03d}")
        assert validate_reaction_death_binding(p["reaction_death_binding"],p["animation_binding_proof"],_attacks(),_reactions())
