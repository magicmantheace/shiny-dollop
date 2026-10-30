"""Joint concordance recovery: less-sparse signal-gated archive recovery.

Frozen protocol: benchmarks/joint_concordance_recovery_protocol.json
(experiment joint_concordance_recovery, frozen 2026-10-30 BEFORE
this implementation). The candidate is a separate optional learner;
the default controller and every existing learner are untouched, and
the graded EvidenceOppositionGuardMemory and the graded
EvidenceOppositionRecoveryMemory are baselines only, not modified.

Mechanism, exactly as preregistered. IDENTICAL to the graded
EvidenceOppositionRecoveryMemory in every element except the single
changed recovery test:
- Acting model: a RelationOutcomeMemory fitted on the LAST 8 observed
  public events only - identically the recent8 baseline.
- Immediate signal: IDENTICAL to the graded evidence-opposition guard,
  reused unchanged and not re-tuned. Newest window = last 2 observed
  events; reference window = the 24 events immediately preceding the
  newest window (indices N-26 .. N-3). For each newest event, the
  reference expectation is the strictly-highest reported outcome class
  among reference events of equal span (the existing engineered
  max-minus-min statistic); a tie or empty set gives expectation None.
  An event is matched if expectation and reported class are both
  progress or damage, and opposed if matched and different.
  opposed_count is in 0..2. No fitted probabilities anywhere.
- Retained-archive concordance test: IDENTICAL per-event definition
  to the graded retained-recovery candidate. The retained archive is
  every observed event BEFORE the reference window (indices
  0 .. N-27, i.e. events[:N-26]); it is not a snapshot and is not
  phase-segmented. For each newest event, the archive expectation is
  the strictly-highest reported outcome class among ALL archive
  events of equal span (tie or empty gives None). An event is
  archive-matched if expectation and reported class are both
  progress or damage, and archive-concordant if archive-matched and
  its reported class EQUALS the expectation. concordant_count and
  archive_matched_count are in 0..2. Raw integer counts only.
- Joint concordance test (NEW, the single changed element): for each
  newest-window event e, e is JOINT if it is archive-CONCORDANT (per
  the unchanged archive test) AND reference-OPPOSED (per the unchanged
  immediate signal) - both flags on the SAME event. joint_count is
  the number of joint newest events (0..2). No other combination of
  the pooled counts enters the recovery branch: concordant_count >= 1
  pooled with opposed_count >= 1 on DIFFERENT events does NOT trigger
  recovery, and the preceding candidate's concordant_count == 2 AND
  opposed_count >= 1 rule is not retained as an alternative trigger.
- Decision rule, evaluated in this exact order once evaluable:
  (1) RECOVERY - if joint_count >= 1, act through a
      RelationOutcomeMemory fitted on the archive events only
      (events[:N-26]); the recovery model never includes the
      reference window or the newest window (source retained_archive).
  (2) ABSTENTION - else if opposed_count == 2, abstain (choose
      returns None), exactly the graded guard's protective response.
  (3) RECENT8 - otherwise act through the acting model exactly.
  There is no other input: no stage, phase, rule, or switch
  information, and no fitted probability enters any branch.
- Minimum events: both signals together require 2 + 24 + at least 1
  archive event = 27 observed events. Below 27 events neither signal
  is evaluable and the learner acts with a RelationOutcomeMemory
  fitted on all available events (branch
  all_available_below_minimum). Every benchmark checkpoint in this
  experiment has at least 240 observed events, so that fallback is
  never exercised during evaluation.
- Action scoring: whichever model the decision rule selects, the
  choice is that model's RelationOutcomeMemory.choose output
  (utility 3 * p(progress) - 10 * p(damage), deterministic action-id
  tie break). An abstention is scored as a failed task, never as a
  success, and is reported separately.

The windows, span statistic, archive definition, joint test, and
decision rule are all designer-supplied; this is choosing among /
applying already-supplied representations under a rule change
(handoff level 2-3), not novel representation discovery, general
regime identification (the archive is global and unsegmented; B2
recovery is pre-registered as NOT expected), calibrated uncertainty,
or real-world safety. The learner issues ZERO training interventions:
all evidence arrives from the shared external actor stream.
"""
from __future__ import annotations

import json

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)
from developmental_ai.relation_outcome_memory import span

SCHEMA = "developmental-ai.joint-concordance-recovery-memory/v1"
ACTING_WINDOW = 8
NEWEST_WINDOW = 2
REFERENCE_WINDOW = 24
MINIMUM_EVENTS = 27
GATE_OPPOSED_COUNT = 2
RECOVERY_JOINT_COUNT = 1


def _reported_class(event):
    if event["progress"]:
        return "progress"
    if event["damage"]:
        return "damage"
    return "neutral"


def _majority(rows, event_span):
    """Strictly-highest reported class among rows of equal span.

    Returns (count_for_span, majority_or_None). Raw counts only.
    """
    counts = {"progress": 0, "damage": 0, "neutral": 0}
    total = 0
    for row in rows:
        if span(row["features"]) == event_span:
            total += 1
            counts[_reported_class(row)] += 1
    majority = None
    if total:
        top = max(counts.values())
        leaders = [name for name, n in counts.items() if n == top]
        if len(leaders) == 1:
            majority = leaders[0]
    return total, majority


class JointConcordanceRecoveryMemory(FastShockMemory):
    """recent8 + evidence-opposition signal + joint-concordance recovery."""

    def __init__(self):
        super().__init__()
        self._cache = None

    def observe(self, event):
        super().observe(event)
        self._cache = None

    def _records(self):
        """Immediate signal, archive concordance, and joint records.

        Caller guarantees at least MINIMUM_EVENTS observed events.
        """
        newest = self.events[-NEWEST_WINDOW:]
        reference = self.events[-(NEWEST_WINDOW + REFERENCE_WINDOW):
                                -NEWEST_WINDOW]
        archive = self.events[:-(NEWEST_WINDOW + REFERENCE_WINDOW)]
        signal_records = []
        archive_records = []
        joint_records = []
        for event in newest:
            event_span = span(event["features"])
            reported = _reported_class(event)
            reference_count, reference_majority = _majority(
                reference, event_span)
            matched = (reference_majority in ("progress", "damage")
                       and reported in ("progress", "damage"))
            opposed = bool(matched and reported != reference_majority)
            signal_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": reference_majority,
                "matched": bool(matched),
                "opposed": opposed,
            })
            archive_count, archive_majority = _majority(
                archive, event_span)
            archive_matched = (archive_majority in ("progress", "damage")
                               and reported in ("progress", "damage"))
            archive_concordant = bool(
                archive_matched and reported == archive_majority)
            archive_records.append({
                "span": event_span,
                "reported_class": reported,
                "archive_count": archive_count,
                "archive_majority": archive_majority,
                "archive_matched": bool(archive_matched),
                "archive_concordant": archive_concordant,
            })
            joint = bool(archive_concordant and opposed)
            joint_records.append({
                "span": event_span,
                "reported_class": reported,
                "archive_concordant": archive_concordant,
                "opposed": opposed,
                "joint": joint,
            })
        return signal_records, archive_records, joint_records, archive

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
                "branch": "all_available_below_minimum",
                "abstained": False,
                "recovery_fired": False,
                "gate_fired": False,
                "gate_evaluable": False,
                "reason": "signals_not_evaluable_below_minimum_events",
                "signal_events": [],
                "archive_events": [],
                "joint_events": [],
                "joint_flags": [],
                "opposed_count": 0,
                "matched_count": 0,
                "concordant_count": 0,
                "archive_matched_count": 0,
                "joint_count": 0,
                "gate_opposed_threshold": GATE_OPPOSED_COUNT,
                "recovery_joint_threshold": RECOVERY_JOINT_COUNT,
                "acting_window": ACTING_WINDOW,
                "newest_window_events": NEWEST_WINDOW,
                "reference_window_events": REFERENCE_WINDOW,
                "archive_events_count": 0,
                "recorded_events": len(self.events),
                "learner_training_actions": 0,
            }
            self._cache = (decision, model)
            return self._cache
        signal_records, archive_records, joint_records, archive = \
            self._records()
        opposed_count = sum(int(r["opposed"]) for r in signal_records)
        matched_count = sum(int(r["matched"]) for r in signal_records)
        concordant_count = sum(
            int(r["archive_concordant"]) for r in archive_records)
        archive_matched_count = sum(
            int(r["archive_matched"]) for r in archive_records)
        joint_flags = [bool(r["joint"]) for r in joint_records]
        joint_count = sum(int(f) for f in joint_flags)
        recovery_fired = joint_count >= RECOVERY_JOINT_COUNT
        abstained = (not recovery_fired
                     and opposed_count == GATE_OPPOSED_COUNT)
        if recovery_fired:
            branch = "retained_archive"
            model = self._model(archive)
            reason = "joint_concordance_recovery"
        elif abstained:
            branch = "abstained"
            model = self._model(self.events[-ACTING_WINDOW:])
            reason = "evidence_opposition_gate_abstain"
        else:
            branch = "recent8"
            model = self._model(self.events[-ACTING_WINDOW:])
            reason = "evidence_opposition_gate_pass"
        decision = {
            "source": branch,
            "selection": branch,
            "branch": branch,
            "abstained": abstained,
            "recovery_fired": recovery_fired,
            "gate_fired": abstained,
            "gate_evaluable": True,
            "reason": reason,
            "signal_events": signal_records,
            "archive_events": archive_records,
            "joint_events": joint_records,
            "joint_flags": joint_flags,
            "opposed_count": opposed_count,
            "matched_count": matched_count,
            "concordant_count": concordant_count,
            "archive_matched_count": archive_matched_count,
            "joint_count": joint_count,
            "gate_opposed_threshold": GATE_OPPOSED_COUNT,
            "recovery_joint_threshold": RECOVERY_JOINT_COUNT,
            "acting_window": ACTING_WINDOW,
            "newest_window_events": NEWEST_WINDOW,
            "reference_window_events": REFERENCE_WINDOW,
            "archive_events_count": len(archive),
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
            raise ValueError("untrained joint concordance recovery memory")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError("invalid joint concordance recovery checkpoint hash")
        state = record["state"]
        if (set(state) != {"schema", "events"} or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError("invalid joint concordance recovery checkpoint structure")
        m = cls()
        for event in state["events"]:
            m.observe(event)
        if m.record() != record:
            raise ValueError("joint concordance recovery checkpoint replay mismatch")
        return m
