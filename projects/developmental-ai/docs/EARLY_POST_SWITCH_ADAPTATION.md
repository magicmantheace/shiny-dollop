# Early post-switch adaptation — gated archive prequential memory

**28 October 2026. Status: optional, simulated, unpromoted. No default-controller
promotion, no PR merge, no D1–D10 or V2A/V2B roadmap change, no AthenZ/Synveil
integration.**

## Experiment identity

- **Name and purpose:** `early_post_switch_adaptation` — whether one
  retained-knowledge mechanism can, in the first 0–8 observations after an
  unannounced rule change, (i) recover task success as fast as the trivial
  recent-8 window, (ii) avoid acting on obsolete knowledge, and (iii) preserve
  pre-switch knowledge for a later return to the original rule. Build Order
  Priority 1 (Independent Learning), items 3 and 4; item 2 measured by the
  return-A stage.
- **Candidate:** `GatedArchivePrequentialMemory`
  (`developmental_ai/gated_archive_prequential_memory.py`) — immutable
  192-event archive, asymmetric displacement margin 1.0, contradiction
  override (≥2 of the latest 4 events at archive p < 0.125), adequacy gate
  abstaining when the selected mean prequential log-score is < −1.2. Separate
  optional learner; the default controller and all existing learners are
  untouched.
- **Branch and commits:** `developmental-ai/early-post-switch-adaptation`
  (forked from `developmental-ai/standalone-policy-review` @ `6e0cac5`).
  Protocol frozen at `76bccc8`; implementation at `a28f97e`; evaluation at
  `8940163`. This grading report is committed on top of the evaluation commit.
- **Frozen protocol:** `benchmarks/early_post_switch_adaptation_protocol.json`
  (schema `developmental-ai.early-post-switch-adaptation-protocol/v1`,
  frozen 2026-10-27, before any implementation or score inspection).
- **Cohorts:** development 292003/292021/292039 and additional
  293001/293017/293041 — NEW at freeze, disjointness verified by repository
  search before the freeze commit. Both cohorts are now **INSPECTED** and must
  never be re-tuned against. Detailed results:
  `benchmarks/early_post_switch_adaptation_results.json` (development) and
  `benchmarks/early_post_switch_adaptation_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged (authored span-to-effect bands,
  two public numeric features). Schedule per seed: A → B1 (inverted) →
  return-A → B2 (inverted), plus a stationary A→A control arm. True outcomes
  flip with probability 1/8; TRAIN reports flip with probability 1/20. The
  learner sees only the public reported stream — no phase label, rule
  identity, or true outcome. Checkpoints 0/2/4/8/16/32/64 (return-A caps at
  48); 96 TEST tasks per cohort-checkpoint (16 per seed, same indices
  re-scored at every checkpoint, never trained on).

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s tests`:
  835 tests OK in the evaluation stage on the evaluation tree, and 835 tests
  OK again in this grading stage (run this pass; the grading-stage changes
  are documentation only, no code changed). Focused candidate tests: 14/14
  PASS in the implementation stage.
- Historical regressions: **PASS** — `python -m benchmarks.transfer_benchmark`
  (unchanged) exited 0 with its standard three-seed output in the evaluation
  stage, and exited 0 again when re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts were run
  with no change to any frozen parameter, threshold, seed, or checkpoint.
  Every checkpoint entry carries a checkpoint SHA256 and restore-replay
  identity verified true at every checkpoint in both cohorts.
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the evaluation
  or grading commit was checked; no CI is claimed for `8940163` or for this
  grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 1 | Early adaptation, no deficit vs recent8 at B1-8 and B2-8 | **FAIL** | **FAIL** |
| 2 | Harm never worse than recent8 at any B1/return-A/B2 checkpoint | **FAIL** | **FAIL** |
| 3 | Retention: return-A-8 ≥ 90% of frozen_A | **PASS** | **FAIL** |
| 4 | Abstention budget ≤24/96 at each 8-observation checkpoint | **PASS** | **PASS** |
| 5 | No false reversion (B-64 selection, B-64 harm ≤8/96, control ≥17/18) | **FAIL** | **FAIL** |
| 6 | Full accounting in the saved detailed results | **PASS** | **PASS** |

Only criteria 4 and 6 pass on both cohorts. Criterion 4 passes vacuously:
the candidate abstained **0 times at every checkpoint in both cohorts**, so
the adequacy gate never fired at all (see below).

### Criterion 1 — early adaptation (FAIL, both cohorts)

Development: B1-8 candidate **7/96** successes vs recent8 **7/96** (meets the
B1 half); B2-8 candidate **5/96** vs recent8 **9/96** (fails the B2 half).
Additional: B1-8 candidate **9/96** vs recent8 **15/96**; B2-8 candidate
**0/96** vs recent8 **15/96**. The candidate does not match the simplest
credible baseline in the first eight observations, and on the additional
cohort's second reversal it completes no task at all at checkpoint 8.

### Criterion 2 — harm never worse than recent8 (FAIL, both cohorts)

Development: candidate harm exceeds recent8 harm at **10 of 21**
stage-checkpoints (cohort aggregate), including B1-0 onset **48 vs 47**,
B1-2 **47 vs 35**, B2-8 **43 vs 39**, and B2-16 **42 vs 30**.
Additional: violations at **9 of 21** stage-checkpoints, including B1-4
**47 vs 34**, B2-8 **48 vs 33**, and B2-16 **46 vs 35**. A single violation
fails the criterion for the cohort; both cohorts fail many times over.

### Criterion 3 — retention (development PASS, additional FAIL)

Development: return-A-8 candidate **29/96** successes vs the required
ceil(0.90 × frozen_A **29/96**) = **27** — PASS, matching frozen_A exactly.
Additional: return-A-8 candidate **24/96** vs the required
ceil(0.90 × frozen_A **35/96**) = **32** — FAIL. The one clear positive
signal in this experiment (development return-A recovery, 29 vs recent8's
18) does not replicate on the additional cohort (24 vs recent8's 28).

### Criterion 4 — abstention budget (PASS, both cohorts — vacuously)

Candidate failed-by-abstention is **0/96** at checkpoint 8 of B1, return-A,
and B2 in both cohorts — and 0 at every other checkpoint too. The adequacy
gate (selected mean prequential log-score < −1.2) never triggered, even at
switch onsets where the candidate then caused 48/96 harmful TEST actions.
Passing a budget by never using the mechanism is not evidence the gate works;
it is evidence the gate, as frozen, is inoperative in this simulator.

### Criterion 5 — no false reversion (FAIL, both cohorts)

(a) Selection at B-64: PASS on both cohorts — no seed selected the archive at
B1-64 or B2-64 (the REGRET_SWITCH late-reselection failure mode did not
recur as a *selection*).
(b) Harm at B-64: FAIL on both cohorts — development B1-64 **10/96** and
B2-64 **28/96** harmful TEST actions (limit ≤8); additional B1-64 **13/96**
and B2-64 **21/96**. Avoiding the archive label did not avoid the harm: the
selected recent windows themselves were still wrong at 64 observations.
(c) Stationary control: development FAIL — archive selected at only
**15/18** seed-checkpoints (required ≥17); additional PASS — **18/18**.
All three parts are required, so the criterion fails on both cohorts.

### Criterion 6 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions, actual
harmful / productive / neutral outcomes, reported harmful, and label flips
for every stage; per-method successes / harmful TEST actions / abstentions /
attempted tasks at every checkpoint; the candidate's recorded selection and
decision at every checkpoint; checkpoint SHA256; and restore-replay identity
(true everywhere). Learner information-acquisition actions = 0 and additional
requested observations = 0 throughout, as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions, 96 tasks per cell;
abstentions are 0 for the candidate at every cell):

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 | 0 / 48 | 1 / 47 | 0 / 48 | 0 / 48 |
| B1-2 | 1 / 47 | 13 / 35 | 0 / 48 | 6 / 42 |
| B1-4 | 2 / 46 | 5 / 43 | 1 / 47 | 14 / 34 |
| B1-8 | 7 / 41 | 7 / 41 | 9 / 39 | 15 / 33 |
| B1-16 | 30 / 18 | 35 / 13 | 20 / 28 | 12 / 36 |
| B1-32 | 23 / 25 | 16 / 32 | 29 / 19 | 30 / 18 |
| B1-64 | 38 / 10 | 29 / 19 | 35 / 13 | 27 / 21 |
| return-A-0 | 0 / 48 | 2 / 46 | 0 / 48 | 0 / 48 |
| return-A-2 | 0 / 48 | 2 / 46 | 0 / 48 | 0 / 48 |
| return-A-4 | 19 / 29 | 5 / 43 | 23 / 25 | 5 / 43 |
| return-A-8 | 29 / 19 | 18 / 30 | 24 / 24 | 28 / 20 |
| return-A-16 | 29 / 19 | 24 / 24 | 35 / 13 | 21 / 27 |
| return-A-32 | 29 / 19 | 26 / 22 | 35 / 13 | 28 / 20 |
| return-A-48 | 18 / 30 | 14 / 34 | 35 / 13 | 25 / 23 |
| B2-0 | 8 / 40 | 4 / 44 | 0 / 48 | 2 / 46 |
| B2-2 | 4 / 44 | 6 / 42 | 0 / 48 | 0 / 48 |
| B2-4 | 5 / 43 | 11 / 37 | 0 / 48 | 2 / 46 |
| B2-8 | 5 / 43 | 9 / 39 | 0 / 48 | 15 / 33 |
| B2-16 | 6 / 42 | 18 / 30 | 2 / 46 | 13 / 35 |
| B2-32 | 25 / 23 | 11 / 37 | 31 / 17 | 29 / 19 |
| B2-64 | 20 / 28 | 20 / 28 | 27 / 21 | 20 / 28 |

Reference points: frozen_A scores 29 (dev) / 35 (additional) successes at
return-A-8 and 0 at every B checkpoint — the archive retains A and nothing
else. The privileged expected oracle (knows the expected hidden rule, not the
realized stochastic flip; a reference only, never a baseline) scores 34/31
(dev B1/B2 onset tables) — the candidate is far below it early and remains
below recent8 where it matters most.

**Mechanism diagnosis (from the recorded decisions, not new tuning):** in
the first 2–4 post-switch observations the contradiction override fires and
routes selection to **recent32**, a window still dominated by pre-switch A
events at that point (recent32 at B1-2: 1/96 dev, 0/96 additional successes —
essentially the obsolete model under a new name). By checkpoint 8 the
candidate has usually converged to recent8-like behavior, but the early harm
is already done and, on B2 in the additional cohort, it has not converged at
all (0/96). Retention, when it appears, comes from the archive default — the
same default that produces 48/96 onset harm at every switch.

**Generalization level:** at most handoff level 2–3 (choosing among /
applying already-supplied representations under a rule change). The A/B
rules, span statistic, windows, margin, and thresholds are all
designer-supplied. No level-6 or novel-representation claim is made.

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; the headline is
  onset harm — candidate 48/96 at B1-0 and return-A-0 (development), 48/96 at
  B1-0, return-A-0, and B2-0 (additional) — and criterion-2 violations at
  10/21 (dev) and 9/21 (additional) stage-checkpoints.
- **Actual harmful TRAIN-acquisition actions** (external actor, counted once
  per seed, never netted against TEST results): development — A 255, B1 76,
  return-A 52, B2 76 harmful of 1,248 main-schedule actions (plus control
  continuation 58 of 192); additional — A 249, B1 75, return-A 48, B2 79 of
  1,248 (plus control 61 of 192). Label flips in the reported stream:
  development 56 (main) + 9 (control); additional 42 (main) + 7 (control).
- **Failed-by-abstention:** 0 for the candidate everywhere (the gate never
  fired); always-abstain baseline is 96/96 abstentions with 0 successes and
  0 harm at every checkpoint, as registered.
- **Additional requested observations / learner acquisition actions:** 0 / 0,
  exactly as frozen.
- **False confidence and unnecessary abstention:** false confidence is the
  dominant failure — the candidate acted on obsolete or A-dominated models at
  every onset. Unnecessary abstention: none observed, because there was no
  abstention at all.
- **Report integrity / provenance:** checkpoint SHA256 replay identity held
  at every checkpoint in both cohorts; hashes validate record integrity only,
  not the truth of the (deliberately corrupted) public reports.

## Scientific conclusion

**Failed — and a Regression relative to the recent8 baseline.**

Per the protocol's own grading definitions: the conclusion is **Failed**
because criteria 1, 2, and 3 all FAIL on the additional cohort. It is
additionally a **Regression** because the candidate is worse than recent8 on
criteria 1 and 2 on *both* cohorts. It is not Demonstrated or Partially
demonstrated under any reading of the frozen definitions.

What the experiment genuinely establishes, negatively: protecting an archive
with a displacement margin plus a contradiction override does **not** buy
early post-switch safety or speed in this simulator. The override's early
routing to recent32 reproduces the obsolete model's harm, the adequacy gate
as frozen never fires, and the development cohort's one positive signal
(return-A retention, criterion 3 PASS) does not replicate on the additional
cohort. The archive-default design keeps paying the historical onset-harm
cost that motivated the experiment.

No frozen parameter, threshold, seed, or checkpoint is changed in response
to these results. Any revised hypothesis gets a NEW protocol and NEW seeds.

## Next limitation (selected for the next cycle)

**P1 — first-contact behavior at switch onset (checkpoints 0–4): the
candidate acts, and never abstains, on a model contradicted by the newest
evidence, causing near-total onset harm (48/96 at most onsets in both
cohorts) while its adequacy gate fires 0 times across every checkpoint in
both cohorts.** Measurable form for the next protocol: harmful TEST actions
and gate/abstention behavior at checkpoints 0, 2, and 4 after a switch,
against recent8 and an always-abstain control, on NEW seed cohorts. This
stays inside Priority 1 (adaptation to changing environments; handoff §8
first-contact overconfidence and weak uncertainty calibration) and does not
re-tune any parameter of this experiment.

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.early_post_switch_adaptation_benchmark --cohort development
python -m benchmarks.early_post_switch_adaptation_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results above; it
does not make the seeds un-inspected.
