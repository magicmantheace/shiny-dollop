"""Minority-archive joint recovery: B2 protection via retained discordant evidence.

Frozen protocol: benchmarks/minority_archive_joint_recovery_protocol.json
(experiment minority_archive_joint_recovery, frozen 2026-11-01 BEFORE
this implementation). The candidate is a separate optional learner;
the default controller and every existing learner are untouched, and
the graded EvidenceOppositionGuardMemory, the graded
EvidenceOppositionRecoveryMemory, the graded
JointConcordanceRecoveryMemory, the graded
BoundedAuthorityJointRecoveryMemory, the graded
LongDisagreementJointRecoveryMemory, and the graded
ExtendedReferenceJointRecoveryMemory are baselines only, not modified.

Mechanism, exactly as preregistered. IDENTICAL to the graded
LongDisagreementJointRecoveryMemory in every element except the
single changed element, the immediate signal's REFERENCE WINDOW:
- Acting model: a RelationOutcomeMemory fitted on the LAST 8 observed
  public events only - identically the recent8 baseline.
- Immediate signal (SINGLE CHANGED ELEMENT): newest window = last 2
  observed events; the span-majority expectation for each newest
  event is computed over the 50 events immediately preceding the
  newest window (indices N-52..N-3) instead of the 24 events
  preceding it (N-26..N-3). Majority rule, matched/opposed
  definitions, and opposed_count in 0..2 are carried over unchanged.
  No fitted probabilities anywhere.
- Legacy reference-24 signal (RECORDS-ONLY): the graded long
  candidate's signal, computed over the 24 events preceding the
  newest window, is recorded in full (legacy signal records, legacy
  opposed/matched counts, per-event legacy joint flags and legacy
  joint_count) and is NEVER a decision input, so the graded long
  candidate's rule is derivable from the records alone.
- Retained archive: IDENTICAL to the graded candidates - every
  observed event BEFORE the original reference partition,
  events[:N-26] (events[:-(2+24)]); it is NOT redefined by the
  reference widening, and the extended reference overlaps its last
  24 events, as stated in the protocol. Not a snapshot, not
  phase-segmented.
- Archive concordance: IDENTICAL per-event definition to the graded
  candidates (archive span-majority; matched/concordant in 0..2).
- Joint test: IDENTICAL in form - a newest event is JOINT if it is
  archive-CONCORDANT and reference-OPPOSED on the SAME event, with
  the opposed flag now computed against the 50-event reference.
  joint_count is in 0..2.
- Authority condition: IDENTICAL to the graded long candidate,
  unchanged and not re-tuned - (A) local-archive disagreement
  (local window last 26, stable_disagreement iff C >= 1 and
  D * 2 > C), (B) acting-window archive concordance
  (recent_concordant_count among the last 8), (C) preceding-window
  archive disagreement (preceding window the 26 events before the
  local window, same strict-majority rule; long_disagreement iff
  both stable flags set). ABSTENTION armed iff NOT
  stable_disagreement; RECOVERY armed iff NOT stable_disagreement
  OR recent_concordant_count >= 2 OR long_disagreement. The
  recovery_arming_leg reporting precedence (no_stable_disagreement,
  then long, then corroboration) is carried over exactly. The
  reference widening does NOT enter the authority condition.
- Decision rule, in exact order once evaluable: (1) RECOVERY - if
  joint_count >= 1 AND recovery armed, act through a
  RelationOutcomeMemory fitted on the archive events only (source
  retained_archive). (2) ABSTENTION - else if opposed_count == 2
  AND abstention armed, abstain. (3) RECENT8 - otherwise act
  through the acting model exactly. Disarmed would-be firings are
  recorded (recovery_would_fire / abstention_would_fire).
- Minimum events: 52 (2 newest + 50 extended reference). Below 52
  the extended signal is not evaluable and the learner acts with a
  RelationOutcomeMemory fitted on all available events (branch
  all_available_below_minimum); the legacy records are likewise not
  evaluable below 52 under this protocol. The authority preceding
  window is partial below 52 events exactly as in the graded long
  candidate. Every benchmark checkpoint has at least 240 observed
  events, so the fallback is never exercised during evaluation.
- Action scoring: whichever model is selected, the choice is that
  model's RelationOutcomeMemory.choose output. An abstention is
  scored as a failed task, never as a success.

- Minority archive (SINGLE NEW ELEMENT): the retained archive's
  own events that are archive-matched and DISCORDANT with the
  archive's per-span majorities form the minority set.
  minority_fraction = discordant / archive-matched non-neutral
  archive events. The minority branch is ARMED iff
  minority_fraction >= 0.25 AND minority_discordant_count >= 8.
  A newest event is MINORITY-JOINT iff it is minority-concordant
  (equals the minority set's per-span majority) AND
  reference-opposed (extended 50-event reference) on the SAME
  event. Decision order: (1) regular RECOVERY, (2) MINORITY
  RECOVERY - if minority_joint_count >= 1 AND minority armed, act
  through a RelationOutcomeMemory fitted on the minority set only
  (source minority_archive), (3) ABSTENTION, (4) RECENT8. The
  carried-over authority condition neither arms nor disarms the
  minority branch, and the minority fraction neither arms nor
  disarms recovery or abstention.

The windows, span statistic, archive definition, joint test,
authority condition, and decision rule are all designer-supplied;
this is choosing among / applying already-supplied representations
under a rule change (handoff level 2-3), not novel representation
discovery, general regime identification, calibrated uncertainty,
or real-world safety. The learner issues ZERO training interventions.
"""
from __future__ import annotations

import json

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)
from developmental_ai.relation_outcome_memory import span

SCHEMA = "developmental-ai.minority-archive-joint-recovery-memory/v1"
ACTING_WINDOW = 8
NEWEST_WINDOW = 2
REFERENCE_WINDOW = 50
LEGACY_REFERENCE_WINDOW = 24
ARCHIVE_PARTITION = NEWEST_WINDOW + LEGACY_REFERENCE_WINDOW
LOCAL_WINDOW = 26
PRECEDING_WINDOW = 26
MINIMUM_EVENTS = 52
GATE_OPPOSED_COUNT = 2
RECOVERY_JOINT_COUNT = 1
RECENT_CONCORDANT_THRESHOLD = 2
MINORITY_FRACTION_THRESHOLD = 0.25
MINORITY_DISCORDANT_MINIMUM = 8
MINORITY_JOINT_THRESHOLD = 1


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


class MinorityArchiveJointRecoveryMemory(FastShockMemory):
    """Extended-reference joint recovery + minority-archive branch."""

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
        legacy_reference = self.events[
            -(NEWEST_WINDOW + LEGACY_REFERENCE_WINDOW):-NEWEST_WINDOW]
        archive = self.events[:-(NEWEST_WINDOW + LEGACY_REFERENCE_WINDOW)]
        local = self.events[-LOCAL_WINDOW:]
        n_events = len(self.events)
        preceding = self.events[max(0, n_events - LOCAL_WINDOW
                                    - PRECEDING_WINDOW):
                                n_events - LOCAL_WINDOW]
        signal_records = []
        legacy_signal_records = []
        archive_records = []
        joint_records = []
        legacy_joint_records = []
        minority_records = []
        minority_joint_records = []
        # Minority set: archive events discordant with the archive's
        # own per-span majorities (archive-matched and differing).
        _archive_majority_by_span = {}
        for _e in archive:
            _sp = span(_e["features"])
            if _sp not in _archive_majority_by_span:
                _archive_majority_by_span[_sp] = _majority(archive, _sp)[1]
        minority_set = []
        minority_archive_matched_count = 0
        for _e in archive:
            _maj = _archive_majority_by_span[span(_e["features"])]
            _rep = _reported_class(_e)
            if _maj in ("progress", "damage") and _rep in ("progress", "damage"):
                minority_archive_matched_count += 1
                if _rep != _maj:
                    minority_set.append(_e)
        minority_discordant_count = len(minority_set)
        minority_fraction = (
            minority_discordant_count / minority_archive_matched_count
            if minority_archive_matched_count else 0.0)
        minority_armed = bool(
            minority_fraction >= MINORITY_FRACTION_THRESHOLD
            and minority_discordant_count >= MINORITY_DISCORDANT_MINIMUM)
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
            legacy_count, legacy_majority = _majority(
                legacy_reference, event_span)
            legacy_matched = (legacy_majority in ("progress", "damage")
                              and reported in ("progress", "damage"))
            legacy_opposed = bool(
                legacy_matched and reported != legacy_majority)
            legacy_signal_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": legacy_count,
                "reference_majority": legacy_majority,
                "matched": bool(legacy_matched),
                "opposed": legacy_opposed,
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
            legacy_joint = bool(archive_concordant and legacy_opposed)
            legacy_joint_records.append({
                "span": event_span,
                "reported_class": reported,
                "archive_concordant": archive_concordant,
                "opposed": legacy_opposed,
                "joint": legacy_joint,
            })
            minority_count_span, minority_majority = _majority(
                minority_set, event_span)
            minority_matched = (
                minority_majority in ("progress", "damage")
                and reported in ("progress", "damage"))
            minority_concordant = bool(
                minority_matched and reported == minority_majority)
            minority_records.append({
                "span": event_span,
                "reported_class": reported,
                "minority_count": minority_count_span,
                "minority_majority": minority_majority,
                "minority_matched": bool(minority_matched),
                "minority_concordant": minority_concordant,
            })
            minority_joint = bool(minority_concordant and opposed)
            minority_joint_records.append({
                "span": event_span,
                "reported_class": reported,
                "minority_concordant": minority_concordant,
                "opposed": opposed,
                "minority_joint": minority_joint,
                "joint": minority_joint,
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
        # (C) Preceding-window archive disagreement, per distinct
        # preceding span, against the SAME archive as (A).
        preceding_span_records = []
        for preceding_span in sorted({span(e["features"])
                                      for e in preceding}):
            preceding_count, preceding_majority = _majority(
                preceding, preceding_span)
            archive_count, archive_majority = _majority(
                archive, preceding_span)
            preceding_comparable = (
                preceding_majority in ("progress", "damage")
                and archive_majority in ("progress", "damage"))
            preceding_disagreeing = bool(
                preceding_comparable
                and preceding_majority != archive_majority)
            preceding_span_records.append({
                "span": preceding_span,
                "preceding_count": preceding_count,
                "preceding_majority": preceding_majority,
                "archive_count": archive_count,
                "archive_majority": archive_majority,
                "preceding_comparable": bool(preceding_comparable),
                "preceding_disagreeing": preceding_disagreeing,
            })
        preceding_comparable_span_count = sum(
            int(r["preceding_comparable"])
            for r in preceding_span_records)
        preceding_disagreeing_span_count = sum(
            int(r["preceding_disagreeing"])
            for r in preceding_span_records)
        preceding_stable_disagreement = bool(
            preceding_comparable_span_count >= 1
            and (preceding_disagreeing_span_count * 2
                 > preceding_comparable_span_count))
        long_disagreement = bool(
            stable_disagreement and preceding_stable_disagreement)
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
        return (signal_records, legacy_signal_records, archive_records,
                joint_records, legacy_joint_records, archive,
                minority_records, minority_joint_records, minority_set,
                minority_archive_matched_count,
                minority_discordant_count, minority_fraction,
                minority_armed,
                expiry_span_records, comparable_span_count,
                disagreeing_span_count, stable_disagreement,
                preceding_span_records, preceding_comparable_span_count,
                preceding_disagreeing_span_count,
                preceding_stable_disagreement, long_disagreement,
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
                "legacy_signal_events": [],
                "archive_events": [],
                "joint_events": [],
                "joint_flags": [],
                "legacy_joint_events": [],
                "legacy_joint_flags": [],
                "opposed_count": 0,
                "matched_count": 0,
                "legacy_opposed_count": 0,
                "legacy_matched_count": 0,
                "legacy_joint_count": 0,
                "minority_events": [],
                "minority_joint_events": [],
                "minority_joint_flags": [],
                "minority_matched_count": 0,
                "minority_concordant_count": 0,
                "minority_joint_count": 0,
                "minority_archive_matched_count": 0,
                "minority_matched_archive_count": 0,
                "minority_discordant_count": 0,
                "minority_set_count": 0,
                "minority_fraction": 0.0,
                "minority_armed": False,
                "minority_fired": False,
                "minority_recovery_fired": False,
                "minority_would_fire": False,
                "concordant_count": 0,
                "archive_matched_count": 0,
                "joint_count": 0,
                "expiry_spans": [],
                "comparable_span_count": 0,
                "disagreeing_span_count": 0,
                "stable_disagreement": False,
                "preceding_spans": [],
                "preceding_comparable_span_count": 0,
                "preceding_disagreeing_span_count": 0,
                "preceding_stable_disagreement": False,
                "long_disagreement": False,
                "recent_events": [],
                "recent_concordant_count": 0,
                "recovery_armed": False,
                "recovery_arming_leg": "none",
                "abstention_armed": False,
                "recovery_would_fire": False,
                "abstention_would_fire": False,
                "minority_fraction_threshold": MINORITY_FRACTION_THRESHOLD,
                "minority_discordant_minimum": MINORITY_DISCORDANT_MINIMUM,
                "minority_joint_threshold": MINORITY_JOINT_THRESHOLD,
                "gate_opposed_threshold": GATE_OPPOSED_COUNT,
                "recovery_joint_threshold": RECOVERY_JOINT_COUNT,
                "recent_concordant_threshold": RECENT_CONCORDANT_THRESHOLD,
                "acting_window": ACTING_WINDOW,
                "newest_window_events": NEWEST_WINDOW,
                "reference_window_events": REFERENCE_WINDOW,
                "legacy_reference_window_events": LEGACY_REFERENCE_WINDOW,
                "archive_partition_events": ARCHIVE_PARTITION,
                "local_window_events": LOCAL_WINDOW,
                "preceding_window_events": PRECEDING_WINDOW,
                "archive_events_count": 0,
                "recorded_events": len(self.events),
                "learner_training_actions": 0,
            }
            self._cache = (decision, model)
            return self._cache
        (signal_records, legacy_signal_records, archive_records,
         joint_records, legacy_joint_records, archive,
         minority_records, minority_joint_records, minority_set,
         minority_archive_matched_count, minority_discordant_count,
         minority_fraction, minority_armed,
         expiry_span_records, comparable_span_count,
         disagreeing_span_count, stable_disagreement,
         preceding_span_records, preceding_comparable_span_count,
         preceding_disagreeing_span_count,
         preceding_stable_disagreement, long_disagreement,
         recent_records, recent_concordant_count) = self._records()
        opposed_count = sum(int(r["opposed"]) for r in signal_records)
        matched_count = sum(int(r["matched"]) for r in signal_records)
        concordant_count = sum(
            int(r["archive_concordant"]) for r in archive_records)
        archive_matched_count = sum(
            int(r["archive_matched"]) for r in archive_records)
        joint_flags = [bool(r["joint"]) for r in joint_records]
        joint_count = sum(int(f) for f in joint_flags)
        legacy_opposed_count = sum(
            int(r["opposed"]) for r in legacy_signal_records)
        legacy_matched_count = sum(
            int(r["matched"]) for r in legacy_signal_records)
        legacy_joint_flags = [bool(r["joint"])
                              for r in legacy_joint_records]
        legacy_joint_count = sum(int(f) for f in legacy_joint_flags)
        recovery_armed = bool(
            (not stable_disagreement)
            or recent_concordant_count >= RECENT_CONCORDANT_THRESHOLD
            or long_disagreement)
        if not recovery_armed:
            recovery_arming_leg = "none"
        elif not stable_disagreement:
            recovery_arming_leg = "no_stable_disagreement"
        elif long_disagreement:
            recovery_arming_leg = "long"
        else:
            recovery_arming_leg = "corroboration"
        abstention_armed = bool(not stable_disagreement)
        recovery_would_fire = joint_count >= RECOVERY_JOINT_COUNT
        abstention_would_fire = opposed_count == GATE_OPPOSED_COUNT
        minority_matched_count = sum(
            int(r["minority_matched"]) for r in minority_records)
        minority_concordant_count = sum(
            int(r["minority_concordant"]) for r in minority_records)
        minority_joint_flags = [bool(r["minority_joint"])
                                for r in minority_joint_records]
        minority_joint_count = sum(int(f) for f in minority_joint_flags)
        minority_would_fire = (
            minority_joint_count >= MINORITY_JOINT_THRESHOLD)
        recovery_fired = bool(recovery_would_fire and recovery_armed)
        minority_fired = bool((not recovery_fired) and minority_would_fire
                              and minority_armed)
        abstained = bool((not recovery_fired) and (not minority_fired)
                         and abstention_would_fire and abstention_armed)
        if recovery_fired:
            branch = "retained_archive"
            model = self._model(archive)
            reason = "joint_concordance_recovery_armed"
        elif minority_fired:
            branch = "minority_archive"
            model = self._model(minority_set)
            reason = "minority_archive_recovery_armed"
        elif abstained:
            branch = "abstained"
            model = self._model(self.events[-ACTING_WINDOW:])
            reason = "evidence_opposition_gate_abstain_armed"
        else:
            branch = "recent8"
            model = self._model(self.events[-ACTING_WINDOW:])
            if recovery_would_fire and not recovery_armed:
                reason = "recovery_disarmed_by_expiry"
            elif minority_would_fire and not minority_armed:
                reason = "minority_disarmed_by_fraction"
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
            "legacy_signal_events": legacy_signal_records,
            "archive_events": archive_records,
            "joint_events": joint_records,
            "joint_flags": joint_flags,
            "legacy_joint_events": legacy_joint_records,
            "legacy_joint_flags": legacy_joint_flags,
            "opposed_count": opposed_count,
            "matched_count": matched_count,
            "legacy_opposed_count": legacy_opposed_count,
            "legacy_matched_count": legacy_matched_count,
            "legacy_joint_count": legacy_joint_count,
            "minority_events": minority_records,
            "minority_joint_events": minority_joint_records,
            "minority_joint_flags": minority_joint_flags,
            "minority_matched_count": minority_matched_count,
            "minority_concordant_count": minority_concordant_count,
            "minority_joint_count": minority_joint_count,
            "minority_archive_matched_count":
                minority_archive_matched_count,
            "minority_matched_archive_count":
                minority_archive_matched_count,
            "minority_discordant_count": minority_discordant_count,
            "minority_set_count": minority_discordant_count,
            "minority_fraction": minority_fraction,
            "minority_armed": minority_armed,
            "minority_fired": minority_fired,
            "minority_recovery_fired": minority_fired,
            "minority_would_fire": minority_would_fire,
            "concordant_count": concordant_count,
            "archive_matched_count": archive_matched_count,
            "joint_count": joint_count,
            "expiry_spans": expiry_span_records,
            "comparable_span_count": comparable_span_count,
            "disagreeing_span_count": disagreeing_span_count,
            "stable_disagreement": stable_disagreement,
            "preceding_spans": preceding_span_records,
            "preceding_comparable_span_count":
                preceding_comparable_span_count,
            "preceding_disagreeing_span_count":
                preceding_disagreeing_span_count,
            "preceding_stable_disagreement":
                preceding_stable_disagreement,
            "long_disagreement": long_disagreement,
            "recent_events": recent_records,
            "recent_concordant_count": recent_concordant_count,
            "recovery_armed": recovery_armed,
            "recovery_arming_leg": recovery_arming_leg,
            "abstention_armed": abstention_armed,
            "recovery_would_fire": recovery_would_fire,
            "abstention_would_fire": abstention_would_fire,
            "minority_fraction_threshold": MINORITY_FRACTION_THRESHOLD,
            "minority_discordant_minimum": MINORITY_DISCORDANT_MINIMUM,
            "minority_joint_threshold": MINORITY_JOINT_THRESHOLD,
            "gate_opposed_threshold": GATE_OPPOSED_COUNT,
            "recovery_joint_threshold": RECOVERY_JOINT_COUNT,
            "recent_concordant_threshold": RECENT_CONCORDANT_THRESHOLD,
            "acting_window": ACTING_WINDOW,
            "newest_window_events": NEWEST_WINDOW,
            "reference_window_events": REFERENCE_WINDOW,
            "legacy_reference_window_events": LEGACY_REFERENCE_WINDOW,
            "archive_partition_events": ARCHIVE_PARTITION,
            "local_window_events": LOCAL_WINDOW,
            "preceding_window_events": PRECEDING_WINDOW,
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
                "untrained minority archive joint recovery memory")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError(
                "invalid minority archive joint recovery checkpoint hash")
        state = record["state"]
        if (set(state) != {"schema", "events"} or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError(
                "invalid minority archive joint recovery checkpoint structure")
        m = cls()
        for event in state["events"]:
            m.observe(event)
        if m.record() != record:
            raise ValueError(
                "minority archive joint recovery checkpoint replay mismatch")
        return m
