"""Frozen-protocol unit tests for FirstContactGuardMemory.

Protocol: benchmarks/first_contact_onset_guard_protocol.json.
These tests use only handcrafted synthetic events and the ALREADY
INSPECTED stochastic cohort seed 212003 (frame/source shape only).
The frozen cohorts of this experiment (302003-family / 303001-family)
are never touched here: no cohort scores are viewed or run before or
during implementation.
"""
from __future__ import annotations

import copy
import unittest

from developmental_ai.first_contact_onset_guard import (
    FirstContactGuardMemory, SCHEMA, ACTING_WINDOW, SCORING_WINDOW,
    FIT_WINDOW, CONTRADICTION_MIN, CONTRADICTION_P, MINIMUM_EVENTS,
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
    m = FirstContactGuardMemory()
    for r in rows:
        m.observe(r)
    return m


def recent8(rows):
    m = RelationOutcomeMemory()
    for r in rows[-ACTING_WINDOW:]:
        m.observe(r)
    return m


# 8 progress, then damage / neutral / damage / neutral at one span.
# Each scoring fit holds exactly 8 events, so a reported class with
# count 0 in its fit gets p = 0.25 / 8.75 = 0.028571 (< 0.125) and a
# class with count 1 gets p = 1.25 / 8.75 = 0.142857 (>= 0.125).
FIRING_ROWS = ([row("progress") for _ in range(8)]
               + [row("damage"), row("neutral"),
                  row("damage"), row("neutral")])


class FirstContactGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Already-inspected seed from the preceding stochastic study;
        # used only for a realistic public source stream and TEST frame.
        cls.seed = STOCHASTIC_DEV[0]
        cls.source, cls.cost = public_train(cls.seed, "original", 1000, 240)

    def test_frozen_parameters_match_protocol(self):
        self.assertEqual(ACTING_WINDOW, 8)
        self.assertEqual(SCORING_WINDOW, 4)
        self.assertEqual(FIT_WINDOW, 8)
        self.assertEqual(CONTRADICTION_MIN, 2)
        self.assertEqual(CONTRADICTION_P, 0.125)
        self.assertEqual(MINIMUM_EVENTS, 12)
        self.assertEqual(MINIMUM_EVENTS,
                         FIT_WINDOW + SCORING_WINDOW)

    def test_gate_not_evaluable_below_minimum_events(self):
        # Even a stream whose newest outcomes contradict the earlier
        # ones cannot fire the gate below 12 events: the learner acts
        # through a fit on all available events and does not abstain.
        m = fed(FIRING_ROWS[:MINIMUM_EVENTS - 1])
        decision, model = m.selection()
        self.assertFalse(decision["gate_evaluable"])
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["prequential_probabilities"], [])
        self.assertEqual(decision["scoring_events"], 0)
        self.assertEqual(len(model.events), MINIMUM_EVENTS - 1)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIn(m.choose(frame),
                      {a["id"] for a in frame["actions"]})

    def test_empty_memory_selection_rejected(self):
        with self.assertRaises(ValueError):
            FirstContactGuardMemory().selection()
        with self.assertRaises(ValueError):
            FirstContactGuardMemory().record()

    def test_gate_fires_on_two_contradictions_exact_probabilities(self):
        decision, _ = fed(FIRING_ROWS).selection()
        self.assertTrue(decision["gate_evaluable"])
        # Strictly-prior fits: the first damage is scored by an
        # all-progress fit (its own outcome is NOT in the fit, or the
        # count would be 1 and p would be 0.142857, not 0.028571).
        self.assertEqual(decision["prequential_probabilities"],
                         [0.028571, 0.028571, 0.142857, 0.142857])
        self.assertEqual(decision["contradiction_count"], 2)
        self.assertTrue(decision["abstained"])
        self.assertEqual(decision["selection"], "abstained-by-gate")
        self.assertEqual(decision["source"], "recent8")
        self.assertEqual(decision["predictor_training_overlap"], 0)
        self.assertEqual(decision["learner_training_actions"], 0)

    def test_gate_firing_abstains_from_test_action(self):
        m = fed(FIRING_ROWS)
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertIsNone(m.choose(frame))
        # Choosing is read-only: the checkpoint is unchanged.
        self.assertEqual(m.record()["state"]["events"],
                         [dict(r) for r in FIRING_ROWS])

    def test_single_contradiction_does_not_fire(self):
        rows = ([row("progress") for _ in range(8)]
                + [row("damage")] + [row("progress") for _ in range(3)])
        decision, _ = fed(rows).selection()
        self.assertEqual(decision["contradiction_count"], 1)
        self.assertFalse(decision["abstained"])
        self.assertEqual(decision["selection"], "recent8")

    def test_probability_equal_to_threshold_is_not_contradicted(self):
        # The contradiction rule is strict (p < 0.125). With an 8-event
        # fit the attainable probabilities nearest the threshold are
        # 0.028571 (count 0) and 0.142857 (count 1); assert the count-1
        # events in the firing stream are recorded at/above threshold
        # and are not counted.
        decision, _ = fed(FIRING_ROWS).selection()
        above = [p for p in decision["prequential_probabilities"]
                 if p >= CONTRADICTION_P]
        self.assertEqual(above, [0.142857, 0.142857])
        self.assertEqual(
            decision["contradiction_count"],
            sum(int(p < CONTRADICTION_P)
                for p in decision["prequential_probabilities"]))

    def test_stationary_evidence_does_not_fire_and_matches_recent8(self):
        rows = [row("progress") for _ in range(24)]
        m = fed(rows)
        decision, model = m.selection()
        self.assertEqual(decision["contradiction_count"], 0)
        self.assertFalse(decision["abstained"])
        frame = StochasticWorld(self.seed, "test", 160000,
                                "original").frame()
        self.assertEqual(m.choose(frame), recent8(rows).choose(frame))
        self.assertEqual(model.estimate({"inlet": 0, "outlet": 5}),
                         recent8(rows).estimate({"inlet": 0, "outlet": 5}))
        self.assertEqual(len(model.events), ACTING_WINDOW)

    def test_gate_releases_as_post_switch_evidence_accumulates(self):
        rows = FIRING_ROWS + [row("damage"), row("neutral"),
                              row("damage"), row("neutral")]
        decision, _ = fed(rows).selection()
        self.assertLess(decision["contradiction_count"], CONTRADICTION_MIN)
        self.assertFalse(decision["abstained"])

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

    def test_new_feedback_invalidates_cached_selection(self):
        m = fed([row("progress") for _ in range(12)])
        old = m.selection()
        self.assertIs(old, m.selection())
        m.observe(row("progress"))
        new = m.selection()
        self.assertIsNot(new, old)
        self.assertEqual(new[0]["recorded_events"], 13)

    def test_replay_exact_and_choice_read_only(self):
        m = fed(self.source)
        for r in public_train(self.seed, "reversed", 2000, 8)[0]:
            m.observe(r)
        saved = m.record()
        restored = FirstContactGuardMemory.restore(copy.deepcopy(saved))
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
        restored = FirstContactGuardMemory.restore(copy.deepcopy(saved))
        self.assertEqual(restored.selection()[0], m.selection()[0])
        self.assertTrue(restored.selection()[0]["abstained"])

    def test_reject_invalid_events_without_partial_write(self):
        m = FirstContactGuardMemory()
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
            FirstContactGuardMemory.restore(bad)
        bad["sha256"] = digest(bad["state"])
        with self.assertRaises(ValueError):
            FirstContactGuardMemory.restore(bad)
        bad2 = copy.deepcopy(saved)
        bad2["state"]["schema"] = "developmental-ai.other/v1"
        bad2["sha256"] = digest(bad2["state"])
        with self.assertRaises(ValueError):
            FirstContactGuardMemory.restore(bad2)

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
