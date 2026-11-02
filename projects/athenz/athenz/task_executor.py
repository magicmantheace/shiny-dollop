"""Isolated execution and feedback loop (roadmap slice A3).

The executor runs ONE planner queue item (slice A1) under ONE standing
task grant (slice A2) through a bounded feedback loop:

    plan -> edit -> syntax check -> targeted tests -> full regression
         -> diagnose -> retry (bounded)

Every operation passes through ``TaskGrantStore.authorize(...)`` first:
starting the task consumes the grant's task budget, each edit is
checked against the grant's file scope, each test-runner invocation
consumes the grant's test-run budget atomically with its check, and
retries consume the per-task retry budget. Authorization is re-checked
between attempts, so a grant paused or revoked mid-run stops the loop
at the next boundary. Denied operations are never performed; the grant
store audits every check, allowed and denied.

Isolation:

- Work happens in a disposable Git worktree of the granted repository
  on a scratch branch (``athenz-task/<grant>-<item>-<exec>``) based on
  the repository HEAD fingerprinted at start. The owner's original
  working tree is never written.
- Edits come from an injected *editor* callable. A3 ships the harness,
  not a model integration: the deterministic :class:`ScriptedEditor`
  below is what tests and the CLI's editor script use; a model-backed
  editor plugs into the same interface later.
- Tests run through a constrained runner: fixed argv templates only
  (never a shell string), a scrubbed environment, a timeout, and no
  network by construction. Only tools named in the grant's
  ``permitted_tools`` can be invoked at all.
- Verification means the bytes on disk: before and after every
  runner invocation, :func:`purge_bytecode_caches` removes any
  ``__pycache__``/``*.pyc`` under the worktree; each run's scrubbed
  environment points ``PYTHONPYCACHEPREFIX`` at a fresh empty
  directory so every cache lookup misses and imports always compile
  from source; and ``-B``/``PYTHONDONTWRITEBYTECODE=1`` stop runner
  processes writing caches at all. A stale cache — Python's
  mtime+size check can serve one when a same-size file is rewritten
  within one mtime tick — can therefore never substitute old
  bytecode for the candidate bytes being verified. (``-B`` alone
  would not suffice: it governs writing, not reading.)
- This module has no code path that reads the private Twin/identity
  stores. Its only profile access is the grant store (for
  ``authorize()``) and its own execution-record tables, in the same
  private profile database slice A2 uses.

The scratch branch and worktree are KEPT when the run ends, whatever
the outcome, for owner review. The executor never merges, pushes,
commits or deletes them — promotion and disposal are slice A5, and
durability/resume across process restarts is slice A4.

Outcomes are recorded exactly as observed: ``succeeded`` only when
every non-skipped verification stage ran green and at least one test
stage actually ran; ``failed`` when attempts or budgets ran out with
tests still red; ``blocked`` when the editor, the grant's state or a
lack of runnable verification stopped the loop; ``denied`` when an
authorization check refused an operation. A record never claims
success the tests did not demonstrate.
"""
from __future__ import annotations

from contextlib import contextmanager
import difflib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid

from .coding import MAX_FILE, protected_repository_path
from .experience import ExperienceStore
from .store import utc_now
from .task_grants import TaskGrantStore

RECORD_SCHEMA = 'athenz.task-execution/v1'

# Hard cap on attempts per task, whatever the grant's retry budget says.
MAX_ATTEMPTS = 5
DEFAULT_COMMAND_TIMEOUT = 120
OUTPUT_TAIL_CHARS = 4000
DIAGNOSTIC_TAIL_CHARS = 2000
MAX_DIFF_CHARS = 20000

EDIT_TOOL = 'edit'
RUN_TESTS_TOOL = 'run_tests'

# The only command templates the runner can build. Each is an argv
# list; there is no shell anywhere in this module.
TEMPLATES = ('syntax', 'targeted', 'full')

# Environment variables a test command may inherit. Everything else —
# credentials, tokens, ATHENZ_HOME, PYTHONPATH — is scrubbed by
# construction. HOME is additionally redirected into the worktree.
_ENV_ALLOWLIST = ('PATH', 'PATHEXT', 'SYSTEMROOT', 'WINDIR', 'COMSPEC',
                  'TEMP', 'TMP', 'TMPDIR', 'LANG', 'LC_ALL', 'LC_CTYPE',
                  'TZ')

_GRANT_STATE_REASONS = frozenset({'grant_paused', 'grant_revoked',
                                  'grant_expired'})
_BUDGET_REASONS = frozenset({'budget_tasks_exhausted',
                             'budget_test_runs_exhausted',
                             'budget_retries_exceeded',
                             'budget_wall_clock_exhausted'})


class ExecutorError(RuntimeError):
    """The executor cannot proceed within its isolation bounds."""


class EditorBlocked(Exception):
    """The editor cannot produce a further edit; stop as blocked."""


class _StopRun(Exception):
    """Internal: abort the loop with a recorded outcome and reason."""

    def __init__(self, outcome: str, reason: str):
        super().__init__(reason)
        self.outcome = outcome
        self.reason = reason


# ---------------------------------------------------------------------------
# Editors
# ---------------------------------------------------------------------------

def _validate_edit(edit) -> tuple[str, str]:
    if not isinstance(edit, dict) or set(edit) != {'path', 'content'}:
        raise EditorBlocked(
            'editor returned a malformed edit (want {"path", "content"})')
    rel, content = edit['path'], edit['content']
    if not isinstance(rel, str) or not rel.strip():
        raise EditorBlocked('editor returned an edit with an invalid path')
    if not isinstance(content, str):
        raise EditorBlocked(f'editor edit for {rel!r} is not text')
    if len(content.encode('utf-8')) > MAX_FILE:
        raise EditorBlocked(f'editor edit for {rel!r} exceeds the '
                            f'{MAX_FILE}-byte file limit')
    return rel, content


class ScriptedEditor:
    """Deterministic editor: one scripted step per attempt.

    Each step is either a list of edit dicts (``{'path', 'content'}`` —
    full-file replacement, the same shape as slice v0.4 proposals), an
    :class:`EditorBlocked` instance to raise, or a callable
    ``(item, worktree, diagnostics) -> list`` for steps that need a
    side effect (e.g. a test revoking the grant mid-run). When the
    script runs out, the editor reports itself blocked rather than
    inventing edits.
    """

    def __init__(self, steps):
        self._steps = list(steps)

    def __call__(self, item: dict, worktree: Path, diagnostics):
        if not self._steps:
            raise EditorBlocked('editor script exhausted')
        step = self._steps.pop(0)
        if isinstance(step, EditorBlocked):
            raise step
        if callable(step):
            return step(item, worktree, diagnostics)
        return step


# ---------------------------------------------------------------------------
# Execution records (private profile data, slice A2 store style)
# ---------------------------------------------------------------------------

class TaskExecutionStore:
    """Durable per-task execution records in the profile database."""

    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home is not None else None
        with self._open() as store:
            store.db.execute('''CREATE TABLE IF NOT EXISTS task_executions (
                id TEXT PRIMARY KEY,
                grant_id TEXT NOT NULL,
                item_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                outcome TEXT,
                record_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )''')
            store.db.commit()

    @contextmanager
    def _open(self):
        store = ExperienceStore(self.home)
        try:
            yield store
        finally:
            store.close()

    def create(self, record: dict) -> None:
        with self._open() as store:
            with store.db:
                store.db.execute(
                    'INSERT INTO task_executions (id,grant_id,item_id,task_id,'
                    'outcome,record_json,created_at,updated_at)'
                    ' VALUES (?,?,?,?,?,?,?,?)',
                    (record['id'], record['grant_id'],
                     record['item']['id'], record['task_id'],
                     record['outcome'], json.dumps(record, sort_keys=True),
                     record['started_at'], record['started_at']))

    def update(self, record: dict) -> None:
        with self._open() as store:
            with store.db:
                store.db.execute(
                    'UPDATE task_executions SET outcome=?, record_json=?,'
                    ' updated_at=? WHERE id=?',
                    (record['outcome'], json.dumps(record, sort_keys=True),
                     utc_now(), record['id']))

    def get(self, execution_id: str) -> dict | None:
        with self._open() as store:
            row = store.db.execute(
                'SELECT record_json FROM task_executions WHERE id=?',
                (execution_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, grant_id: str | None = None) -> list[dict]:
        with self._open() as store:
            if grant_id is None:
                rows = store.db.execute(
                    'SELECT record_json FROM task_executions'
                    ' ORDER BY created_at').fetchall()
            else:
                rows = store.db.execute(
                    'SELECT record_json FROM task_executions'
                    ' WHERE grant_id=? ORDER BY created_at',
                    (grant_id,)).fetchall()
            return [json.loads(row[0]) for row in rows]


# ---------------------------------------------------------------------------
# Git + path helpers
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> str:
    """Local Git only, following the supervised worker's pattern.

    No shell, hooks disabled, no prompts or remote operations. Process
    output is never surfaced in errors (it can embed private paths).
    """
    cmd = ['git', '-c', 'core.hooksPath=/dev/null',
           '-c', 'protocol.file.allow=never', '-C', str(repo), *args]
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True,
                              check=False, timeout=45,
                              env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'})
    except (OSError, subprocess.SubprocessError):
        raise ExecutorError('Local Git command unavailable or timed out') \
            from None
    if proc.returncode:
        raise ExecutorError('Local Git operation failed; inspect the '
                            'trusted repository manually')
    return proc.stdout.rstrip('\n')


def _branch_component(text: str, fallback: str) -> str:
    cleaned = re.sub(r'[^a-z0-9._-]+', '-', str(text).lower()).strip('.-')
    cleaned = cleaned.replace('..', '-')
    return cleaned or fallback


def _resolve_edit_path(worktree: Path, rel: str) -> Path:
    """Resolve an edit path strictly inside *worktree*.

    Mirrors the supervised coding scope checks: no absolute paths, no
    backslashes, no ``.``/``..`` components, no protected filenames, no
    symlink components. The leaf itself may not exist yet (creation).
    """
    if not isinstance(rel, str) or not rel or '\\' in rel \
            or Path(rel).is_absolute():
        raise _StopRun('denied', 'path_not_allowed')
    parts = Path(rel).parts
    if any(p in {'.', '..'} for p in parts) \
            or protected_repository_path(parts):
        raise _StopRun('denied', 'path_not_allowed')
    candidate = worktree
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink():
            raise _StopRun('denied', 'path_not_allowed')
    resolved = candidate.resolve(strict=False)
    if not resolved.is_relative_to(worktree.resolve()):
        raise _StopRun('denied', 'path_not_allowed')
    return candidate


def _read_exact(path: Path) -> str:
    with path.open('r', encoding='utf-8', newline='') as handle:
        return handle.read()


def _diff(rel: str, before: str, after: str) -> str:
    text = ''.join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile='a/' + rel, tofile='b/' + rel))
    if len(text) > MAX_DIFF_CHARS:
        text = text[:MAX_DIFF_CHARS] + '\n[diff truncated]\n'
    return text


def _tail(text) -> str:
    if text is None:
        return ''
    if isinstance(text, bytes):
        text = text.decode('utf-8', errors='replace')
    return text[-OUTPUT_TAIL_CHARS:]


def _targeted_modules(worktree: Path, edited: list[str],
                      extra: list[str]) -> list[str]:
    """Derive targeted unittest modules from the files edited so far.

    An edited test file is its own target; an edited source file maps
    to ``tests/test_<stem>.py`` when that file exists in the worktree.
    Nothing else is guessed.
    """
    modules: list[str] = []

    def add(module: str) -> None:
        if module not in modules:
            modules.append(module)

    for module in extra:
        add(module)
    for rel in edited:
        path = Path(rel)
        if path.suffix != '.py':
            continue
        if path.name.startswith('test_'):
            add('.'.join(path.with_suffix('').parts))
        else:
            candidate = Path('tests') / f'test_{path.stem}.py'
            if (worktree / candidate).is_file():
                add('.'.join(candidate.with_suffix('').parts))
    return modules


def build_command(template: str, worktree: Path, *,
                  files=(), modules=()) -> list[str]:
    """Build the argv for one runner template. Templates are fixed.

    There is deliberately no way to build an arbitrary command: an
    unknown template raises :class:`ExecutorError`.

    Every template carries ``-B`` so the interpreter never *writes*
    bytecode caches. Reading is governed separately: the scrubbed
    environment points ``PYTHONPYCACHEPREFIX`` at a fresh empty
    directory per run (every cache lookup misses, so imports compile
    from the source bytes on disk) and the pre/post-run purge removes
    any caches already in the tree. Together these make Python's
    mtime+size cache check irrelevant to runner verdicts.
    """
    if template == 'syntax':
        return [sys.executable, '-B', '-m', 'py_compile', *files]
    if template == 'targeted':
        return [sys.executable, '-B', '-m', 'unittest', '-v', *modules]
    if template == 'full':
        return [sys.executable, '-B', '-m', 'unittest', 'discover',
                '-s', 'tests']
    raise ExecutorError(f'Unknown runner template: {template!r}')


def _scrubbed_env(worktree: Path,
                  pycache_prefix: Path | None = None) -> dict:
    env = {name: os.environ[name] for name in _ENV_ALLOWLIST
           if name in os.environ}
    env['HOME'] = str(worktree)
    env['PYTHONNOUSERSITE'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    # Bytecode freshness, layered with the -B flag in every argv
    # template and the pre/post-run purge: PYTHONDONTWRITEBYTECODE
    # stops runner processes (and Python children inheriting this
    # environment) writing caches, and a fresh empty
    # PYTHONPYCACHEPREFIX makes every cache *read* miss, so imports
    # always compile the source bytes currently on disk.
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    if pycache_prefix is not None:
        env['PYTHONPYCACHEPREFIX'] = str(pycache_prefix)
    return env


@contextmanager
def _fresh_pycache_prefix():
    """Yield a fresh empty directory for one run's PYTHONPYCACHEPREFIX.

    The directory is created outside the candidate worktree and
    removed when the run ends, whatever the outcome. Because it
    starts empty and bytecode writing is disabled, it stays empty:
    its only job is to make cache lookups miss.
    """
    path = Path(tempfile.mkdtemp(prefix='athenz-pycache-'))
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)


# Bound on the cache-purge walk, so a pathological tree cannot make
# a runner invocation scan forever. No single layer is load-bearing:
# the purge removes caches already in the tree, the fresh empty
# PYTHONPYCACHEPREFIX makes runner cache reads miss, and -B /
# PYTHONDONTWRITEBYTECODE stop runner processes writing new ones.
_MAX_PURGE_ENTRIES = 100_000


def purge_bytecode_caches(root: Path) -> int:
    """Remove bytecode caches under *root*; return the count removed.

    Only directories named ``__pycache__`` and files ending in
    ``.pyc``/``.pyo`` are removed — never source files or anything
    else. The walk never follows symlinks: a symlinked ``__pycache__``
    directory or cache file is left untouched, symlinked directories
    are not descended into, and ``.git`` is not descended into
    (bytecode there is never imported). Every removal is
    containment-checked against the resolved *root* first, in the
    same path-safety discipline as :func:`_resolve_edit_path`.

    Removal is best-effort per entry: an entry that cannot be removed
    is skipped rather than failing the run, because the run's fresh
    empty ``PYTHONPYCACHEPREFIX`` independently makes any surviving
    cache invisible to the verification process's imports.
    """
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        return 0
    resolved_root = root.resolve()
    removed = 0
    seen = 0
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        seen += len(dirnames) + len(filenames)
        if seen > _MAX_PURGE_ENTRIES:
            break
        base = Path(dirpath)
        descend = []
        for name in dirnames:
            candidate = base / name
            if name == '__pycache__':
                if not candidate.is_symlink() \
                        and candidate.resolve().is_relative_to(
                            resolved_root):
                    shutil.rmtree(candidate, ignore_errors=True)
                    if not candidate.exists():
                        removed += 1
                continue  # never descend into a cache directory
            if name == '.git' or candidate.is_symlink():
                continue
            descend.append(name)
        dirnames[:] = descend
        for name in filenames:
            if not name.endswith(('.pyc', '.pyo')):
                continue
            candidate = base / name
            if candidate.is_symlink() \
                    or not candidate.resolve().is_relative_to(
                        resolved_root):
                continue
            try:
                candidate.unlink()
                removed += 1
            except OSError:
                continue
    return removed


class _Clock:
    """Pending wall-clock seconds to declare on the next authorize()."""

    def __init__(self):
        self._t0 = time.monotonic()
        self._accounted = 0

    def take(self) -> int:
        delta = int(time.monotonic() - self._t0) - self._accounted
        if delta > 0:
            self._accounted += delta
            return delta
        return 0


def _deny_outcome(reason: str, *, phase: str) -> str:
    """Map an authorize() denial reason to an execution outcome.

    ``phase`` is 'initial' (the task-start gate), 'boundary' (between
    attempts), 'edit' (edit pre-flight) or 'run' (test-runner gate).
    """
    if phase == 'initial':
        return 'denied'
    if reason in _GRANT_STATE_REASONS:
        return 'blocked'
    if reason in _BUDGET_REASONS:
        return 'failed'
    if phase == 'boundary':
        return 'blocked'
    return 'denied'


# ---------------------------------------------------------------------------
# Executor
# ---------------------------------------------------------------------------

class TaskExecutor:
    """Execute one planner queue item under one grant. See module docs."""

    def __init__(self, home: Path | None = None, *,
                 command_timeout: int = DEFAULT_COMMAND_TIMEOUT):
        if isinstance(command_timeout, bool) \
                or not isinstance(command_timeout, int) \
                or command_timeout < 1:
            raise ExecutorError('command_timeout must be a positive int')
        self.grants = TaskGrantStore(home)
        self.records = TaskExecutionStore(home)
        self.command_timeout = command_timeout
        with self.grants._open() as store:
            self.home = store.home.resolve()
        self.worktree_root = self.home / 'task-worktrees'

    # -- setup ------------------------------------------------------------

    def _prepare(self, grant: dict, item: dict) -> dict:
        repo = Path(grant['repository'])
        base_sha = _git(repo, 'rev-parse', '--verify', 'HEAD')
        if not re.fullmatch(r'[0-9a-f]{40,64}', base_sha):
            raise ExecutorError('Granted repository HEAD is not a commit')
        branch_ref = _git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
        execution_id = 'exec-' + uuid.uuid4().hex[:16]
        branch = 'athenz-task/{}-{}-{}'.format(
            _branch_component(grant['id'], 'grant'),
            _branch_component(item['id'], 'item'),
            execution_id.removeprefix('exec-')[:8])
        worktree = self.worktree_root / execution_id
        return {
            'schema': RECORD_SCHEMA,
            'id': execution_id,
            'grant_id': grant['id'],
            'item': {'id': item['id'], 'title': item.get('title', ''),
                     'success_criteria': item.get('success_criteria', ''),
                     'scope': item.get('scope', []),
                     'source': item.get('source', {})},
            'task_id': f"{grant['id']}:{item['id']}",
            'repository': str(repo),
            'base_sha': base_sha,
            'base_branch': None if branch_ref == 'HEAD' else branch_ref,
            'branch': branch,
            'worktree': str(worktree),
            'started_at': utc_now(),
            'finished_at': None,
            'outcome': None,
            'stop_reason': '',
            'attempts': [],
            'budget_usage': None,
        }

    # -- one test-runner invocation ----------------------------------------

    def _run_stage(self, record: dict, grant: dict, *, task_class: str,
                   clock: _Clock, stage: str, argv: list[str],
                   worktree: Path) -> dict:
        check = self.grants.authorize(
            grant['id'], repository=record['repository'],
            task_class=task_class, tool=RUN_TESTS_TOOL,
            task_id=record['task_id'], test_run=True,
            wall_clock_seconds=clock.take())
        run = {'stage': stage, 'template': stage, 'argv': argv,
               'exit_code': None, 'timed_out': False,
               'duration_seconds': 0.0, 'stdout_tail': '',
               'stderr_tail': '', 'skipped': False, 'skip_reason': ''}
        if not check['allowed']:
            raise _StopRun(
                _deny_outcome(check['reason'], phase='run'),
                check['reason'])
        # Bytecode freshness: drop any pre-existing caches, run with
        # a fresh empty pycache prefix so cache reads miss, and drop
        # whatever the run leaves so the kept worktree carries no
        # caches into later stages, proposals or owner review. (The
        # layers are independent: py_compile writes its cache even
        # under -B, and -B alone does not stop cache reads.)
        purge_bytecode_caches(worktree)
        started = time.monotonic()
        try:
            with _fresh_pycache_prefix() as prefix:
                proc = subprocess.run(
                    argv, cwd=worktree,
                    env=_scrubbed_env(worktree, prefix),
                    capture_output=True, text=True,
                    timeout=self.command_timeout)
            run['exit_code'] = proc.returncode
            run['stdout_tail'] = _tail(proc.stdout)
            run['stderr_tail'] = _tail(proc.stderr)
        except subprocess.TimeoutExpired as exc:
            run['timed_out'] = True
            run['stdout_tail'] = _tail(exc.stdout)
            run['stderr_tail'] = _tail(exc.stderr)
        except OSError as exc:
            run['stderr_tail'] = f'runner unavailable: {exc}'
            run['exit_code'] = None
        finally:
            purge_bytecode_caches(worktree)
        run['duration_seconds'] = round(time.monotonic() - started, 3)
        return run

    @staticmethod
    def _skipped(stage: str, reason: str) -> dict:
        return {'stage': stage, 'template': stage, 'argv': [],
                'exit_code': None, 'timed_out': False,
                'duration_seconds': 0.0, 'stdout_tail': '',
                'stderr_tail': '', 'skipped': True, 'skip_reason': reason}

    # -- the loop -----------------------------------------------------------

    def execute(self, grant_id: str, item: dict, editor, *,
                task_class: str = 'implement',
                extra_test_modules=()) -> dict:
        """Run *item* under grant *grant_id* with *editor*; return the record.

        *editor* is a callable ``(item, worktree, diagnostics)`` ->
        list of ``{'path', 'content'}`` edits, raising
        :class:`EditorBlocked` when it cannot proceed. *diagnostics*
        is ``None`` on the first attempt.
        """
        grant = self.grants.get(grant_id)
        if grant is None:
            raise ExecutorError(f'No such grant: {grant_id}')
        if not isinstance(item, dict) or not item.get('id'):
            raise ExecutorError('A planner queue item with an id is '
                                'required')
        record = self._prepare(grant, item)
        self.records.create(record)
        clock = _Clock()
        try:
            self._loop(record, grant, item, editor,
                       task_class=task_class, clock=clock,
                       extra_test_modules=list(extra_test_modules))
        finally:
            record['finished_at'] = utc_now()
            current = self.grants.get(grant_id)
            if current is not None:
                record['budget_usage'] = {
                    key: current[key] for key in
                    ('tasks_used', 'max_tasks', 'test_runs_used',
                     'max_test_runs', 'wall_clock_seconds_used',
                     'max_wall_clock_seconds')}
            self.records.update(record)
        return record

    def _loop(self, record: dict, grant: dict, item: dict, editor, *,
              task_class: str, clock: _Clock,
              extra_test_modules: list[str]) -> None:
        repo = Path(record['repository'])
        worktree = Path(record['worktree'])
        # Gate 1: starting the task itself. Atomic with consuming the
        # grant's task budget; a denial here means no worktree, no edits.
        check = self.grants.authorize(
            grant['id'], repository=record['repository'],
            task_class=task_class, task_id=record['task_id'],
            new_task=True)
        if not check['allowed']:
            record['outcome'] = 'denied'
            record['stop_reason'] = check['reason']
            return
        max_attempts = min(MAX_ATTEMPTS,
                           1 + grant['max_retries_per_task'])
        self.worktree_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        _git(repo, 'worktree', 'add', '-b', record['branch'],
             str(worktree), record['base_sha'])
        if worktree.resolve().parent != self.worktree_root.resolve():
            raise ExecutorError('Worktree escaped its designated root')
        edited_all: list[str] = []
        diagnostics = None
        attempt_no = 0
        while True:
            attempt_no += 1
            if attempt_no > 1:
                # Between attempts: re-check authorization and consume
                # one retry (plus accrued wall-clock) atomically.
                check = self.grants.authorize(
                    grant['id'], repository=record['repository'],
                    task_class=task_class, task_id=record['task_id'],
                    retry=True, wall_clock_seconds=clock.take())
                if not check['allowed']:
                    record['outcome'] = _deny_outcome(
                        check['reason'], phase='boundary')
                    record['stop_reason'] = check['reason']
                    return
            attempt = {'n': attempt_no, 'started_at': utc_now(),
                       'editor': 'ok', 'edits': [], 'runs': []}
            record['attempts'].append(attempt)
            try:
                self._attempt(record, grant, attempt, item, editor,
                              worktree=worktree, task_class=task_class,
                              clock=clock, diagnostics=diagnostics,
                              edited_all=edited_all,
                              extra_test_modules=extra_test_modules)
            except _StopRun as stop:
                record['outcome'] = stop.outcome
                record['stop_reason'] = stop.reason
                return
            if attempt['runs'] and self._attempt_green(attempt):
                record['outcome'] = 'succeeded'
                record['stop_reason'] = ''
                return
            failing = next(
                (r for r in attempt['runs']
                 if not r['skipped'] and r['exit_code'] != 0), None)
            if failing is None:
                # Everything was skipped or no stage ran: nothing was
                # verified, so success cannot be claimed.
                record['outcome'] = 'blocked'
                record['stop_reason'] = 'no_runnable_verification'
                return
            diagnostics = {
                'attempt': attempt_no,
                'stage': failing['stage'],
                'exit_code': failing['exit_code'],
                'timed_out': failing['timed_out'],
                'output': (failing['stderr_tail']
                           + failing['stdout_tail'])
                          [-DIAGNOSTIC_TAIL_CHARS:],
                'edited_files': list(edited_all),
            }
            if attempt_no >= max_attempts:
                record['outcome'] = 'failed'
                record['stop_reason'] = 'attempts_exhausted'
                return
            self.records.update(record)

    @staticmethod
    def _attempt_green(attempt: dict) -> bool:
        ran = [r for r in attempt['runs'] if not r['skipped']]
        tests_ran = [r for r in ran if r['stage'] in ('targeted', 'full')]
        return bool(tests_ran) and all(r['exit_code'] == 0 for r in ran)

    def _attempt(self, record: dict, grant: dict, attempt: dict,
                 item: dict, editor, *, worktree: Path,
                 task_class: str, clock: _Clock, diagnostics,
                 edited_all: list[str],
                 extra_test_modules: list[str]) -> None:
        try:
            edits = editor(item, worktree, diagnostics)
        except EditorBlocked as exc:
            attempt['editor'] = f'blocked: {exc}'
            raise _StopRun('blocked', str(exc) or 'editor_blocked')
        if not edits:
            attempt['editor'] = 'no_edits'
            raise _StopRun('blocked', 'editor_returned_no_edits')
        validated = []
        for edit in edits:
            try:
                validated.append(_validate_edit(edit))
            except EditorBlocked as exc:
                attempt['editor'] = f'blocked: {exc}'
                raise _StopRun('blocked', str(exc))
        # Pre-flight: authorize EVERY edit before applying ANY, so a
        # denied edit never leaves a half-applied attempt behind.
        resolved = []
        for rel, content in validated:
            check = self.grants.authorize(
                grant['id'], repository=record['repository'],
                task_class=task_class, file=rel, tool=EDIT_TOOL,
                task_id=record['task_id'],
                wall_clock_seconds=clock.take())
            if not check['allowed']:
                raise _StopRun(
                    _deny_outcome(check['reason'], phase='edit'),
                    check['reason'])
            resolved.append(
                (rel, content, _resolve_edit_path(worktree, rel)))
        for rel, content, path in resolved:
            created = not path.is_file()
            before = '' if created else _read_exact(path)
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open('w', encoding='utf-8', newline='') as handle:
                handle.write(content)
            attempt['edits'].append({
                'path': rel, 'created': created,
                'diff': _diff(rel, before, content)})
            if rel not in edited_all:
                edited_all.append(rel)
        # Verification stages, in order, stopping at the first failure.
        py_files = [rel for rel, _, _ in resolved if rel.endswith('.py')]
        stages: list[tuple[str, list[str] | None, str]] = []
        if py_files:
            stages.append(('syntax', build_command(
                'syntax', worktree, files=py_files), ''))
        else:
            stages.append(('syntax', None, 'no Python files edited'))
        modules = _targeted_modules(worktree, edited_all,
                                     extra_test_modules)
        if modules:
            stages.append(('targeted', build_command(
                'targeted', worktree, modules=modules), ''))
        else:
            stages.append(('targeted', None,
                           'no targeted test modules derived'))
        if (worktree / 'tests').is_dir():
            stages.append(('full', build_command('full', worktree), ''))
        else:
            stages.append(('full', None, 'no tests directory'))
        for stage, argv, skip_reason in stages:
            if argv is None:
                attempt['runs'].append(self._skipped(stage, skip_reason))
                continue
            run = self._run_stage(record, grant, task_class=task_class,
                                  clock=clock, stage=stage, argv=argv,
                                  worktree=worktree)
            attempt['runs'].append(run)
            if run['exit_code'] != 0:
                break
