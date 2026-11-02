# Standing task grants (slice A2)

`athenz-task-grants` is how the owner turns a reviewed plan (slice A1)
into **narrow standing authorization** for coding work. It is the
second slice of the owner-directed persistent coding autonomy track
(ROADMAP.md, slices A1–A6). It *authorizes*; it executes nothing.

**Default is off.** With no grant, nothing has standing authorization
and the existing supervised, per-stage manual approvals apply. A plan,
a remembered preference and a model's own idea are never permission —
only a grant created through the explicit owner action below is.

## The grant model

A grant is created once, by the owner, through an explicit local
review, and binds **all** of the following at creation time:

| Field | Meaning |
| --- | --- |
| `objective` | The owner-stated objective the grant serves. |
| provenance | The planner queue item ids the grant was reviewed against (may be empty only when the objective text itself is the record). |
| `repository` / `worktree` | The one repository (and optionally one worktree) in scope. Checks naming any other path are denied. |
| `task_classes` | The permitted kinds of task (e.g. `implement`, `test`, `docs`). |
| `allowed_files` | Repository-relative file globs work may touch. |
| `permitted_tools` | The tools an executor may invoke under this grant. |
| `network_policy` | `none` (default) or `allowlist` with an explicit host list. |
| budgets | `max_tasks`, `max_test_runs`, `max_retries_per_task`, `max_wall_clock_seconds` — all required, no defaults. |
| `expires_at` | Set from a required lifetime at creation. Expired grants deny. |
| `state` | `active`, `paused`, `revoked` or `expired`. |

Creation requires `--confirm` plus an explicit flag for every scope
field. There are no widening defaults: omitting the network flags
means no network access at all, and budgets cannot be left implicit.

```sh
athenz-task-grants create \
  --objective "Work on the AthenZ repository against its roadmap" \
  --repo /path/to/repo --queue-item roadmap-3 \
  --task-class implement --task-class test \
  --allow-file 'athenz/*.py' --allow-file 'tests/*.py' \
  --tool edit --tool run_tests \
  --max-tasks 5 --max-test-runs 40 --max-retries 2 \
  --max-wall-clock 7200 --duration-hours 24 --confirm
athenz-task-grants list
athenz-task-grants show <grant-id>
athenz-task-grants pause <grant-id>          # immediate, no confirm needed
athenz-task-grants resume <grant-id> --confirm
athenz-task-grants revoke <grant-id> --confirm
athenz-task-grants audit <grant-id>
```

## Authorization checks

Slice A3's executor must call `TaskGrantStore.authorize(...)` before
every attempted operation, passing the repository and whichever of
task class, file, tool, network target and budget consumption the
operation involves. The check returns `allowed` plus a specific
machine-readable `reason` — never a bare no:

`grant_not_found`, `grant_paused`, `grant_revoked`, `grant_expired`,
`repository_out_of_scope`, `task_class_not_permitted`,
`file_out_of_scope`, `tool_not_permitted`, `tool_never_grantable`,
`network_not_permitted`, `network_target_not_allowed`,
`budget_tasks_exhausted`, `budget_test_runs_exhausted`,
`budget_retries_exceeded`, `budget_wall_clock_exhausted`.

Budget consumption is recorded atomically with an allowed check
(a caller declares `new_task`, `test_run`, `retry` or
`wall_clock_seconds` on the check it is about to act on), so a
check-then-act race cannot overspend a budget. A denied check
consumes nothing.

## What a grant can never authorize

Some operations are refused at grant creation **and** at check time,
whatever the grant says: remote **push**, **merge**, **release**,
**package installation**, **deployment**, and any **access to private
Twin/profile data**. Those remain separately reviewed, per-action
owner decisions with regression and rollback checks (slice A5's
promotion boundary). A grant also never widens itself: scope changes
require a new grant, and a grant's executor-side fingerprint —
repository, scope, budgets, expiry — is what slice A4 re-verifies on
resume.

## Pause, revoke, expiry

- **Pause** is immediate and needs no confirmation: a paused grant
  denies every check until resumed.
- **Resume** is an owner action (`--confirm`).
- **Revoke** is an owner action (`--confirm`), takes effect
  immediately, and is **permanent for that grant** — a revoked grant
  can never resume; the owner creates a new grant instead.
- **Expiry** is evaluated lazily on every read and check; the first
  observation past `expires_at` records the transition in the audit
  log and the grant denies as `grant_expired` from then on.

## Audit guarantees

Every authorization check — **allowed and denied** — and every
lifecycle event (created, paused, resumed, revoked, expired) is
appended to an audit table in the private profile database, with the
check's scope detail and the reason. `athenz-task-grants audit
<grant-id>` returns the full sequence in order. The API offers no way
to edit or delete audit rows.

Grants and their audit logs are private profile data: they are stored
under the AthenZ profile home (the same profile database the
supervised scheduler uses), never in any repository.
