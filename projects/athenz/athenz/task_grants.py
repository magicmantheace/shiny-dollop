"""Narrow standing authorization for coding tasks (roadmap slice A2).

A *task grant* is an explicit, local, owner-reviewed standing
authorization for coding work on ONE repository/worktree. It is the
only bridge between a planner proposal (slice A1) and any future
execution (slice A3): no grant, no standing authorization — the
supervised, per-stage manual approvals remain the default.

Grants are deliberately narrow and default-deny:

- Creation requires an explicit owner ``--confirm`` action plus an
  explicit value for every scope field. Nothing widens by default:
  the network policy defaults to ``none`` and every budget must be
  stated.
- A grant names a specific repository (and optionally one worktree),
  task classes, allowed file globs, permitted tools, a network policy
  and budgets (tasks, test runs, retries per task, wall-clock) with an
  expiry. Every field is checked on every authorization call.
- Some operations are NEVER grantable, whatever a grant says: remote
  push, merge, release, package installation, deployment and access
  to private Twin/profile data stay owner-gated per action (slice A5).
  They are refused at grant creation and again at check time.
- Pause takes effect immediately; revocation is immediate and
  permanent for that grant (a revoked grant can never resume — the
  owner creates a new grant instead). Expiry is evaluated on every
  read and check.
- Every authorization check — allowed AND denied — and every grant
  lifecycle event is appended to an audit log in the private profile,
  queryable by grant id. The log is append-only through this API.

Grants are private profile data. They live in the profile database
(the same store the supervised scheduler uses, following its
table-creation pattern) and are never written into any repository.
Remembered preferences, planner output and model ideas are NOT
permission: only a grant created through the explicit owner action
below authorizes anything, and even then only within its scope.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
import fnmatch
import json
from pathlib import Path
import re
import uuid

from .experience import ExperienceStore
from .store import utc_now

GRANT_STATES = frozenset({'active', 'paused', 'revoked', 'expired'})
NETWORK_POLICIES = frozenset({'none', 'allowlist'})

# Operations a standing grant can never authorize, however it is
# written. These remain separately reviewed owner decisions (A5).
NEVER_GRANTABLE_TOOLS = frozenset({
    'git_push', 'push', 'merge', 'git_merge', 'release', 'publish',
    'install_package', 'package_install', 'pip_install', 'deploy',
    'deployment', 'profile_read', 'twin_data_read', 'read_private_data',
})

_NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}\Z')


class GrantError(ValueError):
    """A grant action did not meet its owner-authorized boundaries."""


def _clean_names(values, what: str) -> list[str]:
    if isinstance(values, str) or not values:
        raise GrantError(f'At least one {what} is required')
    out = []
    for value in values:
        if not isinstance(value, str) or not _NAME.fullmatch(value.strip().lower()):
            raise GrantError(f'Invalid {what}: {value!r}')
        out.append(value.strip().lower())
    return sorted(set(out))


def _clean_globs(values) -> list[str]:
    if isinstance(values, str) or not values:
        raise GrantError('At least one allowed file glob is required')
    out = []
    for value in values:
        if not isinstance(value, str) or not value.strip():
            raise GrantError(f'Invalid file glob: {value!r}')
        glob = value.strip().replace('\\', '/')
        if glob.startswith('/') or glob == '..' or glob.startswith('../'):
            raise GrantError(f'File globs must be repository-relative: {value!r}')
        out.append(glob)
    return sorted(set(out))


def _clean_budget(value, name: str, minimum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise GrantError(f'Budget {name} must be an integer >= {minimum}')
    return value


class TaskGrantStore:
    """Transactional grant store; separate store handles per method.

    Follows the supervised scheduler's pattern: private operational
    tables created in the profile database, ``BEGIN IMMEDIATE``-style
    serialization through one connection per operation.
    """

    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home is not None else None
        with self._open() as store:
            store.db.execute('''CREATE TABLE IF NOT EXISTS task_grants (
                id TEXT PRIMARY KEY,
                objective TEXT NOT NULL,
                queue_item_ids TEXT NOT NULL DEFAULT '[]',
                repository TEXT NOT NULL,
                worktree TEXT NOT NULL,
                task_classes TEXT NOT NULL,
                allowed_files TEXT NOT NULL,
                permitted_tools TEXT NOT NULL,
                network_policy TEXT NOT NULL
                    CHECK(network_policy IN ('none','allowlist')),
                network_allowlist TEXT NOT NULL DEFAULT '[]',
                max_tasks INTEGER NOT NULL,
                max_test_runs INTEGER NOT NULL,
                max_retries_per_task INTEGER NOT NULL,
                max_wall_clock_seconds INTEGER NOT NULL,
                tasks_used INTEGER NOT NULL DEFAULT 0,
                test_runs_used INTEGER NOT NULL DEFAULT 0,
                wall_clock_seconds_used INTEGER NOT NULL DEFAULT 0,
                state TEXT NOT NULL
                    CHECK(state IN ('active','paused','revoked','expired')),
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT NOT NULL
            )''')
            store.db.execute('''CREATE TABLE IF NOT EXISTS task_grant_retries (
                grant_id TEXT NOT NULL,
                task_id TEXT NOT NULL,
                retries INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (grant_id, task_id)
            )''')
            store.db.execute('''CREATE TABLE IF NOT EXISTS task_grant_audit (
                id INTEGER PRIMARY KEY,
                grant_id TEXT NOT NULL,
                event TEXT NOT NULL
                    CHECK(event IN ('created','paused','resumed','revoked',
                                     'expired','check')),
                allowed INTEGER,
                reason TEXT NOT NULL DEFAULT '',
                detail TEXT NOT NULL DEFAULT '{}',
                created_at TEXT NOT NULL
            )''')
            store.db.commit()

    @contextmanager
    def _open(self):
        store = ExperienceStore(self.home)
        try:
            yield store
        finally:
            store.close()

    # -- internal helpers ------------------------------------------------

    @staticmethod
    def _audit(store, grant_id: str, event: str, *, allowed=None,
               reason: str = '', detail: dict | None = None) -> None:
        store.db.execute(
            'INSERT INTO task_grant_audit (grant_id,event,allowed,reason,detail,created_at)'
            ' VALUES (?,?,?,?,?,?)',
            (grant_id, event, None if allowed is None else int(bool(allowed)),
             reason, json.dumps(detail or {}, sort_keys=True), utc_now()))

    @staticmethod
    def _public(row) -> dict:
        out = dict(row)
        for key, target in (('queue_item_ids', 'queue_item_ids'),
                            ('task_classes', 'task_classes'),
                            ('allowed_files', 'allowed_files'),
                            ('permitted_tools', 'permitted_tools'),
                            ('network_allowlist', 'network_allowlist')):
            out[target] = json.loads(out.pop(key))
        return out

    def _load(self, store, grant_id: str):
        row = store.db.execute('SELECT * FROM task_grants WHERE id=?',
                               (grant_id,)).fetchone()
        return row

    def _evaluate_expiry(self, store, row) -> dict:
        """Return the grant as a dict, lazily expiring it if its time is up."""
        grant = self._public(row)
        if grant['state'] in ('active', 'paused') and \
                datetime.now(timezone.utc) >= datetime.fromisoformat(grant['expires_at']):
            with store.db:
                store.db.execute(
                    "UPDATE task_grants SET state='expired', updated_at=? WHERE id=?",
                    (utc_now(), grant['id']))
                self._audit(store, grant['id'], 'expired',
                            reason='expiry reached')
            grant['state'] = 'expired'
        return grant

    # -- lifecycle ---------------------------------------------------------

    def create(self, *, objective: str, repository, worktree=None,
               queue_item_ids=(), task_classes, allowed_files,
               permitted_tools, network_policy: str = 'none',
               network_allowlist=(), max_tasks: int, max_test_runs: int,
               max_retries_per_task: int, max_wall_clock_seconds: int,
               duration_seconds: int, confirmed: bool = False) -> dict:
        """Create a grant. Requires the explicit owner ``confirmed`` action.

        Every scope field is mandatory; there are no widening defaults.
        """
        if not confirmed:
            raise GrantError(
                'Grant creation is an explicit owner action: pass --confirm')
        if not isinstance(objective, str) or not objective.strip():
            raise GrantError('An objective (what this grant is for) is required')
        if len(objective) > 2000:
            raise GrantError('Objective is too large')
        repo = Path(repository).expanduser().resolve()
        if not repo.is_dir():
            raise GrantError(f'Repository does not exist: {repo}')
        tree = Path(worktree).expanduser().resolve() if worktree else repo
        if not tree.is_dir():
            raise GrantError(f'Worktree does not exist: {tree}')
        classes = _clean_names(task_classes, 'task class')
        tools = _clean_names(permitted_tools, 'tool')
        bad = [t for t in tools if t in NEVER_GRANTABLE_TOOLS]
        if bad:
            raise GrantError(
                f'These operations can never be granted: {", ".join(bad)}')
        globs = _clean_globs(allowed_files)
        if network_policy not in NETWORK_POLICIES:
            raise GrantError(f'Network policy must be one of {sorted(NETWORK_POLICIES)}')
        hosts = []
        if network_policy == 'allowlist':
            if isinstance(network_allowlist, str) or not network_allowlist:
                raise GrantError(
                    'An allowlist network policy requires at least one host')
            for host in network_allowlist:
                if not isinstance(host, str) or not host.strip() or \
                        '://' in host or '/' in host:
                    raise GrantError(f'Invalid allowlist host: {host!r}')
                hosts.append(host.strip().lower())
            hosts = sorted(set(hosts))
        elif network_allowlist:
            raise GrantError(
                'A network allowlist is only meaningful with the allowlist policy')
        items = []
        for item in queue_item_ids or ():
            if not isinstance(item, str) or not item.strip():
                raise GrantError(f'Invalid queue item id: {item!r}')
            items.append(item.strip())
        budgets = {
            'max_tasks': _clean_budget(max_tasks, 'max_tasks', 1),
            'max_test_runs': _clean_budget(max_test_runs, 'max_test_runs', 0),
            'max_retries_per_task': _clean_budget(
                max_retries_per_task, 'max_retries_per_task', 0),
            'max_wall_clock_seconds': _clean_budget(
                max_wall_clock_seconds, 'max_wall_clock_seconds', 1),
        }
        if isinstance(duration_seconds, bool) or \
                not isinstance(duration_seconds, int) or duration_seconds < 1:
            raise GrantError('A positive integer duration is required (expiry)')
        now = datetime.now(timezone.utc)
        grant_id = 'grant-' + uuid.uuid4().hex[:16]
        record = {
            'id': grant_id,
            'objective': objective.strip(),
            'queue_item_ids': items,
            'repository': str(repo),
            'worktree': str(tree),
            'task_classes': classes,
            'allowed_files': globs,
            'permitted_tools': tools,
            'network_policy': network_policy,
            'network_allowlist': hosts,
            **budgets,
            'tasks_used': 0, 'test_runs_used': 0, 'wall_clock_seconds_used': 0,
            'state': 'active',
            'created_at': now.isoformat(), 'updated_at': now.isoformat(),
            'expires_at': (now + timedelta(seconds=duration_seconds)).isoformat(),
        }
        with self._open() as store:
            with store.db:
                store.db.execute(
                    'INSERT INTO task_grants (id,objective,queue_item_ids,repository,'
                    'worktree,task_classes,allowed_files,permitted_tools,network_policy,'
                    'network_allowlist,max_tasks,max_test_runs,max_retries_per_task,'
                    'max_wall_clock_seconds,state,created_at,updated_at,expires_at)'
                    ' VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (record['id'], record['objective'],
                     json.dumps(record['queue_item_ids']), record['repository'],
                     record['worktree'], json.dumps(record['task_classes']),
                     json.dumps(record['allowed_files']),
                     json.dumps(record['permitted_tools']),
                     record['network_policy'], json.dumps(record['network_allowlist']),
                     record['max_tasks'], record['max_test_runs'],
                     record['max_retries_per_task'],
                     record['max_wall_clock_seconds'], record['state'],
                     record['created_at'], record['updated_at'],
                     record['expires_at']))
                self._audit(store, grant_id, 'created', allowed=True,
                            reason='explicit owner confirmation',
                            detail={'objective': record['objective'],
                                    'queue_item_ids': items,
                                    'repository': record['repository']})
        return record

    def get(self, grant_id: str) -> dict | None:
        with self._open() as store:
            row = self._load(store, grant_id)
            return self._evaluate_expiry(store, row) if row else None

    def list(self) -> list[dict]:
        with self._open() as store:
            rows = store.db.execute(
                'SELECT * FROM task_grants ORDER BY created_at').fetchall()
            return [self._evaluate_expiry(store, row) for row in rows]

    def _transition(self, grant_id: str, action: str, *,
                    confirmed: bool = False) -> dict:
        with self._open() as store:
            row = self._load(store, grant_id)
            if row is None:
                raise GrantError(f'No such grant: {grant_id}')
            grant = self._evaluate_expiry(store, row)
            state = grant['state']
            if action == 'pause':
                if state == 'revoked':
                    raise GrantError('A revoked grant cannot be paused')
                if state == 'expired':
                    raise GrantError('An expired grant cannot be paused')
                new_state = 'paused'
            elif action == 'resume':
                if not confirmed:
                    raise GrantError(
                        'Resuming a grant is an owner action: pass --confirm')
                if state == 'revoked':
                    raise GrantError(
                        'A revoked grant can never resume; create a new grant')
                if state == 'expired':
                    raise GrantError(
                        'An expired grant cannot resume; create a new grant')
                new_state = 'active'
            else:  # revoke
                if not confirmed:
                    raise GrantError(
                        'Revoking a grant is an owner action: pass --confirm')
                if state == 'revoked':
                    return grant
                new_state = 'revoked'
            if state != new_state:
                with store.db:
                    store.db.execute(
                        'UPDATE task_grants SET state=?, updated_at=? WHERE id=?',
                        (new_state, utc_now(), grant_id))
                    self._audit(store, grant_id, action + 'd' if action != 'pause'
                                else 'paused', allowed=True,
                                reason=f'owner {action}')
                grant['state'] = new_state
            return grant

    def pause(self, grant_id: str) -> dict:
        """Immediate: pausing never needs confirmation."""
        return self._transition(grant_id, 'pause')

    def resume(self, grant_id: str, *, confirmed: bool = False) -> dict:
        return self._transition(grant_id, 'resume', confirmed=confirmed)

    def revoke(self, grant_id: str, *, confirmed: bool = False) -> dict:
        """Immediate and permanent for this grant once confirmed."""
        return self._transition(grant_id, 'revoke', confirmed=confirmed)

    # -- authorization ---------------------------------------------------

    def authorize(self, grant_id: str, *, repository, task_class: str | None = None,
                  file: str | None = None, tool: str | None = None,
                  network_target: str | None = None, task_id: str | None = None,
                  new_task: bool = False, test_run: bool = False,
                  retry: bool = False, wall_clock_seconds: int = 0) -> dict:
        """Check one attempted operation against a grant; always audited.

        Returns ``{'allowed': bool, 'reason': str, 'grant_id': str}``
        with a specific machine-readable reason. Consumption flags
        (``new_task``/``test_run``/``retry``/``wall_clock_seconds``)
        are recorded only when the operation is allowed, atomically
        with the check, so budgets cannot be overspent by racing
        check-then-act callers.
        """
        detail = {'repository': str(repository), 'task_class': task_class,
                  'file': file, 'tool': tool, 'network_target': network_target,
                  'task_id': task_id}
        with self._open() as store:
            row = self._load(store, grant_id)
            if row is None:
                result = {'allowed': False, 'reason': 'grant_not_found',
                          'grant_id': grant_id}
                with store.db:
                    self._audit(store, grant_id, 'check', allowed=False,
                                reason=result['reason'], detail=detail)
                return result
            grant = self._evaluate_expiry(store, row)
            reason = self._deny_reason(store, grant, repository=repository,
                                       task_class=task_class, file=file,
                                       tool=tool, network_target=network_target,
                                       task_id=task_id, new_task=new_task,
                                       test_run=test_run, retry=retry,
                                       wall_clock_seconds=wall_clock_seconds)
            allowed = reason is None
            result = {'allowed': allowed,
                      'reason': 'allowed' if allowed else reason,
                      'grant_id': grant_id}
            with store.db:
                if allowed:
                    self._consume(store, grant, task_id=task_id,
                                  new_task=new_task, test_run=test_run,
                                  retry=retry,
                                  wall_clock_seconds=wall_clock_seconds)
                self._audit(store, grant_id, 'check', allowed=allowed,
                            reason=result['reason'], detail=detail)
            return result

    @staticmethod
    def _deny_reason(store, grant: dict, *, repository, task_class, file,
                     tool, network_target, task_id, new_task, test_run,
                     retry, wall_clock_seconds) -> str | None:
        if grant['state'] == 'paused':
            return 'grant_paused'
        if grant['state'] == 'revoked':
            return 'grant_revoked'
        if grant['state'] == 'expired':
            return 'grant_expired'
        if tool is not None and tool.strip().lower() in NEVER_GRANTABLE_TOOLS:
            return 'tool_never_grantable'
        repo = Path(repository).expanduser().resolve()
        if str(repo) not in (grant['repository'], grant['worktree']):
            return 'repository_out_of_scope'
        if task_class is not None and \
                task_class.strip().lower() not in grant['task_classes']:
            return 'task_class_not_permitted'
        if file is not None:
            rel = file.replace('\\', '/')
            if rel.startswith('/') or rel == '..' or rel.startswith('../') \
                    or '/..' in rel:
                return 'file_out_of_scope'
            if not any(fnmatch.fnmatchcase(rel, glob)
                       for glob in grant['allowed_files']):
                return 'file_out_of_scope'
        if tool is not None and \
                tool.strip().lower() not in grant['permitted_tools']:
            return 'tool_not_permitted'
        if network_target is not None:
            if grant['network_policy'] == 'none':
                return 'network_not_permitted'
            host = network_target.strip().lower()
            if host not in grant['network_allowlist']:
                return 'network_target_not_allowed'
        if new_task and grant['tasks_used'] >= grant['max_tasks']:
            return 'budget_tasks_exhausted'
        if test_run and grant['test_runs_used'] >= grant['max_test_runs']:
            return 'budget_test_runs_exhausted'
        if retry:
            if not task_id:
                return 'retry_requires_task_id'
            row = store.db.execute(
                'SELECT retries FROM task_grant_retries WHERE grant_id=? AND task_id=?',
                (grant['id'], task_id)).fetchone()
            used = row[0] if row else 0
            if used >= grant['max_retries_per_task']:
                return 'budget_retries_exceeded'
        if wall_clock_seconds:
            if isinstance(wall_clock_seconds, bool) or \
                    not isinstance(wall_clock_seconds, int) or wall_clock_seconds < 0:
                return 'invalid_wall_clock'
            if grant['wall_clock_seconds_used'] + wall_clock_seconds > \
                    grant['max_wall_clock_seconds']:
                return 'budget_wall_clock_exhausted'
        return None

    @staticmethod
    def _consume(store, grant: dict, *, task_id, new_task, test_run, retry,
                 wall_clock_seconds) -> None:
        sets, params = [], []
        if new_task:
            sets.append('tasks_used=tasks_used+1')
        if test_run:
            sets.append('test_runs_used=test_runs_used+1')
        if wall_clock_seconds:
            sets.append('wall_clock_seconds_used=wall_clock_seconds_used+?')
            params.append(wall_clock_seconds)
        if sets:
            sets.append('updated_at=?')
            params.append(utc_now())
            params.append(grant['id'])
            store.db.execute(
                f"UPDATE task_grants SET {', '.join(sets)} WHERE id=?", params)
        if retry and task_id:
            store.db.execute(
                'INSERT INTO task_grant_retries (grant_id,task_id,retries)'
                ' VALUES (?,?,1) ON CONFLICT(grant_id,task_id)'
                ' DO UPDATE SET retries=retries+1', (grant['id'], task_id))

    # -- audit -------------------------------------------------------------

    def audit(self, grant_id: str) -> list[dict]:
        """Every recorded check and lifecycle event for one grant, in order."""
        with self._open() as store:
            rows = store.db.execute(
                'SELECT * FROM task_grant_audit WHERE grant_id=? ORDER BY id',
                (grant_id,)).fetchall()
            out = []
            for row in rows:
                entry = dict(row)
                entry['detail'] = json.loads(entry['detail'])
                entry['allowed'] = None if entry['allowed'] is None \
                    else bool(entry['allowed'])
                out.append(entry)
            return out
