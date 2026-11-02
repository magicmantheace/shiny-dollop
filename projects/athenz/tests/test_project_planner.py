"""Synthetic project planner tests (slice A1). Fixture repos only."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from athenz.project_planner import (PlannerError, build_plan, load_issues,
                                    main, parse_roadmap)

ROADMAP = """# Fixture Roadmap

## Next critical path
1. Build the widget loader for athenz/widget.py
2. Harden the widget loader (depends on #1)

## Backlog
- [ ] **A1 — Read-only project planner:** inspect a selected repository
  and propose a queue.
- [ ] **A2 — Standing grants:** narrow authorization. Blocked by A1.
- [x] **A0 — Already done:** shipped last week.
- [ ] Write documentation for the planner in docs/PROJECT_PLANNER.md
- [ ] P2 Tidy the fixture labels
"""


def _git(repo: Path, *args: str) -> None:
    env = dict(os.environ, GIT_AUTHOR_NAME='Fixture',
               GIT_AUTHOR_EMAIL='fixture@example.invalid',
               GIT_COMMITTER_NAME='Fixture',
               GIT_COMMITTER_EMAIL='fixture@example.invalid')
    subprocess.run(['git', '-C', str(repo), *args], check=True,
                   capture_output=True, text=True, env=env)


def make_repo(base: Path, roadmap: str = ROADMAP) -> Path:
    repo = base / 'fixture-repo'
    repo.mkdir()
    _git(repo, 'init', '-q')
    (repo / 'ROADMAP.md').write_text(roadmap, encoding='utf-8')
    tests = repo / 'tests'
    tests.mkdir()
    (tests / 'test_fixture.py').write_text('# synthetic\n', encoding='utf-8')
    _git(repo, 'add', '-A')
    _git(repo, 'commit', '-q', '-m', 'fixture')
    return repo


def tree_snapshot(repo: Path) -> dict:
    """HEAD, porcelain status and content hashes of every non-.git file."""
    env = dict(os.environ, GIT_OPTIONAL_LOCKS='0')

    def run(*args):
        return subprocess.run(['git', '--no-optional-locks', '-C',
                               str(repo), *args], capture_output=True,
                              text=True, env=env).stdout
    files = {}
    for path in sorted(repo.rglob('*')):
        if path.is_file() and '.git' not in path.parts:
            files[str(path.relative_to(repo))] = hashlib.sha256(
                path.read_bytes()).hexdigest()
    index = repo / '.git' / 'index'
    return {
        'head': run('rev-parse', 'HEAD').strip(),
        'status': run('status', '--porcelain'),
        'files': files,
        'mtimes': {rel: (repo / rel).stat().st_mtime_ns for rel in files},
        'index_sha': hashlib.sha256(index.read_bytes()).hexdigest()
                     if index.is_file() else None,
    }


class ProjectPlannerTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.repo = make_repo(self.base)

    def test_queue_extraction_from_fixture_roadmap(self):
        plan = build_plan(self.repo)
        self.assertEqual(plan['schema'], 'athenz.project-plan/v1')
        self.assertTrue(plan['read_only'])
        titles = [q['title'] for q in plan['queue']]
        self.assertIn('A1 — Read-only project planner', titles)
        self.assertIn('Build the widget loader for athenz/widget.py', titles)
        self.assertEqual(plan['completed_items_excluded'], 1)
        self.assertNotIn('A0 — Already done', ' '.join(titles))
        info = plan['generated_from']
        self.assertEqual(info['test_file_count'], 1)
        self.assertTrue(info['roadmap_found'])
        self.assertEqual(len(info['head']), 40)
        a1 = next(q for q in plan['queue']
                  if q['title'].startswith('A1'))
        self.assertEqual(a1['source']['file'], 'ROADMAP.md')
        self.assertEqual(a1['source']['section'], 'Backlog')
        self.assertGreaterEqual(a1['source']['line'], 1)

    def test_numbered_items_ranked_unranked_after(self):
        plan = build_plan(self.repo)
        queue = plan['queue']
        self.assertEqual(queue[0]['priority'], 1)
        self.assertEqual(queue[1]['priority'], 2)
        self.assertIn('numbered position', queue[0]['priority_basis'])
        unranked = [q for q in queue if q['priority'] == 'unranked']
        self.assertTrue(unranked)
        self.assertTrue(all(queue.index(q) >= 3 for q in unranked))
        a1 = next(q for q in queue if q['title'].startswith('A1'))
        self.assertEqual(a1['priority'], 'unranked')

    def test_explicit_priority_marker_ranks_item(self):
        plan = build_plan(self.repo)
        tidy = next(q for q in plan['queue']
                    if q['title'].startswith('P2 Tidy'))
        self.assertEqual(tidy['priority'], 2)
        self.assertIn('P2', tidy['priority_basis'])

    def test_dependency_extraction(self):
        plan = build_plan(self.repo)
        harden = next(q for q in plan['queue']
                      if q['title'].startswith('Harden the widget'))
        loader = next(q for q in plan['queue']
                      if q['title'].startswith('Build the widget'))
        self.assertEqual(harden['dependencies'], [loader['id']])
        a2 = next(q for q in plan['queue'] if q['title'].startswith('A2'))
        a1 = next(q for q in plan['queue'] if q['title'].startswith('A1'))
        self.assertEqual(a2['dependencies'], [a1['id']])
        self.assertEqual(loader['dependencies'], [])

    def test_scope_and_criteria_defaults_from_source_only(self):
        plan = build_plan(self.repo)
        loader = next(q for q in plan['queue']
                      if q['title'].startswith('Build the widget'))
        self.assertIn('athenz/widget.py', loader['scope'])
        self.assertTrue(loader['success_criteria'].startswith(
            'Unspecified in source'))
        docs = next(q for q in plan['queue']
                    if q['title'].startswith('Write documentation'))
        self.assertEqual(docs['risk']['level'], 'low')
        self.assertIn('docs/PROJECT_PLANNER.md', docs['scope'])

    def test_bounded_queue_and_truncation_flag(self):
        plan = build_plan(self.repo, max_items=2)
        self.assertEqual(len(plan['queue']), 2)
        self.assertTrue(plan['truncated'])
        self.assertGreater(plan['total_candidates'], 2)
        with self.assertRaises(PlannerError):
            build_plan(self.repo, max_items=0)

    def test_non_git_target_rejected(self):
        plain = self.base / 'plain'
        plain.mkdir()
        with self.assertRaisesRegex(PlannerError, 'not a Git repository'):
            build_plan(plain)
        with self.assertRaisesRegex(PlannerError, 'not a directory'):
            build_plan(self.base / 'missing')

    def test_cli_rejects_non_git_with_nonzero_exit(self):
        plain = self.base / 'plain2'
        plain.mkdir()
        with self.assertRaises(SystemExit) as ctx:
            main(['--repo', str(plain)])
        self.assertNotEqual(ctx.exception.code, 0)

    def test_output_inside_target_repo_refused(self):
        out = self.repo / 'plan.json'
        with self.assertRaises(SystemExit) as ctx:
            main(['--repo', str(self.repo), '--out', str(out)])
        self.assertNotEqual(ctx.exception.code, 0)
        self.assertFalse(out.exists())
        nested = self.repo / 'docs' / 'plan.json'
        with self.assertRaises(PlannerError):
            build_out = build_plan(self.repo)
            from athenz.project_planner import write_plan
            write_plan(build_out, nested, self.repo)

    def test_cli_writes_plan_outside_repo(self):
        out = self.base / 'plan.json'
        main(['--repo', str(self.repo), '--out', str(out),
              '--max-items', '3'])
        plan = json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(len(plan['queue']), 3)
        self.assertEqual(plan['generated_from']['repo'],
                         str(self.repo.resolve()))

    def test_run_is_strictly_read_only(self):
        before = tree_snapshot(self.repo)
        build_plan(self.repo)
        main(['--repo', str(self.repo), '--out',
              str(self.base / 'elsewhere.json')])
        after = tree_snapshot(self.repo)
        self.assertEqual(before, after)

    def test_parse_roadmap_ignores_numbered_lists_elsewhere(self):
        items = parse_roadmap('# X\n\n## Steps\n1. First do this\n'
                              '2. Then that\n')
        self.assertEqual(items, [])


class IssuesFileTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.base = Path(tmp.name)
        self.repo = make_repo(self.base)
        self.issues_path = self.base / 'issues.json'

    def write_issues(self, payload) -> Path:
        self.issues_path.write_text(json.dumps(payload), encoding='utf-8')
        return self.issues_path

    def test_owner_issues_ranked_and_merged(self):
        path = self.write_issues({'issues': [
            {'id': 'owner-7', 'title': 'Owner wants the export fixed',
             'priority': 0, 'depends_on': ['roadmap-1'],
             'success_criteria': 'Export round-trips in a fixture test',
             'scope': ['athenz/export.py']},
            {'id': 'owner-9', 'title': 'Unranked owner note'},
        ]})
        plan = build_plan(self.repo, issues_file=path)
        first = plan['queue'][0]
        self.assertEqual(first['id'], 'owner-7')
        self.assertEqual(first['priority'], 0)
        self.assertEqual(first['dependencies'], ['roadmap-1'])
        self.assertEqual(first['success_criteria'],
                         'Export round-trips in a fixture test')
        self.assertEqual(first['scope'], ['athenz/export.py'])
        note = next(q for q in plan['queue'] if q['id'] == 'owner-9')
        self.assertEqual(note['priority'], 'unranked')

    def test_malformed_issues_rejected(self):
        with self.assertRaises(PlannerError):
            load_issues(self.write_issues({'issues': [{'id': 'x'}]}))
        with self.assertRaises(PlannerError):
            load_issues(self.write_issues(
                {'issues': [{'id': 'x', 'title': 't', 'bogus': 1}]}))
        with self.assertRaises(PlannerError):
            load_issues(self.write_issues({'issues': [
                {'id': 'x', 'title': 't'}, {'id': 'x', 'title': 'u'}]}))
        with self.assertRaises(PlannerError):
            load_issues(self.write_issues(['not', 'an', 'object']))
        self.issues_path.write_text('{broken', encoding='utf-8')
        with self.assertRaises(PlannerError):
            load_issues(self.issues_path)


if __name__ == '__main__':
    unittest.main()
