"""Durable, inspectable operations (roadmap slice A4).

An *operation* is one granted run over an ordered list of planner
queue items. Slice A3 executes one item in one process; this module
persists the whole run -- queue, fingerprints, per-item stage state,
output summaries and checkpoints -- in the private profile database,
so an operation survives shutdowns and model changes and can be
inspected and resumed without replaying completed work.

Durability discipline:

- Per-item state is checkpointed (a compare-and-swap update of the
  durable operation record) BEFORE the item is executed and again
  AFTER its A3 execution record is linked. A process that dies
  mid-item therefore leaves the item ``running`` -- never silently
  ``succeeded`` -- and resume surfaces it as ``suspect``.
- Completed items are never re-executed: resume skips them by state
  and by their linked A3 execution records.
- Resume re-verifies the grant before doing anything: it must still
  exist, be active and unexpired, and its permission fingerprint
  (a hash of the grant's scope fields, taken when the operation
  started) must match. A scope change aborts the resume; a revoked
  or expired grant refuses it. Each remaining item's base revision
  is re-checked immediately before it runs; a moved base blocks
  that item rather than silently re-basing it.
- Model and editor fingerprints recorded at start are compared on
  resume when the caller supplies them again. A change is reported
  and stops the resume; the new fingerprint is never silently
  adopted.
- Identical consecutive failures of one item -- same outcome, same
  failing stage, same normalized output tail -- are counted across
  resumes. Reaching the operation's stall threshold marks the
  operation ``stalled`` and stops it.
- Wall-clock accrual is persisted at every checkpoint. The grant's
  own wall-clock budget is consumed atomically by slice A3's
  authorization checks and therefore also accumulates across
  process lifetimes; the operation additionally credits each drive
  segment at its durable boundaries.

One driver at a time: operation records are updated with a revision
check, and a conflicting writer fails closed, but this slice does
not implement cross-process locking or a background daemon. The
owner drives one operation at a time (see docs/TASK_OPERATIONS.md).
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import time
import uuid

from .experience import ExperienceStore
from .project_planner import SCHEMA as PLAN_SCHEMA
from .store import utc_now
from .task_executor import TaskExecutor, _git
from .task_grants import TaskGrantStore

OPERATION_SCHEMA = 'athenz.task-operation/v1'
DEFAULT_STALL_THRESHOLD = 2

OPERATION_STATES = frozenset(
    {'active', 'paused', 'completed', 'aborted', 'stalled'})
ITEM_STATES = frozenset(
    {'pending', 'running', 'succeeded', 'failed', 'blocked', 'denied',
     'skipped', 'suspect'})

# Grant fields whose hash is the operation's permission fingerprint.
# Volatile usage counters and lifecycle state are deliberately NOT
# part of it: pausing a grant must not look like a scope change, and
# spending budget must not either. Expiry IS included -- extending a
# grant's life is a scope change and must mint a new operation.
_PERMISSION_FIELDS = (
    'objective', 'queue_item_ids', 'repository', 'worktree',
    'task_classes', 'allowed_files', 'permitted_tools',
    'network_policy', 'network_allowlist', 'max_tasks',
    'max_test_runs', 'max_retries_per_task', 'max_wall_clock_seconds',
    'expires_at')

_TERMINAL_OPERATIONS = frozenset({'completed', 'aborted'})
_RESUMABLE_ITEM_STATES = frozenset(
    {'pending', 'failed', 'blocked', 'denied'})


class OperationError(RuntimeError):
    """The operation cannot proceed within its durable bounds."""


# ---------------------------------------------------------------------------
# Fingerprints and failure signatures
# ---------------------------------------------------------------------------

def _canonical_hash(value) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(',', ':'),
                         ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def queue_source_fingerprint(plan: dict) -> str:
    """Hash of the exact planner output an operation was built from."""
    return _canonical_hash(plan)


def permission_fingerprint(grant: dict) -> str:
    """Hash of a grant's scope fields (see _PERMISSION_FIELDS)."""
    return _canonical_hash(
        {field: grant.get(field) for field in _PERMISSION_FIELDS})


def code_fingerprint(repository: str, head: str, branch,
                     queue_fingerprint: str) -> str:
    return _canonical_hash({'repository': repository, 'head': head,
                            'branch': branch, 'queue': queue_fingerprint})


def _normalize_output(text: str, record: dict) -> str:
    """Make a failure output tail comparable across executions.

    Worktree paths embed a fresh execution id and unittest reports
    embed per-run durations; both change between otherwise identical
    failures and are normalized out before hashing.
    """
    text = text[-2000:]
    for token, label in ((record.get('worktree'), '<worktree>'),
                         (record.get('repository'), '<repository>')):
        if token:
            text = text.replace(str(token), label)
    text = re.sub(r'exec-[0-9a-f]+', 'exec-<id>', text)
    text = re.sub(r'\b\d+\.\d+s\b', '<duration>s', text)
    return text


def failure_signature(record: dict) -> str:
    """Hash of outcome + failing stage + normalized output tail."""
    failing = None
    for attempt in reversed(record.get('attempts', [])):
        for run in reversed(attempt.get('runs', [])):
            if not run.get('skipped') and run.get('exit_code') != 0:
                failing = run
                break
        if failing is not None:
            break
    if failing is not None:
        stage = failing.get('stage', '')
        tail = _normalize_output(
            (failing.get('stderr_tail') or '')
            + (failing.get('stdout_tail') or ''), record)
        reason = ''
    else:
        stage = 'no_failing_stage'
        tail = record.get('stop_reason', '')
        reason = record.get('stop_reason', '')
    return _canonical_hash({'outcome': record.get('outcome'),
                            'stage': stage, 'stop_reason': reason,
                            'output_tail': tail})


def _execution_summary(record: dict) -> dict:
    edited, stages = [], []
    for attempt in record.get('attempts', []):
        for edit in attempt.get('edits', []):
            if edit['path'] not in edited:
                edited.append(edit['path'])
        for run in attempt.get('runs', []):
            stages.append({'attempt': attempt['n'],
                           'stage': run['stage'],
                           'exit_code': run['exit_code'],
                           'skipped': run['skipped'],
                           'timed_out': run['timed_out']})
    return {'execution_id': record['id'], 'outcome': record['outcome'],
            'stop_reason': record.get('stop_reason', ''),
            'attempts': len(record.get('attempts', [])),
            'edited_files': edited, 'stages': stages,
            'base_sha': record.get('base_sha'),
            'branch': record.get('branch'),
            'worktree': record.get('worktree'),
            'started_at': record.get('started_at'),
            'finished_at': record.get('finished_at')}


# ---------------------------------------------------------------------------
# Durable operation records
# ---------------------------------------------------------------------------

class TaskOperationStore:
    """Operation records in the private profile database (A2/A3 style)."""

    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home is not None else None
        with self._open() as store:
            store.db.execute('''CREATE TABLE IF NOT EXISTS task_operations (
                id TEXT PRIMARY KEY,
                grant_id TEXT NOT NULL,
                state TEXT NOT NULL,
                revision INTEGER NOT NULL,
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
                    'INSERT INTO task_operations (id,grant_id,state,revision,'
                    'record_json,created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                    (record['id'], record['grant_id'], record['state'],
                     record['revision'],
                     json.dumps(record, sort_keys=True),
                     record['created_at'], record['updated_at']))

    def save(self, record: dict, expected_revision: int) -> None:
        """Compare-and-swap update; a conflicting writer fails closed."""
        new_revision = expected_revision + 1
        with self._open() as store:
            with store.db:
                cur = store.db.execute(
                    'UPDATE task_operations SET state=?, revision=?,'
                    ' record_json=?, updated_at=? WHERE id=? AND revision=?',
                    (record['state'], new_revision,
                     json.dumps({**record, 'revision': new_revision},
                                sort_keys=True),
                     record['updated_at'], record['id'], expected_revision))
                if cur.rowcount != 1:
                    raise OperationError(
                        'Operation changed concurrently; reload before '
                        'updating (single-driver assumption violated)')
        record['revision'] = new_revision

    def get(self, operation_id: str) -> dict | None:
        with self._open() as store:
            row = store.db.execute(
                'SELECT record_json FROM task_operations WHERE id=?',
                (operation_id,)).fetchone()
            return json.loads(row[0]) if row else None

    def list(self, grant_id: str | None = None) -> list[dict]:
        with self._open() as store:
            if grant_id is None:
                rows = store.db.execute(
                    'SELECT record_json FROM task_operations'
                    ' ORDER BY created_at').fetchall()
            else:
                rows = store.db.execute(
                    'SELECT record_json FROM task_operations'
                    ' WHERE grant_id=? ORDER BY created_at',
                    (grant_id,)).fetchall()
            return [json.loads(row[0]) for row in rows]


# ---------------------------------------------------------------------------
# Operation driver
# ---------------------------------------------------------------------------

class TaskOperationDriver:
    """Create, drive, resume and inspect durable operations."""

    def __init__(self, home: Path | None = None, *,
                 command_timeout: int = 120):
        self.grants = TaskGrantStore(home)
        self.executor = TaskExecutor(home, command_timeout=command_timeout)
        self.records = self.executor.records
        self.operations = TaskOperationStore(home)
        with self.grants._open() as store:
            self.home = store.home.resolve()

    # -- helpers -----------------------------------------------------------

    @staticmethod
    def _event(record: dict, event: str, detail: dict | None = None) -> None:
        record['events'].append(
            {'at': utc_now(), 'event': event, 'detail': detail or {}})

    def _checkpoint(self, record: dict, event: str,
                    detail: dict | None = None) -> None:
        self._sync_accrued(record)
        self._event(record, event, detail)
        record['updated_at'] = utc_now()
        self.operations.save(record, record['revision'])

    def _sync_accrued(self, record: dict) -> None:
        """Credit wall-clock the grant has already accounted for."""
        grant = self.grants.get(record['grant_id'])
        if grant is not None:
            delta = grant['wall_clock_seconds_used'] \
                - record['grant_wall_clock_seconds_at_start']
            if delta > record['accrued_wall_clock_seconds']:
                record['accrued_wall_clock_seconds'] = float(delta)

    def _finish_segment(self, record: dict, *,
                        credit_elapsed: bool = True) -> None:
        started = record.get('active_segment_started_at')
        if started is not None:
            elapsed = max(0.0, time.time() - started)
            if credit_elapsed:
                # Credit this process's segment on top of the accrued
                # base captured when it began. Grant accounting (via
                # _sync_accrued) overlaps the same seconds, so the
                # accrued figure is the max of the two views, never
                # their sum -- a segment is never double-counted.
                base = record.get('active_segment_base_seconds', 0.0)
                record['accrued_wall_clock_seconds'] = max(
                    record['accrued_wall_clock_seconds'],
                    round(base + elapsed, 3))
                seconds = round(elapsed, 3)
            else:
                # The segment belongs to a process that is gone; its
                # end is unknown and downtime must not be credited.
                # Only the grant's own accounting (synced below) is
                # trusted for it.
                seconds = 0.0
            record['wall_clock_segments'].append(
                {'started_at_epoch': started,
                 'ended_at_epoch': time.time(),
                 'seconds': seconds,
                 'credited': credit_elapsed})
            record['active_segment_started_at'] = None
            record['active_segment_base_seconds'] = 0.0
        self._sync_accrued(record)

    @staticmethod
    def _repo_revision(repository: str) -> dict:
        repo = Path(repository)
        head = _git(repo, 'rev-parse', '--verify', 'HEAD')
        if not re.fullmatch(r'[0-9a-f]{40,64}', head):
            raise OperationError('Granted repository HEAD is not a commit')
        branch = _git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
        return {'repository': str(repo), 'head': head,
                'branch': None if branch == 'HEAD' else branch}

    def _get_or_raise(self, operation_id: str) -> dict:
        record = self.operations.get(operation_id)
        if record is None:
            raise OperationError(f'No such operation: {operation_id}')
        return record

    # -- creation ------------------------------------------------------------

    def create_operation(self, plan: dict, grant_id: str, *,
                         item_ids=None, task_class: str = 'implement',
                         model_fingerprint: str = 'unspecified',
                         editor_fingerprint: str = 'unspecified',
                         stall_threshold: int = DEFAULT_STALL_THRESHOLD,
                         extra_test_modules=()) -> dict:
        """Persist a new operation over *plan*'s queue under *grant_id*.

        Nothing is executed. The queue, the grant's permission
        fingerprint and the repository's base revision are frozen
        into the record; later drift is detected against them.
        """
        if not isinstance(plan, dict) \
                or plan.get('schema') != PLAN_SCHEMA \
                or not isinstance(plan.get('queue'), list):
            raise OperationError(f'Not a {PLAN_SCHEMA} plan')
        if isinstance(stall_threshold, bool) \
                or not isinstance(stall_threshold, int) \
                or stall_threshold < 1:
            raise OperationError('stall_threshold must be a positive int')
        for name, value in (('model_fingerprint', model_fingerprint),
                            ('editor_fingerprint', editor_fingerprint)):
            if not isinstance(value, str) or not value:
                raise OperationError(f'{name} must be a non-empty string')
        grant = self.grants.get(grant_id)
        if grant is None:
            raise OperationError(f'No such grant: {grant_id}')
        planned_repo = (plan.get('generated_from') or {}).get('repo')
        if planned_repo is None or \
                Path(planned_repo).resolve() != \
                Path(grant['repository']).resolve():
            raise OperationError(
                'Plan was generated for a different repository than the '
                'grant authorizes')
        queue = plan['queue']
        if item_ids is None:
            selected = list(queue)
        else:
            if len(set(item_ids)) != len(item_ids):
                raise OperationError('Duplicate item ids in selection')
            by_id = {item.get('id'): item for item in queue}
            selected = []
            for item_id in item_ids:
                if item_id not in by_id:
                    raise OperationError(
                        f'Queue item not in plan: {item_id}')
                selected.append(by_id[item_id])
        if not selected:
            raise OperationError('An operation needs at least one item')
        base = self._repo_revision(grant['repository'])
        queue_fp = queue_source_fingerprint(plan)
        now = utc_now()
        items = []
        for position, item in enumerate(selected):
            items.append({
                'position': position,
                'id': item['id'],
                'item': deepcopy(item),
                'state': 'pending',
                'base_revision': {**base, 'scratch_branch': None},
                'execution_ids': [],
                'orphan_execution_ids': [],
                'output_summaries': [],
                'failure_signatures': [],
                'last_failure_signature': '',
                'consecutive_identical_failures': 0,
                'suspect': False,
                'suspect_reason': '',
                'stop_reason': '',
                'retry_decisions': [],
                'started_at': None,
                'finished_at': None,
            })
        record = {
            'schema': OPERATION_SCHEMA,
            'id': 'op-' + uuid.uuid4().hex[:16],
            'grant_id': grant_id,
            'state': 'active',
            'revision': 1,
            'repository': grant['repository'],
            'task_class': task_class,
            'extra_test_modules': list(extra_test_modules),
            'queue_source': {
                'schema': plan['schema'],
                'generated_from': deepcopy(plan.get('generated_from')),
                'fingerprint': queue_fp},
            'queue_fingerprint': queue_fp,
            'permission_fingerprint': permission_fingerprint(grant),
            'code_fingerprint': code_fingerprint(
                base['repository'], base['head'], base['branch'], queue_fp),
            'model_fingerprint': model_fingerprint,
            'editor_fingerprint': editor_fingerprint,
            'base_revision': base,
            'stall_threshold': stall_threshold,
            'stall': {'item_id': '', 'signature': ''},
            'items': items,
            'current_item_id': None,
            'stop_reason': '',
            'accrued_wall_clock_seconds': 0.0,
            'grant_wall_clock_seconds_at_start':
                grant['wall_clock_seconds_used'],
            'active_segment_started_at': None,
            'active_segment_base_seconds': 0.0,
            'wall_clock_segments': [],
            'created_at': now, 'updated_at': now,
            'started_at': None, 'finished_at': None,
            'events': [],
        }
        self._event(record, 'created',
                    {'items': [i['id'] for i in items],
                     'grant_id': grant_id})
        self.operations.create(record)
        return record

    def start_operation(self, plan: dict, grant_id: str, editor_factory, *,
                        max_items: int | None = None, **kwargs) -> dict:
        """Create an operation and immediately drive it."""
        record = self.create_operation(plan, grant_id, **kwargs)
        return self.drive_operation(
            record['id'], editor_factory, max_items=max_items)

    # -- driving -------------------------------------------------------------

    def drive_operation(self, operation_id: str, editor_factory, *,
                        max_items: int | None = None,
                        retry_suspect: bool = False) -> dict:
        """Run pending items in order through the A3 executor.

        Stops at the first non-success outcome; later items stay
        pending. *max_items* bounds how many items this call executes
        (a rehearsal / clean-shutdown boundary, not a skip).
        """
        record = self._get_or_raise(operation_id)
        if record['state'] in _TERMINAL_OPERATIONS \
                or record['state'] in ('paused', 'stalled'):
            return record
        return self._drive(record, editor_factory, max_items=max_items,
                           retry_suspect=retry_suspect)

    def resume_operation(self, operation_id: str, editor_factory, *,
                         max_items: int | None = None,
                         retry_suspect: bool = False,
                         model_fingerprint: str | None = None,
                         editor_fingerprint: str | None = None) -> dict:
        """Verify the world still matches the record, then continue.

        See the module docstring for the full protocol. A refused
        resume performs no execution and says exactly why in the
        operation's ``stop_reason``.
        """
        record = self._get_or_raise(operation_id)
        if record['state'] in _TERMINAL_OPERATIONS:
            return record
        # 1. A mid-item crash state is surfaced before anything else.
        suspect = next((i for i in record['items']
                        if i['state'] in ('running', 'suspect')), None)
        if suspect is not None and suspect['state'] == 'running':
            self._mark_suspect(record, suspect)
        if suspect is not None and suspect['state'] == 'suspect':
            if not retry_suspect:
                record['state'] = 'active'
                record['current_item_id'] = suspect['id']
                record['stop_reason'] = \
                    'suspect_item_requires_owner_decision'
                self._checkpoint(record, 'resume_blocked_suspect',
                                 {'item': suspect['id']})
                return record
            suspect['retry_decisions'].append(
                {'at': utc_now(), 'decision': 'retry_suspect',
                 'by': 'owner'})
            suspect['state'] = 'pending'
            suspect['suspect'] = False
            suspect['suspect_reason'] = ''
            suspect['stop_reason'] = ''
            self._checkpoint(record, 'suspect_retry_authorized',
                             {'item': suspect['id']})
        # 2. Fingerprint drift: reported, never silently adopted.
        for supplied, stored, reason in (
                (model_fingerprint, record['model_fingerprint'],
                 'model_fingerprint_changed'),
                (editor_fingerprint, record['editor_fingerprint'],
                 'editor_fingerprint_changed')):
            if supplied is not None and supplied != stored:
                record['state'] = 'paused'
                record['stop_reason'] = reason
                self._checkpoint(record, 'resume_refused', 
                                 {'reason': reason})
                return record
        # 3. The grant must still exist, be active and unexpired, and
        #    its scope must be exactly what the operation recorded.
        grant = self.grants.get(record['grant_id'])
        if grant is None:
            return self._abort_resume(record, 'grant_not_found')
        if grant['state'] == 'revoked':
            return self._abort_resume(record, 'grant_revoked')
        if grant['state'] == 'expired':
            return self._abort_resume(record, 'grant_expired')
        if grant['state'] == 'paused':
            record['state'] = 'paused'
            record['stop_reason'] = 'grant_paused'
            self._checkpoint(record, 'resume_refused',
                             {'reason': 'grant_paused'})
            return record
        if permission_fingerprint(grant) != record['permission_fingerprint']:
            return self._abort_resume(
                record, 'permission_fingerprint_changed')
        if grant['wall_clock_seconds_used'] \
                >= grant['max_wall_clock_seconds'] and any(
                    i['state'] in _RESUMABLE_ITEM_STATES
                    for i in record['items']):
            record['state'] = 'active'
            record['stop_reason'] = 'budget_wall_clock_exhausted'
            self._checkpoint(record, 'resume_refused',
                             {'reason': 'budget_wall_clock_exhausted'})
            return record
        record['state'] = 'active'
        record['stop_reason'] = ''
        self._checkpoint(record, 'resume_verified',
                         {'grant_id': record['grant_id']})
        return self._drive(record, editor_factory, max_items=max_items,
                           retry_suspect=retry_suspect)

    def _abort_resume(self, record: dict, reason: str) -> dict:
        record['state'] = 'aborted'
        record['stop_reason'] = reason
        record['finished_at'] = utc_now()
        record['current_item_id'] = None
        self._finish_segment(record, credit_elapsed=False)
        self._checkpoint(record, 'resume_aborted', {'reason': reason})
        return record

    def _mark_suspect(self, record: dict, item: dict) -> None:
        """Convert a leftover ``running`` item to ``suspect``.

        Links any A3 execution record the interrupted process created
        for this item but never reported back, so its partial work
        stays inspectable and is never treated as a success.
        """
        self._finish_segment(record, credit_elapsed=False)
        known = set(item['execution_ids']) | set(item['orphan_execution_ids'])
        for execution in self.records.list(record['grant_id']):
            if execution['item']['id'] != item['id'] \
                    or execution['id'] in known \
                    or execution['started_at'] < record['created_at']:
                continue
            item['orphan_execution_ids'].append(execution['id'])
            item['execution_ids'].append(execution['id'])
            item['output_summaries'].append({
                **_execution_summary(execution),
                'orphaned': True,
                'outcome': execution.get('outcome'),
                'stop_reason': 'process_interrupted_mid_item'})
        item['state'] = 'suspect'
        item['suspect'] = True
        item['suspect_reason'] = 'process_interrupted_mid_item'
        item['stop_reason'] = 'process_interrupted_mid_item'
        record['current_item_id'] = item['id']
        self._checkpoint(record, 'item_suspect', {'item': item['id']})

    def _drive(self, record: dict, editor_factory, *,
               max_items: int | None, retry_suspect: bool) -> dict:
        if max_items is not None and (isinstance(max_items, bool)
                                      or not isinstance(max_items, int)
                                      or max_items < 1):
            raise OperationError('max_items must be a positive int')
        if not callable(editor_factory):
            raise OperationError('editor_factory must be callable')
        record['state'] = 'active'
        if record['started_at'] is None:
            record['started_at'] = utc_now()
        if record['active_segment_started_at'] is None:
            record['active_segment_started_at'] = time.time()
            record['active_segment_base_seconds'] = \
                record['accrued_wall_clock_seconds']
        executed = 0
        for item in record['items']:
            if item['state'] in ('succeeded', 'skipped'):
                continue
            if item['state'] in ('running', 'suspect'):
                if not retry_suspect:
                    record['current_item_id'] = item['id']
                    record['stop_reason'] = \
                        'suspect_item_requires_owner_decision'
                    self._finish_segment(record)
                    self._checkpoint(record, 'drive_blocked_suspect',
                                     {'item': item['id']})
                    return record
                item['retry_decisions'].append(
                    {'at': utc_now(), 'decision': 'retry_suspect',
                     'by': 'owner'})
                item['state'] = 'pending'
                item['suspect'] = False
                item['suspect_reason'] = ''
            if item['state'] not in _RESUMABLE_ITEM_STATES:
                continue
            if max_items is not None and executed >= max_items:
                record['stop_reason'] = 'run_limit_reached'
                self._finish_segment(record)
                self._checkpoint(record, 'drive_stopped',
                                 {'reason': 'run_limit_reached'})
                return record
            # Base revision is re-verified immediately before the
            # item runs; a moved base blocks it -- no silent re-base.
            current = self._repo_revision(record['repository'])
            if current['head'] != item['base_revision']['head']:
                item['state'] = 'blocked'
                item['stop_reason'] = 'base_revision_changed'
                record['current_item_id'] = item['id']
                record['stop_reason'] = 'base_revision_changed'
                self._finish_segment(record)
                self._checkpoint(record, 'item_blocked',
                                 {'item': item['id'],
                                  'reason': 'base_revision_changed',
                                  'recorded_head':
                                      item['base_revision']['head'],
                                  'current_head': current['head']})
                return record
            # Checkpoint BEFORE execution: from here, a crash leaves
            # this item 'running' and therefore suspect on resume.
            item['state'] = 'running'
            if item['started_at'] is None:
                item['started_at'] = utc_now()
            item['stop_reason'] = ''
            record['current_item_id'] = item['id']
            self._checkpoint(record, 'item_started', {'item': item['id']})
            editor = editor_factory(deepcopy(item['item']))
            if not callable(editor):
                raise OperationError(
                    'editor_factory must return a callable editor')
            execution = None
            try:
                execution = self.executor.execute(
                    record['grant_id'], item['item'], editor,
                    task_class=record['task_class'],
                    extra_test_modules=record['extra_test_modules'])
            except Exception as exc:  # executor-level failure: recorded
                item['state'] = 'blocked'
                item['stop_reason'] = f'executor_error: {type(exc).__name__}'
                record['stop_reason'] = item['stop_reason']
                self._finish_segment(record)
                self._checkpoint(record, 'item_blocked',
                                 {'item': item['id'],
                                  'reason': item['stop_reason']})
                return record
            executed += 1
            item['execution_ids'].append(execution['id'])
            item['output_summaries'].append(
                _execution_summary(execution))
            item['base_revision']['scratch_branch'] = execution['branch']
            item['finished_at'] = execution['finished_at']
            outcome = execution['outcome'] or 'blocked'
            item['state'] = outcome if outcome in ITEM_STATES else 'blocked'
            item['stop_reason'] = execution['stop_reason']
            stalled = False
            if outcome == 'succeeded':
                item['consecutive_identical_failures'] = 0
            else:
                signature = failure_signature(execution)
                item['failure_signatures'].append(
                    {'execution_id': execution['id'],
                     'signature': signature})
                if signature == item['last_failure_signature']:
                    item['consecutive_identical_failures'] += 1
                else:
                    item['consecutive_identical_failures'] = 1
                    item['last_failure_signature'] = signature
                if item['consecutive_identical_failures'] \
                        >= record['stall_threshold']:
                    stalled = True
                    record['stall'] = {'item_id': item['id'],
                                       'signature': signature}
            # Checkpoint AFTER execution, with the outcome durable.
            if stalled:
                record['state'] = 'stalled'
                record['stop_reason'] = 'stall_detected'
            else:
                record['stop_reason'] = execution['stop_reason'] \
                    if outcome != 'succeeded' else ''
            if outcome != 'succeeded' or stalled:
                self._finish_segment(record)
            self._checkpoint(record, 'item_finished',
                             {'item': item['id'], 'outcome': outcome,
                              'execution_id': execution['id']})
            if stalled or outcome != 'succeeded':
                return record
        record['state'] = 'completed'
        record['stop_reason'] = ''
        record['current_item_id'] = None
        record['finished_at'] = utc_now()
        self._finish_segment(record)
        self._checkpoint(record, 'completed', {})
        return record

    # -- owner controls ------------------------------------------------------

    def pause_operation(self, operation_id: str) -> dict:
        record = self._get_or_raise(operation_id)
        if record['state'] in _TERMINAL_OPERATIONS:
            return record
        record['state'] = 'paused'
        record['stop_reason'] = 'owner_paused'
        self._checkpoint(record, 'paused', {})
        return record

    def abort_operation(self, operation_id: str) -> dict:
        record = self._get_or_raise(operation_id)
        if record['state'] in _TERMINAL_OPERATIONS:
            return record
        for item in record['items']:
            if item['state'] == 'pending':
                item['state'] = 'skipped'
                item['stop_reason'] = 'operation_aborted'
            elif item['state'] == 'running':
                item['state'] = 'blocked'
                item['stop_reason'] = 'operation_aborted'
        record['state'] = 'aborted'
        record['stop_reason'] = 'owner_aborted'
        record['finished_at'] = utc_now()
        record['current_item_id'] = None
        self._sync_accrued(record)
        record['active_segment_started_at'] = None
        record['active_segment_base_seconds'] = 0.0
        self._checkpoint(record, 'aborted', {})
        return record

    # -- inspection ------------------------------------------------------------

    def get_operation(self, operation_id: str) -> dict | None:
        return self.operations.get(operation_id)

    def list_operations(self, grant_id: str | None = None) -> list[dict]:
        return self.operations.list(grant_id)

    def inspect_operation(self, operation_id: str) -> dict:
        """Structured owner view: attempted / changed / tested /
        blocked / unfinished, derived from the operation record and
        its linked A3 execution records."""
        record = self._get_or_raise(operation_id)
        attempted, changed, tested, blocked, unfinished = [], [], [], [], []
        for item in record['items']:
            state = item['state']
            if item['execution_ids'] or state not in ('pending', 'skipped'):
                attempted.append({'item_id': item['id'], 'state': state,
                                  'execution_ids':
                                      list(item['execution_ids'])})
            for execution_id in item['execution_ids']:
                execution = self.records.get(execution_id)
                if execution is None:
                    continue
                files, diffs = [], []
                stages = []
                for attempt in execution.get('attempts', []):
                    for edit in attempt.get('edits', []):
                        if edit['path'] not in files:
                            files.append(edit['path'])
                        diffs.append({'path': edit['path'],
                                      'created': edit['created'],
                                      'diff': edit['diff']})
                    for run in attempt.get('runs', []):
                        stages.append(
                            {'attempt': attempt['n'],
                             'stage': run['stage'],
                             'exit_code': run['exit_code'],
                             'skipped': run['skipped'],
                             'timed_out': run['timed_out']})
                if files:
                    changed.append({'item_id': item['id'],
                                    'execution_id': execution_id,
                                    'files': files, 'diffs': diffs,
                                    'branch': execution.get('branch')})
                if stages:
                    tested.append({'item_id': item['id'],
                                   'execution_id': execution_id,
                                   'outcome': execution.get('outcome'),
                                   'stages': stages})
            if state in ('blocked', 'denied', 'suspect'):
                blocked.append({'item_id': item['id'], 'state': state,
                                'reason': item['stop_reason'],
                                'suspect': item['suspect']})
            if state not in ('succeeded', 'skipped'):
                unfinished.append({'item_id': item['id'], 'state': state,
                                   'reason': item['stop_reason']})
        summary = {
            'items_total': len(record['items']),
            'succeeded': sum(1 for i in record['items']
                             if i['state'] == 'succeeded'),
            'attempted': len(attempted), 'changed': len(changed),
            'tested': len(tested), 'blocked': len(blocked),
            'unfinished': len(unfinished),
        }
        return {'operation': record, 'summary': summary,
                'attempted': attempted, 'changed': changed,
                'tested': tested, 'blocked': blocked,
                'unfinished': unfinished}
