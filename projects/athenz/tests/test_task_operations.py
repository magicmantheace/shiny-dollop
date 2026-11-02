"""Synthetic durable-operation tests (slice A4). Fixture repos only."""
from __future__ import annotations

import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import tempfile
import unittest

from athenz.project_planner import SCHEMA as PLAN_SCHEMA
from athenz.task_executor import ScriptedEditor, TaskExecutionStore
from athenz.task_grants import TaskGrantStore
from athenz.task_operations import (OperationError, TaskOperationDriver)
from athenz.task_operations_cli import main as cli_main

FIXED = "def add(a, b):\n    return a + b\n"
FEATURE1 = "def plus(a, b):\n    return a + b\n"
FEATURE1_WRONG = "def plus(a, b):\n    return a * b\n"
FEATURE = "def mul(a, b):\n    return a * b\n"

TEST_CALC = (
    "import unittest\n"
    "from calc import add\n\n"
    "class AddTests(unittest.TestCase):\n"
    "    def test_add(self):\n"
    "        self.assertEqual(add(2, 3), 5)\n\n"
    "if __name__ == '__main__':\n"
    "    unittest.main()\n")
TEST_FEATURE1 = (
    "import unittest\n"
    "from feature1 import plus\n\n"
    "class PlusTests(unittest.TestCase):\n"
    "    def test_plus(self):\n"
    "        self.assertEqual(plus(2, 3), 5)\n\n"
    "if __name__ == '__main__':\n"
    "    unittest.main()\n")
TEST_FEATURE = (
    "import unittest\n"
    "from feature2 import mul\n\n"
    "class MulTests(unittest.TestCase):\n"
    "    def test_mul(self):\n"
    "        self.assertEqual(mul(2, 3), 6)\n\n"
    "if __name__ == '__main__':\n"
    "    unittest.main()\n")

ITEM1 = {'id': 'roadmap-1', 'title': 'Add the plus feature',
         'success_criteria': 'tests.test_feature1 passes',
         'scope': ['feature1.py', 'tests/test_feature1.py'],
         'source': {'file': 'ROADMAP.md', 'line': 3}}
ITEM2 = {'id': 'roadmap-2', 'title': 'Add the mul feature',
         'success_criteria': 'tests.test_feature2 passes',
         'scope': ['feature2.py', 'tests/test_feature2.py'],
         'source': {'file': 'ROADMAP.md', 'line': 4}}


def _git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME='Fixture',
               GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Fixture',
               GIT_COMMITTER_EMAIL='fixture@example.invalid')
    proc = subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True, env=env)
    return proc.stdout.strip()


def make_repo(base: Path) -> Path:
    repo = base / 'fixture-repo'
    (repo / 'tests').mkdir(parents=True)
    (repo / 'calc.py').write_text(FIXED, encoding='utf-8')
    (repo / 'tests' / 'test_calc.py').write_text(TEST_CALC,
                                                 encoding='utf-8')
    _git(repo, 'init', '-q')
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-q', '-m', 'fixture')
    return repo


def good_factory(item):
    if item['id'] == 'roadmap-1':
        return ScriptedEditor(
            [[{'path': 'feature1.py', 'content': FEATURE1},
              {'path': 'tests/test_feature1.py',
               'content': TEST_FEATURE1}]])
    return ScriptedEditor([[{'path': 'feature2.py', 'content': FEATURE},
                             {'path': 'tests/test_feature2.py',
                              'content': TEST_FEATURE}]])


def wrong_factory(item):
    return ScriptedEditor(
        [[{'path': 'feature1.py', 'content': FEATURE1_WRONG},
          {'path': 'tests/test_feature1.py', 'content': TEST_FEATURE1}]])


class SimulatedCrash(BaseException):
    """A process death: BaseException, so no handler may tidy it up."""


def crashing_factory(item):
    def crash(item_, worktree, diagnostics):
        raise SimulatedCrash()
    return ScriptedEditor([crash])


class OperationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = make_repo(self.base)
        self.grants = TaskGrantStore(self.home)
        self.grant = self.grants.create(
            objective='Synthetic objective', repository=self.repo,
            queue_item_ids=['roadmap-1', 'roadmap-2'],
            task_classes=['implement'],
            allowed_files=['feature1.py', 'feature2.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=10, max_test_runs=100, max_retries_per_task=0,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        self.plan = {'schema': PLAN_SCHEMA, 'read_only': True,
                     'generated_from': {'repo': str(self.repo.resolve())},
                     'queue': [ITEM1, ITEM2]}
        self.driver = TaskOperationDriver(self.home)
        self.records = TaskExecutionStore(self.home)

    def start(self, factory=good_factory, **kwargs):
        kwargs.setdefault('model_fingerprint', 'model-a')
        kwargs.setdefault('editor_fingerprint', 'editor-a')
        return self.driver.start_operation(
            self.plan, self.grant['id'], factory, **kwargs)

    def resume(self, operation_id, factory=good_factory, **kwargs):
        kwargs.setdefault('model_fingerprint', 'model-a')
        kwargs.setdefault('editor_fingerprint', 'editor-a')
        return TaskOperationDriver(self.home).resume_operation(
            operation_id, factory, **kwargs)

    def item(self, record, item_id):
        return next(i for i in record['items'] if i['id'] == item_id)

    def test_full_run_completes_with_durable_states(self):
        record = self.start()
        self.assertEqual(record['state'], 'completed')
        self.assertEqual(self.item(record, 'roadmap-1')['state'],
                         'succeeded')
        self.assertEqual(self.item(record, 'roadmap-2')['state'],
                         'succeeded')
        self.assertTrue(record['queue_fingerprint'])
        self.assertTrue(record['permission_fingerprint'])
        self.assertTrue(record['code_fingerprint'])
        stored = self.driver.get_operation(record['id'])
        self.assertEqual(stored['state'], 'completed')
        self.assertEqual(len(self.records.list(self.grant['id'])), 2)
        events = [e['event'] for e in stored['events']]
        self.assertIn('item_started', events)
        self.assertIn('item_finished', events)
        self.assertIn('completed', events)

    def test_inspection_reports_attempted_changed_tested_unfinished(self):
        record = self.start(max_items=1)
        view = self.driver.inspect_operation(record['id'])
        self.assertEqual([a['item_id'] for a in view['attempted']],
                         ['roadmap-1'])
        changed_files = [f for c in view['changed'] for f in c['files']]
        self.assertEqual(changed_files,
                         ['feature1.py', 'tests/test_feature1.py'])
        self.assertTrue(view['changed'][0]['diffs'])
        stages = [s['stage'] for t in view['tested'] for s in t['stages']]
        self.assertIn('targeted', stages)
        self.assertIn('full', stages)
        self.assertTrue(all(
            s['exit_code'] == 0 for t in view['tested']
            for s in t['stages'] if not s['skipped']))
        self.assertEqual(view['blocked'], [])
        self.assertEqual([u['item_id'] for u in view['unfinished']],
                         ['roadmap-2'])
        self.assertEqual(view['summary']['succeeded'], 1)

    def test_crash_between_items_resume_without_reexecution(self):
        record = self.start(max_items=1)
        self.assertEqual(record['state'], 'active')
        self.assertEqual(record['stop_reason'], 'run_limit_reached')
        accrued_before = record['accrued_wall_clock_seconds']
        self.assertGreater(accrued_before, 0)
        self.assertEqual(len(self.records.list(self.grant['id'])), 1)

        resumed = self.resume(record['id'])
        self.assertEqual(resumed['state'], 'completed')
        first = self.item(resumed, 'roadmap-1')
        second = self.item(resumed, 'roadmap-2')
        self.assertEqual(len(first['execution_ids']), 1)   # not replayed
        self.assertEqual(len(second['execution_ids']), 1)
        self.assertEqual(len(self.records.list(self.grant['id'])), 2)
        self.assertGreaterEqual(resumed['accrued_wall_clock_seconds'],
                                accrued_before)

    def test_crash_mid_item_suspect_default_blocks_retry_suspect(self):
        operation = self.driver.create_operation(
            self.plan, self.grant['id'], model_fingerprint='model-a',
            editor_fingerprint='editor-a')
        with self.assertRaises(SimulatedCrash):
            self.driver.drive_operation(operation['id'], crashing_factory)
        crashed = self.driver.get_operation(operation['id'])
        self.assertEqual(self.item(crashed, 'roadmap-1')['state'],
                         'running')
        self.assertEqual(len(self.records.list(self.grant['id'])), 1)

        blocked = self.resume(operation['id'])
        suspect = self.item(blocked, 'roadmap-1')
        self.assertEqual(suspect['state'], 'suspect')
        self.assertTrue(suspect['suspect'])
        self.assertEqual(blocked['stop_reason'],
                         'suspect_item_requires_owner_decision')
        # No new execution was performed by the blocked resume, and
        # the interrupted A3 record was linked as an orphan.
        self.assertEqual(len(self.records.list(self.grant['id'])), 1)
        self.assertEqual(len(suspect['orphan_execution_ids']), 1)
        self.assertEqual(len(suspect['execution_ids']), 1)

        retried = self.resume(operation['id'], retry_suspect=True)
        self.assertEqual(retried['state'], 'completed')
        first = self.item(retried, 'roadmap-1')
        self.assertEqual(first['state'], 'succeeded')
        self.assertEqual(len(first['retry_decisions']), 1)
        self.assertEqual(first['retry_decisions'][0]['decision'],
                         'retry_suspect')
        self.assertEqual(len(first['execution_ids']), 2)
        self.assertEqual(len(self.records.list(self.grant['id'])), 3)

    def test_grant_scope_changed_while_down_aborts_resume(self):
        record = self.start(max_items=1)
        with self.grants._open() as store:
            with store.db:
                store.db.execute(
                    'UPDATE task_grants SET allowed_files=? WHERE id=?',
                    (json.dumps(['feature1.py']), self.grant['id']))
        resumed = self.resume(record['id'])
        self.assertEqual(resumed['state'], 'aborted')
        self.assertEqual(resumed['stop_reason'],
                         'permission_fingerprint_changed')
        self.assertEqual(self.item(resumed, 'roadmap-2')['state'],
                         'pending')
        self.assertEqual(len(self.records.list(self.grant['id'])), 1)

    def test_grant_revoked_while_down_refuses_resume(self):
        record = self.start(max_items=1)
        self.grants.revoke(self.grant['id'], confirmed=True)
        resumed = self.resume(record['id'])
        self.assertEqual(resumed['state'], 'aborted')
        self.assertEqual(resumed['stop_reason'], 'grant_revoked')
        self.assertEqual(len(self.records.list(self.grant['id'])), 1)

    def test_base_revision_moved_blocks_item(self):
        record = self.start(max_items=1)
        (self.repo / 'notes.txt').write_text('external work\n',
                                             encoding='utf-8')
        _git(self.repo, 'add', '-A')
        _git(self.repo, 'commit', '-q', '-m', 'external')
        resumed = self.resume(record['id'])
        self.assertEqual(resumed['state'], 'active')
        self.assertEqual(resumed['stop_reason'], 'base_revision_changed')
        second = self.item(resumed, 'roadmap-2')
        self.assertEqual(second['state'], 'blocked')
        self.assertEqual(second['stop_reason'], 'base_revision_changed')
        self.assertEqual(len(self.records.list(self.grant['id'])), 1)

    def test_stall_detection_on_identical_failures_across_resume(self):
        plan = {**self.plan, 'queue': [ITEM1]}
        record = self.driver.start_operation(
            plan, self.grant['id'], wrong_factory,
            model_fingerprint='model-a', editor_fingerprint='editor-a')
        self.assertEqual(record['state'], 'active')
        first = self.item(record, 'roadmap-1')
        self.assertEqual(first['state'], 'failed')
        self.assertEqual(first['consecutive_identical_failures'], 1)

        resumed = self.resume(record['id'], factory=wrong_factory)
        self.assertEqual(resumed['state'], 'stalled')
        self.assertEqual(resumed['stop_reason'], 'stall_detected')
        first = self.item(resumed, 'roadmap-1')
        self.assertEqual(first['consecutive_identical_failures'], 2)
        self.assertEqual(first['failure_signatures'][0]['signature'],
                         first['failure_signatures'][1]['signature'])
        self.assertEqual(resumed['stall']['item_id'], 'roadmap-1')
        self.assertEqual(len(self.records.list(self.grant['id'])), 2)

    def test_model_fingerprint_change_on_resume_is_reported(self):
        record = self.start(max_items=1)
        resumed = self.resume(record['id'], model_fingerprint='model-b')
        self.assertEqual(resumed['state'], 'paused')
        self.assertEqual(resumed['stop_reason'],
                         'model_fingerprint_changed')
        self.assertEqual(self.item(resumed, 'roadmap-2')['state'],
                         'pending')
        self.assertEqual(len(self.records.list(self.grant['id'])), 1)

    def test_pause_and_abort(self):
        operation = self.driver.create_operation(
            self.plan, self.grant['id'])
        paused = self.driver.pause_operation(operation['id'])
        self.assertEqual(paused['state'], 'paused')
        aborted = self.driver.abort_operation(operation['id'])
        self.assertEqual(aborted['state'], 'aborted')
        states = {i['id']: i['state'] for i in aborted['items']}
        self.assertEqual(states, {'roadmap-1': 'skipped',
                                  'roadmap-2': 'skipped'})

    def test_create_rejects_plan_for_other_repository(self):
        plan = {'schema': PLAN_SCHEMA,
                'generated_from': {'repo': str(self.base)},
                'queue': [ITEM1]}
        with self.assertRaises(OperationError):
            self.driver.create_operation(plan, self.grant['id'])


class OperationCliTests(unittest.TestCase):
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
            allowed_files=['feature1.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=3, max_test_runs=50, max_retries_per_task=0,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        plan = {'schema': PLAN_SCHEMA, 'read_only': True,
                'generated_from': {'repo': str(self.repo.resolve())},
                'queue': [ITEM1]}
        self.plan_path = self.base / 'plan.json'
        self.plan_path.write_text(json.dumps(plan), encoding='utf-8')
        script = {'attempts': [[{'path': 'feature1.py',
                                 'content': FEATURE1},
                                {'path': 'tests/test_feature1.py',
                                 'content': TEST_FEATURE1}]]}
        self.script_path = self.base / 'editor.json'
        self.script_path.write_text(json.dumps(script), encoding='utf-8')

    def run_cli(self, *argv):
        out = io.StringIO()
        with redirect_stdout(out):
            cli_main(['--home', str(self.home), *argv])
        return json.loads(out.getvalue())

    def start_argv(self, *extra):
        return ['start', '--grant', self.grant['id'], '--plan',
                str(self.plan_path), '--editor-script',
                str(self.script_path), *extra]

    def test_start_without_confirm_refuses(self):
        with self.assertRaises(OperationError):
            self.run_cli(*self.start_argv())
        self.assertEqual(TaskOperationDriver(self.home)
                         .list_operations(), [])

    def test_start_show_list_resume_round_trip(self):
        record = self.run_cli(*self.start_argv('--confirm'))
        self.assertEqual(record['state'], 'completed')
        shown = self.run_cli('show', record['id'])
        self.assertEqual(shown['operation']['id'], record['id'])
        self.assertEqual(shown['summary']['succeeded'], 1)
        self.assertEqual(shown['unfinished'], [])
        listed = self.run_cli('list', '--grant', self.grant['id'])
        self.assertEqual([r['id'] for r in listed], [record['id']])
        with self.assertRaises(OperationError):
            self.run_cli('resume', record['id'], '--editor-script',
                         str(self.script_path))
        again = self.run_cli('resume', record['id'], '--editor-script',
                             str(self.script_path), '--confirm')
        self.assertEqual(again['state'], 'completed')


if __name__ == '__main__':
    unittest.main()
