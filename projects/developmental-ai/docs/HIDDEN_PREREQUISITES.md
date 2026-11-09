# D3/D4 — Action-precondition discovery without a public graph

**Status:** optional, synthetic, simulation-only experiment; **not** completion
of D1, D3 or D4. The [benchmark protocol](../benchmarks/hidden_prerequisite_protocol.json)
was committed before implementation or evaluation (commit `5eecd140c9ef3b33b1513c9ff5c34566ec9c51bd`).

## Motivation

The preceding procedural-skill benchmark provided the learner with an entire
prerequisite DAG and even manually computed goal ancestry; the learned agent
tied a simple graph planner. This experiment removes the DAG from the public
frame entirely. Instead, an action can be attempted and **blocked**, consuming
one of 12 attempts. Only stable engineered role tags, opaque action names,
the goal alias, completed actions and an accepted/blocked/goal outcome are
visible. Blocked feedback does not reveal which specific prerequisite was
missing. The private DAG stays inside the simulator and privileged oracle.

`PreconditionSkill` explores the *workshop training family only*, then
retains, for each role, the intersection of roles completed before every
accepted instance. This is a simple inference from observational success:
it does **not** identify direct causes, and may include unnecessary earlier
roles. The learner can use this inferred closure for priority selection in a
new task. There is no repair-family policy training or use of test feedback
for updating its record. The role vocabulary is common and intentionally
engineered, so this does not demonstrate semantic discovery or transfer to
unknown action languages.

## Frozen evaluation, baselines and results

Train 360 workshop episodes per seed, indices `train/0..359`. Evaluate 80
fresh `test/81000..81079` episodes per family per seed. Six seeds are from
previous research (14003, 14009, 14033 and 27007, 27011, 27017); these
are **not an independent blind test**. Each family uses 7 roles with opaque
per-episode action names, a different hidden dependency structure and a
12-attempt budget. All methods are evaluated on identical episodes.

Baselines: uniform random; goal-first followed by random retries; stable
hand-coded role ordering; and a privileged DAG oracle. The role-ordering
baseline is intentionally strong and uses the same public role tags as the
learner, so it is a fair warning against overstating this result.

| Mode | Workshop success /480 | Repair success /480 |
| --- | ---: | ---: |
| Random | 373 (77.7%) | 331 (69.0%) |
| Goal-first then random retry | 147 (30.6%) | 92 (19.2%) |
| Hand-coded role order | **480 (100%)** | **480 (100%)** |
| Workshop-trained prerequisite learner | **480 (100%)** | **222 (46.3%)** |
| Privileged hidden-DAG oracle | 480 (100%) | 480 (100%) |

The learner accurately identifies some *necessary workshop ancestors* from
accepted-action contexts, but fails to adapt to the repair family's novel
`inspect`/`pack`/`verify` dependencies. Its repair score is **worse than
random**, even though it still beats a weak goal-first retry method. A
role-order heuristic solves both worlds without learning. This experiment
therefore **does not support a claim of reusable skill discovery or robust
transfer**. Report the negative result as a decision gate for future work.

### Validation and integrity

- New module `developmental_ai.hidden_prerequisites` with strict simulation
  frame and step validation, no hidden DAG in frames, and bounded attempts.
- The skill artifact includes a complete deterministic workshop action trace;
  restore replays actual workshop transitions and compares trained evidence.
  Checksums reject inconsistent state but do **not** authenticate ownership
  or protect against a fully coherent forged history.
- **10 new module tests plus 3 historical transfer tests passed locally**.
- Historical unchanged `benchmarks.transfer_benchmark` returned trained-test
  success 76.0%, 69.0%, and 66.67% for seeds 17, 23, and 41.
- This is *not* a clean checkout of all remote test modules, GitHub Actions
  confirmation, PC validation, a signed owner approval or a deployed agent.

Reproduce from repository root:

```bash
python -m unittest tests.test_hidden_prerequisites -v
python -m benchmarks.hidden_prerequisite_benchmark --cohort development
python -m benchmarks.hidden_prerequisite_benchmark --cohort additional
python -m benchmarks.transfer_benchmark
```

## Next decision

Do not tune these frozen test episodes. A next, separately preregistered
experiment should test **within-episode active diagnosis** from failed
attempts, using unknown dependency structures and unfamiliar roles, and
measure the cost of acquiring enough information to complete a goal.
Independent task authorship and untouched evaluation seeds are needed for
D1/D3 claims. D4 requires discovery/composition of reusable action sequences
and regression-tested rollback, not simple per-role priority statistics.

AthenZ remains the identity/consent owner, Synveil the platform-policy owner;
this simulator grants neither runtime access nor privileges. Planned Version
2A affective cognition still precedes and overlaps Version 2B virtual home.
