"""Frozen-protocol unit tests for EvidenceOppositionGuardMemory.

Protocol: benchmarks/evidence_opposition_onset_guard_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (312003-family / 313001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.evidence_opposition_onset_guard import (
    EvidenceOppositionGuardMemory, SCHEMA, ACTING_WINDOW,
    NEWEST_WINDOW, REFERENCE_WINDOW, MINIMUM_EVENTS,
    GATE_OPPOSED_COUNT,
)
from developmental_ai.observable_affordances import digest
from developmental_ai.relation_outcome_memory import RelationOutcomeMemory
from benchmarks.stochastic_prequential_benchmark import (
    DEV as STOCHASTIC_DEV, StochasticWorld, public_train,
)


def row(outcome, span=5):
    return {"features": {"inlet": 0, "outlet": span},
            "progress": outcome == "progress",
            "damage": outcome == "damage"}


def fed(rows):
    m = EvidenceOppositionGuardMemory()
    for r in rows:
        m.observe(r)
    return m


def recent8(rows):
    m = RelationOutcomeMemory()
    for r in rows[-ACTING_WINDOW:]:
        m.observe(r)
    return m


# 24 progress at one span (reference majority progress), then the two
# newest events damage at the same span: both matched and opposed.
FIRING_ROWS = ([row("progress") for _ in range(24)]
               + [row("damage"), row("damage")])


class EvidenceOppositionGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Already-inspected seed from the preceding stochastic study;
        # used only for a realistic public source stream and TEST frame.
        cls.seed = STOCHASTIC_DEV[0]
        cls.source, cls.cost = public_train(cls.seed, "original", 1000, 240)

    def test_frozen_parameters_match_protocol(self):
        self.assertEqual(ACTING_WINDOW, 8)
        self.assertEqual(NEWEST_WINDOW, 2)
        self.assertEqual(REFERENCE_WINDOW, 24)
        self.assertEqual(MINIMUM_EVENTS, 26)
        self.assertEqual(MINIMUM_EVENTS,
                         NEWEST_WINDOW + REFERENCE_WINDOW)
        self.assertEqual(GATE_OPPOSED_COUNT, 2)

    def test_gate_not_evaluable_below_minimum_events(self):
        # Even a stream whose newest outcomes oppose the earlier ones
        # cannot fire the gate below 26 events: the learner acts
        # through a fit on all available events and does not abstain.
        m = fed(FIRING_ROWS[:MINIMUM_EVENTS - 1])
        decision, model = m.selection()
        self.assertFalse(decision["gate_evaluable"])
        self.assertFalse(decision["abstained"])
        self.assertFalse(decision["gate_fired"])
        self.assertEqual(decision["signal_events"], [])
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(len(model.events), MINIMUM_EVENTS - 1)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIn(m.choose(frame),
                      {a["id"] for a in frame["actions"]})

    def test_empty_memory_selection_rejected(self):
        with self.assertRaises(ValueError):
            EvidenceOppositionGuardMemory().selection()
        with self.assertRaises(ValueError):
            EvidenceOppositionGuardMemory().record()

    def test_gate_fires_when_both_newest_opposed_exact_signal(self):
        decision, _ = fed(FIRING_ROWS).selection()
        self.assertTrue(decision["gate_evaluable"])
        self.assertEqual(decision["signal_events"], [
            {"span": 5, "reported_class": "damage",
             "reference_count": 24, "reference_majority": "progress",
             "matched": True, "opposed": True},
            {"span": 5, "reported_class": "damage",
             "reference_count": 24, "reference_majority": "progress",
             "matched": True, "opposed": True},
        ])
        self.assertEqual(decision["opposed_count"], 2)
        self.assertEqual(decision["matched_count"], 2)
        self.assertTrue(decision["abstained"])
        self.assertTrue(decision["gate_fired"])
        self.assertEqual(decision["selection"], "abstained-by-gate")
        self.assertEqual(decision["source"], "recent8")
        self.assertEqual(decision["learner_training_actions"], 0)

    def test_gate_firing_abstains_from_test_action(self):
        m = fed(FIRING_ROWS)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))
        # Choosing is read-only: the checkpoint is unchanged.
        self.assertEqual(m.record()["state"]["events"],
                         [dict(r) for r in FIRING_ROWS])

    def test_single_opposed_event_does_not_fire(self):
        rows = ([row("progress") for _ in range(24)]
                + [row("damage"), row("progress")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["opposed_count"], 1)
        self.assertEqual(decision["matched_count"], 2)
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["selection"], "recent8")
        self.assertTrue(decision["signal_events"][0]["opposed"])
        self.assertFalse(decision["signal_events"][1]["opposed"])

    def test_neutral_newest_event_is_never_opposed(self):
        rows = ([row("progress") for _ in range(24)]
                + [row("damage"), row("neutral")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["signal_events"][1],
                         {"span": 5, "reported_class": "neutral",
                          "reference_count": 24,
                          "reference_majority": "progress",
                          "matched": False, "opposed": False})
        self.assertEqual(decision["opposed_count"], 1)
        self.assertFalse(decision["abstained"])

    def test_neutral_reference_majority_is_unmatched(self):
        rows = ([row("neutral") for _ in range(24)]
                + [row("damage"), row("damage")])
        decision, _ = fed(rows).selection()
        for rec in decision["signal_events"]:
            self.assertEqual(rec["reference_majority"], "neutral")
            self.assertFalse(rec["matched"])
            self.assertFalse(rec["opposed"])
        self.assertEqual(decision["opposed_count"], 0)
        self.assertFalse(decision["abstained"])

    def test_tied_reference_majority_gives_no_expectation(self):
        rows = ([row("progress") for _ in range(12)]
                + [row("damage") for _ in range(12)]
                + [row("damage"), row("damage")])
        decision, _ = fed(rows).selection()
        for rec in decision["signal_events"]:
            self.assertEqual(rec["reference_count"], 24)
            self.assertIsNone(rec["reference_majority"])
            self.assertFalse(rec["matched"])
            self.assertFalse(rec["opposed"])
        self.assertFalse(decision["abstained"])

    def test_span_absent_from_reference_is_unmatched(self):
        rows = ([row("progress") for _ in range(24)]
                + [row("damage", span=9), row("damage")])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["signal_events"][0],
                         {"span": 9, "reported_class": "damage",
                          "reference_count": 0,
                          "reference_majority": None,
                          "matched": False, "opposed": False})
        self.assertEqual(decision["signal_events"][1]["reference_count"],
                         24)
        self.assertEqual(decision["opposed_count"], 1)
        self.assertFalse(decision["abstained"])

    def test_reference_is_span_specific(self):
        # Reference holds progress at span 5 but damage at span 3;
        # each newest event is judged against its own span only.
        rows = ([row("progress") for _ in range(12)]
                + [row("damage", span=3) for _ in range(12)]
                + [row("damage"), row("progress", span=3)])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["signal_events"][0]["reference_count"],
                         12)
        self.assertEqual(decision["signal_events"][0]
                         ["reference_majority"], "progress")
        self.assertEqual(decision["signal_events"][1]["reference_count"],
                         12)
        self.assertEqual(decision["signal_events"][1]
                         ["reference_majority"], "damage")
        self.assertEqual(decision["opposed_count"], 2)
        self.assertTrue(decision["abstained"])

    def test_only_last_26_events_form_the_signal_windows(self):
        # Older progress history must not dilute a damage reference
        # window: newest damage events are concordant with it.
        rows = ([row("progress") for _ in range(40)]
                + [row("damage") for _ in range(24)]
                + [row("damage"), row("damage")])
        decision, _ = fed(rows).selection()
        for rec in decision["signal_events"]:
            self.assertEqual(rec["reference_majority"], "damage")
            self.assertFalse(rec["opposed"])
        self.assertFalse(decision["abstained"])

    def test_stationary_evidence_does_not_fire_and_matches_recent8(self):
        rows = [row("progress") for _ in range(32)]
        m = fed(rows)
        decision, model = m.selection()
        self.assertEqual(decision["opposed_count"], 0)
        self.assertEqual(decision["matched_count"], 2)
        self.assertFalse(decision["abstained"])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame), recent8(rows).choose(frame))
        self.assertEqual(model.estimate({"inlet": 0, "outlet": 5}),
                         recent8(rows).estimate({"inlet": 0, "outlet": 5}))
        self.assertEqual(len(model.events), ACTING_WINDOW)

    def test_gate_releases_once_reference_window_passes_switch(self):
        # After 26 post-switch damage events the reference window is
        # entirely post-switch, so damage is concordant again.
        rows = FIRING_ROWS + [row("damage") for _ in range(24)]
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["opposed_count"], 0)
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["selection"], "recent8")

    def test_acting_model_is_exactly_recent8_when_gate_passes(self):
        m = fed(self.source)
        decision, model = m.selection()
        if decision["abstained"]:
            self.skipTest("gate fired on this inspected source stream; "
                          "equivalence is covered on synthetic streams")
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame),
                         recent8(self.source).choose(frame))
        self.assertEqual(len(model.events), ACTING_WINDOW)

    def test_no_fitted_probability_fields_in_decision(self):
        decision, _ = fed(FIRING_ROWS).selection()
        for key in decision:
            self.assertNotIn("probabilit", key)
            self.assertNotIn("log_score", key)
        for rec in decision["signal_events"]:
            self.assertEqual(set(rec),
                             {"span", "reported_class", "reference_count",
                              "reference_majority", "matched", "opposed"})

    def test_new_feedback_invalidates_cached_selection(self):
        m = fed([row("progress") for _ in range(26)])
        old = m.selection()
        self.assertIs(old, m.selection())
        m.observe(row("progress"))
        new = m.selection()
        self.assertIsNot(new, old)
        self.assertEqual(new[0]["recorded_events"], 27)

    def test_replay_exact_and_choice_read_only(self):
        m = fed(self.source)
        for r in public_train(self.seed, "reversed", 2000, 8)[0]:
            m.observe(r)
        saved = m.record()
        restored = EvidenceOppositionGuardMemory.restore(
            copy.deepcopy(saved))
        frame = StochasticWorld(self.seed, "test", 160000,
                                "reversed").frame()
        self.assertEqual(m.choose(frame), restored.choose(frame))
        self.assertEqual(m.selection()[0], restored.selection()[0])
        self.assertEqual(m.record(), saved)
        self.assertEqual(restored.record(), saved)
        self.assertFalse(hasattr(m, "step"))

    def test_replay_reproduces_firing_gate_decision(self):
        m = fed(FIRING_ROWS)
        saved = m.record()
        restored = EvidenceOppositionGuardMemory.restore(
            copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertTrue(restored.selection()[0]["abstained"])
        self.assertEqual(restored.selection()[0]["signal_events"],
                         m.selection()[0]["signal_events"])

    def test_reject_invalid_events_without_partial_write(self):
        m = EvidenceOppositionGuardMemory()
        m.observe(row("progress"))
        saved = m.record()
        with self.assertRaises(ValueError):
            m.observe({"features": {"inlet": 0, "outlet": 5},
                       "progress": True, "damage": True})
        with self.assertRaises(ValueError):
            m.observe({"features": {"other": 0, "outlet": 5},
                       "progress": True, "damage": False})
        self.assertEqual(m.record(), saved)

    def test_reject_forged_or_rehashed_record(self):
        m = fed([row("progress")])
        saved = m.record()
        bad = copy.deepcopy(saved)
        bad["state"]["events"][0]["damage"] = True
        with self.assertRaises(ValueError):
            EvidenceOppositionGuardMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            EvidenceOppositionGuardMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            EvidenceOppositionGuardMemory.restore(bad2)

    def test_record_contains_only_public_events(self):
        m = fed(self.source)
        state = m.record()["state"]
        self.assertEqual(set(state), {"schema", "events"})
        self.assertEqual(state["schema"], SCHEMA)
        self.assertEqual(set(state["events"][0]),
                         {"features", "progress", "damage"})
        for forbidden in ('"physics"', '"phase"', '"episode"',
                          '"split"', '"seed"', '"rule"'):
            self.assertNotIn(forbidden, str(m.record()))


if __name__ == "__main__":
    unittest.main()
