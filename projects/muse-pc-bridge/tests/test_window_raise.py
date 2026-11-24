"""Raise-window tests (durable job runner release).

pick_window is pure and tested directly. The platform raise
itself is Windows-only: off Windows it must refuse honestly
(WindowUnavailable), never pretend. The hard rule behind the
feature — never minimize/move/resize ANY other window — is a
property of the Windows implementation (documented in
docs/JOB_RUNNER.md) and is verified on the owner's PC, not here.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import window_raise  # noqa: E402

WINDOWS = [
    {"hwnd": 1, "pid": 100, "title": "Editor - notes.txt",
     "visible": True},
    {"hwnd": 2, "pid": 200, "title": "Game", "visible": True},
    {"hwnd": 3, "pid": 200, "title": "", "visible": False},
    {"hwnd": 4, "pid": 300, "title": "game settings", "visible": False},
]


class PickWindowTest(unittest.TestCase):
    def test_by_pid(self):
        win = window_raise.pick_window(WINDOWS, pid=100)
        self.assertEqual(win["hwnd"], 1)

    def test_by_pid_prefers_visible(self):
        win = window_raise.pick_window(WINDOWS, pid=200)
        self.assertEqual(win["hwnd"], 2)

    def test_by_title_substring_case_insensitive(self):
        win = window_raise.pick_window(WINDOWS, title="NOTES")
        self.assertEqual(win["hwnd"], 1)

    def test_by_title_prefers_visible_match(self):
        win = window_raise.pick_window(WINDOWS, title="game")
        self.assertEqual(win["hwnd"], 2)

    def test_no_match_is_none(self):
        self.assertIsNone(window_raise.pick_window(WINDOWS, pid=999))
        self.assertIsNone(
            window_raise.pick_window(WINDOWS, title="missing"))
        self.assertIsNone(window_raise.pick_window([], pid=1))

    def test_exactly_one_selector(self):
        with self.assertRaises(ValueError):
            window_raise.pick_window(WINDOWS)
        with self.assertRaises(ValueError):
            window_raise.pick_window(WINDOWS, pid=1, title="x")


@unittest.skipIf(window_raise.IS_WINDOWS,
                 "off-Windows refusal only applies off Windows")
class RaiseUnavailableTest(unittest.TestCase):
    def test_raise_window_refuses_off_windows(self):
        with self.assertRaises(window_raise.WindowUnavailable):
            window_raise.raise_window(pid=100)


if __name__ == "__main__":
    unittest.main()
