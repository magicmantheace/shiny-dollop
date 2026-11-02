# Read-only project planner (slice A1)

`athenz-project-planner` inspects an **explicitly selected** Git
repository and proposes a bounded, prioritized task queue as JSON. It is
the first slice of the owner-directed persistent coding autonomy track
(ROADMAP.md, slices A1–A6). It *proposes*; it never executes.

## Usage

```sh
athenz-project-planner --repo /path/to/repo
athenz-project-planner --repo /path/to/repo --max-items 20 \
    --issues-file /path/to/owner-issues.json \
    --out /path/outside/the/repo/plan.json
```

- `--repo` (required): the target repository. It is only ever read.
- `--max-items`: maximum queue length (default 50). The plan records
  `total_candidates` and `truncated` so a bounded queue is never
  mistaken for the whole backlog.
- `--issues-file`: optional owner-approved issues JSON (format below).
- `--out`: write the plan to this path instead of stdout. The path
  **must lie outside the target repository**; an inside path is
  refused, because the planner never writes into the repo it inspects.

Exit status is non-zero with a clear message when the target is not a
Git repository, has no commits, the issues file is malformed, or the
output path is inside the target.

## Read-only guarantees

- Git is invoked only as `git --no-optional-locks` with
  `GIT_OPTIONAL_LOCKS=0`, and only for `rev-parse` (repository root,
  HEAD, branch) and `status --porcelain`. No fetch, checkout, staging,
  or index writes; the working tree, HEAD and `.git/index` are
  byte-identical after a run (covered by a unit test that snapshots
  hashes and mtimes before/after).
- The only file the tool can write is the `--out` plan, outside the
  target. It does not rewrite the roadmap, open issues, or record
  anything in the target.

## Sources

1. **`ROADMAP.md`** at the target's root:
   - Unchecked checkbox items (`- [ ]`) anywhere in the document.
     Checked items are counted (`completed_items_excluded`), not queued.
   - Numbered items under a heading that signals explicit ordering
     ("critical path", "next steps", "priority"). Numbered lists under
     other headings are treated as prose steps, not tasks.
   - Markdown tables are *not* parsed: in this project's roadmap they
     are version/gate registries (status records), not a task backlog.
2. **Owner-approved issues file** (below), when supplied.

Each item records its source (`file`, `line`, `section`) so the owner
can trace every proposal back to the exact text it came from.

## Priority: never invented

An item is *ranked* only from an explicit signal in its source:

| Signal | Basis recorded |
| --- | --- |
| Number in a priority-section list | `numbered position N in section "…"` |
| `P0`–`P9` marker in the item text | `explicit marker PN` |
| `priority` in the issues file | `owner-supplied priority in issues file` |

Everything else is `"priority": "unranked"` and sorts **after** all
ranked items, preserving source order within each group. Ranked items
from different sources sort by their numeric rank; the per-item
`priority_basis` keeps the (incommensurable) origins visible rather
than pretending one scale. Reordering is the owner's act, not the
planner's.

## Dependencies, criteria, risk, scope — source-derived only

- **Dependencies**: recorded only where stated — a phrase such as
  "depends on", "blocked by" or "requires" naming another item's label
  (slice ids like `A1`, versions like `v0.4`, `#n` for numbered items,
  or an issue id), or an issues-file `depends_on` entry. Anything else
  yields an empty list.
- **Success criteria**: taken from an explicit "acceptance gate:" /
  "success criteria:" phrase in the item text, or the issues file's
  `success_criteria`. Otherwise the plan says so verbatim:
  "Unspecified in source — must be defined by the owner before any
  execution." The planner does not draft criteria.
- **Risk** (`low`/`medium`/`high`): a documented lexical screen over
  the item text — words such as *migration*, *delete*, *security*,
  *push*, *merge*, *release* mark `high`; documentation-only signals
  mark `low`; no signals means `medium`. The matched words are listed
  in `risk.rationale`. This is a triage hint, not an assessment.
- **Scope**: file/path tokens appearing in the item text (or the
  issues file's `scope`). When none appear, scope falls back to the
  item's roadmap section name. The planner cannot expand scope beyond
  what the source mentions.

## Owner-approved issues format

There is no network access to GitHub issues from the planner, so owner
approval takes the form of a local JSON file the owner maintains:

```json
{
  "issues": [
    {
      "id": "owner-7",
      "title": "Fix the export round-trip",
      "priority": 0,
      "depends_on": ["roadmap-1"],
      "success_criteria": "Export round-trips in a fixture test",
      "scope": ["athenz/export.py"],
      "notes": "Optional free text; screened for risk signals."
    }
  ]
}
```

`id` and `title` are required; all other fields are optional. Unknown
fields, duplicate ids, negative priorities and non-list
`depends_on`/`scope` are rejected. At most 200 issues per file.

## Output schema (`athenz.project-plan/v1`)

Top level: `schema`, `read_only` (always `true`), `generated_from`
(repo root, `head`, `branch`, `detached_head`, `working_tree_dirty`,
`test_file_count`, `roadmap_found`, `issues_file`), `max_items`,
`total_candidates`, `completed_items_excluded`, `truncated`, and
`queue` — a list of items with `id`, `title`, `source`, `priority`
(integer rank or `"unranked"`), `priority_basis`, `dependencies`
(item ids), `success_criteria`, `risk` (`level`, `rationale`) and
`scope`.

## Non-goals

- **No execution** of any queued item, and no test runs against the
  target (the planner only *counts* test files). Execution is slice A3.
- **No grants or authorization.** Nothing in a plan is permission to
  act; standing authorization is slice A2 and defaults to off.
- **No roadmap edits**, no issue creation, no prioritization beyond the
  explicit signals above, and no model calls — output is a pure
  function of the target's current text.
