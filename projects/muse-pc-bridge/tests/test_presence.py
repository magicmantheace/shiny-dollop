"""Presence tests (durable job runner release).

The game-detection logic is pure and tested here with stubbed
process lists: Steam/Battle.net LAUNCHERS must never count as
gaming, real game executables must. GPU contention combines the
game check with the nvidia-smi utilization threshold. The OS
probes themselves (tasklist, GetLastInputInfo, nvidia-smi) are
platform seams — on this POSIX test host they return None/[]
honestly rather than fabricating readings.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import presence  # noqa: E402


class DetectGamesTest(unittest.TestCase):
    def test_launchers_alone_are_not_gaming(self):
        names = ["steam.exe", "steamwebhelper.exe",
                 "battle.net.exe", "agent.exe",
                 "epicgameslauncher.exe", "leagueclient.exe"]
        self.assertEqual(presence.detect_games(names), [])

    def test_wow_is_gaming(self):
        self.assertEqual(presence.detect_games(["Wow.exe"]),
                         ["Wow.exe"])
        self.assertTrue(presence.detect_games(["wowclassic.exe"]))

    def test_known_games_detected(self):
        for exe in ("ffxiv_dx11.exe", "eldenring.exe", "bg3.exe",
                    "cyberpunk2077.exe", "witcher3.exe",
                    "Diablo IV.exe", "overwatch.exe",
                    "valorant.exe", "cs2.exe", "dota2.exe",
                    "gta5.exe", "rdr2.exe", "starfield.exe"):
            self.assertTrue(presence.detect_games([exe]), exe)

    def test_matching_is_anchored_and_case_insensitive(self):
        self.assertEqual(presence.detect_games(["WOW.EXE"]),
                         ["WOW.EXE"])
        self.assertEqual(presence.detect_games(["notwow.exe"]), [])
        self.assertEqual(presence.detect_games(["wow.exe.bak"]), [])
        self.assertEqual(presence.detect_games(["chrome.exe"]), [])

    def test_games_found_among_launchers(self):
        names = ["steam.exe", "steamwebhelper.exe", "Wow.exe"]
        self.assertEqual(presence.detect_games(names), ["Wow.exe"])

    def test_extra_patterns_extend_detection(self):
        import re
        extra = (re.compile(r"mygame\.exe"),)
        self.assertEqual(
            presence.detect_games(["mygame.exe"], extra),
            ["mygame.exe"])


class GpuContentionTest(unittest.TestCase):
    def test_game_means_contended(self):
        reason = presence.gpu_contention(
            process_names_fn=lambda: ["Wow.exe"],
            gpu_fn=lambda: None)
        self.assertIsNotNone(reason)
        self.assertIn("Wow.exe", reason)

    def test_launchers_only_not_contended(self):
        reason = presence.gpu_contention(
            process_names_fn=lambda: ["steam.exe", "agent.exe"],
            gpu_fn=lambda: {"utilization_pct": 10})
        self.assertIsNone(reason)

    def test_high_gpu_utilization_contends(self):
        reason = presence.gpu_contention(
            threshold_pct=90,
            process_names_fn=lambda: [],
            gpu_fn=lambda: {"utilization_pct": 95})
        self.assertIsNotNone(reason)
        self.assertIn("95", reason)

    def test_low_gpu_utilization_free(self):
        self.assertIsNone(presence.gpu_contention(
            threshold_pct=90,
            process_names_fn=lambda: [],
            gpu_fn=lambda: {"utilization_pct": 50}))

    def test_no_probes_no_contention_no_fabrication(self):
        self.assertIsNone(presence.gpu_contention(
            process_names_fn=lambda: [],
            gpu_fn=lambda: None))


class ParseNvidiaSmiTest(unittest.TestCase):
    def test_parses_reading(self):
        self.assertEqual(
            presence.parse_nvidia_smi("42, 1234, 12288"),
            {"utilization_pct": 42, "memory_used_mib": 1234,
             "memory_total_mib": 12288, "source": "nvidia-smi"})

    def test_garbage_is_none(self):
        self.assertIsNone(presence.parse_nvidia_smi(""))
        self.assertIsNone(presence.parse_nvidia_smi("N/A, N/A, N/A"))
        self.assertIsNone(presence.parse_nvidia_smi("42"))


class SnapshotTest(unittest.TestCase):
    def test_snapshot_shape_with_stubs(self):
        snap = presence.snapshot(
            process_names_fn=lambda: ["steam.exe", "Wow.exe"],
            gpu_fn=lambda: {"utilization_pct": 97},
            idle_fn=lambda: 12.5,
            foreground_fn=lambda: {"pid": 7, "title": "Game"})
        self.assertTrue(snap["gaming"])
        self.assertEqual(snap["games"], ["Wow.exe"])
        self.assertEqual(snap["input_idle_s"], 12.5)
        self.assertEqual(snap["foreground"]["pid"], 7)
        self.assertEqual(snap["gpu"]["utilization_pct"], 97)
        self.assertEqual(snap["processes_seen"], 2)
        self.assertEqual(snap["notes"], [])

    def test_snapshot_degrades_with_notes(self):
        snap = presence.snapshot(
            process_names_fn=lambda: [],
            gpu_fn=lambda: None, idle_fn=lambda: None,
            foreground_fn=lambda: None)
        self.assertFalse(snap["gaming"])
        self.assertIsNone(snap["input_idle_s"])
        self.assertIsNone(snap["gpu"])
        self.assertGreaterEqual(len(snap["notes"]), 3)


if __name__ == "__main__":
    unittest.main()
