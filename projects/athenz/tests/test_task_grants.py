"""Synthetic standing-grant tests (slice A2). Temp profile dirs only."""
from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest

from athenz.task_grants import GrantError, TaskGrantStore
from athenz.task_grants_cli import main as cli_main, parser


class TaskGrantTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = self.base / 'repo'
        self.repo.mkdir()
        self.store = TaskGrantStore(self.home)

    def create(self, **overrides):
        kwargs = dict(
            objective='Synthetic objective', repository=self.repo,
            queue_item_ids=['roadmap-1'], task_classes=['implement', 'test'],
            allowed_files=['athenz/*.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=2, max_test_runs=3, max_retries_per_task=1,
            max_wall_clock_seconds=600, duration_seconds=3600,
            confirmed=True)
        kwargs.update(overrides)
        return self.store.create(**kwargs)

    def check(self, grant_id, **kwargs):
        kwargs.setdefault('repository', self.repo)
        return self.store.authorize(grant_id, **kwargs)

    def test_creation_requires_confirm(self):
        with self.assertRaises(GrantError):
            self.create(confirmed=False)
        self.assertEqual(self.store.list(), [])

    def test_default_deny_without_grant(self):
        result = self.check('grant-missing', task_class='implement',
                            file='athenz/x.py', tool='edit')
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'grant_not_found')
        audit = self.store.audit('grant-missing')
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]['event'], 'check')
        self.assertFalse(audit[0]['allowed'])

    def test_create_then_allow_in_scope(self):
        grant = self.create()
        self.assertEqual(grant['state'], 'active')
        result = self.check(grant['id'], task_class='implement',
                            file='athenz/x.py', tool='edit')
        self.assertTrue(result['allowed'])
        self.assertEqual(result['reason'], 'allowed')

    def test_provenance_is_recorded(self):
        grant = self.create()
        self.assertEqual(grant['queue_item_ids'], ['roadmap-1'])
        self.assertEqual(grant['objective'], 'Synthetic objective')

    def test_deny_out_of_scope_file(self):
        grant = self.create()
        result = self.check(grant['id'], file='docs/secret.md', tool='edit')
        self.assertFalse(result['allowed'])
        self.assertEqual(result['reason'], 'file_out_of_scope')
        escape = self.check(grant['id'], file='../outside.py', tool='edit')
        self.assertEqual(escape['reason'], 'file_out_of_scope')

    def test_deny_out_of_scope_tool_and_task_class(self):
        grant = self.create()
        tool = self.check(grant['id'], tool='shell')
        self.assertEqual(tool['reason'], 'tool_not_permitted')
        klass = self.check(grant['id'], task_class='release-prep')
        self.assertEqual(klass['reason'], 'task_class_not_permitted')

    def test_deny_other_repository(self):
        grant = self.create()
        other = self.base / 'other'
        other.mkdir()
        result = self.store.authorize(grant['id'], repository=other,
                                      tool='edit')
        self.assertEqual(result['reason'], 'repository_out_of_scope')

    def test_network_denied_by_default_and_allowlist_enforced(self):
        grant = self.create()
        result = self.check(grant['id'], network_target='example.com')
        self.assertEqual(result['reason'], 'network_not_permitted')
        listed = self.create(network_policy='allowlist',
                             network_allowlist=['example.com'])
        ok = self.check(listed['id'], network_target='example.com')
        self.assertTrue(ok['allowed'])
        no = self.check(listed['id'], network_target='other.example')
        self.assertEqual(no['reason'], 'network_target_not_allowed')

    def test_pause_denies_and_resume_restores(self):
        grant = self.create()
        self.store.pause(grant['id'])
        result = self.check(grant['id'], tool='edit')
        self.assertEqual(result['reason'], 'grant_paused')
        with self.assertRaises(GrantError):
            self.store.resume(grant['id'])  # resume needs the owner action
        self.store.resume(grant['id'], confirmed=True)
        self.assertTrue(self.check(grant['id'], tool='edit')['allowed'])

    def test_revoke_is_permanent(self):
        grant = self.create()
        self.store.revoke(grant['id'], confirmed=True)
        result = self.check(grant['id'], tool='edit')
        self.assertEqual(result['reason'], 'grant_revoked')
        with self.assertRaises(GrantError):
            self.store.resume(grant['id'], confirmed=True)

    def test_expired_grant_denies(self):
        grant = self.create(duration_seconds=1)
        # Backdate expiry deterministically instead of sleeping.
        with self.store._open() as store:
            with store.db:
                store.db.execute(
                    "UPDATE task_grants SET expires_at='2000-01-01T00:00:00+00:00'"
                    ' WHERE id=?', (grant['id'],))
        result = self.check(grant['id'], tool='edit')
        self.assertEqual(result['reason'], 'grant_expired')
        self.assertEqual(self.store.get(grant['id'])['state'], 'expired')
        events = [e['event'] for e in self.store.audit(grant['id'])]
        self.assertIn('expired', events)

    def test_budget_exhaustion_denies(self):
        grant = self.create()
        self.assertTrue(self.check(grant['id'], new_task=True)['allowed'])
        self.assertTrue(self.check(grant['id'], new_task=True)['allowed'])
        result = self.check(grant['id'], new_task=True)
        self.assertEqual(result['reason'], 'budget_tasks_exhausted')
        tests = self.create()
        for _ in range(3):
            self.assertTrue(self.check(tests['id'], test_run=True)['allowed'])
        result = self.check(tests['id'], test_run=True)
        self.assertEqual(result['reason'], 'budget_test_runs_exhausted')

    def test_retry_and_wall_clock_budgets(self):
        grant = self.create()
        self.assertTrue(self.check(
            grant['id'], retry=True, task_id='task-1')['allowed'])
        result = self.check(grant['id'], retry=True, task_id='task-1')
        self.assertEqual(result['reason'], 'budget_retries_exceeded')
        # A different task has its own retry budget.
        self.assertTrue(self.check(
            grant['id'], retry=True, task_id='task-2')['allowed'])
        clock = self.create()
        self.assertTrue(self.check(
            clock['id'], wall_clock_seconds=600)['allowed'])
        result = self.check(clock['id'], wall_clock_seconds=1)
        self.assertEqual(result['reason'], 'budget_wall_clock_exhausted')

    def test_denied_check_consumes_no_budget(self):
        grant = self.create()
        self.check(grant['id'], new_task=True, tool='shell')  # denied
        self.assertEqual(self.store.get(grant['id'])['tasks_used'], 0)

    def test_never_grantable_tools_refused(self):
        with self.assertRaises(GrantError):
            self.create(permitted_tools=['edit', 'git_push'])
        grant = self.create()
        # Even a hand-forged check naming a never-grantable tool is denied
        # with its own reason (it is also simply not in permitted_tools).
        result = self.check(grant['id'], tool='merge')
        self.assertEqual(result['reason'], 'tool_never_grantable')

    def test_audit_records_allows_denies_and_lifecycle(self):
        grant = self.create()
        self.check(grant['id'], tool='edit')          # allowed
        self.check(grant['id'], tool='shell')         # denied
        self.store.pause(grant['id'])
        self.store.revoke(grant['id'], confirmed=True)
        events = self.store.audit(grant['id'])
        kinds = [(e['event'], e['allowed']) for e in events]
        self.assertEqual(kinds[0], ('created', True))
        self.assertIn(('check', True), kinds)
        self.assertIn(('check', False), kinds)
        self.assertIn(('paused', True), kinds)
        self.assertIn(('revoked', True), kinds)
        reasons = {e['reason'] for e in events if e['event'] == 'check'}
        self.assertIn('tool_not_permitted', reasons)

    def test_grants_are_private_profile_data(self):
        self.create()
        db = self.home / 'identity.sqlite3'
        self.assertTrue(db.exists())
        self.assertFalse((self.repo / 'identity.sqlite3').exists())


class TaskGrantCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = self.base / 'repo'
        self.repo.mkdir()

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(['--home', str(self.home), *argv])
        return json.loads(out.getvalue())

    def create_argv(self, *extra):
        return ['create', '--objective', 'Synthetic', '--repo', str(self.repo),
                '--task-class', 'implement', '--allow-file', 'athenz/*.py',
                '--tool', 'edit', '--max-tasks', '2', '--max-test-runs', '3',
                '--max-retries', '1', '--max-wall-clock', '600',
                '--duration-hours', '1', *extra]

    def test_cli_create_without_confirm_refuses(self):
        with self.assertRaises(GrantError):
            self.run_cli(*self.create_argv())

    def test_cli_create_list_audit_round_trip(self):
        grant = self.run_cli(*self.create_argv('--confirm'))
        self.assertEqual(grant['state'], 'active')
        listed = self.run_cli('list')
        self.assertEqual([g['id'] for g in listed], [grant['id']])
        paused = self.run_cli('pause', grant['id'])
        self.assertEqual(paused['state'], 'paused')
        events = self.run_cli('audit', grant['id'])
        self.assertEqual([e['event'] for e in events], ['created', 'paused'])

    def test_cli_parser_requires_scope_flags(self):
        with self.assertRaises(SystemExit):
            parser().parse_args(['create', '--objective', 'x'])


if __name__ == '__main__':
    unittest.main()
