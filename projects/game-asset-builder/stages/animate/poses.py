"""Procedural pose recipes (pure functions of time — no Blender imports).

Ported from Drabbit Pet's proven pose driver
(``drabbit-pet/desktop/src/renderer/pet/pose-driver.ts``), which itself
mirrors the Blender pose tests for Pip's rig: +headPitch bows the head,
+wingPitch sweeps the wings up, tailYaw wags the tail. ``root_y`` is in
the units of a 2.0-tall character — the rig stage canonicalizes height
to 2.0, so values carry over directly.

P0 bakes two clips:
- ``idle``: 4.8 s loop (two 2.4 s breaths). Deviation from the live
  driver, for loopability: the tail wag uses the 4.8 s clip period
  instead of the driver's 3.8 s, so the clip loops seamlessly.
- ``hop``: 1.24 s loop (two 0.62 s hops; every driver term is periodic
  in 0.62 s, so the loop is exact).

Extension beyond the driver: ``arm_pitch`` for armed templates — arms
trail back slightly during a hop and breathe with the idle. Bones a
template doesn't have are skipped by the animate stage.

P1 adds per-template recipe sets (``TEMPLATE_RECIPES`` below):
quadruped idle + bounce, biped idle + wave. The winged set stays the
module-level ``RECIPES``/``CHANNELS`` for backward compatibility.

P4 adds procedural locomotion (``walk`` / ``run`` for every template)
from the parametric gait model at the bottom of this module: a leg's
cycle is a phase offset into one shared swing/fold pair of curves, so
rig classes differ only in their phase pattern (biped anti-phase,
quadruped lateral-sequence walk, bounding-gallop run) and loops close
exactly by construction. These are functional game locomotion, not
mocap: no IK, so foot placement is approximate.
"""

import math

TAU = math.pi * 2

CHANNELS = ("root_y", "sway", "head_pitch", "ear_pitch", "wing_pitch",
            "wing2_pitch", "arm_pitch", "tail_yaw",
            # P4 gait channels: per-leg swing (+ = foot forward) and
            # per-arm swing (+ = hand forward), winged template.
            "leg.L", "leg.R", "arm.L", "arm.R")

REST = dict.fromkeys(CHANNELS, 0.0)


def hop_arch(t: float, period: float) -> float:
    """One arch of a hop: 0 at the ground, 1 at the apex."""
    p = ((t % period) + period) % period / period
    return math.sin(math.pi * p)


def pose_idle(t: float) -> dict:
    return {
        **REST,
        "root_y": 0.012 * math.sin(TAU * (t / 2.4)),
        "head_pitch": 0.02 * math.sin(TAU * (t / 2.4) + 0.3),
        "ear_pitch": 0.04 * math.sin(TAU * (t / 2.4) + 0.6),
        "wing_pitch": 0.03 * math.sin(TAU * (t / 2.4)),
        "wing2_pitch": 0.015 * math.sin(TAU * (t / 2.4) + 0.4),
        "arm_pitch": 0.02 * math.sin(TAU * (t / 2.4) + 0.5),
        "tail_yaw": 0.08 * math.sin(TAU * (t / 4.8)),
    }


def pose_hop(t: float) -> dict:
    arch = hop_arch(t, 0.62)
    return {
        **REST,
        "root_y": 0.19 * arch ** 1.3,
        "head_pitch": -0.05 * arch,
        "ear_pitch": -0.1 + 0.22 * hop_arch(t - 0.08, 0.62),
        "wing_pitch": 0.65 * arch,
        "wing2_pitch": 0.35 * hop_arch(t - 0.05, 0.62),
        "arm_pitch": -0.35 * arch,
        "tail_yaw": 0.15 * math.sin(TAU * (t / 0.62)),
    }


# name -> (pose function, clip length in seconds)
RECIPES = {
    "idle": (pose_idle, 4.8),
    "hop": (pose_hop, 1.24),
}


def sample(recipe: str, fps: int = 24) -> list[tuple[int, dict]]:
    """(frame, pose) pairs for a winged-creature recipe, frames from 1."""
    fn, seconds = RECIPES[recipe]
    frames = round(seconds * fps)
    return [(f, fn(f / fps)) for f in range(1, frames + 1)]


# ---------------------------------------------------------------------
# Quadruped recipes (P1). Channels name the motion, not the bone-axis
# mechanics — the animate stage's per-template driver table maps each
# channel onto bones with probed axes/signs.
#   leg.XX   upper-leg tuck magnitude in the bounce (the animate
#            stage's drivers carry the sign: probed on the template,
#            +local X swings a leg forward, so the tuck driver is
#            negative and the legs trail/fold as the body lifts)
#   leg2.XX  lower-leg fold that follows the tuck
# The action clip is a happy bounce: all four legs tuck together as
# the body leaves the ground. (A walk cycle in place was the other
# candidate; without ground translation it reads as marching on a
# treadmill, while the bounce is honest in a still and in playback.)
# ---------------------------------------------------------------------

QUAD_CHANNELS = ("root_y", "sway", "spine_pitch", "neck_pitch",
                 "head_pitch", "leg.FL", "leg.FR", "leg.HL", "leg.HR",
                 "leg2.FL", "leg2.FR", "leg2.HL", "leg2.HR", "tail_yaw")
QREST = dict.fromkeys(QUAD_CHANNELS, 0.0)
_QUAD_LEGS = ("leg.FL", "leg.FR", "leg.HL", "leg.HR")
_QUAD_LEGS2 = ("leg2.FL", "leg2.FR", "leg2.HL", "leg2.HR")


def quad_idle(t: float) -> dict:
    breath = math.sin(TAU * (t / 2.4))
    return {
        **QREST,
        "root_y": 0.006 * breath,
        "spine_pitch": 0.012 * breath,
        "neck_pitch": 0.03 * math.sin(TAU * (t / 2.4) + 0.4),
        "head_pitch": 0.025 * math.sin(TAU * (t / 2.4) + 0.7),
        "sway": 0.01 * math.sin(TAU * (t / 4.8)),
        "tail_yaw": 0.10 * math.sin(TAU * (t / 3.2)),
    }


def quad_bounce(t: float) -> dict:
    arch = hop_arch(t, 0.62)
    pose = {
        **QREST,
        "root_y": 0.11 * arch ** 1.2,
        "spine_pitch": -0.04 * arch,
        "neck_pitch": -0.07 * arch,
        "head_pitch": 0.06 * arch,
        "tail_yaw": 0.18 * math.sin(TAU * (t / 0.62)),
    }
    for name in _QUAD_LEGS:
        pose[name] = 0.16 * arch
    for name in _QUAD_LEGS2:
        pose[name] = 0.38 * arch
    return pose


QUAD_RECIPES = {
    "idle": (quad_idle, 4.8),
    "bounce": (quad_bounce, 1.24),
}


# ---------------------------------------------------------------------
# Biped recipes (P1). The action clip is a wave: the right arm raises
# (arm_wave, + = raised), holds while the forearm wiggles (arm2_wave),
# and lowers; the head tilts into it. Idle keeps both arms swaying
# gently via arm_sway.
# ---------------------------------------------------------------------

BIPED_CHANNELS = ("root_y", "sway", "head_pitch", "head_tilt",
                  "ear_pitch", "arm_sway", "arm_wave", "arm2_wave",
                  # P4 gait channels: per-leg swing (+ = foot
                  # forward), per-leg knee fold (+ = shin folds
                  # back), per-arm fore-aft swing (+ = hand
                  # forward) with forearm follow.
                  "leg.L", "leg.R", "leg2.L", "leg2.R",
                  "arm.L", "arm.R", "arm2.L", "arm2.R")
BREST = dict.fromkeys(BIPED_CHANNELS, 0.0)


def biped_idle(t: float) -> dict:
    breath = math.sin(TAU * (t / 2.4))
    return {
        **BREST,
        "root_y": 0.008 * breath,
        "head_pitch": 0.02 * math.sin(TAU * (t / 2.4) + 0.3),
        "head_tilt": 0.02 * math.sin(TAU * (t / 4.8) + 1.0),
        "ear_pitch": 0.03 * math.sin(TAU * (t / 2.4) + 0.9),
        "arm_sway": 0.03 * breath,
        "sway": 0.008 * math.sin(TAU * (t / 4.8)),
    }


def _smoothstep(u: float) -> float:
    u = min(1.0, max(0.0, u))
    return u * u * (3 - 2 * u)


def _wave_envelope(t: float, period: float = 2.4) -> float:
    """0 -> 1 over the first 0.5 s, hold, 1 -> 0 over the last 0.5 s."""
    t = t % period
    if t < 0.5:
        return _smoothstep(t / 0.5)
    if t < period - 0.5:
        return 1.0
    return _smoothstep((period - t) / 0.5)


def biped_wave(t: float) -> dict:
    env = _wave_envelope(t)
    tt = t % 2.4
    wiggle = math.sin(TAU * 2.0 * (tt - 0.5)) if 0.5 <= tt <= 1.9 else 0.0
    return {
        **BREST,
        "root_y": 0.01 * math.sin(TAU * (t / 2.4)),
        "head_pitch": -0.04 * env,
        "head_tilt": 0.09 * env,
        "ear_pitch": 0.05 * env,
        "arm_wave": 1.9 * env,
        "arm2_wave": 0.35 * env * wiggle,
    }


BIPED_RECIPES = {
    "idle": (biped_idle, 4.8),
    "wave": (biped_wave, 2.4),
}


# Per-template recipe registry. ``showcase`` is the clip the catalog
# verifier renders at its apex — the template's signature action.
TEMPLATE_RECIPES = {
    "winged-creature": {"channels": CHANNELS, "rest": REST,
                        "recipes": RECIPES, "showcase": "hop"},
    "quadruped": {"channels": QUAD_CHANNELS, "rest": QREST,
                  "recipes": QUAD_RECIPES, "showcase": "bounce"},
    "biped": {"channels": BIPED_CHANNELS, "rest": BREST,
              "recipes": BIPED_RECIPES, "showcase": "wave"},
}


def template_spec(template: str) -> dict:
    if template not in TEMPLATE_RECIPES:
        raise KeyError(f"unknown template for poses: {template!r}")
    return TEMPLATE_RECIPES[template]


def sample_for(template: str, recipe: str,
               fps: int = 24) -> list[tuple[int, dict]]:
    """(frame, pose) pairs for any template's recipe, frames from 1."""
    fn, seconds = template_spec(template)["recipes"][recipe]
    frames = round(seconds * fps)
    return [(f, fn(f / fps)) for f in range(1, frames + 1)]


def showcase_clip(template: str) -> str:
    return template_spec(template)["showcase"]


# ---------------------------------------------------------------------
# P4 locomotion: a parametric gait model shared by all three rig
# classes. One step cycle is a phase phi in [0, 1). Every leg follows
# the same two curves, shifted by its phase offset:
#
#   gait_swing(phi) = sin(TAU * phi)         +1: foot fully forward,
#                                            -1: fully back
#   gait_fold(phi)  = max(0, sin(TAU * (phi + 0.12))) ** 3
#                     lower-leg fold: zero through the stance phase
#                     (leg loaded, moving back), peaking at phi 0.13,
#                     just after the leg passes vertical into its
#                     forward swing-through.
#
# Every term is a sinusoid (or a clipped sinusoid power) of the cycle
# phase, so pose(0) == pose(period) exactly and the baked clips loop
# seamlessly by construction. Classes differ only in phase pattern:
#
#   biped / winged   anti-phase pair (L 0.0, R 0.5); arms counter-
#                    swing against the same-side leg.
#   quadruped walk   lateral sequence FL 0.0, HR 0.25, FR 0.5,
#                    HL 0.75 (each foot steps in turn).
#   quadruped run    bounding gallop: front pair together (0.0),
#                    hind pair together (0.5), spine rocking and a
#                    once-per-cycle body bounce.
#
# Amplitudes are radians at the bone. Channel sign conventions match
# the animate stage's probed drivers (stages/animate/
# animate_blender.py): biped/winged leg channels are + = foot
# forward; biped leg2 channels are + = knee fold; quadruped leg
# channels keep the P1 convention (+ = foot trails back, the bounce
# tuck direction) and leg2 + = shin fold, so the gait writes the
# quadruped swing negated. The winged template's legs are single-
# segment (no leg2 bone), so its gaits have no knee fold — the
# honest limit of that rig.
# ---------------------------------------------------------------------


def gait_swing(phase: float) -> float:
    return math.sin(TAU * phase)


def gait_fold(phase: float) -> float:
    return max(0.0, math.sin(TAU * (phase + 0.12))) ** 3


def _ph(t: float, period: float, offset: float = 0.0) -> float:
    return (t / period + offset) % 1.0


# --- winged-creature (upright two-leg plan; arms counter-swing) ------

def winged_walk(t: float) -> dict:
    period = 1.5
    swing = gait_swing(_ph(t, period))
    return {
        **REST,
        "leg.L": 0.50 * swing,
        "leg.R": -0.50 * swing,
        "arm.L": -0.35 * swing,
        "arm.R": 0.35 * swing,
        "root_y": -0.015 * (0.5 + 0.5 * math.cos(2 * TAU * (t / period))),
        "head_pitch": 0.04 * math.sin(2 * TAU * (t / period)),
        "ear_pitch": 0.05 * math.sin(2 * TAU * (t / period) - 0.5),
        "wing_pitch": 0.05 * math.sin(2 * TAU * (t / period)),
        "wing2_pitch": 0.03 * math.sin(2 * TAU * (t / period) - 0.4),
        "tail_yaw": 0.15 * math.sin(TAU * (t / period)),
    }


def winged_run(t: float) -> dict:
    period = 1.0
    swing = gait_swing(_ph(t, period))
    return {
        **REST,
        "leg.L": 0.70 * swing,
        "leg.R": -0.70 * swing,
        "arm.L": -0.50 * swing,
        "arm.R": 0.50 * swing,
        "root_y": 0.02 + 0.028 * math.sin(2 * TAU * (t / period)),
        "head_pitch": 0.08 + 0.03 * math.sin(2 * TAU * (t / period)),
        "ear_pitch": -0.06 + 0.04 * math.sin(2 * TAU * (t / period) - 0.5),
        "wing_pitch": 0.16 + 0.10 * math.sin(TAU * (t / period)),
        "wing2_pitch": 0.10 + 0.06 * math.sin(TAU * (t / period) - 0.4),
        "tail_yaw": 0.18 * math.sin(TAU * (t / period)),
    }


# --- biped ------------------------------------------------------------

def biped_walk(t: float) -> dict:
    period = 1.5
    ph = _ph(t, period)
    swing = gait_swing(ph)
    return {
        **BREST,
        "leg.L": 0.50 * swing,
        "leg.R": -0.50 * swing,
        "leg2.L": 0.70 * gait_fold(ph),
        "leg2.R": 0.70 * gait_fold(_ph(t, period, 0.5)),
        "arm.L": -0.38 * swing,
        "arm.R": 0.38 * swing,
        "arm2.L": -0.19 * swing + 0.10,
        "arm2.R": 0.19 * swing + 0.10,
        "root_y": -0.018 * (0.5 + 0.5 * math.cos(2 * TAU * ph)),
        "sway": 0.035 * math.sin(TAU * ph),
        "head_pitch": 0.03 * math.sin(2 * TAU * ph),
        "ear_pitch": 0.03 * math.sin(2 * TAU * ph - 0.5),
    }


def biped_run(t: float) -> dict:
    period = 1.0
    ph = _ph(t, period)
    swing = gait_swing(ph)
    return {
        **BREST,
        "leg.L": 0.78 * swing,
        "leg.R": -0.78 * swing,
        "leg2.L": 1.05 * gait_fold(ph),
        "leg2.R": 1.05 * gait_fold(_ph(t, period, 0.5)),
        "arm.L": -0.55 * swing,
        "arm.R": 0.55 * swing,
        "arm2.L": -0.30 * swing + 0.35,
        "arm2.R": 0.30 * swing + 0.35,
        "root_y": 0.02 + 0.026 * math.sin(2 * TAU * ph),
        "sway": 0.03 * math.sin(TAU * ph),
        "head_pitch": 0.12 + 0.03 * math.sin(2 * TAU * ph),
        "ear_pitch": -0.04 + 0.03 * math.sin(2 * TAU * ph - 0.5),
    }


# --- quadruped ----------------------------------------------------------

QUAD_WALK_OFFSETS = {"FL": 0.0, "HR": 0.25, "FR": 0.5, "HL": 0.75}
QUAD_RUN_OFFSETS = {"FL": 0.0, "FR": 0.0, "HL": 0.5, "HR": 0.5}


def _quad_gait(t: float, period: float, offsets: dict,
               swing_amp: float, fold_amp: float) -> dict:
    pose = dict(QREST)
    for corner, off in offsets.items():
        ph = _ph(t, period, off)
        # Quadruped channel convention: leg + trails the foot back
        # (the P1 tuck direction), so forward swing is negative.
        pose[f"leg.{corner}"] = -swing_amp * gait_swing(ph)
        pose[f"leg2.{corner}"] = fold_amp * gait_fold(ph)
    return pose


def quad_walk(t: float) -> dict:
    period = 2.0
    ph = _ph(t, period)
    pose = _quad_gait(t, period, QUAD_WALK_OFFSETS, 0.42, 0.55)
    pose.update({
        "root_y": 0.012 * math.sin(2 * TAU * ph),
        "spine_pitch": 0.025 * math.sin(2 * TAU * ph + 0.5),
        "neck_pitch": -0.05 * math.sin(TAU * ph + 0.4),
        "head_pitch": 0.04 * math.sin(TAU * ph + 0.9),
        "sway": 0.02 * math.sin(TAU * ph),
        "tail_yaw": 0.12 * math.sin(TAU * ph + 0.5),
    })
    return pose


def quad_run(t: float) -> dict:
    period = 1.0
    ph = _ph(t, period)
    pose = _quad_gait(t, period, QUAD_RUN_OFFSETS, 0.62, 0.85)
    pose.update({
        "root_y": 0.055 * math.sin(TAU * ph - 0.5),
        "spine_pitch": 0.11 * math.sin(TAU * ph),
        "neck_pitch": -0.09 * math.sin(TAU * ph),
        "head_pitch": 0.06 * math.sin(TAU * ph + 0.6),
        "tail_yaw": 0.16 * math.sin(TAU * ph + 1.2),
    })
    return pose


RECIPES["walk"] = (winged_walk, 1.5)
RECIPES["run"] = (winged_run, 1.0)
BIPED_RECIPES["walk"] = (biped_walk, 1.5)
BIPED_RECIPES["run"] = (biped_run, 1.0)
QUAD_RECIPES["walk"] = (quad_walk, 2.0)
QUAD_RECIPES["run"] = (quad_run, 1.0)
