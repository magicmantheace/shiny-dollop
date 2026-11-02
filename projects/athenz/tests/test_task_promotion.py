"""Synthetic promotion-boundary tests (slice A5). Fixture repos only."""
from __future__ import annotations

import argparse
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import subprocess
import tempfile
import unittest

import athenz.task_promotion as promotion_module
from athenz.project_planner import SCHEMA as PLAN_SCHEMA
from athenz.task_executor import (EditorBlocked, ScriptedEditor,
                                  TaskExecutor)
from athenz.task_grants import TaskGrantStore
from athenz.task_operations import TaskOperationDriver
from athenz.task_promotion import PromotionError, TaskPromoter
from athenz.task_promotion_cli import main as cli_main
from athenz.task_promotion_cli import parser as cli_parser

BUGGY = "def add(a, b):\n    return a - b  # fixture bug\n"
FIXED = "def add(a, b):\n    return a + b\n"
WRONG = "def add(a, b):\n    return a * b\n"

TEST_CALC = (
    "import unittest\n"
    "from calc import add\n\n"
    "class AddTests(unittest.TestCase):\n"
    "    def test_add(self):\n"
    "        self.assertEqual(add(2, 3), 5)\n\n"
    "if __name__ == '__main__':\n"
    "    unittest.main()\n")
TEST_CALC_BROKEN = TEST_CALC.replace('add(2, 3), 5', 'add(2, 3), 6')

FEATURE1 = "def plus(a, b):\n    return a + b\n"
FEATURE1_WRONG = "def plus(a, b):\n    return a * b\n"
TEST_FEATURE1 = (
    "import unittest\n"
    "from feature1 import plus\n\n"
    "class PlusTests(unittest.TestCase):\n"
    "    def test_plus(self):\n"
    "        self.assertEqual(plus(2, 3), 5)\n\n"
    "if __name__ == '__main__':\n"
    "    unittest.main()\n")

ITEM = {'id': 'roadmap-1', 'title': 'Fix the add function',
        'success_criteria': 'tests.test_calc passes',
        'scope': ['calc.py'], 'source': {'file': 'ROADMAP.md', 'line': 3}}
OP_ITEM = {'id': 'roadmap-1', 'title': 'Add the plus feature',
           'success_criteria': 'tests.test_feature1 passes',
           'scope': ['feature1.py', 'tests/test_feature1.py'],
           'source': {'file': 'ROADMAP.md', 'line': 3}}


def _git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME='Fixture',
               GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Fixture',
               GIT_COMMITTER_EMAIL='fixture@example.invalid')
    proc = subprocess.run(['git', '-C', str(repo), *args], check=True,
                          capture_output=True, text=True, env=env)
    return proc.stdout.strip()


def make_repo(base: Path, calc_content: str) -> Path:
    repo = base / 'fixture-repo'
    (repo / 'tests').mkdir(parents=True)
    (repo / 'calc.py').write_text(calc_content, encoding='utf-8')
    (repo / 'tests' / 'test_calc.py').write_text(TEST_CALC,
                                                 encoding='utf-8')
    _git(repo, 'init', '-q')
    _git(repo, 'config', 'user.name', 'Fixture')
    _git(repo, 'config', 'user.email', 'fixture@example.invalid')
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-q', '-m', 'fixture')
    return repo


class PromotionTests(unittest.TestCase):
    """Executor-produced candidates (slice A3 path)."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = make_repo(self.base, BUGGY)
        self.grants = TaskGrantStore(self.home)
        self.executor = TaskExecutor(self.home)
        self.promoter = TaskPromoter(self.home)

    def create_grant(self, **overrides):
        kwargs = dict(
            objective='Synthetic objective', repository=self.repo,
            queue_item_ids=['roadmap-1'], task_classes=['implement'],
            allowed_files=['calc.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=5, max_test_runs=100, max_retries_per_task=2,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        kwargs.update(overrides)
        return self.grants.create(**kwargs)

    def run_success(self, grant=None):
        grant = grant or self.create_grant()
        record = self.executor.execute(
            grant['id'], ITEM,
            ScriptedEditor([[{'path': 'calc.py', 'content': FIXED}]]))
        self.assertEqual(record['outcome'], 'succeeded')
        return record

    # -- prepare ---------------------------------------------------------

    def test_proposal_on_succeeded_is_promotable(self):
        record = self.run_success()
        proposal = self.promoter.prepare_proposal(record['id'])
        self.assertEqual(proposal['state'], 'prepared')
        self.assertTrue(proposal['promotable'])
        self.assertEqual(proposal['not_promotable_reason'], '')
        self.assertEqual(proposal['execution_id'], record['id'])
        # Full diff: stat + patch, against the recorded base.
        diff = proposal['diff']
        self.assertEqual([f['path'] for f in diff['files']], ['calc.py'])
        self.assertIn('+    return a + b', diff['patch'])
        self.assertIn('1 file(s) changed', diff['stat'])
        self.assertTrue(diff['diff_hash'])
        # Fresh regression: really ran, green.
        regression = proposal['regression']
        self.assertTrue(regression['ran'])
        self.assertTrue(regression['green'])
        self.assertEqual(regression['exit_code'], 0)
        # Linked A3 evidence: attempts with commands and exit codes.
        attempts = proposal['evidence']['attempts']
        self.assertEqual(len(attempts), 1)
        runs = {r['stage']: r for r in attempts[0]['runs']}
        self.assertEqual(runs['full']['exit_code'], 0)
        self.assertTrue(runs['full']['argv'])
        # Grant state and rollback are recorded; owner steps are explicit.
        self.assertEqual(proposal['grant_at_proposal']['state'],
                         'active')
        self.assertEqual(proposal['rollback']['base_sha'],
                         record['base_sha'])
        steps = ' '.join(proposal['remaining_owner_steps'])
        self.assertIn('NOT something this module can do', steps)
        # Durable in the promotion store.
        stored = self.promoter.get_proposal(proposal['id'])
        self.assertEqual(stored['diff']['diff_hash'], diff['diff_hash'])

    def test_proposal_refuses_failed_execution(self):
        grant = self.create_grant(max_retries_per_task=0)
        record = self.executor.execute(
            grant['id'], ITEM,
            ScriptedEditor([[{'path': 'calc.py', 'content': WRONG}]]))
        self.assertEqual(record['outcome'], 'failed')
        with self.assertRaises(PromotionError):
            self.promoter.prepare_proposal(record['id'])

    def test_proposal_refuses_blocked_execution(self):
        grant = self.create_grant()
        record = self.executor.execute(
            grant['id'], ITEM, ScriptedEditor([EditorBlocked('cannot')]))
        self.assertEqual(record['outcome'], 'blocked')
        with self.assertRaises(PromotionError):
            self.promoter.prepare_proposal(record['id'])

    def test_proposal_refuses_denied_execution(self):
        grant = self.create_grant()
        self.grants.revoke(grant['id'], confirmed=True)
        record = self.executor.execute(
            grant['id'], ITEM,
            ScriptedEditor([[{'path': 'calc.py', 'content': FIXED}]]))
        self.assertEqual(record['outcome'], 'denied')
        with self.assertRaises(PromotionError):
            self.promoter.prepare_proposal(record['id'])

    def break_worktree_tests(self, record):
        """Break the worktree's tests after the execution ran.

        The broken file has the same size as the original, so its
        mtime is moved forward explicitly — otherwise Python would
        (correctly, by its own rules) reuse the stale bytecode cache
        and the fresh regression would not see the break.
        """
        broken = Path(record['worktree']) / 'tests' / 'test_calc.py'
        broken.write_text(TEST_CALC_BROKEN, encoding='utf-8')
        stamp = broken.stat().st_mtime + 5
        os.utime(broken, (stamp, stamp))

    def test_regression_red_at_proposal_time_marks_not_promotable(self):
        record = self.run_success()
        # The worktree's tests are broken AFTER the successful run.
        self.break_worktree_tests(record)
        proposal = self.promoter.prepare_proposal(record['id'])
        self.assertFalse(proposal['promotable'])
        self.assertEqual(proposal['not_promotable_reason'],
                         'regression_failed')
        regression = proposal['regression']
        self.assertTrue(regression['ran'])
        self.assertFalse(regression['green'])
        self.assertEqual(regression['exit_code'], 1)

    # -- checkpoint commit ---------------------------------------------------

    def test_commit_checkpoint_one_commit_on_scratch_branch_only(self):
        record = self.run_success()
        proposal = self.promoter.prepare_proposal(record['id'])
        repo_head_before = _git(self.repo, 'rev-parse', 'HEAD')
        base_branch_tip = _git(self.repo, 'rev-parse',
                               record['base_branch'])
        with self.assertRaises(PromotionError):
            self.promoter.commit_checkpoint(proposal['id'])
        result = self.promoter.commit_checkpoint(proposal['id'],
                                                 confirmed=True)
        self.assertEqual(result['state'], 'committed')
        checkpoint = result['checkpoint']
        self.assertTrue(checkpoint['verification']
                        ['parent_is_recorded_base'])
        self.assertTrue(checkpoint['verification']
                        ['files_match_proposal'])
        # Exactly one new commit, on the scratch branch only.
        branch_tip = _git(self.repo, 'rev-parse', record['branch'])
        self.assertEqual(branch_tip, checkpoint['commit_sha'])
        count = _git(self.repo, 'rev-list', '--count',
                     f"{record['base_sha']}..{record['branch']}")
        self.assertEqual(count, '1')
        committed = _git(self.repo, 'diff-tree', '--no-commit-id',
                         '--name-only', '-r', checkpoint['commit_sha'])
        self.assertEqual(committed, 'calc.py')
        message = _git(self.repo, 'log', '-1', '--format=%B',
                       record['branch'])
        self.assertIn(proposal['id'], message)
        self.assertIn(record['id'], message)
        # The repository's own branch and working tree are untouched.
        self.assertEqual(_git(self.repo, 'rev-parse', 'HEAD'),
                         repo_head_before)
        self.assertEqual(
            _git(self.repo, 'rev-parse', record['base_branch']),
            base_branch_tip)
        self.assertEqual(_git(self.repo, 'status', '--porcelain'), '')
        # A committed proposal cannot be committed again.
        with self.assertRaises(PromotionError):
            self.promoter.commit_checkpoint(proposal['id'],
                                            confirmed=True)

    def test_commit_refuses_when_candidate_changed_since_proposal(self):
        record = self.run_success()
        proposal = self.promoter.prepare_proposal(record['id'])
        worktree = Path(record['worktree'])
        (worktree / 'calc.py').write_text(FIXED + '# drift\n',
                                          encoding='utf-8')
        with self.assertRaises(PromotionError):
            self.promoter.commit_checkpoint(proposal['id'],
                                            confirmed=True)
        stored = self.promoter.get_proposal(proposal['id'])
        refusals = [e for e in stored['events']
                    if e['event'] == 'commit_refused']
        self.assertEqual(refusals[-1]['detail']['reason'],
                         'candidate_changed_since_proposal')
        # Nothing was committed.
        self.assertEqual(_git(self.repo, 'rev-parse', record['branch']),
                         record['base_sha'])

    def test_commit_refuses_not_promotable_proposal(self):
        record = self.run_success()
        self.break_worktree_tests(record)
        proposal = self.promoter.prepare_proposal(record['id'])
        self.assertFalse(proposal['promotable'])
        with self.assertRaises(PromotionError):
            self.promoter.commit_checkpoint(proposal['id'],
                                            confirmed=True)
        self.assertEqual(_git(self.repo, 'rev-parse', record['branch']),
                         record['base_sha'])

    # -- discard -----------------------------------------------------------

    def test_discard_via_proposal_removes_and_records(self):
        record = self.run_success()
        proposal = self.promoter.prepare_proposal(record['id'])
        with self.assertRaises(PromotionError):
            self.promoter.discard_candidate(proposal['id'])
        result = self.promoter.discard_candidate(proposal['id'],
                                                 confirmed=True)
        self.assertEqual(result['state'], 'discarded')
        disposal = result['disposal']
        self.assertEqual(disposal['final_diff_hash'],
                         proposal['diff']['diff_hash'])
        self.assertEqual(disposal['by'], 'owner')
        self.assertTrue(disposal['worktree_removed'])
        self.assertTrue(disposal['branch_deleted'])
        self.assertFalse(Path(record['worktree']).exists())
        self.assertEqual(
            _git(self.repo, 'branch', '--list', 'athenz-task/*'), '')
        with self.assertRaises(PromotionError):
            self.promoter.discard_candidate(proposal['id'],
                                            confirmed=True)

    def test_discard_by_execution_without_proposal(self):
        grant = self.create_grant(max_retries_per_task=0)
        record = self.executor.execute(
            grant['id'], ITEM,
            ScriptedEditor([[{'path': 'calc.py', 'content': WRONG}]]))
        self.assertEqual(record['outcome'], 'failed')
        self.assertTrue(Path(record['worktree']).is_dir())
        result = self.promoter.discard_candidate(
            execution_id=record['id'], confirmed=True)
        self.assertEqual(result['state'], 'discarded')
        self.assertEqual(result['execution_id'], record['id'])
        self.assertIsNotNone(result['disposal']['final_diff_hash'])
        self.assertFalse(Path(record['worktree']).exists())
        self.assertEqual(
            _git(self.repo, 'branch', '--list', 'athenz-task/*'), '')

    def test_discard_after_checkpoint_commit(self):
        record = self.run_success()
        proposal = self.promoter.prepare_proposal(record['id'])
        committed = self.promoter.commit_checkpoint(proposal['id'],
                                                    confirmed=True)
        result = self.promoter.discard_candidate(proposal['id'],
                                                 confirmed=True)
        self.assertEqual(
            result['disposal']['checkpoint_commit_sha'],
            committed['checkpoint']['commit_sha'])
        self.assertEqual(
            _git(self.repo, 'branch', '--list', 'athenz-task/*'), '')

    def test_discard_refuses_non_scratch_branch(self):
        record = self.run_success()
        tampered = self.executor.records.get(record['id'])
        tampered['branch'] = 'owner-branch'
        self.executor.records.update(tampered)
        with self.assertRaises(PromotionError):
            self.promoter.discard_candidate(execution_id=record['id'],
                                            confirmed=True)
        # The real scratch branch and worktree were not touched.
        self.assertTrue(Path(record['worktree']).is_dir())
        self.assertIn('athenz-task/',
                      _git(self.repo, 'branch', '--list', 'athenz-task/*'))

    def test_discard_refuses_worktree_outside_managed_location(self):
        record = self.run_success()
        tampered = self.executor.records.get(record['id'])
        tampered['worktree'] = str(self.base / 'elsewhere')
        self.executor.records.update(tampered)
        with self.assertRaises(PromotionError):
            self.promoter.discard_candidate(execution_id=record['id'],
                                            confirmed=True)
        self.assertTrue(Path(record['worktree']).is_dir())

    # -- boundary by construction ------------------------------------------

    def test_public_api_has_no_forbidden_operations(self):
        forbidden = ('push', 'merge', 'tag', 'release', 'deploy',
                     'install', 'publish', 'self_update')
        names = set()
        for name in dir(promotion_module):
            if name.startswith('_'):
                continue
            obj = getattr(promotion_module, name)
            if callable(obj) and getattr(obj, '__module__', None) == \
                    promotion_module.__name__:
                names.add(name)
                if isinstance(obj, type):
                    names.update(
                        f'{name}.{method}' for method in dir(obj)
                        if not method.startswith('_'))
        self.assertIn('TaskPromoter.prepare_proposal', names)
        self.assertIn('TaskPromoter.commit_checkpoint', names)
        self.assertIn('TaskPromoter.discard_candidate', names)
        for name in names:
            for token in forbidden:
                self.assertNotIn(
                    token, name.lower(),
                    f'forbidden operation in public API: {name}')
        subparsers = next(
            a for a in cli_parser()._actions
            if isinstance(a, argparse._SubParsersAction))
        self.assertEqual(set(subparsers.choices),
                         {'prepare', 'show', 'list', 'commit', 'discard'})
        for command in subparsers.choices:
            for token in forbidden:
                self.assertNotIn(token, command)


class OperationPromotionTests(unittest.TestCase):
    """Operation-item candidates (slice A4 path)."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = make_repo(self.base, FIXED)
        self.grants = TaskGrantStore(self.home)
        self.grant = self.grants.create(
            objective='Synthetic objective', repository=self.repo,
            queue_item_ids=['roadmap-1'], task_classes=['implement'],
            allowed_files=['feature1.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=5, max_test_runs=100, max_retries_per_task=0,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        self.plan = {'schema': PLAN_SCHEMA, 'read_only': True,
                     'generated_from': {'repo': str(self.repo.resolve())},
                     'queue': [OP_ITEM]}
        self.driver = TaskOperationDriver(self.home)
        self.promoter = TaskPromoter(self.home)

    @staticmethod
    def factory(content):
        def make(item):
            return ScriptedEditor(
                [[{'path': 'feature1.py', 'content': content},
                  {'path': 'tests/test_feature1.py',
                   'content': TEST_FEATURE1}]])
        return make

    def test_proposal_via_operation_item(self):
        operation = self.driver.start_operation(
            self.plan, self.grant['id'], self.factory(FEATURE1),
            model_fingerprint='model-a', editor_fingerprint='editor-a')
        self.assertEqual(operation['state'], 'completed')
        item = operation['items'][0]
        self.assertEqual(item['state'], 'succeeded')
        proposal = self.promoter.prepare_proposal(
            operation_id=operation['id'], item_id='roadmap-1')
        self.assertTrue(proposal['promotable'])
        self.assertEqual(proposal['execution_id'],
                         item['execution_ids'][-1])
        self.assertEqual(proposal['operation_id'], operation['id'])
        self.assertEqual(
            proposal['evidence']['operation']['operation_id'],
            operation['id'])
        self.assertEqual(
            {f['path'] for f in proposal['diff']['files']},
            {'feature1.py', 'tests/test_feature1.py'})

    def test_proposal_refuses_failed_operation_item(self):
        operation = self.driver.start_operation(
            self.plan, self.grant['id'], self.factory(FEATURE1_WRONG),
            model_fingerprint='model-a', editor_fingerprint='editor-a')
        self.assertEqual(operation['items'][0]['state'], 'failed')
        with self.assertRaises(PromotionError):
            self.promoter.prepare_proposal(
                operation_id=operation['id'], item_id='roadmap-1')


class PromotionCliTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = make_repo(self.base, BUGGY)
        self.grants = TaskGrantStore(self.home)
        self.grant = self.grants.create(
            objective='Synthetic objective', repository=self.repo,
            queue_item_ids=['roadmap-1'], task_classes=['implement'],
            allowed_files=['calc.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=5, max_test_runs=100, max_retries_per_task=2,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        self.executor = TaskExecutor(self.home)
        self.record = self.executor.execute(
            self.grant['id'], ITEM,
            ScriptedEditor([[{'path': 'calc.py', 'content': FIXED}]]))
        self.assertEqual(self.record['outcome'], 'succeeded')

    def run_cli(self, *argv):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            cli_main(['--home', str(self.home), *argv])
        return json.loads(buffer.getvalue())

    def test_prepare_show_commit_discard_round_trip(self):
        proposal = self.run_cli('prepare', '--execution',
                                self.record['id'])
        self.assertTrue(proposal['promotable'])
        shown = self.run_cli('show', proposal['id'])
        self.assertEqual(shown['id'], proposal['id'])
        with self.assertRaises(PromotionError):
            self.run_cli('commit', proposal['id'])
        committed = self.run_cli('commit', proposal['id'], '--confirm')
        self.assertEqual(committed['state'], 'committed')
        discarded = self.run_cli('discard', proposal['id'], '--confirm')
        self.assertEqual(discarded['state'], 'discarded')
        self.assertFalse(Path(self.record['worktree']).exists())


if __name__ == '__main__':
    unittest.main()
