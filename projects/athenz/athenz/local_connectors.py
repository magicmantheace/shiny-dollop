"""Per-integration opt-in and disable controls for local connectors (v0.8).

A *local connector* is a named integration between AthenZ and something
on the owner's own machine: a local capability such as offline voice
transcription, or a bounded local resource such as a directory of
notes. Connectors in this slice are LOCAL ONLY — no connector here
opens a network connection, and any future network integration needs
its own separately reviewed design.

The registry in this module is the single control plane for every
connector. It follows the same discipline as standing task grants
(slice A2): deny by default, explicit owner action to enable, and an
append-only audit of every decision.

- Every integration starts ``not_opted_in``. Nothing is authorized
  until the owner opts in through the explicit owner action
  (``athenz-connectors opt-in ... --confirm``). ONE documented legacy
  exception exists — see "Voice legacy rule" below.
- Approval is **per tier**. An integration declares its capability
  tiers (``read`` and/or ``write``) separately, and approving one tier
  never approves the other: opting into ``read`` leaves ``write``
  refused with ``tier_not_approved`` until it is separately approved.
- **Disable is frictionless and immediate.** It needs no confirmation,
  clears the approved tiers, and takes effect on the very next gate
  check: approvals are read from the profile store at check time and
  are never cached in memory. Re-enabling after a disable is a fresh
  opt-in — tiers must be approved again, one by one.
- Every gate decision (allow AND refuse) and every state change is
  appended to an audit log in the private profile.

Voice legacy rule — read this before "fixing" it: the builtin
``voice-transcription`` integration predates this registry. The owner
already validated that exact offline transcription flow on their own
hardware, under its own per-use ``--confirm`` and privacy gates, in
October 2026. So the FIRST time this registry is consulted on a
profile, ``voice-transcription`` is seeded ``enabled`` (read tier)
with provenance ``legacy-owner-validated``, and the seeding is
audit-logged. This is a one-way grandfathering of an already-approved
flow, not a precedent: every other integration — builtin or
owner-registered — starts ``not_opted_in`` with no exceptions, and
once the owner disables voice it behaves exactly like any other
integration (re-enable needs an explicit opt-in).

Registry state is private profile data. It lives in the profile
database (the same store the supervised scheduler and task grants
use, following their table-creation pattern) and is never written
into any repository. Remembered preferences and model ideas are NOT
permission: only an opt-in recorded through the explicit owner action
below enables anything, and only for the tiers it names.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import re

from .experience import ExperienceStore
from .store import utc_now

TIERS = frozenset({'read', 'write'})
STATES = frozenset({'not_opted_in', 'enabled', 'disabled'})

VOICE_INTEGRATION_ID = 'voice-transcription'
LOCAL_NOTES_ID = 'local-notes'
LEGACY_VOICE_PROVENANCE = 'legacy-owner-validated'

_NAME = re.compile(r'[a-z0-9][a-z0-9_-]{0,63}\Z')


class ConnectorError(ValueError):
    """A connector action did not meet its owner-authorized boundaries."""


@dataclass(frozen=True)
class Integration:
    """A connector descriptor: what an integration IS (code-defined).

    State — whether the owner has opted in, and to which tiers — is
    separate profile data held by :class:`LocalConnectorStore`.
    """

    id: str
    display_name: str
    kind: str
    tiers: tuple[str, ...]
    description: str
    builtin: bool = True

    def public(self) -> dict:
        return {'id': self.id, 'display_name': self.display_name,
                'kind': self.kind, 'declared_tiers': list(self.tiers),
                'description': self.description, 'builtin': self.builtin}


BUILTIN_INTEGRATIONS: dict[str, Integration] = {
    VOICE_INTEGRATION_ID: Integration(
        id=VOICE_INTEGRATION_ID,
        display_name='Voice transcription',
        kind='speech-to-text',
        tiers=('read',),
        description='Offline transcription of an existing local WAV '
                    'file with a locally installed model (athenz-voice). '
                    'No microphone, upload or storage; each use still '
                    'requires its own --confirm.'),
    LOCAL_NOTES_ID: Integration(
        id=LOCAL_NOTES_ID,
        display_name='Local notes directory',
        kind='local-files',
        tiers=('read', 'write'),
        description='Read text/markdown notes from ONE owner-configured '
                    'local directory; the separately approved write tier '
                    'may only create new note files there, never '
                    'overwrite.'),
}


def _clean_tiers(values, descriptor: Integration) -> list[str]:
    if isinstance(values, str) or not values:
        raise ConnectorError('At least one tier is required')
    out = []
    for value in values:
        if not isinstance(value, str) or value.strip().lower() not in TIERS:
            raise ConnectorError(f'Invalid tier: {value!r}')
        tier = value.strip().lower()
        if tier not in descriptor.tiers:
            raise ConnectorError(
                f'Integration {descriptor.id} does not declare the '
                f'{tier} tier')
        out.append(tier)
    return sorted(set(out))


class LocalConnectorStore:
    """Transactional connector registry; separate store handles per method.

    Follows the task-grant store pattern: private operational tables
    created in the profile database, one connection per operation, so
    a disable recorded by any process is honored by the next check in
    every other process — approvals are never cached.
    """

    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home is not None else None
        with self._open() as store:
            store.db.execute('''CREATE TABLE IF NOT EXISTS local_connector_state (
                integration_id TEXT PRIMARY KEY,
                state TEXT NOT NULL
                    CHECK(state IN ('not_opted_in','enabled','disabled')),
                approved_tiers TEXT NOT NULL DEFAULT '[]',
                config TEXT NOT NULL DEFAULT '{}',
                provenance TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )''')
            store.db.execute('''CREATE TABLE IF NOT EXISTS local_connector_descriptors (
                integration_id TEXT PRIMARY KEY,
                display_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                tiers TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL
            )''')
            store.db.execute('''CREATE TABLE IF NOT EXISTS local_connector_audit (
                id INTEGER PRIMARY KEY,
                integration_id TEXT NOT NULL,
                event TEXT NOT NULL
                    CHECK(event IN ('seeded','registered','opted_in',
                                     'disabled','check')),
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

    # -- internal helpers --------------------------------------------------

    @staticmethod
    def _audit(store, integration_id: str, event: str, *, allowed=None,
               reason: str = '', detail: dict | None = None) -> None:
        store.db.execute(
            'INSERT INTO local_connector_audit'
            ' (integration_id,event,allowed,reason,detail,created_at)'
            ' VALUES (?,?,?,?,?,?)',
            (integration_id, event,
             None if allowed is None else int(bool(allowed)), reason,
             json.dumps(detail or {}, sort_keys=True), utc_now()))

    def _ensure_legacy_voice(self, store) -> None:
        """Seed the one legacy exception, exactly once, audit-logged.

        See the module docstring: ``voice-transcription`` was validated
        by the owner on hardware before this registry existed, so its
        first consult records it enabled (read tier) instead of
        silently breaking an approved flow. Nothing else is seeded.
        """
        row = store.db.execute(
            'SELECT integration_id FROM local_connector_state'
            ' WHERE integration_id=?', (VOICE_INTEGRATION_ID,)).fetchone()
        if row is not None:
            return
        now = utc_now()
        with store.db:
            store.db.execute(
                'INSERT OR IGNORE INTO local_connector_state'
                ' (integration_id,state,approved_tiers,config,provenance,'
                ' created_at,updated_at) VALUES (?,?,?,?,?,?,?)',
                (VOICE_INTEGRATION_ID, 'enabled', json.dumps(['read']),
                 '{}', LEGACY_VOICE_PROVENANCE, now, now))
            self._audit(store, VOICE_INTEGRATION_ID, 'seeded', allowed=True,
                        reason=LEGACY_VOICE_PROVENANCE,
                        detail={'state': 'enabled',
                                'approved_tiers': ['read']})

    def _descriptor(self, store, integration_id: str) -> Integration | None:
        builtin = BUILTIN_INTEGRATIONS.get(integration_id)
        if builtin is not None:
            return builtin
        row = store.db.execute(
            'SELECT * FROM local_connector_descriptors WHERE integration_id=?',
            (integration_id,)).fetchone()
        if row is None:
            return None
        return Integration(id=row['integration_id'],
                           display_name=row['display_name'],
                           kind=row['kind'],
                           tiers=tuple(json.loads(row['tiers'])),
                           description=row['description'], builtin=False)

    def _descriptors(self, store) -> list[Integration]:
        out = list(BUILTIN_INTEGRATIONS.values())
        rows = store.db.execute(
            'SELECT * FROM local_connector_descriptors'
            ' ORDER BY integration_id').fetchall()
        for row in rows:
            out.append(Integration(
                id=row['integration_id'], display_name=row['display_name'],
                kind=row['kind'], tiers=tuple(json.loads(row['tiers'])),
                description=row['description'], builtin=False))
        return out

    @staticmethod
    def _state_row(store, integration_id: str):
        return store.db.execute(
            'SELECT * FROM local_connector_state WHERE integration_id=?',
            (integration_id,)).fetchone()

    @staticmethod
    def _view(descriptor: Integration, row) -> dict:
        view = descriptor.public()
        if row is None:
            view.update({'state': 'not_opted_in', 'approved_tiers': [],
                         'config': {}, 'provenance': '',
                         'created_at': None, 'updated_at': None})
        else:
            view.update({'state': row['state'],
                         'approved_tiers': json.loads(row['approved_tiers']),
                         'config': json.loads(row['config']),
                         'provenance': row['provenance'],
                         'created_at': row['created_at'],
                         'updated_at': row['updated_at']})
        return view

    # -- owner-registered descriptors --------------------------------------

    def register_integration(self, integration_id: str, *,
                             display_name: str, kind: str, tiers,
                             description: str = '',
                             confirmed: bool = False) -> dict:
        """Register an owner-defined descriptor. Requires ``--confirm``.

        Registration only declares what an integration IS; the new
        integration still starts ``not_opted_in`` and needs its own
        per-tier opt-in before the gate allows anything.
        """
        if not confirmed:
            raise ConnectorError(
                'Registering an integration is an explicit owner action:'
                ' pass --confirm')
        if not isinstance(integration_id, str) or \
                not _NAME.fullmatch(integration_id.strip().lower()):
            raise ConnectorError(f'Invalid integration id: {integration_id!r}')
        integration_id = integration_id.strip().lower()
        for value, what in ((display_name, 'display name'), (kind, 'kind')):
            if not isinstance(value, str) or not value.strip():
                raise ConnectorError(f'An integration {what} is required')
        if not isinstance(description, str) or len(description) > 2000:
            raise ConnectorError('Description must be text of at most 2000 chars')
        descriptor = Integration(
            id=integration_id, display_name=display_name.strip(),
            kind=kind.strip(),
            tiers=tuple(_clean_tiers_for_registration(tiers)),
            description=description.strip(), builtin=False)
        with self._open() as store:
            self._ensure_legacy_voice(store)
            if self._descriptor(store, integration_id) is not None:
                raise ConnectorError(
                    f'Integration already registered: {integration_id}')
            with store.db:
                store.db.execute(
                    'INSERT INTO local_connector_descriptors'
                    ' (integration_id,display_name,kind,tiers,description,'
                    ' created_at) VALUES (?,?,?,?,?,?)',
                    (descriptor.id, descriptor.display_name, descriptor.kind,
                     json.dumps(list(descriptor.tiers)),
                     descriptor.description, utc_now()))
                self._audit(store, integration_id, 'registered', allowed=True,
                            reason='explicit owner confirmation',
                            detail={'display_name': descriptor.display_name,
                                    'kind': descriptor.kind,
                                    'tiers': list(descriptor.tiers)})
        return self.get(integration_id)

    # -- reads ---------------------------------------------------------------

    def get(self, integration_id: str) -> dict | None:
        """Descriptor + live state for one integration (None if unknown)."""
        with self._open() as store:
            self._ensure_legacy_voice(store)
            descriptor = self._descriptor(store, integration_id)
            if descriptor is None:
                return None
            return self._view(descriptor,
                              self._state_row(store, integration_id))

    def list(self) -> list[dict]:
        """Every known integration (builtin + owner-registered) with state."""
        with self._open() as store:
            self._ensure_legacy_voice(store)
            return [self._view(descriptor,
                               self._state_row(store, descriptor.id))
                    for descriptor in self._descriptors(store)]

    # -- lifecycle -----------------------------------------------------------

    def opt_in(self, integration_id: str, *, tiers, config: dict | None = None,
               confirmed: bool = False) -> dict:
        """Approve tiers for an integration. Explicit owner action.

        Per-tier: the named tiers are ADDED to the integration's
        approved set; approving one tier never approves another. From
        ``disabled`` the approved set was cleared by the disable, so a
        re-enable approves exactly the tiers named here.
        """
        if not confirmed:
            raise ConnectorError(
                'Opting in is an explicit owner action: pass --confirm')
        with self._open() as store:
            self._ensure_legacy_voice(store)
            descriptor = self._descriptor(store, integration_id)
            if descriptor is None:
                raise ConnectorError(f'No such integration: {integration_id}')
            approved_new = _clean_tiers(tiers, descriptor)
            row = self._state_row(store, integration_id)
            stored_config = json.loads(row['config']) if row else {}
            merged_config = self._clean_config(descriptor, stored_config,
                                               config)
            approved = sorted(set(
                (json.loads(row['approved_tiers']) if row else [])
                + approved_new))
            now = utc_now()
            with store.db:
                if row is None:
                    store.db.execute(
                        'INSERT INTO local_connector_state'
                        ' (integration_id,state,approved_tiers,config,'
                        ' provenance,created_at,updated_at)'
                        ' VALUES (?,?,?,?,?,?,?)',
                        (integration_id, 'enabled', json.dumps(approved),
                         json.dumps(merged_config, sort_keys=True),
                         'owner-opt-in', now, now))
                else:
                    store.db.execute(
                        'UPDATE local_connector_state SET state=?,'
                        ' approved_tiers=?, config=?, provenance=?,'
                        ' updated_at=? WHERE integration_id=?',
                        ('enabled', json.dumps(approved),
                         json.dumps(merged_config, sort_keys=True),
                         'owner-opt-in', now, integration_id))
                self._audit(store, integration_id, 'opted_in', allowed=True,
                            reason='explicit owner confirmation',
                            detail={'approved_tiers': approved,
                                    'newly_approved': approved_new})
            return self._view(descriptor,
                              self._state_row(store, integration_id))

    @staticmethod
    def _clean_config(descriptor: Integration, stored: dict,
                      config: dict | None) -> dict:
        if config is None:
            merged = dict(stored)
        else:
            if not isinstance(config, dict):
                raise ConnectorError('Integration config must be an object')
            merged = {**stored, **config}
        if 'directory' in merged and descriptor.id != LOCAL_NOTES_ID:
            raise ConnectorError(
                'Only the local-notes integration takes a directory')
        if descriptor.id == LOCAL_NOTES_ID:
            directory = merged.get('directory')
            if directory is None:
                raise ConnectorError(
                    'local-notes opt-in requires a notes directory'
                    ' (--directory)')
            if not isinstance(directory, str) or not directory.strip():
                raise ConnectorError('Invalid notes directory')
            resolved = Path(directory).expanduser().resolve()
            if not resolved.is_dir():
                raise ConnectorError(
                    f'Notes directory does not exist: {directory}')
            merged['directory'] = str(resolved)
        return merged

    def disable(self, integration_id: str) -> dict:
        """Disable immediately. No confirmation, by design.

        Clears the approved tiers: a later re-enable is a fresh opt-in
        that must approve tiers again. Takes effect on the very next
        :meth:`require` call in any process, because checks always
        read the store.
        """
        with self._open() as store:
            self._ensure_legacy_voice(store)
            descriptor = self._descriptor(store, integration_id)
            if descriptor is None:
                raise ConnectorError(f'No such integration: {integration_id}')
            row = self._state_row(store, integration_id)
            if row is not None and row['state'] == 'disabled':
                return self._view(descriptor, row)
            now = utc_now()
            with store.db:
                if row is None:
                    store.db.execute(
                        'INSERT INTO local_connector_state'
                        ' (integration_id,state,approved_tiers,config,'
                        ' provenance,created_at,updated_at)'
                        ' VALUES (?,?,?,?,?,?,?)',
                        (integration_id, 'disabled', '[]',
                         '{}', 'owner-disable', now, now))
                else:
                    store.db.execute(
                        'UPDATE local_connector_state SET state=?,'
                        ' approved_tiers=?, provenance=?, updated_at=?'
                        ' WHERE integration_id=?',
                        ('disabled', '[]', 'owner-disable', now,
                         integration_id))
                self._audit(store, integration_id, 'disabled', allowed=True,
                            reason='owner disable (no confirmation required)')
            return self._view(descriptor,
                              self._state_row(store, integration_id))

    # -- the gate --------------------------------------------------------------

    def require(self, integration_id: str, tier: str) -> dict:
        """Check one attempted use against the registry; always audited.

        Returns ``{'allowed': bool, 'reason': str, 'integration_id':
        str, 'tier': str, 'state': str | None}``. Refusal reasons are
        distinct and machine-readable: ``unknown_integration``,
        ``not_opted_in``, ``disabled`` and ``tier_not_approved``. An
        invalid tier NAME is a caller bug, not an authorization
        question, and raises :class:`ConnectorError` instead.
        """
        if not isinstance(tier, str) or tier.strip().lower() not in TIERS:
            raise ConnectorError(f'Invalid tier: {tier!r}')
        tier = tier.strip().lower()
        with self._open() as store:
            self._ensure_legacy_voice(store)
            descriptor = self._descriptor(store, integration_id)
            if descriptor is None:
                result = {'allowed': False, 'reason': 'unknown_integration',
                          'integration_id': integration_id, 'tier': tier,
                          'state': None}
            else:
                row = self._state_row(store, integration_id)
                state = row['state'] if row else 'not_opted_in'
                if state == 'disabled':
                    reason = 'disabled'
                elif state != 'enabled':
                    reason = 'not_opted_in'
                elif tier not in json.loads(row['approved_tiers']):
                    reason = 'tier_not_approved'
                else:
                    reason = 'allowed'
                result = {'allowed': reason == 'allowed', 'reason': reason,
                          'integration_id': integration_id, 'tier': tier,
                          'state': state}
            with store.db:
                self._audit(store, integration_id, 'check',
                            allowed=result['allowed'],
                            reason=result['reason'],
                            detail={'tier': tier, 'state': result['state']})
            return result

    # -- audit -----------------------------------------------------------------

    def audit(self, integration_id: str | None = None,
              limit: int = 100) -> list[dict]:
        """Recent registry events (checks and state changes), oldest first."""
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ConnectorError('Audit limit must be a positive integer')
        with self._open() as store:
            self._ensure_legacy_voice(store)
            if integration_id is None:
                rows = store.db.execute(
                    'SELECT * FROM local_connector_audit ORDER BY id DESC'
                    ' LIMIT ?', (limit,)).fetchall()
            else:
                rows = store.db.execute(
                    'SELECT * FROM local_connector_audit'
                    ' WHERE integration_id=? ORDER BY id DESC LIMIT ?',
                    (integration_id, limit)).fetchall()
            out = []
            for row in reversed(rows):
                entry = dict(row)
                entry['detail'] = json.loads(entry['detail'])
                entry['allowed'] = None if entry['allowed'] is None \
                    else bool(entry['allowed'])
                out.append(entry)
            return out


def _clean_tiers_for_registration(values) -> list[str]:
    """Validate the declared tier set of an owner-registered descriptor."""
    if isinstance(values, str) or not values:
        raise ConnectorError('At least one declared tier is required')
    out = []
    for value in values:
        if not isinstance(value, str) or value.strip().lower() not in TIERS:
            raise ConnectorError(f'Invalid tier: {value!r}')
        out.append(value.strip().lower())
    return sorted(set(out))
