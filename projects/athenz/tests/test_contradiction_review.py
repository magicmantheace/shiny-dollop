"""Synthetic contradiction candidate + owner adjudication tests (v0.3).

Detection proposes pairs only; nothing here uses owner data, and every
record-changing assertion goes through an explicit confirmed adjudication.
"""
from __future__ import annotations

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest

from athenz.contradiction_review import (
    ContradictionReviewError, ContradictionStore, adjudicate_profile,
    list_profile, scan_profile, show_profile)
from athenz.contradiction_review_cli import main as cli_main
from athenz.desktop import DesktopService
from athenz.experience import ExperienceStore


class ContradictionReviewTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.home = Path(tmp.name) / "private"
        self.store = ExperienceStore(self.home)
        self.addCleanup(self.store.close)
        self.review = ContradictionStore(self.home)

    # -- helpers ------------------------------------------------------------

    def identity(self, text, *, kind="preference", approved=True):
        return self.store.propose(kind, text, source="synthetic:test",
                                  approved=approved)

    def status(self, table, record_id):
        return self.store.db.execute(
            f"SELECT status FROM {table} WHERE id=?", (record_id,)).fetchone()[0]

    def events(self, table, record_id):
        return [r[0] for r in self.store.db.execute(
            "SELECT operation FROM events WHERE subject_type=? AND subject_id=?",
            (table, record_id))]

    def scan(self):
        return self.review.scan()

    def only_candidate(self):
        found = self.review.candidates(limit=50)
        self.assertEqual(len(found), 1)
        return found[0]

    # -- detection ------------------------------------------------------------

    def test_negation_pair_fires_for_identity(self):
        first = self.identity("I exercise every morning before work")
        second = self.identity("I do not exercise every morning before work")
        report = self.scan()
        self.assertEqual(report["created"], 1)
        self.assertEqual(report["by_route"]["negation-asymmetry"], 1)
        candidate = self.only_candidate()
        self.assertEqual(candidate["route"], "negation-asymmetry")
        self.assertEqual((candidate["a_id"], candidate["b_id"]), (first, second))
        self.assertEqual(candidate["signals"]["negated_side"], "b")
        self.assertIn("exercise", candidate["signals"]["shared_tokens"])
        self.assertTrue(candidate["records_still_approved"])

    def test_opposite_preference_marker_pair_fires(self):
        self.identity("I prefer synthetic lapsang tea")
        self.identity("I avoid synthetic lapsang tea")
        self.scan()
        candidate = self.only_candidate()
        self.assertEqual(candidate["route"], "opposite-preference")
        self.assertEqual(candidate["signals"]["object"], "synthetic lapsang tea")
        self.assertEqual(candidate["signals"]["verb_a"], "prefer")
        self.assertEqual(candidate["signals"]["verb_b"], "avoid")

    def test_conflicting_favorite_slot_fires(self):
        self.identity("My favorite drink is synthetic tea")
        self.identity("My favorite drink is synthetic coffee")
        self.scan()
        candidate = self.only_candidate()
        self.assertEqual(candidate["route"], "conflicting-slot")
        self.assertEqual(candidate["signals"]["slot"], "favorite")
        self.assertEqual(candidate["signals"]["slot_name"], "drink")
        self.assertEqual(candidate["signals"]["value_a"], "synthetic tea")
        self.assertEqual(candidate["signals"]["value_b"], "synthetic coffee")

    def test_reversed_preference_pair_fires(self):
        self.identity("I prefer synthetic tea over synthetic coffee")
        self.identity("I prefer synthetic coffee over synthetic tea")
        self.scan()
        routes = {c["route"] for c in self.review.candidates(limit=50)}
        self.assertIn("conflicting-slot", routes)

    def test_decision_scenario_slot_fires_on_different_choice(self):
        self.store.add_decision("Choose the synthetic deployment window?",
                                "Friday", "first rationale", source="synthetic:test",
                                approved=True)
        self.store.add_decision("Choose the synthetic deployment window!",
                                "Monday", "second rationale", source="synthetic:test",
                                approved=True)
        self.scan()
        candidate = self.only_candidate()
        self.assertEqual(candidate["a_table"], "decisions")
        self.assertEqual(candidate["signals"]["slot"], "decision-scenario")
        self.assertEqual({candidate["signals"]["choice_a"],
                          candidate["signals"]["choice_b"]}, {"friday", "monday"})

    def test_episode_negation_pair_fires_with_shared_tags(self):
        first = self.store.observe(
            "Synthetic gym", "I train at the synthetic gym every weekday.",
            tags=["health"], source="synthetic:test")
        second = self.store.observe(
            "Synthetic gym", "I do not train at the synthetic gym every weekday.",
            tags=["health"], source="synthetic:test")
        self.store.review_episode(first, "approved")
        self.store.review_episode(second, "approved")
        self.scan()
        candidate = self.only_candidate()
        self.assertEqual(candidate["a_table"], "episodes")
        self.assertEqual(candidate["route"], "negation-asymmetry")
        self.assertEqual(candidate["signals"]["shared_tags"], ["health"])

    def test_unrelated_records_do_not_fire(self):
        self.identity("I prefer synthetic lapsang tea")
        self.identity("The synthetic depot opens at dawn", kind="knowledge")
        self.identity("I keep a synthetic workshop ledger", kind="knowledge")
        report = self.scan()
        self.assertEqual(report["detected"], 0)
        self.assertEqual(self.review.candidates(limit=50), [])

    def test_agreeing_records_do_not_fire(self):
        self.identity("I prefer synthetic lapsang tea")
        self.identity("I like synthetic lapsang tea")
        self.identity("I prefer synthetic lapsang tea blends")
        report = self.scan()
        self.assertEqual(report["detected"], 0)

    def test_pending_records_are_not_scanned(self):
        self.identity("I exercise every morning before work", approved=False)
        self.identity("I do not exercise every morning before work", approved=False)
        report = self.scan()
        self.assertEqual(report["records_scanned"]["identity"], 0)
        self.assertEqual(report["detected"], 0)

    def test_identity_pairs_stay_within_a_kind(self):
        self.identity("I exercise every morning before work", kind="preference")
        self.identity("I do not exercise every morning before work", kind="knowledge")
        self.assertEqual(self.scan()["detected"], 0)

    def test_rescan_is_idempotent(self):
        self.identity("I exercise every morning before work")
        self.identity("I do not exercise every morning before work")
        first = self.scan()
        second = self.scan()
        self.assertEqual(first["created"], 1)
        self.assertEqual(second["created"], 0)
        self.assertEqual(second["already_known"], 1)
        self.assertEqual(len(self.review.candidates(limit=50)), 1)

    def test_unadjudicated_candidates_leave_records_untouched(self):
        first = self.identity("I exercise every morning before work")
        second = self.identity("I do not exercise every morning before work")
        self.scan()
        self.assertEqual(self.status("identity", first), "approved")
        self.assertEqual(self.status("identity", second), "approved")
        self.assertNotIn("superseded", self.events("identity", first))
        self.assertNotIn("superseded", self.events("identity", second))
        self.assertEqual(self.review.adjudications(
            self.only_candidate()["id"]), [])

    def test_orphaned_candidate_is_pruned_when_record_is_deleted(self):
        first = self.identity("I exercise every morning before work")
        self.identity("I do not exercise every morning before work")
        self.scan()
        self.store.delete("identity", first)
        report = self.scan()
        self.assertEqual(report["pruned_orphaned"], 1)
        self.assertEqual(self.review.candidates(limit=50), [])

    # -- adjudication -----------------------------------------------------------

    def test_confirm_required_for_adjudication(self):
        self.identity("I exercise every morning before work")
        self.identity("I do not exercise every morning before work")
        self.scan()
        candidate = self.only_candidate()
        with self.assertRaises(ContradictionReviewError):
            self.review.adjudicate(candidate["id"], action="confirm",
                                   resolution="keep-a")
        with self.assertRaises(ContradictionReviewError):
            adjudicate_profile(self.home, candidate["id"], action="dismiss")
        self.assertEqual(self.only_candidate()["state"], "pending")

    def test_keep_a_supersedes_b_through_existing_machinery(self):
        first = self.identity("I exercise every morning before work")
        second = self.identity("I do not exercise every morning before work")
        self.scan()
        candidate = self.only_candidate()
        result = self.review.adjudicate(
            candidate["id"], action="confirm", resolution="keep-a",
            note="current habit wins", confirmed=True)
        self.assertTrue(result["records_changed"])
        self.assertEqual(result["superseded"], {"table": "identity", "id": second})
        self.assertEqual(self.status("identity", first), "approved")
        self.assertEqual(self.status("identity", second), "rejected")
        self.assertIn("superseded", self.events("identity", second))
        history = self.review.adjudications(candidate["id"])
        self.assertEqual(len(history), 1)
        entry = history[0]
        self.assertEqual(entry["candidate_id"], candidate["id"])
        self.assertEqual(entry["actor"], "owner")
        self.assertEqual(entry["action"], "confirm")
        self.assertEqual(entry["resolution"], "keep-a")
        self.assertEqual(entry["note"], "current habit wins")
        self.assertEqual(entry["superseded_id"], second)
        self.assertEqual(self.review.get(candidate["id"])["state"], "confirmed")

    def test_keep_b_supersedes_a_for_episodes(self):
        first = self.store.observe(
            "Synthetic gym", "I train at the synthetic gym every weekday.",
            tags=["health"], source="synthetic:test")
        second = self.store.observe(
            "Synthetic gym", "I do not train at the synthetic gym every weekday.",
            tags=["health"], source="synthetic:test")
        self.store.review_episode(first, "approved")
        self.store.review_episode(second, "approved")
        self.scan()
        candidate = self.only_candidate()
        self.review.adjudicate(candidate["id"], action="confirm",
                               resolution="keep-b", confirmed=True)
        self.assertEqual(self.status("episodes", first), "rejected")
        self.assertEqual(self.status("episodes", second), "approved")
        self.assertIn("superseded", self.events("episodes", first))

    def test_keep_both_leaves_both_approved_with_note(self):
        first = self.identity("My favorite drink is synthetic tea")
        second = self.identity("My favorite drink is synthetic coffee")
        self.scan()
        candidate = self.only_candidate()
        result = self.review.adjudicate(
            candidate["id"], action="confirm", resolution="keep-both",
            note="depends on the season", confirmed=True)
        self.assertFalse(result["records_changed"])
        self.assertIsNone(result["superseded"])
        self.assertEqual(self.status("identity", first), "approved")
        self.assertEqual(self.status("identity", second), "approved")
        history = self.review.adjudications(candidate["id"])
        self.assertEqual(history[0]["resolution"], "keep-both")
        self.assertEqual(history[0]["note"], "depends on the season")

    def test_dismiss_suppresses_reproposal_for_same_signal(self):
        self.identity("I exercise every morning before work")
        self.identity("I do not exercise every morning before work")
        self.scan()
        candidate = self.only_candidate()
        self.review.adjudicate(candidate["id"], action="dismiss",
                               note="tense differs; both true", confirmed=True)
        self.assertEqual(self.review.get(candidate["id"])["state"], "dismissed")
        report = self.scan()
        self.assertEqual(report["created"], 0)
        self.assertEqual(report["already_known"], 1)
        self.assertEqual(self.review.candidates(limit=50), [])
        dismissed = self.review.candidates(state="dismissed", limit=50)
        self.assertEqual(len(dismissed), 1)

    def test_defer_stays_actionable_and_untouched(self):
        first = self.identity("I exercise every morning before work")
        second = self.identity("I do not exercise every morning before work")
        self.scan()
        candidate = self.only_candidate()
        self.review.adjudicate(candidate["id"], action="defer", confirmed=True)
        parked = self.review.get(candidate["id"])
        self.assertEqual(parked["state"], "deferred")
        self.assertEqual(self.status("identity", first), "approved")
        self.assertEqual(self.status("identity", second), "approved")
        actionable = self.review.candidates(limit=50)
        self.assertEqual([c["id"] for c in actionable], [candidate["id"]])
        # A deferred candidate can still be adjudicated later.
        self.review.adjudicate(candidate["id"], action="dismiss", confirmed=True)
        self.assertEqual(self.review.get(candidate["id"])["state"], "dismissed")

    def test_stale_candidate_refuses_without_writes(self):
        first = self.identity("I exercise every morning before work")
        second = self.identity("I do not exercise every morning before work")
        self.scan()
        candidate = self.only_candidate()
        self.store.status(second, "rejected")  # changed outside adjudication
        with self.assertRaises(ContradictionReviewError):
            self.review.adjudicate(candidate["id"], action="confirm",
                                   resolution="keep-a", confirmed=True)
        self.assertEqual(self.status("identity", first), "approved")
        self.assertEqual(self.review.get(candidate["id"])["state"], "pending")
        self.assertEqual(self.review.adjudications(candidate["id"]), [])

    def test_double_adjudication_is_refused(self):
        self.identity("I exercise every morning before work")
        self.identity("I do not exercise every morning before work")
        self.scan()
        candidate = self.only_candidate()
        self.review.adjudicate(candidate["id"], action="dismiss", confirmed=True)
        with self.assertRaises(ContradictionReviewError):
            self.review.adjudicate(candidate["id"], action="dismiss", confirmed=True)


    # -- CLI / profile surface --------------------------------------------------

    def test_cli_scan_list_show_and_adjudicate(self):
        self.identity("I exercise every morning before work")
        self.identity("I do not exercise every morning before work")
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(["--home", str(self.home), "scan"])
        self.assertEqual(json.loads(out.getvalue())["created"], 1)

        listing = list_profile(self.home)
        self.assertFalse(listing["private_data_in_output"])
        blob = json.dumps(listing)
        self.assertNotIn("exercise every morning", blob)  # no record text/fragments
        candidate_id = listing["candidates"][0]["id"]

        with self.assertRaises(ContradictionReviewError):
            show_profile(self.home, candidate_id)  # private text needs --confirm
        shown = show_profile(self.home, candidate_id, confirmed=True)
        self.assertIn("exercise every morning", shown["record_a"]["text"])
        self.assertIn("do not exercise", shown["record_b"]["text"])

        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(["--home", str(self.home), "adjudicate", str(candidate_id),
                      "--action", "dismiss", "--note", "cli dismissal",
                      "--confirm"])
        result = json.loads(out.getvalue())
        self.assertEqual(result["state"], "dismissed")
        self.assertFalse(result["records_changed"])

    def test_cli_adjudicate_without_confirm_is_refused(self):
        self.identity("I exercise every morning before work")
        self.identity("I do not exercise every morning before work")
        scan_profile(self.home)
        candidate_id = list_profile(self.home)["candidates"][0]["id"]
        with self.assertRaises(ContradictionReviewError):
            cli_main(["--home", str(self.home), "adjudicate", str(candidate_id),
                      "--action", "confirm", "--keep", "a"])

    # -- desktop service ----------------------------------------------------------

    def test_desktop_service_scan_detail_and_adjudication(self):
        first = self.identity("I exercise every morning before work")
        second = self.identity("I do not exercise every morning before work")
        service = DesktopService(self.home)
        report = service.contradiction_candidates()
        self.assertEqual(report["scan"]["created"], 1)
        self.assertEqual(len(report["candidates"]), 1)
        candidate = report["candidates"][0]
        detail = service.contradiction_detail(candidate["id"])
        self.assertEqual(detail["record_a"]["id"], first)
        self.assertEqual(detail["record_b"]["id"], second)
        with self.assertRaises(Exception):
            service.adjudicate_contradiction(candidate["id"], "confirm",
                                             resolution="keep-a")
        result = service.adjudicate_contradiction(
            candidate["id"], "confirm", resolution="keep-b", confirmed=True)
        self.assertEqual(result["superseded"], {"table": "identity", "id": first})
        self.assertEqual(self.status("identity", second), "approved")


if __name__ == "__main__":
    unittest.main()
