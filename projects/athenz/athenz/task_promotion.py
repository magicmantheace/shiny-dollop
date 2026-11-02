"""Promotion and self-development boundary (roadmap slice A5).

Slices A3/A4 produce *candidates*: edits sitting uncommitted on an
isolated scratch branch (``athenz-task/...``) in a disposable worktree
under the private profile. This module is the only bridge between a
candidate and anything more durable, and the bridge is deliberately
narrow:

- :meth:`TaskPromoter.prepare_proposal` builds a durable proposal for
  a **succeeded** execution (directly, or via its A4 operation item):
  the candidate's full diff against its recorded base revision, the
  linked A3/A4 evidence, a **fresh** full-suite regression run in the
  scratch worktree through slice A3's constrained runner, the grant's
  state at proposal time, and a rollback plan. A proposal is
  promotable only when that fresh regression actually ran green.
- :meth:`TaskPromoter.commit_checkpoint` is the ONLY write this module
  can perform on a candidate, and it is small: one local commit, on
  the isolated scratch branch, containing exactly the proposal's
  recorded diff, under explicit owner confirmation, and only while
  the worktree's diff still matches the proposal byte-for-byte (by
  hash). If the candidate moved, the owner re-prepares.
- :meth:`TaskPromoter.discard_candidate` is the owner-confirmed
  disposal path A3/A4 deferred here: it removes the scratch worktree
  and deletes the scratch branch, recording what was discarded (its
  final diff hash) in the proposal store. It refuses any branch that
  is not an ``athenz-task/`` scratch branch and any worktree outside
  the managed location.

The boundary is by construction, not by policy text: this module
exposes **no** push, merge, tag, release, package-install, deploy or
self-update operation, and nothing here can modify the running AthenZ.
Landing a checkpointed candidate — merging it anywhere, publishing
it, replacing the installed AthenZ with it — remains a separately
reviewed owner decision taken through the owner's own route, with
its own regression and rollback checks. Every proposal ends with an
explicit ``remaining_owner_steps`` section saying exactly that.

Proposals and disposals are private profile data, stored in the same
profile database as grants, execution records and operations — never
in a repository.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import difflib
import hashlib
import json
from pathlib import Path
import subprocess
import time
import uuid

from .experience import ExperienceStore
from .store import utc_now
from .task_executor import (DEFAULT_COMMAND_TIMEOUT, ExecutorError,
                            RUN_TESTS_TOOL, TaskExecutionStore,
                            _git as _executor_git, _scrubbed_env, _tail,
                            build_command)
from .task_grants import TaskGrantStore
from .task_operations import TaskOperationStore

PROMOTION_SCHEMA = 'athenz.task-promotion/v1'

# A3's scratch branches always carry this prefix; nothing outside it
# is a candidate this module may commit to or dispose of.
SCRATCH_BRANCH_PREFIX = 'athenz-task/'

PROPOSAL_STATES = frozenset({'prepared', 'committed', 'discarded'})

_GRANT_SNAPSHOT_FIELDS = (
    'id', 'state', 'repository', 'worktree', 'task_classes',
    'permitted_tools', 'tasks_used', 'max_tasks', 'test_runs_used',
    'max_test_runs', 'wall_clock_seconds_used',
    'max_wall_clock_seconds', 'expires_at')


class PromotionError(RuntimeError):
    """The promotion action did not meet its owner-gated boundaries."""


def _git(repo: Path, *args: str) -> str:
    try:
        return _executor_git(repo, *args)
    except ExecutorError as exc:
        raise PromotionError(str(exc)) from exc


# ---------------------------------------------------------------------------
# Candidate diff (working tree versus the recorded base revision)
# ---------------------------------------------------------------------------

def _untracked_patch(rel: str, path: Path) -> tuple[str, int]:
    """A git-style new-file patch for one untracked file, plus its
    insertion count. Binary/unreadable files are represented honestly
    instead of being decoded into garbage."""
    try:
        text = path.read_bytes().decode('utf-8')
    except (OSError, UnicodeDecodeError):
        try:
            size = path.stat().st_size
        except OSError:
            size = -1
        return (f'Binary file {rel} (untracked, {size} bytes) '
                f'not shown\n'), 0
    patch = ''.join(difflib.unified_diff(
        [], text.splitlines(keepends=True),
        fromfile='a/' + rel, tofile='b/' + rel))
    return patch, len(text.splitlines())


def _is_generated_artifact(rel: str) -> bool:
    """Python bytecode caches are artifacts of *running* the tests —
    slice A3's own verification runs create them in the worktree —
    never candidate source edits (the editor writes text files). They
    are excluded from candidate diffs; everything else is included.
    """
    parts = Path(rel).parts
    return '__pycache__' in parts or rel.endswith(('.pyc', '.pyo'))


def _candidate_diff(worktree: Path, base_sha: str) -> dict:
    """The full diff of *worktree* against *base_sha*.

    Tracked changes come from ``git diff <base>`` (which compares the
    working tree with the base commit, so staged, unstaged and
    already-checkpointed changes are all included); untracked files —
    the files an A3 editor created — are appended as synthesized
    new-file patches in sorted order. The result is deterministic for
    a given worktree state, which is what lets commit_checkpoint
    verify that the candidate has not moved since proposal.
    """
    files: list[dict] = []
    numstat = _git(worktree, 'diff', '--numstat', '-z', base_sha,
                   '--', '.')
    counts: dict[str, tuple[int | None, int | None]] = {}
    for entry in numstat.split('\0'):
        if not entry:
            continue
        parts = entry.split('\t')
        if len(parts) < 3:
            continue
        ins = None if parts[0] == '-' else int(parts[0])
        dels = None if parts[1] == '-' else int(parts[1])
        counts[parts[2]] = (ins, dels)
    statuses: dict[str, str] = {}
    raw_status = _git(worktree, 'diff', '--name-status', '-z', base_sha,
                      '--', '.')
    tokens = [t for t in raw_status.split('\0') if t != '']
    i = 0
    while i < len(tokens):
        code = tokens[i]
        i += 1
        if code.startswith('R') or code.startswith('C'):
            old, new = tokens[i], tokens[i + 1]
            i += 2
            statuses[new] = 'renamed'
            counts.setdefault(new, counts.pop(old, (None, None)))
        else:
            path = tokens[i]
            i += 1
            statuses[path] = {'M': 'modified', 'A': 'added',
                              'D': 'deleted'}.get(code, code)
    for path in sorted(set(counts) | set(statuses)):
        ins, dels = counts.get(path, (None, None))
        files.append({'path': path,
                      'status': statuses.get(path, 'modified'),
                      'insertions': ins, 'deletions': dels})
    tracked_patch = _git(worktree, 'diff', '--no-color', '--no-ext-diff',
                         base_sha, '--', '.')
    patch_parts = []
    if tracked_patch:
        patch_parts.append(
            tracked_patch if tracked_patch.endswith('\n')
            else tracked_patch + '\n')
    porcelain = _git(worktree, 'status', '--porcelain=v1', '-z',
                     '--untracked-files=all')
    untracked = []
    for entry in porcelain.split('\0'):
        if len(entry) > 3 and entry[:2] == '??':
            if not _is_generated_artifact(entry[3:]):
                untracked.append(entry[3:])
    for rel in sorted(untracked):
        patch, ins = _untracked_patch(rel, worktree / rel)
        patch_parts.append(patch)
        files.append({'path': rel, 'status': 'added',
                      'insertions': ins, 'deletions': 0})
    files.sort(key=lambda f: f['path'])
    patch = ''.join(patch_parts)
    total_ins = sum(f['insertions'] or 0 for f in files)
    total_dels = sum(f['deletions'] or 0 for f in files)
    stat_lines = [
        f" {f['path']} | {f['status']} "
        f"+{f['insertions']} -{f['deletions']}"
        if f['insertions'] is not None else
        f" {f['path']} | {f['status']} (binary)"
        for f in files]
    stat_lines.append(
        f"{len(files)} file(s) changed, {total_ins} insertion(s)(+), "
        f"{total_dels} deletion(s)(-)")
    return {'files': files, 'insertions': total_ins, 'deletions': total_dels,
            'stat': '\n'.join(stat_lines), 'patch': patch,
            'diff_hash': hashlib.sha256(patch.encode('utf-8')).hexdigest()}


# ---------------------------------------------------------------------------
# Proposal records (private profile data, slice A2/A3 store style)
# ---------------------------------------------------------------------------

class TaskPromotionStore:
    """Durable promotion proposals and disposal records."""

    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home is not None else None
        with self._open() as store:
            store.db.execute('''CREATE TABLE IF NOT EXISTS task_promotions (
                id TEXT PRIMARY KEY,
                execution_id TEXT NOT NULL,
                operation_id TEXT,
                state TEXT NOT NULL,
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
                    'INSERT INTO task_promotions (id,execution_id,'
                    'operation_id,state,record_json,created_at,updated_at)'
                    ' VALUES (?,?,?,?,?,?,?)',
                    (record['id'], record['execution_id'],
                     record.get('operation_id'), record['state'],
                     json.dumps(record, sort_keys=True),
                     record['created_at'], record['updated_at']))

    def update(self, record: dict) -> None:
        record['updated_at'] = utc_now()
        with self._open() as store:
            with store.db:
                store.db.execute(
                    'UPDATE task_promotions SET state=?, record_json=?,'
                    ' updated_at=? WHERE id=?',
                    (record['state'], json.dumps(record, sort_keys=True),
                     record['updated_at'], record['id']))

    def get(self, proposal_id: str) -> dict | None:
        with self._open() as store:
            row = store.db.execute(
                'SELECT record_json FROM task_promotions WHERE id=?',
                (proposal_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, execution_id: str | None = None) -> list[dict]:
        with self._open() as store:
            if execution_id is None:
                rows = store.db.execute(
                    'SELECT record_json FROM task_promotions'
                    ' ORDER BY created_at').fetchall()
            else:
                rows = store.db.execute(
                    'SELECT record_json FROM task_promotions'
                    ' WHERE execution_id=? ORDER BY created_at',
                    (execution_id,)).fetchall()
            return [json.loads(row[0]) for row in rows]


# ---------------------------------------------------------------------------
# Promoter
# ---------------------------------------------------------------------------

class TaskPromoter:
    """Prepare proposals, checkpoint-commit and discard candidates."""

    def __init__(self, home: Path | None = None, *,
                 command_timeout: int = DEFAULT_COMMAND_TIMEOUT):
        if isinstance(command_timeout, bool) \
                or not isinstance(command_timeout, int) \
                or command_timeout < 1:
            raise PromotionError('command_timeout must be a positive int')
        self.grants = TaskGrantStore(home)
        self.executions = TaskExecutionStore(home)
        self.operations = TaskOperationStore(home)
        self.promotions = TaskPromotionStore(home)
        self.command_timeout = command_timeout
        with self.grants._open() as store:
            self.home = store.home.resolve()
        self.worktree_root = self.home / 'task-worktrees'

    # -- target resolution -------------------------------------------------

    def _resolve_execution(self, execution_id: str | None,
                           operation_id: str | None,
                           item_id: str | None) -> tuple[dict, dict | None]:
        """Return (execution record, A4 evidence or None).

        Raises PromotionError unless the identified execution exists
        and its outcome is exactly ``succeeded``.
        """
        operation_evidence = None
        if operation_id is not None:
            if not item_id:
                raise PromotionError(
                    'An operation proposal needs an item id')
            operation = self.operations.get(operation_id)
            if operation is None:
                raise PromotionError(f'No such operation: {operation_id}')
            item = next((i for i in operation['items']
                         if i['id'] == item_id), None)
            if item is None:
                raise PromotionError(
                    f'Item not in operation {operation_id}: {item_id}')
            if item['state'] != 'succeeded':
                raise PromotionError(
                    f"Operation item is {item['state']}, not succeeded; "
                    'only a succeeded item can be proposed for promotion')
            execution = None
            for linked_id in reversed(item['execution_ids']):
                candidate = self.executions.get(linked_id)
                if candidate is not None \
                        and candidate.get('outcome') == 'succeeded':
                    execution = candidate
                    break
            if execution is None:
                raise PromotionError(
                    'Operation item has no succeeded execution record '
                    'to propose')
            operation_evidence = {
                'operation_id': operation['id'],
                'operation_state': operation['state'],
                'item_id': item['id'],
                'item_state': item['state'],
                'output_summaries': deepcopy(item['output_summaries']),
                'permission_fingerprint':
                    operation['permission_fingerprint'],
                'code_fingerprint': operation['code_fingerprint'],
            }
            return execution, operation_evidence
        if not execution_id:
            raise PromotionError(
                'Name an execution id, or an operation id plus item id')
        execution = self.executions.get(execution_id)
        if execution is None:
            raise PromotionError(f'No such execution: {execution_id}')
        if execution.get('outcome') != 'succeeded':
            raise PromotionError(
                f"Execution outcome is {execution.get('outcome')}, not "
                'succeeded; only a succeeded execution can be proposed '
                'for promotion')
        return execution, operation_evidence

    def _candidate_paths(self, source: dict, *, managed: bool) -> tuple[Path, Path]:
        repo = Path(source['repository'])
        worktree = Path(source['worktree'])
        if managed:
            resolved = worktree.resolve()
            if resolved.parent != self.worktree_root.resolve():
                raise PromotionError(
                    'Worktree is outside the managed task-worktrees '
                    f'location: {worktree}')
        return repo, worktree

    @staticmethod
    def _check_scratch_branch(source: dict) -> None:
        branch = source.get('branch') or ''
        if not branch.startswith(SCRATCH_BRANCH_PREFIX):
            raise PromotionError(
                f'Not an {SCRATCH_BRANCH_PREFIX} scratch branch: '
                f'{branch!r}; this module never touches other branches')

    def _grant_snapshot(self, grant_id: str) -> dict | None:
        grant = self.grants.get(grant_id)
        if grant is None:
            return None
        return {key: grant.get(key) for key in _GRANT_SNAPSHOT_FIELDS}

    @staticmethod
    def _event(record: dict, event: str, detail: dict | None = None) -> None:
        record['events'].append(
            {'at': utc_now(), 'event': event, 'detail': detail or {}})

    # -- fresh regression at proposal time ----------------------------------

    def _run_regression(self, execution: dict) -> dict:
        """Re-run the full test suite in the scratch worktree.

        Uses slice A3's constrained runner exactly: the fixed ``full``
        argv template, the scrubbed environment, the timeout, and a
        grant authorization (consuming one test-run budget) before
        anything runs. The recorded result is the actual result.
        """
        worktree = Path(execution['worktree'])
        run = {'stage': 'full', 'template': 'full', 'argv': [],
               'exit_code': None, 'timed_out': False,
               'duration_seconds': 0.0, 'stdout_tail': '',
               'stderr_tail': '', 'ran': False, 'run_reason': '',
               'green': False}
        if not (worktree / 'tests').is_dir():
            run['run_reason'] = 'no_tests_directory'
            return run
        check = self.grants.authorize(
            execution['grant_id'], repository=execution['repository'],
            tool=RUN_TESTS_TOOL, task_id=execution['task_id'],
            test_run=True)
        if not check['allowed']:
            run['run_reason'] = check['reason']
            return run
        argv = build_command('full', worktree)
        run['argv'] = argv
        started = time.monotonic()
        try:
            proc = subprocess.run(
                argv, cwd=worktree, env=_scrubbed_env(worktree),
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
            run['run_reason'] = 'runner_unavailable'
            run['duration_seconds'] = round(time.monotonic() - started, 3)
            return run
        run['duration_seconds'] = round(time.monotonic() - started, 3)
        run['ran'] = True
        run['green'] = run['exit_code'] == 0 and not run['timed_out']
        if not run['green']:
            run['run_reason'] = 'regression_failed'
        return run

    # -- prepare -------------------------------------------------------------

    def prepare_proposal(self, execution_id: str | None = None, *,
                         operation_id: str | None = None,
                         item_id: str | None = None) -> dict:
        """Build a durable promotion proposal for a succeeded candidate.

        Read-only against the candidate except for the fresh regression
        run (which executes the worktree's own test suite under grant
        authorization — that run is this method's documented cost).
        Refuses non-succeeded outcomes outright; a candidate whose
        fresh regression is red or cannot run is recorded as a
        proposal that is **not promotable**, with the reason.
        """
        execution, operation_evidence = self._resolve_execution(
            execution_id, operation_id, item_id)
        self._check_scratch_branch(execution)
        existing = [p for p in self.promotions.list(execution['id'])
                    if p['state'] in ('prepared', 'committed')]
        if existing:
            raise PromotionError(
                f"Execution already has proposal {existing[0]['id']} "
                f"({existing[0]['state']}); discard it before preparing "
                'another')
        _, worktree = self._candidate_paths(execution, managed=False)
        if not worktree.is_dir():
            raise PromotionError(
                f'Candidate worktree no longer exists: {worktree}')
        current_branch = _git(worktree, 'rev-parse', '--abbrev-ref',
                              'HEAD')
        if current_branch != execution['branch']:
            raise PromotionError(
                f"Worktree is on branch {current_branch!r}, not the "
                f"recorded scratch branch {execution['branch']!r}")
        head = _git(worktree, 'rev-parse', '--verify', 'HEAD')
        if head != execution['base_sha']:
            raise PromotionError(
                'Scratch branch has advanced past its recorded base '
                'revision; this module only proposes uncommitted '
                'candidates')
        diff = _candidate_diff(worktree, execution['base_sha'])
        if diff['files']:
            regression = self._run_regression(execution)
        else:
            regression = {'stage': 'full', 'template': 'full', 'argv': [],
                          'exit_code': None, 'timed_out': False,
                          'duration_seconds': 0.0, 'stdout_tail': '',
                          'stderr_tail': '', 'ran': False,
                          'run_reason': 'candidate_diff_empty',
                          'green': False}
        if not diff['files']:
            promotable, reason = False, 'candidate_diff_empty'
        elif not regression['ran']:
            promotable = False
            reason = f"regression_not_run: {regression['run_reason']}"
        elif not regression['green']:
            promotable, reason = False, 'regression_failed'
        else:
            promotable, reason = True, ''
        now = utc_now()
        proposal = {
            'schema': PROMOTION_SCHEMA,
            'id': 'promo-' + uuid.uuid4().hex[:16],
            'state': 'prepared',
            'promotable': promotable,
            'not_promotable_reason': reason,
            'execution_id': execution['id'],
            'operation_id': operation_id,
            'item_id': execution['item']['id'],
            'grant_id': execution['grant_id'],
            'task_id': execution['task_id'],
            'repository': execution['repository'],
            'base_sha': execution['base_sha'],
            'base_branch': execution['base_branch'],
            'branch': execution['branch'],
            'worktree': execution['worktree'],
            'item': deepcopy(execution['item']),
            'evidence': {
                'execution_outcome': execution['outcome'],
                'execution_stop_reason': execution.get('stop_reason', ''),
                'attempts': deepcopy(execution['attempts']),
                'budget_usage': deepcopy(execution.get('budget_usage')),
                'operation': operation_evidence,
            },
            'diff': diff,
            'regression': regression,
            'grant_at_proposal': self._grant_snapshot(execution['grant_id']),
            'rollback': {
                'base_sha': execution['base_sha'],
                'base_branch': execution['base_branch'],
                'procedure': [
                    'Discard the candidate with '
                    f"athenz-task-promote discard <this-proposal-id> "
                    '--confirm (removes the scratch worktree and '
                    'deletes the scratch branch), or manually:',
                    f"git -C {execution['repository']} worktree remove "
                    f"--force {execution['worktree']}",
                    f"git -C {execution['repository']} branch -D "
                    f"{execution['branch']}",
                    f"The base revision {execution['base_sha']} and "
                    "the owner's original working tree are untouched "
                    'either way; nothing was ever committed to them '
                    'by slices A3/A4.',
                ],
            },
            'remaining_owner_steps': [
                'Review this proposal: the diff below, the linked '
                'execution evidence, and the fresh regression result.',
                'To keep the candidate locally, run '
                'athenz-task-promote commit <proposal-id> --confirm '
                '(one local commit on the scratch branch only), or '
                'discard it with athenZ-task-promote discard '
                '<proposal-id> --confirm.',
                'Landing the candidate — merging it into any other '
                'branch, pushing it anywhere, tagging or releasing '
                'it, installing packages, deploying it, or replacing '
                'the running AthenZ with it — is NOT something this '
                'module can do. Those remain separate owner decisions '
                'taken through your own route, with their own '
                'regression and rollback checks.',
            ],
            'checkpoint': None,
            'disposal': None,
            'created_at': now, 'updated_at': now,
            'events': [],
        }
        self._event(proposal, 'prepared',
                    {'promotable': promotable,
                     'not_promotable_reason': reason,
                     'diff_hash': diff['diff_hash']})
        self.promotions.create(proposal)
        return proposal

    def get_proposal(self, proposal_id: str) -> dict | None:
        return self.promotions.get(proposal_id)

    def list_proposals(self, execution_id: str | None = None) -> list[dict]:
        return self.promotions.list(execution_id)

    # -- checkpoint commit (the module's only candidate write) ---------------

    def commit_checkpoint(self, proposal_id: str, *,
                          confirmed: bool = False) -> dict:
        """Create ONE local commit on the proposal's scratch branch.

        Requires explicit owner confirmation, a promotable proposal,
        and a worktree whose current diff still matches the proposal's
        recorded diff exactly. Never commits to any other branch.
        """
        if not confirmed:
            raise PromotionError(
                'A checkpoint commit is an explicit owner action: '
                'pass --confirm')
        proposal = self.promotions.get(proposal_id)
        if proposal is None:
            raise PromotionError(f'No such proposal: {proposal_id}')
        if proposal['state'] != 'prepared':
            raise PromotionError(
                f"Proposal is {proposal['state']}, not prepared; only "
                'a prepared proposal can be checkpoint-committed')
        if not proposal['promotable']:
            self._refuse_commit(proposal, 'proposal_not_promotable')
        repo, worktree = self._candidate_paths(proposal, managed=True)
        self._check_scratch_branch(proposal)
        if not worktree.is_dir():
            raise PromotionError(
                f'Candidate worktree no longer exists: {worktree}')
        current_branch = _git(worktree, 'rev-parse', '--abbrev-ref',
                              'HEAD')
        if current_branch != proposal['branch']:
            raise PromotionError(
                f"Worktree is on branch {current_branch!r}, not the "
                f"proposal's scratch branch {proposal['branch']!r}; "
                'refusing to commit anywhere else')
        head = _git(worktree, 'rev-parse', '--verify', 'HEAD')
        if head != proposal['base_sha']:
            raise PromotionError(
                'Scratch branch has advanced past the proposal base '
                'revision; re-prepare instead of committing onto '
                'unknown history')
        current = _candidate_diff(worktree, proposal['base_sha'])
        recorded = proposal['diff']
        if current['diff_hash'] != recorded['diff_hash'] or \
                [f['path'] for f in current['files']] != \
                [f['path'] for f in recorded['files']]:
            self._refuse_commit(proposal, 'candidate_changed_since_proposal')
        paths = [f['path'] for f in recorded['files']]
        _git(worktree, 'add', '--', *paths)
        staged = [t for t in _git(worktree, 'diff', '--cached',
                                  '--name-only', '-z',
                                  proposal['base_sha']).split('\0') if t]
        if sorted(staged) != sorted(paths):
            _git(worktree, 'reset', '-q')
            raise PromotionError(
                'Staged changes do not match the proposal diff; '
                'unstaged and refusing to commit')
        title = ' '.join(
            str(proposal['item'].get('title', '')).split())[:120]
        subject = f"AthenZ task checkpoint: {proposal['item_id']}"
        if title:
            subject += f" — {title}"
        body = '\n'.join([
            f"Proposal: {proposal['id']}",
            f"Execution: {proposal['execution_id']}",
            *([f"Operation: {proposal['operation_id']}"]
              if proposal.get('operation_id') else []),
            f"Grant: {proposal['grant_id']}",
            f"Base: {proposal['base_sha']}",
            '',
            'Local checkpoint commit on the isolated scratch branch, '
            'created by athenZ-task-promote under explicit owner '
            'confirmation (roadmap slice A5). Not merged, not '
            'pushed; landing it is a separate owner decision.',
        ])
        _git(worktree, 'commit', '-q', '-m', subject, '-m', body)
        commit_sha = _git(worktree, 'rev-parse', '--verify', 'HEAD')
        parent = _git(worktree, 'rev-parse', '--verify', 'HEAD~1')
        committed_files = sorted(
            t for t in _git(worktree, 'diff-tree', '--no-commit-id',
                            '--name-only', '-r', '-z',
                            commit_sha).split('\0') if t)
        proposal['checkpoint'] = {
            'commit_sha': commit_sha,
            'committed_at': utc_now(),
            'message_subject': subject,
            'files': committed_files,
            'verification': {
                'parent_is_recorded_base': parent == proposal['base_sha'],
                'files_match_proposal': committed_files == sorted(paths),
                'branch': proposal['branch'],
            },
        }
        proposal['state'] = 'committed'
        self._event(proposal, 'checkpoint_committed',
                    {'commit_sha': commit_sha})
        self.promotions.update(proposal)
        return proposal

    def _refuse_commit(self, proposal: dict, reason: str) -> None:
        self._event(proposal, 'commit_refused', {'reason': reason})
        self.promotions.update(proposal)
        raise PromotionError(f'Checkpoint commit refused: {reason}')

    # -- discard (owner-confirmed disposal) ------------------------------------

    def discard_candidate(self, proposal_id: str | None = None, *,
                          execution_id: str | None = None,
                          confirmed: bool = False) -> dict:
        """Remove a candidate's scratch worktree and scratch branch.

        The disposal is recorded — what was discarded, its final diff
        hash, when, and that it was an owner action — whether or not a
        proposal was ever prepared. Refuses without confirmation, for
        any branch that is not an ``athenz-task/`` scratch branch, and
        for any worktree outside the managed location.
        """
        if not confirmed:
            raise PromotionError(
                'Discarding a candidate is an explicit owner action: '
                'pass --confirm')
        proposal = None
        if proposal_id is not None:
            proposal = self.promotions.get(proposal_id)
            if proposal is None:
                raise PromotionError(f'No such proposal: {proposal_id}')
            if proposal['state'] == 'discarded':
                raise PromotionError(
                    f'Proposal already discarded: {proposal_id}')
            source = proposal
        elif execution_id is not None:
            for candidate in self.promotions.list(execution_id):
                if candidate['state'] in ('prepared', 'committed'):
                    proposal = candidate
                    break
            execution = self.executions.get(execution_id)
            if execution is None:
                raise PromotionError(
                    f'No such execution: {execution_id}')
            source = proposal if proposal is not None else execution
        else:
            raise PromotionError(
                'Name a proposal id or an execution id to discard')
        self._check_scratch_branch(source)
        repo, worktree = self._candidate_paths(source, managed=True)
        final_diff = None
        diff_error = ''
        if worktree.is_dir():
            try:
                final_diff = _candidate_diff(worktree, source['base_sha'])
            except PromotionError as exc:
                diff_error = str(exc)
        worktree_removed = False
        if worktree.is_dir():
            _git(repo, 'worktree', 'remove', '--force', str(worktree))
            worktree_removed = not worktree.exists()
        else:
            _git(repo, 'worktree', 'prune')
            worktree_removed = True
        branch_deleted = False
        if _git(repo, 'branch', '--list', source['branch']).strip():
            _git(repo, 'branch', '-D', source['branch'])
            branch_deleted = not _git(
                repo, 'branch', '--list', source['branch']).strip()
        disposal = {
            'discarded_at': utc_now(),
            'by': 'owner',
            'execution_id': source['execution_id'] if proposal is not None
            else source['id'],
            'branch': source['branch'],
            'worktree': source['worktree'],
            'base_sha': source['base_sha'],
            'final_diff_hash': final_diff['diff_hash']
            if final_diff else None,
            'final_stat': final_diff['stat'] if final_diff else None,
            'final_diff_error': diff_error,
            'checkpoint_commit_sha': (proposal or {}).get(
                'checkpoint', {}).get('commit_sha')
            if (proposal or {}).get('checkpoint') else None,
            'worktree_removed': worktree_removed,
            'branch_deleted': branch_deleted,
        }
        if proposal is not None:
            proposal['disposal'] = disposal
            proposal['state'] = 'discarded'
            self._event(proposal, 'discarded',
                        {'final_diff_hash': disposal['final_diff_hash']})
            self.promotions.update(proposal)
            return proposal
        now = utc_now()
        record = {
            'schema': PROMOTION_SCHEMA,
            'id': 'promo-' + uuid.uuid4().hex[:16],
            'state': 'discarded',
            'promotable': False,
            'not_promotable_reason': 'discarded_without_proposal',
            'execution_id': source['id'],
            'operation_id': None,
            'item_id': source['item']['id'],
            'grant_id': source['grant_id'],
            'task_id': source['task_id'],
            'repository': source['repository'],
            'base_sha': source['base_sha'],
            'base_branch': source['base_branch'],
            'branch': source['branch'],
            'worktree': source['worktree'],
            'item': deepcopy(source['item']),
            'evidence': {
                'execution_outcome': source.get('outcome'),
                'execution_stop_reason': source.get('stop_reason', ''),
                'attempts': deepcopy(source.get('attempts', [])),
                'budget_usage': deepcopy(source.get('budget_usage')),
                'operation': None,
            },
            'diff': final_diff,
            'regression': None,
            'grant_at_proposal': None,
            'rollback': None,
            'remaining_owner_steps': [],
            'checkpoint': None,
            'disposal': disposal,
            'created_at': now, 'updated_at': now,
            'events': [{'at': now, 'event': 'discarded',
                        'detail': {
                            'final_diff_hash':
                                disposal['final_diff_hash'],
                            'without_proposal': True}}],
        }
        self.promotions.create(record)
        return record
