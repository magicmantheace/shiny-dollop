"""Long-window support partial recovery: leg L on partial triggers.

Frozen protocol:
benchmarks/long_window_support_partial_recovery_protocol.json
(experiment long_window_support_partial_recovery, frozen
2026-11-14 BEFORE this implementation, commit 96c7c6e). The
candidate is a separate optional learner; the default controller
and every existing learner are untouched, and the graded
candidates are baselines only, not modified.

Mechanism, exactly as preregistered. IDENTICAL to the graded
PartialScopedSupportAbstentionRecoveryMemory in every element
(acting model recent8 exactly, extended signal newest 2 vs
50-event reference, retained archive events[:N-26], archive
concordance, joint test joint_count >= 1, recovery model, the
full three-leg authority condition, the minority branch in full
INCLUDING the inverted minority model and leg W on the minority
branch, leg T on both recovery branches, leg N and leg D on the
regular branch, leg C on partial abstention triggers, the
reference-purity gate >= 0.70 on both recovery branches, and
the full / retained-partial abstention classes with the widened
class removed with its quantities records-only) except the
SINGLE changed element:

THE ADDITION OF LEG L, A LONG-WINDOW SUPPORTING-OPPOSITION
LEG ON PARTIAL ABSTENTION TRIGGERS ONLY: leg L is armed iff
stale_opposed_count >= 1, where stale_opposed_count is the
number of opposed events in the stale window
events[-26:-8] (18 events, the same window leg T reads, each
scored against the extended-reference per-span majorities
exactly as the stale joint records score them),
long_window_threshold 1 carried unchanged from leg S's
support_threshold (no new numeric value). The full gate is
leg P ALONE, exactly the graded partial-scoped candidate's
full gate (neither leg S nor leg L applies); the partial
gate is leg P AND (leg R OR leg C) AND (leg S OR leg L).
abstention_disarmed_by_support is recorded true exactly
when BOTH support legs fail a partial trigger whose other
gate legs all pass (supporting_opposed_count == 0 AND
stale_opposed_count == 0, leg P armed, leg R OR leg C armed)
and neither recovery branch fired; at every other state it
is false. New decision-record fields: stale_opposed_count,
long_window_threshold, long_window_armed, and
abstention_taken_through_long_window, the last recorded
true exactly when a partial trigger with supporting 0 and
stale >= 1, every other gate leg passing and neither
recovery branch fired, is TAKEN through leg L. Leg P /
leg R / leg C / leg S / leg T / leg W / leg N / leg D are
explicitly NOT re-tuned.

Decision order: (1) RECOVERY (joint + authority + purity +
leg T + leg N OR leg D), (2) MINORITY RECOVERY (minority joint
+ minority armed + purity + leg T + leg W, acting through the
inverted archive model), (3) ABSTENTION (a trigger class holds
- full or partial - + authority + leg P, plus leg R OR leg C
AND (leg S OR leg L) when the trigger kind is partial), (4) RECENT8.
Minimum events: 52; below that the extended signal, purity, the
abstention gate, the preceding-pair records, the widened
quantities, the stale records, the companion fields, the
acting joint fields, and the newest joint fields are not
evaluable and the learner acts on all available events. Zero
learner training actions.
"""
from __future__ import annotations

import json

from developmental_ai.fast_shock_memory import FastShockMemory
from developmental_ai.observable_affordances import (
    MAX_SAMPLES, VariableOutcomeMemory, canonical, digest,
)
from developmental_ai.relation_outcome_memory import (
    RelationOutcomeMemory, span,
)

SCHEMA = "developmental-ai.long-window-support-partial-recovery-memory/v1"
ACTING_WINDOW = 8
NEWEST_WINDOW = 2
REFERENCE_WINDOW = 50
LEGACY_REFERENCE_WINDOW = 24
ARCHIVE_PARTITION = NEWEST_WINDOW + LEGACY_REFERENCE_WINDOW
LOCAL_WINDOW = 26
PRECEDING_WINDOW = 26
MINIMUM_EVENTS = 52
GATE_OPPOSED_COUNT = 1
RECOVERY_JOINT_COUNT = 1
RECENT_CONCORDANT_THRESHOLD = 2
MINORITY_FRACTION_THRESHOLD = 0.25
MINORITY_DISCORDANT_MINIMUM = 8
MINORITY_JOINT_THRESHOLD = 1
PURITY_THRESHOLD = 0.70
SUPPORT_THRESHOLD = 1
LONG_WINDOW_THRESHOLD = 1
PRECEDING_PAIR_THRESHOLD = 1
WIDENED_THRESHOLD = 3
STALE_WINDOW = LOCAL_WINDOW - ACTING_WINDOW
STALENESS_PAIR_THRESHOLD = 2
COMPANION_THRESHOLD = None
ACTING_JOINT_THRESHOLD = 3
NEWEST_JOINT_THRESHOLD = 2


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



def _swapped_event(event):
    """Archive event with progress/damage labels swapped.

    Neutral events (neither flag) are unchanged by the swap.
    """
    return {"features": dict(event["features"]),
            "progress": bool(event["damage"]),
            "damage": bool(event["progress"])}


def _inverted_model(archive):
    """RelationOutcomeMemory fitted on the swapped archive."""
    model = RelationOutcomeMemory()
    for event in archive:
        model.observe(_swapped_event(event))
    return model


class LongWindowSupportPartialRecoveryMemory(FastShockMemory):
    """Partial-scoped candidate plus leg L on partial triggers."""

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
        # Reference purity (SINGLE NEW ELEMENT): each reference event
        # scored against the reference window's own per-span majority.
        reference_records = []
        for _e in reference:
            _sp = span(_e["features"])
            _rep = _reported_class(_e)
            _cnt, _maj = _majority(reference, _sp)
            _matched = (_maj in ("progress", "damage")
                        and _rep in ("progress", "damage"))
            reference_records.append({
                "span": _sp,
                "reported_class": _rep,
                "reference_count": _cnt,
                "reference_majority": _maj,
                "reference_matched": bool(_matched),
                "reference_concordant": bool(_matched and _rep == _maj),
            })
        reference_matched_count = sum(
            int(r["reference_matched"]) for r in reference_records)
        reference_concordant_count = sum(
            int(r["reference_concordant"]) for r in reference_records)
        reference_purity = (
            reference_concordant_count / reference_matched_count
            if reference_matched_count else 0.0)
        purity_armed = bool(reference_purity >= PURITY_THRESHOLD)
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
        # Acting-window opposition records: each of the last 8
        # events scored against the SAME extended-reference
        # per-span majorities as the signal. The supporting count
        # derived from them in selection() is leg S's input for
        # both abstention classes; the count over this window is also
        # one component of the records-only widened_armed
        # derivation (see selection()). The graded >= 4 and >= 3
        # gate rules also remain derivable from the records alone.
        acting_records = []
        for event in self.events[-ACTING_WINDOW:]:
            event_span = span(event["features"])
            reported = _reported_class(event)
            reference_count, reference_majority = _majority(
                reference, event_span)
            matched = (reference_majority in ("progress", "damage")
                       and reported in ("progress", "damage"))
            opposed = bool(matched and reported != reference_majority)
            acting_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": reference_majority,
                "matched": bool(matched),
                "opposed": opposed,
            })
        acting_matched_count = sum(
            int(r["matched"]) for r in acting_records)
        acting_opposed_count = sum(
            int(r["opposed"]) for r in acting_records)
        # Preceding-pair records (carried leg R's input, and one
        # component of the records-only newest-four total):
        # the two events immediately preceding the newest pair,
        # events[-4:-2], each scored against the SAME extended
        # reference per-span majorities as the acting-window
        # records above. Records only here; leg R is applied in
        # selection() to partial abstention triggers only.
        preceding_pair_records = []
        for event in self.events[-4:-2]:
            event_span = span(event["features"])
            reported = _reported_class(event)
            reference_count, reference_majority = _majority(
                reference, event_span)
            matched = (reference_majority in ("progress", "damage")
                       and reported in ("progress", "damage"))
            opposed = bool(matched and reported != reference_majority)
            preceding_pair_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": reference_majority,
                "matched": bool(matched),
                "opposed": opposed,
            })
        preceding_pair_matched_count = sum(
            int(r["matched"]) for r in preceding_pair_records)
        preceding_pair_opposed_count = sum(
            int(r["opposed"]) for r in preceding_pair_records)
        # Stale-window records (leg T, THE SINGLE CHANGED
        # ELEMENT): the 18 events of events[-26:-8] (the local
        # window minus the acting window), each scored with each
        # recovery branch's own joint definition against the
        # current archive / minority set / reference majorities,
        # exactly as the newest pair's joint flags are scored.
        # The pair counts aggregate the 9 consecutive disjoint
        # pairs in stream order; a pair counts when BOTH events
        # are joint for that branch. Records only here; leg T is
        # applied in selection().
        stale_joint_records = []
        stale_minority_joint_records = []
        for event in self.events[-LOCAL_WINDOW:-ACTING_WINDOW]:
            event_span = span(event["features"])
            reported = _reported_class(event)
            reference_count, reference_majority = _majority(
                reference, event_span)
            matched = (reference_majority in ("progress", "damage")
                       and reported in ("progress", "damage"))
            opposed = bool(matched and reported != reference_majority)
            archive_count, archive_majority = _majority(
                archive, event_span)
            archive_matched = (archive_majority in ("progress", "damage")
                               and reported in ("progress", "damage"))
            archive_concordant = bool(
                archive_matched and reported == archive_majority)
            joint = bool(archive_concordant and opposed)
            stale_joint_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": reference_majority,
                "matched": bool(matched),
                "opposed": opposed,
                "archive_count": archive_count,
                "archive_majority": archive_majority,
                "archive_matched": bool(archive_matched),
                "archive_concordant": archive_concordant,
                "joint": joint,
            })
            minority_count_span, minority_majority = _majority(
                minority_set, event_span)
            minority_matched = (
                minority_majority in ("progress", "damage")
                and reported in ("progress", "damage"))
            minority_concordant = bool(
                minority_matched and reported == minority_majority)
            minority_joint = bool(minority_concordant and opposed)
            stale_minority_joint_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": reference_majority,
                "matched": bool(matched),
                "opposed": opposed,
                "minority_count": minority_count_span,
                "minority_majority": minority_majority,
                "minority_matched": bool(minority_matched),
                "minority_concordant": minority_concordant,
                "minority_joint": minority_joint,
                "joint": minority_joint,
            })
        stale_joint_pair_count = sum(
            int(stale_joint_records[i]["joint"]
                and stale_joint_records[i + 1]["joint"])
            for i in range(0, len(stale_joint_records) - 1, 2))
        stale_minority_joint_pair_count = sum(
            int(stale_minority_joint_records[i]["joint"]
                and stale_minority_joint_records[i + 1]["joint"])
            for i in range(0, len(stale_minority_joint_records) - 1, 2))
        # Acting-window joint records (leg W, THE SINGLE CHANGED
        # ELEMENT): the 8 events of events[-8:] (the carried
        # ACTING_WINDOW), each scored with each recovery branch's
        # own joint definition against the current archive /
        # minority set / reference majorities, exactly as the
        # newest pair's and the stale window's joint flags are
        # scored. Records only here; leg W is applied in
        # selection().
        acting_joint_records = []
        acting_minority_joint_records = []
        for event in self.events[-ACTING_WINDOW:]:
            event_span = span(event["features"])
            reported = _reported_class(event)
            reference_count, reference_majority = _majority(
                reference, event_span)
            matched = (reference_majority in ("progress", "damage")
                       and reported in ("progress", "damage"))
            opposed = bool(matched and reported != reference_majority)
            archive_count, archive_majority = _majority(
                archive, event_span)
            archive_matched = (archive_majority in ("progress", "damage")
                               and reported in ("progress", "damage"))
            archive_concordant = bool(
                archive_matched and reported == archive_majority)
            joint = bool(archive_concordant and opposed)
            acting_joint_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": reference_majority,
                "matched": bool(matched),
                "opposed": opposed,
                "archive_count": archive_count,
                "archive_majority": archive_majority,
                "archive_matched": bool(archive_matched),
                "archive_concordant": archive_concordant,
                "joint": joint,
            })
            minority_count_span, minority_majority = _majority(
                minority_set, event_span)
            minority_matched = (
                minority_majority in ("progress", "damage")
                and reported in ("progress", "damage"))
            minority_concordant = bool(
                minority_matched and reported == minority_majority)
            minority_joint = bool(minority_concordant and opposed)
            acting_minority_joint_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": reference_majority,
                "matched": bool(matched),
                "opposed": opposed,
                "minority_count": minority_count_span,
                "minority_majority": minority_majority,
                "minority_matched": bool(minority_matched),
                "minority_concordant": minority_concordant,
                "minority_joint": minority_joint,
                "joint": minority_joint,
            })
        acting_joint_count = sum(
            int(r["joint"]) for r in acting_joint_records)
        acting_minority_joint_count = sum(
            int(r["joint"]) for r in acting_minority_joint_records)
        # Newest-window joint records (leg N, THE SINGLE CHANGED
        # ELEMENT): the 4 events of events[-4:], each scored with
        # the regular branch's joint definition against the
        # current archive / reference majorities, exactly as the
        # newest pair's, the stale window's, and the acting
        # window's joint flags are scored. Records only here;
        # leg N is applied in selection().
        newest_joint_records = []
        for event in self.events[-4:]:
            event_span = span(event["features"])
            reported = _reported_class(event)
            reference_count, reference_majority = _majority(
                reference, event_span)
            matched = (reference_majority in ("progress", "damage")
                       and reported in ("progress", "damage"))
            opposed = bool(matched and reported != reference_majority)
            archive_count, archive_majority = _majority(
                archive, event_span)
            archive_matched = (archive_majority in ("progress", "damage")
                               and reported in ("progress", "damage"))
            archive_concordant = bool(
                archive_matched and reported == archive_majority)
            joint = bool(archive_concordant and opposed)
            newest_joint_records.append({
                "span": event_span,
                "reported_class": reported,
                "reference_count": reference_count,
                "reference_majority": reference_majority,
                "matched": bool(matched),
                "opposed": opposed,
                "archive_count": archive_count,
                "archive_majority": archive_majority,
                "archive_matched": bool(archive_matched),
                "archive_concordant": archive_concordant,
                "joint": joint,
            })
        newest_joint_count = sum(
            int(r["joint"]) for r in newest_joint_records)
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
                recent_records, recent_concordant_count,
                reference_records, reference_matched_count,
                reference_concordant_count, reference_purity,
                purity_armed,
                acting_records, acting_matched_count,
                acting_opposed_count,
                preceding_pair_records, preceding_pair_matched_count,
                preceding_pair_opposed_count,
                stale_joint_records, stale_minority_joint_records,
                stale_joint_pair_count, stale_minority_joint_pair_count,
                acting_joint_records, acting_minority_joint_records,
                acting_joint_count, acting_minority_joint_count,
                newest_joint_records, newest_joint_count)

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
                "minority_model_archive_count": 0,
                "minority_model_inverted": True,
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
                "reference_events": [],
                "reference_matched_count": 0,
                "reference_concordant_count": 0,
                "reference_purity": 0.0,
                "purity_armed": False,
                "purity_threshold": PURITY_THRESHOLD,
                "recovery_disarmed_by_purity": False,
                "minority_disarmed_by_purity": False,
                "acting_events": [],
                "acting_matched_count": 0,
                "acting_opposed_count": 0,
                "supporting_opposed_count": 0,
                "support_threshold": SUPPORT_THRESHOLD,
                "abstention_support_threshold": SUPPORT_THRESHOLD,
                "abstention_gate_armed": False,
                "abstention_disarmed_by_purity": False,
                "abstention_disarmed_by_support": False,
                "stale_opposed_count": 0,
                "long_window_threshold": LONG_WINDOW_THRESHOLD,
                "long_window_armed": False,
                "abstention_taken_through_long_window": False,
                "abstention_trigger_kind": "none",
                "preceding_pair_events": [],
                "preceding_pair_matched_count": 0,
                "preceding_pair_opposed_count": 0,
                "preceding_pair_armed": False,
                "preceding_pair_threshold": PRECEDING_PAIR_THRESHOLD,
                "abstention_disarmed_by_preceding_pair": False,
                "companion_matched": False,
                "companion_concordant": False,
                "companion_armed": False,
                "companion_threshold": COMPANION_THRESHOLD,
                "abstention_disarmed_by_companion": False,
                "newest4_opposed_count": 0,
                "widened_armed": False,
                "widened_threshold": WIDENED_THRESHOLD,
                "stale_joint_events": [],
                "stale_minority_joint_events": [],
                "stale_joint_pair_count": 0,
                "stale_minority_joint_pair_count": 0,
                "staleness_pair_threshold": STALENESS_PAIR_THRESHOLD,
                "recovery_disarmed_by_staleness": False,
                "minority_disarmed_by_staleness": False,
                "acting_joint_events": [],
                "acting_minority_joint_events": [],
                "acting_joint_count": 0,
                "acting_minority_joint_count": 0,
                "acting_joint_threshold": ACTING_JOINT_THRESHOLD,
                "recovery_disarmed_by_acting_breadth": False,
                "minority_disarmed_by_acting_breadth": False,
                "newest_joint_events": [],
                "newest_joint_count": 0,
                "newest_joint_threshold": NEWEST_JOINT_THRESHOLD,
                "recovery_disarmed_by_newest_breadth": False,
                "singleton_release_fired": False,
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
         recent_records, recent_concordant_count,
         reference_records, reference_matched_count,
         reference_concordant_count, reference_purity,
         purity_armed,
         acting_records, acting_matched_count,
         acting_opposed_count,
         preceding_pair_records, preceding_pair_matched_count,
         preceding_pair_opposed_count,
         stale_joint_records, stale_minority_joint_records,
         stale_joint_pair_count,
         stale_minority_joint_pair_count,
         acting_joint_records, acting_minority_joint_records,
         acting_joint_count,
         acting_minority_joint_count,
         newest_joint_records, newest_joint_count) = self._records()
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
        # Widened quantities, RECORDS-ONLY (THE SINGLE CHANGED
        # ELEMENT): newest-four total and acting-window
        # accumulation, both recomputable from the records above.
        # widened_armed records whether the REMOVED class would
        # have armed; it is not a trigger, gate leg, or branch
        # input anywhere in this candidate.
        newest4_opposed_count = (
            opposed_count + preceding_pair_opposed_count)
        widened_armed = bool(
            newest4_opposed_count <= 1
            and acting_opposed_count >= WIDENED_THRESHOLD)
        abstention_would_fire = bool(
            opposed_count >= GATE_OPPOSED_COUNT)
        # Trigger kind, exactly as frozen: full / partial / none
        # only -- never widened, the widened class being removed.
        if opposed_count == 2:
            abstention_trigger_kind = "full"
        elif opposed_count == 1:
            abstention_trigger_kind = "partial"
        else:
            abstention_trigger_kind = "none"
        # Companion records (leg C, THE SINGLE CHANGED ELEMENT):
        # defined only for a partial trigger, from the newest
        # pair's own signal records -- the non-opposed event is
        # the companion. Outside a partial trigger there is no
        # companion event and the fields take their fallback
        # form, so leg C can never arm there.
        if abstention_trigger_kind == "partial":
            _companion = next(
                r for r in signal_records if not r["opposed"])
            companion_matched = bool(_companion["matched"])
            companion_concordant = bool(
                _companion["matched"] and not _companion["opposed"])
            companion_armed = bool(not companion_concordant)
        else:
            companion_matched = False
            companion_concordant = False
            companion_armed = False
        minority_matched_count = sum(
            int(r["minority_matched"]) for r in minority_records)
        minority_concordant_count = sum(
            int(r["minority_concordant"]) for r in minority_records)
        minority_joint_flags = [bool(r["minority_joint"])
                                for r in minority_joint_records]
        minority_joint_count = sum(int(f) for f in minority_joint_flags)
        minority_would_fire = (
            minority_joint_count >= MINORITY_JOINT_THRESHOLD)
        recovery_disarmed_by_purity = bool(
            recovery_would_fire and recovery_armed and not purity_armed)
        recovery_disarmed_by_staleness = bool(
            recovery_would_fire and recovery_armed and purity_armed
            and stale_joint_pair_count >= STALENESS_PAIR_THRESHOLD)
        recovery_disarmed_by_acting_breadth = bool(
            recovery_would_fire and recovery_armed and purity_armed
            and stale_joint_pair_count < STALENESS_PAIR_THRESHOLD
            and acting_joint_count < ACTING_JOINT_THRESHOLD)
        recovery_disarmed_by_newest_breadth = bool(
            recovery_would_fire and recovery_armed and purity_armed
            and stale_joint_pair_count < STALENESS_PAIR_THRESHOLD
            and acting_joint_count >= ACTING_JOINT_THRESHOLD
            and newest_joint_count < NEWEST_JOINT_THRESHOLD)
        singleton_release_fired = bool(
            recovery_would_fire and recovery_armed and purity_armed
            and stale_joint_pair_count < STALENESS_PAIR_THRESHOLD
            and newest_joint_count == 1
            and acting_joint_count >= ACTING_JOINT_THRESHOLD)
        recovery_fired = bool(
            recovery_would_fire and recovery_armed and purity_armed
            and stale_joint_pair_count < STALENESS_PAIR_THRESHOLD
            and (newest_joint_count >= NEWEST_JOINT_THRESHOLD
                 or singleton_release_fired))
        minority_disarmed_by_purity = bool(
            (not recovery_fired) and minority_would_fire
            and minority_armed and not purity_armed)
        minority_disarmed_by_staleness = bool(
            (not recovery_fired) and minority_would_fire
            and minority_armed and purity_armed
            and (stale_minority_joint_pair_count
                 >= STALENESS_PAIR_THRESHOLD))
        minority_disarmed_by_acting_breadth = bool(
            (not recovery_fired) and minority_would_fire
            and minority_armed and purity_armed
            and (stale_minority_joint_pair_count
                 < STALENESS_PAIR_THRESHOLD)
            and acting_minority_joint_count < ACTING_JOINT_THRESHOLD)
        minority_fired = bool(
            (not recovery_fired) and minority_would_fire
            and minority_armed and purity_armed
            and (stale_minority_joint_pair_count
                 < STALENESS_PAIR_THRESHOLD)
            and acting_minority_joint_count >= ACTING_JOINT_THRESHOLD)
        supporting_opposed_count = acting_opposed_count - opposed_count
        stale_opposed_count = sum(
            int(r["opposed"]) for r in stale_joint_records)
        long_window_armed = bool(
            stale_opposed_count >= LONG_WINDOW_THRESHOLD)
        preceding_pair_armed = bool(
            preceding_pair_opposed_count >= PRECEDING_PAIR_THRESHOLD)
        support_armed = bool(
            supporting_opposed_count >= SUPPORT_THRESHOLD)
        # Gate, composite for the trigger kind: leg P ALONE
        # for a full trigger (neither leg S nor leg L applies);
        # leg P AND (leg R OR leg C) AND (leg S OR leg L) for a
        # partial trigger only -- THE SINGLE CHANGED ELEMENT is
        # leg L, the long-window leg; recorded as purity_armed
        # when there is no trigger, exactly as carried.
        if abstention_trigger_kind == "partial":
            abstention_other_legs_armed = bool(
                purity_armed
                and (preceding_pair_armed or companion_armed))
            abstention_gate_armed = bool(
                abstention_other_legs_armed
                and (support_armed or long_window_armed))
        elif abstention_trigger_kind == "full":
            abstention_other_legs_armed = bool(purity_armed)
            abstention_gate_armed = bool(purity_armed)
        else:
            abstention_other_legs_armed = bool(purity_armed)
            abstention_gate_armed = bool(purity_armed)
        abstention_gate_blocked = bool(
            (not recovery_fired) and (not minority_fired)
            and abstention_would_fire and abstention_armed
            and not abstention_gate_armed)
        abstention_disarmed_by_purity = bool(
            abstention_gate_blocked and not purity_armed)
        abstention_disarmed_by_preceding_pair = bool(
            abstention_gate_blocked
            and abstention_trigger_kind == "partial"
            and not preceding_pair_armed and not companion_armed)
        abstention_disarmed_by_companion = bool(
            abstention_gate_blocked
            and abstention_trigger_kind == "partial"
            and not preceding_pair_armed and not companion_armed)
        abstention_disarmed_by_support = bool(
            abstention_gate_blocked and not support_armed
            and not long_window_armed
            and abstention_trigger_kind == "partial"
            and abstention_other_legs_armed)
        abstained = bool((not recovery_fired) and (not minority_fired)
                         and abstention_would_fire and abstention_armed
                         and abstention_gate_armed)
        abstention_taken_through_long_window = bool(
            abstained and abstention_trigger_kind == "partial"
            and not support_armed and long_window_armed)
        if recovery_fired:
            branch = "retained_archive"
            model = self._model(archive)
            reason = "joint_concordance_recovery_armed"
        elif minority_fired:
            branch = "minority_archive"
            model = _inverted_model(archive)
            reason = "minority_archive_recovery_armed"
        elif abstained:
            branch = "abstained"
            model = self._model(self.events[-ACTING_WINDOW:])
            reason = "evidence_opposition_gate_abstain_armed"
        else:
            branch = "recent8"
            model = self._model(self.events[-ACTING_WINDOW:])
            if recovery_disarmed_by_purity:
                reason = "recovery_disarmed_by_purity"
            elif recovery_disarmed_by_staleness:
                reason = "recovery_disarmed_by_staleness"
            elif recovery_disarmed_by_newest_breadth:
                reason = "recovery_disarmed_by_newest_breadth"
            elif recovery_disarmed_by_acting_breadth:
                reason = "recovery_disarmed_by_acting_breadth"
            elif minority_disarmed_by_purity:
                reason = "minority_disarmed_by_purity"
            elif minority_disarmed_by_staleness:
                reason = "minority_disarmed_by_staleness"
            elif minority_disarmed_by_acting_breadth:
                reason = "minority_disarmed_by_acting_breadth"
            elif recovery_would_fire and not recovery_armed:
                reason = "recovery_disarmed_by_expiry"
            elif minority_would_fire and not minority_armed:
                reason = "minority_disarmed_by_fraction"
            elif abstention_disarmed_by_purity:
                reason = "abstention_disarmed_by_purity"
            elif abstention_disarmed_by_preceding_pair:
                reason = "abstention_disarmed_by_preceding_pair"
            elif abstention_disarmed_by_support:
                reason = "abstention_disarmed_by_support"
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
            "minority_model_archive_count": len(archive),
            "minority_model_inverted": True,
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
            "reference_events": reference_records,
            "reference_matched_count": reference_matched_count,
            "reference_concordant_count": reference_concordant_count,
            "reference_purity": reference_purity,
            "purity_armed": purity_armed,
            "purity_threshold": PURITY_THRESHOLD,
            "recovery_disarmed_by_purity": recovery_disarmed_by_purity,
            "minority_disarmed_by_purity": minority_disarmed_by_purity,
            "acting_events": acting_records,
            "acting_matched_count": acting_matched_count,
            "acting_opposed_count": acting_opposed_count,
            "supporting_opposed_count": supporting_opposed_count,
            "support_threshold": SUPPORT_THRESHOLD,
            "abstention_support_threshold": SUPPORT_THRESHOLD,
            "abstention_gate_armed": abstention_gate_armed,
            "abstention_disarmed_by_purity": abstention_disarmed_by_purity,
            "abstention_disarmed_by_support": abstention_disarmed_by_support,
            "stale_opposed_count": stale_opposed_count,
            "long_window_threshold": LONG_WINDOW_THRESHOLD,
            "long_window_armed": long_window_armed,
            "abstention_taken_through_long_window":
                abstention_taken_through_long_window,
            "abstention_trigger_kind": abstention_trigger_kind,
            "preceding_pair_events": preceding_pair_records,
            "preceding_pair_matched_count": preceding_pair_matched_count,
            "preceding_pair_opposed_count": preceding_pair_opposed_count,
            "preceding_pair_armed": preceding_pair_armed,
            "preceding_pair_threshold": PRECEDING_PAIR_THRESHOLD,
            "abstention_disarmed_by_preceding_pair":
                abstention_disarmed_by_preceding_pair,
            "companion_matched": companion_matched,
            "companion_concordant": companion_concordant,
            "companion_armed": companion_armed,
            "companion_threshold": COMPANION_THRESHOLD,
            "abstention_disarmed_by_companion":
                abstention_disarmed_by_companion,
            "newest4_opposed_count": newest4_opposed_count,
            "widened_armed": widened_armed,
            "widened_threshold": WIDENED_THRESHOLD,
            "stale_joint_events": stale_joint_records,
            "stale_minority_joint_events": stale_minority_joint_records,
            "stale_joint_pair_count": stale_joint_pair_count,
            "stale_minority_joint_pair_count":
                stale_minority_joint_pair_count,
            "staleness_pair_threshold": STALENESS_PAIR_THRESHOLD,
            "recovery_disarmed_by_staleness":
                recovery_disarmed_by_staleness,
            "minority_disarmed_by_staleness":
                minority_disarmed_by_staleness,
            "acting_joint_events": acting_joint_records,
            "acting_minority_joint_events": acting_minority_joint_records,
            "acting_joint_count": acting_joint_count,
            "acting_minority_joint_count": acting_minority_joint_count,
            "acting_joint_threshold": ACTING_JOINT_THRESHOLD,
            "recovery_disarmed_by_acting_breadth":
                recovery_disarmed_by_acting_breadth,
            "minority_disarmed_by_acting_breadth":
                minority_disarmed_by_acting_breadth,
            "newest_joint_events": newest_joint_records,
            "newest_joint_count": newest_joint_count,
            "newest_joint_threshold": NEWEST_JOINT_THRESHOLD,
            "recovery_disarmed_by_newest_breadth":
                recovery_disarmed_by_newest_breadth,
            "singleton_release_fired": singleton_release_fired,
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
                "untrained long window support partial recovery memory")
        state = {"schema": SCHEMA, "events": self.events}
        return {"state": json.loads(canonical(state)), "sha256": digest(state)}

    @classmethod
    def restore(cls, record):
        if (type(record) is not dict or set(record) != {"state", "sha256"}
                or type(record["state"]) is not dict
                or type(record["sha256"]) is not str
                or digest(record["state"]) != record["sha256"]):
            raise ValueError(
                "invalid long window support partial recovery checkpoint hash")
        state = record["state"]
        if (set(state) != {"schema", "events"} or state["schema"] != SCHEMA
                or type(state["events"]) is not list
                or not 1 <= len(state["events"]) <= MAX_SAMPLES):
            raise ValueError(
                "invalid long window support partial recovery checkpoint structure")
        m = cls()
        for event in state["events"]:
            m.observe(event)
        if m.record() != record:
            raise ValueError(
                "long window support partial recovery checkpoint replay mismatch")
        return m
