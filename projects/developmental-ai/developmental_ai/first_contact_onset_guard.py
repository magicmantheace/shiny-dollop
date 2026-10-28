"""First-contact onset guard: recent8 acting model plus abstention gate.

Frozen protocol: benchmarks/first_contact_onset_guard_protocol.json
(experiment first_contact_onset_guard, frozen 2026-10-28 BEFORE this
implementation). The candidate is a separate optional learner; the
default controller and every existing learner are untouched.

Mechanism, exactly as preregistered:
- Acting model: a RelationOutcomeMemory fitted on the LAST 8 observed
  public events only - identically the recent8 baseline. The candidate
  adds no model selection, no archive, and no displacement margin:
  the gate below is the only difference from recent8.
- Strict prequential scoring over the newest 4 observed events: for
  the scoring event at index i, a RelationOutcomeMemory is fitted
  ONLY on events[i-8:i] (the 8 events strictly before i) and the
  natural probability it assigns to event i's REPORTED outcome class
  is recorded (p(progress) / p(damage) / 1 - p(progress) - p(damage)
  for reported neutral). No scored event is ever in its own fit.
- Contradiction gate: a scoring event is contradicted if its
  prequential probability is strictly below 0.125. If at least 2 of
  the newest 4 scoring events are contradicted, the gate fires and
  the learner abstains from the TEST action (choose returns None).
  An abstention is a failed task, never a success.
- Minimum events: the gate requires 4 scoring events each with 8
  strictly prior fit events, i.e. at least 12 observed events. Below
  12 events the gate is not evaluable and the learner acts with a
  RelationOutcomeMemory fitted on all available events. Every
  benchmark checkpoint in this experiment has at least 240 observed
  events, so that fallback is never exercised during evaluation.
- Action scoring: when the gate does not fire, the choice is exactly
  the acting model's choice (RelationOutcomeMemory utility
  3 * p(progress) - 10 * p(damage), deterministic action-id tie
  break, via RelationOutcomeMemory.choose).

The estimator is the existing RelationOutcomeMemory as coded
(engineered max-minus-min span statistic, 0.25 Laplace smoothing).
The acting window, gate thresholds, and span statistic are all
designer-supplied; this is choosing among / applying already-supplied
representations under a rule change plus a designer-supplied
abstention rule (handoff level 2-3), not novel representation
discovery, independent generalization, or real-world safety. The
learner issues ZERO training interventions: all evidence arrives
from the shared external actor stream.
"""
from __future__ import annotations

import json
import math

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)
SCHEMA = "developmental-ai.first-contact-guard-memory/v1"
ACTING_WINDOW = 8
SCORING_WINDOW = 4
FIT_WINDOW = 8
CONTRADICTION_MIN = 2
CONTRADICTION_P = 0.125
MINIMUM_EVENTS = 12


class FirstContactGuardMemory(FastShockMemory):
    """recent8 acting model guarded by a count-based contradiction gate."""

    def __init__(self):
        super().__init__()
        self._cache = None

    def observe(self, event):
        super().observe(event)
        self._cache = None

    def selection(self):
        if self._cache is not None:
            return self._cache
        if not self.events:
            raise ValueError("insufficient public source outcomes")
        if len(self.events) < MINIMUM_EVENTS:
            model = self._model(self.events)
            decision = {
                "source": "all_available_below_minimum",
                "selection": "all_available_below_minimum",
                "abstained": False,
                "gate_evaluable": False,
                "reason": "gate_not_evaluable_below_minimum_events",
                "prequential_probabilities": [],
                "contradiction_count": 0,
                "contradiction_probability_threshold": CONTRADICTION_P,
                "contradiction_count_threshold": CONTRADICTION_MIN,
                "acting_window": ACTING_WINDOW,
                "scoring_events": 0,
                "predictor_training_overlap": 0,
                "recorded_events": len(self.events),
                "learner_training_actions": 0,
            }
            self._cache = (decision, model)
            return self._cache
        probabilities = []
        for i in range(len(self.events) - SCORING_WINDOW, len(self.events)):
            event = self.events[i]
            fitted = self._model(self.events[i - FIT_WINDOW:i])
            p = self._probability(fitted, event)
            if not math.isfinite(p) or p <= 0:
                raise ValueError("bad prequential probabilities")
            probabilities.append(p)
        contradictions = sum(
            int(p < CONTRADICTION_P) for p in probabilities
        )
        abstained = contradictions >= CONTRADICTION_MIN
        model = self._model(self.events[-ACTING_WINDOW:])
        decision = {
            "source": "recent8",
            "selection": "abstained-by-gate" if abstained else "recent8",
            "abstained": abstained,
            "gate_evaluable": True,
            "reason": ("contradiction_gate_abstain" if abstained
                       else "contradiction_gate_pass"),
            "prequential_probabilities": [round(v, 6) for v in probabilities],
            "contradiction_count": contradictions,
            "contradiction_probability_threshold": CONTRADICTION_P,
            "contradiction_count_threshold": CONTRADICTION_MIN,
            "acting_window": ACTING_WINDOW,
            "scoring_events": SCORING_WINDOW,
            "predictor_training_overlap": 0,
            "recorded_events": len(self.events),
            "learner_training_actions": 0,
        }
        self._cache = (decision, model)
        return self._cache

    def choose(self, frame):
        # Strict public frame validation, exactly as the existing learners;
        # its prediction is not used.
        VariableOutcomeMemory().choose(frame)
        if frame["done"]:
            return None
        decision, model = self.selection()
        if decision["abstained"]:
            return None
        return model.choose(frame)

    def record(self):
        if not self.events:
            raise ValueError("untrained first-contact guard memory")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid first-contact guard checkpoint hash")
        state = record["state"]
        if (set(state) != {"schema", "events"} or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid first-contact guard checkpoint structure")
        m = cls()
        for event in state["events"]:
            m.observe(event)
        if m.record() != record:
            raise ValueError("first-contact guard checkpoint replay mismatch")
        return m
