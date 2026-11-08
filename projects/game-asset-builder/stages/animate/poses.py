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
"""

import math

TAU = math.pi * 2

CHANNELS = ("root_y", "sway", "head_pitch", "ear_pitch", "wing_pitch",
            "wing2_pitch", "arm_pitch", "tail_yaw")

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
                  "ear_pitch", "arm_sway", "arm_wave", "arm2_wave")
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
