"""Owner CLI for local connectors (v0.8 control plane).

Off by default: every integration starts ``not_opted_in`` (one
documented legacy exception — voice transcription, grandfathered from
its pre-registry owner validation) until the owner opts in here, per
tier, with ``--confirm``. Disabling needs no confirmation and takes
effect on the next gate check anywhere. See docs/LOCAL_CONNECTORS.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .local_connectors import LocalConnectorStore
from .local_notes import LocalNotes


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='athenz-connectors',
        description='Per-integration opt-in and disable controls for '
                    'local connectors; default is no integration enabled')
    p.add_argument('--home', type=Path, default=None)
    sub = p.add_subparsers(dest='command', required=True)

    sub.add_parser('list', help='integrations with state and approved tiers')
    x = sub.add_parser('show', help='one integration with state and config')
    x.add_argument('integration_id')
    x = sub.add_parser('opt-in', help='approve tiers (explicit owner action)')
    x.add_argument('integration_id')
    x.add_argument('--tier', action='append', required=True,
                   choices=('read', 'write'),
                   help='tier to approve (repeatable); approving read '
                        'never approves write')
    x.add_argument('--directory', default=None,
                   help='notes directory (local-notes opt-in)')
    x.add_argument('--confirm', action='store_true')
    x = sub.add_parser('disable',
                       help='disable immediately (no confirmation needed)')
    x.add_argument('integration_id')
    x = sub.add_parser('audit', help='recent gate and state events')
    x.add_argument('--integration', default=None,
                   help='only events for this integration')
    x.add_argument('--limit', type=int, default=100)

    notes = sub.add_parser('notes',
                           help='the local-notes reference connector')
    nsub = notes.add_subparsers(dest='notes_command', required=True)
    nsub.add_parser('list', help='list notes in the configured directory')
    x = nsub.add_parser('read', help='read one note')
    x.add_argument('name')
    x = nsub.add_parser('append',
                        help='create a NEW note (never overwrites)')
    x.add_argument('name')
    x.add_argument('--text', required=True)
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    store = LocalConnectorStore(args.home)
    if args.command == 'list':
        result = store.list()
    elif args.command == 'show':
        result = store.get(args.integration_id)
    elif args.command == 'opt-in':
        config = {'directory': args.directory} \
            if args.directory is not None else None
        result = store.opt_in(args.integration_id, tiers=args.tier,
                              config=config, confirmed=args.confirm)
    elif args.command == 'disable':
        result = store.disable(args.integration_id)
    elif args.command == 'audit':
        result = store.audit(args.integration, limit=args.limit)
    else:  # notes
        notes = LocalNotes(args.home)
        if args.notes_command == 'list':
            result = notes.list_notes()
        elif args.notes_command == 'read':
            result = notes.read_note(args.name)
        else:  # append
            result = notes.append_note(args.name, args.text)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
