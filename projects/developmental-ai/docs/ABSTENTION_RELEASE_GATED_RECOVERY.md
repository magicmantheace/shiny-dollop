# Abstention release gated recovery — release gate on the abstention branch

**3 November 2026 protocol / 3 November 2026 graded. Status: optional, simulated,
unpromoted. No default-controller promotion, no PR merge, no D1–D10 or
V2A/V2B roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `abstention_release_gated_recovery` — whether an
  evidence-derived release condition on the ABSTENTION branch can
  restore stationary selectivity and remove late abstention from the
  checkpoint-32 records, the limitation the graded reference-purity
  experiment selected: its PRIMARY criterion 5 and criteria 1–4 and 7
  PASSed on both cohorts, and its SOLE failure was criterion 6 on the
  additional cohort — caused entirely by ONE stationary control state
  (checkpoint 32, seed 383017) at which the candidate abstained on all
  16 tasks, downstream of the abstention branch, the family's only
  branch with no expiry or release condition of any kind. The same
  branch was also that experiment's sole remaining additional k=32
  non-recent8 state (a return-A abstention, seed 383041). Build Order
  Priority 1 (Independent Learning), items 2 + 3 + 4; handoff §8 weak
  uncertainty calibration / excessive abstention. This protocol's
  PRIMARY criterion is criterion 6, stationary-control selectivity;
  criteria 5 (release by k=32, with the new zero-abstention
  sub-condition (d)), 1 (B2 protection), and 4 (return-A harm) are its
  co-graded guards. They are reported first, second, third, and
  fourth below, as the protocol requires.
- **Candidate:** `AbstentionReleaseGatedRecoveryMemory`
  (`developmental_ai/abstention_release_gated_recovery.py`) —
  IDENTICAL to the graded `ReferencePurityGatedRecoveryMemory` in
  acting model (recent8 exactly), extended signal (newest 2 vs
  50-event reference, opposed_count), retained archive
  (events[:N-26]), archive concordance, joint test form
  (joint_count >= 1), recovery model, abstention trigger
  (opposed_count == 2), the full three-leg authority condition,
  the minority branch in full, and the reference-purity gate
  (>= 0.70) on BOTH recovery branches. The SINGLE new element is a
  RELEASE GATE on the ABSTENTION branch ONLY: abstention fires iff
  opposed_count == 2 AND carried-over authority armed (NOT
  stable_disagreement) AND leg P (reference_purity >= 0.70, the
  identical frozen quantity/threshold) AND leg S
  (acting_opposed_count >= 3 over the last 8 events against the same
  extended-reference majorities — at least one supporting opposed
  event beyond the triggering pair). Gate-blocked abstentions are
  recorded (abstention_disarmed_by_purity /
  abstention_disarmed_by_support; both false when the carried-over
  authority was already disarmed) and fall through to recent8.
  Minimum 52 events (never exercised in evaluation; all checkpoints
  >= 240 events). Separate optional learner; the default controller
  and all existing learners are untouched; the graded
  reference-purity candidate and every earlier candidate appear only
  as baselines.
- **Branch and commits:** `developmental-ai/abstention-release-gated-recovery`
  (forked from `developmental-ai/reference-purity-gated-recovery` @
  `30fe70b`). Protocol frozen at `8b11a38`; implementation at
  `d396299`; evaluation at `d718f4f`. This grading report is committed
  on top of the evaluation commit.
- **Frozen protocol:** `benchmarks/abstention_release_gated_recovery_protocol.json`
  (schema `developmental-ai.abstention-release-gated-recovery-protocol/v1`,
  frozen 2026-11-03, before any implementation, unit test, harness, or
  score inspection for this experiment).
- **Cohorts:** development 392003/392021/392039 and additional
  393001/393017/393041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit. Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/abstention_release_gated_recovery_results.json`
  (development) and
  `benchmarks/abstention_release_gated_recovery_additional_results.json`
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
  tests`: 1080 tests OK in the evaluation stage, and 1080 tests OK again
  in this grading stage (run this pass; the grading-stage changes are
  documentation only, no code changed). Focused candidate tests:
  34/34 PASS in the implementation stage.
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
  over the last 8 events, acting_matched/opposed counts,
  supporting_opposed_count, support threshold, abstention_gate_armed,
  both abstention-disarmed flags — plus every count, branch,
  recovery-fired / minority-fired / abstained / gate-evaluable flags,
  acting source, and the records-only reference-purity-rule,
  minority-rule, extended-rule, legacy-long-rule,
  unexpired-joint-rule, and bounded-authority-rule derivations), a
  checkpoint SHA256, and restore-replay identity verified true at
  every checkpoint in both cohorts (script-verified again in this
  grading stage — 72/72 entries per cohort; no criterion-7 field
  missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `d718f4f` or for this grading commit.
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
| 6 | PRIMARY stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **FAIL** | **PASS** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 k=32 states; NEW (d) abstained branch in 0 of 9 states) | **PASS** | **PASS** |
| 1 | Second-switch B2 protection preserved ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **PASS** | **PASS** |
| 4 | Return-A onset harm preserved (≤ guard AND ≤60% of recent8, pooled k=2,4) | **FAIL** | **PASS** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 6 (PRIMARY) — stationary control downstream selectivity (FAIL development, PASS additional)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **16/240** — (a) passes — harm **106** vs recent8 **115**
— (c) passes — but successes **118** vs recent8 **125** (required
≥ 119) — (b) **fails by 1**. The entire deficit is ONE state, and it
is the protocol's pre-registered central risk (expected failure
mode 1) realized exactly as specified: at control checkpoint **8**
(seed 392039) a stationary opposed pair **survived both gate legs**
— realized reference purity **0.857** (leg P armed, by design on
stationary evidence) and acting_opposed_count **3** with
supporting_opposed_count **1** (leg S satisfied at its minimum) —
and the candidate **abstained on all 16 tasks** there (0 successes /
0 harm at that state against recent8's 7 / 9 there; the abstention
was harm-protective and success-empty, and its −7 successes are the
cohort's entire control successes deficit). The gate did
release the cohort's other stationary trigger: at control
checkpoint 8, seed 392003, the records-only reference-purity-rule
derivation abstained, but the candidate's gate blocked it by leg S
alone (purity 0.857 armed, acting_opposed_count 2,
abstention_disarmed_by_support true) and fell through to recent8 —
so the purity-rule derivation took 2 abstention states on this
control arm and the candidate 1. The candidate also took one
productive control recovery (retained_archive at control k=2, seed
392021), a branch the gate does not govern. Net against the decisive
reference-purity baseline method on the same arm (115 successes /
93 harm / 32 abstentions): the gate converted one full refusal into
recent8 play (+3 successes, +13 harm at that cell) and left the
other standing — the successes line moved from 115 to 118 and still
fell 1 short of 119. A flipped pair on stationary evidence is
locally identical to an onset pair (pre-registered); the gate is a
calibrated evidence bar, and on this cohort the bar was met by a
stationary draw. Charged, not excused.

Additional: abstentions **0/240** — (a) passes — successes **122**
= recent8 **122** (required ≥ 116) — (b) passes — harm **118** =
recent8 **118** — (c) passes. The candidate is downstream-identical
to recent8 on every graded control checkpoint on this cohort: no
abstention trigger survived, none was gate-blocked on the control
arm (no disarmed flag is set at any additional control state), and
the records-only reference-purity-rule derivation also took recent8
at all 15 graded control states. This is the failure mode of the
preceding experiment repaired on the cohort type that failed it
there — and, symmetrically, the development failure above shows the
repair is a thinner lottery, not a property of the branch.

### Criterion 5 — release and productivity by checkpoint 32 (PASS, both cohorts)

Development: k=32 abstentions **0/144** — (a) passes — successes
**81** vs recent8 **77** (required ≥ 69) — (b) passes — non-recent8
branch in **1 of 9** switch-stage k=32 states — (c) passes — and the
abstained branch in **0 of 9** states — NEW sub-condition (d) passes.
The one non-recent8 state is a B2 minority_archive routing (seed
392003, realized purity 0.780, armed) — identical to the
reference-purity-rule derivation's 1/9 on this cohort, and the
candidate's k=32 totals are identical to the decisive
reference-purity baseline method's (81 successes / 63 harm /
0 abstentions): no abstention trigger was present at any development
k=32 state, so the gate changed no k=32 outcome here. Realized
purity across the 9 states was 0.618–0.780.

Additional: abstentions **0/144** — (a) passes — successes **69** =
recent8 **69** (required ≥ 61) — (b) passes — non-recent8 branch in
**1 of 9** states — (c) passes — abstained branch in **0 of 9** —
(d) passes. Here the gate did the exact work sub-condition (d) was
written for: the records-only reference-purity-rule derivation took
a non-recent8 branch in 2/9 states, one of them an **abstention** at
return-A checkpoint 32, seed 393041 — the same configuration that
supplied the preceding experiment's sole remaining additional k=32
state. The candidate recorded an abstention trigger there disarmed
by **both** gate legs (abstention_disarmed_by_purity AND
abstention_disarmed_by_support both true; realized purity 0.69,
acting_opposed_count 2, supporting_opposed_count 0) and fell
through to recent8, scoring that state's recent8 outcome instead of
0 successes / 0 harm. Against the decisive baseline method's k=32
totals (57 successes / 71 harm / 16 abstentions), the candidate's
69 / 75 / 0 is the release the protocol hypothesized: the late
abstention is gone from the records, at a cost of +4 harm at that
one state against the refusal it replaced (and the ungated minority
method's k=32 totals on this cohort, 53 / 91 / 0, show the
fall-through was also the best of the three late responses there).
The candidate's one remaining non-recent8 k=32 state is a B1
retained_archive routing (seed 393001, purity 0.72, armed), also
taken by the purity-rule derivation. Realized purity across the 9
states was 0.613–0.800.

### Criterion 1 — second-switch B2 protection preserved (PASS, both cohorts)

**(a) ENGAGEMENT:** minority recovery was TAKEN at **5 of 6** pooled
B2 onset states on both cohorts (3/3 at checkpoint 2 alone and 2/3
at checkpoint 4 on each); required ≥ 3. Realized minority fractions
at the B2 onset states were 0.273–0.310 (development) and
0.272–0.313 (additional), and realized purity at every B2 onset
state was armed (0.795–0.950 development, 0.781–0.897 additional).
**(b) SELECTIVITY:** minority TAKEN at **0 of 6** B1 onset states
and **0 of 6** return-A onset states on both cohorts (required
≤ 1 each). **(c) HARM:** B2 pooled onset harm candidate **37** vs
guard **77** (development) and **36** vs guard **40** (additional)
— passes — and vs recent8 **92 / 75** the 60% ceilings are 55.2 /
45.0 — passes on both. **(d) PRODUCTIVITY:** B2 pooled successes
candidate **59** vs guard + 16 = **19** (guard 3, development) and
**60** vs **24** (guard 8, additional) — passes. The abstention
release gate sits below both recovery branches and changed no B2
engagement figure on either cohort; the candidate's B2 onset
profile is the graded purity profile, preserved. Abstention-branch
detail at B2, reported as the protocol requires: the candidate
abstained at 0/6 B2 onset states on both cohorts (the purity
baseline method also 0/6 at B2 — its onset abstentions are at B1);
no B2 onset abstention was gate-disarmed on either cohort.

### Criterion 4 — return-A onset harm preserved (FAIL development, PASS additional)

Development: pooled return-A harm candidate **44** vs guard **49**
— (a) passes — but vs recent8 **69** the 60% ceiling is **41.4** —
(b) **fails by 2.6 harm** (44 recorded; the ceiling is a
real-valued bound, so the failure margin is 44 − 41.4). The
candidate is identical to the decisive reference-purity baseline
method on every return-A onset figure on this cohort (52 successes
/ 44 harm / 0 abstentions): the release gate changed nothing at
return-A onset here — regular recovery was TAKEN at 6/6 return-A
onset states and no return-A onset abstention was gate-disarmed —
so this failure is inherited from the carried-over profile, not
caused by the new element. It is charged unchanged, exactly as the
preceding experiment charged its inherited criterion-6 failure:
on this cohort the family's return-A play (archive-model recovery
at every onset state) converts at 44 harm where plain cumulative
and frozen retention score 36 harm with MORE successes (60 each —
see criterion 2). The graded purity experiment passed this
criterion on both of its cohorts (37 vs ceiling 55.8; 29 vs 46.8);
the ceiling is cohort-relative (60% of recent8's realized harm),
and on this cohort recent8's return-A harm (69) was low enough
that the same carried profile misses it.

Additional: candidate **48** vs guard **66** — (a) passes — and vs
recent8 **82** the ceiling is 49.2 — (b) passes, by 1.2 harm.
Regular recovery was TAKEN at 4/6 return-A onset states (2 states
fell through to recent8); no return-A onset abstention was
gate-disarmed; candidate identical to the reference-purity baseline
method's return-A onset figures (48 / 48).

### Criterion 2 — return-A recovery successes preserved (PASS, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **52**
against frozen_A **60** — the 40% floor passes (52 × 5 = 260 ≥
60 × 2 = 120) — and against the guard-relative floor of guard + 16
= **31** (guard scored 15) — passes. Additional: candidate **48**
against frozen_A **62** (floor passes: 240 ≥ 124) and guard + 16 =
**30** (guard scored 14) — passes. Reported in full, as the
protocol requires — and recorded with the same prominence as the
PASS: plain cumulative scored **60 / 56** return-A successes at
**36 / 40** harm and frozen_A **60 / 62** at **36 / 34** harm, so
on BOTH cohorts BOTH simple retention baselines beat the candidate
on both axes at return-A (candidate 52 at 44 harm development;
48 at 48 additional). The joint / bounded / long baselines scored
50 / 50 / 50 successes (development) and 33 / 25 / 33 (additional)
at return-A; the extended and minority baselines scored the
identical 52 / 48. Cumulative's dominance at the first return —
recorded as a secondary, unselected limitation in every preceding
grading in this line — is now total on these cohorts: it holds
against the candidate on successes AND harm on both.

### Criterion 3 — pooled onset harm not above the guard (PASS, both cohorts)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm
**160** vs guard **190** — (a) passes — with candidate harm ≤
recent8 in **6 of 6** individual cells — (b) passes (vs recent8
pooled 256). Additional: candidate **148** vs guard **178** — (a)
passes — with **6 of 6** cells ≤ recent8 (vs recent8 pooled 238).
The gate's pre-registered onset cost (expected failure mode 2)
realized on development only: candidate pooled onset abstentions
**16/288** vs the reference-purity baseline method's **32/288** —
one onset abstention firing was gate-disarmed, by leg S alone
(support-only; B1 checkpoint 4, seed 392039, falling through to
recent8), and pooled onset harm rose from the baseline
method's 145 to the candidate's 160 (+15) while pooled onset
successes rose 111 → 112. The margin absorbed it (criterion 3(a)
margin 30; criterion 1 and the B1 cells unaffected in grade). On
additional the candidate is identical to the baseline method on
every pooled onset figure (108 successes / 148 harm / 32
abstentions) — no onset abstention was gate-disarmed there.

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions,
actual harmful / productive / neutral outcomes, reported harmful,
and label flips for every stage; per-method successes / harmful
TEST actions / abstentions / attempted tasks at every checkpoint;
the candidate's full decision record (per-event extended-reference
signal records, legacy reference-24 signal records, archive
concordance records, per-event joint and legacy joint
flags/records, the full authority record, the full minority record,
the full purity record, AND the full abstention-gate record —
per-event acting-window opposition records over the last 8 events,
acting matched/opposed counts, supporting_opposed_count, support
threshold, abstention_gate_armed, both abstention-disarmed flags —
plus every count, branch, recovery-fired / minority-fired /
abstained / gate-evaluable flags, acting source, and the
records-only reference-purity-rule, minority-rule, extended-rule,
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
| B1-0 † | 0 / 48 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| B1-2 | 0 / 48 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| B1-4 | 1 / 31 / 16 | 1 / 47 | 0 / 16 / 32 | 15 / 33 |
| B1-8 | 13 / 3 / 32 | 20 / 28 | 22 / 10 / 16 | 35 / 13 |
| B1-16 | 24 / 8 / 16 | 37 / 11 | 33 / 15 / 0 | 33 / 15 |
| B1-32 | 31 / 17 / 0 | 31 / 17 | 18 / 30 / 0 | 18 / 30 |
| return-A-0 † | 9 / 39 / 0 | 0 / 48 | 4 / 44 / 0 | 4 / 44 |
| return-A-2 | 24 / 24 / 0 | 7 / 41 | 28 / 20 / 0 | 1 / 47 |
| return-A-4 | 28 / 20 / 0 | 20 / 28 | 20 / 28 / 0 | 13 / 35 |
| return-A-8 | 34 / 14 / 0 | 34 / 14 | 28 / 20 / 0 | 19 / 29 |
| return-A-16 | 27 / 21 / 0 | 27 / 21 | 19 / 29 / 0 | 27 / 21 |
| return-A-32 | 28 / 20 / 0 | 28 / 20 | 23 / 25 / 0 | 23 / 25 |
| B2-0 † | 0 / 48 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| B2-2 | 34 / 14 / 0 | 1 / 47 | 33 / 15 / 0 | 6 / 42 |
| B2-4 | 25 / 23 / 0 | 3 / 45 | 27 / 21 / 0 | 15 / 33 |
| B2-8 | 36 / 12 / 0 | 17 / 31 | 33 / 15 / 0 | 37 / 11 |
| B2-16 | 25 / 23 / 0 | 21 / 27 | 27 / 21 / 0 | 21 / 27 |
| B2-32 | 22 / 26 / 0 | 18 / 30 | 28 / 20 / 0 | 28 / 20 |
| control-0 † | 28 / 20 / 0 | 31 / 17 | 22 / 26 / 0 | 22 / 26 |
| control-2 | 30 / 18 / 0 | 30 / 18 | 29 / 19 / 0 | 29 / 19 |
| control-4 | 26 / 22 / 0 | 26 / 22 | 21 / 27 / 0 | 21 / 27 |
| control-8 | 5 / 27 / 16 | 12 / 36 | 21 / 27 / 0 | 21 / 27 |
| control-16 | 21 / 27 / 0 | 21 / 27 | 25 / 23 / 0 | 25 / 23 |
| control-32 | 36 / 12 / 0 | 36 / 12 | 26 / 22 / 0 | 26 / 22 |

† Checkpoint 0 is a reported diagnostic, not graded. k=0 candidate
harm per switch stage is 48 / 39 / 48 (development, B1 / return-A /
B2) and 48 / 44 / 48 (additional).

Reference points on the same cohorts (pooled onset, k=2,4, all
stages; successes / harm / abstentions): the decisive
abstention-gate comparison `reference_purity_gated_recovery`
(identical but for the abstention release gate) scored **111/145/32**
(development) and **108/148/32** (additional) pooled onset — on
additional identical to the candidate; on development the gate's
one disarmed onset firing accounts for the whole difference
(candidate 112/160/16). At checkpoint 32 it scored 81/63/0
(development, identical to the candidate) and 57/71/16 (additional,
against the candidate's 69/75/0 — see criterion 5). On the control
arm it scored 115/93/32 (development — two abstention states to the
candidate's one) and 122/118/0 (additional, identical). The
ungated `minority_archive_joint_recovery` scored k=32 72/72/0
(development) and 53/91/0 (additional). The harm comparator
`evidence_opposition_guard` scored pooled onset harm 190
(development) and 178 (additional). `cumulative` and `frozen_A`
dominate the candidate at return-A on both axes on both cohorts
(criterion 2, reported in full there). The privileged expected
oracle pooled onset successes/harm were 192/96 (development) and
206/82 (additional): onset tasks remain largely solvable, and
every realizable learner here remains far from that.

**Persistence note (checkpoints 8 and 16, reported not graded):**
pooled switch-stage successes/harm/abstentions at k=8 were 83/29/32
(development, identical to the reference-purity baseline method)
and 83/45/16 (additional, also identical); at k=16, 76/52/16
(development, vs the baseline method's 68/44/32 — the gate's
thinning shows here as +8 successes at +8 harm) and 79/65/0
(additional, identical). Realized purity at the switch-stage k=32
states (0.618–0.780 development, 0.613–0.800 additional) again sits
above the 0.5675 global-composition design value — the
pre-registered self-fit compression — and leg P was armed at 6/9
(development) and 4/9 (additional) of those states; the gate's
k=32 work on additional was done by the conjunction, not by leg P
alone (the disarmed return-A state had purity 0.69, below leg P's
threshold, AND no supporting event).

**Retention note:** the release gate removed late abstention from
the checkpoint-32 records on both cohorts (sub-condition (d),
new this cycle, PASSes on both — the first graded cycle in this
line in which no k=32 state on either cohort is an abstention) and
kept every recovery-branch release the purity gate had graded,
while thinning onset abstention on development by exactly one
firing at a designed, absorbed cost. What it did not do is make
stationary abstention impossible: at its minimum corroboration
(acting_opposed_count exactly 3) a stationary pair still fired a
full refusal mid-segment on development and decided the PRIMARY
criterion there. The gate raises the evidence bar for a refusal;
it does not — and by the pre-registered local-identity argument
cannot — tell a flipped stationary pair from a genuine onset pair.

**Generalization level:** at most handoff level 2–3 (choosing among
/ applying already-supplied representations under a rule change,
plus designer-supplied signal, concordance, minority, routing,
expiry, disagreement-age, reference-width, reference-purity, and
abstention-release rules). No level-6 or novel-representation claim
is made. The minority read the candidate carries exploits this
simulator's exact-inversion structure, and both gate legs read
segment composition in this simulator's geometry (240/64/48) — so
even the PASSes are bounded: release of an ungated abstention
branch by reference purity plus acting-window opposition
corroboration, in this simulator only — not general
excessive-abstention handling, not calibrated uncertainty, and not
real-world safety.

## Safety and evidence costs

- Harmful TEST actions: reported per cell above and per criterion;
  pooled onset 160 (development) / 148 (additional) against
  recent8's 256 / 238 and the guard's 190 / 178.
- Harmful TRAIN acquisition actions by the learner: **0** — the
  learner issues no training interventions; all TRAIN evidence
  comes from the shared external actor stream, whose actual harmful
  / productive / neutral outcomes, reported harm, and label flips
  are published per seed in the saved results (criterion 7).
- Failed-by-abstention: pooled onset 16 / 288 (development) and
  32 / 288 (additional); checkpoint-32 0 / 144 on both cohorts;
  stationary control 16 / 240 (development — the single surviving
  stationary state of criterion 6) and 0 / 240 (additional).
  Abstentions are scored as failed tasks, never as successes.
- Additional requested observations: **0**.
- False confidence / unnecessary abstention: the development
  control k=8 surviving abstention (purity 0.857,
  acting_opposed_count 3) is the cycle's one unnecessary full
  refusal; the development return-A harm failure (criterion 4) is
  false-confidence harm of the carried recovery profile, identical
  to the decisive baseline's. Both are graded above, not buried.
- Report integrity: frozen protocol committed before implementation
  (`8b11a38`); cohorts inspected only through the registered
  evaluation; no parameter was re-tuned against the 392003-family /
  393001-family cohorts after inspection. Provenance limitation:
  developer-selected simulation seeds in one engineered two-feature
  simulator family; not independent external proof.

## Scientific conclusion

**Partially demonstrated.** Per the protocol's own grading
definitions: NOT Demonstrated (criteria 6 and 4 FAIL on the
development cohort); NOT Failed (the protocol's Failed clause keys
on the additional cohort — criterion 6 FAILs on additional, or
criterion 5 FAILs on additional, or any of criteria 1–4 FAILs on
additional, or criterion 7 FAILs on either — and NONE of those
occurred: all seven criteria PASS on the additional cohort); NOT a
Regression (pooled onset harm 160 / 148 well below recent8's
256 / 238 on both cohorts; checkpoint-32 successes 81 / 69 against
the recent8 − 4 lines of 73 / 65; the stationary-control Regression
clause requires control successes below recent8 by more than 6 on
BOTH cohorts — development is −7 but additional is 0, so the clause
does not trigger; full unit suite and historical transfer benchmark
pass — see Verification). The residual category is therefore
Partially demonstrated, and it is stated with its limits rather
than smoothed over: the experiment's PRIMARY criterion PASSes on
the additional cohort — the cohort type whose stationary failure
motivated this cycle — and FAILs on development, where one
stationary abstention survived both gate legs at the minimum
corroboration level and cost the successes line by exactly the
1 success it was short. What is demonstrated, within this
simulator: a two-leg evidence bar (reference purity + acting-window
opposition corroboration) CAN remove abstention from the late
records entirely (criterion 5(d), both cohorts — on additional by
actively disarming, by both legs, the exact late-abstention
configuration the preceding experiment left standing) while
preserving B2 protection, return-A successes, pooled onset harm,
and the recovery branches' k=32 release on both cohorts. What is
NOT demonstrated: stationary selectivity as a property — the same
gate that went 0/240 on additional went 16/240 with a
criterion-deciding survival on development, and the development
return-A harm ceiling failed on the carried profile the gate does
not touch. Generalization level 2–3, simulator-bounded (see
Learning evaluation).

**Next limitation (selected for the next cycle, Priority 1):**
stationary abstention survival at the release gate's minimum
corroboration — the one surviving development state fired at
acting_opposed_count exactly 3 (a single supporting opposed event
beyond the triggering pair), the lowest corroboration the gate
admits, at a MID-segment stationary checkpoint (k=8, not k=32);
whether a higher corroboration bar for abstention (at least two
supporting opposed events) can close the stationary survival
without thinning onset abstention past the criterion 1/3/4 harm
margins — the protocol's own threshold arithmetic warns that
checkpoint-2 onset retention falls to roughly 0.18 under that bar,
so the trade is the hypothesis, graded on both sides — on NEW
cohorts under a NEW protocol. Recorded but not selected: the
development criterion-4 return-A harm failure is inherited from
the carried profile (candidate identical to the decisive baseline
at return-A onset on both cohorts), and cumulative / frozen_A now
dominate the candidate at return-A on both axes on both cohorts —
plain retention's first-return dominance over every gated variant
in this line remains open and unaddressed by gate tuning.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration, D1–D10/V2A/V2B
unchanged.
