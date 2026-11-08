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
appends may rotate, and forces the fatal interleave: the first
writer is parked between its rotation size check and the archive
renames (its decision is already taken from the primed state)
until the second writer has rotated and appended in full — the
first writer's stale rotation then shifts the archives a second
time and overwrites a retained archive. It asserts that every
entry a correct serialized run retains is still on disk
afterwards. A second test pins the plain sequential sharing
behaviour.

Coordination is two layers: a per-path threading lock shared by
every core in the process, and an OS file lock on a sidecar for
the cross-process case (the production split: agent process vs
helper process). The shared threading lock exists so co-hosted
cores never depend on platform file-lock subtleties — Windows
byte-range locks have per-handle semantics quite unlike flock,
including dropping a process's locks when any of its handles to
the file closes. These tests prove the coordination end to end
where the suite runs; the owner-PC run of this same test file is
recorded in docs/TEST_PLAN.md.
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
        # Prime: the current log holds C1+C2, the archives R1/R2/R3.
        audit.write_text(_line("C1") + "\n" + _line("C2") + "\n",
                         encoding="utf-8")
        for suffix, marker in ((".1", "R1"), (".2", "R2"),
                               (".3", "R3")):
            audit.with_name(audit.name + suffix).write_text(
                _line(marker) + "\n", encoding="utf-8")
        # The cap comes from MEASURED on-disk sizes, not arithmetic:
        # a line occupies LINE+1 bytes on POSIX but LINE+2 on
        # Windows (text mode writes CRLF), while the core accounts
        # an incoming line as len(line)+1. (An arithmetic cap of
        # 2*(LINE+1) sat one byte per line too low on Windows and
        # made the second append rotate legitimately — the first
        # owner-PC failure of this test was that accounting, not the
        # coordination.) Capped at the primed current size, the
        # first append necessarily rotates (size + incoming >
        # size); afterwards the fresh current holds one line, whose
        # on-disk size + incoming stays under the cap on both
        # platforms — so a second rotation can only come from a
        # stale, uncoordinated decision.
        cap = audit.stat().st_size
        self.assertGreaterEqual(
            audit.with_name(audit.name + ".1").stat().st_size,
            LINE + 1)
        core_a = _make_core(root, "agent-state", audit,
                            max_bytes=cap, keep=3)
        core_b = _make_core(root, "helper-state", audit,
                            max_bytes=cap, keep=3)

        # Force the fatal interleave deterministically: park the
        # FIRST writer inside its rotation size check — the stat
        # result is already computed from the primed state, but not
        # yet returned — until the second writer has rotated and
        # appended in full. Uncoordinated, the first writer then
        # acts on its stale decision: its renames shift the archives
        # a second time and overwrite a retained archive.
        # Coordinated (the fix), the second writer blocks on the
        # audit locks and cannot complete, so the park simply times
        # out and the first writer finishes alone and correctly.
        real_stat = os.stat
        release = threading.Event()
        park_lock = threading.Lock()
        parked_once = [False]

        def stat_wrapper(path, *args, **kwargs):
            result = real_stat(path, *args, **kwargs)
            try:
                is_audit = os.fspath(path) == str(audit)
            except TypeError:
                is_audit = False
            if is_audit:
                with park_lock:
                    first = not parked_once[0]
                    parked_once[0] = True
                if first:
                    release.wait(timeout=3)
            return result

        barrier = threading.Barrier(2)
        errors: list[Exception] = []

        def write(core, marker):
            try:
                barrier.wait(timeout=10)
                core.audit(_entry(marker))
            except Exception as exc:  # surfaced by the assert below
                errors.append(exc)
            finally:
                release.set()

        os.stat = stat_wrapper
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
            os.stat = real_stat
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
