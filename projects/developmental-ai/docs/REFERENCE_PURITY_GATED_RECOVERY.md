# Reference purity gated recovery — onset-bounded expiry for both recovery branches

**2 November 2026 protocol / 3 November 2026 graded. Status: optional, simulated,
unpromoted. No default-controller promotion, no PR merge, no D1–D10 or
V2A/V2B roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `reference_purity_gated_recovery` — whether an
  evidence-derived expiry condition can restore checkpoint-32 release
  for the recovery branches, the limitation the graded
  minority-archive experiment selected: its PRIMARY B2-protection
  criterion PASSed on both cohorts, but criterion 5 (release by
  k=32) FAILed on both — the minority branch had NO expiry (a static
  archive fraction arming that only grows) and the regular branch
  was re-armed late by the corroboration leg — and on the additional
  cohort two stale k=32 routings at 0/16 each triggered the
  protocol's Regression clause. Build Order Priority 1 (Independent
  Learning), items 2 + 3 + 4; handoff §8 slow or incorrect recovery
  of old knowledge / weak uncertainty calibration. The protocol's
  PRIMARY criterion is criterion 5, release by checkpoint 32;
  criteria 1 (B2 protection) and 4 (return-A harm) are its co-graded
  guards. They are reported first, second, and third below, as the
  protocol requires.
- **Candidate:** `ReferencePurityGatedRecoveryMemory`
  (`developmental_ai/reference_purity_gated_recovery.py`) —
  IDENTICAL to the graded `MinorityArchiveJointRecoveryMemory` in
  acting model (recent8 exactly), extended signal (newest 2 vs
  50-event reference, opposed_count), retained archive
  (events[:N-26]), archive concordance, joint test form
  (joint_count >= 1), recovery model, abstention trigger
  (opposed_count == 2), the full three-leg authority condition
  (local disagreement, corroboration recent_concordant_count >= 2,
  long disagreement; strict-majority rule D * 2 > C in both
  windows), and the minority branch in full (minority set, fraction
  >= 0.25 AND discordant >= 8 arming, minority joint test,
  minority-set model). The SINGLE new element is a REFERENCE-PURITY
  expiry gate on the two recovery branches ONLY:
  reference_purity = reference-concordant / reference-matched events
  over the extended reference window (the 50 events preceding the
  newest 2), each scored against the reference's own per-span
  majorities; the gate is ARMED iff reference_purity >= 0.70;
  regular recovery fires iff joint_count >= 1 AND carried-over
  authority armed AND purity armed; minority recovery fires iff
  minority_joint_count >= 1 AND minority armed AND purity armed
  (below regular recovery, above abstention, as graded); abstention
  is NOT purity-gated. A recovery trigger whose own arming holds
  while purity is disarmed is recorded
  (recovery_disarmed_by_purity / minority_disarmed_by_purity) and
  falls through. Minimum 52 events (never exercised in evaluation;
  all checkpoints >= 240 events). Separate optional learner; the
  default controller and all existing learners are untouched; the
  graded minority-archive candidate and every earlier candidate
  appear only as baselines.
- **Branch and commits:** `developmental-ai/reference-purity-gated-recovery`
  (forked from `developmental-ai/minority-archive-joint-recovery` @
  `381aa61`). Protocol frozen at `46d496e`; implementation at
  `2330228`; evaluation at `2501dab`. This grading report is committed
  on top of the evaluation commit.
- **Frozen protocol:** `benchmarks/reference_purity_gated_recovery_protocol.json`
  (schema `developmental-ai.reference-purity-gated-recovery-protocol/v1`,
  frozen 2026-11-02, before any implementation, unit test, harness, or
  score inspection for this experiment).
- **Cohorts:** development 382003/382021/382039 and additional
  383001/383017/383041 — NEW at freeze, disjointness verified by
  project-wide search before the freeze commit. Both cohorts are now
  **INSPECTED** and must never be re-tuned against. Detailed results:
  `benchmarks/reference_purity_gated_recovery_results.json`
  (development) and
  `benchmarks/reference_purity_gated_recovery_additional_results.json`
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
  tests`: 1046 tests OK in the implementation stage, 1046 tests OK in
  the evaluation stage, and 1046 tests OK again in this grading stage
  (run this pass; the grading-stage changes are documentation only,
  no code changed). Focused candidate tests: 29/29 PASS in the
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
  joint and legacy joint flags/records, the full authority record,
  the full minority record, AND the full purity record — per-event
  reference concordance records over the 50 reference events,
  reference matched/concordant counts, reference_purity,
  purity_armed, purity_threshold, both disarmed-by-purity flags —
  plus every count, branch, recovery-fired / minority-fired /
  abstained / gate-evaluable flags, acting source, and the
  records-only minority-rule, extended-rule, legacy-long-rule,
  unexpired-joint-rule, and bounded-authority-rule derivations), a
  checkpoint SHA256, and restore-replay identity verified true at
  every checkpoint in both cohorts (script-verified again in this
  grading stage; no criterion-7 field missing anywhere).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `2501dab` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results
in this grading stage, not hand-copied. Denominators are exact episode
counts (48 per stage-checkpoint cell; 96 per pooled B2 or return-A
onset figure; 288 per pooled all-stage onset figure); decision-record
denominators are seed-checkpoint states (3 per stage per cohort at
checkpoint 2 alone; 6 per stage per cohort pooled at checkpoints 2
and 4; 9 switch-stage states per cohort at checkpoint 32). Criterion
5, this experiment's PRIMARY criterion, is reported first, and
criteria 1 and 4, its co-graded guards, next, as the protocol
requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 5 | PRIMARY release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 switch-stage k=32 states, from records) | **PASS** | **PASS** |
| 1 | Second-switch B2 protection preserved ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **PASS** | **PASS** |
| 4 | Return-A onset harm preserved (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **PASS** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 6 | Stationary control selectivity (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **FAIL** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 5 (PRIMARY) — release and productivity by checkpoint 32 (PASS, both cohorts)

Development: k=32 abstentions **0/144** — (a) passes — successes
**73** vs recent8 **74** (required ≥ 66) — (b) passes — and from the
decision records the candidate took a non-recent8 branch in **1 of
9** switch-stage k=32 states — (c) passes (required ≤ 1). The one
state is a B2 minority_archive routing (seed 382003, realized purity
0.727, armed) scoring 7/9 vs recent8's 8/8 there. Realized purity
across the 9 states was 0.645–0.758 (armed 3/9: the state above and
two return-A states at 0.758 / 0.744 where no recovery trigger was
present); no k=32 state on this cohort was disarmed by purity —
the candidate's k=32 totals are identical to the minority baseline
method's (73 successes / 71 harm), and the records-only minority-rule
derivation also took exactly 1/9 non-recent8 states here, so on
development the gate changed no k=32 outcome at all.

Additional: abstentions **16/144** — (a) passes — successes **64**
vs recent8 **66** (required ≥ 58) — (b) passes — and non-recent8
branch in **1 of 9** states — (c) passes. Here the gate did the
work the protocol designed it for: the records-only minority-rule
derivation took a non-recent8 branch in **4 of 9** k=32 states, and
recovery_disarmed_by_purity is recorded true at all four (return-A
seeds 383001 and 383017, return-A seed 383041, B2 seed 383041;
realized purity 0.694 / 0.697 / 0.694 / 0.684). The candidate's one
remaining non-recent8 state is a return-A **abstention** (seed
383041, 0 successes / 0 harm vs recent8's 2/14 there) — the branch
the purity gate deliberately does not govern, charged here under
this criterion exactly as pre-registered (expected failure mode 4).
Realized purity across the 9 states was 0.658–0.810 (armed 3/9,
none of them a taken recovery state). The honest counterweight,
recorded with the same prominence: on this cohort the four disarmed
late recoveries had been **productive** for the minority method —
its k=32 totals are 80 successes / 64 harm against the candidate's
64 / 64 — so the gate bought the records-level release (4/9 → 1/9)
and the criterion's success floor, but at a real productivity cost
against the ungated candidate on this cohort: release by purity is
blunt — it cannot distinguish a stale late routing from a
still-productive one. (On the graded minority cohorts the same
ungated branches scored 0/16 twice; which side of that tradeoff a
cohort lands on is cohort-variable, exactly as the preceding report
recorded for late firing itself.)

### Criterion 1 — second-switch B2 protection preserved (PASS, both cohorts)

**(a) ENGAGEMENT:** minority recovery was TAKEN at **5 of 6** pooled
B2 onset states on development (3/3 at checkpoint 2 alone, 2/3 at
checkpoint 4 — seed 382021 at k=4 recorded minority_joint_count 0)
and at **4 of 6** on additional (1/3 at k=2 — seeds 383001 and
383017 recorded minority_joint_count 0 — and 3/3 at k=4); required
≥ 3. Realized minority fractions at the taken states were
0.272–0.325 (development) and 0.273–0.301 (additional), and realized
purity at every B2 onset state was armed (0.784–0.900 development,
0.795–0.889 additional): **zero onset states on either cohort were
disarmed by purity** (no recovery_disarmed_by_purity or
minority_disarmed_by_purity flag is set at any pooled onset state in
either cohort) — the pre-registered central onset risk (expected
failure mode 1) did not materialize. The candidate is identical to
the minority baseline method on every pooled onset figure on both
cohorts. **(b) SELECTIVITY:** minority TAKEN at **0 of 6** B1 onset
states and **0 of 6** return-A onset states on both cohorts
(required ≤ 1 each). **(c) HARM:** B2 pooled onset harm candidate
**48** vs guard **64** (development) and **49** vs guard **78**
(additional) — passes — and vs recent8 **96 / 90** the 60% ceilings
are 57.6 / 54.0 — passes on both. **(d) PRODUCTIVITY:** B2 pooled
successes candidate **48** vs guard + 16 = **16** (guard 0,
development) and **47** vs **18** (guard 2, additional) — passes.
Regular recovery was TAKEN at 1/6 B1 onset states (development) and
0/6 (additional), and at 5/6 return-A onset states on both cohorts,
exactly as the minority-rule derivation records.

### Criterion 4 — return-A onset harm preserved (PASS, both cohorts)

Development: pooled return-A harm candidate **37** vs guard **79**
— (a) passes — and vs recent8 **93** the 60% ceiling is 55.8 — (b)
passes. Additional: candidate **29** vs guard **54** — (a) passes —
and vs recent8 **78** the ceiling is 46.8 — (b) passes. Identical to
the minority baseline's return-A harm on both cohorts (37 / 29):
the purity gate gave nothing back at the first return, because it
never disarmed there.

### Criterion 2 — return-A recovery successes preserved (PASS, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **59**
against frozen_A **70** — the 40% floor passes (59 × 5 = 295 ≥
70 × 2 = 140) — and against the guard-relative floor of guard + 16 =
**17** (guard scored 1) — passes. Additional: candidate **67**
against frozen_A **64** (floor passes: 335 ≥ 128) and guard + 16 =
**26** (guard scored 10) — passes. Reported in full, as the protocol
requires: plain cumulative scored **68 / 78** return-A successes at
**28 / 18** harm — it beats the candidate on both axes on BOTH
cohorts (candidate 59 at 37 harm; 67 at 29); the minority baseline
scored the identical 59 / 67 at 37 / 29, the extended baseline the
identical return-A successes and harm, and the joint / bounded /
long baselines 36 / 67 successes on development / additional.

### Criterion 3 — pooled onset harm not above the guard (PASS, both cohorts)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate harm
**137** vs guard **195** — (a) passes — with candidate harm ≤
recent8 in **6 of 6** individual cells — (b) passes (vs recent8
pooled 273). Additional: candidate **133** vs guard **218** — (a)
passes — with **6 of 6** cells ≤ recent8 (vs recent8 pooled 254).
Identical figures to the minority baseline method on both cohorts:
the gate changed no onset cell anywhere.

### Criterion 6 — stationary control downstream selectivity (PASS development, FAIL additional)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **0/240** — (a) passes — successes **124** vs recent8
**118** (required ≥ 112) — (b) passes — harm **116** vs recent8
**122** — (c) passes. The candidate took a non-recent8 branch at
1/15 graded control states (a regular recovery at control k=2,
seed 382039, scoring 9/7 vs recent8's 3/13 — productive), and no
control state differed from the records-only minority-rule
derivation. This repairs, on this cohort, the development control
failure the graded minority candidate recorded (harm +2 from one
control recovery firing at k=8) — the repair is the cohort's draws,
not the gate: purity was armed at that state too and the branch
taken is the minority rule's own.

Additional: abstentions **16/240** — (a) passes — but successes
**110** vs recent8 **120** (required ≥ 114) — (b) **fails by 4** —
harm **114** vs recent8 **120** — (c) passes. The entire deficit is
ONE state: at control checkpoint 32 (seed 383017) the candidate
**abstained on all 16 tasks** (0 successes / 0 harm vs recent8's
10/6 there), downstream of the abstention branch — opposed_count
== 2 with its carried-over authority armed on stationary evidence,
at realized purity 0.886 (armed; purity does not govern
abstention, by this protocol's design). The candidate is identical
to the minority baseline method AND to the guard method on every
pooled control figure on this cohort (110 / 114 / 16), and no
control state differed from the records-only minority-rule
derivation on either cohort: the purity gate changed nothing on
the stationary arm anywhere, exactly as designed (design purity
0.8375, armed throughout), and the failure is inherited from the
carried-over abstention branch, not caused by the new element —
charged here unchanged, as the protocol requires.

### Criterion 7 — full accounting (PASS, both cohorts)

Both saved result files contain, per seed: TRAIN actor actions,
actual harmful / productive / neutral outcomes, reported harmful,
and label flips for every stage; per-method successes / harmful
TEST actions / abstentions / attempted tasks at every checkpoint;
the candidate's full decision record (per-event extended-reference
signal records, legacy reference-24 signal records, archive
concordance records, per-event joint and legacy joint
flags/records, the full authority record, the full minority record,
AND the full purity record — per-event reference concordance
records over the 50 reference events, reference matched/concordant
counts, reference_purity, purity_armed, purity_threshold, both
disarmed-by-purity flags — plus every count, branch,
recovery-fired / minority-fired / abstained / gate-evaluable flags,
acting source, and the records-only minority-rule, extended-rule,
legacy-long-rule, unexpired-joint-rule, and
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
| B1-0 † | 2 / 46 / 0 | 2 / 46 | 0 / 48 / 0 | 0 / 48 |
| B1-2 | 5 / 11 / 32 | 5 / 43 | 2 / 30 / 16 | 2 / 46 |
| B1-4 | 7 / 41 / 0 | 7 / 41 | 7 / 25 / 16 | 8 / 40 |
| B1-8 | 13 / 35 / 0 | 13 / 35 | 27 / 21 / 0 | 27 / 21 |
| B1-16 | 29 / 19 / 0 | 29 / 19 | 19 / 29 / 0 | 19 / 29 |
| B1-32 | 26 / 22 / 0 | 26 / 22 | 21 / 27 / 0 | 21 / 27 |
| return-A-0 † | 12 / 36 / 0 | 1 / 47 | 0 / 48 / 0 | 0 / 48 |
| return-A-2 | 24 / 24 / 0 | 1 / 47 | 36 / 12 / 0 | 8 / 40 |
| return-A-4 | 35 / 13 / 0 | 2 / 46 | 31 / 17 / 0 | 10 / 38 |
| return-A-8 | 28 / 20 / 0 | 27 / 21 | 37 / 11 / 0 | 26 / 22 |
| return-A-16 | 24 / 24 / 0 | 19 / 29 | 31 / 17 / 0 | 25 / 23 |
| return-A-32 | 22 / 26 / 0 | 22 / 26 | 19 / 13 / 16 | 21 / 27 |
| B2-0 † | 0 / 48 / 0 | 0 / 48 | 1 / 47 / 0 | 1 / 47 |
| B2-2 | 29 / 19 / 0 | 0 / 48 | 13 / 35 / 0 | 1 / 47 |
| B2-4 | 19 / 29 / 0 | 0 / 48 | 34 / 14 / 0 | 5 / 43 |
| B2-8 | 13 / 35 / 0 | 14 / 34 | 33 / 15 / 0 | 11 / 37 |
| B2-16 | 25 / 23 / 0 | 25 / 23 | 30 / 18 / 0 | 26 / 22 |
| B2-32 | 25 / 23 / 0 | 26 / 22 | 24 / 24 / 0 | 24 / 24 |
| control-0 † | 19 / 29 / 0 | 19 / 29 | 29 / 19 / 0 | 29 / 19 |
| control-2 | 25 / 23 / 0 | 19 / 29 | 24 / 24 / 0 | 24 / 24 |
| control-4 | 19 / 29 / 0 | 19 / 29 | 22 / 26 / 0 | 22 / 26 |
| control-8 | 29 / 19 / 0 | 29 / 19 | 24 / 24 / 0 | 24 / 24 |
| control-16 | 27 / 21 / 0 | 27 / 21 | 24 / 24 / 0 | 24 / 24 |
| control-32 | 24 / 24 / 0 | 24 / 24 | 16 / 16 / 16 | 26 / 22 |

† Checkpoint 0 is a reported diagnostic, not graded. k=0 candidate
harm per switch stage is 46 / 36 / 48 (development, B1 / return-A /
B2) and 48 / 48 / 47 (additional).

Reference points on the same cohorts (pooled onset, k=2,4, all
stages; successes / harm / abstentions): the decisive purity-gate
comparison `minority_archive_joint_recovery` (identical but for the
purity gate) scored **119/137/32** (development) and **123/133/32**
(additional) pooled onset — identical to the candidate on both
cohorts, because the gate disarmed no onset state anywhere. Its
realized differences are entirely at k=32 and entirely on the
additional cohort (candidate 64 successes vs its 80, at identical
64 harm, with the candidate's 16 abstentions against its 0 — see
criterion 5). `extended_reference_joint_recovery` scored pooled
onset 71/153/64 (development) and 78/162/48 (additional) — no B2
protection on either. The harm comparator
`evidence_opposition_guard` scored pooled onset harm 195
(development) and 218 (additional). `cumulative` scored return-A
pooled successes **68 / 78** at return-A harm **28 / 18** — it
dominates the candidate at return-A on both axes on both cohorts,
while scoring 0 B2 successes at 96 B2 harm on both: undifferentiated
retention still cannot protect the second switch, and the gated
minority read still can. `frozen_A` scored return-A **70 / 64**
successes at **26 / 32** harm and 0 B2 successes. The privileged
expected oracle pooled onset successes/harm were 206/82
(development) and 198/90 (additional): onset tasks remain largely
solvable, and every realizable learner here remains far from that.

**Persistence note (checkpoints 8 and 16, reported not graded):**
pooled switch-stage successes/harm at k=8 were 54/90 (development,
identical to recent8 and to the minority method) and 97/47
(additional, identical to the minority method, vs recent8 64/80);
at k=16, 78/66 (development, vs recent8 73/71) and 80/64
(additional, vs the minority method's 82/62). Realized purity
trajectories track the design values with the pre-registered
self-fit compression visible at k=32 (realized 0.645–0.810 across
the 18 switch-stage k=32 states of both cohorts against the 0.5675
global-composition design value; armed at 6/18 states, of which
exactly one took a recovery branch).

**Retention note:** the purity gate is the first expiry mechanism
in this line to restore the checkpoint-32 records condition on
both cohorts while leaving the onset profile — B2 protection and
the first return — numerically untouched on both cohorts. Its
release action was decisive only where it was needed in the
records sense on the additional cohort (4/9 → 1/9), and there it
also removed four late recoveries that were in fact productive —
so what is demonstrated is records-level, onset-bounded release,
not a way to tell stale retained knowledge from still-valid
retained knowledge late in a segment.

**Generalization level:** at most handoff level 2–3 (choosing among
/ applying already-supplied representations under a rule change,
plus designer-supplied signal, concordance, minority, routing,
expiry, disagreement-age, reference-width, and reference-purity
rules). No level-6 or novel-representation claim is made. The
minority read the gate bounds exploits this simulator's
exact-inversion structure, and the purity quantity reads segment
mixture in the reference window of this simulator's geometry
(240/64/48) — so even the PASSes are bounded: onset-bounded release
of retained-evidence recovery by reference self
...[truncated 8065 chars]