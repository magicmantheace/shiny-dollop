"""Bounded-authority joint recovery: joint recovery with expiry.

Frozen protocol: benchmarks/bounded_authority_joint_recovery_protocol.json
(experiment bounded_authority_joint_recovery, frozen 2026-10-30 BEFORE
this implementation). The candidate is a separate optional learner;
the default controller and every existing learner are untouched, and
the graded EvidenceOppositionGuardMemory, the graded
EvidenceOppositionRecoveryMemory, and the graded
JointConcordanceRecoveryMemory are baselines only, not modified.

Mechanism, exactly as preregistered. IDENTICAL to the graded
JointConcordanceRecoveryMemory in every element except the single
changed element, branch AUTHORITY (expiry):
- Acting model: a RelationOutcomeMemory fitted on the LAST 8 observed
  public events only - identically the recent8 baseline.
- Immediate signal: IDENTICAL to the graded evidence-opposition guard.
  Newest window = last 2 observed events; reference window = the 24
  events immediately preceding the newest window (indices N-26..N-3).
  For each newest event, the reference expectation is the
  strictly-highest reported outcome class among reference events of
  equal span (tie or empty gives None). An event is matched if
  expectation and reported class are both progress or damage, and
  opposed if matched and different. opposed_count is in 0..2. No
  fitted probabilities anywhere.
- Retained archive: every observed event BEFORE the reference window
  (events[:N-26]); not a snapshot, not phase-segmented.
- Archive concordance: IDENTICAL per-event definition to the graded
  candidates. For each newest event, the archive expectation is the
  strictly-highest reported class among ALL archive events of equal
  span; archive-matched if expectation and reported class are both
  progress or damage; archive-concordant if matched and equal.
  concordant_count and archive_matched_count are in 0..2.
- Joint test: IDENTICAL to the graded joint candidate. A newest event
  is JOINT if it is archive-CONCORDANT and reference-OPPOSED on the
  SAME event. joint_count is in 0..2.
- Expiry condition (NEW, the single changed element), computed from
  observed reported events only, no phase/checkpoint/elapsed input:
  (A) Local-archive disagreement. Local window = last 26 events.
      For each distinct span s in the local window, compare the
      local span-majority vs the archive span-majority (same
      strictly-highest machinery; tie/empty gives None). Span s is
      comparable iff both majorities are progress or damage, and
      disagreeing iff comparable and the majorities differ. Let
      C = comparable_span_count and D = disagreeing_span_count.
      stable_disagreement is set iff C >= 1 AND D * 2 > C.
  (B) Acting-window archive concordance. For each of the last 8
      events, counted archive-concordant iff archive-matched and
      its reported class equals archive_majority(span(event)),
      using the SAME current archive. recent_concordant_count
      is in 0..8.
  Branch authority: ABSTENTION is armed iff stable_disagreement is
  NOT set. RECOVERY is armed iff stable_disagreement is NOT set OR
  recent_concordant_count >= 2. A disarmed branch that would have
  fired is recorded (recovery_would_fire / abstention_would_fire)
  and falls through to the next branch.
- Decision rule, evaluated in this exact order once evaluable:
  (1) RECOVERY - if joint_count >= 1 AND recovery is armed, act
      through a RelationOutcomeMemory fitted on the archive events
      only (source retained_archive).
  (2) ABSTENTION - else if opposed_count == 2 AND abstention is
      armed, abstain (choose returns None).
  (3) RECENT8 - otherwise act through the acting model exactly.
- Minimum events: 27 (2 newest + 24 reference + at least 1 archive).
  Below 27 neither signal is evaluable and the learner acts with a
  RelationOutcomeMemory fitted on all available events (branch
  all_available_below_minimum). Every benchmark checkpoint has at
  least 240 observed events, so that fallback is never exercised
  during evaluation.
- Action scoring: whichever model is selected, the choice is that
  model's RelationOutcomeMemory.choose output. An abstention is
  scored as a failed task, never as a success.

The windows, span statistic, archive definition, joint test, expiry
condition, and decision rule are all designer-supplied; this is
choosing among / applying already-supplied representations under a
rule change (handoff level 2-3), not novel representation discovery,
general regime identification, calibrated uncertainty, or real-world
safety. The learner issues ZERO training interventions.
"""
from __future__ import annotations

import json

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)
from developmental_ai.relation_outcome_memory import span

SCHEMA = "developmental-ai.bounded-authority-joint-recovery-memory/v1"
ACTING_WINDOW = 8
NEWEST_WINDOW = 2
REFERENCE_WINDOW = 24
LOCAL_WINDOW = 26
MINIMUM_EVENTS = 27
GATE_OPPOSED_COUNT = 2
RECOVERY_JOINT_COUNT = 1
RECENT_CONCORDANT_THRESHOLD = 2


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


class BoundedAuthorityJointRecoveryMemory(FastShockMemory):
    """recent8 + joint recovery/abstention with evidence expiry."""

    def __init__(self):
        super().__init__()
        self._cache = None

    def observe(self, event):
        super().observe(event)
        self._cache = None

    def _records(self):
        """Signal, archive, joint, and expiry records.

        Caller guarantees at least MINIMUM_EVENTS observed events.
        """
        newest = self.events[-NEWEST_WINDOW:]
        reference = self.events[-(NEWEST_WINDOW + REFERENCE_WINDOW):
                                -NEWEST_WINDOW]
        archive = self.events[:-(NEWEST_WINDOW + REFERENCE_WINDOW)]
        local = self.events[-LOCAL_WINDOW:]
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
        # (A) Local-archive disagreement, per distinct local span.
        expiry_span_records = []
        for local_span in sorted({span(e["features"]) for e in local}):
            local_count, local_majority = _majority(local, local_span)
            archive_count, archive_majority = _majority(
                archive, local_span)
            comparable = (local_majority in ("progress", "damage")
                          and archive_majority in ("progress", "damage"))
            disagreeing = bool(comparable
                               and local_majority != archive_majority)
            expiry_span_records.append({
                "span": local_span,
                "local_count": local_count,
                "local_majority": local_majority,
                "archive_count": archive_count,
                "archive_majority": archive_majority,
                "comparable": bool(comparable),
                "disagreeing": disagreeing,
            })
        comparable_span_count = sum(
            int(r["comparable"]) for r in expiry_span_records)
        disagreeing_span_count = sum(
            int(r["disagreeing"]) for r in expiry_span_records)
        stable_disagreement = bool(
            comparable_span_count >= 1
            and disagreeing_span_count * 2 > comparable_span_count)
        # (B) Acting-window archive concordance, vs the current archive.
        recent_records = []
        for event in self.events[-ACTING_WINDOW:]:
            event_span = span(event["features"])
            reported = _reported_class(event)
            archive_count, archive_majority = _majority(
                archive, event_span)
            archive_matched = (archive_majority in ("progress", "damage")
                               and reported in ("progress", "damage"))
            archive_concordant = bool(
                archive_matched and reported == archive_majority)
            recent_records.append({
                "span": event_span,
                "reported_class": reported,
                "archive_count": archive_count,
                "archive_majority": archive_majority,
                "archive_matched": bool(archive_matched),
                "archive_concordant": archive_concordant,
            })
        recent_concordant_count = sum(
            int(r["archive_concordant"]) for r in recent_records)
        return (signal_records, archive_records, joint_records, archive,
                expiry_span_records, comparable_span_count,
                disagreeing_span_count, stable_disagreement,
                recent_records, recent_concordant_count)

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
                "expiry_spans": [],
                "comparable_span_count": 0,
                "disagreeing_span_count": 0,
                "stable_disagreement": False,
                "recent_events": [],
                "recent_concordant_count": 0,
                "recovery_armed": False,
                "abstention_armed": False,
                "recovery_would_fire": False,
                "abstention_would_fire": False,
                "gate_opposed_threshold": GATE_OPPOSED_COUNT,
                "recovery_joint_threshold": RECOVERY_JOINT_COUNT,
                "recent_concordant_threshold": RECENT_CONCORDANT_THRESHOLD,
                "acting_window": ACTING_WINDOW,
                "newest_window_events": NEWEST_WINDOW,
                "reference_window_events": REFERENCE_WINDOW,
                "local_window_events": LOCAL_WINDOW,
                "archive_events_count": 0,
                "recorded_events": len(self.events),
                "learner_training_actions": 0,
            }
            self._cache = (decision, model)
            return self._cache
        (signal_records, archive_records, joint_records, archive,
         expiry_span_records, comparable_span_count,
         disagreeing_span_count, stable_disagreement,
         recent_records, recent_concordant_count) = self._records()
        opposed_count = sum(int(r["opposed"]) for r in signal_records)
        matched_count = sum(int(r["matched"]) for r in signal_records)
        concordant_count = sum(
            int(r["archive_concordant"]) for r in archive_records)
        archive_matched_count = sum(
            int(r["archive_matched"]) for r in archive_records)
        joint_flags = [bool(r["joint"]) for r in joint_records]
        joint_count = sum(int(f) for f in joint_flags)
        recovery_armed = bool(
            (not stable_disagreement)
            or recent_concordant_count >= RECENT_CONCORDANT_THRESHOLD)
        abstention_armed = bool(not stable_disagreement)
        recovery_would_fire = joint_count >= RECOVERY_JOINT_COUNT
        abstention_would_fire = opposed_count == GATE_OPPOSED_COUNT
        recovery_fired = bool(recovery_would_fire and recovery_armed)
        abstained = bool((not recovery_fired) and abstention_would_fire
                         and abstention_armed)
        if recovery_fired:
            branch = "retained_archive"
            model = self._model(archive)
            reason = "joint_concordance_recovery_armed"
        elif abstained:
            branch = "abstained"
            model = self._model(self.events[-ACTING_WINDOW:])
            reason = "evidence_opposition_gate_abstain_armed"
        else:
            branch = "recent8"
            model = self._model(self.events[-ACTING_WINDOW:])
            if recovery_would_fire and not recovery_armed:
                reason = "recovery_disarmed_by_expiry"
            elif abstention_would_fire and not abstention_armed:
                reason = "abstention_disarmed_by_expiry"
            else:
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
            "expiry_spans": expiry_span_records,
            "comparable_span_count": comparable_span_count,
            "disagreeing_span_count": disagreeing_span_count,
            "stable_disagreement": stable_disagreement,
            "recent_events": recent_records,
            "recent_concordant_count": recent_concordant_count,
            "recovery_armed": recovery_armed,
            "abstention_armed": abstention_armed,
            "recovery_would_fire": recovery_would_fire,
            "abstention_would_fire": abstention_would_fire,
            "gate_opposed_threshold": GATE_OPPOSED_COUNT,
            "recovery_joint_threshold": RECOVERY_JOINT_COUNT,
            "recent_concordant_threshold": RECENT_CONCORDANT_THRESHOLD,
            "acting_window": ACTING_WINDOW,
            "newest_window_events": NEWEST_WINDOW,
            "reference_window_events": REFERENCE_WINDOW,
            "local_window_events": LOCAL_WINDOW,
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
            raise ValueError(
                "untrained bounded authority joint recovery memory")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError(
                "invalid bounded authority joint recovery checkpoint hash")
        state = record["state"]
        if (set(state) != {"schema", "events"} or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError(
                "invalid bounded authority joint recovery checkpoint structure")
        m = cls()
        for event in state["events"]:
            m.observe(event)
        if m.record() != record:
            raise ValueError(
                "bounded authority joint recovery checkpoint replay mismatch")
        return m
