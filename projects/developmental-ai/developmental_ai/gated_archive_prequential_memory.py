"""Gated archive with strict prequential displacement; simulation-only.

Frozen protocol: benchmarks/early_post_switch_adaptation_protocol.json
(experiment early_post_switch_adaptation, frozen 2026-10-27 BEFORE this
implementation). The candidate is a separate optional learner; the default
controller and every existing learner are untouched.

Mechanism, exactly as preregistered:
- Archive: a RelationOutcomeMemory fitted once on the FIRST 192 public
  events. It is never refitted, extended, or overwritten; later events
  only ever enter the recent-window candidate fits and the scoring tail.
- Strict prequential scoring over the last 8 observed events: for the
  scoring event at index i, every candidate is fitted ONLY on events
  strictly before i (archive events[0:192]; recent8 events[i-8:i];
  recent32 events[i-32:i]) and scored by the natural log probability it
  assigns to that event's REPORTED outcome class. No scored event is in
  its own scoring model.
- Displacement: the archive is the default selection. A recent window
  displaces it only if that window's total prequential log-score exceeds
  the archive's by MORE than 1.0. Between the recent windows, recent32
  is selected only if its total exceeds recent8's by MORE than 1.0,
  otherwise recent8 (when recent8 is the qualifying displacer; if only
  recent32 qualifies, recent32 is selected).
- Contradiction override: if at least 2 of the latest 4 scoring events
  have archive-assigned probability < 0.125 for their reported outcome
  class, the archive is ineligible at that decision regardless of the
  margin rule; the better recent window (per the recent32-vs-recent8
  margin rule above) is selected.
- Adequacy gate: if the SELECTED candidate's mean prequential log-score
  over the 8 scoring events is below -1.2 (total below -9.6), the
  learner abstains from the TEST action (choose returns None). An
  abstention is a failed task, never a success.
- Action scoring: the selected candidate is a RelationOutcomeMemory, so
  choosing reuses its utility 3 * p(progress) - 10 * p(damage) with the
  deterministic action-id tie break, exactly as preregistered.

The estimator is the existing RelationOutcomeMemory as coded (engineered
max-minus-min span statistic). Windows, margin, thresholds, and the span
statistic are all designer-supplied; this is choosing among / applying
already-supplied representations under a rule change (handoff level
2-3), not novel representation discovery, independent generalization,
or real-world safety. The learner issues ZERO training interventions:
all evidence arrives from the shared external actor stream.
"""
from __future__ import annotations

import json
import math

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)

SCHEMA = "developmental-ai.gated-archive-prequential-memory/v1"
ARCHIVE_SIZE = 192
WARMUP = 240
WINDOWS = (8, 32)
SCORING_TAIL = 8
DISPLACEMENT_MARGIN = 1.0
CONTRADICTION_WINDOW = 4
CONTRADICTION_MIN = 2
CONTRADICTION_P = 0.125
ADEQUACY_MEAN_THRESHOLD = -1.2
ADEQUACY_TOTAL_THRESHOLD = -9.6


class GatedArchivePrequentialMemory(FastShockMemory):
    """Immutable archive, margin-gated recent windows, adequacy abstention."""

    def __init__(self):
        super().__init__()
        self._cache = None

    def observe(self, event):
        super().observe(event)
        self._cache = None

    @staticmethod
    def _observed_likelihood(model, event):
        probs = model.estimate(event["features"])
        if event["progress"]:
            return probs["progress"]
        if event["damage"]:
            return probs["damage"]
        return 1.0 - probs["progress"] - probs["damage"]

    def selection(self):
        if self._cache is not None:
            return self._cache
        if len(self.events) < WARMUP:
            raise ValueError("insufficient public source outcomes")
        archive = self._model(self.events[:ARCHIVE_SIZE])
        scores = [0.0, 0.0, 0.0]
        archive_probs = []
        for i in range(len(self.events) - SCORING_TAIL, len(self.events)):
            event = self.events[i]
            fitted = [
                archive,
                self._model(self.events[i - WINDOWS[0]:i]),
                self._model(self.events[i - WINDOWS[1]:i]),
            ]
            ps = [self._observed_likelihood(m, event) for m in fitted]
            if any(not math.isfinite(p) or p <= 0 for p in ps):
                raise ValueError("bad prequential probabilities")
            for index, p in enumerate(ps):
                scores[index] += math.log(p)
            archive_probs.append(ps[0])
        contradictions = sum(
            int(p < CONTRADICTION_P)
            for p in archive_probs[-CONTRADICTION_WINDOW:]
        )
        override = contradictions >= CONTRADICTION_MIN
        if override:
            if scores[2] - scores[1] > DISPLACEMENT_MARGIN:
                selected = 2
                reason = "contradiction_override_recent32"
            else:
                selected = 1
                reason = "contradiction_override_recent8"
        else:
            recent8_qualifies = scores[1] - scores[0] > DISPLACEMENT_MARGIN
            recent32_qualifies = scores[2] - scores[0] > DISPLACEMENT_MARGIN
            if not recent8_qualifies and not recent32_qualifies:
                selected = 0
                reason = "archive_retained_margin_not_beaten"
            elif recent32_qualifies and (
                not recent8_qualifies
                or scores[2] - scores[1] > DISPLACEMENT_MARGIN
            ):
                selected = 2
                reason = "recent32_displaced_archive_by_margin"
            else:
                selected = 1
                reason = "recent8_displaced_archive_by_margin"
        names = ("archive", "recent8", "recent32")
        selected_mean = scores[selected] / SCORING_TAIL
        abstained = selected_mean < ADEQUACY_MEAN_THRESHOLD
        if abstained:
            reason = "adequacy_gate_abstain:" + reason
        live = (
            archive,
            self._model(self.events[-WINDOWS[0]:]),
            self._model(self.events[-WINDOWS[1]:]),
        )
        decision = {
            "source": names[selected],
            "selection": "abstained-by-gate" if abstained else names[selected],
            "abstained": abstained,
            "reason": reason,
            "prequential_scores": [round(v, 6) for v in scores],
            "prequential_scoring_events": SCORING_TAIL,
            "predictor_training_overlap": 0,
            "archive_contradictions_latest4": contradictions,
            "contradiction_override": override,
            "selected_mean_prequential_log_score": round(selected_mean, 6),
            "adequacy_mean_threshold": ADEQUACY_MEAN_THRESHOLD,
            "displacement_margin": DISPLACEMENT_MARGIN,
            "recorded_events": len(self.events),
            "archive_retained": True,
            "archive_events": ARCHIVE_SIZE,
            "learner_training_actions": 0,
        }
        self._cache = (decision, live[selected])
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
            raise ValueError("untrained gated archive memory")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid gated archive checkpoint hash")
        state = record["state"]
        if (set(state) != {"schema", "events"} or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid gated archive checkpoint structure")
        m = cls()
        for event in state["events"]:
            m.observe(event)
        if m.record() != record:
            raise ValueError("gated archive checkpoint replay mismatch")
        return m
