# Extended reference joint recovery — widened onset-signal reference

**1 November 2026 (graded 1 November 2026). Status: optional, simulated,
unpromoted. No default-controller promotion, no PR merge, no D1–D10 or
V2A/V2B roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `extended_reference_joint_recovery` — whether
  widening the immediate evidence-opposition signal's REFERENCE WINDOW
  from the 24 events preceding the newest 2 to the 50 events preceding
  them can restore return-A recovery engagement AT checkpoint 2, the
  point where the graded long-disagreement experiment localized its
  failure (newest-2 joint/opposition signal empty in 5 of 6 return-A
  k=2 states across its cohorts, because the 24-event reference holds
  only ~2–3 events per span). Build Order Priority 1 (Independent
  Learning), items 2 + 3 + 4; handoff §8 slow or incorrect recovery of
  old knowledge / weak uncertainty calibration / first-contact
  overconfidence. The protocol's PRIMARY criterion is criterion 2,
  with its checkpoint-2 sub-condition (a) as the headline; criteria 4
  (return-A harm) and 5 (release by k=32) are its co-graded guards.
  They are reported first, second, and third below, as the protocol
  requires.
- **Candidate:** `ExtendedReferenceJointRecoveryMemory`
  (`developmental_ai/extended_reference_joint_recovery.py`) —
  IDENTICAL to the graded `LongDisagreementJointRecoveryMemory` in
  acting model (recent8 exactly), retained archive (events[:N-26] —
  the original partition, NOT redefined by the widening), per-event
  archive concordance, joint test form (joint_count >= 1), archive-only
  recovery model, abstention trigger form (opposed_count == 2), and
  the full three-leg authority condition (local disagreement,
  corroboration recent_concordant_count >= 2, long disagreement; the
  strict-majority rule D * 2 > C in both windows). The SINGLE changed
  element is the immediate signal's reference window: the span-majority
  expectation for each newest-2 event is computed over the 50 events
  immediately preceding the newest window (indices N-52..N-3) instead
  of the 24 events preceding it (N-26..N-3). The decision record
  additionally carries the LEGACY reference-24 signal records
  (records-only, never a decision input) so the graded long
  candidate's rule is derivable from the records alone. Minimum 52
  events for the extended signal (never exercised in evaluation; all
  checkpoints >= 240 events). Separate optional learner; the default
  controller and all existing learners are untouched; the graded
  guard, retained-recovery, joint, bounded-authority, and
  long-disagreement candidates appear only as baselines.
- **Branch and commits:** `developmental-ai/extended-reference-joint-recovery`
  (forked from `developmental-ai/long-disagreement-joint-recovery` @
  `fd78867`). Protocol frozen at `58ddc20`; implementation at
  `314d807`; evaluation at `3c078e5`. This grading report is committed
  on top of the evaluation commit.
- **Frozen protocol:** `benchmarks/extended_reference_joint_recovery_protocol.json`
  (schema `developmental-ai.extended-reference-joint-recovery-protocol/v1`,
  frozen 2026-11-01, before any implementation, unit test, harness, or
  score inspection for this experiment).
- **Cohorts:** development 362003/362021/362039 and additional
  363001/363017/363041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit. Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/extended_reference_joint_recovery_results.json`
  (development) and
  `benchmarks/extended_reference_joint_recovery_additional_results.json`
  (additional).
- **Simulator:** `StochasticWorld` unchanged. Schedule per seed: A →
  B1 (inverted) → return-A → B2 (inverted), plus a stationary A→A
  control arm. True outcomes flip with probability 1/8; TRAIN reports
  flip with probability 1/20. The learner sees only the public reported
  stream — no phase label, rule identity, or true outcome. Checkpoints
  0/2/4/8/16/32 for every stage; 48 TEST episodes per cohort cell (16
  per seed, same indices re-scored at every checkpoint, never trained
  on). Checkpoint 0 is a reported diagnostic, NOT graded.

## Verification

- Unit tests: **PASS** — full suite `python -m unittest discover -s
  tests`: 995 tests OK in the implementation stage, 995 tests OK in
  the evaluation stage, and 995 tests OK again in this grading stage
  (run this pass; the grading-stage changes are documentation only, no
  code changed). Focused candidate tests: 26/26 PASS in the
  implementation stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the
  evaluation stage, and exited 0 again when re-run in this grading
  stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts
  were run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's full
  decision record (extended-reference signal records, legacy
  reference-24 signal records, archive concordance records, per-event
  joint and legacy joint flags/records, and the full authority record
  — expiry span records, comparable/disagreeing counts,
  stable_disagreement flag, preceding span records, preceding
  comparable/disagreeing counts, preceding stable flag,
  long_disagreement flag, recovery_arming_leg, per-event last-8
  archive-concordance records, recent_concordant_count, armed and
  would-fire flags — plus every count, branch, recovery-fired /
  abstained / gate-evaluable flags, acting source, and the
  records-only legacy-long-rule, unexpired-joint-rule, and
  bounded-authority-rule derivations), a checkpoint SHA256, and
  restore-replay identity verified true at every checkpoint in both
  cohorts (script-verified again in this grading stage; no
  criterion-7 field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `3c078e5` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results
in this grading stage, not hand-copied. Denominators are exact episode
counts (48 per stage-checkpoint cell; 96 per pooled return-A onset
figure; 288 per pooled all-stage onset figure); decision-record
denominators are seed-checkpoint states (3 per stage per cohort at
checkpoint 2 alone; 6 per stage per cohort pooled at checkpoints 2
and 4; 9 switch-stage states per cohort at checkpoint 32). Criterion
2, this experiment's PRIMARY criterion, is reported first (its
checkpoint-2 sub-condition (a) first within it), and criteria 4 and
5, its co-graded guards, next, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 2 | PRIMARY engagement restored and selective, from decision records alone ((a) recovery TAKEN ≥2/3 return-A states AT checkpoint 2 alone; (b) pooled k=2,4 TAKEN ≥4/6; (c) B1 pooled ≤1/6) | **PASS** | **PASS** |
| 4 | Return-A onset harm (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **PASS** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 switch-stage k=32 states, from records) | **PASS** | **PASS** |
| 1 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4; cumulative/joint/bounded/long reported, not graded) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **FAIL** | **PASS** |
| 6 | Stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 2 (PRIMARY) — checkpoint-2 engagement restored and selective (PASS, both cohorts)

**(a) HEADLINE, checkpoint 2 alone:** recovery was TAKEN at **2 of 3**
return-A checkpoint-2 states on development (seeds 362021, 362039;
required ≥ 2) and at **3 of 3** on additional (required ≥ 2) — both
PASS, and a sharp contrast with the graded long cohorts, where k=2
recovery took in only 1 of 6 states across cohorts. **(b) Pooled
k=2,4:** TAKEN at **4 of 6** return-A states development and **6 of
6** additional (required ≥ 4). **(c) Selectivity:** B1 pooled TAKEN
**0 of 6** on both cohorts (required ≤ 1); B2 TAKEN 0 of 6 on both.
Every taken state on both cohorts reports arming leg `long`;
would-fire-but-disarmed return-A states are **0 of 6** on both
cohorts; abstention never fired at a return-A onset state (it is
disarmed there by design, as in the preceding protocols), with
abstention would-fire-but-disarmed counts of 2 (development) and 3
(additional) among the pooled return-A states. The records, however,
overturn the experiment's premise, and this report does not soften
that:

- **The widened reference changed NO return-A recovery engagement on
  either cohort.** The candidate's TAKEN states are IDENTICAL to the
  records-only legacy reference-24 derivation at every return-A onset
  state in both cohorts (k=2 alone: 2/3 development and 3/3
  additional, exactly the legacy derivation's counts; pooled k=2,4:
  4/6 and 6/6, again identical). On these cohorts the 24-event
  reference was NOT the binding constraint at k=2: every state the
  extended signal engaged, the legacy signal engaged too, and the one
  non-taken development k=2 state (seed 362003) was silent under BOTH
  references with joint_count == 0, opposed_count == 0, and
  concordant_count == 0 — an information-empty newest draw (the
  protocol's pre-registered failure mode 1), which no reference width
  can repair.
- So criterion 2's PASS is **not credited to the reference widening**.
  Engagement on these cohorts was determined by the newest draws
  themselves (and, as in the long experiment, every taken state was
  armed via the long-disagreement reporting leg). Reference width
  joins disagreement-age authority in the list of mechanisms that
  changed no return-A outcome: across the last two experiments the
  binding variable at k=2 has been whether the two newest draws carry
  a matched archive-concordant event at all, not how the expectation
  they are compared against is computed and not who is allowed to act
  on it.
- The widening's realized effects are elsewhere, and small: score
  diffs vs the graded long baseline method at only **2 of 72**
  checkpoints development (extended-only late recovery at return-A
  k=16 and k=32, seed 362021, scoring 9 successes / 7 harm at both
  checkpoints against the long baseline's 10/6 and 13/3 there) and **5 of 72**
  additional, all five being abstention-branch differences at B1/B2
  (extended-reference abstentions at B1-2 seed 363001, B2-4 seed
  363001, B2-2 seed 363017, and B1-8 seed 363041, plus one reverse
  case at B2-4 seed 363041 where the candidate acted and the long
  baseline abstained). Branch diffs vs the legacy derivation total
  **3 (development) / 6 (additional)**, none of them a return-A onset
  state.

### Criterion 4 — return-A onset harm (PASS, both cohorts)

Development: pooled return-A harm candidate **52** vs guard **58** —
(a) passes — and vs recent8 **90** the 60% ceiling is 54.0 — (b)
passes, by 2 actions. Additional: candidate **34** vs guard **45** —
(a) passes — and vs recent8 **82** the ceiling is 49.2 — (b) passes
comfortably. This criterion FAILed on both cohorts in the graded
long experiment (58 vs ceiling 55.8; 65 vs guard 64 and ceiling
57.0); here it passes on both, driven by the return-A cells
themselves (development k=2 harm 25 and k=4 harm 27, against the
long cohorts' 40/48-at-k=2 pattern; additional 17 and 17). The pass
is credited to the engagement that occurred on these cohorts (see
criterion 2), not to the reference width, which the records show
changed none of it.

### Criterion 5 — release and productivity by checkpoint 32 (PASS, both cohorts)

Development: k=32 abstentions **0/144** — (a) passes — successes
**54** vs recent8 **58** (required ≥ 50) — (b) passes — and from the
decision records the candidate took a non-recent8 branch in exactly
**1 of 9** switch-stage k=32 states — (c) passes (an
extended-reference-only retained_archive routing at return-A k=32,
seed 362021; the graded long baseline scored 58 there pooled, the
unexpired joint baseline also 58 — the candidate is 4 below both on
this cohort's k=32 total, inside the frozen margin). Additional:
abstentions **0/144**, successes **97** = recent8 **97** (required
≥ 89) — passes — non-recent8 branch in **1 of 9** states (return-A
k=32, seed 363041, again an extended-only late recovery). The
pre-registered slower-slide risk (failure mode 3) did NOT survive to
checkpoint 32 on either cohort; its cost is visible earlier instead
— at k=8 on the additional cohort the candidate's switch-stage
pooled successes are 50 vs recent8 76 with 32 abstentions (B1-8 and
B2-8 abstention states under the still-sliding 50-event reference),
a reported persistence cost, not a graded one. Development k=8
pooled: 62 vs 66 successes, 16 abstentions; k=16 pooled: development
87 vs 84, additional 60 vs 56 — the slide cost is an
additional-cohort k=8 phenomenon, recovered by k=16.

### Criterion 1 — return-A recovery successes preserved (PASS, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **44**
against frozen_A **66** — the 40% floor passes (44 × 5 = 220 ≥
66 × 2 = 132) — and against the guard-relative floor of guard + 16 =
**22** (guard scored 6) — passes. Additional: candidate **62**
against frozen_A **70** (floor passes: 310 ≥ 140) and guard + 16 =
**19** (guard scored 3) — passes. Reported in full, as the protocol
requires: plain cumulative scored **66 / 68** return-A successes at
**30 / 28** harm on the same cells — it BEATS the candidate on both
axes on both cohorts (candidate 44 at 52 harm development; 62 at 34
additional) — and the joint and long baselines scored exactly the
candidate's return-A successes on both cohorts (44 / 62; long at
identical 52 / 34 harm), with bounded at 37 / 51. Passing these
floors does not soften the cumulative gap: at a return, cumulative
needs no signal, no concordance test, and no authority to use
retained knowledge, and on these cohorts it still dominates every
gated variant at return-A.

### Criterion 3 — pooled onset harm not above the guard (FAIL development, PASS additional)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm
**192** vs guard **182** — (a) **fails by 10 actions** — although
candidate harm ≤ recent8 in **6 of 6** individual cells — (b) passes
(vs recent8 pooled 273). Additional: candidate **125** vs guard
**162** — (a) passes — with **6 of 6** cells ≤ recent8 (vs recent8
pooled 230). The development failure decomposes exactly, per stage:
B1 candidate **46** = guard **46**; return-A candidate **52** vs
guard **58** (candidate better by 6); **B2 candidate 94 vs guard 78
(candidate worse by 16)** — the whole failure, plus 6 more, is the
B2 stage. At B2 onset on development the candidate took NO
non-recent8 branch in any of the 6 states (joint_count 0 in all 6;
opposed_count 0 or 1 in all 6 — the abstention trigger never
reached 2), so its B2 harm is identical to recent8's (94 = 94),
while the guard's 24-event signal abstained at one B2 state (seed
362039, k=4, where the legacy opposed_count was 2 and the extended
count was 1 — the widening actually REMOVED that one firing). On
the additional cohort the same stage ran the other way (candidate
B2 harm 15 vs guard 25, with extended-reference abstentions at 4 of
6 B2 states), so the B2 signal sparsity is cohort-variable, not
uniform — but on development it is total, and a fail under the
frozen rule is recorded as such; no threshold is adjusted after
inspection.

### Criterion 6 — stationary control downstream selectivity (PASS, both cohorts)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **0/240**, successes **135** = recent8 135, harm **105**
= recent8 105; recovery engaged at 0 of 15 graded control states and
no control abstention occurred — downstream-identical to recent8 on
the stationary arm. Additional: abstentions **0/240**, successes
**115** = recent8 115, harm **125** = recent8 125; recovery 0 of 15
graded control states — likewise identical.

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions,
actual harmful / productive / neutral outcomes, reported harmful,
and label flips for every stage; per-method successes / harmful
TEST actions / abstentions / attempted tasks at every checkpoint;
the candidate's full decision record (per-event extended-reference
signal records, legacy reference-24 signal records, archive
concordance records, per-event joint and legacy joint
flags/records, and the full authority record — expiry span records
with comparable/disagreeing counts and stable_disagreement flag,
preceding span records with preceding comparable/disagreeing
counts and preceding stable flag, long_disagreement flag,
recovery_arming_leg, per-event last-8 archive-concordance records,
recent_concordant_count, recovery / abstention armed and
would-fire flags — plus every count, branch, recovery-fired /
abstained / gate-evaluable flags, acting source, and the
records-only legacy-long-rule, unexpired-joint-rule, and
bounded-authority-rule derivations) at every checkpoint; checkpoint
SHA256; and restore-replay identity (true at every checkpoint in
both cohorts, script-verified in this stage — no field missing
anywhere). Learner information-acquisition actions = 0, additional
requested observations = 0, and learner training actions = 0
throughout, as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions,
48 episodes per cell).

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 0 / 48 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| B1-2 | 0 / 16 / 32 | 0 / 48 | 0 / 32 / 16 | 0 / 48 |
| B1-4 | 2 / 30 / 16 | 7 / 41 | 4 / 44 / 0 | 4 / 44 |
| B1-8 | 20 / 28 / 0 | 20 / 28 | 1 / 31 / 16 | 14 / 34 |
| B1-16 | 29 / 19 / 0 | 29 / 19 | 5 / 43 / 0 | 5 / 43 |
| B1-32 | 16 / 32 / 0 | 16 / 32 | 33 / 15 / 0 | 33 / 15 |
| return-A-0 † | 9 / 39 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| return-A-2 | 23 / 25 / 0 | 1 / 47 | 31 / 17 / 0 | 1 / 47 |
| return-A-4 | 21 / 27 / 0 | 5 / 43 | 31 / 17 / 0 | 13 / 35 |
| return-A-8 | 32 / 16 / 0 | 25 / 23 | 31 / 17 / 0 | 32 / 16 |
| return-A-16 | 33 / 15 / 0 | 30 / 18 | 31 / 17 / 0 | 27 / 21 |
| return-A-32 | 21 / 27 / 0 | 25 / 23 | 31 / 17 / 0 | 31 / 17 |
| B2-0 † | 12 / 20 / 16 | 12 / 36 | 0 / 48 / 0 | 0 / 48 |
| B2-2 | 1 / 47 / 0 | 1 / 47 | 0 / 0 / 48 | 11 / 37 |
| B2-4 | 1 / 47 / 0 | 1 / 47 | 17 / 15 / 16 | 29 / 19 |
| B2-8 | 10 / 22 / 16 | 21 / 27 | 18 / 14 / 16 | 30 / 18 |
| B2-16 | 25 / 23 / 0 | 25 / 23 | 24 / 24 / 0 | 24 / 24 |
| B2-32 | 17 / 31 / 0 | 17 / 31 | 33 / 15 / 0 | 33 / 15 |
| control-0 † | 26 / 22 / 0 | 22 / 26 | 30 / 18 / 0 | 30 / 18 |
| control-2 | 23 / 25 / 0 | 23 / 25 | 28 / 20 / 0 | 28 / 20 |
| control-4 | 25 / 23 / 0 | 25 / 23 | 21 / 27 / 0 | 21 / 27 |
| control-8 | 23 / 25 / 0 | 23 / 25 | 16 / 32 / 0 | 16 / 32 |
| control-16 | 39 / 9 / 0 | 39 / 9 | 31 / 17 / 0 | 31 / 17 |
| control-32 | 25 / 23 / 0 | 25 / 23 | 19 / 29 / 0 | 19 / 29 |

† Checkpoint 0 is a reported diagnostic, not graded. k=0 candidate
harm per switch stage is 48 / 39 / 20 (development, B1 / return-A /
B2) and 48 / 48 / 48 (additional).

Reference points on the same cohorts (pooled onset, k=2,4, all
stages; successes / harm / abstentions): the decisive reference-width
comparison `long_disagreement_joint_recovery` (identical but for the
24-event reference) scored **48/192/48** (development) and **78/151/80**
(additional) pooled onset — identical totals to the candidate on
development, and on additional the candidate's entire pooled-onset
advantage over it (125 vs 151 harm) comes from its B1/B2 abstention
differences, not from return-A, where the two are again identical
(62 successes at 34 harm). The harm comparator
`evidence_opposition_guard` scored pooled onset harm 182
(development) and 162 (additional). `cumulative` scored return-A
pooled successes **66 / 68** at return-A harm **30 / 28** —
dominating every gated variant at return-A on both axes on both
cohorts, again. `frozen_A` scored return-A **66 / 70** successes at
**30 / 26** harm. The privileged expected oracle
pooled onset successes/harm were 198/90 (development) and 210/78
(additional): onset tasks remain largely solvable, and every
realizable learner here remains far from that.

**Retention note:** two successive single-mechanism changes —
disagreement-age authority (graded long experiment) and now
reference width (this experiment) — have each changed NO return-A
outcome relative to their records-only predecessors on their
cohorts. What varies return-A engagement across cohorts is the
newest draws themselves: where a newest event is matched and
archive-concordant, the existing signal (either reference width)
registers it and recovery engages (here: k=2 in 5 of 6 states across
cohorts, vs 1 of 6 in the long cohorts); where the draw is neutral
or archive-discordant (here: seed 362003 at k=2, concordant_count
0), no signal of this family exists at k=2 under any reference or
authority. The remaining unprotected onset in this experiment is
not at the first return at all: it is the SECOND switch (B2), where
the archive is original-rule-dominated, the B1 segment is a
minority inside it, recovery is pre-registered as not expected,
and on development neither branch fired in any onset state.

**Generalization level:** at most handoff level 2–3 (choosing among
/ applying already-supplied representations under a rule change,
plus designer-supplied signal, concordance, routing, expiry,
disagreement-age, and reference-width rules). No level-6 or
novel-representation claim is made. Nothing in this experiment
speaks to general regime identification: the archive is global and
unsegmented, B2 recovery was pre-registered as not expected (and
did not occur at onset in either cohort), and switches after
segments shorter than the 50-event reference are outside the
design's scope.

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; pooled
  onset harm 192 (development) and 125 (additional) vs recent8
  273 / 230 and vs the guard 182 / 162. The development pooled
  figure's failure against the guard is entirely the B2 stage
  (94 = recent8, vs guard 78), where no branch fired.
- **Actual harmful TRAIN-acquisition actions** (external actor,
  counted once per seed, never netted against TEST results):
  development — A 258, B1 81, return-A 56, B2 91 harmful of 1,248
  main-schedule actions (plus control continuation 56 of 192);
  additional — A 256, B1 76, return-A 53, B2 85 of 1,248 (plus
  control 47 of 192). Label flips in the reported stream:
  development 37 (main) + 5 (control); additional 45 (main) + 6
  (control).
- **Failed-by-abstention:** candidate onset abstentions 48/288
  (development) and 80/288 (additional); k=32 abstentions 0/144 on
  both cohorts; graded stationary control abstentions 0/240 on
  both cohorts. The always-abstain baseline is 48/48 abstentions
  with 0 successes and 0 harm at every checkpoint, as registered.
- **Additional requested observations / learner acquisition
  actions:** 0 / 0, exactly as frozen.
- **False confidence and unnecessary abstention:** false recovery
  at B1 — the pre-registered dangerous direction — occurred at 0
  of 6 states on both cohorts, and B2 recovery never engaged at
  onset. The realized errors are (i) signal absence at the second
  switch on development (B2 opposed_count never above 1, harm at
  recent8's level), and (ii) the pre-registered slower-slide cost
  at k=8 on additional (32 switch-stage abstentions there, pooled
  successes 50 vs recent8 76), fully released by k=32.
- **Report integrity / provenance:** checkpoint SHA256 replay
  identity held at every checkpoint in both cohorts; hashes
  validate record integrity only, not the truth of the
  (deliberately corrupted) public reports.

## Scientific conclusion

**Partially demonstrated** — per the protocol's own grading
definitions: criterion 2 (PRIMARY) and criterion 7 PASS on both
cohorts, but criterion 3 FAILs on the development cohort (pooled
onset harm 192 vs the guard's 182, the entire margin at the B2
stage), which is the protocol's Partially-demonstrated condition.
It is **not** Failed under the protocol's definition (criterion 2
passes on the additional cohort; none of criteria 1, 3, 4, or 5
fails on the additional cohort; criterion 7 passes on both) and
**not** a Regression under any clause of the protocol's definition:
pooled onset harm does not exceed recent8's on either cohort
(192 < 273; 125 < 230), stationary-control successes do not fall
below recent8's on either cohort (135 = 135; 115 = 115),
checkpoint-32 successes stay above the graded long candidate's
deficit line on both cohorts (54 ≥ 58 − 9 = 49; 97 ≥ 97 − 9 = 88),
and the full unit suite and historical transfer benchmark pass.

The experiment's decisive finding is again a null result about its
own mechanism, recorded as prominently as the passes: **widening
the reference from 24 to 50 events changed no return-A recovery
engagement on either cohort** — the candidate's taken states are
exactly the records-only legacy reference-24 derivation's taken
states (k=2: 2/3 and 3/3; pooled: 4/6 and 6/6), so criterion 2's
PASS, criterion 4's PASS on both cohorts (the preceding experiment
failed it on both), and the return-A successes under criterion 1
are achievements of the carried-over gate on cohorts whose newest
draws happened to be informative — they are NOT evidence that
reference width was the binding constraint, and the hypothesis
that reference sparsity capped k=2 engagement is not supported as
the binding mechanism on this evidence. Where k=2 engagement
failed here (1 of 6 states across cohorts), the newest draws
carried no matched archive-concordant event at all. Two mechanism
families in a row (authority age, reference width) have now been
shown not to bind return-A engagement; what binds it, when it
binds, is the information content of the first two post-return
draws themselves.

No frozen parameter, threshold, seed, or checkpoint is changed in
response to these results. Any revised hypothesis gets a NEW
protocol and NEW seeds.

## Next limitation (selected for the next cycle)

**P1 — second-switch (B2) onset non-protection: at the second
inversion the gate family has no working protective response on
the development cohort — recovery never engages at B2 onset in
either cohort (pre-registered: the global archive is
original-rule-dominated and the B1 segment is a minority inside
it), and on development the abstention branch also never fires at
B2 onset (opposed_count 0 or 1 in all 6 states, vs the guard's one
firing), so B2 pooled onset harm runs at exactly recent8's level
(94 vs the guard's 78), single-handedly failing pooled onset harm
(criterion 3) on that cohort — while on the additional cohort the
same stage is the candidate's best (harm 15 vs guard 25, abstentions
at 4 of 6 states), showing the protection exists in the signal on
some cohorts and is absent on others.** Measurable form for the
next protocol: on NEW seed cohorts, whether a learner can protect
the second switch — B2 pooled onset harm at or below the
evidence-opposition guard's on the same cohort, with its B2
engagement/abstention behavior graded from decision records —
without giving back the first-return profile (return-A engagement
and harm at the graded level) or the checkpoint-32 release — vs
recent8, cumulative, frozen_A, the evidence-opposition guard, and
the joint / bounded / long / extended-reference candidates as
baselines. This stays inside Priority 1 items 2, 3, and 4 and does
not re-tune any parameter of the nine graded onset experiments
against their inspected cohorts; the revised hypothesis gets its
own frozen protocol and NEW seeds. (Secondary, recorded but not
selected: cumulative's continued dominance of every gated variant
at return-A on both axes and both cohorts — 66/68 successes at
30/28 harm vs the candidate's 44/62 at 52/34; the
additional-cohort k=8 slower-slide persistence cost, 50 vs 76
pooled successes with 32 abstentions, released by k=32; and the
information-empty k=2 ceiling, realized once here at seed 362003,
which no newest-2 signal of any reference width can repair.)

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.extended_reference_joint_recovery_benchmark --cohort development
python -m benchmarks.extended_reference_joint_recovery_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results
above; it does not make the seeds un-inspected.
