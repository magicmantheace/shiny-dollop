# Bounded authority joint recovery — evidence-derived expiry for the joint gate

**31 October 2026. Status: optional, simulated, unpromoted. No default-controller
promotion, no PR merge, no D1–D10 or V2A/V2B roadmap change, no AthenZ/Synveil
integration.**

## Experiment identity

- **Name and purpose:** `bounded_authority_joint_recovery` — whether a
  recovery/abstention gate whose authority is bounded to the onset window —
  by an evidence-derived condition, not by any phase, stage, or checkpoint
  information the learner cannot see — can preserve the graded joint test's
  onset engagement and harm profile while restoring checkpoint-32
  productivity to within 8 successes of recent8. This tests the limitation
  selected after the preceding experiment was graded Failed: gate
  persistence without expiry (the joint candidate's recovery and abstention
  branches stayed armed at every checkpoint; two stale-archive routings at
  k=32 scored 0/16 each in development and one late abstention in additional
  failed release/productivity on both cohorts). Build Order Priority 1
  (Independent Learning), items 2 + 3 joined to item 4; handoff §8 slow or
  incorrect recovery of old knowledge. The protocol's PRIMARY criterion is
  criterion 5 (release/productivity by k=32), and it is reported first below.
- **Candidate:** `BoundedAuthorityJointRecoveryMemory`
  (`developmental_ai/bounded_authority_joint_recovery.py`) — IDENTICAL to
  the graded `JointConcordanceRecoveryMemory` in acting model (recent8
  exactly), immediate evidence-opposition signal (newest 2 vs 24-event
  reference, opposed_count), retained archive (events[:N-26]), per-event
  archive concordance definition, joint recovery test (joint_count >= 1),
  archive-only recovery model, and abstention trigger (opposed_count == 2).
  The SINGLE changed element is branch AUTHORITY (expiry), computed from
  observed reported events only: (A) local-archive disagreement — local
  window = last 26 events; per distinct span, local span-majority vs archive
  span-majority; comparable iff both majorities non-neutral;
  stable_disagreement iff C >= 1 AND D * 2 > C; (B) acting-window archive
  concordance — recent_concordant_count = archive-concordant events among
  the last 8 (vs the current archive). ABSTENTION is armed iff NOT
  stable_disagreement; RECOVERY is armed iff NOT stable_disagreement OR
  recent_concordant_count >= 2. A disarmed branch that would have fired is
  recorded (recovery_would_fire / abstention_would_fire) and falls through.
  Minimum 27 events, else an all-available fallback (never exercised in
  evaluation). Separate optional learner; the default controller and all
  existing learners are untouched; the graded guard, the graded
  retained-recovery candidate, and the graded joint candidate appear only
  as baselines.
- **Branch and commits:** `developmental-ai/bounded-authority-joint-recovery`
  (forked from `developmental-ai/joint-concordance-recovery` @ `a8ac886`,
  itself forked from `developmental-ai/evidence-opposition-retained-recovery`
  @ `594a8b0`, itself forked from
  `developmental-ai/evidence-opposition-onset-guard` @ `9c6e5c2`, itself
  forked from `developmental-ai/first-contact-onset-guard` @ `8e0a686`,
  itself forked from `developmental-ai/early-post-switch-adaptation` @
  `edd371f`, itself forked from `developmental-ai/standalone-policy-review`
  @ `6e0cac5`). Protocol frozen at `a05e033`; implementation at `606dc49`;
  evaluation at `9004ff8`. This grading report is committed on top of the
  evaluation commit.
- **Frozen protocol:** `benchmarks/bounded_authority_joint_recovery_protocol.json`
  (schema `developmental-ai.bounded-authority-joint-recovery-protocol/v1`,
  frozen 2026-10-30, before any implementation, unit test, harness, or score
  inspection for this experiment).
- **Cohorts:** development 342003/342021/342039 and additional
  343001/343017/343041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit. Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/bounded_authority_joint_recovery_results.json` (development)
  and `benchmarks/bounded_authority_joint_recovery_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged (authored span-to-effect bands,
  two public numeric features). Schedule per seed: A → B1 (inverted) →
  return-A → B2 (inverted), plus a stationary A→A control arm. True outcomes
  flip with probability 1/8; TRAIN reports flip with probability 1/20. The
  learner sees only the public reported stream — no phase label, rule
  identity, or true outcome. Checkpoints 0/2/4/8/16/32 for every stage; 48
  TEST episodes per cohort cell (16 per seed, same indices re-scored at
  every checkpoint, never trained on). Checkpoint 0 is a reported
  diagnostic, NOT graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s tests`:
  944 tests OK in the implementation stage, 944 tests OK in the evaluation
  stage, and 944 tests OK again in this grading stage (run this pass; the
  grading-stage changes are documentation only, no code changed). Focused
  candidate tests: 24/24 PASS in the implementation stage.
- Historical regressions: **PASS** — `python -m benchmarks.transfer_benchmark`
  (unchanged) exited 0 in the evaluation stage, and exited 0 again when
  re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts were
  run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's full decision
  record (immediate signal records, archive concordance records, per-event
  joint flags/records, the full expiry record — per-span local/archive
  majorities, comparable/disagreeing counts, stable_disagreement flag,
  per-event last-8 archive-concordance records, recent_concordant_count,
  per-branch armed and would-fire flags — all counts, branch taken,
  recovery-fired / abstained / gate-evaluable flags, acting source, plus
  the records-only unexpired-joint-rule derivation), a checkpoint SHA256,
  and restore-replay identity verified true at every checkpoint in both
  cohorts (script-verified again in this grading stage; no criterion-7
  field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the evaluation
  or grading commit was checked; no CI is claimed for `9004ff8` or for this
  grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results in
this grading stage, not hand-copied. Denominators are exact episode counts
(48 per stage-checkpoint cell; 96 per pooled return-A onset figure; 288 per
pooled all-stage onset figure); decision-record denominators are
seed-checkpoint states (6 per stage per cohort at checkpoints 2 and 4; 9
switch-stage states per cohort at checkpoint 32). Criterion 5, this
experiment's PRIMARY criterion, is reported first, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 5 | PRIMARY release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 switch-stage k=32 states, from records) | **FAIL** | **PASS** |
| 1 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4; cumulative reported, not graded) | **PASS** | **PASS** |
| 2 | Recovery engagement preserved and selective, from decision records alone (recovery TAKEN ≥3/6 return-A states; ≤1/6 B1 states) | **PASS** | **FAIL** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 4 | Return-A onset harm (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **FAIL** |
| 6 | Stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

The protocol carries no cumulative-dominance cap and no graded
exceed-cumulative sub-condition in this cycle (justification recorded in
the protocol: that sub-condition was the preceding cycle's headline test of
a different limitation). Cumulative's return-A figures are reported in
full under criterion 1 — including where they exceed the candidate's —
and are not hidden.

### Criterion 5 (PRIMARY) — release and productivity by checkpoint 32 (FAIL development, PASS additional)

Additional: k=32 abstentions **0/144** — (a) passes — successes **63** vs
recent8 **63** (required ≥ 55) — (b) passes with the gap fully closed —
and from the decision records alone the candidate took a non-recent8
branch in **0 of 9** switch-stage k=32 states — (c) passes. On this cohort
the expiry is a complete success at k=32: every switch-stage k=32 cell is
identical to recent8, and against the unexpired joint candidate's k=32
pooled 52 successes the bound recovers +11 — including the joint
candidate's B2 stale-archive state (seed 343001) flipping from 0/16 to
11/5, identical to recent8. Development: abstentions **0/144** — (a)
passes — and the records sub-condition passes with exactly **1 of 9**
non-recent8 k=32 states, at the bound — but successes **56** vs recent8
**69** (required ≥ 61) — (b) **fails** by 5. The mechanism is localized
to a single state, and it is the protocol's pre-registered expected
failure mode 3 (residual late false recovery), not a general failure of
the expiry: at B2 k=32, seed 342021, the last-8 window carried
recent_concordant_count == 2 — exactly the corroboration threshold — with
a joint event in the newest window (joint_count == 1), so recovery stayed
armed under stable disagreement and the stale-archive route scored
**0 successes / 16 harm** vs recent8's **13 / 3** in that state. That one
state is the *entire* remaining development k=32 deficit: every other
switch-stage k=32 cell is identical to recent8, and replacing that state
with recent8's outcome would give 69 = recent8 exactly. The bound
nevertheless did real work on this cohort: k=32 pooled successes rose
from the joint candidate's **42** to **56** (the joint candidate's second
stale state, B2 seed 342003 at 0/16, was disarmed to recent8's 14/2), and
no k=32 abstention occurred on either cohort. Persistence at k=8/16 is
mixed and reported, not graded: non-recent8 branches in 3/9 (dev) and 4/9
(add) switch states at k=8, 2/9 and 1/9 at k=16; B1-16 pooled successes
lag recent8 on both cohorts (12 vs 16 dev; 8 vs 16 add).

### Criterion 1 — return-A recovery successes preserved (PASS, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **68** against
frozen_A **64** — the 40% floor passes (68 × 5 = 340 ≥ 64 × 2 = 128) —
and against the guard-relative floor of guard + 16 = **19** (guard scored
3) — passes. Additional: candidate **30** against frozen_A **62** (40%
floor passes: 150 ≥ 124) and guard + 16 = **25** (guard scored 9) —
passes, by 5 over the guard-relative floor. Reported in full, as the
protocol requires: on the additional cohort the candidate's 30 successes
fall far short of plain cumulative's **74** and of the unexpired joint
candidate's **64** on the same cells, at return-A harm 66 vs cumulative's
22 and the joint candidate's 32 (see criterion 4) — the
shortfall is the over-expiry documented under criterion 2, and passing
this criterion's floors does not soften it. On development, cumulative
scored **72** vs the candidate's 68 (−4, again a single-state margin:
seed 342039, where cumulative beat the archive route 13/3 vs 10/6 at both
k=2 and k=4, partly offset by seed 342021, where the candidate beat
cumulative 13/3 vs 12/4 at both checkpoints).

### Criterion 2 — recovery engagement preserved and selective (PASS development, FAIL additional)

Development: recovery was TAKEN at **6 of 6** return-A onset states
(required ≥ 3 — the low edge of the design interval; the unexpired joint
candidate took 5 of 6 on its cohorts) and at **0 of 6** B1 onset states
(required ≤ 1). Would-fire-but-disarmed at return-A onset: **0 of 6** —
on this cohort the expiry cost no onset engagement at all; pooled onset
successes / harm / abstentions are identical to the unexpired joint
candidate's profile shape (101 / 155 / 32 candidate here; the joint
baseline *on these same cohorts* also scored 101 / 155 / 32 pooled
onset). Additional: recovery was TAKEN at only **2 of 6** return-A onset
states — **FAIL** (required ≥ 3) — with B1 at **0 of 6** (passes). The
records separate the cause exactly as the protocol pre-registered: of
the 4 non-taking return-A states, **3 are would-fire-but-disarmed**
(joint_count >= 1, recovery not armed) and only 1 is joint-test silence
(seed 343017 at k=2, joint_count == 0, where the unexpired joint
candidate also scored 1/15). All three disarmed states sit at the
corroboration boundary: stable_disagreement set (as designed at a
return) and recent_concordant_count == **1**, one short of the >= 2
threshold — at k=2 for seeds 343001 and 343041 (disarmed-state outcomes
1/15 and 0/16 vs the joint candidate's 12/4 and 14/2 in those states)
and at k=4 for seed 343017 (1/15 vs joint 10/6). This is the protocol's
pre-registered expected failure mode 1 — over-expiry at return onset —
realized on one cohort: at k=2 the acting window holds only 2 return
events, so the corroboration count leans on flip-back concordance among
the 6 preceding reversed events, and on this cohort that count landed at
1 in both k=2 joint states. The design armed-rate expectation was
approx 0.55–0.70 of return states; realized taken rates are 6/6
(development) and 2/6 (additional) — the condition's variance across
cohorts is itself the finding.

### Criterion 3 — pooled onset harm not above the guard (PASS, both cohorts)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm
**155** vs guard **188** — (a) passes — and candidate harm ≤ recent8 in
**6 of 6** individual cells (required ≥ 5). The candidate's pooled onset
harm equals the unexpired joint candidate's on these cohorts (155) and
cuts recent8's 239 by a third. Additional: candidate **174** vs guard
**195** — (a) passes — with **6 of 6** cells ≤ recent8 (vs recent8 pooled
259). The additional pass coexists with criterion 4's failure: the harm
the disarmed return-A states added (return-A pooled 66) was offset
elsewhere in the pooled figure by the abstention-heavy B1/B2 onset cells
(80/288 onset abstentions on this cohort, vs 32/288 development). Pooled
onset harm passing must not be read as return-A harm passing; the
protocol grades them separately precisely for this reason, and so does
this report.

### Criterion 4 — return-A onset harm (PASS development, FAIL additional)

Development: pooled return-A harm candidate **28** vs guard **61** —
(a) passes — and vs recent8 **90** the 60% ceiling is 54.0 — (b) passes
with margin; this also improves on the joint candidate's development
failure mode in the preceding experiment (40 vs a 37.8 ceiling there).
For reference, cumulative's return-A harm is 24 and frozen_A's is 32 on
this cohort: with 6 of 6 firing states the candidate's archive play is
nearly as clean as the retained references. Additional: candidate **66**
vs guard **87** — (a) passes — but vs recent8 **87** the 60% ceiling is
52.2 — (b) **fails** by 13.8 actions. The mechanism is the criterion-2
over-expiry plus the protocol's pre-registered expected failure mode 2:
at a return onset the local segment is the reversed segment, so
stable_disagreement is set and the abstention fallback is disarmed BY
DESIGN at all 6 additional return-A states — a non-engaging return state
therefore acts through stale recent8 (return-A-2 pooled successes 2/96
episode-checkpoints at harm 46, near recent8's own onset harm) instead
of abstaining as the guard or the unexpired joint candidate's fallback
would. Where recovery did engage on this cohort it was clean (firing
states 12/4 and 15/1, identical to cumulative and the joint candidate).

### Criterion 6 — stationary control downstream selectivity (PASS, both cohorts)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **16/240** (required ≤ 32), successes **121** vs recent8 117
(required ≥ 111), harm **103** vs recent8 123. Recovery engaged at 1 of
15 graded control states and abstention at 1 of 15 (control-16, costing
that cell: 18 successes / 16 abstentions vs recent8's 29 / 0 — offset in
the pooled totals by a recovery state at control-8, 28 vs 13 successes);
stable_disagreement was set at 0 of 15 graded control states, as designed
(local and archive rules agree on stationary evidence). Additional:
abstentions **0/240**, successes **115** = recent8 115, harm **125** =
recent8 125; recovery engaged at 0 of 15 graded control states — the
candidate is downstream-identical to recent8 on the stationary arm.

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions, actual
harmful / productive / neutral outcomes, reported harmful, and label
flips for every stage; per-method successes / harmful TEST actions /
abstentions / attempted tasks at every checkpoint; the candidate's full
decision record (per-event immediate signal records, archive concordance
records, per-event joint flags/records, and the full expiry record —
per-span local/archive majorities with comparable/disagreeing counts,
stable_disagreement flag, per-event last-8 archive-concordance records,
recent_concordant_count, recovery/abstention armed and would-fire flags —
plus every count, branch, recovery-fired / abstained / gate-evaluable
flags, acting source, and the records-only unexpired-joint-rule
derivation) at every checkpoint; checkpoint SHA256; and restore-replay
identity (true at every checkpoint in both cohorts, script-verified in
this stage — no field missing anywhere). Learner information-acquisition
actions = 0, additional requested observations = 0, and learner training
actions = 0 throughout, as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions,
48 episodes per cell).

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 1 / 47 / 0 | 1 / 47 | 2 / 46 / 0 | 2 / 46 |
| B1-2 | 11 / 21 / 16 | 16 / 32 | 1 / 15 / 32 | 4 / 44 |
| B1-4 | 21 / 27 / 0 | 21 / 27 | 3 / 29 / 16 | 14 / 34 |
| B1-8 | 27 / 21 / 0 | 27 / 21 | 18 / 30 / 0 | 18 / 30 |
| B1-16 | 12 / 36 / 0 | 16 / 32 | 8 / 40 / 0 | 16 / 32 |
| B1-32 | 15 / 33 / 0 | 15 / 33 | 24 / 24 / 0 | 24 / 24 |
| return-A-0 † | 0 / 48 / 0 | 0 / 48 | 1 / 47 / 0 | 1 / 47 |
| return-A-2 | 34 / 14 / 0 | 3 / 45 | 2 / 46 / 0 | 2 / 46 |
| return-A-4 | 34 / 14 / 0 | 3 / 45 | 28 / 20 / 0 | 7 / 41 |
| return-A-8 | 33 / 15 / 0 | 25 / 23 | 37 / 11 / 0 | 27 / 21 |
| return-A-16 | 16 / 32 / 0 | 16 / 32 | 25 / 23 / 0 | 25 / 23 |
| return-A-32 | 22 / 26 / 0 | 22 / 26 | 21 / 27 / 0 | 21 / 27 |
| B2-0 † | 0 / 48 / 0 | 0 / 48 | 4 / 44 / 0 | 4 / 44 |
| B2-2 | 1 / 47 / 0 | 1 / 47 | 0 / 32 / 16 | 0 / 48 |
| B2-4 | 0 / 32 / 16 | 5 / 43 | 0 / 32 / 16 | 2 / 46 |
| B2-8 | 16 / 32 / 0 | 16 / 32 | 13 / 19 / 16 | 14 / 34 |
| B2-16 | 29 / 19 / 0 | 29 / 19 | 23 / 25 / 0 | 23 / 25 |
| B2-32 | 19 / 29 / 0 | 32 / 16 | 18 / 30 / 0 | 18 / 30 |
| control-0 † | 24 / 24 / 0 | 24 / 24 | 19 / 29 / 0 | 19 / 29 |
| control-2 | 28 / 20 / 0 | 28 / 20 | 14 / 34 / 0 | 14 / 34 |
| control-4 | 18 / 30 / 0 | 18 / 30 | 18 / 30 / 0 | 18 / 30 |
| control-8 | 28 / 20 / 0 | 13 / 35 | 33 / 15 / 0 | 33 / 15 |
| control-16 | 18 / 14 / 16 | 29 / 19 | 31 / 17 / 0 | 31 / 17 |
| control-32 | 29 / 19 / 0 | 29 / 19 | 19 / 29 / 0 | 19 / 29 |

† Checkpoint 0 is a reported diagnostic, not graded (zero post-switch events
in the stream at k=0 for the switch stages). k=0 harm is 44–48 of 48 per
switch stage across cohorts and methods.

Reference points on the same cohorts (pooled onset, k=2,4, all stages;
successes / harm / abstentions): the decisive expiry comparison
`joint_concordance_recovery` (identical but for the authority condition)
scored 101/155/32 (development) and 68/140/80 (additional) pooled onset,
with return-A pooled successes **68 / 64** — the bound preserves the joint
profile exactly on development and trades it away at return-A on
additional, while beating it at k=32 on both cohorts (56 vs 42 dev; 63 vs
52 add). The harm comparator `evidence_opposition_guard` scored 36/188/64
(development) and 13/195/80 (additional) pooled onset. The pooled
retained-recovery candidate scored 65/191/32 (development) and 13/195/80
(additional). `cumulative` scored return-A pooled successes **72 / 74** at
return-A harm **24 / 22** — on the additional cohort plain cumulative
retention dominates every gated variant at return-A by a wide margin,
because it needs no authority to act on retained knowledge. `frozen_A`
scored return-A **64 / 62** successes at **32 / 34** harm. The privileged
expected oracle (knows the expected hidden rule, not the realized
stochastic flip; a reference only, never a baseline) pooled onset
successes/harm were 184/104 (development) and 198/90 (additional): onset
tasks remain largely solvable, and every realizable learner here remains
far from that.

**Retention note:** the expiry bound answers the preceding experiment's
persistence failure in the records sense on both cohorts (non-recent8
k=32 states 1/9 and 0/9, vs the joint candidate's stale routings) and in
totals on additional (63 = recent8). What it costs is authority exactly
where the return evidence is thinnest: at k=2 on the additional cohort
the corroboration count reached only 1 in both joint states, recovery
never engaged at k=2 there, and return-A pooled successes fell to 30 —
less than half the unexpired gate's 64 on the same records. The two
cohorts bracket the condition's behavior: where return windows carry
their own corroboration (development recent_concordant_count at return
k=2: 4, 2, 2) the bound is free; where they do not (additional: 1, 0, 1)
it is decisive against recovery.

**Generalization level:** at most handoff level 2–3 (choosing among /
applying already-supplied representations under a rule change, plus
designer-supplied signal, concordance, routing, and now expiry rules).
The A/B rules, span statistic, windows, archive definition, joint test,
disagreement and corroboration conditions, and decision rule are all
designer-supplied. No level-6 or novel-representation claim is made.
Nothing in this experiment speaks to general regime identification: the
archive is global and unsegmented, and B2 recovery was pre-registered as
not expected (and did not occur at onset in either cohort).

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; pooled onset
  harm 155 (development) and 174 (additional) vs recent8 239 / 259 and
  vs the guard 188 / 195 — the candidate is the least harmful realizable
  onset method pooled on both cohorts, but that pooled figure conceals
  the additional cohort's return-A concentration (66 of its 174 onset
  harm is at return-A, above the 60%-of-recent8 ceiling there). The one
  residual late false recovery (development B2-32, seed 342021) caused
  16/16 harm in its state.
- **Actual harmful TRAIN-acquisition actions** (external actor, counted
  once per seed, never netted against TEST results): development — A
  244, B1 80, return-A 52, B2 84 harmful of 1,248 main-schedule actions
  (plus control continuation 72 of 192); additional — A 271, B1 78,
  return-A 60, B2 84 of 1,248 (plus control 67 of 192). Label flips in
  the reported stream: development 57 (main) + 4 (control); additional
  52 (main) + 9 (control).
- **Failed-by-abstention:** candidate onset abstentions 32/288
  (development) and 80/288 (additional); k=32 abstentions 0/144 on both
  cohorts; graded stationary control abstentions 16/240 (development,
  the single control-16 state) and 0/240 (additional). The
  always-abstain baseline is 48/48 abstentions with 0 successes and 0
  harm at every checkpoint, as registered.
- **Additional requested observations / learner acquisition actions:**
  0 / 0, exactly as frozen.
- **False confidence and unnecessary abstention:** at onset, false
  recovery at B1 — the pre-registered dangerous direction — occurred at
  0 of 6 states on both cohorts, and B2 recovery never engaged at onset.
  The false-confidence residual is now narrow and exactly located: one
  late corroboration re-arming (development B2-32, recent_concordant
  == 2 with a joint event) out of 18 switch-stage k=32 states across
  cohorts. The symmetric error dominates this experiment instead:
  *false expiry* — recovery authority withdrawn at genuine return-A
  onset states whose corroboration count landed at 1 (3 states,
  additional cohort), compounded by the by-design disarmed abstention
  fallback at those same states, which converted what the guard would
  have answered with abstention into stale-recent8 action at near-maximal
  harm.
- **Report integrity / provenance:** checkpoint SHA256 replay identity
  held at every checkpoint in both cohorts; hashes validate record
  integrity only, not the truth of the (deliberately corrupted) public
  reports.

## Scientific conclusion

**Failed** — per the protocol's own grading definitions: criterion 2
FAILs and criterion 4 FAILs on the additional cohort, which is the
protocol's Failed condition (any of criteria 1–4 FAIL on the additional
cohort). The PRIMARY criterion 5 splits: PASS on additional, FAIL on
development on its productivity sub-condition alone, by one state's
margin. It is **not** a Regression under any clause of the protocol's
definition: pooled onset harm does not exceed recent8's on either cohort
(155 < 239; 174 < 259), stationary-control successes do not fall below
recent8's (121 > 117; 115 = 115), checkpoint-32 successes stay above the
joint candidate's worse-cohort deficit line on both cohorts (56 ≥
69 − 19 = 50; 63 ≥ 63 − 19), and the full unit suite and historical
transfer benchmark pass.

What the experiment genuinely establishes, recorded with the failure:
the expiry mechanism works in the direction it was built for. Bounding
the gate's authority by stable local-archive disagreement plus acting-
window corroboration (i) preserved the joint onset profile *exactly* on
the development cohort (6/6 return-A engagement, pooled onset identical
to the unexpired baseline on the same cohorts, return-A harm 28 — the
best return-A harm figure of any gated candidate so far), (ii) restored
k=32 productivity completely on the additional cohort (63 = recent8,
0/9 non-recent8 states, +11 over the unexpired gate) and substantially
on development (42 → 56 of recent8's 69), and (iii) kept stationary
selectivity on both cohorts. Its cost is equally specific and was
pre-registered as the central risk: the corroboration leg is weakest
exactly at k=2, where only 2 of the last 8 events follow the returned
rule — on the additional cohort every k=2 return state failed to engage
(2 disarmed at count == 1, 1 joint-silent), return-A engagement fell to
2/6, and because abstention is disarmed at a return by design, those
states acted through stale recent8 and pushed return-A harm over its
ceiling. One residual late re-arming (count exactly 2, development
B2-32) accounts for the entire remaining k=32 deficit on development.
Plain cumulative retention remains the strongest simple return-A policy
on the additional cohort (74 successes at 22 harm) — on that cohort it
dominates every gated variant, because it never has to earn authority
to use retained knowledge.

No frozen parameter, threshold, seed, or checkpoint is changed in
response to these results. Any revised hypothesis gets a NEW protocol
and NEW seeds.

## Next limitation (selected for the next cycle)

**P1 — return-onset authority starvation: the corroboration leg of the
expiry condition (recent_concordant_count >= 2 among the last 8 events)
is structurally weakest at checkpoint 2, where only 2 of those 8 events
follow the returned rule, so on a cohort whose return windows carry few
flip-back concordant events the recovery branch is disarmed at exactly
the moment it is needed — additional cohort: 0 of 3 return-A states
engaged at k=2 (2 disarmed with the count at exactly 1, outcomes 1/15
and 0/16 vs the unexpired gate's 12/4 and 14/2), engagement pooled 2/6,
return-A successes 30 vs the unexpired gate's 64 and cumulative's 74 on
the same cohorts, and return-A harm pushed over its ceiling because the
abstention fallback is disarmed at a return by the same flag — while on
the development cohort the identical condition cost nothing (counts
4/2/2 at k=2, engagement 6/6).** Measurable form for the next protocol:
on NEW seed cohorts, whether a recovery-authority condition that does
not starve at the earliest onset checkpoint — while still expiring late
(criterion-5 analogue: k=32 productivity within 8 of recent8 and ≤1
non-recent8 branch state in 9, from records) — can restore return-A
engagement to at least the graded joint candidate's level and keep
return-A harm at or below 60% of recent8, against recent8, cumulative,
frozen_A, the evidence-opposition guard, the graded joint candidate,
and this experiment's candidate as baselines. This stays inside
Priority 1 items 2, 3, and 4 and does not re-tune any parameter of the
seven graded onset experiments against their inspected cohorts; the
revised hypothesis gets its own frozen protocol and NEW seeds.
(Secondary, recorded but not selected: the residual late false recovery
via corroboration re-arming — one development B2-32 state at count
exactly 2 scoring 0/16 vs recent8 13/3, the entire remaining
development k=32 deficit of criterion 5 sub-condition (b); the
opposed_count == 0 blind spot, which did not bind as a return-A
engagement failure in this cycle — the one joint-silent additional
return state had joint_count == 0 with opposed_count == 1 and
concordance absent as well; and B1-16 pooled productivity lagging
recent8 on both cohorts, 12 vs 16 and 8 vs 16, at non-recent8 branch
counts of 2/9 and 1/9.)

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.bounded_authority_joint_recovery_benchmark --cohort development
python -m benchmarks.bounded_authority_joint_recovery_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results above;
it does not make the seeds un-inspected.
