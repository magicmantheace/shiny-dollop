"""Owner CLI for contradiction candidates over approved memory (v0.3).

Detection proposes; only the owner adjudicates. ``list`` prints metadata
only (no record text, no fragments); ``show`` prints complete private
records and requires ``--confirm``; ``adjudicate`` changes at most one
record and also requires ``--confirm``. See docs/CONTRADICTION_REVIEW.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contradiction_review import (
    adjudicate_profile, list_profile, scan_profile, show_profile)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='athenz-contradiction-review',
        description='Deterministic contradiction candidates over approved '
                    'memory; explicit owner adjudication only')
    p.add_argument('--home', type=Path, default=None,
                   help='Existing private profile outside Git')
    sub = p.add_subparsers(dest='command', required=True)

    sub.add_parser('scan', help='run detection; stores new candidates only, '
                                'never changes a record')
    x = sub.add_parser('list', help='list candidates (metadata only)')
    x.add_argument('--state', default='actionable',
                   choices=('pending', 'deferred', 'actionable', 'confirmed',
                            'dismissed', 'all'))
    x.add_argument('--limit', type=int, default=80)
    x = sub.add_parser('show', help='show one candidate with complete PRIVATE records')
    x.add_argument('candidate_id', type=int)
    x.add_argument('--confirm', action='store_true',
                   help='required: the output contains private record text')
    x = sub.add_parser('adjudicate', help='apply one explicit owner decision')
    x.add_argument('candidate_id', type=int)
    x.add_argument('--action', required=True,
                   choices=('confirm', 'dismiss', 'defer'))
    x.add_argument('--keep', choices=('a', 'b', 'both'), default=None,
                   help='with --action confirm: which side stays approved')
    x.add_argument('--note', default='', help='optional owner note (max 1000 chars)')
    x.add_argument('--confirm', action='store_true',
                   help='required: adjudication is an explicit owner action')
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    if args.command == 'scan':
        result = scan_profile(args.home)
    elif args.command == 'list':
        result = list_profile(args.home, state=args.state, limit=args.limit)
    elif args.command == 'show':
        result = show_profile(args.home, args.candidate_id, confirmed=args.confirm)
    else:  # adjudicate
        resolution = None if args.keep is None else {
            'a': 'keep-a', 'b': 'keep-b', 'both': 'keep-both'}[args.keep]
        result = adjudicate_profile(
            args.home, args.candidate_id, action=args.action,
            resolution=resolution, note=args.note, confirmed=args.confirm)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
