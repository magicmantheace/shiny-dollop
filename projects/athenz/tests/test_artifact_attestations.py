"""Synthetic artifact attestation tests (v0.3). Temp profile dirs only."""
from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import sqlite3
import tempfile
import unittest

from athenz.artifact_attestations import (
    ArtifactAttestationStore, AttestationError)
from athenz.artifact_attestations_cli import main as cli_main


PASS_SUITE = '''
import unittest

class PassingTests(unittest.TestCase):
    def test_one(self):
        self.assertEqual(1, 1)

    def test_two(self):
        self.assertTrue(True)
'''

FAIL_SUITE = '''
import unittest

class MixedTests(unittest.TestCase):
    def test_ok(self):
        self.assertTrue(True)

    def test_bad(self):
        self.assertEqual(1, 2)

    def test_skipped(self):
        self.skipTest('synthetic skip')
'''


class ArtifactAttestationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.artifact_path = self.base / 'bundle.bin'
        self.artifact_path.write_bytes(b'synthetic artifact bytes\x00\x01\x02')
        self.store = ArtifactAttestationStore(self.home)
        self.pass_dir = self.base / 'suite_pass'
        self.pass_dir.mkdir()
        (self.pass_dir / 'test_passing.py').write_text(PASS_SUITE)
        self.fail_dir = self.base / 'suite_fail'
        self.fail_dir.mkdir()
        (self.fail_dir / 'test_mixed.py').write_text(FAIL_SUITE)

    def register(self, **kwargs):
        kwargs.setdefault('source', 'synthetic test artifact')
        return self.store.register(self.artifact_path, **kwargs)

    # -- registry ------------------------------------------------------

    def test_register_id_is_independent_sha256(self):
        entry = self.register()
        expected = hashlib.sha256(self.artifact_path.read_bytes()).hexdigest()
        self.assertEqual(entry['artifact_id'], expected)
        self.assertEqual(entry['size'], self.artifact_path.stat().st_size)
        self.assertFalse(entry['already_registered'])
        again = self.register()
        self.assertTrue(again['already_registered'])
        self.assertEqual(again['artifact_id'], expected)
        self.assertEqual(len(self.store.list()), 1)

    def test_register_missing_file_refuses(self):
        with self.assertRaises(AttestationError):
            self.store.register(self.base / 'nope.bin')

    # -- attestation issuance ---------------------------------------------

    def test_attest_passing_suite_records_real_result(self):
        entry = self.register()
        att = self.store.attest(entry['artifact_id'], self.pass_dir)
        self.assertEqual(att['result']['tests_run'], 2)
        self.assertEqual(att['result']['passed'], 2)
        self.assertEqual(att['result']['failed'], 0)
        self.assertTrue(att['result']['successful'])
        self.assertEqual(att['suite_name'], 'unittest-discover')
        self.assertTrue(att['environment']['python_version'])
        self.assertTrue(att['environment']['platform'])

    def test_attest_failing_suite_is_recorded_as_failed(self):
        entry = self.register()
        att = self.store.attest(entry['artifact_id'], self.fail_dir)
        self.assertEqual(att['result']['tests_run'], 3)
        self.assertEqual(att['result']['passed'], 1)
        self.assertEqual(att['result']['failed'], 1)
        self.assertEqual(att['result']['skipped'], 1)
        self.assertFalse(att['result']['successful'])
        self.assertTrue(any('test_bad' in t
                            for t in att['result']['failed_test_ids']))
        report = self.store.verify(entry['artifact_id'])
        self.assertEqual(report['attestations'][0]['status'],
                         'suite_result_failed')
        self.assertFalse(report['ok'])

    def test_attest_unregistered_artifact_refuses(self):
        with self.assertRaises(AttestationError):
            self.store.attest('0' * 64, self.pass_dir)
        self.assertEqual(self.store.list(), [])

    def test_attest_refuses_when_bytes_changed(self):
        entry = self.register()
        self.artifact_path.write_bytes(b'different bytes entirely')
        with self.assertRaises(AttestationError):
            self.store.attest(entry['artifact_id'], self.pass_dir)
        self.assertEqual(
            self.store.get(entry['artifact_id'])['attestations'], [])

    # -- verification -------------------------------------------------------

    def test_verify_happy_path(self):
        entry = self.register()
        self.store.attest(entry['artifact_id'], self.pass_dir)
        report = self.store.verify(entry['artifact_id'])
        self.assertEqual(report['registry_status'], 'ok')
        self.assertEqual(report['artifact_status'], 'present')
        self.assertTrue(report['identity_match'])
        self.assertEqual(report['attestations'][0]['status'], 'valid')
        self.assertTrue(report['ok'])

    def test_verify_detects_artifact_mismatch(self):
        entry = self.register()
        self.store.attest(entry['artifact_id'], self.pass_dir)
        self.artifact_path.write_bytes(b'tampered artifact bytes')
        report = self.store.verify(entry['artifact_id'])
        self.assertEqual(report['artifact_status'], 'present')
        self.assertFalse(report['identity_match'])
        self.assertEqual(report['attestations'][0]['status'],
                         'artifact_mismatch')
        self.assertFalse(report['ok'])

    def test_verify_detects_tampered_attestation_record(self):
        entry = self.register()
        att = self.store.attest(entry['artifact_id'], self.pass_dir)
        db = sqlite3.connect(self.home / 'identity.sqlite3')
        try:
            row = db.execute(
                'SELECT result FROM artifact_attestations WHERE id=?',
                (att['id'],)).fetchone()
            forged = json.loads(row[0])
            forged['tests_run'] = 999
            forged['passed'] = 999
            db.execute(
                'UPDATE artifact_attestations SET result=? WHERE id=?',
                (json.dumps(forged, sort_keys=True), att['id']))
            db.commit()
        finally:
            db.close()
        report = self.store.verify(entry['artifact_id'])
        self.assertEqual(report['attestations'][0]['status'],
                         'record_tampered')
        self.assertFalse(report['ok'])

    def test_verify_missing_artifact_file(self):
        entry = self.register()
        self.store.attest(entry['artifact_id'], self.pass_dir)
        self.artifact_path.unlink()
        report = self.store.verify(entry['artifact_id'])
        self.assertEqual(report['artifact_status'], 'missing')
        self.assertIsNone(report['current_artifact_id'])
        self.assertEqual(report['attestations'][0]['status'],
                         'artifact_missing')
        self.assertFalse(report['ok'])

    # -- portability ----------------------------------------------------------

    def test_export_import_roundtrip_into_fresh_profile(self):
        entry = self.register()
        self.store.attest(entry['artifact_id'], self.pass_dir)
        self.store.attest(entry['artifact_id'], self.fail_dir)
        doc = self.store.export(entry['artifact_id'])
        self.assertNotIn('location', json.dumps(doc))
        other = ArtifactAttestationStore(self.base / 'other-profile')
        imported = other.import_document(doc)
        self.assertEqual(imported['artifact_id'], entry['artifact_id'])
        self.assertEqual(imported['imported_attestations'], 2)
        self.assertIsNone(imported['location'])
        report = other.verify(entry['artifact_id'])
        # No bytes in the new profile yet: records intact, file missing.
        self.assertEqual(report['registry_status'], 'ok')
        self.assertEqual(report['artifact_status'], 'missing')
        # Registering the same bytes binds the location to the same ID,
        # after which the imported attestations verify against them.
        rebound = other.register(self.artifact_path)
        self.assertEqual(rebound['artifact_id'], entry['artifact_id'])
        report = other.verify(entry['artifact_id'])
        statuses = {a['status'] for a in report['attestations']}
        self.assertEqual(statuses, {'valid', 'suite_result_failed'})

    def test_import_tampered_document_rejected_wholesale(self):
        entry = self.register()
        self.store.attest(entry['artifact_id'], self.pass_dir)
        doc = self.store.export(entry['artifact_id'])
        other = ArtifactAttestationStore(self.base / 'other-profile')
        forged = json.loads(json.dumps(doc))
        forged['attestations'][0]['result']['passed'] = 42
        with self.assertRaises(AttestationError):
            other.import_document(forged)
        self.assertEqual(other.list(), [])
        forged2 = json.loads(json.dumps(doc))
        forged2['artifact']['name'] = 'forged name'
        with self.assertRaises(AttestationError):
            other.import_document(forged2)
        self.assertEqual(other.list(), [])

    def test_import_duplicate_artifact_refused(self):
        entry = self.register()
        doc = self.store.export(entry['artifact_id'])
        other = ArtifactAttestationStore(self.base / 'other-profile')
        other.import_document(doc)
        with self.assertRaises(AttestationError):
            other.import_document(doc)

    # -- CLI -----------------------------------------------------------------

    def test_cli_register_attest_verify(self):
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(['--home', str(self.home), 'register',
                      '--path', str(self.artifact_path),
                      '--source', 'cli smoke'])
        entry = json.loads(out.getvalue())
        artifact_id = entry['artifact_id']
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(['--home', str(self.home), 'attest',
                      '--artifact', artifact_id,
                      '--suite-dir', str(self.pass_dir)])
        att = json.loads(out.getvalue())
        self.assertTrue(att['result']['successful'])
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(['--home', str(self.home), 'verify', artifact_id])
        report = json.loads(out.getvalue())
        self.assertTrue(report['ok'])


if __name__ == '__main__':
    unittest.main()
