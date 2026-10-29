"""Evidence-opposition onset guard: recent8 acting model plus evidence-count gate.

Frozen protocol: benchmarks/evidence_opposition_onset_guard_protocol.json
(experiment evidence_opposition_onset_guard, frozen 2026-10-28 BEFORE
this implementation). The candidate is a separate optional learner;
the default controller and every existing learner are untouched.

Mechanism, exactly as preregistered:
- Acting model: a RelationOutcomeMemory fitted on the LAST 8 observed
  public events only - identically the recent8 baseline. The candidate
  adds no model selection, no archive, and no displacement margin:
  the gate below is the only difference from recent8.
- Signal (NO fitted probabilities anywhere): the newest window is the
  last 2 observed events; the reference window is the 24 events
  immediately preceding the newest window (indices N-26 .. N-3). For
  each newest event e, ref(e) is the reference-window events whose
  span (the existing engineered max-minus-min statistic over the
  event's two public features, exactly as in RelationOutcomeMemory)
  equals span(e). The reference expectation is the reported outcome
  class (progress / damage / neutral) with the strictly highest count
  among ref(e); a tie for highest, or an empty ref(e), gives
  expectation None. e is MATCHED if its expectation is progress or
  damage AND e's own reported class is progress or damage. e is
  OPPOSED if it is matched and its reported class differs from the
  expectation. Neutral expectations and neutral newest events are
  never matched and never opposed.
- Gate: the gate fires and the learner abstains from the TEST action
  (choose returns None) if and only if opposed_count == 2 (both
  newest-window events opposed). An abstention is a failed task,
  never a success. There is no other gate input: no stage, phase, or
  switch information, and no fitted probability.
- Minimum events: the signal requires 2 + 24 = 26 observed events.
  Below 26 events the gate is not evaluable and the learner acts with
  a RelationOutcomeMemory fitted on all available events. Every
  benchmark checkpoint in this experiment has at least 240 observed
  events, so that fallback is never exercised during evaluation.
- Action scoring: when the gate does not fire, the choice is exactly
  the acting model's choice (RelationOutcomeMemory utility
  3 * p(progress) - 10 * p(damage), deterministic action-id tie
  break, via RelationOutcomeMemory.choose).

The windows, span statistic, and gate rule are all designer-supplied;
this is choosing among / applying already-supplied representations
under a rule change plus a designer-supplied abstention rule (handoff
level 2-3), not novel representation discovery, independent
generalization, or real-world safety. The learner issues ZERO
training interventions: all evidence arrives from the shared
external actor stream.
"""
from __future__ import annotations

import json

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)
from developmental_ai.relation_outcome_memory import span

SCHEMA = "developmental-ai.evidence-opposition-guard-memory/v1"
ACTING_WINDOW = 8
NEWEST_WINDOW = 2
REFERENCE_WINDOW = 24
MINIMUM_EVENTS = 26
GATE_OPPOSED_COUNT = 2


def _reported_class(event):
    if event["progress"]:
        return "progress"
    if event["damage"]:
        return "damage"
    return "neutral"


class EvidenceOppositionGuardMemory(FastShockMemory):
    """recent8 acting model guarded by a raw evidence-opposition gate."""

    def __init__(self):
        super().__init__()
        self._cache = None

    def observe(self, event):
        super().observe(event)
        self._cache = None

    def _signal_record(self):
        """Per-newest-event signal records plus pooled counts.

        Caller guarantees at least MINIMUM_EVENTS observed events.
        Counts are raw integer counts of observed events only; no
        probability is fitted, smoothed, or thresholded here.
        """
        newest = self.events[-NEWEST_WINDOW:]
        reference = self.events[-(NEWEST_WINDOW + REFERENCE_WINDOW):
                                -NEWEST_WINDOW]
        records = []
        for event in newest:
            event_span = span(event["features"])
            counts = {"progress": 0, "damage": 0, "neutral": 0}
            reference_count = 0
            for ref_event in reference:
                if span(ref_event["features"]) == event_span:
                    reference_count += 1
                    counts[_reported_class(ref_event)] += 1
            majority = None
            if reference_count:
                top = max(counts.values())
                leaders = [name for name, n in counts.items() if n == top]
                if len(leaders) == 1:
                    majority = leaders[0]
            reported = _reported_class(event)
            matched = (majority in ("progress", "damage")
                       and reported in ("progress", "damage"))
            opposed = bool(matched and reported != majority)
            records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": majority,
                "matched": bool(matched),
                "opposed": opposed,
            })
        return records

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
                "gate_fired": False,
                "gate_evaluable": False,
                "reason": "gate_not_evaluable_below_minimum_events",
                "signal_events": [],
                "opposed_count": 0,
                "matched_count": 0,
                "gate_opposed_threshold": GATE_OPPOSED_COUNT,
                "acting_window": ACTING_WINDOW,
                "newest_window_events": NEWEST_WINDOW,
                "reference_window_events": REFERENCE_WINDOW,
                "recorded_events": len(self.events),
                "learner_training_actions": 0,
            }
            self._cache = (decision, model)
            return self._cache
        records = self._signal_record()
        opposed_count = sum(int(r["opposed"]) for r in records)
        matched_count = sum(int(r["matched"]) for r in records)
        abstained = opposed_count == GATE_OPPOSED_COUNT
        model = self._model(self.events[-ACTING_WINDOW:])
        decision = {
            "source": "recent8",
            "selection": "abstained-by-gate" if abstained else "recent8",
            "abstained": abstained,
            "gate_fired": abstained,
            "gate_evaluable": True,
            "reason": ("evidence_opposition_gate_abstain" if abstained
                       else "evidence_opposition_gate_pass"),
            "signal_events": records,
            "opposed_count": opposed_count,
            "matched_count": matched_count,
            "gate_opposed_threshold": GATE_OPPOSED_COUNT,
            "acting_window": ACTING_WINDOW,
            "newest_window_events": NEWEST_WINDOW,
            "reference_window_events": REFERENCE_WINDOW,
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
            raise ValueError("untrained evidence-opposition guard memory")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid evidence-opposition guard checkpoint hash")
        state = record["state"]
        if (set(state) != {"schema", "events"} or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid evidence-opposition guard checkpoint structure")
        m = cls()
        for event in state["events"]:
            m.observe(event)
        if m.record() != record:
            raise ValueError("evidence-opposition guard checkpoint replay mismatch")
        return m
