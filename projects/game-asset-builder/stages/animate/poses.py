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
    """(frame, pose) pairs for a recipe, frames numbered from 1."""
    fn, seconds = RECIPES[recipe]
    frames = round(seconds * fps)
    return [(f, fn(f / fps)) for f in range(1, frames + 1)]
