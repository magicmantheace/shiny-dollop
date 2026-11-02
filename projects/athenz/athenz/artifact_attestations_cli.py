"""Owner CLI for verified artifact IDs and test attestations (v0.3).

Attestations are issued only for suite runs this CLI performs itself
(``athenz-artifact-attestations attest`` runs ``unittest discover``
in a subprocess and records the real result), so a recorded result
cannot be a hand-typed claim. See docs/ARTIFACT_ATTESTATIONS.md.
"""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
import platform
import sys
import time
import unittest

from .artifact_attestations import (
    DEFAULT_PATTERN, DEFAULT_TIMEOUT_SECONDS, MAX_FAILED_TEST_IDS,
    ArtifactAttestationStore,
)


def _run_suite_in_process(suite_dir: str, pattern: str) -> dict:
    """Discover and run a suite here (the subprocess child's job).

    Prints nothing; returns the payload the parent records. The
    environment fingerprint is captured from THIS runtime — the one
    that actually executed the tests.
    """
    start_dir = str(Path(suite_dir).resolve())
    if start_dir not in sys.path:
        sys.path.insert(0, start_dir)
    loader = unittest.TestLoader()
    suite = loader.discover(start_dir, pattern=pattern, top_level_dir=start_dir)
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=0)
    started = time.monotonic()
    result = runner.run(suite)
    duration = round(time.monotonic() - started, 3)
    failed_ids = sorted({str(t) for t, _ in
                         list(result.failures) + list(result.errors)})
    payload_result = {
        'tests_run': result.testsRun,
        'passed': result.testsRun - len(result.failures)
                  - len(result.errors) - len(result.skipped),
        'failures': len(result.failures),
        'errors': len(result.errors),
        'failed': len(result.failures) + len(result.errors),
        'skipped': len(result.skipped),
        'successful': bool(result.wasSuccessful()),
        'failed_test_ids': failed_ids[:MAX_FAILED_TEST_IDS],
        'failed_test_ids_truncated': len(failed_ids) > MAX_FAILED_TEST_IDS,
        'duration_seconds': duration,
    }
    environment = {
        'platform': platform.platform(),
        'python_implementation': platform.python_implementation(),
        'python_version': platform.python_version(),
        'machine': platform.machine(),
    }
    return {'result': payload_result, 'environment': environment}


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='athenz-artifact-attestations',
        description='Verified artifact IDs (SHA-256 of exact bytes) and '
                    'reproducible test attestations recorded from real '
                    'suite runs performed by this tool')
    p.add_argument('--home', type=Path, default=None)
    sub = p.add_subparsers(dest='command', required=True)

    x = sub.add_parser('register',
                       help='register a file under its SHA-256 artifact ID')
    x.add_argument('--path', required=True, help='file to register')
    x.add_argument('--name', default=None,
                   help='display name (default: the file name)')
    x.add_argument('--source', default='',
                   help='where this artifact came from (owner note)')

    x = sub.add_parser('attest',
                       help='run a unittest suite now and record its real '
                            'result against a registered artifact')
    x.add_argument('--artifact', required=True, help='artifact ID')
    x.add_argument('--suite-dir', required=True,
                   help='directory unittest discovery runs against')
    x.add_argument('--pattern', default=DEFAULT_PATTERN,
                   help='discovery pattern (default: test*.py)')
    x.add_argument('--timeout', type=int, default=DEFAULT_TIMEOUT_SECONDS,
                   help='suite run timeout in seconds')

    x = sub.add_parser('verify',
                       help='recompute the artifact hash and every record '
                            'digest; trust nothing stored')
    x.add_argument('artifact_id')

    sub.add_parser('list', help='list registered artifacts')

    x = sub.add_parser('export',
                       help='export one artifact + its attestations as JSON')
    x.add_argument('artifact_id')
    x.add_argument('--out', type=Path, default=None,
                   help='write the document here instead of stdout')

    x = sub.add_parser('import',
                       help='import an exported document, verifying every '
                            'digest on ingest')
    x.add_argument('--file', required=True, type=Path,
                   help='export document to import')

    x = sub.add_parser('_run-suite', help=argparse.SUPPRESS)
    x.add_argument('--suite-dir', required=True)
    x.add_argument('--pattern', default=DEFAULT_PATTERN)
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    if args.command == '_run-suite':
        payload = _run_suite_in_process(args.suite_dir, args.pattern)
        print(json.dumps(payload, sort_keys=True))
        return
    store = ArtifactAttestationStore(args.home)
    if args.command == 'register':
        result = store.register(args.path, name=args.name, source=args.source)
    elif args.command == 'attest':
        result = store.attest(args.artifact, args.suite_dir,
                              pattern=args.pattern, timeout=args.timeout)
    elif args.command == 'verify':
        result = store.verify(args.artifact_id)
    elif args.command == 'list':
        result = store.list()
    elif args.command == 'export':
        result = store.export(args.artifact_id)
        if args.out is not None:
            args.out.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + '\n',
                encoding='utf-8')
            print(json.dumps({'written': str(args.out),
                              'artifact_id': args.artifact_id},
                             indent=2, ensure_ascii=False))
            return
    else:  # import
        doc = json.loads(args.file.read_text(encoding='utf-8'))
        result = store.import_document(doc)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
