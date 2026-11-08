"""Smoke tests for the GUI supervisor shell.

Import-level only: creating a real Tk window needs a display and is
verified on the owner's PC (see docs/MUSE_HANDOFF.md), never claimed
from a headless run. What is checked here: the module imports cleanly
without side effects, and every art key display_state can emit has a
committed animation asset beside the agent.
"""
import sys
import unittest
from pathlib import Path

AGENT_DIR = Path(__file__).resolve().parent.parent / "agent"
sys.path.insert(0, str(AGENT_DIR))

import display_state  # noqa: E402

ART_KEYS = {"idle", "working", "session", "connecting", "celebrate",
            "alert"}


class SupervisorGuiSmokeTests(unittest.TestCase):
    def test_module_imports_without_creating_a_window(self):
        import supervisor_gui  # noqa: F401
        self.assertTrue(hasattr(supervisor_gui, "main"))
        self.assertTrue(hasattr(supervisor_gui, "AvatarWindow"))

    def test_every_art_key_has_an_asset(self):
        for key in ART_KEYS:
            path = AGENT_DIR / "assets" / "avatar" / f"{key}.gif"
            self.assertTrue(path.exists(), f"missing asset: {path}")
            self.assertGreater(path.stat().st_size, 1000,
                               f"asset suspiciously small: {path}")

    def test_every_asset_declares_a_transparent_colour(self):
        # The floating window is colour-key transparent, so the GIFs
        # themselves must carry transparency: a Graphic Control
        # Extension (0x21 0xF9 0x04) whose packed byte has the
        # transparent-colour flag (bit 0) set. Byte-level check —
        # rendering is verified on the owner's PC.
        for key in ART_KEYS:
            data = (AGENT_DIR / "assets" / "avatar"
                    / f"{key}.gif").read_bytes()
            found = False
            idx = 0
            while True:
                idx = data.find(b"\x21\xf9\x04", idx)
                if idx < 0:
                    break
                if data[idx + 3] & 0x01:
                    found = True
                    break
                idx += 1
            self.assertTrue(found,
                            f"{key}.gif has no transparent colour")

    def test_display_state_only_emits_known_art_keys(self):
        cases = [
            ({"state": "running"}, {"jobs_running": 0,
                                    "sessions_open": 0,
                                    "processes_alive": 0}, {}),
            ({"state": "running"}, {"jobs_running": 1,
                                    "sessions_open": 0,
                                    "processes_alive": 0}, {}),
            ({"state": "running"}, {"jobs_running": 0,
                                    "sessions_open": 1,
                                    "processes_alive": 0}, {}),
            ({"state": "restarting"}, None, {}),
            ({"state": "update_apply_failed"},
             {"jobs_running": 0, "sessions_open": 0,
              "processes_alive": 0}, {}),
        ]
        for sup, agt, upd in cases:
            view = display_state.resolve_display(sup, agt, upd, now=100.0)
            self.assertIn(view["art"], ART_KEYS)


if __name__ == "__main__":
    unittest.main()
