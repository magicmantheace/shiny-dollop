# Minority archive joint recovery — retained discordant-evidence recovery

**1 November 2026 protocol / 2 November 2026 graded. Status: optional, simulated,
unpromoted. No default-controller promotion, no PR merge, no D1–D10 or
V2A/V2B roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `minority_archive_joint_recovery` — whether a
  learner can protect the SECOND switch (B2) at onset, the limitation
  the graded extended-reference experiment selected: at B2 the global
  archive is original-rule-dominated, the retained B1 segment is a
  minority inside it, a B2-following event is archive-discordant by
  construction, and the joint recovery test realized 0/6 B2
  engagement on every cohort of all five preceding experiments —
  while on the extended-reference development cohort the abstention
  branch also never fired at B2 onset, so B2 harm ran at exactly
  recent8's level (94 vs the guard's 78) and single-handedly failed
  pooled onset harm. Build Order Priority 1 (Independent Learning),
  items 2 + 3 + 4; handoff §8 slow or incorrect recovery of old
  knowledge / weak uncertainty calibration / first-contact
  overconfidence. The protocol's PRIMARY criterion is criterion 1,
  B2 protection (engagement sub-condition (a) first within it, then
  selectivity (b), harm (c), productivity (d)); criteria 4
  (return-A harm) and 5 (release by k=32) are its co-graded guards.
  They are reported first, second, and third below, as the protocol
  requires.
- **Candidate:** `MinorityArchiveJointRecoveryMemory`
  (`developmental_ai/minority_archive_joint_recovery.py`) —
  IDENTICAL to the graded `ExtendedReferenceJointRecoveryMemory` in
  acting model (recent8 exactly), extended signal (newest 2 vs
  50-event reference, opposed_count), retained archive
  (events[:N-26]), archive concordance, joint test form
  (joint_count >= 1), recovery model, abstention trigger
  (opposed_count == 2), and the full three-leg authority condition
  (local disagreement, corroboration recent_concordant_count >= 2,
  long disagreement; strict-majority rule D * 2 > C in both
  windows). The SINGLE new element is a MINORITY-ARCHIVE recovery
  branch, evaluated BELOW regular recovery and ABOVE abstention:
  the minority set is the archive events that are archive-matched
  and DISCORDANT with the archive's own per-span majorities;
  minority_fraction = discordant / archive-matched archive events;
  the branch is ARMED iff fraction >= 0.25 AND discordant >= 8; a
  newest event is minority-joint iff minority-concordant AND
  reference-opposed (extended reference) on the SAME event;
  minority recovery fires iff minority_joint_count >= 1 AND armed,
  acting through a RelationOutcomeMemory fitted on the minority
  set only (source minority_archive). The carried-over authority
  neither arms nor disarms the minority branch — a design fact
  that matters for the k=32 grading below. Minimum 52 events
  (never exercised in evaluation; all checkpoints >= 240 events).
  Separate optional learner; the default controller and all
  existing learners are untouched; the graded extended-reference
  candidate and every earlier candidate appear only as baselines.
- **Branch and commits:** `developmental-ai/minority-archive-joint-recovery`
  (forked from `developmental-ai/extended-reference-joint-recovery` @
  `0707a59`). Protocol frozen at `512fe4c`; implementation at
  `30aa0f4`; evaluation at `2c7da40`. This grading report is committed
  on top of the evaluation commit.
- **Frozen protocol:** `benchmarks/minority_archive_joint_recovery_protocol.json`
  (schema `developmental-ai.minority-archive-joint-recovery-protocol/v1`,
  frozen 2026-11-01, before any implementation, unit test, harness, or
  score inspection for this experiment).
- **Cohorts:** development 372003/372021/372039 and additional
  373001/373017/373041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit. Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/minority_archive_joint_recovery_results.json`
  (development) and
  `benchmarks/minority_archive_joint_recovery_additional_results.json`
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
  tests`: 1017 tests OK in the implementation stage, 1017 tests OK in
  the evaluation stage, and 1017 tests OK again in this grading stage in this grading
  stage (run this pass; the grading-stage changes are documentation
  only, no code changed). Focused candidate tests: 22/22 PASS in the
  implementation stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the
  evaluation stage, and exited 0 again when re-run in this grading stage in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts
  were run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's full
  decision record (extended-reference signal records, legacy
  reference-24 signal records, archive concordance records, per-event
  joint and legacy joint flags/records, the full authority record,
  AND the full minority record — minority matched/discordant counts,
  fraction, armed flag, per-event minority concordance records,
  per-event minority joint flags, minority_joint_count,
  minority_would_fire flag — plus every count, branch,
  recovery-fired / minority-fired / abstained / gate-evaluable flags,
  acting source, and the records-only extended-rule, legacy-long-rule,
  unexpired-joint-rule, and bounded-authority-rule derivations), a
  checkpoint SHA256, and restore-replay identity verified true at
  every checkpoint in both cohorts (script-verified again in this
  grading stage; no criterion-7 field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `2c7da40` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results
in this grading stage, not hand-copied. Denominators are exact episode
counts (48 per stage-checkpoint cell; 96 per pooled B2 or return-A
onset figure; 288 per pooled all-stage onset figure); decision-record
denominators are seed-checkpoint states (3 per stage per cohort at
checkpoint 2 alone; 6 per stage per cohort pooled at checkpoints 2
and 4; 9 switch-stage states per cohort at checkpoint 32). Criterion
1, this experiment's PRIMARY criterion, is reported first (its
engagement sub-condition (a) first within it, then selectivity (b),
harm (c), productivity (d)), and criteria 4 and 5, its co-graded
guards, next, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 1 | PRIMARY second-switch B2 protection ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **PASS** | **PASS** |
| 4 | Return-A onset harm (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **PASS** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 switch-stage k=32 states, from records) | **FAIL** | **FAIL** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 6 | Stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **FAIL** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 1 (PRIMARY) — second-switch B2 protection (PASS, both cohorts)

**(a) ENGAGEMENT:** minority recovery was TAKEN at **6 of 6** pooled
B2 onset states on development (3/3 at checkpoint 2 alone and 3/3 at
checkpoint 4) and at **5 of 6** on additional (2/3 at k=2 — seed
373041 stayed on recent8 with minority_joint_count 0 — and 3/3 at
k=4); required ≥ 3. Realized minority fractions at the taken states
were 0.299–0.339 (development) and 0.272–0.308 (additional), armed at
all 6 B2 onset states on both cohorts. This is the first B2 recovery
engagement in the line: the records-only extended-rule derivation
took **no** B2 onset state via recovery on either cohort (4 recent8 /
2 abstained per cohort), so — unlike the two preceding null results —
the new element is credited with the engagement: the minority branch
changed B2 engagement and B2 scores materially on both cohorts.
**(b) SELECTIVITY:** minority TAKEN at **0 of 6** B1 onset states and
**0 of 6** return-A onset states on both cohorts (required ≤ 1 each).
At B1 the branch was unarmed in all 12 states across cohorts
(fractions 0.133–0.212); minority would-fire-but-disarmed was 5/6
(development) and 6/6 (additional) there — the joint side was present
and the fraction arming alone held the branch off, exactly as
designed. At return-A the branch was armed in 6/6 (development) and
4/6 (additional) states but minority_joint_count was 0 in every one —
the pre-registered double block held. **(c) HARM:** B2 pooled onset
harm candidate **30** vs guard **52** (development) and **29** vs
guard **76** (additional) — passes — and vs recent8 **70 / 91** the
60% ceilings are 42.0 / 54.6 — passes on both. The pre-registered
abstention-conversion tradeoff did NOT materialize as a harm failure:
on additional, where the extended baseline protected B2 partly by
abstention (harm 61 with 32 abstentions), minority play scored harm
29 with 0 abstentions. **(d) PRODUCTIVITY:** B2 pooled successes
candidate **66** vs guard + 16 = **28** (guard 12, development) and
**67** vs **20** (guard 4, additional) — passes by wide margins; the
extended baseline scored 12 / 3 B2 successes on the same cells, and
no other realizable baseline in the set plays the second switch at
onset (cumulative 0, frozen_A 0 on both cohorts).

### Criterion 4 — return-A onset harm (PASS, both cohorts)

Development: pooled return-A harm candidate **45** vs guard **69**
— (a) passes — and vs recent8 **85** the 60% ceiling is 51.0 — (b)
passes. Additional: candidate **28** vs guard **59** — (a) passes —
and vs recent8 **75** the ceiling is 45.0 — (b) passes. Identical to
the extended baseline's return-A harm on both cohorts (45 / 28): the
minority branch, which never fired at return-A onset, gave nothing
back at the first return.

### Criterion 5 — release and productivity by checkpoint 32 (FAIL, both cohorts)

Development: k=32 abstentions **0/144** — (a) passes — successes
**79** vs recent8 **68** (required ≥ 60) — (b) passes — but from the
decision records the candidate took a non-recent8 branch in **2 of
9** switch-stage k=32 states — (c) **fails** (required ≤ 1). The two
states were productive here (return-A retained_archive, seed 372003,
9/7 vs recent8 5/11; B2 minority_archive, seed 372003, 13/3 vs
recent8 6/10), so the development failure is a records-level release
failure only. Additional: abstentions **0/144** — (a) passes — but
successes **68** vs recent8 **86** (required ≥ 78) — (b) **fails by
10** — and non-recent8 branch in **2 of 9** states — (c) **fails**.
On additional both late states scored **0 successes / 16 harm**
(return-A minority_archive, seed 373041 — the minority branch firing
late at a first return, minority fraction 0.301, armed; B2
retained_archive, seed 373017), against recent8's 12/4 and 6/10
there: the entire −18 k=32 gap is those two stale routings. The
minority branch has no expiry by design (the carried-over authority
neither arms nor disarms it, and its fraction arming only grows as
displaced segments accumulate in the archive), and the regular
branch's authority did not disarm the B2 late state either. This is
the experiment's binding failure, and on the additional cohort it
also triggers the protocol's Regression clause (see the conclusion).

### Criterion 2 — return-A recovery successes preserved (PASS, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **51**
against frozen_A **56** — the 40% floor passes (51 × 5 = 255 ≥
56 × 2 = 112) — and against the guard-relative floor of guard + 16 =
**27** (guard scored 11) — passes. Additional: candidate **68**
against frozen_A **62** (floor passes: 340 ≥ 124) and guard + 16 =
**37** (guard scored 21) — passes. Reported in full, as the protocol
requires: plain cumulative scored **64 / 68** return-A successes at
**32 / 28** harm — it still beats the candidate on both axes on
development (candidate 51 at 45 harm) and exactly matches it on
additional (68 at 28); the extended baseline scored the identical
51 / 68 at 45 / 28, the joint and long baselines 50 / 68, bounded
37 / 55. Regular recovery engagement at return-A onset was 5/6
(development) and 6/6 (additional), every taken state reporting
arming leg `long`, identical to the extended-rule derivation.

### Criterion 3 — pooled onset harm not above the guard (PASS, both cohorts)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm
**128** vs guard **174** — (a) passes — with candidate harm ≤
recent8 in **6 of 6** individual cells — (b) passes (vs recent8
pooled 221). Additional: candidate **120** vs guard **200** — (a)
passes — with **6 of 6** cells ≤ recent8 (vs recent8 pooled 245).
This is the criterion the graded extended candidate FAILed on
development (192 vs 182, the entire margin at B2); the B2 repair
carries it on both cohorts here, with room to spare.

### Criterion 6 — stationary control downstream selectivity (FAIL development, PASS additional)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **0/240** — (a) passes — successes **90** vs recent8
**92** (required ≥ 86) — (b) passes — but harm **150** vs recent8
**148** — (c) **fails by 2 actions**. The entire difference is one
checkpoint: at control k=8 the candidate scored 20/28 vs recent8
22/26, downstream of a single regular-recovery firing (seed 372039,
retained_archive) — the minority branch never fired on the control
arm on either cohort (fractions 0.167–0.212 development, 0.132–0.199
additional, unarmed at every graded control checkpoint, as
designed). Additional: abstentions **0/240**, successes **111** =
recent8 111, harm **129** = recent8 129 — downstream-identical to
recent8 on the stationary arm; control recovery fired 0/15 graded
states (development 1/15, the k=8 state above).

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions,
actual harmful / productive / neutral outcomes, reported harmful,
and label flips for every stage; per-method successes / harmful
TEST actions / abstentions / attempted tasks at every checkpoint;
the candidate's full decision record (per-event extended-reference
signal records, legacy reference-24 signal records, archive
concordance records, per-event joint and legacy joint
flags/records, the full authority record, AND the full minority
record — minority matched/discordant counts, fraction, armed flag,
per-event minority concordance records, per-event minority joint
flags, minority_joint_count, minority_would_fire flag — plus every
count, branch, recovery-fired / minority-fired / abstained /
gate-evaluable flags, acting source, and the records-only
extended-rule, legacy-long-rule, unexpired-joint-rule, and
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
| B1-2 | 2 / 30 / 16 | 5 / 43 | 8 / 40 / 0 | 8 / 40 |
| B1-4 | 25 / 23 / 0 | 25 / 23 | 9 / 23 / 16 | 9 / 39 |
| B1-8 | 19 / 29 / 0 | 19 / 29 | 0 / 16 / 32 | 21 / 27 |
| B1-16 | 21 / 11 / 16 | 30 / 18 | 33 / 15 / 0 | 33 / 15 |
| B1-32 | 19 / 29 / 0 | 19 / 29 | 28 / 20 / 0 | 28 / 20 |
| return-A-0 † | 1 / 47 / 0 | 1 / 47 | 9 / 39 / 0 | 0 / 48 |
| return-A-2 | 19 / 29 / 0 | 0 / 48 | 35 / 13 / 0 | 0 / 48 |
| return-A-4 | 32 / 16 / 0 | 11 / 37 | 33 / 15 / 0 | 21 / 27 |
| return-A-8 | 32 / 16 / 0 | 18 / 30 | 32 / 16 / 0 | 27 / 21 |
| return-A-16 | 32 / 16 / 0 | 19 / 29 | 26 / 22 / 0 | 27 / 21 |
| return-A-32 | 31 / 17 / 0 | 27 / 21 | 21 / 27 / 0 | 33 / 15 |
| B2-0 † | 14 / 34 / 0 | 2 / 46 | 24 / 24 / 0 | 2 / 46 |
| B2-2 | 33 / 15 / 0 | 5 / 43 | 29 / 19 / 0 | 2 / 46 |
| B2-4 | 33 / 15 / 0 | 21 / 27 | 38 / 10 / 0 | 3 / 45 |
| B2-8 | 29 / 19 / 0 | 27 / 21 | 27 / 21 / 0 | 20 / 28 |
| B2-16 | 37 / 11 / 0 | 31 / 17 | 24 / 24 / 0 | 31 / 17 |
| B2-32 | 29 / 19 / 0 | 22 / 26 | 19 / 29 / 0 | 25 / 23 |
| control-0 † | 23 / 25 / 0 | 22 / 26 | 20 / 28 / 0 | 20 / 28 |
| control-2 | 4 / 44 / 0 | 4 / 44 | 19 / 29 / 0 | 19 / 29 |
| control-4 | 9 / 39 / 0 | 9 / 39 | 26 / 22 / 0 | 26 / 22 |
| control-8 | 20 / 28 / 0 | 22 / 26 | 22 / 26 / 0 | 22 / 26 |
| control-16 | 32 / 16 / 0 | 32 / 16 | 28 / 20 / 0 | 28 / 20 |
| control-32 | 25 / 23 / 0 | 25 / 23 | 16 / 32 / 0 | 16 / 32 |

† Checkpoint 0 is a reported diagnostic, not graded. k=0 candidate
harm per switch stage is 48 / 47 / 34 (development, B1 / return-A /
B2) and 48 / 39 / 24 (additional).

Reference points on the same cohorts (pooled onset, k=2,4, all
stages; successes / harm / abstentions): the decisive minority-branch
comparison `extended_reference_joint_recovery` (identical but for
the minority branch) scored **90/150/48** (development) and
**88/152/48** (additional) pooled onset against the candidate's
144/128/16 and 152/120/16 — the candidate's entire pooled-onset
advantage over it is at B2 (successes 66 vs 12 and 67 vs 3; harm 30
vs 52 and 29 vs 61), with B1 and return-A identical on both cohorts.
The harm comparator `evidence_opposition_guard` scored pooled onset
harm 174 (development) and 200 (additional). `cumulative` scored
return-A pooled successes **64 / 68** at return-A harm **32 / 28** —
still dominating the candidate at return-A on development and
matching it on additional, while scoring 0 B2 successes at 96 B2
harm on both cohorts: undifferentiated retention cannot protect the
second switch, and the minority read can. `frozen_A` scored
return-A **56 / 62** successes at **40 / 34** harm and 0 B2
successes. The privileged expected oracle pooled onset
successes/harm were 208/80 (development) and 192/96 (additional):
onset tasks remain largely solvable, and every realizable learner
here remains far from that.

**Retention note:** the minority read is the first mechanism in
this line whose engagement is credited to the mechanism itself at
the stage it targeted: at B2 onset the global archive's discordant
events — counted and discarded in all five preceding experiments —
carried a usable model of the displaced rule, and the fraction
arming separated that displaced segment from flip noise exactly as
designed (unarmed at B1 and on stationary evidence, armed at B2 and
at return-A, doubly blocked at return-A). What the experiment did
not solve is time: neither the minority branch (no authority at
all) nor the regular branch (authority satisfied at the B2 late
state) released reliably by checkpoint 32 on the additional
cohort, where two stale routings cost 18 successes against recent8.

**Generalization level:** at most handoff level 2–3 (choosing among
/ applying already-supplied representations under a rule change,
plus designer-supplied signal, concordance, minority, routing,
expiry, disagreement-age, and reference-width rules). No level-6 or
novel-representation claim is made. The minority read exploits this
simulator's exact-inversion structure — original-segment flip
reports reinforce the inverted class in the minority pool instead
of diluting it (the protocol's pre-registered failure mode 4) — so
even the B2 result is bounded: minority-evidence recovery in an
inversion simulator, not general displaced-segment discovery.

## Safety and evidence costs

- **Harmful TEST actions:** reported per checkpoint above; pooled
  onset harm 128 (development) and 120 (additional) vs recent8
  221 / 245 and vs the guard 174 / 200. The harm failures are late
  and stationary, not onset: k=32 pooled harm 65 vs recent8 76
  (development, candidate better) but 76 vs 58 (additional, the two
  0/16 stale routings), and stationary control harm 150 vs 148
  (development, one control recovery firing at k=8).
- **Actual harmful TRAIN-acquisition actions** (external actor,
  counted once per seed, never netted against TEST results):
  development — A 265, B1 82, return-A 43, B2 75 harmful of 1,248
  main-schedule actions (plus control continuation 64 of 192);
  additional — A 253, B1 79, return-A 49, B2 81 of 1,248 (plus
  control 71 of 192). Label flips in the reported stream:
  development 46 (main) + 6 (control); additional 45 (main) + 7
  (control).
- **Failed-by-abstention:** candidate onset abstentions 16/288 on
  both cohorts; k=32 abstentions 0/144 on both cohorts; graded
  stationary control abstentions 0/240 on both cohorts. The
  always-abstain baseline is 48/48 abstentions with 0 successes and
  0 harm at every checkpoint, as registered.
- **Additional requested observations / learner acquisition
  actions:** 0 / 0, exactly as frozen.
- **False confidence and unnecessary abstention:** false minority
  engagement at onset — the pre-registered dangerous direction —
  occurred at 0 of 6 B1 and 0 of 6 return-A states on both cohorts,
  and the minority branch never fired on stationary evidence. The
  realized errors are (i) late persistence: minority recovery at
  return-A k=32 on additional (0/16) and regular recovery at B2
  k=32 on additional (0/16), plus two productive-but-unreleased
  late routings on development that fail the records sub-condition
  there, and (ii) a single regular-recovery firing on the
  stationary arm at control k=8 on development (harm +2 vs recent8,
  failing criterion 6 there by exactly that margin).
- **Report integrity / provenance:** checkpoint SHA256 replay
  identity held at every checkpoint in both cohorts; hashes
  validate record integrity only, not the truth of the
  (deliberately corrupted) public reports.

## Scientific conclusion

**Failed** — per the protocol's own grading definitions: criterion
5 FAILs on the additional cohort (successes 68 vs recent8 86,
required ≥ 78; non-recent8 branch in 2 of 9 k=32 states, required
≤ 1), which is the protocol's Failed condition. It is also a
**Regression** under the protocol's checkpoint-32 clause: the
additional cohort's k=32 successes (68) fall below recent8 − 4
(86 − 4 = 82), the graded extended candidate's worse-cohort deficit
line. The other Regression clauses do not trigger (pooled onset
harm well below recent8 on both cohorts, 128 < 221 and 120 < 245;
stationary-control successes within 6 of recent8 on both, −2 and
0; suite + transfer pass). Criterion 5 also FAILs on development
(records sub-condition only: 2 of 9 states, both productive there)
and criterion 6 FAILs on development (control harm 150 vs recent8
148, from one control recovery firing).

That verdict must not bury the experiment's positive finding,
which is recorded with the same prominence: **the PRIMARY
criterion passes on both cohorts, and for the first time in this
line a mechanism is credited with its own targeted engagement.**
Minority recovery took 6/6 (development) and 5/6 (additional) B2
onset states where the records-only extended derivation took none;
B2 harm fell to 30 / 29 against the guard's 52 / 76 and recent8's
70 / 91; B2 successes rose to 66 / 67 against the guard's 12 / 4;
pooled onset harm (criterion 3) — the criterion B2 sank in the
preceding experiment — passes on both cohorts; and the first-return
profile (criteria 2 and 4) is fully preserved. Second-switch onset
protection from retained discordant evidence is demonstrated on
these cohorts, in this simulator, at handoff level 2–3. What
failed is release: a branch with no expiry, added to a gate family
whose late persistence has now failed in three experiments (joint,
bounded on development, and this one on both records counts),
cannot be left armed at checkpoint 32 — on the additional cohort
two stale routings converted the experiment's onset gains into a
k=32 regression against the simplest baseline.

No frozen parameter, threshold, seed, or checkpoint is changed in
response to these results. Any revised hypothesis gets a NEW
protocol and NEW seeds.

## Next limitation (selected for the next cycle)

**P1 — late persistence of the recovery branches at checkpoint 32,
now including the minority branch: the minority branch's arming is
a static archive summary (fraction ≥ 0.25) with no expiry or
authority condition at all, so it stays armed and can fire long
after the recent window has adapted — realized as a minority
routing at return-A k=32 on the additional cohort scoring 0/16 vs
recent8's 12/4, alongside a regular retained-archive routing at B2
k=32 scoring 0/16 vs 6/10 — failing release on both cohorts (2 of
9 non-recent8 k=32 states each; additional k=32 successes 68 vs
recent8 86) and triggering the protocol's Regression clause, while
on development the same two unreleased states were productive
(9/7 and 13/3), so late firing is cohort-variable harm, not a
uniform defect.** Measurable form for the next protocol: on NEW
seed cohorts, whether an evidence-derived authority/expiry
condition for the minority branch (and the carried-over branches)
can restore checkpoint-32 release — successes within 8 of recent8
and a non-recent8 branch in at most 1 of 9 switch-stage k=32
states, from records — without giving back the B2 onset protection
graded here (minority engagement ≥ 3/6, B2 harm at or below the
guard's) or the first-return profile — vs recent8, cumulative,
frozen_A, the evidence-opposition guard, and the extended-reference
and minority-archive candidates as baselines. This stays inside
Priority 1 items 2, 3, and 4 and does not re-tune any parameter of
the ten graded onset experiments against their inspected cohorts;
the revised hypothesis gets its own frozen protocol and NEW seeds.
(Secondary, recorded but not selected: the stationary-control
regular-recovery firing at k=8 on development that failed
criterion 6 by 2 harm actions; cumulative's continued dominance of
the candidate at return-A on the development cohort — 64 successes
at 32 harm vs the candidate's 51 at 45 — while exactly matching it
on additional; and B1 k=8 persistence costs on additional, 0
successes with 32 abstentions at B1-8 against recent8's 21.)

## Reproduction

```bash
python -m unittest discover -s tests
python -m benchmarks.transfer_benchmark
python -m benchmarks.minority_archive_joint_recovery_benchmark --cohort development
python -m benchmarks.minority_archive_joint_recovery_benchmark --cohort additional
```

Re-running the benchmark cohorts reproduces the inspected results
above; it does not make the seeds un-inspected.
