from copy import deepcopy

import pytest

from livingworld.crawl_domain import CrawlEvent
from livingworld.crawl_service import CrawlLifecycleService
from livingworld.equipment_attachment import attachment_profile_payload, attachment_profiles
from livingworld.live_camera_director import LiveCameraDirector
from livingworld.live_presentation_bridge import LivePresentationScheduler
from livingworld.presentation_facing import (
    desired_facing_for_movement,
    plan_turn,
    signed_angular_error,
)


def environment():
    return {
        "room_bounds": {"min": {"x": -1300, "y": -1800, "z": 0}, "max": {"x": 1300, "y": 1800, "z": 700}},
        "valid_camera_region": {"min": {"x": -1240, "y": -1740, "z": 80}, "max": {"x": 1240, "y": 1740, "z": 620}},
        "camera_forbidden_volumes": [],
    }


def event(index, event_type="CRAWLER_MOVED", actors=("live_descender_004",)):
    return CrawlEvent(
        id=f"event_{index:03d}", crawl_id="descent_a", floor_number=1, tick=index,
        event_type=event_type, summary="presentation QA", actor_ids=list(actors),
        location_id="sector_a", data={},
    )


def actor_state(actor_id="live_descender_004"):
    return {
        actor_id: {
            "actor_id": actor_id, "actor_kind": "descender", "spawned": True, "terminal": False,
            "transform": {"x": -300.0, "y": 0.0, "z": 94.0, "yaw": 0.0},
        }
    }


@pytest.mark.parametrize("species", ["human", "dwarf"])
def test_equipment_profiles_resolve_required_sockets_and_modes(species):
    profiles = attachment_profiles(species)
    assert {item.socket_name for item in profiles} == {"head", "spine_03", "hand_r"}
    assert {item.attachment_mode for item in profiles} == {"skeletal_skin"}
    assert len({item.slot for item in profiles}) == 3


def test_equipment_profiles_are_deterministic_and_species_specific():
    assert attachment_profile_payload("human") == attachment_profile_payload("human")
    human = {item["slot"]: item for item in attachment_profile_payload("human")}
    dwarf = {item["slot"]: item for item in attachment_profile_payload("dwarf")}
    assert human["head_armor"]["geometry"] != dwarf["head_armor"]["geometry"]
    assert human["right_hand"]["geometry"] != dwarf["right_hand"]["geometry"]


@pytest.mark.parametrize("angle", [45.0, 90.0, 135.0, 180.0])
def test_turn_planner_handles_required_angles(angle):
    result = plan_turn(0.0, angle, mode="align_to_movement")
    assert result["absolute_angular_error"] == pytest.approx(angle)
    assert result["turn_action"] == f"turn_{int(angle)}"
    assert 0.0 < result["duration_seconds"] <= 0.36


def test_desired_facing_uses_authored_positive_y_forward_axis():
    assert desired_facing_for_movement(1, 0, current_yaw=20) == pytest.approx(-90)
    assert desired_facing_for_movement(0, 1, current_yaw=20) == pytest.approx(0)
    assert abs(signed_angular_error(179, -179)) == pytest.approx(2)


def test_scheduler_turns_before_direction_change_and_locomotion_is_aligned():
    service = CrawlLifecycleService()
    descent = service.create_seeded_crawl(
        seed="29a1.1-facing", crawler_ids=["live_descender_004"], floor_count=2, crawl_id="descent_a"
    )
    service.start(descent)
    scheduler = LivePresentationScheduler(
        descent.id, presentation_seed="facing", focus_actor_ids=["live_descender_004"]
    )
    scheduler.bootstrap(descent, environment=environment())
    scheduler.schedule([event(1)], authoritative_tick=1)
    result = scheduler.schedule([event(2)], authoritative_tick=2)
    turn = next(item for item in result["commands"] if item["type"] == "turn_actor")
    move = next(item for item in result["commands"] if item["type"] == "move_actor")
    locomotion = next(item for item in result["commands"] if item["type"] == "play_locomotion")
    assert turn["presentation_seconds"] < move["presentation_seconds"]
    assert move["transform"]["yaw"] == locomotion["desired_yaw"]
    assert abs(signed_angular_error(move["transform"]["yaw"], locomotion["desired_yaw"])) <= 12.0


def test_terminal_actor_ignores_later_facing_and_movement():
    service = CrawlLifecycleService()
    descent = service.create_seeded_crawl(
        seed="29a1.1-terminal", crawler_ids=["live_descender_004"], floor_count=2, crawl_id="descent_a"
    )
    service.start(descent)
    scheduler = LivePresentationScheduler(
        descent.id, presentation_seed="terminal", focus_actor_ids=["live_descender_004"]
    )
    scheduler.bootstrap(descent, environment=environment())
    scheduler.schedule([event(1, "CRAWLER_DIED")], authoritative_tick=1)
    result = scheduler.schedule([event(2)], authoritative_tick=2)
    assert not any(item["type"] in {"turn_actor", "move_actor", "play_locomotion"} for item in result["commands"])


def test_camera_waits_for_missing_follow_actor_then_reacquires_it():
    director = LiveCameraDirector("descent_a", presentation_seed="camera", environment=environment())
    transition = {
        "transition_id": "focus_a", "to_descender_id": "live_descender_004",
        "mode": "manual", "reason": "manual_follow", "presentation_seconds": 0.0,
    }
    director.direct(
        frame_sequence=1, current_events=[event(1)], lookahead_events=[], commands=[],
        actor_states={}, from_seconds=0.0, to_seconds=0.2, authoritative_tick=1,
        focus_transition=transition,
    )
    assert director.pending_focus_transition == transition
    result = director.direct(
        frame_sequence=2, current_events=[event(2)], lookahead_events=[], commands=[],
        actor_states=actor_state(), from_seconds=0.5, to_seconds=0.8, authoritative_tick=2,
    )
    assert result[-1]["target_actor_ids"] == ["live_descender_004"]
    assert director.pending_focus_transition is None
    diagnostics = director.diagnostics(1.0)
    assert diagnostics["actor_readiness_waits"] == 1
    assert diagnostics["stale_target_incidents"] == 0


def test_manual_follow_cut_excludes_stale_old_target():
    director = LiveCameraDirector("descent_a", presentation_seed="camera", environment=environment())
    states = {**actor_state("live_descender_004"), **actor_state("live_descender_005")}
    director.direct(
        frame_sequence=1, current_events=[event(1)], lookahead_events=[], commands=[],
        actor_states=states, from_seconds=0.0, to_seconds=0.2, authoritative_tick=1,
    )
    transition = {
        "transition_id": "focus_b", "to_descender_id": "live_descender_005",
        "mode": "manual", "reason": "manual_switch", "presentation_seconds": 0.5,
    }
    result = director.direct(
        frame_sequence=2, current_events=[event(2)], lookahead_events=[], commands=[],
        actor_states=states, from_seconds=0.5, to_seconds=0.8, authoritative_tick=2,
        focus_transition=deepcopy(transition),
    )
    assert result[-1]["target_actor_ids"] == ["live_descender_005"]
    assert director.diagnostics(1.0)["stale_target_incidents"] == 0


def test_manual_follow_overrides_terminal_hold_and_preserves_acquisition_on_reconnect():
    director = LiveCameraDirector("descent_a", presentation_seed="camera", environment=environment())
    states = {**actor_state("live_descender_004"), **actor_state("live_descender_005")}
    director.direct(
        frame_sequence=1, current_events=[event(1)], lookahead_events=[], commands=[{
            "type": "play_terminal", "actor_id": "enemy_a", "presentation_seconds": 0.0,
            "source_event_id": "terminal_a",
        }], actor_states=states, from_seconds=0.0, to_seconds=0.2, authoritative_tick=1,
    )
    transition = {
        "transition_id": "focus_during_hold", "to_descender_id": "live_descender_005",
        "mode": "manual", "reason": "manual_switch", "presentation_seconds": 0.5,
    }
    result = director.direct(
        frame_sequence=2, current_events=[event(2)], lookahead_events=[], commands=[],
        actor_states=states, from_seconds=0.5, to_seconds=0.8, authoritative_tick=2,
        focus_transition=transition,
    )
    assert result[-1]["target_actor_ids"] == ["live_descender_005"]
    assert director.diagnostics(1.0)["maximum_focus_acquisition_seconds"] == 0.0
    snapshot = director.snapshot()
    restored = LiveCameraDirector("descent_a", presentation_seed="camera", environment=environment())
    restored.restore(snapshot)
    diagnostics = restored.diagnostics(1.0)
    assert diagnostics["acquisition_records"] == director.diagnostics(1.0)["acquisition_records"]
    assert diagnostics["stale_target_incidents"] == 0
