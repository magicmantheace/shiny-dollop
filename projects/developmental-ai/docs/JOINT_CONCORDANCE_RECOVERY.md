# Joint concordance recovery — per-event joint archive recovery at return-A

**30 October 2026. Status: optional, simulated, unpromoted. No default-controller
promotion, no PR merge, no D1–D10 or V2A/V2B roadmap change, no AthenZ/Synveil
integration.**

## Experiment identity

- **Name and purpose:** `joint_concordance_recovery` — whether a recovery rule
  whose concordance test is less sparse than the graded retained-recovery
  candidate's pooled both-events test can engage at materially more return-A
  onset states, exceed plain cumulative retention's return-A successes, keep
  false recovery at B1 at or below 1 of 6 states, and keep pooled onset harm at
  or below the evidence-opposition guard's level on the same cohort. This tests
  the limitation selected after the preceding experiment was graded Failed:
  recovery engagement sparsity (the both-events archive-concordance requirement
  engaged at only 1 of 6 return-A onset states per cohort, with
  concordant_count == 1 in 5 of 6 states in both cohorts). Build Order
  Priority 1 (Independent Learning), items 2 + 3 joined to item 4; handoff §8
  slow or incorrect recovery of old knowledge.
- **Candidate:** `JointConcordanceRecoveryMemory`
  (`developmental_ai/joint_concordance_recovery.py`) — IDENTICAL to the graded
  `EvidenceOppositionRecoveryMemory` in acting model (recent8 exactly),
  immediate evidence-opposition signal (newest 2 vs 24-event reference,
  opposed_count), retained archive (events[:N-26]), per-event archive
  concordance definition, and archive-only recovery model. The SINGLE changed
  element is the recovery test: a per-event JOINT flag (a newest event that is
  BOTH archive-concordant AND reference-opposed, on the SAME event). Decision
  order: (1) RECOVERY — if joint_count >= 1, act through the archive model;
  (2) ABSTENTION — else if opposed_count == 2, abstain as the guard;
  (3) else recent8 exactly. Minimum 27 events, else an all-available fallback
  (never exercised in evaluation). Separate optional learner; the default
  controller and all existing learners are untouched; the graded guard and the
  graded retained-recovery candidate appear only as baselines.
- **Branch and commits:** `developmental-ai/joint-concordance-recovery`
  (forked from `developmental-ai/evidence-opposition-retained-recovery` @
  `594a8b0`, itself forked from `developmental-ai/evidence-opposition-onset-guard`
  @ `9c6e5c2`, itself forked from `developmental-ai/first-contact-onset-guard`
  @ `8e0a686`, itself forked from `developmental-ai/early-post-switch-adaptation`
  @ `edd371f`, itself forked from `developmental-ai/standalone-policy-review`
  @ `6e0cac5`). Protocol frozen at `0f23f44`; implementation at `bcf36ea`;
  evaluation at `d4c9efb`. This grading report is committed on top of the
  evaluation commit.
- **Frozen protocol:** `benchmarks/joint_concordance_recovery_protocol.json`
  (schema `developmental-ai.joint-concordance-recovery-protocol/v1`, frozen
  2026-10-30, before any implementation, unit test, harness, or score
  inspection for this experiment).
- **Cohorts:** development 332003/332021/332039 and additional
  333001/333017/333041 — NEW at freeze, disjointness verified by project-wide
  search before the freeze commit. Both cohorts are now **INSPECTED** and must
  never be re-tuned against. Detailed results:
  `benchmarks/joint_concordance_recovery_results.json` (development) and
  `benchmarks/joint_concordance_recovery_additional_results.json` (additional).
- **Simulator:** `StochasticWorld` unchanged (authored span-to-effect bands,
  two public numeric features). Schedule per seed: A → B1 (inverted) →
  return-A → B2 (inverted), plus a stationary A→A control arm. True outcomes
  flip with probability 1/8; TRAIN reports flip with probability 1/20. The
  learner sees only the public reported stream — no phase label, rule
  identity, or true outcome. Checkpoints 0/2/4/8/16/32 for every stage; 48 TEST
  episodes per cohort cell (16 per seed, same indices re-scored at every
  checkpoint, never trained on). Checkpoint 0 is a reported diagnostic, NOT
  graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s tests`:
  920 tests OK in the implementation stage, 920 tests OK in the evaluation
  stage, and 920 tests OK again in this grading stage (run this pass; the
  grading-stage changes are documentation only, no code changed). Focused
  candidate tests: 25/25 PASS in the implementation stage.
- Historical regressions: **PASS** — `python -m benchmarks.transfer_benchmark`
  (unchanged) exited 0 in the evaluation stage, and exited 0 again when
  re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts were run
  with no change to any frozen parameter, threshold, seed, or checkpoint.
  Every checkpoint entry carries the candidate's full decision record
  (immediate signal records, archive concordance records, per-event joint
  flags/records, opposed / matched / concordant / archive-matched / joint
  counts, branch taken, recovery-fired / abstained / gate-evaluable flags,
  acting source, plus the records-only pooled-rule would-fire derivation), a
  checkpoint SHA256, and restore-replay identity verified true at every
  checkpoint in both cohorts (script-verified again in this grading stage; no
  criterion-7 field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the evaluation
  or grading commit was checked; no CI is claimed for `d4c9efb` or for this
  grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results in
this grading stage, not hand-copied. Denominators are exact episode counts
(48 per stage-checkpoint cell; 96 per pooled return-A onset figure; 288 per
pooled all-stage onset figure); decision-record denominators are
seed-checkpoint states (6 per stage per cohort at checkpoints 2 and 4).

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 1 | Return-A recovery successes (≥40% of frozen_A AND ≥ guard + 16 AND > cumulative, pooled k=2,4) | **FAIL** | **FAIL** |
| 2 | Recovery engagement from decision records alone (≥4/6 return-A states; ≤1/6 B1 states) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 4 | Return-A onset harm (≤ guard AND ≤60% of recent8, pooled k=2,4) | **FAIL** | **PASS** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8) | **FAIL** | **FAIL** |
| 6 | Stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

No separate cumulative-dominance cap exists in this protocol: criterion 1
sub-condition (c) already requires exceeding cumulative, and it is graded
there — and it fails on both cohorts (below).

### Criterion 1 — return-A recovery successes, incl. exceeding cumulative (FAIL, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **56** against
frozen_A **68** — the 40% floor passes (56 × 5 = 280 ≥ 68 × 2 = 136) — and
against the guard-relative floor of guard + 16 = **38** (guard scored 22) —
passes. Sub-condition (c) **fails**: cumulative scored **60**, and the
candidate must strictly exceed it (≥ 61). Additional: candidate **52**
against frozen_A **60** (40% floor passes: 260 ≥ 120) and guard + 16 = **23**
(guard scored 7) — passes; sub-condition (c) **fails**: cumulative scored
**64** (required ≥ 65). This is exactly the protocol's pre-registered central
risk (expected failure mode 1, "exceed-cumulative shortfall"), and the
per-state records localize it completely: **at every return-A onset state
where recovery fired, the candidate's successes and harm are identical to
cumulative's in that state** (development firing states 9/7, 9/7, 11/5, 10/6,
10/6 successes/harm; additional 10/6, 10/6, 12/4, 10/6). The entire deficit
comes from the single non-engaging return-A state in each cohort —
development seed 332021 at k=2 (candidate 7 successes / 9 harm vs cumulative
11 / 5, a −4 gap = the pooled −4 deficit) and additional seed 333017 at k=2
(candidate 0 / 16 vs cumulative 12 / 4, a −12 gap = the pooled −12 deficit).
Both non-engaging states are opposed_count == 0 states — the protocol's
pre-registered blind spot (failure mode 4): the joint test requires
opposition on the joint event itself, so a return-A state whose newest events
agree with the already-partly-slid reference window cannot recover. The
additional state had concordant_count == 1 (archive signal present, opposition
absent); the development state had concordant_count == 0 as well.

### Criterion 2 — recovery engagement, from decision records alone (PASS, both cohorts)

Development: recovery fired at **5 of 6** return-A onset states (required
≥ 4; the preceding candidate fired at 1 of 6) and at **1 of 6** B1 onset
states (required ≤ 1). Additional: recovery fired at **5 of 6** return-A
states and **0 of 6** B1 states. B2 engagement was 0 of 6 in both cohorts,
exactly the pre-registered expectation (archive and reference majorities
agree at B2). For continuity, the preceding candidate's pooled rule
(concordant_count == 2 AND opposed_count >= 1), derived records-only from
this candidate's recorded counts, would have fired at only 3 of 6
(development) and 2 of 6 (additional) return-A states — the per-event joint
test is genuinely less sparse than the pooled test it replaced, on the same
decision records. The gate change worked as designed; criterion 1 shows why
engagement alone was not enough.

### Criterion 3 — pooled onset harm not above the guard (PASS, both cohorts)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm **165**
vs guard **166** — sub-condition (a) passes by a single action — and
candidate harm ≤ recent8 in **5 of 6** individual cells (required ≥ 5; the
exception is B1-2, 48 vs recent8 47). Additional: candidate **156** vs guard
**185** — (a) passes — with **6 of 6** cells ≤ recent8. Against recent8's
pooled onset harm the candidate cuts harm by a third or more on both cohorts
(165 vs 248 development; 156 vs 261 additional) — a large improvement over
the preceding candidate, whose pooled onset harm was 262 / 231 and failed
this comparison outright. The development pass is narrow (one action under
the guard) and is reported as such, not rounded into comfort.

### Criterion 4 — return-A onset harm (FAIL development, PASS additional)

Development: pooled return-A harm candidate **40** vs guard **42** —
(a) passes — but vs recent8 **63** the 60% ceiling is 37.8 — (b) **fails**
by 2.2 actions. Additional: candidate **44** vs guard **73** — (a) passes —
and vs recent8 **86** the ceiling is 51.6 — (b) passes. For reference,
cumulative's return-A harm is 36 / 32 and frozen_A's is 28 / 36 on these
cohorts: archive-model play in firing states carries its own nonzero harm
(design approx 4–8 per firing state, realized 5–7), and with five firing
states the development cohort's pooled return-A harm lands just above the
60% line even though it beats the abstaining guard.

### Criterion 5 — release and productivity by checkpoint 32 (FAIL, both cohorts)

Development: k=32 abstentions **0/144** — (a) passes — but successes **58**
vs recent8 **77** (required ≥ 69) — (b) **fails** by 11. Additional:
abstentions **16/144** — (a) passes — but successes **77** vs recent8 **86**
(required ≥ 78) — (b) **fails** by a single success. The mechanism is
localized and is this experiment's sharpest new finding: **the gate never
expires.** Long after onset, when recent8 has adapted to the current rule, a
single spurious joint event can still route the learner to the stale global
archive for a full 16-episode checkpoint. Development k=32: a false recovery
at B1 (seed 332003) scored 0 successes / 16 harm vs recent8's 10 / 6, and a
false recovery at B2 (seed 332021) scored 0 / 16 vs recent8's 10 / 6 — two
states costing −20 successes against a +1 at return-A-32, netting the −19
pooled gap. Additional k=32: a single abstention state at B1 (seed 333001,
opposed_count == 2) scored 0 successes (16 abstentions) vs recent8's 9 — the
entire −9 pooled gap; every other additional k=32 state is identical to
recent8. Persistence at k=8/16 is milder but present (reported in the table
below; e.g. additional B2-8 abstentions in 2 of 3 states cost successes
7 vs recent8 30 there, partly recovered by k=16). Release in the narrow
sense (the gate does not stay shut) passes; productivity at k=32 does not.

### Criterion 6 — stationary control downstream selectivity (PASS, both cohorts)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32) abstentions
**0/240**, successes **97** vs recent8 91 (required ≥ 85), harm **143** vs
recent8 149. Recovery engaged at 1 of 15 graded control states. Additional:
abstentions **0/240**, successes **130** vs recent8 120, harm **110** vs
recent8 120; recovery engaged at 3 of 15 graded control states — inside the
protocol's design expectation of approx 2–4 of 15. As pre-registered, the
archive model is itself a valid stationary model, so control-arm engagement
costs nothing measurable downstream on either cohort; criterion 6 grades
those totals, and they pass with margin.

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions, actual
harmful / productive / neutral outcomes, reported harmful, and label flips
for every stage; per-method successes / harmful TEST actions / abstentions /
attempted tasks at every checkpoint; the candidate's full decision record
(per-event immediate signal records, archive concordance records, and
per-event joint flags/records with every field the protocol lists, plus
joint / opposed / matched / concordant / archive-matched counts, branch,
recovery-fired / abstained / gate-evaluable flags, acting source, and the
records-only pooled-rule would-fire derivation) at every checkpoint;
checkpoint SHA256; and restore-replay identity (true at every checkpoint in
both cohorts, script-verified in this stage — no field missing anywhere).
Learner information-acquisition actions = 0, additional requested
observations = 0, and learner training actions = 0 throughout, as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions,
48 episodes per cell).

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| B1-2 | 0 / 48 / 0 | 1 / 47 | 0 / 32 / 16 | 0 / 48 |
| B1-4 | 1 / 31 / 16 | 2 / 46 | 9 / 23 / 16 | 9 / 39 |
| B1-8 | 22 / 26 / 0 | 22 / 26 | 29 / 19 / 0 | 29 / 19 |
| B1-16 | 7 / 25 / 16 | 18 / 30 | 13 / 35 / 0 | 13 / 35 |
| B1-32 | 10 / 38 / 0 | 20 / 28 | 22 / 10 / 16 | 31 / 17 |
| return-A-0 † | 9 / 39 / 0 | 9 / 39 | 13 / 35 / 0 | 1 / 47 |
| return-A-2 | 26 / 22 / 0 | 13 / 35 | 20 / 28 / 0 | 3 / 45 |
| return-A-4 | 30 / 18 / 0 | 20 / 28 | 32 / 16 / 0 | 7 / 41 |
| return-A-8 | 19 / 29 / 0 | 9 / 39 | 24 / 24 / 0 | 26 / 22 |
| return-A-16 | 32 / 16 / 0 | 32 / 16 | 31 / 17 / 0 | 31 / 17 |
| return-A-32 | 35 / 13 / 0 | 34 / 14 | 26 / 22 / 0 | 26 / 22 |
| B2-0 † | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| B2-2 | 0 / 0 / 48 | 2 / 46 | 1 / 31 / 16 | 1 / 47 |
| B2-4 | 2 / 46 / 0 | 2 / 46 | 6 / 26 / 16 | 7 / 41 |
| B2-8 | 30 / 18 / 0 | 30 / 18 | 7 / 9 / 32 | 30 / 18 |
| B2-16 | 14 / 34 / 0 | 14 / 34 | 21 / 27 / 0 | 21 / 27 |
| B2-32 | 13 / 35 / 0 | 23 / 25 | 29 / 19 / 0 | 29 / 19 |
| control-0 † | 19 / 29 / 0 | 19 / 29 | 26 / 22 / 0 | 26 / 22 |
| control-2 | 29 / 19 / 0 | 23 / 25 | 27 / 21 / 0 | 26 / 22 |
| control-4 | 11 / 37 / 0 | 11 / 37 | 24 / 24 / 0 | 24 / 24 |
| control-8 | 11 / 37 / 0 | 11 / 37 | 30 / 18 / 0 | 21 / 27 |
| control-16 | 20 / 28 / 0 | 20 / 28 | 21 / 27 / 0 | 21 / 27 |
| control-32 | 26 / 22 / 0 | 26 / 22 | 28 / 20 / 0 | 28 / 20 |

† Checkpoint 0 is a reported diagnostic, not graded (zero post-switch events
in the stream at k=0 for the switch stages). k=0 harm is 35–48 of 48 per
switch stage across cohorts and methods.

Reference points on the same cohorts (pooled onset, k=2,4, all stages;
successes / harm / abstentions): the decisive gate comparison
`evidence_opposition_retained_recovery` (identical but for the recovery test)
scored 48/176/64 (development) and 44/180/64 (additional) pooled onset, with
return-A pooled successes 44 / 28 — the joint test improves on it on every
pooled onset axis. The harm comparator `evidence_opposition_guard` scored
26/166/96 (development) and 23/185/80 (additional). `cumulative` scored
return-A pooled successes **60 / 64** at return-A harm **36 / 32** — still
ahead of the candidate at return-A (criterion 1), for the single-state reason
documented there. `frozen_A` scored return-A **68 / 60** successes at
**28 / 36** harm. The privileged expected oracle (knows the expected hidden
rule, not the realized stochastic flip; a reference only, never a baseline)
pooled onset successes/harm were 186/102 (development) and 176/112
(additional): onset tasks remain largely solvable, and every realizable
learner here remains far from that.

**Retention note:** at a genuine return, the joint-gated recovery now
inherits retained knowledge about as well as plain cumulative retention does
*in the states where it engages* — firing-state outcomes are identical to
cumulative's state by state. What separates them is coverage (one blind-spot
state per cohort) and, at later checkpoints, the unexpired gate's occasional
stale-archive routing (criterion 5). The preceding experiment's lesson —
that a sparse gate forfeits the recovery it exists to enable — is answered
for engagement; it is not yet answered for coverage or for persistence.

**Generalization level:** at most handoff level 2–3 (choosing among /
applying already-supplied representations under a rule change, plus
designer-supplied signal, concordance, and routing rules). The A/B rules,
span statistic, windows, archive definition, joint test, and decision rule
are all designer-supplied. No level-6 or novel-representation claim is made.
Nothing in this experiment speaks to general regime identification: the
archive is global and unsegmented, and B2 recovery was pre-registered as not
expected (and did not occur at onset).

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; pooled onset harm
  165 (development) and 156 (additional) vs recent8 248 / 261 and vs the
  guard 166 / 185 — the candidate is the least harmful realizable onset
  method on the additional cohort and effectively tied-least on development.
  That onset safety does not persist costlessly: at k=32 the two development
  false-recovery states caused 16/16 harm each (criterion 5).
- **Actual harmful TRAIN-acquisition actions** (external actor, counted once
  per seed, never netted against TEST results): development — A 256, B1 78,
  return-A 48, B2 86 harmful of 1,248 main-schedule actions (plus control
  continuation 62 of 192); additional — A 262, B1 83, return-A 52, B2 83 of
  1,248 (plus control 62 of 192). Label flips in the reported stream:
  development 38 (main) + 11 (control); additional 51 (main) + 6 (control).
- **Failed-by-abstention:** candidate onset abstentions 64/288 on both
  cohorts; k=32 abstentions 0/144 (development) and 16/144 (additional, the
  single B1 state in criterion 5); 0 at every graded stationary control
  checkpoint in both cohorts. The always-abstain baseline is 48/48
  abstentions with 0 successes and 0 harm at every checkpoint, as registered.
- **Additional requested observations / learner acquisition actions:**
  0 / 0, exactly as frozen.
- **False confidence and unnecessary abstention:** at onset, false recovery
  at B1 — the pre-registered dangerous direction — occurred at 1 of 6
  development states (at the criterion's ceiling) and 0 of 6 additional
  states, and B2 recovery never engaged at onset. The false-confidence
  problem has moved rather than vanished: it now appears *late*, as
  stale-archive routing at k=32 (two development states at 0/16) and one
  late abstention (additional B1-32), after recent8 has already adapted.
  Unnecessary abstention on stationary evidence at graded checkpoints is
  zero in both cohorts.
- **Report integrity / provenance:** checkpoint SHA256 replay identity held
  at every checkpoint in both cohorts; hashes validate record integrity
  only, not the truth of the (deliberately corrupted) public reports.

## Scientific conclusion

**Failed** — per the protocol's own grading definitions: criterion 1 FAILs
on the additional cohort (in fact on both cohorts, on the exceed-cumulative
sub-condition alone), which is the protocol's Failed condition; criterion 4
also FAILs on development and criterion 5 FAILs on both cohorts. It is
**not** a Regression under any clause of the protocol's definition: pooled
onset harm does not exceed recent8's on either cohort (165 < 248; 156 < 261),
stationary-control successes do not fall below recent8's (97 > 91; 130 > 120,
let alone by more than 6 on both cohorts), and the full unit suite and
historical transfer benchmark pass.

What the experiment genuinely establishes — and this is a real advance over
the preceding candidate, recorded with the failure, not instead of it: the
per-event joint test **solves the engagement problem it was designed to
solve.** Recovery engagement rose from 1 of 6 to 5 of 6 return-A onset states
on both cohorts (criterion 2 PASS), the records-only pooled-rule derivation
(3/6 and 2/6 on the same records) shows the gain is the joint test's, pooled
onset harm fell to at-or-below the guard's level on both cohorts (criterion 3
PASS, development by one action), and in every firing state the candidate
matched cumulative exactly. Three distinct limits remain, each localized by
the records: (i) **coverage** — the one non-engaging return-A state per
cohort is an opposed_count == 0 blind-spot state, and it accounts for the
*entire* exceed-cumulative deficit (−4 development, −12 additional);
(ii) **archive harm at scale** — five firing states' archive play puts
development return-A harm (40) just over the 60%-of-recent8 ceiling (37.8),
even while beating the guard; (iii) **no expiry** — the recovery and
abstention branches stay armed indefinitely, and single spurious firings at
k=32 (two stale-archive routings scoring 0/16 in development; one abstention
in additional) fail the release/productivity criterion on both cohorts.
Plain cumulative retention remains, on these cohorts, the strongest simple
return-A policy overall — but by a margin that is now one state wide, not
the 35/48-success chasm of the preceding experiment.

No frozen parameter, threshold, seed, or checkpoint is changed in response
to these results. Any revised hypothesis gets a NEW protocol and NEW seeds.

## Next limitation (selected for the next cycle)

**P1 — gate persistence without expiry: the joint recovery and abstention
branches remain armed at every checkpoint, so long after onset — when the
recent window has already adapted to the current rule — a single spurious
joint event can still route the learner to the stale global archive for a
full checkpoint (development k=32: two such states scoring 0 successes /
16 harm each, vs recent8's 10 / 6; additional k=32: one late abstention
state costing 9 successes), failing release/productivity at k=32 on both
cohorts (58 vs recent8 77; 77 vs 86) even though onset behavior improved on
nearly every axis.** Measurable form for the next protocol: on NEW seed
cohorts, whether a recovery/abstention gate whose authority is bounded to
the onset window — by an evidence-derived condition, not by any phase or
checkpoint information the learner cannot see — can preserve the joint
test's onset engagement and harm profile (criteria 1–4 analogues) while
restoring k=32 productivity to within 8 successes of recent8, against
recent8, cumulative, frozen_A, the evidence-opposition guard, the graded
retained-recovery candidate, and this experiment's candidate as baselines.
This stays inside Priority 1 items 2, 3, and 4 and does not re-tune any
parameter of the five graded onset experiments against their inspected
cohorts; the revised hypothesis gets its own frozen protocol and NEW seeds.
(Secondary, recorded but not selected: the opposed_count == 0 return-A
blind spot — one non-engaging state per cohort in this experiment,
accounting for the entire exceed-cumulative deficit of −4 / −12 successes;
and development return-A archive harm at five firing states landing just
above the 60%-of-recent8 ceiling, 40 vs 37.8.)

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.joint_concordance_recovery_benchmark --cohort development
python -m benchmarks.joint_concordance_recovery_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results above;
it does not make the seeds un-inspected.
