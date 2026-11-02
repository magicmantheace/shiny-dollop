"""Verified artifact IDs and reproducible external test attestations.

Roadmap v0.3 leftover. Two pieces:

- **Artifact identity.** An artifact is any file whose bytes matter
  (a build output, a portable bundle, an exported model...). Its ID
  is the SHA-256 of its exact bytes — content-addressed, reproducible
  by anyone with the file. A registry in the private profile maps the
  ID to metadata (name, size, media type, source note, registration
  time) and a *location reference*: the path where the bytes were
  seen. The bytes themselves are never copied into the database.

- **Test attestations.** An attestation binds an artifact ID to a
  test-suite run that THIS tool performed: the CLI runs
  ``unittest discover`` itself in a subprocess and records the real
  result (tests run / passed / failed / skipped, exit status), the
  suite identity (runner kind + a fingerprint of the exact command
  shape and target), and an environment fingerprint captured from the
  runner's actual runtime (platform, Python implementation/version,
  machine). Attestations are append-only. Each stored record carries
  a digest of its own canonical serialization, and each result
  payload carries its own digest, so later edits to the stored rows
  are detectable. A failing suite is recorded as failed — never
  hidden, never rounded up to a pass.

Verification never trusts a stored hash: ``verify`` recomputes the
artifact's digest from its recorded location, recomputes every
record digest, and reports per-attestation status — ``valid``,
``record_tampered``, ``artifact_mismatch`` (the bytes at the
location no longer hash to the artifact ID) or
``suite_result_failed``. A missing file is the distinct
``artifact_missing`` outcome.

**What this does not prove.** An attestation proves that a specific
result was recorded, bound to exact bytes, in a record whose later
tampering is detectable. It does NOT prove the runner was honest at
issuance time, and it cannot manufacture trust in the original
runner: a malicious runner could record a fabricated result and the
digests would still be self-consistent. External verification
detects tampering and byte mismatch; trust in the issuing
environment remains the owner's judgement. This matches the
codebase's standing position that local observed results are not
independent or cryptographic attestations.

Records are private profile data (the profile database, following
the task-grants store pattern) and are never written into any
repository. Export produces a single JSON document carrying only the
artifact metadata and its attestations — no location, no other
profile data — and import into another profile re-verifies every
digest on ingest and rejects a tampered document wholesale.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid

from .experience import ExperienceStore
from .store import utc_now

EXPORT_FORMAT = 'athenz-artifact-attestations/v1'
RUNNER_KIND = 'unittest-discover'
RUNNER_NAME = 'athenz-artifact-attestations'
RUNNER_VERSION = '1'
DEFAULT_PATTERN = 'test*.py'
DEFAULT_TIMEOUT_SECONDS = 600
MAX_FAILED_TEST_IDS = 100
_HEX64 = frozenset('0123456789abcdef')


class AttestationError(ValueError):
    """An artifact/attestation action did not meet its boundaries."""


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=False).encode('utf-8')


def _digest(obj) -> str:
    return hashlib.sha256(_canonical(obj)).hexdigest()


def hash_file(path: Path) -> str:
    """SHA-256 of a file's exact bytes, read in chunks."""
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def _artifact_identity_fields(row: dict) -> dict:
    """The fields an artifact record digest covers.

    The recorded location is deliberately excluded: it is per-profile
    bookkeeping (where THIS profile last saw the bytes), not part of
    the artifact's identity, and it must be free to differ across
    profiles for export/import digests to stay stable.
    """
    return {
        'artifact_id': row['artifact_id'],
        'name': row['name'],
        'size': row['size'],
        'media_type': row['media_type'],
        'source': row['source'],
        'created_at': row['created_at'],
    }


def _attestation_identity_fields(row: dict) -> dict:
    return {
        'id': row['id'],
        'artifact_id': row['artifact_id'],
        'suite_name': row['suite_name'],
        'suite_target': row['suite_target'],
        'suite_fingerprint': row['suite_fingerprint'],
        'result': row['result'],
        'result_digest': row['result_digest'],
        'environment': row['environment'],
        'created_at': row['created_at'],
    }


def suite_fingerprint(suite_dir: Path, pattern: str) -> str:
    """Fingerprint of what a suite run is: runner + command shape + target.

    Reproducible: the same runner version against the same target
    with the same pattern yields the same fingerprint.
    """
    return _digest({
        'kind': RUNNER_KIND,
        'runner': RUNNER_NAME,
        'runner_version': RUNNER_VERSION,
        'command': ['python', '-m', 'unittest', 'discover',
                    '-s', '<suite_dir>', '-p', pattern],
        'suite_target': str(suite_dir),
        'pattern': pattern,
    })


def run_suite(suite_dir: Path, *, pattern: str = DEFAULT_PATTERN,
              timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """Run a unittest suite in a subprocess and return its real result.

    The child process performs discovery and execution and prints one
    JSON document (result + environment fingerprint captured from the
    child's own runtime). A suite that fails is a *result*, not an
    error here; only a runner malfunction (no/invalid output, timeout)
    raises, and then nothing is recorded by the caller.
    """
    suite_dir = Path(suite_dir).expanduser().resolve()
    if not suite_dir.is_dir():
        raise AttestationError(f'Suite directory does not exist: {suite_dir}')
    env = dict(os.environ)
    package_parent = str(Path(__file__).resolve().parent.parent)
    existing = env.get('PYTHONPATH', '')
    env['PYTHONPATH'] = package_parent + (os.pathsep + existing if existing else '')
    argv = [sys.executable, '-m', 'athenz.artifact_attestations_cli',
            '_run-suite', '--suite-dir', str(suite_dir),
            '--pattern', pattern]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=timeout, env=env)
    except subprocess.TimeoutExpired:
        raise AttestationError(
            f'Suite run timed out after {timeout}s; no attestation recorded') from None
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    if not lines:
        raise AttestationError(
            'Suite runner produced no result; no attestation recorded. '
            f'stderr: {proc.stderr.strip()[-500:]}')
    try:
        payload = json.loads(lines[-1])
        result = payload['result']
        environment = payload['environment']
    except (ValueError, KeyError, TypeError):
        raise AttestationError(
            'Suite runner produced an unreadable result; no attestation '
            f'recorded. stderr: {proc.stderr.strip()[-500:]}') from None
    return {'result': result, 'environment': environment}


class ArtifactAttestationStore:
    """Artifact registry + append-only attestation log in the profile DB.

    Follows the task-grants pattern: private operational tables in the
    profile database, one store handle per operation.
    """

    def __init__(self, home: Path | None = None):
        self.home = Path(home) if home is not None else None
        with self._open() as store:
            store.db.execute('''CREATE TABLE IF NOT EXISTS artifacts (
                artifact_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                size INTEGER NOT NULL,
                media_type TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT '',
                location TEXT,
                created_at TEXT NOT NULL,
                record_digest TEXT NOT NULL
            )''')
            store.db.execute('''CREATE TABLE IF NOT EXISTS artifact_attestations (
                id TEXT PRIMARY KEY,
                artifact_id TEXT NOT NULL,
                suite_name TEXT NOT NULL,
                suite_target TEXT NOT NULL,
                suite_fingerprint TEXT NOT NULL,
                result TEXT NOT NULL,
                result_digest TEXT NOT NULL,
                environment TEXT NOT NULL,
                created_at TEXT NOT NULL,
                record_digest TEXT NOT NULL
            )''')
            store.db.execute('''CREATE INDEX IF NOT EXISTS
                artifact_attestations_by_artifact
                ON artifact_attestations (artifact_id, created_at)''')
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
    def _artifact_public(row) -> dict:
        out = dict(row)
        out['size'] = int(out['size'])
        return out

    @staticmethod
    def _attestation_public(row) -> dict:
        out = dict(row)
        out['result'] = json.loads(out['result'])
        out['environment'] = json.loads(out['environment'])
        return out

    def _load_artifact(self, store, artifact_id: str):
        return store.db.execute(
            'SELECT * FROM artifacts WHERE artifact_id=?',
            (artifact_id,)).fetchone()

    def _load_attestations(self, store, artifact_id: str) -> list[dict]:
        rows = store.db.execute(
            'SELECT * FROM artifact_attestations WHERE artifact_id=?'
            ' ORDER BY created_at, id', (artifact_id,)).fetchall()
        return [self._attestation_public(r) for r in rows]

    @staticmethod
    def _check_id(artifact_id) -> str:
        if not isinstance(artifact_id, str) or len(artifact_id) != 64 \
                or any(c not in _HEX64 for c in artifact_id):
            raise AttestationError(f'Invalid artifact id: {artifact_id!r}')
        return artifact_id

    # -- registry ----------------------------------------------------------

    def register(self, path, *, name: str | None = None,
                 source: str = '') -> dict:
        """Register a file's bytes under their SHA-256 identity.

        Re-registering the same bytes returns the existing entry (and
        refreshes the recorded location, which is only ever set after
        the file's hash has been recomputed and matched).
        """
        target = Path(path).expanduser().resolve()
        if not target.is_file():
            raise AttestationError(f'Artifact file does not exist: {target}')
        if name is not None and (not isinstance(name, str)
                                 or not name.strip() or len(name) > 300):
            raise AttestationError('Artifact name must be 1..300 characters')
        if not isinstance(source, str) or len(source) > 2000:
            raise AttestationError('Source description is too large')
        artifact_id = hash_file(target)
        with self._open() as store:
            row = self._load_artifact(store, artifact_id)
            if row is not None:
                entry = self._artifact_public(row)
                if entry['location'] != str(target):
                    with store.db:
                        store.db.execute(
                            'UPDATE artifacts SET location=? WHERE artifact_id=?',
                            (str(target), artifact_id))
                    entry['location'] = str(target)
                entry['already_registered'] = True
                return entry
            entry = {
                'artifact_id': artifact_id,
                'name': (name or target.name).strip(),
                'size': target.stat().st_size,
                'media_type': mimetypes.guess_type(target.name)[0]
                              or 'application/octet-stream',
                'source': source.strip(),
                'location': str(target),
                'created_at': utc_now(),
            }
            entry['record_digest'] = _digest(_artifact_identity_fields(entry))
            with store.db:
                store.db.execute(
                    'INSERT INTO artifacts (artifact_id,name,size,media_type,'
                    'source,location,created_at,record_digest)'
                    ' VALUES (?,?,?,?,?,?,?,?)',
                    (entry['artifact_id'], entry['name'], entry['size'],
                     entry['media_type'], entry['source'], entry['location'],
                     entry['created_at'], entry['record_digest']))
            entry['already_registered'] = False
            return entry

    def get(self, artifact_id: str) -> dict:
        self._check_id(artifact_id)
        with self._open() as store:
            row = self._load_artifact(store, artifact_id)
            if row is None:
                raise AttestationError(f'Unknown artifact: {artifact_id}')
            entry = self._artifact_public(row)
            entry['attestations'] = self._load_attestations(store, artifact_id)
            return entry

    def list(self) -> list[dict]:
        with self._open() as store:
            rows = store.db.execute(
                'SELECT a.*, (SELECT COUNT(*) FROM artifact_attestations t'
                ' WHERE t.artifact_id = a.artifact_id) AS attestation_count'
                ' FROM artifacts a ORDER BY a.created_at, a.artifact_id').fetchall()
            out = []
            for row in rows:
                entry = self._artifact_public(row)
                entry['attestation_count'] = int(entry.pop('attestation_count'))
                out.append(entry)
            return out

    # -- attestations ------------------------------------------------------

    def attest(self, artifact_id: str, suite_dir, *,
               pattern: str = DEFAULT_PATTERN,
               timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict:
        """Run a suite now and record its real result against an artifact.

        Refuses when the artifact is unregistered, when its recorded
        file is missing, or when the file's current bytes no longer
        hash to the artifact ID — an attestation is never issued
        against bytes other than the ones the ID names.
        """
        self._check_id(artifact_id)
        with self._open() as store:
            row = self._load_artifact(store, artifact_id)
            if row is None:
                raise AttestationError(
                    f'Cannot attest an unregistered artifact: {artifact_id}')
            entry = self._artifact_public(row)
        location = entry['location']
        if not location or not Path(location).is_file():
            raise AttestationError(
                'Artifact file is missing at its recorded location; '
                're-register the bytes before attesting')
        if hash_file(Path(location)) != artifact_id:
            raise AttestationError(
                'Artifact bytes no longer match the artifact ID; '
                'register the current bytes as their own artifact first')
        suite_path = Path(suite_dir).expanduser().resolve()
        run = run_suite(suite_path, pattern=pattern, timeout=timeout)
        attestation = {
            'id': uuid.uuid4().hex,
            'artifact_id': artifact_id,
            'suite_name': RUNNER_KIND,
            'suite_target': str(suite_path),
            'suite_fingerprint': suite_fingerprint(suite_path, pattern),
            'result': run['result'],
            'result_digest': _digest(run['result']),
            'environment': run['environment'],
            'created_at': utc_now(),
        }
        attestation['record_digest'] = _digest(
            _attestation_identity_fields(attestation))
        with self._open() as store:
            with store.db:
                store.db.execute(
                    'INSERT INTO artifact_attestations (id,artifact_id,'
                    'suite_name,suite_target,suite_fingerprint,result,'
                    'result_digest,environment,created_at,record_digest)'
                    ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (attestation['id'], attestation['artifact_id'],
                     attestation['suite_name'], attestation['suite_target'],
                     attestation['suite_fingerprint'],
                     json.dumps(attestation['result'], sort_keys=True),
                     attestation['result_digest'],
                     json.dumps(attestation['environment'], sort_keys=True),
                     attestation['created_at'], attestation['record_digest']))
        return attestation

    # -- verification --------------------------------------------------------

    def verify(self, artifact_id: str) -> dict:
        """Recompute everything; trust no stored hash.

        Per-attestation status, in precedence order:
        ``record_tampered`` (the stored record no longer matches its
        own digest), ``artifact_missing`` (no bytes at the recorded
        location to check against), ``artifact_mismatch`` (the bytes
        present hash to a different ID), ``suite_result_failed`` (the
        recorded run itself failed) and ``valid``.
        """
        self._check_id(artifact_id)
        with self._open() as store:
            row = self._load_artifact(store, artifact_id)
            if row is None:
                raise AttestationError(f'Unknown artifact: {artifact_id}')
            entry = self._artifact_public(row)
            attestations = self._load_attestations(store, artifact_id)
        registry_ok = _digest(_artifact_identity_fields(entry)) \
            == entry['record_digest']
        location = entry['location']
        current_id = None
        if location and Path(location).is_file():
            artifact_status = 'present'
            current_id = hash_file(Path(location))
        else:
            artifact_status = 'missing'
        checked = []
        for att in attestations:
            intact = _digest(_attestation_identity_fields(att)) \
                == att['record_digest'] \
                and _digest(att['result']) == att['result_digest']
            if not intact:
                status = 'record_tampered'
            elif artifact_status == 'missing':
                status = 'artifact_missing'
            elif current_id != artifact_id:
                status = 'artifact_mismatch'
            elif not att['result'].get('successful', False):
                status = 'suite_result_failed'
            else:
                status = 'valid'
            checked.append({**att, 'status': status})
        ok = registry_ok and artifact_status == 'present' \
            and current_id == artifact_id \
            and all(a['status'] == 'valid' for a in checked)
        return {
            'artifact': entry,
            'registry_status': 'ok' if registry_ok else 'record_tampered',
            'artifact_status': artifact_status,
            'current_artifact_id': current_id,
            'identity_match': current_id == artifact_id,
            'attestations': checked,
            'ok': ok,
        }

    # -- portability ---------------------------------------------------------

    def export(self, artifact_id: str) -> dict:
        """Export one artifact's entry + attestations as a single document.

        Carries only the artifact's own metadata and attestations: no
        recorded location and no other profile data.
        """
        self._check_id(artifact_id)
        with self._open() as store:
            row = self._load_artifact(store, artifact_id)
            if row is None:
                raise AttestationError(f'Unknown artifact: {artifact_id}')
            entry = self._artifact_public(row)
            attestations = self._load_attestations(store, artifact_id)
        artifact_block = _artifact_identity_fields(entry)
        artifact_block['record_digest'] = entry['record_digest']
        return {
            'format': EXPORT_FORMAT,
            'artifact': artifact_block,
            'attestations': attestations,
        }

    def import_document(self, doc) -> dict:
        """Import an exported document, verifying every digest on ingest.

        Any inconsistency rejects the whole document and imports
        nothing. The imported entry has no recorded location (paths
        are per-profile); registering the artifact's bytes in this
        profile afterwards binds a location to the same ID.
        """
        if not isinstance(doc, dict) or doc.get('format') != EXPORT_FORMAT:
            raise AttestationError('Not an artifact attestations export document')
        block = doc.get('artifact')
        atts = doc.get('attestations')
        if not isinstance(block, dict) or not isinstance(atts, list):
            raise AttestationError('Export document is malformed')
        try:
            artifact_id = self._check_id(block['artifact_id'])
            identity = {k: block[k] for k in
                        ('artifact_id', 'name', 'size', 'media_type',
                         'source', 'created_at')}
        except (KeyError, TypeError):
            raise AttestationError('Export document is malformed') from None
        if _digest(identity) != block.get('record_digest'):
            raise AttestationError(
                'Artifact record digest mismatch; document rejected')
        for att in atts:
            try:
                if att['artifact_id'] != artifact_id:
                    raise AttestationError(
                        'Attestation names a different artifact; '
                        'document rejected')
                if _digest(att['result']) != att['result_digest']:
                    raise AttestationError(
                        'Attestation result digest mismatch; '
                        'document rejected')
                if _digest(_attestation_identity_fields(att)) \
                        != att['record_digest']:
                    raise AttestationError(
                        'Attestation record digest mismatch; '
                        'document rejected')
            except (KeyError, TypeError):
                raise AttestationError(
                    'Export document is malformed') from None
        with self._open() as store:
            if self._load_artifact(store, artifact_id) is not None:
                raise AttestationError(
                    'Artifact is already registered in this profile; '
                    'document rejected')
            with store.db:
                store.db.execute(
                    'INSERT INTO artifacts (artifact_id,name,size,media_type,'
                    'source,location,created_at,record_digest)'
                    ' VALUES (?,?,?,?,?,NULL,?,?)',
                    (artifact_id, identity['name'], int(identity['size']),
                     identity['media_type'], identity['source'],
                     identity['created_at'], block['record_digest']))
                for att in atts:
                    store.db.execute(
                        'INSERT INTO artifact_attestations (id,artifact_id,'
                        'suite_name,suite_target,suite_fingerprint,result,'
                        'result_digest,environment,created_at,record_digest)'
                        ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                        (att['id'], att['artifact_id'], att['suite_name'],
                         att['suite_target'], att['suite_fingerprint'],
                         json.dumps(att['result'], sort_keys=True),
                         att['result_digest'],
                         json.dumps(att['environment'], sort_keys=True),
                         att['created_at'], att['record_digest']))
        entry = self.get(artifact_id)
        entry['imported_attestations'] = len(atts)
        return entry
