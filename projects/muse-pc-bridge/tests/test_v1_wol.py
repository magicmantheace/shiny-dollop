"""V1.1 tests: Wake-on-LAN (POST /v1/wol).

The agent sends a magic packet by UDP broadcast. Where the
environment permits UDP sends, the live tests point the agent at a
UDP listener on loopback and verify the exact 102 bytes arrive;
where it does not (this build VM's sandbox refuses ALL outbound UDP,
even plain loopback), those tests skip with the reason stated and
the route is still exercised end-to-end with the sender stubbed.
Whether a real sleeping machine wakes is a property of that
machine's BIOS/NIC/OS settings — owner-PC verification, listed in
docs/TEST_PLAN.md. The bridge cannot wake its own host; that
limitation is documented, not tested around.
"""

from __future__ import annotations

import importlib.util
import json
import socket
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))
sys.path.insert(0, str(PROJECT_DIR / "client"))

from unittest import mock  # noqa: E402

import bridge_agent  # noqa: E402
import bridge_client  # noqa: E402

TOKEN = "test-token-v11-wol"
MAC = "AA:BB:CC:DD:EE:FF"


def load_wol_send():
    path = PROJECT_DIR / "scripts" / "wol-send.py"
    spec = importlib.util.spec_from_file_location("wol_send", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HttpClient:
    def __init__(self, base: str):
        self.base = base

    def request(self, method, path, payload=None, token=TOKEN):
        headers = {}
        if token is not None:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base + path, data=data,
                                     headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                return exc.code, json.loads(body)
            except json.JSONDecodeError:
                return exc.code, {"raw": body}


class PacketShapeTests(unittest.TestCase):
    def test_normalize_mac_forms(self):
        for raw in ("AA:BB:CC:DD:EE:FF", "aa-bb-cc-dd-ee-ff",
                    "aabbccddeeff", "Aa:Bb:Cc:Dd:Ee:Ff"):
            self.assertEqual(bridge_agent.normalize_mac(raw), MAC)

    def test_normalize_mac_rejects_garbage(self):
        for bad in ("", "AA:BB:CC:DD:EE", "GG:BB:CC:DD:EE:FF",
                    "AA:BB:CC:DD:EE:FF:00", None, 42, "hello"):
            with self.assertRaises(ValueError, msg=repr(bad)):
                bridge_agent.normalize_mac(bad)

    def test_magic_packet_layout(self):
        packet = bridge_agent.build_magic_packet("aabbccddeeff")
        self.assertEqual(len(packet), 102)
        self.assertEqual(packet[:6], b"\xff" * 6)
        raw = bytes.fromhex("AABBCCDDEEFF")
        for i in range(16):
            self.assertEqual(packet[6 + i * 6:12 + i * 6], raw)

    def test_validate_payload_defaults(self):
        mac, broadcast, port = bridge_agent.validate_wol_payload(
            {"mac": "aa-bb-cc-dd-ee-ff"})
        self.assertEqual((mac, broadcast, port),
                         (MAC, "255.255.255.255", 9))

    def test_validate_payload_rejects(self):
        for payload in ({"mac": "nope"},
                        {"mac": MAC, "port": 0},
                        {"mac": MAC, "port": 65536},
                        {"mac": MAC, "port": "9"},
                        {"mac": MAC, "port": True},
                        {"mac": MAC, "broadcast": "not-an-ip"},
                        {"mac": MAC, "broadcast": 7}):
            with self.assertRaises(ValueError, msg=repr(payload)):
                bridge_agent.validate_wol_payload(payload)

    def test_standalone_sender_shares_the_packet_shape(self):
        wol_send = load_wol_send()
        self.assertEqual(wol_send.build_magic_packet(MAC),
                         bridge_agent.build_magic_packet(MAC))
        self.assertEqual(wol_send.normalize_mac("aa-bb-cc-dd-ee-ff"), MAC)
        with self.assertRaises(ValueError):
            wol_send.normalize_mac("nope")


class WolRouteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        cfg = dict(bridge_agent.DEFAULT_CONFIG)
        cfg.update({
            "host": "127.0.0.1", "port": 0, "token": TOKEN,
            "allowed_file_root": str(root / "bridge-files"),
            "audit_log": str(root / "logs" / "audit.jsonl"),
            "state_dir": str(root / "state"),
        })
        cls.server = bridge_agent.create_server(cfg)
        cls.port = cls.server.server_address[1]
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()
        cls.http = HttpClient(f"http://127.0.0.1:{cls.port}")
        cls.audit_log = root / "logs" / "audit.jsonl"
        # UDP listener standing in for a sleeping machine's NIC.
        cls.listener = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        cls.listener.bind(("127.0.0.1", 0))
        cls.listener.settimeout(10)
        cls.listen_port = cls.listener.getsockname()[1]
        # One probe decides whether live-delivery tests can run in
        # this environment at all (the build VM's sandbox refuses
        # every outbound UDP send with EPERM, loopback included).
        cls.udp_ok = True
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            probe.sendto(b"probe", ("127.0.0.1", cls.listen_port))
            cls.listener.recvfrom(64)
        except OSError:
            cls.udp_ok = False
        finally:
            probe.close()

    @classmethod
    def tearDownClass(cls):
        cls.listener.close()
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def wol_payload(self, **extra):
        payload = {"mac": "aa-bb-cc-dd-ee-ff",
                   "broadcast": "127.0.0.1", "port": self.listen_port}
        payload.update(extra)
        return payload

    def drain_listener(self):
        """Read one datagram; fail the test if none arrives."""
        try:
            data, _addr = self.listener.recvfrom(2048)
        except socket.timeout:
            self.fail("no magic packet arrived at the listener")
        return data

    def test_wol_route_with_sender_stubbed(self):
        # Environment-independent: proves the route validates, calls
        # the sender with the canonical values, returns its result,
        # and writes the audit line. The real send path is covered by
        # PacketShapeTests (packet bytes) and, where UDP is allowed,
        # the live tests below.
        sent = {}

        def fake_send(mac, broadcast, port):
            sent.update(mac=mac, broadcast=broadcast, port=port)
            return {"mac": mac, "broadcast": broadcast, "port": port,
                    "bytes": 102}

        with mock.patch.object(bridge_agent, "send_magic_packet",
                               fake_send):
            status, obj = self.http.request("POST", "/v1/wol",
                                            self.wol_payload())
        self.assertEqual(status, 200, obj)
        self.assertEqual(sent, {"mac": MAC, "broadcast": "127.0.0.1",
                                "port": self.listen_port})
        self.assertEqual(obj["bytes"], 102)
        lines = self.audit_log.read_text(encoding="utf-8").splitlines()
        wol_lines = [ln for ln in lines if "wol magic packet" in ln]
        self.assertTrue(wol_lines, lines[-3:])
        entry = json.loads(wol_lines[-1])
        self.assertEqual(entry["status"], 200)
        self.assertIn(MAC, entry["summary"])

    def test_wol_sends_the_exact_packet(self):
        if not self.udp_ok:
            self.skipTest("environment refuses outbound UDP sends "
                          "(sandbox EPERM); live delivery unverified here")
        status, obj = self.http.request("POST", "/v1/wol",
                                        self.wol_payload())
        self.assertEqual(status, 200, obj)
        self.assertEqual(obj["mac"], MAC)
        self.assertEqual(obj["broadcast"], "127.0.0.1")
        self.assertEqual(obj["port"], self.listen_port)
        self.assertEqual(obj["bytes"], 102)
        self.assertEqual(self.drain_listener(),
                         bridge_agent.build_magic_packet(MAC))

    def test_wol_via_client_library(self):
        if not self.udp_ok:
            self.skipTest("environment refuses outbound UDP sends "
                          "(sandbox EPERM); live delivery unverified here")
        client = bridge_client.BridgeClient(
            f"http://127.0.0.1:{self.port}", TOKEN)
        obj = client.wol(MAC, broadcast="127.0.0.1",
                         port=self.listen_port)
        self.assertEqual(obj["mac"], MAC)
        self.assertEqual(self.drain_listener(),
                         bridge_agent.build_magic_packet(MAC))

    def test_wol_requires_auth(self):
        status, _obj = self.http.request("POST", "/v1/wol",
                                         self.wol_payload(), token=None)
        self.assertEqual(status, 401)
        status, _obj = self.http.request("POST", "/v1/wol",
                                         self.wol_payload(), token="wrong")
        self.assertEqual(status, 401)

    def test_wol_rejects_bad_requests(self):
        for payload in ({"mac": "nope", "broadcast": "127.0.0.1",
                         "port": self.listen_port},
                        {"broadcast": "127.0.0.1", "port": self.listen_port},
                        {"mac": MAC, "port": 0},
                        {"mac": MAC, "broadcast": "not-an-ip"}):
            status, obj = self.http.request("POST", "/v1/wol", payload)
            self.assertEqual(status, 400, (payload, obj))
            self.assertIn("error", obj)

    def test_wol_capability_advertised(self):
        status, obj = self.http.request("GET", "/v1/status")
        self.assertEqual(status, 200)
        self.assertIn("wol", obj["capabilities"])
        self.assertEqual(obj["version"], bridge_agent.VERSION)


if __name__ == "__main__":
    unittest.main()
