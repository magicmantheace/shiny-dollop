# Long-disagreement release recovery — leg Q, a long-disagreement release on the regular recovery branch

**15 November 2026 protocol frozen; 16 November 2026
implementation; 16 November 2026 evaluation; graded 16 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `long_disagreement_release_recovery`
  — whether ONE changed element, leg Q, a long-disagreement
  release on the REGULAR recovery branch (the branch fires iff
  the standard path holds — `joint_count >= 1` AND authority
  armed AND leg P armed AND leg T passing AND (leg N OR
  leg D) — OR leg Q's path holds — authority armed AND leg P
  armed AND leg T passing AND `long_disagreement`, where
  `long_disagreement` is the authority condition's own carried
  field, `stable_disagreement AND
  preceding_stable_disagreement`, two 26-event windows against
  the retained archive's per-span majorities, NO new numeric
  value; the joint test and the leg N / leg D breadth complex
  are released on leg Q's path only, the standard path retained
  bit-for-bit; new decision-record field
  `long_disagreement_release_fired`, true exactly when the
  regular branch fires through leg Q while the standard path
  does not hold) can hold criterion 4's frozen return-A form
  on BOTH cohorts — the support-agreement grading's selected
  limitation (criteria 17/4 FAILed on BOTH cohorts carried
  identical to the decisive baseline, leg A disarming zero
  return-A states, criterion 2 FAILing development alongside
  them) — while holding stationary selectivity (criteria
  22/19/6), B1 engagement (criteria 21/9), checkpoint-32
  release (criteria 18/5), and B2 protection (criterion 1) as
  co-graded guards. By the frozen segment geometry leg Q's
  population is structurally empty at every graded B1, B2,
  and control checkpoint and at checkpoint 32 on every arm,
  and it can never pre-empt an abstention (abstention
  authority is armed iff NOT `stable_disagreement`). Leg P,
  leg R, leg C, leg S, leg L, leg A, leg T, leg W, leg N, and
  leg D were explicitly NOT re-tuned. Build Order Priority 1
  (Independent Learning); handoff §8 inconsistent adaptation
  to changing rules / slow or incorrect recovery of old
  knowledge. This protocol's PRIMARY criterion is criterion
  23, criterion 4's frozen return-A form promoted to PRIMARY.
  The protocol froze ONE grading cap: a Demonstrated verdict
  requires at least one graded return-A onset state in at
  least one cohort where the decisive baseline fell through
  to recent8 while the candidate fired the regular branch
  through leg Q (`long_disagreement_release_fired` true); any
  Demonstrated verdict would in any case be a return-A-onset
  verdict through the leg-Q cap alone, within the frozen
  segment geometry (the sustained-regime tail beyond that
  geometry is untested; no general return-recognition claim).
- **Candidate:** `LongDisagreementReleaseRecoveryMemory`
  (`developmental_ai/long_disagreement_release_recovery.py`)
  — IDENTICAL to the graded
  `SupportAgreementPartialRecoveryMemory` in every element
  except leg Q (see the campaign state and the frozen
  protocol for the full carried inventory).
- **Repository branch and exact commits:** branch
  `developmental-ai/long-disagreement-release-recovery`,
  forked from `7defa59`. Protocol frozen at `1829bed`;
  implementation at `ceb5f5d`; evaluation at `8ba0dfd` (the
  commit graded here); this grading commit sits on top of
  `8ba0dfd`.
- **Frozen protocol:**
  `benchmarks/long_disagreement_release_recovery_protocol.json`.
- **Seeds:** development 572003 / 572021 / 572039; additional
  573001 / 573017 / 573041 — both cohorts NEW and uninspected
  at freeze, both now INSPECTED. Never re-tune any parameter
  against them (or any earlier inspected cohort).
- **Decisive baseline:** the graded support-agreement
  candidate (identical but for leg Q). **Simplest credible
  baseline:** recent8.

## Verification

- Unit tests: PASS — full suite re-run in the grading stage
  (2537 tests; see the grading-stage run recorded in the
  campaign state).
- Historical regressions: PASS — historical transfer
  benchmark re-run in the grading stage, exit 0 (gains
  0.5567 / 0.50 / 0.51).
- Frozen cohorts: graded below, per criterion, per cohort.
- Linux validation: UNVERIFIED (no CI claimed for the
  grading commit).
- Windows validation: UNVERIFIED (no CI claimed for the
  grading commit).
- Replay identity: script-verified true at every checkpoint
  in both cohorts (72/72 entries per cohort) in the grading
  stage, with the evaluation analysis script re-run in full;
  no criterion-7 field missing; `support_threshold` 1 and
  `long_window_threshold` 1 everywhere; `long_disagreement`
  recomputed exactly (`stable_disagreement AND
  preceding_stable_disagreement`);
  `long_disagreement_release_fired` recomputed exactly
  ((NOT standard path) AND authority armed AND leg P armed
  AND leg T passing AND `long_disagreement`) and
  `recovery_fired` recomputed exactly as standard-path OR
  leg Q everywhere; long-disagreement-release-rule ==
  candidate branch and support-agreement-rule == decisive
  branch everywhere; the carried support-agreement fields
  recomputed exactly as in the preceding grading (agreement-
  disarmed states 2 dev / 6 add, all on states where the
  candidate is identical to decisive); the gate recomputed
  exactly everywhere (full: leg P alone; partial: leg P AND
  (leg R OR leg C) AND leg S AND leg L); companion fields
  recomputable at every partial state and at fallback
  elsewhere; kind never widened; acting lists of 8 and
  newest lists of 4 with all counts recomputable everywhere
  and newest records == acting tail;
  `minority_model_archive_count == archive_events_count` and
  `minority_model_inverted` true everywhere; cross-check PASS
  at every minority-fired state 5/5 dev and 7/7 add;
  acquisition 0, training actions 0, additional requested
  observations 0.

## Learning evaluation

Leg Q fired exactly ELEVEN states across both cohorts, every
one at return-A, every one converting a decisive-baseline
fall-through to recent8, ZERO UNEXPECTED — dev 7: 572021
k=0 (diagnostic, joint 0, purity 0.884, candidate retained
10/6 vs decisive recent8 0/16), 572021 k=2 (joint 1, newest
1, acting 1, purity 0.884, 10/6 vs 0/16, GRADED), 572021 k=4
(joint 0, purity 0.857, 10/6 vs 0/16, GRADED), 572021 k=8
(UNGRADED, 10/6 vs 8/8), 572039 k=0 (diagnostic, joint 0,
newest 2, acting 3, purity 0.818, 6/10 vs 1/15), 572039 k=2
(joint 0, purity 0.853, 6/10 vs 0/16, GRADED), 572039 k=4
(joint 0, purity 0.853, 6/10 vs 0/16, GRADED); add 4: 573017
k=0 (diagnostic, joint 1, newest 1, acting 2, purity 0.857,
6/10 vs 0/16), 573041 k=0 (diagnostic, joint 0, purity
0.849, 11/5 vs 0/16), 573041 k=2 (joint 0, purity 0.849,
11/5 vs 0/16, GRADED), 573041 k=4 (joint 1, newest 1,
acting 1, purity 0.839, 11/5 vs 1/15, GRADED). Graded
return-A onset conversions: 4 dev (2 at k=2, 2 at k=4) /
2 add (1 at k=2, 1 at k=4). Branch diffs vs decisive:
dev 7, add 4, ALL classified leg_Q_conversion; score diffs
vs decisive 7/72 dev and 4/72 add. Leg Q fired ZERO states
outside return-A on either cohort, exactly as the frozen
geometry scan predicted.

Scores [successes, harm] (abstained episodes third where
graded): pooled onset candidate [58, 150] dev vs decisive
[26, 182] and recent8 [27, 261]; add candidate [102, 106]
vs decisive [81, 127] and recent8 [40, 248]. Return-A
candidate [36, 60] dev vs decisive [4, 92] and recent8
[4, 92] (guard [4, 92]); add [56, 40] vs decisive [35, 61]
and recent8 [15, 81] (guard [7, 73]). B1 candidate [0, 16]
dev / [1, 31] add, identical to decisive on both. B2
candidate [22, 74] dev / [45, 35] add, identical to
decisive on both. Checkpoint-32 candidate [70, 74, 0] dev
and [64, 80, 0] add, identical to decisive AND recent8.
Control candidate [128, 80, 32] dev and [85, 123, 32] add,
IDENTICAL to decisive on both, vs recent8 [140, 100, 0] /
[95, 145, 0].

Per-criterion grading (development / additional), PRIMARY
criterion 23 first, then co-graded guards 17/4, 22/19/6,
21/9, 18/5, 1, 11, 2, 3, 7 — script-computed from the saved
detailed results at `8ba0dfd`:

- **C23 PRIMARY (= criterion 4's frozen return-A form):
  FAIL / PASS.** Development on ceiling sub-condition (b)
  alone — harm 60 vs guard 92 PASS (a), ceiling 0.60 ×
  recent8 92 = 55.2 FAIL (b) by 4.8. The residual dev
  return-A harm is exactly the two non-converted 572003
  fall-throughs (k=2: `long_disagreement` FALSE, joint 1,
  purity 0.875, 0/16; k=4: `long_disagreement` FALSE,
  joint 0, purity 0.867, 4/12 — 28 harm, shared identically
  with decisive and recent8) plus the four conversions' own
  32 harm (10/6, 10/6, 6/10, 6/10 in successes/harm terms:
  harm 6+6+10+10). Additional in full — harm 40 vs guard 73
  AND ceiling 0.60 × recent8 81 = 48.6, both sub-conditions
  hold.
- **C17 / C4 (the same computation in its carried guard
  positions): FAIL / PASS**, exactly as C23.
- **C22 / C19 / C6 (stationary selectivity, criterion 6's
  frozen form): FAIL / FAIL**, on sub-condition (b) alone
  on both cohorts — abstentions 32/240 AT the budget PASS
  (a) on both; successes 128 vs recent8 140 (line >= 134)
  dev and 85 vs 95 (line >= 89) add FAIL (b); harm 80 vs
  100 dev and 123 vs 145 add PASS (c). The candidate is
  branch-identical to decisive at every graded control
  state on both cohorts (leg Q structurally inert there, as
  frozen); the entire deficit on each cohort is exactly TWO
  carried partial S&L abstention firings, identical to
  decisive: dev 572021 k=2 (partial, supporting 1, stale 3,
  purity 0.800, abstained 0/0 vs recent8 6/10) and 572021
  k=4 (partial, supporting 2, stale 2, purity 0.778,
  abstained 0/0 vs recent8 6/10); add 573017 k=16 (partial,
  supporting 1, stale 2, purity 0.848, abstained 0/0 vs
  recent8 7/9) and 573041 k=4 (partial, supporting 1,
  stale 1, purity 0.848, abstained 0/0 vs recent8 3/13).
- **C21 / C9 (B1 engagement): PASS / PASS.** Dev TAKEN 5/6
  (3 full + 2 partial, paths R and R+C), harm 16 vs guard
  48 and < recent8 89; add TAKEN 4/6 (3 full + 1 partial,
  path C), harm 31 vs guard 59 and < recent8 81. Identical
  takings to decisive on both (leg Q inert at B1, as
  frozen).
- **C18 / C5 (checkpoint-32 release): PASS / PASS**, in
  full on both — abstentions 0/144, successes 70 = recent8
  70 dev and 64 = 64 add, non-recent8 0/9, abstained 0/9;
  zero abstained k32 states on either cohort.
- **C1 (B2 protection): FAIL / PASS.** Dev on (a), (c),
  and (d) — minority 1/6; harm 74 vs guard 69 FAIL and
  ceiling 0.60 × recent8 80 = 48.0 FAIL; successes 22 vs
  guard+16 = 27 FAIL; selectivity (b) PASS (B1 0/6,
  return-A 0/6). Carried identical to decisive (the
  minority branch is untouched by leg Q). Add in full —
  minority 4/6, harm 35 vs guard 60 and ceiling 51.6,
  successes 45 vs guard+16 = 20.
- **C11 (conjunction of C6 and C9): FAIL / FAIL** — on its
  stationary side only, both cohorts (C9 PASSes both).
- **C2 (return-A successes): PASS / PASS.** Dev successes
  36 vs frozen_A floor 0.40 × 64 = 25.6 and guard+16 = 20;
  add 56 vs floor 0.40 × 56 = 22.4 and guard+16 = 23. Note
  in full: frozen_A (64/32 dev, 56/40 add) and cumulative
  (66/30 both) still sit at or above the candidate's
  successes on both cohorts, frozen_A with lower harm on
  development (32 vs 60) and equal harm on additional
  (40 vs 40) — the candidate's return-A gain is against
  the decisive baseline and recent8, not against every
  carried method.
- **C3 (pooled onset): PASS / PASS** — harm 150 vs guard
  209 dev and 106 vs guard 192 add, cells 6/6 on both.
- **C7 (accounting / reproducibility): PASS / PASS** —
  replay 72/72 per cohort, all recomputations clean
  (above), acquisition 0.

**The grading cap is MET on BOTH cohorts** — six graded
return-A onset leg-Q conversions (dev 572021 k=2 and k=4,
572039 k=2 and k=4; add 573041 k=2 and k=4), at every one
of which the decisive baseline fell through to recent8
while the candidate fired the regular branch through
leg Q. Leg Q's mechanism is therefore demonstrated on its
designed population on both cohorts — and the PRIMARY
still FAILs on development, on the ceiling sub-condition
alone, because the conversions' own harm (32) plus the
two `long_disagreement`-false 572003 fall-throughs (28)
total 60 against a 55.2 ceiling.

## Safety and evidence costs

- Harmful task actions: pooled onset 150 dev / 106 add
  (vs decisive 182 / 127 and recent8 261 / 248); return-A
  60 dev / 40 add; B1 16 / 31; B2 74 / 35; control harm
  80 / 123 (below recent8 100 / 145 on both).
- Failed-by-abstention: control 32 abstained episodes per
  cohort (32/240, AT the frozen budget), all from the two
  carried partial S&L firings per cohort named under
  C22/19/6; onset abstentions 0 on both cohorts; k32
  abstentions 0.
- Additional requested observations / learner information
  acquisition / training actions: 0 / 0 / 0.
- False confidence and unnecessary abstention: leg Q's
  conversions fired the retained archive at states the
  decisive baseline abandoned to recent8 and were worth
  +53 successes / −53 harm pooled against decisive at
  return-A onset across both cohorts (dev +32/−32,
  add +21/−21); the stationary abstentions are the cycle's
  unnecessary-abstention cost, carried identical to
  decisive and charged in full under C22/19/6 and the
  Regression clause.
- Report integrity: all figures script-computed this pass
  from the saved detailed results at `8ba0dfd`; the
  evaluation analysis script was re-run in the grading
  stage with identical recomputations. No CI claimed for
  the evaluation or grading commits (Linux/Windows
  UNVERIFIED).

## Scientific conclusion

**FAILED / REGRESSION (stationary clause)**, under the
protocol's own definitions. The Failed clause triggers on
the additional cohort (criteria 22, 19, and 6 FAIL there,
and criterion 11 with them; criterion 7 PASSes both), and
PRIMARY criterion 23 FAILs on development on its ceiling
sub-condition alone. The Regression clause triggers on the
stationary arm: control successes 128 vs recent8 140
(−12) dev and 85 vs 95 (−10) add, both past the
more-than-6 both-cohorts line, on carried abstention
firings identical to the decisive baseline's. The other
Regression clauses do not trigger — pooled onset harm
150/106 below recent8 261/248, k=32 successes 70/64 above
the recent8 − 4 lines of 66/60, suite + transfer pass.

This is not a leg-Q failure on its own population: leg Q
converted every graded return-A onset fall-through it was
designed to reach (6/6 graded conversions across both
cohorts, cap MET on both), cut return-A harm against the
decisive baseline by 32 dev and 21 add at +32/+21
successes, and PASSed the PRIMARY in full on additional.
Development's PRIMARY failure is the arithmetic of the
remainder: the conversions' own 32 harm plus 28 harm from
the two 572003 states where `long_disagreement` is FALSE —
a population leg Q by construction cannot reach. The
cycle's Regression is likewise not leg Q's: it is the
carried support-agreement abstention profile drawing two
partial S&L stationary firings per cohort on these seeds,
at exactly the volume budget, each converting a productive
recent8 state (6/10, 6/10, 7/9, 3/13) into 16 abstained
episodes. Generalization level: handoff level 2–3 at most
(choosing among / applying designer-supplied rules); no
novel-representation, calibrated-uncertainty, or
real-world-safety claim. Any positive reading of leg Q is
a return-A-onset reading through the leg-Q cap alone,
within the frozen segment geometry, stated in those words.

## Next limitation selected

**P1 stationary selectivity of the carried
support-agreement abstention classes** — criteria 22/19/6
FAIL on BOTH cohorts on sub-condition (b) alone and carry
this cycle's Regression (control successes −12 dev /
−10 add against recent8), on an arm where leg Q is
structurally inert and the candidate is identical to the
decisive baseline at every control state. The entire
deficit on each cohort is two PARTIAL abstention firings
that pass the full support-agreement gate (supporting
>= 1 AND stale >= 1; purities 0.778–0.848), each worth
exactly its cohort's success deficit against recent8.
Whether an evidence-derived condition on the partial
abstention class — one that distinguishes these stationary
S&L firings from the B1 S&L partial takings that PASS
criteria 21/9 on both cohorts this cycle — can hold
criterion 6's frozen form on BOTH cohorts while holding
the return-A gains leg Q just demonstrated (criteria
23/17/4, PASSing additional and failing development on
the ceiling alone), B1 engagement (criteria 21/9, PASSing
both), checkpoint-32 release (criteria 18/5, PASSing
both), and B2 protection (criterion 1) as co-graded
guards, on NEW cohorts under a NEW protocol. Recorded but
not selected: development's return-A ceiling residual
(60 vs 55.2) — leg Q converted every convertible state;
the residual population is the two
`long_disagreement`-false 572003 fall-throughs plus the
conversions' own engagement harm, and a further return-A
retry would need a condition on a population this
experiment did not isolate; criterion 1 FAILs development
carried identical on the minority branch, which leg Q
does not touch, and PASSes additional in full — carried
as a co-graded guard.
