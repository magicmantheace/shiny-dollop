"""Owner CLI for the isolated task executor (roadmap slice A3).

Runs ONE planner queue item under ONE standing grant through the
bounded edit/test feedback loop in :mod:`athenz.task_executor`.
Execution is an explicit owner action (``--confirm``); without it the
command refuses. There is no model editor in this slice: edits come
from an owner-supplied editor script (the deterministic
:class:`~athenz.task_executor.ScriptedEditor` format), which is also
what makes a run exactly rehearsed and reviewable in advance.

Editor script format (JSON)::

    {"attempts": [[{"path": "calc.py", "content": "..."}], ...]}

Each inner list is one attempt's edits (full-file replacements). An
optional top-level ``"blocked": "reason"`` makes the editor report
itself blocked instead. See docs/TASK_EXECUTOR.md.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .project_planner import SCHEMA as PLAN_SCHEMA
from .task_executor import (DEFAULT_COMMAND_TIMEOUT, EditorBlocked,
                            ExecutorError, ScriptedEditor, TaskExecutor)
from .task_grants import TaskGrantStore


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='athenz-task-executor',
        description='Execute one planner queue item under one standing '
                    'grant, in a disposable worktree, with a bounded '
                    'edit/test feedback loop (slice A3)')
    p.add_argument('--home', type=Path, default=None)
    sub = p.add_subparsers(dest='command', required=True)

    x = sub.add_parser('run', help='run one queue item (explicit owner action)')
    x.add_argument('--grant', required=True, help='grant id (slice A2)')
    x.add_argument('--plan', type=Path, required=True,
                   help='planner output JSON file (slice A1)')
    x.add_argument('--item', required=True, help='queue item id in the plan')
    x.add_argument('--editor-script', type=Path, required=True,
                   help='editor script JSON (see docs/TASK_EXECUTOR.md)')
    x.add_argument('--task-class', default='implement',
                   help='task class to authorize against the grant')
    x.add_argument('--test-module', action='append', default=[],
                   help='extra targeted unittest module (repeatable)')
    x.add_argument('--command-timeout', type=int,
                   default=DEFAULT_COMMAND_TIMEOUT,
                   help='per-command timeout in seconds')
    x.add_argument('--confirm', action='store_true')

    x = sub.add_parser('show-record', help='print one execution record')
    x.add_argument('execution_id')
    x = sub.add_parser('list-records', help='list execution records')
    x.add_argument('--grant', default=None,
                   help='only records under this grant id')
    return p


def _load_plan(path: Path) -> dict:
    try:
        plan = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutorError(f'Plan file is not valid JSON: {exc}') from exc
    if not isinstance(plan, dict) or plan.get('schema') != PLAN_SCHEMA \
            or not isinstance(plan.get('queue'), list):
        raise ExecutorError(f'Not a {PLAN_SCHEMA} plan file')
    return plan


def _load_editor(path: Path) -> ScriptedEditor:
    try:
        raw = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExecutorError(
            f'Editor script is not valid JSON: {exc}') from exc
    if not isinstance(raw, dict) or not set(raw) <= {'attempts', 'blocked'}:
        raise ExecutorError(
            'Editor script must be an object with "attempts" and/or '
            '"blocked"')
    steps = []
    if raw.get('blocked') is not None:
        if not isinstance(raw['blocked'], str) or not raw['blocked']:
            raise ExecutorError('Editor script "blocked" must be text')
        steps.append(EditorBlocked(raw['blocked']))
    attempts = raw.get('attempts', [])
    if not isinstance(attempts, list) \
            or not all(isinstance(a, list) for a in attempts):
        raise ExecutorError(
            'Editor script "attempts" must be a list of edit lists')
    steps.extend(attempts)
    if not steps:
        raise ExecutorError('Editor script contains no steps')
    return ScriptedEditor(steps)


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    executor = TaskExecutor(args.home,
                            command_timeout=getattr(
                                args, 'command_timeout',
                                DEFAULT_COMMAND_TIMEOUT))
    if args.command == 'show-record':
        result = executor.records.get(args.execution_id)
    elif args.command == 'list-records':
        result = executor.records.list(args.grant)
    else:  # run
        if not args.confirm:
            raise ExecutorError(
                'Execution is an explicit owner action: pass --confirm')
        grants = TaskGrantStore(args.home)
        grant = grants.get(args.grant)
        if grant is None:
            raise ExecutorError(f'No such grant: {args.grant}')
        plan = _load_plan(args.plan)
        planned_repo = (plan.get('generated_from') or {}).get('repo')
        if planned_repo is None or \
                Path(planned_repo).resolve() != \
                Path(grant['repository']).resolve():
            raise ExecutorError(
                'Plan was generated for a different repository than the '
                'grant authorizes')
        item = next((q for q in plan['queue'] if q.get('id') == args.item),
                    None)
        if item is None:
            raise ExecutorError(
                f'Queue item not in plan: {args.item}')
        editor = _load_editor(args.editor_script)
        result = executor.execute(args.grant, item, editor,
                                  task_class=args.task_class,
                                  extra_test_modules=args.test_module)
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
