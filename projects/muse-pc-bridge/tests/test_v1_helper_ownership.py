"""V1.1 tests: single-helper ownership of the shared state dir
(Codex PR #47 finding).

Opening the avatar launcher twice against a running core used to
start TWO session helpers. Their heartbeats overwrote the same
session-helper.json while their process registries diverged, so a
process spawned through one helper vanished (404 / empty listing)
whenever the other's registration won the last heartbeat.

The contract proven here, at both layers that can start a helper:

- a second SessionHelper against the same state dir is refused
  (HelperOwnershipError) and the first helper's registration is
  untouched;
- the GUI attach path (supervisor_gui.start_attach_helper) reuses
  the live helper instead of starting another, and a process
  spawned through the surviving helper stays visible through the
  main agent;
- a STALE registration (dead heartbeat) does not block a fresh
  helper, and a stopped owner frees the state dir for the next one.

Ownership is an OS file lock held for the helper's lifetime, so a
crashed owner's lock dies with its process — no stale-lock janitor
is needed. POSIX runs prove the logic here; the Windows suite run
on the owner's PC is recorded in docs/TEST_PLAN.md.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402
import session_helper  # noqa: E402
import supervisor_gui  # noqa: E402

TOKEN = "test-token-helper-ownership"
SLEEPER = "import time; time.sleep(60)"


def call(method, port, path, payload=None, token=TOKEN):
    data = json.dumps(payload).encode("utf-8") \
        if payload is not None else None
    req = urllib.request.Request(
        f"http://127.0.0.1:{port}{path}", data=data, method=method,
        headers={"Authorization": f"Bearer {token}",
                 "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, {"raw": raw}


class OwnershipFixture(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.state_dir = root / "state"
        self.state_dir.mkdir()
        self.audit_path = root / "logs" / "audit.jsonl"
        self.config_path = root / "config.json"
        self.config_path.write_text(json.dumps({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(root / "bridge-files"),
            "audit_log": str(self.audit_path),
            "state_dir": str(self.state_dir),
        }), encoding="utf-8")
        self.helpers = []
        self.servers = []
        self.spawned = []
        self.addCleanup(self._cleanup)

    def _cleanup(self):
        for port, proc_id in self.spawned:
            try:
                call("POST", port, f"/v1/processes/{proc_id}/kill")
            except Exception:
                pass
        for helper in self.helpers:
            try:
                helper.stop()
            except Exception:
                pass
        for server in self.servers:
            try:
                stopper = threading.Thread(target=server.shutdown,
                                           daemon=True)
                stopper.start()
                stopper.join(timeout=5)
                server.server_close()
            except Exception:
                pass

    def registration(self):
        path = self.state_dir / bridge_agent.HELPER_REGISTRY_NAME
        return json.loads(path.read_text(encoding="utf-8"))

    def start_main(self):
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(Path(self.tmp.name)
                                     / "bridge-files"),
            "audit_log": str(self.audit_path),
            "state_dir": str(self.state_dir),
        })
        server = bridge_agent.create_server(cfg)
        self.servers.append(server)
        thread = threading.Thread(target=server.serve_forever,
                                  daemon=True)
        thread.start()
        return server.server_address[1]


class SessionHelperOwnershipTests(OwnershipFixture):
    def test_second_helper_refused_first_keeps_registration(self):
        first = session_helper.SessionHelper(
            self.config_path, self.state_dir).start()
        self.helpers.append(first)
        self.assertEqual(self.registration()["port"], first.port)

        intruder = session_helper.SessionHelper(
            self.config_path, self.state_dir)
        started = False
        try:
            intruder.start()
            started = True
        except Exception:
            started = False
        if started:   # pre-fix behaviour: keep the suite clean
            self.helpers.append(intruder)
        self.assertFalse(
            started,
            "a second session helper started against the same "
            "state dir; two helpers diverge process registries "
            "while overwriting one registration")
        # The first helper's registration is untouched (give a
        # heartbeat a chance to prove whose file it still is).
        time.sleep(0.2)
        self.assertEqual(self.registration()["port"], first.port)
        self.assertEqual(self.registration()["pid"], os.getpid())

    def test_second_helper_raises_ownership_error(self):
        first = session_helper.SessionHelper(
            self.config_path, self.state_dir).start()
        self.helpers.append(first)
        with self.assertRaises(session_helper.HelperOwnershipError):
            session_helper.SessionHelper(
                self.config_path, self.state_dir).start()

    def test_stopped_owner_frees_the_state_dir(self):
        first = session_helper.SessionHelper(
            self.config_path, self.state_dir).start()
        first.stop()
        second = session_helper.SessionHelper(
            self.config_path, self.state_dir).start()
        self.helpers.append(second)
        self.assertEqual(self.registration()["port"], second.port)


class GuiAttachOwnershipTests(OwnershipFixture):
    def test_attach_reuses_live_helper_and_processes_stay_visible(self):
        first = supervisor_gui.start_attach_helper(
            self.config_path, self.state_dir)
        self.assertIsNotNone(first)
        self.helpers.append(first)
        port_before = self.registration()["port"]
        self.assertEqual(port_before, first.port)

        second = supervisor_gui.start_attach_helper(
            self.config_path, self.state_dir)
        self.assertIsNone(
            second,
            "attach mode started a second helper against a live "
            "registration instead of reusing it")
        self.assertEqual(self.registration()["port"], port_before)

        # A process spawned through the surviving helper (brokered
        # by the main agent) stays visible: by id and in the
        # listing. With two helpers this lookup flipped to the
        # other registry and 404'd.
        port = self.start_main()
        status, obj = call("POST", port, "/v1/processes", {
            "gui": True, "executable": sys.executable,
            "args": ["-c", SLEEPER]})
        self.assertEqual(status, 201, obj)
        self.spawned.append((port, obj["process_id"]))
        status, got = call("GET", port,
                           f"/v1/processes/{obj['process_id']}")
        self.assertEqual(status, 200, got)
        self.assertTrue(got["alive"])
        status, listing = call("GET", port, "/v1/processes")
        self.assertEqual(status, 200)
        ids = {p["process_id"] for p in listing["processes"]}
        self.assertIn(obj["process_id"], ids)

    def test_stale_registration_does_not_block_attach(self):
        (self.state_dir / bridge_agent.HELPER_REGISTRY_NAME).write_text(
            json.dumps({"port": 9, "pid": os.getpid(),
                        "session_id": 1,
                        "started_at": time.time() - 3600,
                        "updated_at": time.time() - 3600}),
            encoding="utf-8")
        helper = supervisor_gui.start_attach_helper(
            self.config_path, self.state_dir)
        self.assertIsNotNone(
            helper, "a stale registration blocked a fresh helper")
        self.helpers.append(helper)
        self.assertEqual(self.registration()["port"], helper.port)


if __name__ == "__main__":
    unittest.main()
