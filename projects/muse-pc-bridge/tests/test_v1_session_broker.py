"""V1.1 tests: interactive session broker (Codex PR #47 fix).

The boot core runs in Windows session 0; desktop routes (screenshot,
input, UIA, clipboard, GUI spawn) belong to the interactive session.
These tests prove the broker mechanics on POSIX with a real helper
server and a real main server sharing one state dir + audit log:

- the helper serves ONLY desktop routes (everything else 404),
- the helper registers itself (fresh heartbeat, live pid) and
  unregisters on stop,
- the main agent proxies GUI spawns / process records to the
  helper, and both sides audit with via markers,
- a stale registration or session_broker=false means local service,
- a session-0 agent with no helper refuses desktop routes (501)
  instead of acting on the wrong desktop,
- the helper does not start a second UAC watch (no double audit).

Windows session behaviour itself — a SYSTEM core brokering to a
helper in the real logon session — is owner-PC verification, listed
in docs/TEST_PLAN.md.
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

TOKEN = "test-token-session-broker"
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


class BrokerFixture(unittest.TestCase):
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
        self.servers = []
        self.helpers = []
        self.spawned = []       # (port, process_id) to clean up
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
                # shutdown() blocks until serve_forever notices; run
                # it in a thread so one wedged server cannot hang
                # the whole suite in cleanup.
                stopper = threading.Thread(target=server.shutdown,
                                           daemon=True)
                stopper.start()
                stopper.join(timeout=5)
                server.server_close()
            except Exception:
                pass

    def start_main(self, **overrides):
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(Path(self.tmp.name)
                                     / "bridge-files"),
            "audit_log": str(self.audit_path),
            "state_dir": str(self.state_dir),
        })
        cfg.update(overrides)
        server = bridge_agent.create_server(cfg)
        self.servers.append(server)
        thread = threading.Thread(target=server.serve_forever,
                                  daemon=True)
        thread.start()
        return server, server.server_address[1]

    def start_helper(self):
        helper = session_helper.SessionHelper(
            self.config_path, self.state_dir).start()
        self.helpers.append(helper)
        return helper

    def spawn_sleeper(self, port):
        status, obj = call("POST", port, "/v1/processes", {
            "gui": True, "executable": sys.executable,
            "args": ["-c", SLEEPER]})
        self.assertEqual(status, 201, obj)
        self.spawned.append((port, obj["process_id"]))
        return obj


class DesktopRouteWhitelistTests(unittest.TestCase):
    def test_route_matrix(self):
        yes = [("GET", "/v1/screenshot"), ("POST", "/v1/input"),
               ("POST", "/v1/uia"), ("GET", "/v1/clipboard"),
               ("POST", "/v1/clipboard"), ("POST", "/v1/processes"),
               ("GET", "/v1/processes"),
               ("GET", "/v1/processes/abcdef012345"),
               ("POST", "/v1/processes/abcdef012345/kill")]
        no = [("GET", "/v1/status"), ("POST", "/v1/exec"),
              ("POST", "/v1/sessions"), ("GET", "/v1/file/list"),
              ("POST", "/v1/wol"), ("GET", "/v1/audit/tail"),
              ("POST", "/v1/update/stage"),
              ("DELETE", "/v1/processes/abcdef012345")]
        for method, route in yes:
            self.assertTrue(session_helper.is_desktop_route(
                method, route), (method, route))
        for method, route in no:
            self.assertFalse(session_helper.is_desktop_route(
                method, route), (method, route))


class HelperServerTests(BrokerFixture):
    def test_helper_serves_only_desktop_routes(self):
        helper = self.start_helper()
        status, obj = call("GET", helper.port, "/v1/status")
        self.assertEqual(status, 404)
        self.assertIn("not a desktop route", obj["error"])
        status, _ = call("POST", helper.port, "/v1/exec",
                         {"command": "echo hi"})
        self.assertEqual(status, 404)
        # A desktop route IS served: on Windows the clipboard
        # answers for real; off Windows it honestly 501s.
        status, obj = call("GET", helper.port, "/v1/clipboard")
        if bridge_agent.IS_WINDOWS:
            self.assertEqual(status, 200)
            self.assertIn("text", obj)
        else:
            self.assertEqual(status, 501)
            self.assertTrue(obj.get("platform_limited"))
        status, obj = call("GET", helper.port, "/v1/processes")
        self.assertEqual(status, 200)
        self.assertEqual(obj["processes"], [])
        # Auth still applies on the helper.
        status, _ = call("GET", helper.port, "/v1/processes",
                         token="wrong")
        self.assertEqual(status, 401)

    def test_registration_lifecycle(self):
        helper = self.start_helper()
        path = self.state_dir / bridge_agent.HELPER_REGISTRY_NAME
        self.assertTrue(path.exists())
        reg = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(reg["port"], helper.port)
        self.assertEqual(reg["pid"], os.getpid())
        self.assertIn("session_id", reg)
        self.assertLess(time.time() - reg["updated_at"], 5)
        helper.stop()
        self.helpers.remove(helper)
        self.assertFalse(path.exists())


class BrokerProxyTests(BrokerFixture):
    def test_gui_spawn_get_kill_proxied_to_helper(self):
        helper = self.start_helper()
        server, port = self.start_main()
        obj = self.spawn_sleeper(port)
        self.assertTrue(obj["gui"])
        self.assertTrue(obj["alive"])
        pid = obj["pid"]
        self.assertTrue(bridge_agent.pid_alive(pid))
        # The record lives with the HELPER, not the main agent.
        self.assertNotIn(obj["process_id"], server.core.processes)
        status, got = call("GET", port,
                           f"/v1/processes/{obj['process_id']}")
        self.assertEqual(status, 200)
        self.assertTrue(got["alive"])
        self.assertEqual(got["pid"], pid)
        status, killed = call(
            "POST", port, f"/v1/processes/{obj['process_id']}/kill")
        self.assertEqual(status, 200)
        self.assertTrue(killed["killed"])
        # Death is judged through the API: the helper's record polls
        # its Popen (reaping the child), while a raw os.kill(pid, 0)
        # from this test process would still see the zombie.
        deadline = time.time() + 10
        alive = True
        while time.time() < deadline and alive:
            _s, got = call("GET", port,
                           f"/v1/processes/{obj['process_id']}")
            alive = bool(got.get("alive"))
            if alive:
                time.sleep(0.1)
        self.assertFalse(alive)
        # Both sides audited the brokered spawn, marked as such.
        entries = [json.loads(line) for line in
                   self.audit_path.read_text(encoding="utf-8")
                   .splitlines() if line.strip()]
        vias = {e.get("via") for e in entries
                if e.get("path") == "/v1/processes"
                and e.get("method") == "POST"}
        self.assertIn("session-broker", vias)
        self.assertIn("session-helper", vias)

    def test_stale_registration_means_local_service(self):
        _server, port = self.start_main()
        (self.state_dir / bridge_agent.HELPER_REGISTRY_NAME).write_text(
            json.dumps({"port": 9, "pid": os.getpid(),
                        "session_id": 1,
                        "updated_at": time.time() - 3600}),
            encoding="utf-8")
        obj = self.spawn_sleeper(port)
        server = self.servers[0]
        self.assertIn(obj["process_id"], server.core.processes)

    def test_broker_disabled_means_local_service(self):
        self.start_helper()
        server, port = self.start_main(session_broker=False)
        obj = self.spawn_sleeper(port)
        self.assertIn(obj["process_id"], server.core.processes)


class SessionZeroBlockTests(BrokerFixture):
    """Simulate the session-0 core by patching the platform probes:
    desktop routes must 501 without a helper and proxy with one."""

    def setUp(self):
        super().setUp()
        self._real_session_id = bridge_agent.current_session_id
        self.addCleanup(self._unpatch)

    def _unpatch(self):
        bridge_agent.current_session_id = self._real_session_id

    def _patch_session_zero(self):
        # Only the session probe is patched: the block keys off the
        # session id alone (None off Windows never equals 0), and
        # patching IS_WINDOWS would corrupt unrelated platform
        # branches (pid probes, spawn flags) in the same process.
        bridge_agent.current_session_id = lambda: 0

    def test_desktop_routes_refused_in_session_zero(self):
        _server, port = self.start_main()
        self._patch_session_zero()
        status, obj = call("GET", port, "/v1/screenshot")
        self.assertEqual(status, 501)
        self.assertIn("session 0", obj["error"])
        status, obj = call("POST", port, "/v1/processes", {
            "gui": True, "executable": sys.executable,
            "args": ["-c", SLEEPER]})
        self.assertEqual(status, 501)
        self.assertIn("session 0", obj["error"])

    def test_desktop_routes_proxied_in_session_zero_with_helper(self):
        self.start_helper()     # registers with a non-0 session here
        _server, port = self.start_main()
        self._patch_session_zero()
        obj = self.spawn_sleeper(port)
        self.assertTrue(obj["alive"])
        self.assertNotIn(obj["process_id"],
                         self.servers[0].core.processes)


class HelperThreadTests(BrokerFixture):
    def test_helper_starts_no_second_uac_watch(self):
        # The watch thread exits instantly off Windows (run() is a
        # no-op there), so count watch STARTS by patching the entry
        # point create_server launches — the gate is what matters:
        # helper configs must not start it, normal configs must.
        started = []
        real_watch = bridge_agent._uac_watch
        bridge_agent._uac_watch = lambda core: started.append(core)
        try:
            helper_server = bridge_agent.create_server(
                session_helper.build_helper_config(self.config_path))
            try:
                self.assertEqual(started, [],
                                 "helper must not duplicate the "
                                 "UAC watch")
            finally:
                # Never served: server_close only — shutdown()
                # would block forever waiting for a serve_forever
                # loop that never ran.
                helper_server.server_close()
            _server, _port = self.start_main()
            self.assertEqual(len(started), 1)
        finally:
            bridge_agent._uac_watch = real_watch


if __name__ == "__main__":
    unittest.main()
