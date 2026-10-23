"""Presentation-only terminal death policy shared by the Unreal build."""

TERMINAL_ROLES = frozenset({"death", "defeat"})
CORPSE_ROOT_DROP_CM = 70.0
CORPSE_ROOT_MIN_Z = 20.0
CORPSE_ROOT_PITCH_DEGREES = -70.0


def corpse_transform_pose(pose):
    corpse = dict(pose)
    corpse["z"] = max(CORPSE_ROOT_MIN_Z, float(pose.get("z", 90.0)) - CORPSE_ROOT_DROP_CM)
    corpse["pitch"] = CORPSE_ROOT_PITCH_DEGREES
    return corpse


def terminal_start_seconds(intents):
    starts = [
        float(intent["start_seconds"])
        for intent in intents
        if intent.get("role") in TERMINAL_ROLES
    ]
    return min(starts) if starts else None


def intent_allowed_after_terminal(intent, terminal_start):
    if terminal_start is None:
        return True
    if intent.get("role") in TERMINAL_ROLES:
        return float(intent["start_seconds"]) <= float(terminal_start) + 1.0e-9
    return float(intent["start_seconds"]) < float(terminal_start) - 1.0e-9
