"""Owner CLI for the promotion boundary (roadmap slice A5).

Wraps :mod:`athenz.task_promotion`. A proposal is prepared from a
succeeded slice A3 execution — directly (``--execution``) or through
its slice A4 operation item (``--operation`` + ``--item``) — and
records the candidate's full diff, the linked execution evidence, a
fresh full-suite regression run, the grant's state and a rollback
plan. Preparing and showing are read-only apart from that regression
run (slice A3's constrained runner, under grant authorization);
``prepare`` therefore needs no ``--confirm``.

The two writes are explicit owner actions and refuse without
``--confirm``: ``commit`` creates ONE local commit on the isolated
scratch branch containing exactly the proposal's diff, and
``discard`` removes the scratch worktree and deletes the scratch
branch. There is deliberately no subcommand that pushes, merges,
tags, releases, installs, deploys or updates AthenZ itself — landing
a candidate is a separate owner decision through the owner's own
route.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .task_executor import DEFAULT_COMMAND_TIMEOUT
from .task_promotion import PromotionError, TaskPromoter


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='athenz-task-promote',
        description='Prepare promotion proposals for succeeded task '
                    'executions, checkpoint-commit them locally on '
                    'their isolated scratch branches, or discard them '
                    '(slice A5)')
    p.add_argument('--home', type=Path, default=None)
    sub = p.add_subparsers(dest='command', required=True)

    x = sub.add_parser('prepare', help='build a proposal for a '
                                       'succeeded execution (runs a '
                                       'fresh full regression in the '
                                       'candidate worktree)')
    source = x.add_mutually_exclusive_group(required=True)
    source.add_argument('--execution', default=None,
                        help='execution id (slice A3)')
    source.add_argument('--operation', default=None,
                        help='operation id (slice A4); needs --item')
    x.add_argument('--item', default=None,
                   help='queue item id within --operation')
    x.add_argument('--command-timeout', type=int,
                   default=DEFAULT_COMMAND_TIMEOUT,
                   help='per-command timeout in seconds')

    x = sub.add_parser('show', help='print one proposal')
    x.add_argument('proposal_id')
    x = sub.add_parser('list', help='list proposals')
    x.add_argument('--execution', default=None,
                   help='only proposals for this execution id')

    x = sub.add_parser('commit', help='create the proposal\'s local '
                                      'checkpoint commit on its '
                                      'scratch branch (explicit owner '
                                      'action)')
    x.add_argument('proposal_id')
    x.add_argument('--confirm', action='store_true')

    x = sub.add_parser('discard', help='remove the candidate\'s '
                                       'scratch worktree and branch '
                                       '(explicit owner action)')
    x.add_argument('proposal_id', nargs='?', default=None)
    x.add_argument('--execution', default=None,
                   help='discard by execution id instead of proposal '
                        'id')
    x.add_argument('--confirm', action='store_true')
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    promoter = TaskPromoter(
        args.home,
        command_timeout=getattr(args, 'command_timeout',
                                DEFAULT_COMMAND_TIMEOUT))
    if args.command == 'prepare':
        result = promoter.prepare_proposal(
            args.execution, operation_id=args.operation,
            item_id=args.item)
    elif args.command == 'show':
        result = promoter.get_proposal(args.proposal_id)
        if result is None:
            raise PromotionError(
                f'No such proposal: {args.proposal_id}')
    elif args.command == 'list':
        result = promoter.list_proposals(args.execution)
    elif args.command == 'commit':
        if not args.confirm:
            raise PromotionError(
                'A checkpoint commit is an explicit owner action: '
                'pass --confirm')
        result = promoter.commit_checkpoint(args.proposal_id,
                                            confirmed=True)
    else:  # discard
        if not args.confirm:
            raise PromotionError(
                'Discarding a candidate is an explicit owner action: '
                'pass --confirm')
        if (args.proposal_id is None) == (args.execution is None):
            raise PromotionError(
                'Name exactly one of a proposal id or --execution')
        result = promoter.discard_candidate(
            args.proposal_id, execution_id=args.execution,
            confirmed=True)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
