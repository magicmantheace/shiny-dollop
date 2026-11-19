# Disagreeing span partial recovery — leg X, a local-archive span-disagreement leg on partial abstention triggers only

**18 November 2026 protocol frozen; 18 November 2026
implementation; 18 November 2026 evaluation; graded 18 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `disagreeing_span_partial_recovery`
  — whether ONE changed element, leg X, a local-archive
  span-disagreement leg on PARTIAL abstention triggers only
  (the partial gate becomes leg P AND (leg R OR leg C) AND
  leg S AND leg L AND leg V AND
  (`disagreeing_span_count >= 1`), `disagreeing_span_count`
  the carried authority-record field counting comparable
  spans whose local-window (`events[-26:]`) majority
  disagrees with the retained archive's majority for that
  span, at its presence value 1, NO new numeric value; the
  full gate stays leg P alone; new decision-record field
  `abstention_disarmed_by_disagreeing_span`) can hold
  criterion 6's frozen stationary form on BOTH cohorts —
  the minority-removal grading's selected limitation
  (criteria 24/22/19/6 were the SOLE failing family, FAILing
  additional on sub-condition (b) alone by 1 success, the
  entire deficit one kept concordant-0 partial S&L firing)
  — while holding the B2 gains (criterion 1), the return-A
  gains (criteria 23/17/4), B1 engagement (criteria 21/9,
  a LIVE priced guard: leg X removes 6/26 pooled B1 onset
  partial takings in the evidence review), checkpoint-32
  release (criteria 18/5), and criteria 11/2/3 as co-graded
  guards. Leg P, leg R, leg C, leg S, leg L, leg A, leg V,
  leg T, leg W, leg N, leg D, leg Q and the minority-branch
  leg-W removal were explicitly NOT re-tuned; the minority
  branch is carried bit-for-bit from the decisive baseline.
  Build Order Priority 1 (Independent Learning); handoff §8
  inconsistent adaptation / slow or incorrect recovery of
  old knowledge. This protocol's PRIMARY criterion is
  criterion 24, criterion 6's frozen stationary form
  promoted to PRIMARY. The protocol froze ONE grading cap:
  a Demonstrated verdict requires at least one graded
  control state in at least one cohort where the decisive
  baseline took a kept concordant-0 partial S&L abstention
  with `disagreeing_span_count == 0` while the candidate was
  disarmed by leg X and fell through to recent8; any
  Demonstrated verdict is a PARTIAL-class verdict through
  the leg-X cap alone.
- **Candidate:** `DisagreeingSpanPartialRecoveryMemory`
  (`developmental_ai/disagreeing_span_partial_recovery.py`)
  — IDENTICAL to the graded
  `MinorityActingBreadthRemovalRecoveryMemory` in every
  element except leg X (see the campaign state and the
  frozen protocol for the full carried inventory).
- **Repository branch and exact commits:** branch
  `developmental-ai/disagreeing-span-partial-recovery`,
  forked from `070e52c`. Protocol frozen at `3d9338d`;
  implementation at `5c11417`; evaluation at `8a16e7a` (the
  commit graded here); this grading commit sits on top of
  `8a16e7a`.
- **Frozen protocol:**
  `benchmarks/disagreeing_span_partial_recovery_protocol.json`.
- **Seeds:** development 602003 / 602021 / 602039; additional
  603001 / 603017 / 603041 — both cohorts NEW and uninspected
  at freeze, both now INSPECTED. Never re-tune any parameter
  against them (or any earlier inspected cohort).
- **Decisive baseline:** the graded minority-removal
  candidate (identical but for leg X). **Simplest credible
  baseline:** recent8.

## Verification

- Unit tests: PASS — full suite re-run in the grading stage
  (3053 tests OK).
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
  `long_window_threshold` 1 everywhere;
  `disagreeing_span_count` and `comparable_span_count`
  recomputed exactly from the `expiry_spans` records;
  `abstention_disarmed_by_disagreeing_span` recomputed
  exactly (gate blocked AND partial AND other legs pass AND
  support_agreement_armed AND concordant == 0 AND
  disagreeing == 0); gate recomputed exactly everywhere
  (full: leg P alone; partial: leg P AND (leg R OR leg C)
  AND leg S AND leg L AND leg V AND
  disagreeing_span_count >= 1);
  `abstention_taken_through_long_window` false at every
  taken state, as carried; disagreeing-span-rule ==
  candidate branch and minority-breadth-removal-rule ==
  decisive branch everywhere;
  `minority_breadth_removal_fired` recomputed exactly as
  carried; `singleton_release_fired` 0 firings on either
  cohort, carried identical to decisive, and the
  `recovery_fired` composition recomputed everywhere;
  companion fields recomputable at every partial state and
  at fallback elsewhere; kind never widened; acting lists
  of 8 and newest lists of 4 with all counts recomputable
  everywhere and newest records == acting tail;
  `minority_model_archive_count == archive_events_count`
  and `minority_model_inverted` true everywhere;
  cross-check PASS at every minority-fired state 8/8 dev
  and 10/10 add; acquisition 0, training actions 0,
  additional requested observations 0.

## Learning evaluation

Leg X disarmed exactly TWO states across both cohorts, ZERO
on development and two on additional, every one a PARTIAL
S&L trigger the decisive baseline took as a kept
concordant-0 firing with `disagreeing_span_count == 0`, ALL
classified leg_X_disarming, ZERO UNEXPECTED — add 603001 B1
k=4 (GRADED B1 onset: supporting 1, stale 4, concordant 0,
disagreeing 0, comparable 3, purity 0.8529, candidate recent8
1/15 vs decisive abstained 0/0) and add 603041 control k=8
(GRADED control: supporting 1, stale 2, concordant 0,
disagreeing 0, comparable 4, purity 0.8286, candidate recent8
11/5 vs decisive abstained 0/0 — the PRIMARY criterion 24
grading cap's population, on the additional cohort). Branch
diffs vs decisive: dev 0, add 2, ALL classified
leg_X_disarming; score diffs vs decisive 0/72 dev and 2/72
add. Kept concordant-0 partial S&L takings under leg X
(disagreeing >= 1): dev 3 (602003 B1 k=4 disagreeing 2,
602003 B1 k=8 disagreeing 4 UNGRADED, 602021 control k=4
disagreeing 1), add 0.

Scores [successes, harm] (abstained episodes third where
graded): pooled onset candidate [106, 134] dev IDENTICAL to
decisive vs recent8 [61, 227]; add candidate [115, 173] vs
decisive [114, 158] (the sole gap the B1 leg-X fall-through:
+1 success, +15 harm) and recent8 [46, 242]. B1 candidate
[11, 37] dev identical to decisive; add [2, 94] vs decisive
[1, 79] and IDENTICAL to recent8 [2, 94] and guard [2, 94].
B2 candidate [31, 65] dev / [51, 45] add, identical to
decisive on both. Return-A candidate [64, 32] dev /
[62, 34] add, identical to decisive on both. Checkpoint-32
candidate [63, 81, 0] dev identical to decisive vs recent8
[65, 79, 0]; add [91, 53, 0] identical to decisive vs
recent8 [93, 51, 0]. Control candidate [87, 121, 32] dev
IDENTICAL to decisive vs recent8 [89, 151, 0] (the two taken
control abstentions: 602003 k=2 FULL, recent8 cell 2/14, and
602021 k=4 partial S&L concordant 0 disagreeing 1 KEPT under
leg X, recent8 cell 0/16); add [118, 106, 16] vs decisive
[107, 101, 32] (the sole difference the graded control leg-X
disarming above: +11 successes, +5 harm, −16 abstained
episodes) and recent8 [128, 112, 0] (the one taken control
abstention a FULL firing at 603017 k=2, recent8 cell 10/6 —
leg X cannot touch the full class by construction).
Engagement onset (k=2/4): B1 abstained dev 3/6 (2 full + 1
partial) identical to decisive, add 0/6 vs decisive 1/6 (the
leg-X B1 disarming); B2 minority dev 4/6 and add 5/6,
identical to decisive; return-A recovery dev 6/6 and add
6/6, identical to decisive.

Per-criterion grading (development / additional), PRIMARY
criterion 24 first, then co-graded guards 22/19/6, 1,
23/17/4, 21/9, 18/5, 11, 2, 3, 7 — script-computed from the
saved detailed results at `8a16e7a`:

- **C24 PRIMARY (stationary selectivity, criterion 6's
  frozen form, through leg X): PASS / FAIL.** Dev:
  abstentions 32/240 AT the budget PASS (a); successes 87
  vs recent8 89, line >= 83, PASS (b); harm 121 vs 151
  PASS (c) — identical to decisive at every state. Add:
  abstentions 16/240 PASS (a); successes 118 vs recent8
  128, line >= 122, FAIL (b) by 4; harm 106 vs 112 PASS
  (c). Additional's entire remaining (b) deficit is the one
  taken control abstention leg X cannot touch: the FULL
  firing at 603017 control k=2 (supporting 0, stale 3,
  purity 0.8529, abstained 0/0 vs recent8 10/6), whose
  10-success cost is exactly the candidate's −10 gap
  against recent8; decisive's additional control profile
  [107, 101, 32] would fail (b) by 15, so leg X's one graded
  disarming closed 11 of the 15.
- **C22 / C19 / C6 (stationary selectivity, same
  computation): PASS / FAIL** — identical figures to C24
  on both cohorts.
- **C1 (B2 protection): FAIL / FAIL.** Dev on (c) alone:
  minority 4/6 PASS (a); selectivity PASS (b) (B1 minority
  0/6, return-A minority 0/6); harm 65 vs guard 56 FAIL
  and ceiling 0.60 × recent8 85 = 51.0 FAIL (c); successes
  31 vs guard+16 = 24 PASS (d). Add on (c)-ceiling alone:
  minority 5/6 PASS (a); selectivity PASS (b); harm 45 vs
  guard 63 PASS but ceiling 0.60 × recent8 70 = 42.0 FAIL
  by 3 (c); successes 51 vs guard+16 = 33 PASS (d).
  Identical to decisive on both cohorts — leg X disarmed
  zero B2 states; this is the preceding cycle's recorded
  thin ceiling margin (44 vs 45.6) realized as a failure
  on new draws, carried, not caused by leg X.
- **C23 / C17 / C4 (return-A harm, criterion 4's frozen
  form): PASS / PASS**, in full on both — dev harm 32 vs
  guard 69 and ceiling 0.60 × recent8 75 = 45.0; add harm
  34 vs guard 62 and ceiling 0.60 × recent8 78 = 46.8.
  Identical to decisive on both; leg X's return-A onset
  population is zero, as frozen (structurally inert).
- **C21 / C9 (B1 engagement): PASS / FAIL.** Dev TAKEN 3/6
  AT the floor (2 full + 1 partial, path R+C), harm 37 vs
  guard 48 and < recent8 67 — identical takings to
  decisive. Add TAKEN 0/6 FAIL (a) — decisive took 1/6, its
  one taking exactly the graded B1 leg-X disarming at
  603001 k=4 above; harm 94 vs guard 94 PASS (b) at
  equality but 94 < recent8 94 FAIL (c) — the candidate is
  identical to recent8 and guard at B1 onset on additional.
  This is leg X's pre-registered B1 price realized on the
  additional draw: the evidence review priced leg X
  removing 6/26 pooled B1 onset partial takings.
- **C18 / C5 (checkpoint-32 release): PASS / FAIL.** Dev
  in full — abstentions 0/144, successes 63 vs the
  recent8 − 8 line of 57, non-recent8 1/9 (the carried
  retained firing at 602039 return-A k=32, identical to
  decisive), abstained 0/9. Add on (c) alone —
  abstentions 0/144 PASS, successes 91 vs line 85 PASS,
  non-recent8 2/9 FAIL (the two carried non-recent8 firings
  at k=32: 603001 B2 minority and 603041 return-A retained,
  both identical to decisive), abstained 0/9 PASS. Leg X's
  k=32 population is zero, as frozen (structurally inert).
- **C11 (conjunction of C6 and C9): PASS / FAIL** — the
  additional failure is both of its sides (stationary (b)
  and B1 (a)/(c)); the development conjunction PASSes.
- **C2 (return-A successes): PASS / PASS.** Dev successes
  64 vs frozen_A floor 0.40 × 60 = 24.0 and guard+16 = 27;
  add 62 vs floor 0.40 × 74 = 29.6 and guard+16 = 34. Note
  in full: frozen_A's return-A successes (60 dev / 74 add)
  sit below the candidate's on development and above it on
  additional this cycle.
- **C3 (pooled onset): PASS / PASS** — harm 134 vs guard
  173 dev and 173 vs guard 219 add, cells 6/6 on both.
- **C7 (accounting / reproducibility): PASS / PASS** —
  replay 72/72 per cohort, all recomputations clean
  (above), acquisition 0.

**The grading cap is MET on the additional cohort and NOT
MET on development** — exactly ONE graded control leg-X
disarming occurs across both cohorts (add 603041 control
k=8 above), so leg X is demonstrated on its designed
population on one cohort; but a Demonstrated verdict
additionally requires all sixteen criteria to PASS on both
cohorts, which does not hold. Any positive reading would in
any case be a PARTIAL-class verdict through the leg-X cap
alone, on one graded state, in one cohort, no full-class
claim.

## Safety and evidence costs

- Harmful task actions: pooled onset 134 dev / 173 add (vs
  decisive 134 / 158 and recent8 227 / 242); return-A 32 /
  34; B1 37 / 94; B2 65 / 45; control harm 121 / 106 (below
  recent8 151 / 112).
- Failed-by-abstention: control 32 abstained episodes dev
  (32/240, AT the budget — two taken control abstentions)
  and 16 add (16/240, the one FULL firing at 603017 k=2);
  onset abstentions identical to decisive except the two
  leg-X disarmings; k32 abstentions 0.
- Additional requested observations / learner information
  acquisition / training actions: 0 / 0 / 0.
- False confidence and unnecessary abstention: leg X's two
  disarmings converted decisive abstentions 0/0 into recent8
  actions at 1/15 (B1 onset — a near-worst-cell conversion,
  +15 harm for +1 success, the priced B1 tail) and 11/5
  (graded control — +11 successes for +5 harm, the designed
  stationary gain). The remaining unnecessary-abstention
  cost on additional is the FULL control firing at 603017
  k=2 (0/0 vs recent8 10/6), a class no partial leg in this
  line touches.
- Report integrity: all figures script-computed this pass
  from the saved detailed results at `8a16e7a`; the
  evaluation analysis script was re-run in the grading
  stage with identical recomputations. No CI claimed for
  the evaluation or grading commits (Linux/Windows
  UNVERIFIED).

## Scientific conclusion

**FAILED, not a Regression**, under the protocol's own
definitions. The Failed clause triggers on the additional
cohort several times over: PRIMARY criterion 24 (and its
carried forms 22/19/6) FAIL there on sub-condition (b)
alone, and criteria 1, 21, 9, 18, 5, and 11 FAIL there with
them; criterion 1 also FAILs development on its harm
ceiling; criterion 7 PASSes both. The Regression clauses
do not trigger — pooled onset harm 134/173 below recent8
227/242, control successes −2 dev / −10 add (the clause
needs more than −6 on BOTH cohorts), k=32 successes 63/91
above the recent8 − 4 lines of 61/89, suite + transfer
pass. Leg X itself did exactly what it was designed to do
on the population it drew: it disarmed the one graded
control concordant-0 partial S&L firing with
disagreeing_span_count == 0 on additional (cap MET) and
closed 11 of decisive's 15-success stationary deficit
there — but additional's stationary (b) still FAILs by 4,
because the cohort's other taken control abstention is a
FULL firing, a class leg X cannot touch by construction;
and leg X's priced B1 tail was realized on the same cohort
(its one B1 disarming was decisive's only B1 taking there,
failing criteria 21/9). Development drew zero leg-X
disarmings and PASSes the PRIMARY as a carried profile
identical to decisive. Six of sixteen criteria PASS on
both cohorts (23/17/4, 2, 3, 7); criterion 1 FAILs both,
carried identical to decisive on a branch leg X does not
touch. Generalization level: handoff level 2–3 at most
(choosing among / applying designer-supplied rules); no
novel-representation, calibrated-uncertainty, or
real-world-safety claim.

## Next limitation selected

**P1 stationary selectivity of the FULL abstention trigger
class** — the PRIMARY family (criteria 24/22/19/6) still
FAILs additional, and after leg X its entire remaining
deficit is one FULL control firing (603017 control k=2,
supporting 0, stale 3, purity 0.8529, abstained 0/0 vs
recent8 10/6; its 10 successes are exactly additional's
−10 gap, (b) failing by 4 net of leg X's +11 gain). Every
leg in this line (S, L, A, V, X) is scoped to partial
triggers; the full gate is leg P alone in every candidate
so far, and development's taken control abstentions are
likewise one full (602003 k=2) and one leg-X-kept partial.
Whether an evidence-derived condition on the full trigger
class itself can hold criterion 6's frozen form on BOTH
cohorts while holding B1 engagement (criteria 21/9 — the
full class carries B1's takings: 2 of development's 3 taken
B1 states this cycle are full), the B2 profile (criterion
1), the return-A gains (criteria 23/17/4), checkpoint-32
release (criteria 18/5), and criteria 11/2/3 as co-graded
guards, on NEW cohorts under a NEW protocol. Recorded but
not selected: criterion 1 FAILs BOTH cohorts on its harm
ceiling (dev 65 vs guard 56 and ceiling 51.0; add 45 vs
ceiling 42.0), carried identical to decisive on the
minority branch leg X does not touch — the preceding
cycle's thin-margin tail, carried as a guard; criteria
21/9 FAIL additional through leg X's own priced B1 tail
(above) — a B1 retry would need a condition separating
B1-onset partial takings from stationary ones, which the
pooled evidence review's twin pair (identical records,
opposite arms) prices against; criteria 18/5 FAIL
additional on two carried k=32 non-recent8 firings
identical to decisive, no leg-X population at k=32.
