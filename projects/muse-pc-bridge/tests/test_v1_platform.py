"""V1-S2 tests: screenshot/input/clipboard/UIA platform services.

The image encoders are pure Python and fully tested here. The capture
and injection endpoints are Windows-only: on the dev VM they must
report 501 + platform_limited and show up in /v1/status accordingly;
on Windows (owner PC) the screenshot path is exercised for real.
"""

from __future__ import annotations

import json
import struct
import sys
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import zlib
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_DIR / "agent"))

import bridge_agent  # noqa: E402

TOKEN = "test-token-v1-platform"
ON_WINDOWS = sys.platform.startswith("win")


class EncoderTests(unittest.TestCase):
    def test_png_roundtrip_structure(self):
        # 2x1 pixels: red, green (RGBA)
        rgba = bytes([255, 0, 0, 255, 0, 255, 0, 255])
        png = bridge_agent.encode_png(2, 1, rgba)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        # Walk chunks: IHDR must declare 2x1, color type 6 (RGBA).
        pos = 8
        idat = b""
        ihdr = None
        while pos < len(png):
            length = struct.unpack(">I", png[pos:pos + 4])[0]
            typ = png[pos + 4:pos + 8]
            data = png[pos + 8:pos + 8 + length]
            if typ == b"IHDR":
                ihdr = struct.unpack(">IIBBBBB", data)
            elif typ == b"IDAT":
                idat += data
            pos += 12 + length
        self.assertIsNotNone(ihdr)
        self.assertEqual((ihdr[0], ihdr[1], ihdr[3]), (2, 1, 6))
        raw = zlib.decompress(idat)
        self.assertEqual(raw, b"\x00" + rgba)   # filter 0 + the row

    def test_png_rejects_wrong_buffer_size(self):
        with self.assertRaises(ValueError):
            bridge_agent.encode_png(2, 2, b"\x00" * 10)

    def test_bmp_structure(self):
        bgra = bytes([0, 0, 255, 255])  # one blue pixel (BGRA)
        bmp = bridge_agent.encode_bmp(1, 1, bgra)
        self.assertTrue(bmp.startswith(b"BM"))
        size, = struct.unpack("<I", bmp[2:6])
        self.assertEqual(size, len(bmp))
        offset, = struct.unpack("<I", bmp[10:14])
        self.assertEqual(offset, 54)
        self.assertEqual(bmp[54:], bgra)

    def test_bgra_to_rgba_swaps_and_forces_alpha(self):
        bgra = bytes([10, 20, 30, 0, 40, 50, 60, 0])
        rgba = bridge_agent.bgra_to_rgba(bgra)
        self.assertEqual(rgba, bytes([30, 20, 10, 255, 60, 50, 40, 255]))

    def test_png_roundtrip_real_capture_size(self):
        # Regression: the live-PC staging failure (HTTP 500 on
        # ?format=png) appeared only at real capture dimensions.
        # Exercise the full BGRA->RGBA->PNG path at 1536x864 (the
        # staged size) and decode the result end to end.
        import binascii
        w, h = 1536, 864
        bgra = bytes(range(256)) * (w * h * 4 // 256)
        rgba = bridge_agent.bgra_to_rgba(bgra)
        png = bridge_agent.encode_png(w, h, rgba)
        self.assertTrue(png.startswith(b"\x89PNG\r\n\x1a\n"))
        pos = 8
        idat = b""
        ihdr = None
        while pos < len(png):
            length = struct.unpack(">I", png[pos:pos + 4])[0]
            typ = png[pos + 4:pos + 8]
            data = png[pos + 8:pos + 8 + length]
            crc, = struct.unpack(">I", png[pos + 8 + length:
                                            pos + 12 + length])
            self.assertEqual(crc, binascii.crc32(typ + data) & 0xFFFFFFFF)
            if typ == b"IHDR":
                ihdr = struct.unpack(">IIBBBBB", data)
            elif typ == b"IDAT":
                idat += data
            pos += 12 + length
        self.assertIsNotNone(ihdr)
        self.assertEqual((ihdr[0], ihdr[1], ihdr[3]), (w, h, 6))
        stride = w * 4
        expected = b"".join(b"\x00" + rgba[y * stride:(y + 1) * stride]
                            for y in range(h))
        self.assertEqual(zlib.decompress(idat), expected)


class CaptureSignatureTests(unittest.TestCase):
    """Regression guard for the live-PC screenshot HTTP 500
    ("argument 1: OverflowError: int too long to convert"): the GDI
    capture functions round-trip pointer-sized handles, so every
    signature capture_screen relies on must be declared with
    c_void_p handle slots. Undeclared ctypes signatures convert
    Python ints through the 32-bit Windows C long and raise on
    handle values above INT_MAX. The capture itself is Windows-only,
    so this test drives the declaration routine with stand-in
    function objects and pins the declared table."""

    def test_capture_signatures_declared(self):
        import ctypes
        import types

        def fake_dll(*names):
            return types.SimpleNamespace(
                **{name: types.SimpleNamespace() for name in names})

        user32 = fake_dll("GetDC", "ReleaseDC", "GetSystemMetrics")
        gdi32 = fake_dll("CreateCompatibleDC", "CreateCompatibleBitmap",
                         "SelectObject", "BitBlt", "GetDIBits",
                         "DeleteObject", "DeleteDC")
        bridge_agent._declare_capture_signatures(user32, gdi32)
        P, I, U, UL = (ctypes.c_void_p, ctypes.c_int, ctypes.c_uint,
                       ctypes.c_ulong)
        expected = {
            "GetDC": ([P], P),
            "ReleaseDC": ([P, P], I),
            "GetSystemMetrics": ([I], I),
            "CreateCompatibleDC": ([P], P),
            "CreateCompatibleBitmap": ([P, I, I], P),
            "SelectObject": ([P, P], P),
            "BitBlt": ([P, I, I, I, I, P, I, I, UL], I),
            "GetDIBits": ([P, P, U, U, P, P, U], I),
            "DeleteObject": ([P], I),
            "DeleteDC": ([P], I),
        }
        funcs = {}
        for dll in (user32, gdi32):
            for name in expected:
                if hasattr(dll, name):
                    funcs[name] = getattr(dll, name)
        self.assertEqual(set(funcs), set(expected))
        for name, (argtypes, restype) in expected.items():
            with self.subTest(function=name):
                self.assertEqual(funcs[name].argtypes, argtypes)
                self.assertIs(funcs[name].restype, restype)


class PlatformEndpointTests(unittest.TestCase):
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
        cls.base = f"http://127.0.0.1:{cls.server.server_address[1]}"
        cls.thread = threading.Thread(target=cls.server.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.core.log_stop()
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.tmp.cleanup()

    def request(self, method, path, payload=None):
        headers = {"Authorization": f"Bearer {TOKEN}"}
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

    def test_capabilities_reflect_platform(self):
        status, obj = self.request("GET", "/v1/status")
        self.assertEqual(status, 200)
        for cap in ("jobs", "processes", "sessions", "files.chunked",
                    "files.hash", "audit.tail"):
            self.assertIn(cap, obj["capabilities"])
        if ON_WINDOWS:
            self.assertIn("screenshot", obj["capabilities"])
            self.assertEqual(obj["platform_limited"], [])
        else:
            self.assertIn("screenshot", obj["platform_limited"])
            self.assertNotIn("screenshot", obj["capabilities"])

    @unittest.skipIf(ON_WINDOWS, "POSIX-only expectation")
    def test_screenshot_501_off_windows(self):
        status, obj = self.request("GET", "/v1/screenshot")
        self.assertEqual(status, 501)
        self.assertTrue(obj["platform_limited"])

    @unittest.skipIf(ON_WINDOWS, "POSIX-only expectation")
    def test_input_501_off_windows(self):
        status, obj = self.request("POST", "/v1/input",
                                   {"actions": [{"type": "mouse_pos"}]})
        self.assertEqual(status, 501)
        self.assertTrue(obj["platform_limited"])

    @unittest.skipIf(ON_WINDOWS, "POSIX-only expectation")
    def test_clipboard_501_off_windows(self):
        status, obj = self.request("GET", "/v1/clipboard")
        self.assertEqual(status, 501)

    @unittest.skipIf(ON_WINDOWS, "POSIX-only expectation")
    def test_uia_501_off_windows(self):
        status, obj = self.request("POST", "/v1/uia", {"action": "windows"})
        self.assertEqual(status, 501)

    @unittest.skipUnless(ON_WINDOWS, "Windows-only real capture")
    def test_screenshot_real_png(self):
        import base64
        import hashlib
        status, obj = self.request("GET", "/v1/screenshot")
        self.assertEqual(status, 200)
        self.assertEqual(obj["format"], "png")
        data = base64.b64decode(obj["content_b64"])
        self.assertTrue(data.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertEqual(hashlib.sha256(data).hexdigest(), obj["sha256"])
        self.assertGreater(obj["width"], 0)
        self.assertGreater(obj["height"], 0)

    def test_screenshot_bad_format_is_400(self):
        status, _ = self.request("GET", "/v1/screenshot?format=tiff")
        self.assertEqual(status, 400)

    def test_input_requires_actions(self):
        status, _ = self.request("POST", "/v1/input", {"actions": []})
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
