"""V1.1 tests: audit coordination across agent + session helper
(Codex PR #47 finding).

The main agent and the session helper are separate BridgeCore
instances — in production, separate processes — appending to ONE
audit log. Each core's threading lock only serializes its own
writers, so two cores can both decide to rotate from the same stale
file state and shift the archives twice, discarding an archive that
a single rotation would have retained.

The race test primes the log and its archives with sentinel
entries, sets the rotation cap so exactly ONE of two concurrent
appends may rotate, widens the rename window (a short sleep before
the current -> .1 rename) so the second writer's stale rotation
decision lands mid-rotation, and asserts that every entry a correct
serialized run retains is still on disk afterwards. A second test
pins the plain sequential sharing behaviour.

Windows cross-process behaviour of the underlying file lock is
owner-PC verification, listed in docs/TEST_PLAN.md; these tests
prove the coordination logic where the suite runs.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

TOKEN = "test-token-audit-coordination"
TS = "2026-01-01T00:00:00.000Z"   # same length as utc_now_iso()
LINE = 120                        # chars per audit line


def _entry(marker: str) -> dict:
    """An audit entry whose serialized line is exactly LINE chars
    (the ts the core prepends has the same length as TS)."""
    entry = {"event": "race", "marker": marker, "pad": ""}
    probe = {"ts": TS}
    probe.update(entry)
    entry["pad"] = "x" * (LINE - len(json.dumps(probe)))
    return entry


def _line(marker: str) -> str:
    record = {"ts": TS}
    record.update(_entry(marker))
    line = json.dumps(record)
    assert len(line) == LINE
    return line


def _make_core(root: Path, name: str, audit_path: Path,
               max_bytes: int, keep: int) -> bridge_agent.BridgeCore:
    cfg = dict(bridge_agent.DEFAULT_CONFIG)
    cfg.update({
        "host": "127.0.0.1", "port": 0, "token": TOKEN,
        "allowed_file_root": str(root / "bridge-files"),
        "audit_log": str(audit_path),
        "state_dir": str(root / name),
        "audit_max_bytes": max_bytes, "audit_keep": keep,
    })
    return bridge_agent.BridgeCore(cfg)


def _markers_on_disk(audit: Path) -> set[str]:
    found = set()
    for suffix in ("", ".1", ".2", ".3"):
        try:
            lines = audit.with_name(audit.name + suffix) \
                .read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for line in lines:
            try:
                found.add(json.loads(line)["marker"])
            except (json.JSONDecodeError, KeyError):
                pass
    return found


class TwoCoreSequentialTests(unittest.TestCase):
    def test_two_cores_share_one_log_in_order(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        audit = root / "logs" / "audit.jsonl"
        core_a = _make_core(root, "agent-state", audit,
                            max_bytes=10 * 1024 * 1024, keep=3)
        core_b = _make_core(root, "helper-state", audit,
                            max_bytes=10 * 1024 * 1024, keep=3)
        for i in range(3):
            core_a.audit({"event": "test", "marker": f"A{i}"})
            core_b.audit({"event": "test", "marker": f"B{i}"})
        lines = audit.read_text(encoding="utf-8").splitlines()
        markers = [json.loads(line)["marker"] for line in lines]
        self.assertEqual(markers,
                         ["A0", "B0", "A1", "B1", "A2", "B2"])


class TwoCoreRotationRaceTests(unittest.TestCase):
    def test_concurrent_writers_rotate_once_between_them(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        audit = root / "logs" / "audit.jsonl"
        audit.parent.mkdir(parents=True)
        line_bytes = LINE + 1     # chars + the newline
        # Prime: the current log holds C1+C2, the archives R1/R2/R3.
        audit.write_text(_line("C1") + "\n" + _line("C2") + "\n",
                         encoding="utf-8")
        for suffix, marker in ((".1", "R1"), (".2", "R2"),
                               (".3", "R3")):
            audit.with_name(audit.name + suffix).write_text(
                _line(marker) + "\n", encoding="utf-8")
        # Cap = exactly the primed current size: the first append
        # must rotate (2 lines + 1 incoming > cap); once it has, the
        # fresh current holds a single line, so the second append
        # must NOT rotate (1 + 1 <= cap). A second rotation can only
        # come from a stale, uncoordinated decision.
        core_a = _make_core(root, "agent-state", audit,
                            max_bytes=2 * line_bytes, keep=3)
        core_b = _make_core(root, "helper-state", audit,
                            max_bytes=2 * line_bytes, keep=3)

        # Widen the race window: pause just before the rename that
        # moves the current log to .1, so the second writer takes
        # its rotation decision from the pre-rename state too.
        real_replace = os.replace

        def slow_replace(src, dst):
            if Path(dst).name == audit.name + ".1":
                time.sleep(0.25)
            return real_replace(src, dst)

        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def write(core, marker):
            try:
                barrier.wait(timeout=10)
                core.audit(_entry(marker))
            except Exception as exc:  # surfaced by the assert below
                errors.append(exc)

        os.replace = slow_replace
        try:
            threads = [threading.Thread(target=write,
                                        args=(core_a, "EA")),
                       threading.Thread(target=write,
                                        args=(core_b, "EB"))]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=30)
        finally:
            os.replace = real_replace
        self.assertEqual(errors, [])
        found = _markers_on_disk(audit)
        # R3 is the one legitimate discard (oldest archive at
        # keep=3). Everything else a serialized run retains must
        # still be on disk.
        for kept in ("C1", "C2", "R1", "R2", "EA", "EB"):
            self.assertIn(kept, found,
                          f"audit entry {kept} lost to the "
                          f"rotation race")


if __name__ == "__main__":
    unittest.main()
