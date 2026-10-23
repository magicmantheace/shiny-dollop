import math
from dataclasses import asdict, dataclass, replace


ARENA_SAFE_HALF_SIZE = 560.0
PRESENTATION_FPS = 60


@dataclass(frozen=True)
class AttackPresentationProfile:
    """Asset-specific, non-authoritative presentation data for a canonical hit."""

    asset_slot: str
    asset_path: str
    contact_phase: float
    contact_frame_offset: int
    contact_effector: str
    forward_reach_cm: float
    lateral_reach_cm: float
    contact_height_cm: float
    target_chest_height_cm: float
    ready_forward_distance_cm: float
    recovery_forward_distance_cm: float
    target_knockback_cm: float
    approach_lead_seconds: float
    reaction_latency_seconds: float
    root_yaw_offset_degrees: float
    animation_forward_axis: str
    source_duration_seconds: float
    locomotion_reference_speed_cm_s: float
    minimum_locomotion_play_rate: float
    maximum_locomotion_play_rate: float
    force_root_lock: bool
    maximum_evaluated_planar_error_cm: float
    maximum_evaluated_contact_error_cm: float
    presentation_severity: str
    reaction_severity: str


_MM_ATTACK_01 = AttackPresentationProfile(
    asset_slot="humanoid.combat.attack.default",
    asset_path="/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_01.MM_Attack_01",
    # Measured from MM_Attack_01 at 100 samples across its one-second clip.
    # At 0.41 s the right hand is at maximum forward extension from the torso;
    # with authored root translation removed it is 93.9 cm forward and only
    # 2.6 cm lateral. The cross-body right strike reads more clearly than the
    # extended-arm silhouette in MM_Attack_02 from the automated camera angle.
    contact_phase=0.4083333333333333,
    # At 60 fps, 18 presentation frames and a 1.3667x play rate evaluate
    # source phase 0.41 exactly. This avoids landing on either side of the
    # strike's very fast cross-body sweep after Sequencer frame rounding.
    contact_frame_offset=18,
    contact_effector="hand_r",
    forward_reach_cm=93.75389138214155,
    lateral_reach_cm=-0.2642009185206877,
    contact_height_cm=131.0665834249894,
    target_chest_height_cm=130.0,
    ready_forward_distance_cm=145.0,
    recovery_forward_distance_cm=128.0,
    target_knockback_cm=45.0,
    approach_lead_seconds=0.75,
    reaction_latency_seconds=1.0 / 60.0,
    root_yaw_offset_degrees=-90.0,
    animation_forward_axis="+Y",
    source_duration_seconds=1.0,
    # MF_Unarmed_Walk_Fwd moves 450 cm over its 1.5 s authored cycle.
    locomotion_reference_speed_cm_s=300.0,
    # Short engagement adjustments need a partial slow stride. A 0.65 floor
    # made the limbs cycle much faster than a 35-75 cm/s root translation.
    minimum_locomotion_play_rate=0.25,
    maximum_locomotion_play_rate=1.8,
    force_root_lock=True,
    # spine_05 is a center point, while a mannequin upper torso is a volume.
    # This still rejects shoulder-adjacent air hits but permits surface contact.
    maximum_evaluated_planar_error_cm=30.0,
    maximum_evaluated_contact_error_cm=45.0,
    presentation_severity="light",
    reaction_severity="light",
)

_MM_ATTACK_02 = AttackPresentationProfile(
    asset_slot="humanoid.combat.attack.02",
    asset_path="/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_02.MM_Attack_02",
    # UE AnimPose component-space measurement, root locked, 241 samples.
    # Attack_02's left hand is the actual forward strike; the right hand stays
    # in a higher guard/sweep pose and must not be used as its contact effector.
    contact_phase=0.4708333333333333,
    contact_frame_offset=21,
    contact_effector="hand_l",
    forward_reach_cm=97.7748906987194,
    lateral_reach_cm=9.30160308312567,
    contact_height_cm=131.095181748399,
    target_chest_height_cm=130.0,
    ready_forward_distance_cm=150.0,
    recovery_forward_distance_cm=136.0,
    target_knockback_cm=40.0,
    approach_lead_seconds=0.75,
    reaction_latency_seconds=1.0 / 60.0,
    root_yaw_offset_degrees=-90.0,
    animation_forward_axis="+Y",
    source_duration_seconds=1.0,
    locomotion_reference_speed_cm_s=300.0,
    minimum_locomotion_play_rate=0.25,
    maximum_locomotion_play_rate=1.8,
    force_root_lock=True,
    maximum_evaluated_planar_error_cm=30.0,
    maximum_evaluated_contact_error_cm=45.0,
    presentation_severity="light",
    reaction_severity="light",
)

_MM_ATTACK_03 = AttackPresentationProfile(
    asset_slot="humanoid.combat.attack.03",
    asset_path="/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_Attack_03.MM_Attack_03",
    # Full-resolution render review identifies this asset as a high right-foot
    # kick. The AnimPose measurement finds torso-height extension at source
    # phase 0.3167; using the later hand follow-through delayed the reaction by
    # roughly 0.2 seconds after the visible kick landed.
    contact_phase=0.316666666666667,
    contact_frame_offset=19,
    contact_effector="foot_r",
    forward_reach_cm=124.526041468324,
    lateral_reach_cm=-2.74402341032634,
    contact_height_cm=131.860785853606,
    target_chest_height_cm=130.0,
    ready_forward_distance_cm=168.0,
    recovery_forward_distance_cm=154.0,
    target_knockback_cm=50.0,
    approach_lead_seconds=0.78,
    reaction_latency_seconds=1.0 / 60.0,
    root_yaw_offset_degrees=-90.0,
    animation_forward_axis="+Y",
    source_duration_seconds=1.6666666269302368,
    locomotion_reference_speed_cm_s=300.0,
    minimum_locomotion_play_rate=0.25,
    maximum_locomotion_play_rate=1.8,
    force_root_lock=True,
    maximum_evaluated_planar_error_cm=30.0,
    maximum_evaluated_contact_error_cm=45.0,
    presentation_severity="medium",
    reaction_severity="medium",
)

_MM_CHARGED_ATTACK = AttackPresentationProfile(
    asset_slot="humanoid.combat.attack.charged",
    asset_path="/Game/Characters/Mannequins/Anims/Unarmed/Attack/MM_ChargedAttack.MM_ChargedAttack",
    # ChargedAttack's right hand accelerates more than 115 cm over the 5% phase
    # preceding contact, giving this profile a visibly different heavy windup.
    contact_phase=0.6083333333333333,
    contact_frame_offset=39,
    contact_effector="hand_r",
    forward_reach_cm=98.03181408576881,
    lateral_reach_cm=-9.285899742679897,
    contact_height_cm=123.6758770384452,
    target_chest_height_cm=130.0,
    ready_forward_distance_cm=170.0,
    recovery_forward_distance_cm=150.0,
    target_knockback_cm=65.0,
    approach_lead_seconds=0.85,
    reaction_latency_seconds=1.0 / 60.0,
    root_yaw_offset_degrees=-90.0,
    animation_forward_axis="+Y",
    source_duration_seconds=1.8333333730697632,
    locomotion_reference_speed_cm_s=300.0,
    minimum_locomotion_play_rate=0.25,
    maximum_locomotion_play_rate=1.8,
    force_root_lock=True,
    maximum_evaluated_planar_error_cm=30.0,
    maximum_evaluated_contact_error_cm=45.0,
    presentation_severity="heavy",
    reaction_severity="heavy",
)

_HUMANOID_ATTACK_PROFILES = (
    _MM_ATTACK_01,
    _MM_ATTACK_02,
    _MM_ATTACK_03,
    _MM_CHARGED_ATTACK,
)

ATTACK_PRESENTATION_PROFILES = {
    profile.asset_slot: profile
    for profile in _HUMANOID_ATTACK_PROFILES
}
ATTACK_PRESENTATION_PROFILES.update({
    profile.asset_slot.replace("humanoid", "enemy.biped", 1): replace(
        profile,
        asset_slot=profile.asset_slot.replace("humanoid", "enemy.biped", 1),
    )
    for profile in _HUMANOID_ATTACK_PROFILES
})

# Backwards-compatible names used by earlier Slice 28A validation.
ATTACK_APPROACH_LEAD_SECONDS = _MM_ATTACK_01.approach_lead_seconds
ATTACK_READY_DISTANCE = _MM_ATTACK_01.ready_forward_distance_cm
ATTACK_CONTACT_DISTANCE = math.hypot(
    _MM_ATTACK_01.forward_reach_cm,
    _MM_ATTACK_01.lateral_reach_cm,
)
ATTACK_RECOVER_DISTANCE = math.hypot(
    _MM_ATTACK_01.recovery_forward_distance_cm,
    _MM_ATTACK_01.lateral_reach_cm,
)
TARGET_KNOCKBACK_DISTANCE = _MM_ATTACK_01.target_knockback_cm
IMPACT_FRACTION = _MM_ATTACK_01.contact_phase


def attack_profile_for_slot(asset_slot):
    try:
        return ATTACK_PRESENTATION_PROFILES[asset_slot]
    except KeyError as exc:
        raise ValueError(f"No attack presentation profile for {asset_slot!r}") from exc


def attack_profile_debug(profile):
    return asdict(profile)


def _copy_pose(pose):
    return dict(pose)


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def planar_distance(source, target):
    dx = float(target["x"]) - float(source["x"])
    dy = float(target["y"]) - float(source["y"])
    return math.sqrt(dx * dx + dy * dy)


def _direction(source, target):
    dx = float(target["x"]) - float(source["x"])
    dy = float(target["y"]) - float(source["y"])
    length = math.sqrt(dx * dx + dy * dy)
    if length > 1.0e-4:
        return dx / length, dy / length

    yaw = math.radians(float(source.get("yaw", 0.0)))
    return math.cos(yaw), math.sin(yaw)


def _face(source, target):
    return math.degrees(
        math.atan2(
            float(target["y"]) - float(source["y"]),
            float(target["x"]) - float(source["x"]),
        )
    )


def _normalize_angle(angle):
    return (float(angle) + 180.0) % 360.0 - 180.0


def _animation_facing_yaw(source, target, profile):
    return _normalize_angle(_face(source, target) + profile.root_yaw_offset_degrees)


def _offset_from_target(target, direction_x, direction_y, forward, lateral):
    # With local +Y authored as attack-forward and root yaw offset -90 degrees,
    # the local +X hand offset maps to this clockwise perpendicular basis.
    lateral_x, lateral_y = direction_y, -direction_x
    result = _copy_pose(target)
    result["x"] = float(target["x"]) - direction_x * forward - lateral_x * lateral
    result["y"] = float(target["y"]) - direction_y * forward - lateral_y * lateral
    return result


def _translate_pose(pose, offset_x, offset_y):
    result = _copy_pose(pose)
    result["x"] = float(result["x"]) + offset_x
    result["y"] = float(result["y"]) + offset_y
    return result


def _fit_group_inside_arena(poses):
    min_x = min(float(pose["x"]) for pose in poses)
    max_x = max(float(pose["x"]) for pose in poses)
    min_y = min(float(pose["y"]) for pose in poses)
    max_y = max(float(pose["y"]) for pose in poses)
    span_x = max_x - min_x
    span_y = max_y - min_y
    if span_x > ARENA_SAFE_HALF_SIZE * 2.0 or span_y > ARENA_SAFE_HALF_SIZE * 2.0:
        raise ValueError("Combat staging group is wider than the proof arena")

    offset_x = 0.0
    offset_y = 0.0
    if min_x < -ARENA_SAFE_HALF_SIZE:
        offset_x = -ARENA_SAFE_HALF_SIZE - min_x
    if max_x + offset_x > ARENA_SAFE_HALF_SIZE:
        offset_x += ARENA_SAFE_HALF_SIZE - (max_x + offset_x)
    if min_y < -ARENA_SAFE_HALF_SIZE:
        offset_y = -ARENA_SAFE_HALF_SIZE - min_y
    if max_y + offset_y > ARENA_SAFE_HALF_SIZE:
        offset_y += ARENA_SAFE_HALF_SIZE - (max_y + offset_y)
    return [_translate_pose(pose, offset_x, offset_y) for pose in poses]


def _locomotion_metrics(distance_cm, duration_seconds, profile):
    distance = max(0.0, float(distance_cm))
    duration = max(0.0, float(duration_seconds))
    speed = distance / duration if duration > 1.0e-6 else 0.0
    raw_rate = speed / profile.locomotion_reference_speed_cm_s if speed > 0.0 else 1.0
    play_rate = _clamp(
        raw_rate,
        profile.minimum_locomotion_play_rate,
        profile.maximum_locomotion_play_rate,
    )
    return speed, play_rate


def contact_effector_position(attacker_contact, profile, attacker_scale=1.0):
    facing = math.radians(
        float(attacker_contact["yaw"]) - profile.root_yaw_offset_degrees
    )
    direction_x, direction_y = math.cos(facing), math.sin(facing)
    lateral_x, lateral_y = direction_y, -direction_x
    scale = float(attacker_scale)
    return {
        "x": float(attacker_contact["x"]) + direction_x * profile.forward_reach_cm * scale + lateral_x * profile.lateral_reach_cm * scale,
        "y": float(attacker_contact["y"]) + direction_y * profile.forward_reach_cm * scale + lateral_y * profile.lateral_reach_cm * scale,
        "z": float(attacker_contact["z"]) + profile.contact_height_cm * scale,
    }


def stage_attack_exchange(
    attacker_pose,
    target_pose,
    start_seconds,
    duration_seconds,
    asset_slot="humanoid.combat.attack.default",
    attacker_scale=1.0,
    target_scale=1.0,
    attacker_available_seconds=0.0,
    target_available_seconds=0.0,
):
    """Create deterministic presentation poses for one canonical hit.

    The ledger already established the outcome. This stages both participants,
    aligns MM_Attack_01's measured right-hand reach to the target torso, and
    synchronizes reaction timing to that visual contact pose.
    """
    profile = attack_profile_for_slot(asset_slot)
    attacker = _copy_pose(attacker_pose)
    target = _copy_pose(target_pose)
    duration = max(0.1, float(duration_seconds))
    start = max(0.0, float(start_seconds))
    end = start + duration
    attacker_approach_start = max(
        0.0,
        start - profile.approach_lead_seconds,
        float(attacker_available_seconds),
    )
    target_approach_start = max(
        0.0,
        start - profile.approach_lead_seconds,
        float(target_available_seconds),
    )
    start_frame = int(round(start * PRESENTATION_FPS))
    end_frame = max(start_frame + 2, int(round(end * PRESENTATION_FPS)))
    contact_frame_offset = min(
        int(profile.contact_frame_offset),
        end_frame - start_frame - 1,
    )
    visual_contact_frame = start_frame + contact_frame_offset
    visual_contact = visual_contact_frame / PRESENTATION_FPS
    reaction_latency_frames = max(
        0,
        int(round(profile.reaction_latency_seconds * PRESENTATION_FPS)),
    )
    reaction_start = (visual_contact_frame + reaction_latency_frames) / PRESENTATION_FPS
    attack_animation_play_rate = (
        profile.contact_phase
        * profile.source_duration_seconds
        * PRESENTATION_FPS
        / contact_frame_offset
    )

    direction_x, direction_y = _direction(attacker, target)
    initial_distance = planar_distance(attacker, target)
    attacker_scale = float(attacker_scale)
    target_scale = float(target_scale)
    ready_forward = profile.ready_forward_distance_cm * attacker_scale
    ready_lateral = profile.lateral_reach_cm * attacker_scale
    closing_distance = max(0.0, initial_distance - ready_forward)
    attacker_available = max(0.0, start - attacker_approach_start)
    target_available = max(0.0, start - target_approach_start)
    available_total = attacker_available + target_available
    target_forward_move = (
        closing_distance * target_available / available_total
        if available_total > 1.0e-6
        else 0.0
    )

    target_ready = _copy_pose(target)
    target_ready["x"] = float(target_ready["x"]) - direction_x * target_forward_move
    target_ready["y"] = float(target_ready["y"]) - direction_y * target_forward_move
    ready = _offset_from_target(
        target_ready,
        direction_x,
        direction_y,
        ready_forward,
        ready_lateral,
    )

    contact = _offset_from_target(
        target_ready,
        direction_x,
        direction_y,
        profile.forward_reach_cm * attacker_scale,
        profile.lateral_reach_cm * attacker_scale,
    )

    target_hit = _copy_pose(target_ready)
    target_hit["x"] = float(target_hit["x"]) + direction_x * profile.target_knockback_cm * target_scale
    target_hit["y"] = float(target_hit["y"]) + direction_y * profile.target_knockback_cm * target_scale

    recover = _offset_from_target(
        target_hit,
        direction_x,
        direction_y,
        profile.recovery_forward_distance_cm * attacker_scale,
        profile.lateral_reach_cm * attacker_scale,
    )

    ready, contact, recover, target_ready, target_hit = _fit_group_inside_arena(
        [ready, contact, recover, target_ready, target_hit]
    )

    attack_direction_yaw = math.degrees(math.atan2(direction_y, direction_x))
    attack_root_yaw = _normalize_angle(
        attack_direction_yaw + profile.root_yaw_offset_degrees
    )
    # Preserve the measured animation-forward axis. The hand's authored lateral
    # offset is solved in position, so rotating the torso toward its own offset
    # root would undo the contact alignment.
    ready["yaw"] = attack_root_yaw
    contact["yaw"] = attack_root_yaw
    recover["yaw"] = attack_root_yaw
    target_ready["yaw"] = _animation_facing_yaw(target_ready, ready, profile)
    target_hit["yaw"] = _animation_facing_yaw(target_hit, recover, profile)

    attacker_approach_distance = planar_distance(attacker, ready)
    target_approach_distance = planar_distance(target, target_ready)
    attacker_speed, attacker_play_rate = _locomotion_metrics(
        attacker_approach_distance,
        attacker_available,
        profile,
    )
    target_speed, target_play_rate = _locomotion_metrics(
        target_approach_distance,
        target_available,
        profile,
    )
    effector = contact_effector_position(contact, profile, attacker_scale)
    target_chest = {
        "x": float(target_ready["x"]),
        "y": float(target_ready["y"]),
        "z": float(target_ready["z"]) + profile.target_chest_height_cm * target_scale,
    }
    horizontal_contact_error = math.hypot(
        effector["x"] - target_chest["x"],
        effector["y"] - target_chest["y"],
    )

    return {
        "asset_slot": profile.asset_slot,
        "attack_profile": attack_profile_debug(profile),
        "approach_start_seconds": attacker_approach_start,
        "target_approach_start_seconds": target_approach_start,
        "attack_start_seconds": start,
        "visual_contact_seconds": visual_contact,
        "visual_contact_frame": visual_contact_frame,
        "contact_frame_offset": contact_frame_offset,
        "attack_animation_play_rate": attack_animation_play_rate,
        "impact_seconds": visual_contact,
        "reaction_start_seconds": reaction_start,
        "end_seconds": end,
        "attacker_initial": attacker,
        "attacker_ready": ready,
        "attacker_contact": contact,
        "attacker_recover": recover,
        "target_initial": target,
        "target_ready": target_ready,
        "target_contact": _copy_pose(target_ready),
        "target_hit": target_hit,
        "target_recover": _copy_pose(target_hit),
        "target_chest": target_chest,
        "estimated_contact_effector": effector,
        "initial_distance": initial_distance,
        "ready_distance": planar_distance(ready, target_ready),
        "contact_distance": planar_distance(contact, target_ready),
        "recover_distance": planar_distance(recover, target_hit),
        "contact_phase": profile.contact_phase,
        "impact_fraction": profile.contact_phase,
        "attacker_yaw": contact["yaw"],
        "target_yaw": target_ready["yaw"],
        "attacker_facing_error_degrees": abs(
            _normalize_angle(
                contact["yaw"] - profile.root_yaw_offset_degrees - _face(contact, target_ready)
            )
        ),
        "target_facing_error_degrees": abs(
            _normalize_angle(
                target_ready["yaw"] - profile.root_yaw_offset_degrees - _face(target_ready, ready)
            )
        ),
        "approach_distance": attacker_approach_distance,
        "approach_duration_seconds": attacker_available,
        "approach_speed_cm_s": attacker_speed,
        "locomotion_play_rate": attacker_play_rate,
        "target_approach_distance": target_approach_distance,
        "target_approach_duration_seconds": target_available,
        "target_approach_speed_cm_s": target_speed,
        "target_locomotion_play_rate": target_play_rate,
        "expected_contact_error_cm": horizontal_contact_error,
        "vertical_contact_error_cm": effector["z"] - target_chest["z"],
        "authoritative": False,
    }
