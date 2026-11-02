"""Synthetic task executor tests (slice A3). Fixture repos only."""
from __future__ import annotations

import hashlib
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import tempfile
import unittest

from athenz.project_planner import SCHEMA as PLAN_SCHEMA
from athenz.task_executor import (EditorBlocked, ExecutorError,
                                  ScriptedEditor, TaskExecutor,
                                  build_command)
from athenz.task_executor_cli import main as cli_main
from athenz.task_grants import TaskGrantStore

BUGGY = "def add(a, b):\n    return a - b  # fixture bug\n"
FIXED = "def add(a, b):\n    return a + b\n"
WRONG = "def add(a, b):\n    return a * b\n"
WRONG2 = "def add(a, b):\n    return a * b + 1\n"

TEST_CALC = (
    "import unittest\n"
    "from calc import add\n\n"
    "class AddTests(unittest.TestCase):\n"
    "    def test_add(self):\n"
    "        self.assertEqual(add(2, 3), 5)\n\n"
    "if __name__ == '__main__':\n"
    "    unittest.main()\n")

TEST_SLOW = (
    "import time\nimport unittest\n\n"
    "class SlowTests(unittest.TestCase):\n"
    "    def test_slow(self):\n"
    "        time.sleep(60)\n\n"
    "if __name__ == '__main__':\n"
    "    unittest.main()\n")

ITEM = {'id': 'roadmap-1', 'title': 'Fix the add function',
        'success_criteria': 'tests.test_calc passes',
        'scope': ['calc.py'], 'source': {'file': 'ROADMAP.md', 'line': 3}}


def _git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME='Fixture',
               GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Fixture',
               GIT_COMMITTER_EMAIL='fixture@example.invalid')
    proc = subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True, env=env)
    return proc.stdout.strip()


def make_repo(base: Path, extra_files: dict | None = None) -> Path:
    repo = base / 'fixture-repo'
    (repo / 'tests').mkdir(parents=True)
    files = {'calc.py': BUGGY, 'tests/test_calc.py': TEST_CALC}
    files.update(extra_files or {})
    for rel, content in files.items():
        (repo / rel).write_text(content, encoding='utf-8')
    _git(repo, 'init', '-q')
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-q', '-m', 'fixture')
    return repo


def tree_hashes(repo: Path) -> dict:
    out = {}
    for path in sorted(repo.rglob('*')):
        if path.is_file() and '.git' not in path.parts:
            out[str(path.relative_to(repo))] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    return out


class ExecutorTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = make_repo(self.base)
        self.grants = TaskGrantStore(self.home)
        self.executor = TaskExecutor(self.home)

    def create_grant(self, **overrides):
        kwargs = dict(
            objective='Synthetic objective', repository=self.repo,
            queue_item_ids=['roadmap-1'], task_classes=['implement'],
            allowed_files=['calc.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=3, max_test_runs=50, max_retries_per_task=2,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        kwargs.update(overrides)
        return self.grants.create(**kwargs)

    def run_task(self, grant, editor, **kwargs):
        return self.executor.execute(grant['id'], ITEM, editor, **kwargs)

    def test_end_to_end_success(self):
        grant = self.create_grant()
        record = self.run_task(
            grant, ScriptedEditor([[{'path': 'calc.py',
                                     'content': FIXED}]]))
        self.assertEqual(record['outcome'], 'succeeded')
        self.assertEqual(record['stop_reason'], '')
        self.assertEqual(len(record['attempts']), 1)
        attempt = record['attempts'][0]
        stages = {r['stage']: r for r in attempt['runs']}
        self.assertEqual(stages['syntax']['exit_code'], 0)
        self.assertEqual(stages['targeted']['exit_code'], 0)
        self.assertEqual(stages['targeted']['argv'][-1], 'tests.test_calc')
        self.assertEqual(stages['full']['exit_code'], 0)
        edit = attempt['edits'][0]
        self.assertEqual(edit['path'], 'calc.py')
        self.assertFalse(edit['created'])
        self.assertIn('+    return a + b', edit['diff'])
        # The record is durable in the profile store.
        stored = self.executor.records.get(record['id'])
        self.assertEqual(stored['outcome'], 'succeeded')
        self.assertEqual(record['budget_usage']['tasks_used'], 1)
        self.assertGreaterEqual(record['budget_usage']['test_runs_used'], 3)

    def test_worktree_and_branch_kept_original_untouched(self):
        before = tree_hashes(self.repo)
        grant = self.create_grant()
        record = self.run_task(
            grant, ScriptedEditor([[{'path': 'calc.py',
                                     'content': FIXED}]]))
        self.assertEqual(tree_hashes(self.repo), before)
        self.assertEqual(_git(self.repo, 'status', '--porcelain'), '')
        branches = _git(self.repo, 'branch', '--list', 'athenz-task/*')
        self.assertIn(record['branch'], branches)
        # The scratch branch still points at the fingerprinted base:
        # the executor never commits (promotion is slice A5).
        tip = _git(self.repo, 'rev-parse', record['branch'])
        self.assertEqual(tip, record['base_sha'])
        worktree = Path(record['worktree'])
        self.assertTrue(worktree.is_dir())
        self.assertEqual((worktree / 'calc.py').read_text(
            encoding='utf-8'), FIXED)

    def test_failure_recorded_honestly(self):
        grant = self.create_grant(max_retries_per_task=1)
        editor = ScriptedEditor([
            [{'path': 'calc.py', 'content': WRONG}],
            [{'path': 'calc.py', 'content': WRONG2}],
        ])
        record = self.run_task(grant, editor)
        self.assertEqual(record['outcome'], 'failed')
        self.assertEqual(record['stop_reason'], 'attempts_exhausted')
        self.assertEqual(len(record['attempts']), 2)
        self.assertIn('return a * b', record['attempts'][0]['edits'][0]['diff'])
        self.assertIn('return a * b + 1',
                      record['attempts'][1]['edits'][0]['diff'])
        for attempt in record['attempts']:
            self.assertTrue(attempt['edits'])
            failing = [r for r in attempt['runs']
                       if not r['skipped'] and r['exit_code'] != 0]
            self.assertTrue(failing)
            output = failing[0]['stdout_tail'] + failing[0]['stderr_tail']
            self.assertIn('FAIL', output)

    def test_revoked_grant_denies_before_any_edit(self):
        grant = self.create_grant()
        self.grants.revoke(grant['id'], confirmed=True)
        record = self.run_task(
            grant, ScriptedEditor([[{'path': 'calc.py',
                                     'content': FIXED}]]))
        self.assertEqual(record['outcome'], 'denied')
        self.assertEqual(record['stop_reason'], 'grant_revoked')
        self.assertEqual(record['attempts'], [])
        self.assertFalse(Path(record['worktree']).exists())
        self.assertEqual(
            _git(self.repo, 'branch', '--list', 'athenz-task/*'), '')

    def test_out_of_scope_edit_aborts_before_applying_any(self):
        grant = self.create_grant(allowed_files=['calc.py'])
        editor = ScriptedEditor([[
            {'path': 'calc.py', 'content': FIXED},
            {'path': 'other.py', 'content': 'x = 1\n'},
        ]])
        record = self.run_task(grant, editor)
        self.assertEqual(record['outcome'], 'denied')
        self.assertEqual(record['stop_reason'], 'file_out_of_scope')
        attempt = record['attempts'][0]
        self.assertEqual(attempt['edits'], [])
        self.assertEqual(attempt['runs'], [])
        worktree = Path(record['worktree'])
        # Pre-flight denied the batch: even the in-scope edit was
        # never applied.
        self.assertEqual((worktree / 'calc.py').read_text(
            encoding='utf-8'), BUGGY)
        self.assertFalse((worktree / 'other.py').exists())

    def test_non_allowlisted_command_cannot_run(self):
        with self.assertRaises(ExecutorError):
            build_command('shell', self.repo)
        with self.assertRaises(ExecutorError):
            build_command('rm -rf', self.repo)
        grant = self.create_grant(permitted_tools=['edit'])
        record = self.run_task(
            grant, ScriptedEditor([[{'path': 'calc.py',
                                     'content': FIXED}]]))
        self.assertEqual(record['outcome'], 'denied')
        self.assertEqual(record['stop_reason'], 'tool_not_permitted')
        attempt = record['attempts'][0]
        self.assertEqual(len(attempt['edits']), 1)   # edit tool allowed
        self.assertEqual(attempt['runs'], [])        # no command ran

    def test_mid_run_revocation_stops_the_loop(self):
        grant = self.create_grant(max_retries_per_task=3)
        grants = self.grants

        def revoke_then_edit(item, worktree, diagnostics):
            grants.revoke(grant['id'], confirmed=True)
            return [{'path': 'calc.py', 'content': WRONG}]

        editor = ScriptedEditor([
            [{'path': 'calc.py', 'content': WRONG}],
            revoke_then_edit,
        ])
        record = self.run_task(grant, editor)
        self.assertEqual(record['outcome'], 'blocked')
        self.assertEqual(record['stop_reason'], 'grant_revoked')
        self.assertEqual(len(record['attempts']), 2)
        second = record['attempts'][1]
        self.assertEqual(second['edits'], [])
        self.assertEqual(second['runs'], [])

    def test_editor_blocked_is_recorded_as_blocked(self):
        grant = self.create_grant()
        record = self.run_task(
            grant, ScriptedEditor([EditorBlocked('needs a design call')]))
        self.assertEqual(record['outcome'], 'blocked')
        self.assertEqual(record['stop_reason'], 'needs a design call')
        self.assertEqual(record['attempts'][0]['runs'], [])

    def test_command_timeout_is_enforced(self):
        # Build the slow fixture in its own directory.
        slow_base = self.base / 'slowcase'
        slow_base.mkdir()
        slow_repo = make_repo(slow_base, {'tests/test_slow.py': TEST_SLOW})
        grants = TaskGrantStore(self.home)
        grant = grants.create(
            objective='Synthetic', repository=slow_repo,
            queue_item_ids=['roadmap-1'], task_classes=['implement'],
            allowed_files=['calc.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=1, max_test_runs=10, max_retries_per_task=0,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        executor = TaskExecutor(self.home, command_timeout=2)
        record = executor.execute(
            grant['id'], ITEM,
            ScriptedEditor([[{'path': 'calc.py', 'content': FIXED}]]))
        self.assertEqual(record['outcome'], 'failed')
        full = next(r for r in record['attempts'][0]['runs']
                    if r['stage'] == 'full')
        self.assertTrue(full['timed_out'])
        self.assertIsNone(full['exit_code'])
        self.assertLess(full['duration_seconds'], 30)


class ExecutorCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = make_repo(self.base)
        self.grants = TaskGrantStore(self.home)
        self.grant = self.grants.create(
            objective='Synthetic', repository=self.repo,
            queue_item_ids=['roadmap-1'], task_classes=['implement'],
            allowed_files=['calc.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=3, max_test_runs=50, max_retries_per_task=1,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        plan = {'schema': PLAN_SCHEMA, 'read_only': True,
                'generated_from': {'repo': str(self.repo.resolve())},
                'queue': [ITEM]}
        self.plan_path = self.base / 'plan.json'
        self.plan_path.write_text(json.dumps(plan), encoding='utf-8')
        script = {'attempts': [[{'path': 'calc.py', 'content': FIXED}]]}
        self.script_path = self.base / 'editor.json'
        self.script_path.write_text(json.dumps(script), encoding='utf-8')

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(['--home', str(self.home), *argv])
        return json.loads(out.getvalue())

    def run_argv(self, *extra):
        return ['run', '--grant', self.grant['id'], '--plan',
                str(self.plan_path), '--item', 'roadmap-1',
                '--editor-script', str(self.script_path), *extra]

    def test_run_without_confirm_refuses(self):
        with self.assertRaises(ExecutorError):
            self.run_cli(*self.run_argv())

    def test_run_and_show_record_round_trip(self):
        record = self.run_cli(*self.run_argv('--confirm'))
        self.assertEqual(record['outcome'], 'succeeded')
        shown = self.run_cli('show-record', record['id'])
        self.assertEqual(shown['id'], record['id'])
        self.assertEqual(shown['outcome'], 'succeeded')
        listed = self.run_cli('list-records', '--grant', self.grant['id'])
        self.assertEqual([r['id'] for r in listed], [record['id']])

    def test_plan_for_another_repository_refused(self):
        plan = {'schema': PLAN_SCHEMA,
                'generated_from': {'repo': str(self.base)},
                'queue': [ITEM]}
        other = self.base / 'other-plan.json'
        other.write_text(json.dumps(plan), encoding='utf-8')
        with self.assertRaises(ExecutorError):
            self.run_cli('run', '--grant', self.grant['id'], '--plan',
                         str(other), '--item', 'roadmap-1',
                         '--editor-script', str(self.script_path),
                         '--confirm')


if __name__ == '__main__':
    unittest.main()
