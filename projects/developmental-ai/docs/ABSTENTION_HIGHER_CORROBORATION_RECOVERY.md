# Abstention higher corroboration recovery — raised support bar on the abstention release gate

**3 November 2026 protocol / 4 November 2026 graded. Status: optional, simulated,
unpromoted. No default-controller promotion, no PR merge, no D1–D10 or
V2A/V2B roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `abstention_higher_corroboration_recovery` —
  whether raising the abstention release gate's support leg from
  acting_opposed_count ≥ 3 to ≥ 4 (at least TWO supporting opposed
  events beyond the triggering pair) can close stationary abstention
  survival at the gate's minimum corroboration without thinning
  onset abstention past the onset harm margins — the limitation the
  graded abstention-release experiment selected: all seven criteria
  PASSed on its additional cohort, and its PRIMARY criterion 6
  FAILed on development by exactly 1 success because ONE stationary
  state (control checkpoint 8, seed 392039) survived both gate legs
  at leg S's minimum (acting_opposed_count exactly 3, purity
  0.857). The frozen protocol priced the trade in advance:
  checkpoint-2 onset retention under the raised bar falls to
  roughly 0.18, so the trade itself was the hypothesis, graded on
  both sides. Build Order Priority 1 (Independent Learning), items
  2 + 3 + 4; handoff §8 weak uncertainty calibration / excessive
  abstention. This protocol's PRIMARY criterion is again criterion
  6, stationary-control selectivity; criteria 5 (release by k=32,
  including sub-condition (d), abstained branch in 0 of 9 states),
  1 (B2 protection), and 4 (return-A harm) are its co-graded
  guards, reported second, third, and fourth below.
- **Candidate:** `AbstentionHigherCorroborationRecoveryMemory`
  (`developmental_ai/abstention_higher_corroboration_recovery.py`) —
  IDENTICAL to the graded `AbstentionReleaseGatedRecoveryMemory`
  in acting model (recent8 exactly), extended signal (newest 2 vs
  50-event reference, opposed_count), retained archive
  (events[:N-26]), archive concordance, joint test
  (joint_count >= 1), recovery model, abstention trigger
  (opposed_count == 2), the full three-leg authority condition,
  the minority branch in full, the reference-purity gate
  (>= 0.70) on BOTH recovery branches, and leg P of the abstention
  release gate (reference_purity >= 0.70). The SINGLE changed
  element is the release gate's leg-S support threshold:
  acting_opposed_count >= 4 in place of >= 3. Gate-blocked
  abstentions are recorded (abstention_disarmed_by_purity /
  abstention_disarmed_by_support; both false when the carried-over
  authority was already disarmed) and fall through to recent8.
  Minimum 52 events (never exercised in evaluation; all
  checkpoints >= 240 events). Separate optional learner; the
  default controller and all existing learners are untouched; the
  graded abstention-release candidate and every earlier candidate
  appear only as baselines.
- **Branch and commits:** `developmental-ai/abstention-higher-corroboration-recovery`
  (forked from `developmental-ai/abstention-release-gated-recovery` @
  `c92bbdb`). Protocol frozen at `35ced36`; implementation at
  `25a3c3b`; evaluation at `8459316`. This grading report is committed
  on top of the evaluation commit.
- **Frozen protocol:** `benchmarks/abstention_higher_corroboration_recovery_protocol.json`
  (schema `developmental-ai.abstention-higher-corroboration-recovery-protocol/v1`,
  frozen 2026-11-03, before any implementation, unit test, harness, or
  score inspection for this experiment).
- **Cohorts:** development 412003/412021/412039 and additional
  413001/413017/413041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit (the 402/403
  families were not used: the string 403041 occurs inside a decimal
  fraction in a saved results file). Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/abstention_higher_corroboration_recovery_results.json`
  (development) and
  `benchmarks/abstention_higher_corroboration_recovery_additional_results.json`
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
  tests`: 1116 tests OK in the implementation and evaluation stages,
  and 1116 tests OK again in this grading stage (run this pass; the
  grading-stage changes are documentation only, no code changed).
  Focused candidate tests: 36/36 PASS in the implementation stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the
  evaluation stage, and exited 0 again when re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts
  were run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's full
  decision record (extended-reference signal records, legacy
  reference-24 signal records, archive concordance records, per-event
  joint and legacy joint flags/records, the full authority record,
  the full minority record, the full purity record, AND the full
  abstention-gate record — per-event acting-window opposition records
  over the last 8 events, acting matched/opposed counts,
  supporting_opposed_count, support threshold 4,
  abstention_gate_armed, both abstention-disarmed flags — plus every
  count, branch, recovery-fired / minority-fired / abstained /
  gate-evaluable flags, acting source, and the records-only
  abstention-release-rule (threshold 3), reference-purity-rule,
  minority-rule, extended-rule, legacy-long-rule,
  unexpired-joint-rule, and bounded-authority-rule derivations), a
  checkpoint SHA256, and restore-replay identity verified true at
  every checkpoint in both cohorts (script-verified again in this
  grading stage — 72/72 entries per cohort; no criterion-7 field
  missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `8459316` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results
in this grading stage, not hand-copied. Denominators are exact episode
counts (48 per stage-checkpoint cell; 96 per pooled B2 or return-A
onset figure; 288 per pooled all-stage onset figure); decision-record
denominators are seed-checkpoint states (3 per stage per cohort at
checkpoint 2 alone; 6 per stage per cohort pooled at checkpoints 2
and 4; 9 switch-stage states per cohort at checkpoint 32; 15 graded
control states per cohort). Criterion 6, this experiment's PRIMARY
criterion, is reported first, and criteria 5, 1, and 4, its co-graded
guards, next, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 6 | PRIMARY stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 k=32 states; (d) abstained branch in 0 of 9 states) | **FAIL** | **PASS** |
| 1 | Second-switch B2 protection preserved ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **PASS** | **PASS** |
| 4 | Return-A onset harm preserved (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **FAIL** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **FAIL** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 6 (PRIMARY) — stationary control downstream selectivity (PASS, both cohorts — a no-trigger PASS)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **0/240** — (a) passes — successes **124** = recent8
**124** (required ≥ 118) — (b) passes — harm **116** = recent8
**116** — (c) passes. Additional: abstentions **0/240**, successes
**116** = recent8 **116** (required ≥ 110), harm **124** = recent8
**124** — all three sub-conditions pass. On both cohorts the
candidate is downstream-identical to recent8 at every graded
control checkpoint, and its taken branch differs from BOTH the
records-only abstention-release-rule derivation (the graded ≥ 3
rule) and the reference-purity-rule derivation at **0 of 15**
graded control states per cohort: no stationary abstention trigger
was taken, and none was gate-blocked, on either control arm. This
PASS must be read exactly as recorded: the stationary failure mode
this cycle targeted — a stationary pair surviving the gate — did
not occur on these cohorts under ANY of the three gate variants,
so the raised bar's stationary benefit is **untested here, not
demonstrated**. The cohorts simply drew no graded stationary
trigger. Realized control-arm purity was 0.742–0.923 (development)
and 0.805–0.968 (additional) — leg P armed throughout, as designed
on stationary evidence — and the minority branch never fired on
either control arm (fractions unarmed throughout).

### Criterion 5 — release and productivity by checkpoint 32 (FAIL development, PASS additional)

Development: k=32 abstentions **0/144** — (a) passes — successes
**68** vs recent8 **72** (required ≥ 64) — (b) passes — abstained
branch in **0 of 9** states — sub-condition (d) passes — but the
candidate takes a non-recent8 branch in **2 of 9** switch-stage
k=32 states — (c) **fails** (allowance 1). The two states, both
seed 412003: a return-A retained_archive routing at realized
purity 0.72 (armed), scoring per-seed 9 successes / 7 harm against
recent8's 13 / 3 there — that one state is the cohort's entire
k=32 successes deficit (−4) — and a B2 minority_archive routing at
purity 0.737 (armed), scoring 9 / 7, identical to recent8's 9 / 7
there. Neither state is an abstention, and neither involves the
raised support bar: the candidate's k=32 totals (68 successes /
76 harm / 0 abstentions) are identical to both the
abstention-release and reference-purity baseline methods' on this
cohort, and its branch differs from both records-only derivations
at 0 of 9 k=32 states. The failure is the carried recovery
branches' records-level release, charged as recorded: purity was
armed at 7 of 9 development k=32 states (realized 0.630–0.784), so
the purity gate released — i.e. did not block — both routings.
Additional: abstentions **0/144** — (a) passes — successes **93**
= recent8 **93** (required ≥ 85) — (b) passes — non-recent8 branch
in **0 of 9** states — (c) passes — abstained branch in **0 of 9**
— (d) passes. Realized purity across the 9 states was 0.658–1.000
(armed 5/9); the candidate is again identical to both baseline
methods at k=32 (93 / 51 / 0).

### Criterion 1 — second-switch B2 protection preserved (PASS, both cohorts)

**(a) ENGAGEMENT:** minority recovery was TAKEN at **6 of 6**
pooled B2 onset states on development (3/3 at checkpoint 2 and
3/3 at checkpoint 4) and **5 of 6** on additional (2/3 at
checkpoint 2, 3/3 at checkpoint 4); required ≥ 3. Realized
minority fractions at the B2 onset states were 0.262–0.299
(development) and 0.260–0.320 (additional), and realized purity
was armed at every B2 onset state (0.757–0.875 development,
0.838–0.900 additional). **(b) SELECTIVITY:** minority TAKEN at
**0 of 6** B1 onset states and **0 of 6** return-A onset states
on both cohorts (required ≤ 1 each). **(c) HARM:** B2 pooled
onset harm candidate **42** vs guard **86** (development) and
**52** vs guard **61** (additional) — passes — and vs recent8
**86 / 93** the 60% ceilings are 51.6 / 55.8 — passes on both.
**(d) PRODUCTIVITY:** B2 pooled successes candidate **54** vs
guard + 16 = **26** (guard 10, development) and **44** vs **19**
(guard 3, additional) — passes. The abstention gate sits below
both recovery branches and changed no B2 figure on either cohort;
the candidate's B2 onset profile is the graded profile,
preserved. Abstention-branch detail at B2, as the protocol
requires: the candidate abstained at 0/6 B2 onset states on both
cohorts and no B2 onset abstention was gate-disarmed on either.

### Criterion 4 — return-A onset harm preserved (PASS development, FAIL additional)

Development: pooled return-A harm candidate **44** vs guard
**71** — (a) passes — and vs recent8 **86** the 60% ceiling is
**51.6** — (b) passes. (This criterion FAILed on development in
the preceding cycle on a lower recent8 draw; here the same
carried profile, at the identical 44 harm, passes both
comparisons.) Additional: candidate **35** vs guard **32** —
(a) **fails by 3** — and vs recent8 **88** the ceiling is 52.8 —
(b) passes. Attribution, from the records: regular recovery was
TAKEN at 5 of 6 return-A onset states on both cohorts, no
return-A onset abstention was gate-disarmed at the raised bar on
either cohort, and the candidate is identical to the
abstention-release baseline method — and to the reference-purity
baseline method — on every return-A onset figure on both cohorts
(52 successes / 44 harm development; 61 / 35 additional). The
additional failure is therefore not a raised-bar effect: it is
the carried recovery profile measured against a guard whose
additional return-A protection is abstention itself (the guard
abstained at 64 of 96 return-A onset episode-checkpoints there,
scoring 0 successes). Charged unchanged, exactly as the preceding
gradings charged inherited failures — neither excused nor
misattributed to the one changed parameter.

### Criterion 2 — return-A recovery successes preserved (PASS, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **52**
against frozen_A **62** — the 40% floor passes (52 × 5 = 260 ≥
62 × 2 = 124) — and against the guard-relative floor of
guard + 16 = **25** (guard scored 9) — passes. Additional:
candidate **61** against frozen_A **72** (305 ≥ 144) and
guard + 16 = **16** (guard scored 0) — passes. Reported in full,
as the protocol requires — and with the same prominence as the
PASS: plain cumulative scored **62 / 66** return-A successes at
**34 / 30** harm and frozen_A **62 / 72** at **34 / 24** harm, so
on BOTH cohorts BOTH simple retention baselines again beat the
candidate on both axes at return-A (candidate 52 at 44 harm
development; 61 at 35 additional). The joint / bounded / long
baselines scored 52 / 52 / 52 successes (development) and 61 / 61
/ 61 (additional) at return-A — identical to the candidate, as in
the preceding cycles, because the return-A profile is carried,
not gate-produced. Cumulative's and frozen_A's first-return
dominance over every gated variant in this line is now recorded
on four consecutive graded cohort pairs.

### Criterion 3 — pooled onset harm not above the guard (PASS development, FAIL additional)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate
harm **149** vs guard **202** — (a) passes — with candidate harm
≤ recent8 in **6 of 6** individual cells — (b) passes (vs recent8
pooled 265). Additional: candidate **175** vs guard **151** —
(a) **fails by 24** — with **6 of 6** cells ≤ recent8 (vs recent8
pooled 269), so the failure is entirely the guard comparison.
Decomposition against the guard, per stage: development B1
candidate 63 vs guard 45 (+18), return-A 44 vs 71 (−27), B2 42 vs
86 (−44) — the B1 excess is absorbed by the recovery stages.
Additional B1 88 vs 58 (**+30**), return-A 35 vs 32 (+3), B2 52
vs 61 (−9): the B1 cell alone exceeds the entire failure margin.
B1 is the stage at which neither recovery branch can protect —
regular recovery is archive-blocked there and the minority
branch was unarmed at every B1 onset state on both cohorts — so
abstention is B1's only protective response, and the gate
generations have thinned it generation by generation (B1 pooled
onset harm / abstentions: reference-purity method 31 / 64
development and 58 / 32 additional; abstention-release method
47 / 48 and 88 / 0; this candidate 63 / 32 and **88 / 0** — on
additional the candidate's B1 harm equals recent8's 88 exactly:
no B1 protection at all). The raised bar's own incremental cost
is isolated under Learning evaluation below; the criterion
grades the candidate as it stands, and as it stands its pooled
onset harm is above the guard's on the additional cohort.
Charged, not excused.

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions,
actual harmful / productive / neutral outcomes, reported harmful,
and label flips for every stage; per-method successes / harmful
TEST actions / abstentions / attempted tasks at every checkpoint;
the candidate's full decision record (per-event extended-reference
signal records, legacy reference-24 signal records, archive
concordance records, per-event joint and legacy joint
flags/records, the full authority record, the full minority
record, the full purity record, AND the full abstention-gate
record — per-event acting-window opposition records over the last
8 events, acting matched/opposed counts, supporting_opposed_count,
support threshold 4, abstention_gate_armed, both
abstention-disarmed flags — plus every count, branch,
recovery-fired / minority-fired / abstained / gate-evaluable
flags, acting source, and the records-only abstention-release-rule,
reference-purity-rule, minority-rule, extended-rule,
legacy-long-rule, unexpired-joint-rule, and
bounded-authority-rule derivations) at every checkpoint; checkpoint
SHA256; and restore-replay identity (true at every checkpoint in
both cohorts, script-verified in this stage — 72/72 entries per
cohort; no field missing anywhere). Learner
information-acquisition actions = 0, additional requested
observations = 0, and learner training actions = 0 throughout, as
frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions,
48 episodes per cell).

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| B1-2 | 1 / 47 / 0 | 1 / 47 | 2 / 46 / 0 | 2 / 46 |
| B1-4 | 0 / 16 / 32 | 2 / 46 | 6 / 42 / 0 | 6 / 42 |
| B1-8 | 3 / 29 / 16 | 16 / 32 | 14 / 34 / 0 | 14 / 34 |
| B1-16 | 24 / 24 / 0 | 24 / 24 | 13 / 19 / 16 | 16 / 32 |
| B1-32 | 27 / 21 / 0 | 27 / 21 | 27 / 21 / 0 | 27 / 21 |
| return-A-0 † | 12 / 36 / 0 | 4 / 44 | 0 / 48 / 0 | 0 / 48 |
| return-A-2 | 31 / 17 / 0 | 5 / 43 | 23 / 25 / 0 | 0 / 48 |
| return-A-4 | 21 / 27 / 0 | 5 / 43 | 38 / 10 / 0 | 8 / 40 |
| return-A-8 | 28 / 20 / 0 | 21 / 27 | 30 / 18 / 0 | 22 / 26 |
| return-A-16 | 27 / 21 / 0 | 22 / 26 | 31 / 17 / 0 | 26 / 22 |
| return-A-32 | 26 / 22 / 0 | 30 / 18 | 37 / 11 / 0 | 37 / 11 |
| B2-0 † | 1 / 47 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| B2-2 | 27 / 21 / 0 | 1 / 47 | 18 / 30 / 0 | 2 / 46 |
| B2-4 | 27 / 21 / 0 | 9 / 39 | 26 / 22 / 0 | 1 / 47 |
| B2-8 | 21 / 27 / 0 | 31 / 17 | 18 / 30 / 0 | 15 / 33 |
| B2-16 | 14 / 34 / 0 | 14 / 34 | 27 / 21 / 0 | 31 / 17 |
| B2-32 | 15 / 33 / 0 | 15 / 33 | 29 / 19 / 0 | 29 / 19 |
| control-0 † | 28 / 20 / 0 | 28 / 20 | 25 / 23 / 0 | 25 / 23 |
| control-2 | 27 / 21 / 0 | 27 / 21 | 34 / 14 / 0 | 34 / 14 |
| control-4 | 34 / 14 / 0 | 34 / 14 | 22 / 26 / 0 | 22 / 26 |
| control-8 | 25 / 23 / 0 | 25 / 23 | 20 / 28 / 0 | 20 / 28 |
| control-16 | 18 / 30 / 0 | 18 / 30 | 23 / 25 / 0 | 23 / 25 |
| control-32 | 20 / 28 / 0 | 20 / 28 | 17 / 31 / 0 | 17 / 31 |

† Checkpoint 0 is a reported diagnostic, not graded. k=0 candidate
harm per switch stage is 47 / 36 / 47 (development, B1 / return-A /
B2) and 48 / 48 / 48 (additional).

**The raised bar, isolated (candidate vs the decisive
abstention-release baseline):** the candidate's taken branch
differs from the records-only abstention-release-rule derivation
(the graded ≥ 3 rule) at exactly **ONE** graded state across both
cohorts: development B1 checkpoint 4, seed 412039
(acting_opposed_count 3, supporting_opposed_count 1, realized
purity 0.868) — disarmed by leg S alone at the raised bar, falling
through to recent8 at 0 successes / 16 harm where the ≥ 3 gate
abstained at 0 / 0. That single state is the candidate's entire
difference from the abstention-release baseline method on
development: pooled onset harm 149 vs 133 (+16), onset abstentions
32 vs 48, every other aggregate identical. On additional there
are **zero** branch differences against the ≥ 3 rule in any
graded population (onset, control, checkpoint 32): the candidate
is identical to the abstention-release baseline method on every
aggregate on that cohort, so its criterion 3 and 4 failures there
are shared with the ≥ 3 gate, not produced by the raise — against
the ungated reference-purity rule, both gate generations disarm
the same two additional B1 checkpoint-2 states (seeds 413001 and
413041, acting_opposed_count 2, supporting 0), at B1 harm 58 →
88. The experiment's pre-registered cost side therefore realized
in its mildest form for the raise itself (one state, +16 harm,
absorbed on development) — and the cycle still FAILs, because
what the raise was meant to buy, stationary survival closure, was
never tested by these cohorts (criterion 6), while the gate
family's already-thinned onset profile failed the guard margins
on additional for reasons the raise neither caused nor repaired.

Reference points on the same cohorts (pooled onset, k=2,4, all
stages; successes / harm / abstentions): the decisive comparison
`abstention_release_gated_recovery` (identical but for leg S ≥ 3)
scored **107/133/48** (development) and **113/175/0**
(additional) pooled onset — on additional identical to the
candidate; on development the one disarmed state above accounts
for the whole difference (candidate 107/149/32). The ungated
`reference_purity_gated_recovery` scored 107/117/64 (development)
and 111/145/32 (additional): the two gate generations together
cost +32 / +30 pooled onset harm against it, all of it at B1.
At checkpoint 32 the release and purity baseline methods scored
identically to the candidate on both cohorts (68/76/0
development; 93/51/0 additional). On the control arm all three
methods are identical to recent8 on both cohorts. The harm
comparator `evidence_opposition_guard` scored pooled onset harm
202 (development) and 151 (additional) — its additional advantage
is concentrated at B1 (58, via 32 abstentions) and return-A (32,
via 64 abstentions). `cumulative` and `frozen_A` dominate the
candidate at return-A on both axes on both cohorts (criterion 2,
reported in full there). The privileged expected oracle pooled
onset successes/harm were 194/94 (development) and 186/102
(additional): onset tasks remain largely solvable, and every
realizable learner here remains far from that.

**Persistence note (checkpoints 8 and 16, reported not graded):**
pooled switch-stage successes/harm/abstentions at k=8 were 52/76/16
(development, identical to the release and purity baseline methods)
and 62/82/0 (additional, also identical); at k=16, 65/79/0
(development, vs the purity baseline method's 52/76/16 — a
purity-disarmed recovery difference, not an abstention-gate one)
and 71/57/16 (additional, identical to both baselines). Realized
purity at the switch-stage k=32 states (0.630–0.784 development,
0.658–1.000 additional) again sits above the 0.5675
global-composition design value — the pre-registered self-fit
compression — with leg P armed at 7/9 (development) and 5/9
(additional) of those states.

**Retention note:** what the two gate generations have retained is
the checkpoint-32 abstention release (sub-condition 5(d) PASSes
again on both cohorts — no k=32 abstention state anywhere) and,
on these cohorts, a control arm with no abstention at all. What
they have spent to retain it is B1 onset protection: the only
stage where abstention was ever the sole defense now runs, on the
additional cohort, at exactly recent8's harm. A corroboration bar
cannot be tuned out of that trade from this side: at B1 the
triggering pair's own segment IS the preceding segment, so any
support requirement priced for stationary evidence prices B1
onset identically — the pre-registered local-identity limit,
now realized at the level of a whole stage rather than a single
state.

**Generalization level:** at most handoff level 2–3 (choosing among
/ applying already-supplied representations under a rule change,
plus designer-supplied signal, concordance, minority, routing,
expiry, disagreement-age, reference-width, reference-purity, and
abstention-release rules). No level-6 or novel-representation claim
is made. The minority read the candidate carries exploits this
simulator's exact-inversion structure, and both gate legs read
segment composition in this simulator's geometry (240/64/48) — so
even the PASSes are bounded: stationary and late records free of
abstention states on cohorts that drew no stationary trigger, in
this simulator only — not general excessive-abstention handling,
not calibrated uncertainty, and not real-world safety.

## Safety and evidence costs

- Harmful TEST actions: reported per cell above and per criterion;
  pooled onset 149 (development) / 175 (additional) against
  recent8's 265 / 269 and the guard's 202 / 151.
- Harmful TRAIN acquisition actions by the learner: **0** — the
  learner issues no training interventions; all TRAIN evidence
  comes from the shared external actor stream, whose actual harmful
  / productive / neutral outcomes, reported harm, and label flips
  are published per seed in the saved results (criterion 7).
- Failed-by-abstention: pooled onset 32 / 288 (development) and
  0 / 288 (additional); checkpoint-32 0 / 144 on both cohorts;
  stationary control 0 / 240 on both cohorts. Abstentions are
  scored as failed tasks, never as successes.
- Additional requested observations: **0**.
- False confidence / unnecessary abstention: no unnecessary
  abstention occurred on either cohort (the control arms are
  abstention-free); the cycle's false-confidence cost is instead
  the fall-through harm at the states the gates disarmed —
  development B1 checkpoint 4, seed 412039 (+16 harm at the raised
  bar) and, shared with the ≥ 3 gate, the two additional B1
  checkpoint-2 states (+30 B1 harm against the ungated purity
  rule). Both are graded above, not buried.
- Report integrity: frozen protocol committed before implementation
  (`35ced36`); cohorts inspected only through the registered
  evaluation; no parameter was re-tuned against the 412003-family /
  413001-family cohorts after inspection. Provenance limitation:
  developer-selected simulation seeds in one engineered two-feature
  simulator family; not independent external proof.

## Scientific conclusion

**Failed.** Per the protocol's own grading definitions: NOT
Demonstrated (criteria 5, 3, and 4 FAIL); the **Failed** clause is
triggered on the additional cohort — criterion 3 FAILs there
(pooled onset harm 175 vs the guard's 151) and criterion 4 FAILs
there (return-A harm 35 vs the guard's 32), either of which is
sufficient under the clause (criterion 7 PASSes on both, criterion
6 PASSes on both, criterion 5 PASSes on additional and FAILs only
on development). The Partially-demonstrated clause is the residual
category when the Failed clause does not trigger, as in the
preceding gradings in this line; here it does trigger, so the
conclusion is Failed, stated without softening. NOT a Regression
(pooled onset harm 149 / 175 well below recent8's 265 / 269 on
both cohorts; control successes equal to recent8 on both, not
below by more than 6; checkpoint-32 successes 68 / 93 against the
recent8 − 4 lines of 68 / 89 — development sits exactly ON its
line, not below it; full unit suite and historical transfer
benchmark pass — see Verification). What the experiment
establishes, stated as prominently as the failure: the raised bar
itself changed exactly one graded outcome across both cohorts
(one development B1 onset disarming, +16 harm, absorbed there),
and it bought nothing measurable in return — no stationary
trigger occurred on either control arm under any gate variant,
so PRIMARY criterion 6's PASS is a no-trigger PASS and the
hypothesis that a higher bar "closes stationary survival" is
**Unproven** on this evidence, neither confirmed nor refuted.
What failed is the candidate as graded: the gated family's onset
profile — already thinned at B1 by the ≥ 3 gate, and not further
thinned by the raise on additional — is above the guard's pooled
onset harm and return-A harm on the additional cohort, and its
carried recovery branches still take 2 of 9 development k=32
states against a 1-of-9 records allowance. Generalization level
2–3, simulator-bounded (see Learning evaluation).

**Next limitation (selected for the next cycle, Priority 1):**
first-switch (B1) onset non-protection in the gated family — at
B1 neither recovery branch can protect (regular recovery is
archive-blocked; the minority branch was unarmed at every B1
onset state on both cohorts, fractions 0.125–0.192), so
abstention is the only protective response the family has there,
and the two release-gate generations have thinned it to 32 of 96
B1 onset episode-checkpoints abstained on development and 0 of
96 on additional, where B1 pooled onset harm runs at exactly
recent8's level (88 = 88) and +30 above the guard — the entire
criterion-3 failure margin on additional, and +18 above the
guard on development, absorbed there only by the recovery
stages. Measurable: on NEW cohorts, whether a protective response
at B1 onset — one that does not price B1 triggers with a
stationary-evidence corroboration bar — can restore B1 pooled
onset harm at or below the guard's (and below recent8's) without
giving back stationary selectivity (criterion 6's form) or the
checkpoint-32 release (criterion 5's form) — on NEW cohorts under
a NEW protocol. Recorded but not selected: criterion 5's
development failure is the carried recovery branches' k=32
records (2/9; one state neutral at 9/7 = recent8, one the
return-A retained state costing the whole −4 k=32 deficit), not
an abstention or gate effect; criterion 4's additional failure
(+3) is shared identically with the ≥ 3 gate and the purity
candidate at return-A; and cumulative / frozen_A dominate the
candidate at return-A on both axes on both cohorts for the
fourth consecutive graded cohort pair — plain retention's
first-return dominance remains open and unaddressed by gate
tuning.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration, D1–D10/V2A/V2B
unchanged.
