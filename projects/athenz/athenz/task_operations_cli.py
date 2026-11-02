"""Owner CLI for durable operations (roadmap slice A4).

Wraps :mod:`athenz.task_operations`: an operation runs an ordered
list of planner queue items under one standing grant, checkpointing
per-item state in the private profile so it can be paused, inspected
and resumed across process restarts.

Starting and resuming are explicit owner actions (``--confirm``).
Editors are supplied exactly as in slice A3 -- owner-written editor
scripts -- either one script applied to every item (``--editor-script``)
or one per item (``--editor-script-for ITEM=PATH``). The editor
fingerprint recorded in the operation is a hash of the script files'
contents unless ``--editor-fingerprint`` overrides it; on resume the
recomputed fingerprint must match the recorded one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .task_executor import ScriptedEditor
from .task_executor_cli import _load_editor, _load_plan
from .task_operations import (DEFAULT_STALL_THRESHOLD, OperationError,
                              TaskOperationDriver)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog='athenz-task-operations',
        description='Run and resume durable multi-item operations '
                    'under one standing grant (slice A4)')
    p.add_argument('--home', type=Path, default=None)
    sub = p.add_subparsers(dest='command', required=True)

    def editor_args(x):
        x.add_argument('--editor-script', type=Path, default=None,
                       help='editor script applied to every item')
        x.add_argument('--editor-script-for', action='append', default=[],
                       metavar='ITEM=PATH',
                       help='editor script for one queue item (repeatable)')
        x.add_argument('--model-fingerprint', default='scripted/no-model',
                       help='opaque model fingerprint recorded/compared')
        x.add_argument('--editor-fingerprint', default=None,
                       help='opaque editor fingerprint (default: hash '
                            'of the editor script contents)')
        x.add_argument('--max-items', type=int, default=None,
                       help='execute at most this many items in this call')

    x = sub.add_parser('start', help='create and drive an operation '
                                     '(explicit owner action)')
    x.add_argument('--grant', required=True, help='grant id (slice A2)')
    x.add_argument('--plan', type=Path, required=True,
                   help='planner output JSON file (slice A1)')
    x.add_argument('--item', action='append', default=[],
                   help='queue item id to include (repeatable; default: '
                        'the whole queue, in plan order)')
    x.add_argument('--task-class', default='implement')
    x.add_argument('--test-module', action='append', default=[])
    x.add_argument('--command-timeout', type=int, default=120)
    x.add_argument('--stall-threshold', type=int,
                   default=DEFAULT_STALL_THRESHOLD)
    editor_args(x)
    x.add_argument('--confirm', action='store_true')

    x = sub.add_parser('resume', help='verify and continue an operation '
                                      '(explicit owner action)')
    x.add_argument('operation_id')
    x.add_argument('--retry-suspect', action='store_true',
                   help='owner decision: retry an item left suspect by '
                        'a mid-item interruption')
    x.add_argument('--command-timeout', type=int, default=120)
    editor_args(x)
    x.add_argument('--confirm', action='store_true')

    x = sub.add_parser('pause', help='pause an operation (immediate)')
    x.add_argument('operation_id')
    x = sub.add_parser('abort', help='abort an operation; pending items '
                                     'are marked skipped')
    x.add_argument('operation_id')
    x = sub.add_parser('list', help='list operations')
    x.add_argument('--grant', default=None)
    x = sub.add_parser('show', help='show one operation with its '
                                    'attempted/changed/tested/blocked/'
                                    'unfinished inspection')
    x.add_argument('operation_id')
    return p


def _editor_paths(args) -> dict:
    paths = {}
    for spec in getattr(args, 'editor_script_for', []) or []:
        item_id, sep, path = spec.partition('=')
        if not sep or not item_id or not path:
            raise OperationError(
                f'--editor-script-for wants ITEM=PATH, got {spec!r}')
        paths[item_id] = Path(path)
    return paths


def _editor_fingerprint(args, paths: dict) -> str:
    if getattr(args, 'editor_fingerprint', None):
        return args.editor_fingerprint
    digests = {}
    if getattr(args, 'editor_script', None) is not None:
        digests['*'] = hashlib.sha256(
            Path(args.editor_script).read_bytes()).hexdigest()
    for item_id, path in sorted(paths.items()):
        digests[item_id] = hashlib.sha256(
            Path(path).read_bytes()).hexdigest()
    if not digests:
        return 'no-editor-supplied'
    payload = json.dumps(digests, sort_keys=True)
    return 'scripts:' + hashlib.sha256(payload.encode()).hexdigest()


def _editor_factory(args, paths: dict):
    global_path = getattr(args, 'editor_script', None)

    def factory(item: dict) -> ScriptedEditor:
        path = paths.get(item['id'], global_path)
        if path is None:
            raise OperationError(
                f"No editor script supplied for item {item['id']}")
        return _load_editor(path)

    return factory


def main(argv: list[str] | None = None) -> None:
    args = parser().parse_args(argv)
    driver = TaskOperationDriver(
        args.home,
        command_timeout=getattr(args, 'command_timeout', 120))
    if args.command == 'list':
        result = driver.list_operations(args.grant)
    elif args.command == 'show':
        result = driver.inspect_operation(args.operation_id)
    elif args.command == 'pause':
        result = driver.pause_operation(args.operation_id)
    elif args.command == 'abort':
        result = driver.abort_operation(args.operation_id)
    elif args.command == 'start':
        if not args.confirm:
            raise OperationError(
                'Starting an operation is an explicit owner action: '
                'pass --confirm')
        plan = _load_plan(args.plan)
        paths = _editor_paths(args)
        selected = args.item or [q['id'] for q in plan['queue']]
        for item_id in selected:
            if item_id not in paths and args.editor_script is None:
                raise OperationError(
                    f'No editor script supplied for item {item_id}')
        result = driver.start_operation(
            plan, args.grant, _editor_factory(args, paths),
            item_ids=args.item or None, task_class=args.task_class,
            extra_test_modules=args.test_module,
            model_fingerprint=args.model_fingerprint,
            editor_fingerprint=_editor_fingerprint(args, paths),
            stall_threshold=args.stall_threshold,
            max_items=args.max_items)
    else:  # resume
        if not args.confirm:
            raise OperationError(
                'Resuming an operation is an explicit owner action: '
                'pass --confirm')
        paths = _editor_paths(args)
        result = driver.resume_operation(
            args.operation_id, _editor_factory(args, paths),
            max_items=args.max_items, retry_suspect=args.retry_suspect,
            model_fingerprint=args.model_fingerprint,
            editor_fingerprint=_editor_fingerprint(args, paths))
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
