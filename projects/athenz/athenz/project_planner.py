"""Read-only project planner (roadmap slice A1).

Given an *explicitly selected* Git repository, produce a bounded,
prioritized task queue as structured data. The planner is strictly
read-only with respect to the target repository:

- Git is invoked only with ``--no-optional-locks`` (and
  ``GIT_OPTIONAL_LOCKS=0``) and only for ``rev-parse`` / ``status``.
  Nothing is fetched, checked out, staged or written.
- The plan is printed to stdout or written to an owner-chosen output
  path that must lie *outside* the target repository; an output path
  inside the target is refused.

The planner never invents owner priorities. An item is *ranked* only
when the source carries an explicit ordering signal: a position in a
numbered list under a priority/critical-path heading, an explicit
``P0``-``P9`` marker in the item text, or an owner-supplied ``priority``
in the owner-approved issues file. Everything else is reported as
``priority: "unranked"`` and placed after all ranked items, in source
order. Dependencies are recorded only where the source states them
explicitly (a dependency phrase naming another item's label, or the
issues file's ``depends_on``); otherwise the list is empty.

This module proposes a queue. It executes nothing, grants nothing and
rewrites no roadmap — execution and standing authorization are slices
A3 and A2 respectively.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess

SCHEMA = 'athenz.project-plan/v1'
DEFAULT_MAX_ITEMS = 50
MAX_ISSUES = 200
MAX_FILE_BYTES = 2 * 1024 * 1024
UNSPECIFIED_CRITERIA = ('Unspecified in source — must be defined by the '
                        'owner before any execution.')
_ISSUE_FIELDS = {'id', 'title', 'priority', 'depends_on',
                 'success_criteria', 'scope', 'notes'}

_HEADING_RE = re.compile(r'^(#{1,6})\s+(.*?)\s*$')
_CHECKBOX_RE = re.compile(r'^\s*[-*]\s+\[([ xX])\]\s+(.*)$')
_NUMBERED_RE = re.compile(r'^\s*(\d+)[.)]\s+(.*)$')
_LIST_ITEM_RE = re.compile(r'^\s*(?:[-*]\s|\d+[.)]\s)')
_PRIORITY_HEADING_RE = re.compile(r'critical path|next steps|priorit',
                                  re.IGNORECASE)
_PRIORITY_MARKER_RE = re.compile(r'\bP([0-9])\b')
_LABEL_RE = re.compile(r'^\*{0,2}([A-Z]\d+|v\d+\.\d+)\b')
_DEPENDS_RE = re.compile(
    r'(?:depends on|dependent on|blocked by|requires)\s+'
    r'([A-Z]\d+|v\d+\.\d+|#\d+|[A-Za-z][\w-]*)', re.IGNORECASE)
_GATE_RE = re.compile(r'(?:acceptance gate|success criteria)\s*[:—-]\s*(.+)',
                      re.IGNORECASE)
_PATH_RE = re.compile(
    r'(?<![\w/.-])([\w][\w.-]*(?:/[\w.-]+)+|[\w][\w.-]*\.'
    r'(?:py|md|toml|json|cfg|txt|sh|rs|js|ts))(?![\w/.-])')
_HIGH_RISK = ('migration', 'delete', 'erase', 'security', 'credential',
              'auth', 'network', 'push', 'merge', 'release', 'deploy',
              'training', 'permission', 'sandbox')
_LOW_RISK = ('documentation', 'docs', 'typo', 'rename', 'comment only')


class PlannerError(ValueError):
    """The planner cannot produce a plan within its read-only bounds."""


def _git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')
    try:
        proc = subprocess.run(
            ['git', '--no-optional-locks', '-C', str(repo), *args],
            capture_output=True, text=True, timeout=30, env=env)
    except (OSError, subprocess.SubprocessError) as exc:
        raise PlannerError(f'git invocation failed: {exc}') from exc
    if proc.returncode != 0:
        raise PlannerError(
            f'git {" ".join(args)} failed: {proc.stderr.strip()}')
    return proc.stdout.strip()


def inspect_repo(repo: Path) -> dict:
    """Verify *repo* is a Git repository; record HEAD/branch read-only."""
    repo = Path(repo)
    if not repo.is_dir():
        raise PlannerError(f'Target is not a directory: {repo}')
    try:
        _git(repo, 'rev-parse', '--git-dir')
    except PlannerError:
        raise PlannerError(f'Target is not a Git repository: {repo}')
    root = Path(_git(repo, 'rev-parse', '--show-toplevel')).resolve()
    head = _git(repo, 'rev-parse', '--verify', 'HEAD')
    if not head:
        raise PlannerError('Target repository has no commits yet')
    branch = _git(repo, 'rev-parse', '--abbrev-ref', 'HEAD')
    status = _git(repo, 'status', '--porcelain')
    tests_dir = root / 'tests'
    test_files = (sum(1 for p in tests_dir.rglob('test_*.py')
                      if p.is_file()) if tests_dir.is_dir() else 0)
    return {
        'repo': str(root),
        'head': head,
        'branch': None if branch == 'HEAD' else branch,
        'detached_head': branch == 'HEAD',
        'working_tree_dirty': bool(status),
        'test_file_count': test_files,
    }


def _clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text.replace('**', '')).strip()


def _risk(text: str) -> dict:
    low = text.casefold()
    high = [w for w in _HIGH_RISK if w in low]
    if high:
        return {'level': 'high',
                'rationale': 'Source mentions: ' + ', '.join(high)}
    low_hits = [w for w in _LOW_RISK if w in low]
    if low_hits:
        return {'level': 'low',
                'rationale': 'Documentation-only signals: '
                             + ', '.join(low_hits)}
    return {'level': 'medium',
            'rationale': 'No explicit risk signals in source text'}


def _scope(text: str, section: str) -> list[str]:
    found = sorted(set(_PATH_RE.findall(text)))
    if found:
        return found
    return [f'section: {section}'] if section else []


def _criteria(text: str) -> str:
    match = _GATE_RE.search(text)
    if match:
        return _clean(match.group(1))
    return UNSPECIFIED_CRITERIA


def parse_roadmap(text: str) -> list[dict]:
    """Extract candidate tasks from ROADMAP.md source text.

    Sources: unchecked checkbox items anywhere, and numbered items
    under a priority/critical-path heading (their number is an explicit
    ordering signal). Completed (checked) items are counted, not queued.
    """
    items: list[dict] = []
    completed = 0
    section = ''
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        heading = _HEADING_RE.match(line)
        if heading:
            section = _clean(heading.group(2))
            i += 1
            continue
        checkbox = _CHECKBOX_RE.match(line)
        numbered = _NUMBERED_RE.match(line) if not checkbox else None
        if checkbox and checkbox.group(1) in 'xX':
            completed += 1
            i += 1
            continue
        if not checkbox and not (numbered and _PRIORITY_HEADING_RE.search(section)):
            i += 1
            continue
        start = i
        body = (checkbox or numbered).group(2)
        j = i + 1
        while j < len(lines):
            nxt = lines[j]
            if (not nxt.strip() or _HEADING_RE.match(nxt)
                    or _LIST_ITEM_RE.match(nxt)):
                break
            if nxt[:1] in (' ', '\t'):
                body += ' ' + nxt.strip()
                j += 1
            else:
                break
        i = j
        body = _clean(body)
        title = body
        prefix, sep, _ = body.partition(': ')
        if sep and len(prefix) <= 90:
            title = prefix
        elif '. ' in body:
            title = body.split('. ')[0].strip()
        item = {
            'title': title,
            'detail': body,
            'section': section,
            'line': start + 1,
        }
        marker = _PRIORITY_MARKER_RE.search(body)
        if numbered:
            item['rank'] = int(numbered.group(1))
            item['priority_basis'] = (
                f'numbered position {numbered.group(1)} in section '
                f'"{section}"')
        elif marker:
            item['rank'] = int(marker.group(1))
            item['priority_basis'] = f'explicit marker P{marker.group(1)}'
        else:
            item['rank'] = None
            item['priority_basis'] = 'none — unranked'
        label = _LABEL_RE.match(body)
        item['label'] = label.group(1) if label else None
        if numbered and item['label'] is None:
            item['label'] = f"#{numbered.group(1)}"
        items.append(item)
    for item in items:
        item['completed_excluded'] = completed
    return items


def load_issues(path: Path) -> list[dict]:
    """Parse and schema-validate the owner-approved issues file."""
    path = Path(path)
    if not path.is_file():
        raise PlannerError(f'Issues file is missing: {path}')
    if path.stat().st_size > MAX_FILE_BYTES:
        raise PlannerError('Issues file is too large')
    try:
        raw = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PlannerError(f'Issues file is not valid JSON: {exc}') from exc
    if not isinstance(raw, dict) or set(raw) != {'issues'} \
            or not isinstance(raw['issues'], list):
        raise PlannerError('Issues file must be an object with one '
                           '"issues" array')
    if len(raw['issues']) > MAX_ISSUES:
        raise PlannerError(f'Issues file exceeds {MAX_ISSUES} issues')
    issues = []
    seen = set()
    for index, entry in enumerate(raw['issues']):
        if not isinstance(entry, dict) or not set(entry) <= _ISSUE_FIELDS:
            raise PlannerError(f'issue {index}: malformed issue object')
        issue_id = entry.get('id')
        title = entry.get('title')
        if not isinstance(issue_id, str) or not issue_id.strip() \
                or not isinstance(title, str) or not title.strip():
            raise PlannerError(f'issue {index}: id and title are required')
        if issue_id in seen:
            raise PlannerError(f'issue {index}: duplicate id {issue_id!r}')
        seen.add(issue_id)
        priority = entry.get('priority')
        if priority is not None and (not isinstance(priority, int)
                                     or isinstance(priority, bool)
                                     or priority < 0):
            raise PlannerError(f'issue {index}: priority must be a '
                               'non-negative integer')
        depends = entry.get('depends_on', [])
        if not isinstance(depends, list) \
                or not all(isinstance(d, str) for d in depends):
            raise PlannerError(f'issue {index}: depends_on must be a '
                               'list of item ids')
        scope = entry.get('scope', [])
        if not isinstance(scope, list) \
                or not all(isinstance(s, str) for s in scope):
            raise PlannerError(f'issue {index}: scope must be a list of '
                               'strings')
        for field in ('success_criteria', 'notes'):
            if field in entry and not isinstance(entry[field], str):
                raise PlannerError(f'issue {index}: {field} must be a '
                                   'string')
        issues.append({
            'id': issue_id, 'title': title, 'rank': priority,
            'depends_on': depends, 'scope': scope,
            'success_criteria': entry.get('success_criteria'),
            'detail': entry.get('notes', ''),
        })
    return issues


def build_plan(repo: Path, max_items: int = DEFAULT_MAX_ITEMS,
               issues_file: Path | None = None) -> dict:
    """Build the bounded task queue for the repository at *repo*."""
    if not isinstance(max_items, int) or max_items < 1:
        raise PlannerError('max_items must be a positive integer')
    info = inspect_repo(repo)
    root = Path(info['repo'])
    candidates: list[dict] = []
    completed = 0
    roadmap_path = root / 'ROADMAP.md'
    roadmap_found = roadmap_path.is_file()
    if roadmap_found:
        parsed = parse_roadmap(roadmap_path.read_text(encoding='utf-8'))
        if parsed:
            completed = parsed[0]['completed_excluded']
        for seq, raw_item in enumerate(parsed, start=1):
            candidates.append({
                'id': f'roadmap-{seq}',
                'title': raw_item['title'],
                'detail': raw_item['detail'],
                'label': raw_item['label'],
                'rank': raw_item['rank'],
                'priority_basis': raw_item['priority_basis'],
                'source': {'file': 'ROADMAP.md', 'line': raw_item['line'],
                           'section': raw_item['section']},
                'section': raw_item['section'],
                'declared_deps': [],
            })
    if issues_file is not None:
        for issue in load_issues(issues_file):
            candidates.append({
                'id': issue['id'],
                'title': issue['title'],
                'detail': issue['detail'],
                'label': issue['id'],
                'rank': issue['rank'],
                'priority_basis': ('owner-supplied priority in issues file'
                                   if issue['rank'] is not None
                                   else 'none — unranked'),
                'source': {'file': str(issues_file), 'line': None,
                           'section': 'owner-approved issues'},
                'section': 'owner-approved issues',
                'declared_deps': issue['depends_on'],
                'owner_scope': issue['scope'],
                'owner_criteria': issue['success_criteria'],
            })
    by_label = {c['label']: c['id'] for c in candidates if c['label']}
    by_id = {c['id'] for c in candidates}
    queue = []
    for cand in candidates:
        deps = set()
        for dep in cand['declared_deps']:
            if dep in by_id and dep != cand['id']:
                deps.add(dep)
        for match in _DEPENDS_RE.finditer(cand['detail']):
            token = match.group(1)
            target = by_label.get(token) or by_label.get(token.upper())
            if target and target != cand['id']:
                deps.add(target)
        queue.append({
            'id': cand['id'],
            'title': cand['title'],
            'source': cand['source'],
            'priority': cand['rank'] if cand['rank'] is not None
                        else 'unranked',
            'priority_basis': cand['priority_basis'],
            'dependencies': sorted(deps),
            'success_criteria': cand.get('owner_criteria')
                                or _criteria(cand['detail']),
            'risk': _risk(cand['detail'] + ' ' + cand['title']),
            'scope': cand.get('owner_scope')
                     or _scope(cand['detail'], cand['section']),
        })
    ranked = sorted((q for q in queue if q['priority'] != 'unranked'),
                    key=lambda q: q['priority'])
    unranked = [q for q in queue if q['priority'] == 'unranked']
    ordered = ranked + unranked
    total = len(ordered)
    return {
        'schema': SCHEMA,
        'read_only': True,
        'generated_from': {
            **info,
            'roadmap_found': roadmap_found,
            'issues_file': str(issues_file) if issues_file else None,
        },
        'max_items': max_items,
        'total_candidates': total,
        'completed_items_excluded': completed,
        'truncated': total > max_items,
        'queue': ordered[:max_items],
    }


def write_plan(plan: dict, out: Path, repo_root: Path) -> Path:
    """Write *plan* to *out*, refusing any path inside the target repo."""
    out = Path(out)
    resolved = out.resolve()
    root = Path(repo_root).resolve()
    if resolved == root or root in resolved.parents:
        raise PlannerError(
            'Output path lies inside the target repository; the planner '
            'never writes into the repo it inspects')
    if not resolved.parent.is_dir():
        raise PlannerError(f'Output directory does not exist: '
                           f'{resolved.parent}')
    resolved.write_text(json.dumps(plan, indent=2, sort_keys=True) + '\n',
                        encoding='utf-8')
    return resolved


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description='Read-only project planner: propose a bounded, '
                    'prioritized task queue for an explicitly selected '
                    'Git repository (slice A1; executes nothing)')
    parser.add_argument('--repo', type=Path, required=True,
                        help='Path to the target Git repository (read-only)')
    parser.add_argument('--max-items', type=int, default=DEFAULT_MAX_ITEMS,
                        help=f'Maximum queue length (default '
                             f'{DEFAULT_MAX_ITEMS})')
    parser.add_argument('--issues-file', type=Path, default=None,
                        help='Optional owner-approved issues JSON file')
    parser.add_argument('--out', type=Path, default=None,
                        help='Write the plan JSON here (must be outside '
                             'the target repo); default: stdout')
    args = parser.parse_args(argv)
    try:
        plan = build_plan(args.repo, max_items=args.max_items,
                          issues_file=args.issues_file)
        if args.out is not None:
            written = write_plan(plan, args.out,
                                 Path(plan['generated_from']['repo']))
            print(json.dumps({'written': str(written),
                              'queue_length': len(plan['queue']),
                              'total_candidates':
                                  plan['total_candidates']},
                             sort_keys=True))
        else:
            print(json.dumps(plan, indent=2, sort_keys=True))
    except PlannerError as exc:
        parser.error(str(exc))


if __name__ == '__main__':
    main()
