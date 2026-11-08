"""Versioned, headless, simulation-only environment adapter (D2 experimental).

This module provides a *common interface*, not a common learned intelligence.
Each backend keeps its own task observations and action vocabulary. No hidden
world state, human data, unrestricted tool commands, or operating-system access
is exposed by the interface. Checkpoints are replayed from deterministic inputs.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from typing import Any

from developmental_ai.delayed_choice import DelayArena, episode_seed as delay_seed
from developmental_ai.occluded_navigation import OccludedWorld, episode_seed as occluded_seed
from developmental_ai.transfer import Layout, TransferArena, episode_seed as transfer_seed

SCHEMA = "developmental-ai.environment-session/v1"
FRAME_SCHEMA = "developmental-ai.environment-frame/v1"
CHECKPOINT_SCHEMA = "developmental-ai.environment-checkpoint/v1"
FAMILIES = ("grid", "occluded", "delayed")
SPLITS = ("train", "test")
MAX_ACTIONS = 200


def canonical(value: Any) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True, allow_nan=False)


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _config(family: str, seed: int, split: str, index: int, variant: str) -> dict:
    if (type(family) is not str or family not in FAMILIES or type(seed) is not int or
            not -(2**31) <= seed < 2**31 or type(split) is not str or split not in SPLITS or
            type(index) is not int or not 0 <= index < 1000000 or
            type(variant) is not str or variant not in (("short", "long") if family == "delayed" else ("default",))):
        raise ValueError("invalid environment configuration")
    return {"family": family, "seed": seed, "split": split, "index": index, "variant": variant}


@dataclass(frozen=True)
class PublicResult:
    observation: dict
    reward: float
    done: bool
    event: str


class EnvironmentSession:
    """Typed in-memory simulator; no file I/O, network I/O or privileged actions."""

    def __init__(self, family: str, seed: int, split: str, index: int, variant: str = "default"):
        self.config = _config(family, seed, split, index, variant)
        self.episode_id = digest({"schema": SCHEMA, "config": self.config})
        self.family = family
        if family == "grid":
            self._world = TransferArena(Layout.generate(transfer_seed(seed, split, index)))
            self.actions = (0, 1, 2, 3, 4)
        elif family == "occluded":
            self._world = OccludedWorld(Layout.generate(occluded_seed(seed, split, index)))
            self.actions = (0, 1, 2, 3, 4)
        else:
            self._world = DelayArena(delay_seed(seed, split, index, variant), variant)
            self.actions = (0, 1, 2, 3, 4)
        self.tick = 0
        self.done = False
        self._entries: list[dict] = []
        self._chain = digest({"schema": CHECKPOINT_SCHEMA, "episode_id": self.episode_id})

    def _observation(self) -> dict:
        observed = self._world.observe()
        if self.family == "grid":
            dx, dy, walls = observed
            return {"target_dx": dx, "target_dy": dy, "blocked": walls}
        return dict(observed)

    def _available(self) -> list[int]:
        if self.done:
            return []
        if self.family != "delayed":
            return list(self.actions)
        return [0, 1, 2, 3] if self._world.observe()["phase"] == "decision" else [4]

    def frame(self) -> dict:
        return {"schema": FRAME_SCHEMA, "episode_id": self.episode_id,
                "family": self.family, "tick": self.tick, "observation": self._observation(),
                "available_actions": self._available(), "done": self.done,
                "scope": "simulation-only", "source": "simulation"}

    def step(self, action: int, *, expected_tick: int) -> dict:
        if self.done or self.tick >= MAX_ACTIONS:
            raise ValueError("episode completed or action budget exhausted")
        if type(expected_tick) is not int or expected_tick != self.tick:
            raise ValueError("stale or invalid expected tick")
        if type(action) is not int or action not in self._available():
            raise ValueError("action not allowed in current observation")
        prior = self.frame()
        if self.family == "grid":
            _, reward, done, event = self._world.step(action)
        elif self.family == "occluded":
            reward, done, event = self._world.step(action)
        else:
            _, reward, done, event = self._world.step(action)
        if not math.isfinite(reward):
            raise ValueError("invalid simulated reward")
        self.tick += 1
        self.done = bool(done) or self.tick >= MAX_ACTIONS
        if self.tick >= MAX_ACTIONS and not done:
            event = "budget_exhausted"
        result = {"frame": self.frame(), "reward": reward, "event": event}
        entry = {"action": action, "before": prior, "result": result}
        self._chain = digest({"previous": self._chain, "entry": entry})
        self._entries.append(entry)
        return result

    def checkpoint(self) -> dict:
        state = {"schema": CHECKPOINT_SCHEMA, "config": self.config,
                 "initial_id": self.episode_id, "entries": self._entries,
                 "chain": self._chain, "tick": self.tick, "done": self.done}
        return {"state": json.loads(canonical(state)), "digest": digest(state)}

    @classmethod
    def restore(cls, saved: dict) -> "EnvironmentSession":
        if (type(saved) is not dict or set(saved) != {"state", "digest"} or
                type(saved["state"]) is not dict or type(saved["digest"]) is not str or
                digest(saved["state"]) != saved["digest"]):
            raise ValueError("invalid checkpoint digest")
        state = saved["state"]
        if (set(state) != {"schema", "config", "initial_id", "entries", "chain", "tick", "done"} or
                state["schema"] != CHECKPOINT_SCHEMA or type(state["config"]) is not dict or
                set(state["config"]) != {"family", "seed", "split", "index", "variant"} or
                type(state["entries"]) is not list or len(state["entries"]) > MAX_ACTIONS or
                type(state["tick"]) is not int or type(state["done"]) is not bool):
            raise ValueError("invalid checkpoint structure")
        rebuilt = cls(**state["config"])
        if rebuilt.episode_id != state["initial_id"]:
            raise ValueError("checkpoint environment mismatch")
        for entry in state["entries"]:
            if (type(entry) is not dict or set(entry) != {"action", "before", "result"} or
                    entry["before"] != rebuilt.frame()):
                raise ValueError("checkpoint observation mismatch")
            replayed = rebuilt.step(entry["action"], expected_tick=rebuilt.tick)
            if replayed != entry["result"]:
                raise ValueError("checkpoint replay mismatch")
        if (rebuilt.tick != state["tick"] or rebuilt.done != state["done"] or
                rebuilt._chain != state["chain"]):
            raise ValueError("checkpoint chain mismatch")
        return rebuilt
