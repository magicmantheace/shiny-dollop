"""Synthetic local-connector tests (v0.8). Temp profile dirs only."""
from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import wave

from athenz.local_connectors import (ConnectorError, LocalConnectorStore,
                                     LEGACY_VOICE_PROVENANCE)
from athenz.local_connectors_cli import main as cli_main
from athenz.local_notes import MAX_NOTE_BYTES, LocalNotes


class ConnectorGateTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.notes_dir = self.base / 'notes'
        self.notes_dir.mkdir()
        self.store = LocalConnectorStore(self.home)

    def opt_in_notes(self, tiers=('read',), **kwargs):
        kwargs.setdefault('config', {'directory': str(self.notes_dir)})
        return self.store.opt_in('local-notes', tiers=list(tiers),
                                 confirmed=True, **kwargs)

    def test_unknown_integration_refused_with_distinct_reason(self):
        result = self.store.require('no-such-integration', 'read')
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'unknown_integration')
        self.assertIsNone(result['state'])
        self.assertIsNone(self.store.get('no-such-integration'))
        events = self.store.audit('no-such-integration')
        self.assertEqual([e['event'] for e in events], ['check'])
        self.assertEqual(events[0]['reason'], 'unknown_integration')

    def test_default_state_is_not_opted_in(self):
        view = self.store.get('local-notes')
        self.assertEqual(view['state'], 'not_opted_in')
        self.assertEqual(view['approved_tiers'], [])
        result = self.store.require('local-notes', 'read')
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'not_opted_in')

    def test_opt_in_requires_confirm(self):
        with self.assertRaises(ConnectorError):
            self.store.opt_in('local-notes', tiers=['read'],
                              config={'directory': str(self.notes_dir)})
        self.assertEqual(self.store.get('local-notes')['state'],
                         'not_opted_in')

    def test_opt_in_read_allows_read_and_refuses_write(self):
        self.opt_in_notes()
        read = self.store.require('local-notes', 'read')
        self.assertTrue(read['allowed'])
        self.assertEqual(read['reason'], 'allowed')
        write = self.store.require('local-notes', 'write')
        self.assertFalse(write['allowed'])
        self.assertEqual(write['reason'], 'tier_not_approved')
        self.assertEqual(self.store.get('local-notes')['approved_tiers'],
                         ['read'])

    def test_write_tier_is_a_separate_opt_in(self):
        self.opt_in_notes(('read',))
        self.opt_in_notes(('write',), config=None)
        self.assertEqual(self.store.get('local-notes')['approved_tiers'],
                         ['read', 'write'])
        self.assertTrue(self.store.require('local-notes', 'write')['allowed'])

    def test_opt_in_undeclared_tier_refused(self):
        # voice-transcription declares only the read tier.
        with self.assertRaises(ConnectorError):
            self.store.opt_in('voice-transcription', tiers=['write'],
                              confirmed=True)

    def test_local_notes_opt_in_requires_directory(self):
        with self.assertRaises(ConnectorError):
            self.store.opt_in('local-notes', tiers=['read'], confirmed=True)
        with self.assertRaises(ConnectorError):
            self.store.opt_in('local-notes', tiers=['read'], confirmed=True,
                              config={'directory': str(self.base / 'missing')})

    def test_disable_blocks_the_next_check_immediately(self):
        self.opt_in_notes()
        self.assertTrue(self.store.require('local-notes', 'read')['allowed'])
        # Disable is frictionless: no confirmation argument exists.
        view = self.store.disable('local-notes')
        self.assertEqual(view['state'], 'disabled')
        self.assertEqual(view['approved_tiers'], [])
        result = self.store.require('local-notes', 'read')
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'disabled')
        # A fresh store instance on the same profile sees it too:
        # approvals are read from the store at check time, never cached.
        fresh = LocalConnectorStore(self.home)
        self.assertEqual(fresh.require('local-notes', 'read')['reason'],
                         'disabled')

    def test_reenable_after_disable_requires_fresh_opt_in(self):
        self.opt_in_notes(('read', 'write'))
        self.store.disable('local-notes')
        with self.assertRaises(ConnectorError):
            self.store.opt_in('local-notes', tiers=['read'])
        view = self.opt_in_notes(('read',))
        self.assertEqual(view['state'], 'enabled')
        # The previously approved write tier was cleared by the disable
        # and is NOT silently restored by re-approving read.
        self.assertEqual(
            self.store.require('local-notes', 'write')['reason'],
            'tier_not_approved')

    def test_audit_records_checks_and_state_changes(self):
        self.opt_in_notes()
        self.store.require('local-notes', 'read')
        self.store.require('local-notes', 'write')
        self.store.disable('local-notes')
        events = self.store.audit('local-notes')
        kinds = [e['event'] for e in events]
        self.assertEqual(kinds, ['opted_in', 'check', 'check', 'disabled'])
        self.assertTrue(events[1]['allowed'])
        self.assertFalse(events[2]['allowed'])
        self.assertEqual(events[2]['reason'], 'tier_not_approved')

    def test_voice_legacy_seed_on_first_consult(self):
        view = self.store.get('voice-transcription')
        self.assertEqual(view['state'], 'enabled')
        self.assertEqual(view['approved_tiers'], ['read'])
        self.assertEqual(view['provenance'], LEGACY_VOICE_PROVENANCE)
        self.assertTrue(
            self.store.require('voice-transcription', 'read')['allowed'])
        seeded = [e for e in self.store.audit('voice-transcription')
                  if e['event'] == 'seeded']
        # Repeated consultation never re-seeds.
        self.store.list()
        self.store.get('voice-transcription')
        seeded = [e for e in self.store.audit('voice-transcription')
                  if e['event'] == 'seeded']
        self.assertEqual(len(seeded), 1)
        self.assertEqual(seeded[0]['reason'], LEGACY_VOICE_PROVENANCE)

    def test_voice_after_disable_behaves_like_any_integration(self):
        self.store.get('voice-transcription')  # trigger the legacy seed
        self.store.disable('voice-transcription')
        result = self.store.require('voice-transcription', 'read')
        self.assertEqual(result['reason'], 'disabled')
        with self.assertRaises(ConnectorError):
            self.store.opt_in('voice-transcription', tiers=['read'])
        view = self.store.opt_in('voice-transcription', tiers=['read'],
                                 confirmed=True)
        self.assertEqual(view['provenance'], 'owner-opt-in')
        self.assertTrue(
            self.store.require('voice-transcription', 'read')['allowed'])

    def test_owner_registered_integration_starts_not_opted_in(self):
        with self.assertRaises(ConnectorError):
            self.store.register_integration(
                'synthetic-feeds', display_name='Synthetic feeds',
                kind='local-files', tiers=['read'])
        view = self.store.register_integration(
            'synthetic-feeds', display_name='Synthetic feeds',
            kind='local-files', tiers=['read'], confirmed=True)
        self.assertFalse(view['builtin'])
        self.assertEqual(view['state'], 'not_opted_in')
        self.assertEqual(
            self.store.require('synthetic-feeds', 'read')['reason'],
            'not_opted_in')
        self.store.opt_in('synthetic-feeds', tiers=['read'], confirmed=True)
        self.assertTrue(
            self.store.require('synthetic-feeds', 'read')['allowed'])
        ids = [row['id'] for row in self.store.list()]
        self.assertIn('synthetic-feeds', ids)

    def test_list_shows_every_integration_with_state(self):
        rows = {row['id']: row for row in self.store.list()}
        self.assertEqual(rows['voice-transcription']['state'], 'enabled')
        self.assertEqual(rows['local-notes']['state'], 'not_opted_in')
        self.assertEqual(rows['local-notes']['declared_tiers'],
                         ['read', 'write'])


class LocalNotesTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.notes_dir = self.base / 'notes'
        self.notes_dir.mkdir()
        self.store = LocalConnectorStore(self.home)
        self.notes = LocalNotes(self.home)

    def opt_in(self, tiers=('read',)):
        return self.store.opt_in(
            'local-notes', tiers=list(tiers),
            config={'directory': str(self.notes_dir)}, confirmed=True)

    def test_operations_refuse_before_opt_in(self):
        (self.notes_dir / 'a.md').write_text('synthetic')
        with self.assertRaises(ConnectorError):
            self.notes.list_notes()
        with self.assertRaises(ConnectorError):
            self.notes.read_note('a.md')
        with self.assertRaises(ConnectorError):
            self.notes.append_note('b.md', 'synthetic')

    def test_list_and_read_end_to_end(self):
        (self.notes_dir / 'alpha.md').write_text('# Alpha\n')
        (self.notes_dir / 'beta.txt').write_text('plain text')
        (self.notes_dir / 'code.py').write_text('not a note')
        subdir = self.notes_dir / 'sub'
        subdir.mkdir()
        (subdir / 'nested.md').write_text('not listed: no recursion')
        self.opt_in()
        listed = self.notes.list_notes()
        self.assertEqual([row['name'] for row in listed],
                         ['alpha.md', 'beta.txt'])
        read = self.notes.read_note('alpha.md')
        self.assertEqual(read['text'], '# Alpha\n')
        with self.assertRaises(ConnectorError):
            self.notes.read_note('code.py')
        with self.assertRaises(ConnectorError):
            self.notes.read_note('missing.md')

    def test_write_tier_create_only_never_overwrites(self):
        self.opt_in(('read',))
        with self.assertRaises(ConnectorError):
            self.notes.append_note('new.md', 'first version')
        self.opt_in(('write',))
        created = self.notes.append_note('new.md', 'first version')
        self.assertTrue(created['created'])
        self.assertEqual((self.notes_dir / 'new.md').read_text(),
                         'first version')
        with self.assertRaises(ConnectorError):
            self.notes.append_note('new.md', 'hostile replacement')
        self.assertEqual((self.notes_dir / 'new.md').read_text(),
                         'first version')
        self.assertEqual(self.notes.read_note('new.md')['text'],
                         'first version')

    def test_path_escapes_are_refused(self):
        outside = self.base / 'secret.txt'
        outside.write_text('outside the notes directory')
        self.opt_in(('read', 'write'))
        for name in ('../secret.txt', '..\\secret.txt', 'sub/inner.md',
                     '/etc/passwd', '.hidden.md'):
            with self.assertRaises(ConnectorError, msg=name):
                self.notes.read_note(name)
        with self.assertRaises(ConnectorError):
            self.notes.append_note('../evil.md', 'escape attempt')
        self.assertFalse((self.base / 'evil.md').exists())

    def test_symlink_escape_is_refused(self):
        outside = self.base / 'target.txt'
        outside.write_text('symlink target outside the directory')
        link = self.notes_dir / 'link.txt'
        try:
            link.symlink_to(outside)
        except OSError:
            self.skipTest('symlinks unavailable on this platform')
        self.opt_in()
        listed = [row['name'] for row in self.notes.list_notes()]
        self.assertNotIn('link.txt', listed)
        with self.assertRaises(ConnectorError):
            self.notes.read_note('link.txt')

    def test_oversize_note_is_refused(self):
        big = self.notes_dir / 'big.md'
        big.write_bytes(b'x' * (MAX_NOTE_BYTES + 1))
        self.opt_in()
        rows = {row['name']: row for row in self.notes.list_notes()}
        self.assertFalse(rows['big.md']['readable'])
        with self.assertRaises(ConnectorError):
            self.notes.read_note('big.md')
        with self.assertRaises(ConnectorError):
            self.notes.append_note('also-big.md', 'x' * (MAX_NOTE_BYTES + 1))

    def test_disable_blocks_notes_immediately(self):
        (self.notes_dir / 'a.md').write_text('synthetic')
        self.opt_in()
        self.assertEqual(len(self.notes.list_notes()), 1)
        self.store.disable('local-notes')
        with self.assertRaises(ConnectorError):
            self.notes.list_notes()


class VoiceWiringTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.wav = self.base / 'synthetic.wav'
        self.model = self.base / 'offline-model'
        self.model.mkdir()
        (self.model / 'config.json').write_text('{"model":"synthetic"}')
        (self.model / 'model.bin').write_bytes(b'fictional-private-weights')
        with wave.open(str(self.wav), 'wb') as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(16000)
            stream.writeframes(b'\x00\x00' * 16000)

    def fake_engine(self, *segments):
        class Engine:
            def transcribe(self, path, **kwargs):
                return (iter(segments), {'language': 'en'})
        return Engine()

    def run_transcribe(self):
        from types import SimpleNamespace
        from athenz.voice import main as voice_main
        engine = self.fake_engine(SimpleNamespace(text='SYNTHETIC WORDS'))
        with mock.patch.dict(os.environ, {'ATHENZ_HOME': str(self.home)}), \
                mock.patch('athenz.voice._load_engine', return_value=engine), \
                mock.patch('builtins.print') as printed:
            voice_main(['transcribe', str(self.wav), '--model',
                        str(self.model), '--confirm'])
        return json.loads(printed.call_args.args[0])

    def test_legacy_default_leaves_transcribe_working(self):
        report = self.run_transcribe()
        self.assertEqual(report['transcript'], 'SYNTHETIC WORDS')
        self.assertFalse(report['stored_in_profile'])
        view = LocalConnectorStore(self.home).get('voice-transcription')
        self.assertEqual(view['provenance'], LEGACY_VOICE_PROVENANCE)

    def test_disabled_voice_refuses_before_any_transcription(self):
        from athenz.voice import VoiceError, main as voice_main
        LocalConnectorStore(self.home).disable('voice-transcription')
        with mock.patch.dict(os.environ, {'ATHENZ_HOME': str(self.home)}), \
                mock.patch('athenz.voice._load_engine',
                           side_effect=AssertionError(
                               'model must not load when disabled')):
            with self.assertRaisesRegex(VoiceError, 'disabled') as caught:
                voice_main(['transcribe', str(self.wav), '--model',
                            str(self.model), '--confirm'])
        self.assertIn('voice-transcription', str(caught.exception))
        events = LocalConnectorStore(self.home).audit('voice-transcription')
        checks = [e for e in events if e['event'] == 'check']
        self.assertEqual(checks[-1]['reason'], 'disabled')
        self.assertFalse(checks[-1]['allowed'])


class ConnectorCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.notes_dir = self.base / 'notes'
        self.notes_dir.mkdir()

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(['--home', str(self.home), *argv])
        return json.loads(out.getvalue())

    def test_control_plane_and_notes_end_to_end_via_cli(self):
        with self.assertRaises(ConnectorError):
            self.run_cli('opt-in', 'local-notes', '--tier', 'read',
                         '--directory', str(self.notes_dir))
        view = self.run_cli('opt-in', 'local-notes', '--tier', 'read',
                            '--directory', str(self.notes_dir), '--confirm')
        self.assertEqual(view['state'], 'enabled')
        self.assertEqual(view['approved_tiers'], ['read'])
        listed = self.run_cli('list')
        states = {row['id']: row['state'] for row in listed}
        self.assertEqual(states['local-notes'], 'enabled')
        # Append needs the write tier, which read opt-in never grants.
        with self.assertRaises(ConnectorError):
            self.run_cli('notes', 'append', 'cli-note.md',
                         '--text', 'written through the CLI')
        self.run_cli('opt-in', 'local-notes', '--tier', 'write', '--confirm')
        created = self.run_cli('notes', 'append', 'cli-note.md',
                               '--text', 'written through the CLI')
        self.assertTrue(created['created'])
        read = self.run_cli('notes', 'read', 'cli-note.md')
        self.assertEqual(read['text'], 'written through the CLI')
        names = [row['name'] for row in self.run_cli('notes', 'list')]
        self.assertEqual(names, ['cli-note.md'])
        self.run_cli('disable', 'local-notes')
        with self.assertRaises(ConnectorError):
            self.run_cli('notes', 'list')
        events = self.run_cli('audit', '--integration', 'local-notes')
        kinds = [e['event'] for e in events]
        self.assertIn('opted_in', kinds)
        self.assertIn('disabled', kinds)
        self.assertIn('check', kinds)


if __name__ == '__main__':
    unittest.main()
