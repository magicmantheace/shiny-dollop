# Evidence-opposition retained recovery — signal-gated archive recovery at return-A

**30 October 2026. Status: optional, simulated, unpromoted. No default-controller
promotion, no PR merge, no D1–D10 or V2A/V2B roadmap change, no AthenZ/Synveil
integration.**

## Experiment identity

- **Name and purpose:** `evidence_opposition_retained_recovery` — whether a
  learner that pairs the graded evidence-opposition onset signal with a
  retained-knowledge concordance test can, at return-A checkpoints 2 and 4,
  act through retained pre-switch knowledge instead of merely abstaining or
  acting through a stale recent window — approaching frozen_A's return-A
  successes while keeping pooled onset harm at or below the
  evidence-opposition guard's level on the same cohort. This tests the
  limitation selected after the preceding experiment was graded
  Demonstrated: detection without recovery (the guard abstains when its
  gate fires and acts through stale recent8 when it does not, forfeiting
  frozen_A's 68 / 70 pooled return-A onset successes). Build Order
  Priority 1 (Independent Learning), items 2 + 3 joined to item 4;
  handoff §8 slow or incorrect recovery of old knowledge.
- **Candidate:** `EvidenceOppositionRecoveryMemory`
  (`developmental_ai/evidence_opposition_retained_recovery.py`) — recent8
  acting model exactly; the immediate evidence-opposition signal EXACTLY
  as in the graded guard (newest 2 events vs the 24-event reference
  window, opposed_count, no fitted probabilities); plus a retained-archive
  concordance test (hard span-majority over ALL events before the
  reference window; the archive is events[:N-26]). Decision order:
  (1) RECOVERY — if concordant_count == 2 AND opposed_count >= 1, act
  through a `RelationOutcomeMemory` fitted on the archive events only;
  (2) ABSTENTION — else if opposed_count == 2, abstain exactly as the
  guard; (3) else act through recent8 exactly. Minimum 27 events, else
  an all-available fallback (never exercised in evaluation). Separate
  optional learner; the default controller and all existing learners are
  untouched; the graded guard appears only as a baseline.
- **Branch and commits:** `developmental-ai/evidence-opposition-retained-recovery`
  (forked from `developmental-ai/evidence-opposition-onset-guard` @
  `9c6e5c2`, itself forked from `developmental-ai/first-contact-onset-guard`
  @ `8e0a686`, itself forked from
  `developmental-ai/early-post-switch-adaptation` @ `edd371f`, itself
  forked from `developmental-ai/standalone-policy-review` @ `6e0cac5`).
  Protocol frozen at `71c2c9c`; implementation at `7359a0a`; evaluation
  at `e86228d`. This grading report is committed on top of the
  evaluation commit.
- **Frozen protocol:** `benchmarks/evidence_opposition_retained_recovery_protocol.json`
  (schema `developmental-ai.evidence-opposition-retained-recovery-protocol/v1`,
  frozen 2026-10-29, before any implementation, unit test, harness, or
  score inspection for this experiment).
- **Cohorts:** development 322003/322021/322039 and additional
  323001/323017/323041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit. Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/evidence_opposition_retained_recovery_results.json`
  (development) and
  `benchmarks/evidence_opposition_retained_recovery_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged (authored span-to-effect
  bands, two public numeric features). Schedule per seed: A → B1
  (inverted) → return-A → B2 (inverted), plus a stationary A→A control
  arm. True outcomes flip with probability 1/8; TRAIN reports flip with
  probability 1/20. The learner sees only the public reported stream —
  no phase label, rule identity, or true outcome. Checkpoints
  0/2/4/8/16/32 for every stage; 48 TEST episodes per cohort cell (16
  per seed, same indices re-scored at every checkpoint, never trained
  on). Checkpoint 0 is a reported diagnostic, NOT graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s tests`:
  895 tests OK in the implementation stage, 895 tests OK in the
  evaluation stage, and 895 tests OK again in this grading stage (run
  this pass; the grading-stage changes are documentation only, no code
  changed). Focused candidate tests: 22/22 PASS in the implementation
  stage.
- Historical regressions: **PASS** — `python -m benchmarks.transfer_benchmark`
  (unchanged) exited 0 with its standard three-seed output in the
  evaluation stage, and exited 0 again when re-run in this grading
  stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts
  were run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's full
  decision record (immediate signal records, archive concordance
  records, opposed / matched / concordant / archive-matched counts,
  branch taken, recovery-fired / abstained / gate-evaluable flags,
  acting source), a checkpoint SHA256, and restore-replay identity
  verified true at every checkpoint in both cohorts (script-verified
  again in this grading stage; no criterion-7 field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `e86228d` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results
in this grading stage, not hand-copied. Denominators are exact episode
counts (48 per stage-checkpoint cell; 96 per pooled return-A onset
figure; 288 per pooled all-stage onset figure); decision-record
denominators are seed-checkpoint states (6 per stage per cohort at
checkpoints 2 and 4).

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 1 | Return-A recovery successes (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **FAIL** | **FAIL** |
| 2 | Recovery engagement from decision records alone (≥2/6 return-A states; ≤1/6 B1 states) | **FAIL** | **FAIL** |
| 3 | Pooled onset harm (≤ guard same-cohort AND ≤75% of recent8; ≥5/6 cells ≤ recent8) | **FAIL** | **FAIL** |
| 4 | Return-A onset harm (≤ guard AND ≤60% of recent8, pooled k=2,4) | **FAIL** | **FAIL** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8) | **PASS** | **PASS** |
| 6 | Stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

**Cumulative-dominance cap (protocol grading section): TRIGGERED on both
cohorts.** Cumulative's pooled return-A onset successes exceed the
candidate's by 35 (development: 58 vs 23) and 48 (additional: 66 vs 18),
both far above the cap's margin of 8. Had every criterion passed, the
conclusion would still have been capped at Partially demonstrated:
plain cumulative retention dominates this signal-gated recovery.

### Criterion 1 — return-A recovery successes (FAIL, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **23** against
frozen_A **64** — the 40% floor requires candidate × 5 ≥ frozen_A × 2
(115 < 128) — and against the guard-relative floor of guard + 16 =
**30** (guard scored 14). Both sub-conditions fail. Additional:
candidate **18** against frozen_A **66** (90 < 132) and the floor of
**29** (guard scored 13). Both sub-conditions fail. The candidate's
return-A successes are 36% (development) and 27% (additional) of
frozen_A's — and on the development cohort the candidate's 23 successes
are exactly recent8's 23: the recovery branch added no pooled return-A
productivity there at all. On the additional cohort it added +5 over
recent8 (18 vs 13), from the single firing state (criterion 2).

### Criterion 2 — recovery engagement, from decision records alone (FAIL, both cohorts)

Development: the recovery branch fired at **1 of 6** return-A onset
seed-checkpoint states (required ≥ 2) — seed 322003 at k=4
(opposed_count 2, concordant_count 2). B1 engagement **0 of 6**
(required ≤ 1; the selectivity half passes). Additional: recovery fired
at **1 of 6** return-A states (seed 323001 at k=4, opposed_count 1,
concordant_count 2); B1 engagement **0 of 6**. B2 engagement was 0 of 6
in both cohorts, exactly the pre-registered expectation (the global
archive majority is original-rule-dominated; B2 recovery was not
expected). The diagnosis is in the counts themselves:
**concordant_count == 1 in 5 of 6 return-A onset states in BOTH
cohorts** — one newest event archive-concordant, the other not — so the
both-events requirement (concordant_count == 2) is the binding
constraint, precisely the protocol's pre-registered expected failure
mode 1 (engagement sparsity from squaring a per-event probability).
The opposed side adds a second thin spot on the additional cohort:
opposed_count == 0 in 2 of 6 return-A states (the pre-registered blind
spot — those states are unreachable by design) and == 1 in 3 of 6.

### Criterion 3 — pooled onset harm not above the guard (FAIL, both cohorts)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm
**262** vs guard **255** — sub-condition (a) fails (candidate above the
guard) — and vs recent8 **262**, against the 75% ceiling of 196.5 —
sub-condition (b) fails by a wide margin. Sub-condition (c) passes
(6 of 6 cells ≤ recent8 — indeed the candidate is *identical* to
recent8 in all six development onset cells, successes and harm alike;
its one recovery state converted a guard abstention into archive play
that pooled to the same cell totals as recent8). Additional: candidate
**231** vs guard **236** — (a) passes — but vs recent8 **254** the 75%
ceiling is 190.5 — (b) fails. (c) passes, 6 of 6 cells ≤ recent8. On
neither cohort does the candidate reproduce the guard's demonstrated
harm level as graded here, because on these cohorts the abstention
branch itself was nearly silent (development onset abstentions
**0/288** — opposed_count reached 2 at exactly one onset state, and
that state recovered instead of abstaining; additional **32/288**,
from one B1 and one B2 firing state) — the pooled onset comparison is
dominated by unprotected recent8 acting, the candidate's and the
guard's alike.

### Criterion 4 — return-A onset harm (FAIL, both cohorts)

Development: pooled return-A harm candidate **73** vs guard **66** —
(a) fails — and vs recent8 **73**, against the 60% ceiling of 43.8 —
(b) fails; candidate return-A harm is identical to recent8's.
Additional: candidate **78** vs guard **83** — (a) passes — but vs
recent8 **83** the 60% ceiling is 49.8 — (b) fails. For reference,
frozen_A's return-A harm on these cohorts is 32 / 30 and cumulative's
is 38 / 30: retained-knowledge play *can* cut return-A harm to near
the ceiling level, but only when it actually engages — at 1 of 6
states it cannot move the pooled figure. Where recovery did fire, it
behaved as designed: the additional cohort's firing state sits inside
a return-A-4 cell that improves on recent8 by +5 successes / −5 harm
(pooled cell 14/34 vs recent8 9/39, the other two seeds' states being
identical across methods there).

### Criterion 5 — release and productivity by checkpoint 32 (PASS, both cohorts)

Development: k=32 abstentions **0/144**, successes **57** vs recent8
**62** (required ≥ 54). Additional: abstentions **0/144**, successes
**65** = recent8 65 (required ≥ 57). Release is complete in both
cohorts. The pre-registered persistence interaction at k=8/16 is
reported, not hidden: on the development cohort the inherited
abstention branch fires at B1-8 and B2-8 (one state each; pooled
successes 16 vs recent8 25 and 15 vs 26, harm lower in compensation,
16 vs 23 and 17 vs 22), and one return-A-16 recovery engagement
coincides with pooled successes 26 vs recent8 28 there; on the
additional cohort one B2-8 abstention state costs successes 19 vs 27
(harm 13 vs 21). None of this breaks the checkpoint-32 bound the
protocol grades.

### Criterion 6 — stationary control downstream selectivity (PASS, both cohorts)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **0/240**, successes **114** = recent8 114, harm **126** =
recent8 126 — the candidate is indistinguishable from recent8 on
stationary evidence at every graded control checkpoint, and recovery
never engaged at any graded control state. Additional: abstentions
**0/240**, successes **148** vs recent8 146, harm **92** vs recent8 94.
Recovery engaged at exactly 1 of 15 graded control states, and — as
the protocol expected — the archive model is itself a valid stationary
model, so downstream totals stayed within (in fact slightly inside)
the bounds. This pass is not vacuous in the damaging direction: the
same decision rule demonstrably engages and abstains elsewhere
(criteria 2–4 records) while costing nothing measurable here.

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions, actual
harmful / productive / neutral outcomes, reported harmful, and label
flips for every stage; per-method successes / harmful TEST actions /
abstentions / attempted tasks at every checkpoint; the candidate's full
decision record (per-event immediate signal records and archive
concordance records with every field the protocol lists, plus counts,
branch, recovery-fired / abstained / gate-evaluable flags, acting
source) at every checkpoint; checkpoint SHA256; and restore-replay
identity (true at every checkpoint in both cohorts, script-verified in
this stage — no field missing anywhere). Learner
information-acquisition actions = 0, additional requested observations
= 0, and learner training actions = 0 throughout, as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions,
48 episodes per cell). The candidate equals recent8 in most cells; the
exceptions are exactly the states where its recovery or abstention
branch fired.

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 0 / 32 / 16 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| B1-2 | 0 / 48 / 0 | 0 / 48 | 3 / 45 / 0 | 3 / 45 |
| B1-4 | 1 / 47 / 0 | 1 / 47 | 3 / 29 / 16 | 16 / 32 |
| B1-8 | 16 / 16 / 16 | 25 / 23 | 19 / 29 / 0 | 19 / 29 |
| B1-16 | 19 / 29 / 0 | 19 / 29 | 25 / 23 / 0 | 25 / 23 |
| B1-32 | 6 / 42 / 0 | 11 / 37 | 21 / 27 / 0 | 21 / 27 |
| return-A-0 † | 3 / 45 / 0 | 3 / 45 | 4 / 44 / 0 | 4 / 44 |
| return-A-2 | 7 / 41 / 0 | 7 / 41 | 4 / 44 / 0 | 4 / 44 |
| return-A-4 | 16 / 32 / 0 | 16 / 32 | 14 / 34 / 0 | 9 / 39 |
| return-A-8 | 19 / 29 / 0 | 19 / 29 | 25 / 23 / 0 | 25 / 23 |
| return-A-16 | 26 / 22 / 0 | 28 / 20 | 21 / 27 / 0 | 21 / 27 |
| return-A-32 | 25 / 23 / 0 | 25 / 23 | 15 / 33 / 0 | 15 / 33 |
| B2-0 † | 0 / 48 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| B2-2 | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| B2-4 | 1 / 47 / 0 | 1 / 47 | 1 / 31 / 16 | 2 / 46 |
| B2-8 | 15 / 17 / 16 | 26 / 22 | 19 / 13 / 16 | 27 / 21 |
| B2-16 | 12 / 36 / 0 | 12 / 36 | 25 / 23 / 0 | 25 / 23 |
| B2-32 | 26 / 22 / 0 | 26 / 22 | 29 / 19 / 0 | 29 / 19 |
| control-0 † | 11 / 21 / 16 | 12 / 36 | 34 / 14 / 0 | 30 / 18 |
| control-2 | 20 / 28 / 0 | 20 / 28 | 35 / 13 / 0 | 35 / 13 |
| control-4 | 27 / 21 / 0 | 27 / 21 | 26 / 22 / 0 | 26 / 22 |
| control-8 | 30 / 18 / 0 | 30 / 18 | 29 / 19 / 0 | 27 / 21 |
| control-16 | 17 / 31 / 0 | 17 / 31 | 31 / 17 / 0 | 31 / 17 |
| control-32 | 20 / 28 / 0 | 20 / 28 | 27 / 21 / 0 | 27 / 21 |

† Checkpoint 0 is a reported diagnostic, not graded (zero post-switch
events in the stream at k=0 for the switch stages). k=0 harm is 45–48
of 48 per switch stage in both cohorts for candidate and recent8
alike. (The development B1-0 and control-0 rows show the candidate
abstaining on pre-switch evidence — opposed_count == 2 arising from
ordinary pre-switch noise at that single early state; reported here
because checkpoint 0 is diagnostic-only and ungraded.)

Reference points on the same cohorts (pooled onset, k=2,4, all stages;
successes / harm / abstentions): the decisive comparator
`evidence_opposition_guard` scored 17/255/16 (development) and
20/236/32 (additional); its return-A pooled figures are graded above
(14 successes, 66 harm development; 13 successes, 83 harm
additional). `cumulative` — a plain relation model on all observed
events, with no signal machinery at all — scored return-A pooled
successes **58 / 66** with return-A harm **38 / 30**, beating the
candidate on both axes at the stage this experiment was built for;
`frozen_A` scored return-A **64 / 66** successes at **32 / 30** harm.
The earlier `gated_archive_prequential` baseline's pooled onset harm
was 256 (development) and 273 (additional). The privileged expected
oracle (knows the expected hidden rule, not the realized stochastic
flip; a reference only, never a baseline) pooled onset
successes/harm were 174/114 (development) and 168/120 (additional):
onset tasks remain largely solvable, and every realizable learner
here remains far from that.

**Retention note:** the retained knowledge itself is not the problem.
frozen_A and cumulative both demonstrate on these cohorts that the
pre-switch rule, retained plainly, scores 58–66 successes at return-A
onset with harm 30–38. What failed is the *gate* on using it: the
signal-gated recovery engages too rarely to inherit that performance,
and where it does not engage the learner is recent8 (development
return-A successes identical, 23 = 23) or the abstaining guard.

**Generalization level:** at most handoff level 2–3 (choosing among /
applying already-supplied representations under a rule change, plus
designer-supplied signal, concordance, and routing rules). The A/B
rules, span statistic, windows, archive definition, and decision rule
are all designer-supplied. No level-6 or novel-representation claim is
made. Nothing in this experiment speaks to general regime
identification: the archive is global and unsegmented, and B2 recovery
was pre-registered as not expected (and did not occur).

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; pooled onset
  harm 262 (development) and 231 (additional) vs recent8 262 / 254 —
  on the development cohort the candidate's onset harm is *identical*
  to the unprotected acting model's; k=0 diagnostic harm 45–48/48 at
  every switch stage in both cohorts.
- **Actual harmful TRAIN-acquisition actions** (external actor, counted
  once per seed, never netted against TEST results): development — A
  264, B1 80, return-A 48, B2 94 harmful of 1,248 main-schedule actions
  (plus control continuation 62 of 192); additional — A 239, B1 75,
  return-A 53, B2 80 of 1,248 (plus control 68 of 192). Label flips in
  the reported stream: development 47 (main) + 8 (control); additional
  47 (main) + 7 (control).
- **Failed-by-abstention:** candidate onset abstentions 0/288
  (development) and 32/288 (additional); persistence abstentions at
  k=8 on the development cohort (B1-8, B2-8, one state each) and the
  additional cohort (B2-8, one state); 0 at every graded stationary
  control checkpoint and 0 at k=32 in both cohorts. The always-abstain
  baseline is 48/48 abstentions with 0 successes and 0 harm at every
  checkpoint, as registered.
- **Additional requested observations / learner acquisition actions:**
  0 / 0, exactly as frozen.
- **False confidence and unnecessary abstention:** false confidence
  remains the dominant term — at 5 of 6 return-A onset states per
  cohort (and nearly every B1/B2 onset state) the candidate acts
  through the stale recent8 model exactly as the unprotected baseline
  does, because its recovery test is one concordant event short
  (concordant_count == 1 in 5/6 return-A states, both cohorts).
  Unnecessary abstention at graded checkpoints is zero on stationary
  evidence in both cohorts, and false recovery at B1 — the
  pre-registered dangerous direction — never occurred (0/6 states,
  both cohorts): the gate is selective, it is the *sensitivity* that
  failed.
- **Report integrity / provenance:** checkpoint SHA256 replay identity
  held at every checkpoint in both cohorts; hashes validate record
  integrity only, not the truth of the (deliberately corrupted) public
  reports.

## Scientific conclusion

**Failed** — per the protocol's own grading definitions: criteria
1–4 FAIL on the additional cohort (in fact all four FAIL on both
cohorts), which is the protocol's Failed condition. It is **not** a
Regression under any clause of the protocol's definition: pooled onset
harm does not exceed recent8's on both cohorts (equal on development,
262 = 262; below on additional, 231 < 254), stationary-control
successes do not fall below recent8 − 6 on both cohorts (equal on
development; above on additional), and the full unit suite and
historical transfer benchmark pass. The cumulative-dominance cap is
also triggered on both cohorts (margins 35 and 48 vs the cap's 8), so
even the passing criteria could not have carried a Demonstrated grade.

What the experiment genuinely establishes: the recovery *mechanism*
works where it engages and is safe where it should not engage. In the
additional cohort's single firing state (seed 323001, return-A-4)
archive play scored 11 successes / 5 harm against recent8's and the
guard's identical 6 / 10 in that state — a genuine +5 / −5 conversion.
In the development cohort's single firing state (seed 322003,
return-A-4) archive play scored 9 successes where the guard abstained
(0 successes, 16 abstentions), at harm 7 — identical to recent8's
outcome in that same state, so that state evidences the productivity
conversion but nothing about harm. And false recovery at B1 never
occurred in either cohort. What failed is *engagement*: requiring BOTH
newest events to be archive-concordant squares a per-event concordance
probability that these cohorts realize at roughly one-half to
two-thirds, leaving concordant_count == 1 — one event short — in 5 of
6 return-A onset states in both cohorts, exactly the sparsity the
protocol pre-registered as its first expected failure mode. The
pre-registered design expectation (engagement at ≈0.35–0.42 of
return-A states, ≈2–2.5 of 6) was itself optimistic against the
realized per-event rates. Meanwhile the plain cumulative baseline —
no signal, no gate, just all retained events — captures nearly all of
frozen_A's return-A performance on these cohorts (58/66 successes,
38/30 harm), which is the experiment's sharpest lesson: at a first
return in this simulator, retained knowledge does not need a sparse
gate to be useful; the gate's selectivity was bought at the price of
the recovery it existed to enable.

No frozen parameter, threshold, seed, or checkpoint is changed in
response to these results. Any revised hypothesis gets a NEW protocol
and NEW seeds.

## Next limitation (selected for the next cycle)

**P1 — recovery engagement sparsity: the both-events archive-concordance
requirement engages recovery at only 1 of 6 return-A onset states per
cohort (concordant_count == 1 in 5 of 6 states in both cohorts), so
signal-gated recovery neither approaches frozen_A (64 / 66 pooled
return-A onset successes) nor beats plain cumulative retention
(58 / 66 successes at 38 / 30 harm, vs the candidate's 23 / 18
successes at 73 / 78 harm) — and pooled onset harm stays at recent8's
level on the development cohort.** Measurable form for the next
protocol: at return-A checkpoints 2 and 4 on NEW seed cohorts, whether
a recovery rule whose concordance test is less sparse — engaging on
weaker per-state concordance evidence — can engage at materially more
return-A onset states and exceed cumulative's return-A successes
without false recovery at B1 (≤1 of 6 states) and without pooled onset
harm above the evidence-opposition guard's level on the same cohort —
against recent8, cumulative, frozen_A, the evidence-opposition guard,
and this experiment's candidate as baselines. This stays inside
Priority 1 items 2, 3, and 4 and does not re-tune any parameter of the
four graded onset experiments against their inspected cohorts; the
revised hypothesis gets its own frozen protocol and NEW seeds.
(Secondary, recorded but not selected: the opposed_count == 0 return-A
blind spot — 2 of 6 additional-cohort states unreachable by design —
and the near-silence of the abstention branch on the development
cohort's onset states, where opposed_count == 1 dominated.)

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.evidence_opposition_retained_recovery_benchmark --cohort development
python -m benchmarks.evidence_opposition_retained_recovery_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results above;
it does not make the seeds un-inspected.
