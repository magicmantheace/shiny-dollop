"""Synthetic task executor tests (slice A3). Fixture repos only."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
from contextlib import redirect_stdout
from pathlib import Path
import py_compile
import struct
import subprocess
import sys
import tempfile
import unittest

from athenz.project_planner import SCHEMA as PLAN_SCHEMA
from athenz.task_executor import (EditorBlocked, ExecutorError,
                                  ScriptedEditor, TaskExecutor,
                                  _fresh_pycache_prefix, _scrubbed_env,
                                  build_command, purge_bytecode_caches)
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

# Same byte length, different behavior: the exact shape of the
# stale-bytecode flaw (a same-size rewrite Python's mtime+size cache
# check cannot distinguish from the original).
VALUE_V1 = "def value():\n    return 1111\n"
VALUE_V2 = "def value():\n    return 2222\n"
TEST_VALUE = (
    "import unittest\n"
    "from calc import value\n\n"
    "class ValueTests(unittest.TestCase):\n"
    "    def test_value(self):\n"
    "        self.assertEqual(value(), 2222)\n\n"
    "if __name__ == '__main__':\n"
    "    unittest.main()\n")

FORGED_MTIME = 1_600_000_000


def plant_stale_cache(worktree: Path, rel: str, stale_source: str,
                      current_source: str | None = None) -> Path:
    """Forge a bytecode cache Python's mtime+size check accepts for
    the bytes on disk while the cache actually holds *stale_source*'s
    bytecode.

    Deterministic — no timing race: if *current_source* is given it
    is written over the target first; the target's mtime is then
    pinned with os.utime and the cache header (mtime + size fields)
    is rewritten to match it exactly. (Patching the size field is
    precisely the state a genuine same-size rewrite within one mtime
    tick produces on its own.)
    """
    target = worktree / rel
    handle, stale_path = tempfile.mkstemp(suffix='.py')
    try:
        with os.fdopen(handle, 'w', encoding='utf-8') as fh:
            fh.write(stale_source)
        cache = Path(importlib.util.cache_from_source(str(target)))
        py_compile.compile(stale_path, cfile=str(cache), doraise=True)
    finally:
        os.unlink(stale_path)
    if current_source is not None:
        target.write_bytes(current_source.encode())
    current = target.read_bytes()
    os.utime(target, (FORGED_MTIME, FORGED_MTIME))
    header = bytearray(cache.read_bytes())
    header[8:16] = struct.pack('<II', FORGED_MTIME, len(current))
    cache.write_bytes(bytes(header))
    return cache


def naive_import(worktree: Path, expression: str) -> str:
    """Run a plain, unprotected import (no -B, no pycache prefix,
    caches intact) — the control proving a planted trap is armed."""
    env = {k: v for k, v in os.environ.items()
           if k not in ('PYTHONPYCACHEPREFIX',
                        'PYTHONDONTWRITEBYTECODE')}
    proc = subprocess.run([sys.executable, '-c', expression],
                          cwd=worktree, capture_output=True, text=True,
                          env=env)
    if proc.returncode != 0:
        raise RuntimeError(f'control import failed: {proc.stderr}')
    return proc.stdout.strip()


def bytecode_leftovers(root: Path) -> list[str]:
    return sorted(
        str(p.relative_to(root)) for p in root.rglob('*')
        if '.git' not in p.parts
        and (p.name == '__pycache__' or p.suffix in ('.pyc', '.pyo')))


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


class BytecodeFreshnessTests(unittest.TestCase):
    """Verification must mean the bytes on disk (stale-cache flaw).

    Python's timestamp cache validation compares only source mtime
    (whole seconds) and size, so a same-size rewrite within one tick
    is served stale bytecode by a plain interpreter. The runner's
    layered defense — purge, fresh empty pycache prefix, no cache
    writes — is exercised end to end against a deterministically
    forged cache.
    """

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.home = self.base / 'profile'
        self.repo = make_repo(self.base)
        self.grants = TaskGrantStore(self.home)
        self.executor = TaskExecutor(self.home)

    def create_grant(self, repo, **overrides):
        kwargs = dict(
            objective='Synthetic objective', repository=repo,
            queue_item_ids=['roadmap-1'], task_classes=['implement'],
            allowed_files=['calc.py', 'tests/*.py'],
            permitted_tools=['edit', 'run_tests'],
            max_tasks=3, max_test_runs=50, max_retries_per_task=2,
            max_wall_clock_seconds=3600, duration_seconds=3600,
            confirmed=True)
        kwargs.update(overrides)
        return self.grants.create(**kwargs)

    def test_templates_and_env_disable_bytecode_caches(self):
        for template, kwargs in (('syntax', {'files': ['a.py']}),
                                 ('targeted',
                                  {'modules': ['tests.test_calc']}),
                                 ('full', {})):
            argv = build_command(template, self.repo, **kwargs)
            self.assertEqual(argv[1], '-B', template)
        prefix = self.base / 'some-prefix'
        env = _scrubbed_env(self.repo, prefix)
        self.assertEqual(env['PYTHONDONTWRITEBYTECODE'], '1')
        self.assertEqual(env['PYTHONPYCACHEPREFIX'], str(prefix))
        # Without a prefix the variable is simply absent (the caller
        # passes a fresh one per run).
        self.assertNotIn('PYTHONPYCACHEPREFIX',
                         _scrubbed_env(self.repo))

    def test_fresh_pycache_prefix_is_empty_and_removed(self):
        with _fresh_pycache_prefix() as prefix:
            self.assertTrue(prefix.is_dir())
            self.assertEqual(list(prefix.iterdir()), [])
        self.assertFalse(prefix.exists())

    def test_purge_removes_only_bytecode_caches(self):
        tree = self.base / 'tree'
        (tree / 'pkg' / '__pycache__').mkdir(parents=True)
        (tree / '__pycache__').mkdir()
        (tree / '.git' / '__pycache__').mkdir(parents=True)
        (tree / 'pkg' / 'mod.py').write_text('x = 1\n', encoding='utf-8')
        (tree / 'pkg' / '__pycache__' / 'mod.cpython-312.pyc') \
            .write_bytes(b'cache')
        (tree / '__pycache__' / 'top.cpython-312.pyc').write_bytes(b'c')
        (tree / '.git' / '__pycache__' / 'git.cpython-312.pyc') \
            .write_bytes(b'cache')
        (tree / 'loose.pyc').write_bytes(b'cache')
        (tree / 'loose.pyo').write_bytes(b'cache')
        (tree / 'keep.pyc.txt').write_text('not a cache',
                                           encoding='utf-8')
        removed = purge_bytecode_caches(tree)
        # Two __pycache__ directories + the two loose cache files;
        # the .git tree is never descended into.
        self.assertEqual(removed, 4)
        self.assertEqual(bytecode_leftovers(tree), [])
        self.assertTrue((tree / '.git' / '__pycache__'
                         / 'git.cpython-312.pyc').exists())
        self.assertEqual((tree / 'pkg' / 'mod.py').read_text(
            encoding='utf-8'), 'x = 1\n')
        self.assertEqual((tree / 'keep.pyc.txt').read_text(
            encoding='utf-8'), 'not a cache')

    def test_purge_never_follows_symlinks_out_of_the_tree(self):
        tree = self.base / 'tree'
        (tree / 'sub').mkdir(parents=True)
        outside = self.base / 'outside'
        (outside / '__pycache__').mkdir(parents=True)
        (outside / '__pycache__' / 'evil.pyc').write_bytes(b'cache')
        try:
            os.symlink(outside / '__pycache__',
                       tree / 'sub' / '__pycache__',
                       target_is_directory=True)
            os.symlink(outside, tree / 'vendor',
                       target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('symlinks unavailable')
        purge_bytecode_caches(tree)
        # The symlinks are left in place and nothing outside the
        # tree was removed.
        self.assertTrue((tree / 'sub' / '__pycache__').is_symlink())
        self.assertTrue((tree / 'vendor').is_symlink())
        self.assertEqual(
            (outside / '__pycache__' / 'evil.pyc').read_bytes(),
            b'cache')

    def test_runner_executes_disk_bytes_not_stale_cache(self):
        stale_base = self.base / 'stalecase'
        stale_base.mkdir()
        stale_repo = make_repo(stale_base, {
            'calc.py': VALUE_V1, 'tests/test_calc.py': TEST_VALUE})
        grant = self.create_grant(stale_repo)
        control = []

        def plant_and_edit(item, worktree, diagnostics):
            # Arm the trap inside the fresh worktree: the cache holds
            # V1's bytecode, forged to match the same-size V2 source
            # now on disk. A plain interpreter serves V1 (control);
            # the constrained runner must serve the V2 bytes.
            plant_stale_cache(worktree, 'calc.py', VALUE_V1, VALUE_V2)
            control.append(naive_import(
                worktree, 'from calc import value; print(value())'))
            # An authorized edit so the attempt has stages to run:
            # a same-content rewrite of the test file.
            return [{'path': 'tests/test_calc.py',
                     'content': TEST_VALUE}]

        record = self.executor.execute(
            grant['id'], ITEM, ScriptedEditor([plant_and_edit]))
        self.assertEqual(control, ['1111'])  # trap armed, stale served
        self.assertEqual(record['outcome'], 'succeeded')
        runs = [r for r in record['attempts'][0]['runs']
                if not r['skipped']]
        self.assertTrue(runs)
        self.assertTrue(all(r['exit_code'] == 0 for r in runs))
        self.assertEqual(
            bytecode_leftovers(Path(record['worktree'])), [])

    def test_run_leaves_no_bytecode_caches_in_worktree(self):
        grant = self.create_grant(self.repo)
        record = self.executor.execute(
            grant['id'], ITEM,
            ScriptedEditor([[{'path': 'calc.py', 'content': FIXED}]]))
        self.assertEqual(record['outcome'], 'succeeded')
        self.assertEqual(
            bytecode_leftovers(Path(record['worktree'])), [])


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
