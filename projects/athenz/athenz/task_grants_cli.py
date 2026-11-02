"""Owner CLI for standing task grants (roadmap slice A2).

Off by default: nothing is authorized until the owner creates a grant
here with explicit scope flags and ``--confirm``. See
docs/TASK_GRANTS.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .task_grants import TaskGrantStore


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='athenz-task-grants',
        description='Owner-reviewed standing authorization for coding tasks; '
                    'default is no authorization')
    p.add_argument('--home', type=Path, default=None)
    sub = p.add_subparsers(dest='command', required=True)

    x = sub.add_parser('create', help='create a grant (explicit owner action)')
    x.add_argument('--objective', required=True,
                   help='what this grant authorizes work toward')
    x.add_argument('--repo', required=True, help='repository the grant is scoped to')
    x.add_argument('--worktree', default=None,
                   help='worktree the grant is scoped to (default: the repository)')
    x.add_argument('--queue-item', action='append', default=[],
                   help='planner queue item id this grant was reviewed against')
    x.add_argument('--task-class', action='append', required=True,
                   help='permitted task class (repeatable)')
    x.add_argument('--allow-file', action='append', required=True,
                   help='allowed file glob, repository-relative (repeatable)')
    x.add_argument('--tool', action='append', required=True,
                   help='permitted tool (repeatable)')
    x.add_argument('--network-policy', choices=('none', 'allowlist'),
                   default='none')
    x.add_argument('--network-allow', action='append', default=[],
                   help='allowed host for the allowlist policy (repeatable)')
    x.add_argument('--max-tasks', type=int, required=True)
    x.add_argument('--max-test-runs', type=int, required=True)
    x.add_argument('--max-retries', type=int, required=True,
                   help='max retries per task')
    x.add_argument('--max-wall-clock', type=int, required=True,
                   help='max total wall-clock seconds across the grant')
    x.add_argument('--duration-hours', type=int, required=True,
                   help='grant lifetime in hours, after which it expires')
    x.add_argument('--confirm', action='store_true')

    sub.add_parser('list')
    x = sub.add_parser('show'); x.add_argument('grant_id')
    x = sub.add_parser('pause'); x.add_argument('grant_id')
    x = sub.add_parser('resume'); x.add_argument('grant_id')
    x.add_argument('--confirm', action='store_true')
    x = sub.add_parser('revoke'); x.add_argument('grant_id')
    x.add_argument('--confirm', action='store_true')
    x = sub.add_parser('audit'); x.add_argument('grant_id')
    return p


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    store = TaskGrantStore(args.home)
    if args.command == 'create':
        result = store.create(
            objective=args.objective, repository=args.repo,
            worktree=args.worktree, queue_item_ids=args.queue_item,
            task_classes=args.task_class, allowed_files=args.allow_file,
            permitted_tools=args.tool, network_policy=args.network_policy,
            network_allowlist=args.network_allow, max_tasks=args.max_tasks,
            max_test_runs=args.max_test_runs,
            max_retries_per_task=args.max_retries,
            max_wall_clock_seconds=args.max_wall_clock,
            duration_seconds=args.duration_hours * 3600,
            confirmed=args.confirm)
    elif args.command == 'list':
        result = store.list()
    elif args.command == 'show':
        result = store.get(args.grant_id)
    elif args.command == 'pause':
        result = store.pause(args.grant_id)
    elif args.command == 'resume':
        result = store.resume(args.grant_id, confirmed=args.confirm)
    elif args.command == 'revoke':
        result = store.revoke(args.grant_id, confirmed=args.confirm)
    else:  # audit
        result = store.audit(args.grant_id)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
