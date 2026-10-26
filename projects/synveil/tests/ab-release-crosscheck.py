#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Cross-check: releases packaged by tools/ab_release.py (the exact
bytes the guest agent verifies in-crate) must verify under the host
transaction core tools/ab_update.py, and the guest trust record the
packager writes must carry the pinned key in the guest's shape.
This is the format-interop evidence between the host model and the
installed-system implementation; the guest-side Ed25519
verification itself is covered by the veil-core unit tests and the
QEMU proof.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import ab_release
import ab_update


class ReleaseCrosscheck(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name)
        self.trust = base / "trust"
        self.payload = base / "gen.efi"
        self.payload.write_bytes(b"UKI-BYTES" * 4096)
        self.private, self.public_hex = ab_release.ensure_keypair(self.trust)
        # Host-core trust directory: PEM + the 3-field record the
        # host core pins (the guest record adds the raw public key).
        self.host_trust = base / "host-trust"
        self.host_trust.mkdir()
        subprocess.run(["openssl", "pkey", "-in", str(self.private),
                        "-pubout", "-out", str(self.host_trust / "publisher.pem")],
                       check=True)
        (self.host_trust / "publisher.json").write_text(json.dumps({
            "schema": "synveil.ab-trust/v1",
            "key_id": ab_release.KEY_ID,
            "development": True,
        }) + "\n")

    def stage_dir(self, metadata, signature):
        directory = Path(self.tmp.name) / "release"
        directory.mkdir(exist_ok=True)
        (directory / "synveil.release.json").write_bytes(
            json.dumps(metadata, indent=2).encode() + b"\n")
        (directory / "synveil.release.sig").write_bytes(signature)
        (directory / "synveil.release.bin").write_bytes(self.payload.read_bytes())
        return directory

    def test_packager_output_verifies_in_host_core(self):
        metadata = ab_release.build_metadata(self.payload, 2)
        metadata_bytes = json.dumps(metadata, indent=2).encode() + b"\n"
        signature = ab_release.sign_metadata(self.private, metadata_bytes)
        directory = self.stage_dir(metadata, signature)
        trust = ab_update.load_trust(self.host_trust)
        data, fd = ab_update.signed_release(
            directory, "synveil", trust, metadata["issued_at"] + 60)
        os.close(fd)
        self.assertEqual(data["version"], 2)
        self.assertEqual(data["sha256"], metadata["sha256"])

    def test_corrupt_signature_rejected_by_host_core(self):
        metadata = ab_release.build_metadata(self.payload, 2)
        metadata_bytes = json.dumps(metadata, indent=2).encode() + b"\n"
        signature = bytearray(ab_release.sign_metadata(self.private, metadata_bytes))
        signature[10] ^= 0x01
        directory = self.stage_dir(metadata, bytes(signature))
        trust = ab_update.load_trust(self.host_trust)
        with self.assertRaises(ab_update.UpdateError):
            ab_update.signed_release(
                directory, "synveil", trust, metadata["issued_at"] + 60)

    def test_guest_trust_record_shape(self):
        record = json.loads((self.trust / "publisher.json").read_text())
        self.assertEqual(record, {
            "schema": "synveil.ab-trust/v1",
            "key_id": "synveil-dev-2026-01",
            "development": True,
            "public_key_hex": self.public_hex,
        })
        self.assertEqual(len(self.public_hex), 64)


if __name__ == "__main__":
    unittest.main()
