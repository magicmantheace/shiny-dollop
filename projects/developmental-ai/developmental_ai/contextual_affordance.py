"""Optional A-B-A context-indexed risk memory for changing action descriptors.

The simulator supplies a clear, engineered two-number context beacon. The
learner uses only this beacon and the replayed public outcome histories to
route risk memories. It does not infer regimes without the beacon, discover
action semantics, obtain private recipes, or authorize real-world actions.
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from developmental_ai.affordance_memory import (
    DescribedWorld, FilteredNovel, RiskMemory, check as check_public,
    signature, token,
)
from developmental_ai.outcome_skills import canonical, digest
from developmental_ai.opaque_causal import OpaqueWorld

SCHEMA = "developmental-ai.contextual-affordance/v1"
CUES = {"A": [0, 2], "B": [2, 0]}  # SIMULATOR ONLY; never seen as phase names
LIMIT_BYTES = 4 * 1024 * 1024


def validate_cue(value):
    if (type(value) is not list or len(value) != 2
        or any(type(x) is not int or not 0 <= x <= 3 for x in value)):
        raise ValueError("invalid context observation")
    return value


def key(cue):
    return ".".join(str(x) for x in validate_cue(cue))


class ShiftedCargo:
    """Simulator with unchanged cargo rules but phase-dependent code meanings."""
    def __init__(self, seed, split, index, phase):
        if phase not in CUES:
            raise ValueError("only two controlled environments")
        self.phase = phase
        self.seed = seed
        try:
            self.world = DescribedWorld(seed, split, index, "cargo")
        except ValueError as exc:
            if str(exc) != "descriptor hash collision":
                raise
            # Protocol-preserving simulator fix: two-byte descriptors can
            # collide on an already-frozen seed (51013: load/spoil). Do NOT
            # cherry-pick a replacement seed or change the earlier simulator.
            # Resolve duplicate codes deterministically in action declaration
            # order, only inside this new optional synthetic environment.
            world = object.__new__(DescribedWorld)
            world.base = OpaqueWorld(seed, split, index, "cargo")
            world.seed, world.family, world.remap = seed, "cargo", False
            world._features = {}
            used = set()
            for name in world.base._names:
                code = signature(seed, "cargo", name)
                while token(code) in used:
                    code = [code[0], (code[1] + 1) % 256]
                world._features[name] = code
                used.add(token(code))
            self.world = world
        if phase == "B":
            # SIMULATOR ONLY. The same numeric code now identifies a
            # different private action; neither the learner nor record
            # contains the mapping names or the phase identifier.
            a, b = self.world._features["spoil"], self.world._features["wash"]
            self.world._features["spoil"] = list(b)
            self.world._features["wash"] = list(a)

    def frame(self, *, ambiguous=False):
        observation = self.world.frame()
        return {"public": observation,
                "cue": [1, 1] if ambiguous else list(CUES[self.phase])}

    def step(self, action, tick, *, ambiguous=False):
        result = self.world.step(action, tick)
        return {"accepted": result["accepted"],
                "frame": self.frame(ambiguous=ambiguous)}

    def success(self):
        return self.world.public_success()


def check(frame):
    if type(frame) is not dict or set(frame) != {"public", "cue"}:
        raise ValueError("unexpected contextual observation fields")
    check_public(frame["public"])
    validate_cue(frame["cue"])
    return frame


class ContextMemory:
    """Exactly two replay-verified outcome memories indexed by public cues."""
    def __init__(self, pairs):
        if (type(pairs) is not list or len(pairs) != 2):
            raise ValueError("two independently fitted contexts required")
        self._rows = {}
        for pair in pairs:
            if type(pair) is not list or len(pair) != 2:
                raise ValueError("invalid cue/model pair")
            cue, memory = pair
            index = key(cue)
            if index in self._rows or not isinstance(memory, RiskMemory) or not memory.events:
                raise ValueError("duplicate or untrained memory")
            self._rows[index] = (list(cue), RiskMemory.restore(memory.record()))
        if len(self._rows) != 2:
            raise ValueError("missing context history")

    def choose_memory(self, cue):
        value = validate_cue(cue)
        # Generic Euclidean cue matching. Exact cues are engineered by
        # the simulator; ties choose lexical order, NOT privileged regime.
        select = min(self._rows,
                     key=lambda name: (sum((a-b)**2 for a,b in
                                           zip(value, self._rows[name][0])), name))
        return self._rows[select][1]

    def record(self):
        state = {"schema": SCHEMA, "contexts": [
            {"cue": self._rows[k][0], "memory": self._rows[k][1].record()}
            for k in sorted(self._rows)]}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, saved):
        if (type(saved) is not dict or set(saved) != {"state", "sha256"}
            or type(saved["state"]) is not dict
            or saved["sha256"] != digest(saved["state"])):
            raise ValueError("invalid contextual checkpoint digest")
        state = saved["state"]
        if (set(state) != {"schema", "contexts"} or state["schema"] != SCHEMA
            or type(state["contexts"]) is not list or len(state["contexts"]) != 2):
            raise ValueError("invalid contextual checkpoint schema")
        pairs = []
        for row in state["contexts"]:
            if type(row) is not dict or set(row) != {"cue", "memory"}:
                raise ValueError("invalid contextual checkpoint row")
            pairs.append([row["cue"], RiskMemory.restore(row["memory"])])
        model = cls(pairs)
        if model.record() != saved:
            raise ValueError("contextual replay mismatch")
        return model

    def save(self, path):
        target = Path(path)
        payload = (canonical(self.record()) + "\n").encode("utf-8")
        if len(payload) > LIMIT_BYTES:
            raise ValueError("contextual checkpoint too large")
        target.parent.mkdir(parents=True, exist_ok=True)
        pending = None
        try:
            with tempfile.NamedTemporaryFile("wb", dir=target.parent,
                                             prefix=".context-risk-", delete=False) as stream:
                pending = Path(stream.name)
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(pending, target)
        finally:
            if pending is not None:
                pending.unlink(missing_ok=True)

    @classmethod
    def load(cls, path):
        target = Path(path)
        if target.stat().st_size > LIMIT_BYTES:
            raise ValueError("contextual checkpoint too large")
        return cls.restore(json.loads(target.read_text(encoding="utf-8")))


class ContextNovel:
    """Read-only per-episode controller using public cue-selected prior."""
    def __init__(self, memory):
        if not isinstance(memory, ContextMemory):
            raise TypeError("contextual memory required")
        self.memory = memory
        self.cue = None
        self._controller = None

    def choose(self, frame):
        check(frame)
        if self.cue is None:
            if frame["public"]["base"]["tick"] != 0:
                raise ValueError("initial beacon required")
            self.cue = list(frame["cue"])
            self._controller = FilteredNovel(self.memory.choose_memory(self.cue))
        if frame["cue"] != self.cue:
            raise ValueError("context unexpectedly changed mid-episode")
        return self._controller.choose(frame["public"])

    def feedback(self, before, action, accepted, after):
        check(before)
        check(after)
        if before["cue"] != after["cue"]:
            raise ValueError("invalid mid-episode context change")
        self.choose(before)
        return self._controller.feedback(before["public"], action, accepted,
                                         after["public"])
