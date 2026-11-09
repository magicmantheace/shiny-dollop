"""Conservative *known-context* checks using two public outcome probes.

This is an optional toy-simulation controller, not generally safe causal
exploration. Both probes are drawn from prior segregated A/B histories.
It has NO trained C model. Novel signatures force abstention; this is NOT
successful C task solving or independent semantic affordance learning.
"""
from __future__ import annotations

import json

from developmental_ai.affordance_memory import FilteredNovel, check as check_public, record_step, token
from developmental_ai.contextual_affordance import ContextMemory
from developmental_ai.no_cue_diagnostic import diagnostic_table
from developmental_ai.outcome_skills import canonical, digest

SCHEMA = "developmental-ai.dual-sentinel/v1"
MIN_EXPOSURE = 2
MIN_GAP = 0.25
MAX_STEPS = 18


def sentinel_design(histories):
    """Choose public descriptor codes from each known history's risk evidence.

    The known-context names come from the training harness; runtime public
    observations never contain the phase name or a context beacon.
    """
    if not isinstance(histories, ContextMemory):
        raise TypeError("ContextMemory required")
    names = sorted(histories._rows)
    if len(names) != 2:
        raise ValueError("exactly two fitted histories required")
    risk_sets = [histories._rows[name][1].avoid() for name in names]
    if any(len(s) != 1 for s in risk_sets):
        return None
    codes = [next(iter(s)) for s in risk_sets]
    if codes[0] == codes[1]:
        return None
    observations = diagnostic_table(histories)
    profiles = {}
    for name in names:
        profiles[name] = []
        for code in codes:
            samples = observations[name].get(code)
            if samples is None or samples[1] < MIN_EXPOSURE:
                return None
            smoothed = (samples[0] + 1) / (samples[1] + 2)
            if abs(smoothed - 0.5) < MIN_GAP:
                return None
            profiles[name].append(smoothed > 0.5)
    if profiles[names[0]] == profiles[names[1]]:
        return None
    return {"codes": codes, "profiles": profiles}


class DualSentinel:
    """Probe both known-risk signatures BEFORE any planned resource gathering.

    In the fixed empty-resource cargo simulation, these probes are
    blocked or non-harmful. This is NOT a safety guarantee elsewhere.
    """
    def __init__(self, histories):
        if not isinstance(histories, ContextMemory):
            raise TypeError("two source histories required")
        self.memories = histories
        self.source_sha = histories.record()["sha256"]
        self.design = sentinel_design(histories)
        self.events = []
        self.episode = None
        self.selected = None
        self.unknown = False
        self._delegate = None

    def _choose_probe(self, frame, index):
        signature = self.design["codes"][index]
        matches = [row["id"] for row in frame["descriptors"]
                   if token(row["signature"]) == signature]
        return matches[0] if len(matches) == 1 else None

    def choose(self, frame):
        check_public(frame)
        base = frame["base"]
        if base["done"] or base["tick"] != len(self.events):
            raise ValueError("invalid episode continuity")
        if self.episode is None:
            if base["tick"] != 0:
                raise ValueError("must begin at episode start")
            self.episode = base["episode"]
            if self.design is None or any(v != 0 for v in base["channels"]):
                self.unknown = True
                return None
        if base["episode"] != self.episode:
            raise ValueError("cross-episode evidence")
        if self.events and frame != self.events[-1]["after"]:
            raise ValueError("public observation changed since feedback")
        if self.unknown:
            return None
        if len(self.events) < 2:
            return self._choose_probe(frame, len(self.events))
        return self._delegate.choose(frame) if self._delegate else None

    def feedback(self, before, action, accepted, after):
        check_public(before)
        check_public(after)
        if self.choose(before) != action or type(action) is not str:
            raise ValueError("feedback was not chosen by the public policy")
        observation = record_step(before, action, accepted, after)
        self.events.append({"before": json.loads(canonical(before)),
                            "action": action, "accepted": accepted,
                            "after": json.loads(canonical(after))})
        if len(self.events) == 2:
            evidence = tuple(row["accepted"] for row in self.events)
            eligible = [key for key, prediction in self.design["profiles"].items()
                        if tuple(prediction) == evidence]
            if len(eligible) != 1:
                self.unknown = True
            else:
                self.selected = eligible[0]
                self._delegate = FilteredNovel(self.memories._rows[self.selected][1])
                # Both probes consumed REAL action steps. Keep their public
                # feedback in the continuing action-budget/history.
                for row in self.events:
                    state = record_step(row["before"], row["action"],
                                        row["accepted"], row["after"])
                    self._delegate.history.append({
                        "action": row["action"],
                        "before": json.loads(canonical(row["before"]["base"])),
                        "after": json.loads(canonical(row["after"]["base"])),
                        "accepted": row["accepted"], "effect": state})
        elif len(self.events) > 2:
            if self._delegate is None:
                raise ValueError("no active known memory")
            # The selected delegate has already been queried by choose().
            # It does not mutate the persisted learning histories.
            if len(self._delegate.history) != len(self.events)-1:
                raise AssertionError("delegate history mismatch")
            row = self.events[-1]
            self._delegate.history.append({
                "action": action,
                "before": json.loads(canonical(before["base"])),
                "after": json.loads(canonical(after["base"])),
                "accepted": accepted, "effect": observation})
        return observation

    def record(self):
        if not self.events:
            raise ValueError("no feedback to checkpoint")
        state = {"schema": SCHEMA, "source_sha256": self.source_sha,
                 "events": self.events, "selected": self.selected,
                 "unknown": self.unknown}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, histories, saved):
        if (type(saved) is not dict or set(saved) != {"state","sha256"}
            or type(saved["state"]) is not dict
            or saved["sha256"] != digest(saved["state"])):
            raise ValueError("invalid sentinel checkpoint digest")
        state = saved["state"]
        if (set(state) != {"schema","source_sha256","events","selected","unknown"}
            or state["schema"] != SCHEMA
            or type(state["events"]) is not list
            or not 1 <= len(state["events"]) <= MAX_STEPS):
            raise ValueError("invalid sentinel event schema")
        model = cls(histories)
        if state["source_sha256"] != model.source_sha:
            raise ValueError("checkpoint bound to different training evidence")
        for row in state["events"]:
            if type(row) is not dict or set(row) != {"before","action","accepted","after"}:
                raise ValueError("invalid public transition")
            model.feedback(row["before"], row["action"],
                           row["accepted"], row["after"])
        if model.record() != saved:
            raise ValueError("sentinel decisions failed deterministic replay")
        return model
