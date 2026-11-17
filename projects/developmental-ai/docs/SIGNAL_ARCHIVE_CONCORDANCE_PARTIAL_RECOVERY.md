# Signal archive concordance partial recovery — leg V, a signal archive-concordance veto on partial abstention triggers only

**16 November 2026 protocol frozen; 16 November 2026
implementation; 17 November 2026 evaluation; graded 17 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `signal_archive_concordance_partial_recovery`
  — whether ONE changed element, leg V, a signal
  archive-concordance veto on PARTIAL abstention triggers only
  (the partial gate becomes leg P AND (leg R OR leg C) AND
  leg S AND leg L AND (`concordant_count == 0`), where
  `concordant_count` is the carried decision-record field
  summing `archive_concordant` over the signal pair, at its
  absence value 0, NO new numeric value; the full gate stays
  leg P alone; new decision-record field
  `abstention_disarmed_by_signal_concordance`, true exactly
  when a partial trigger taken by the decisive baseline
  through leg S AND leg L with `concordant_count >= 1`, every
  other gate leg passing and neither recovery branch fired,
  is disarmed by leg V alone) can hold criterion 6's frozen
  stationary form on BOTH cohorts — the long-disagreement
  grading's selected limitation (criteria 22/19/6 FAILed on
  BOTH cohorts on sub-condition (b) alone and carried that
  cycle's Regression, the entire deficit on each cohort
  exactly two carried partial S&L firings) — while holding
  the return-A gains (criteria 23/17/4), B1 engagement
  (criteria 21/9), checkpoint-32 release (criteria 18/5), and
  B2 protection (criterion 1) as co-graded guards. Leg P,
  leg R, leg C, leg S, leg L, leg A, leg T, leg W, leg N,
  leg D, and leg Q were explicitly NOT re-tuned. Build Order
  Priority 1 (Independent Learning); handoff §8 inconsistent
  adaptation / slow or incorrect recovery of old knowledge.
  This protocol's PRIMARY criterion is criterion 24,
  criterion 6's frozen stationary form promoted to PRIMARY.
  The protocol froze ONE grading cap: a Demonstrated verdict
  requires at least one graded control state in at least one
  cohort where the decisive baseline took a PARTIAL S&L
  abstention with `concordant_count >= 1` while the candidate
  was disarmed by leg V and fell through to recent8; any
  Demonstrated verdict would in any case be a PARTIAL-class
  verdict through the leg-V cap alone (the full gate is leg P
  alone in both candidates; no full-class claim).
- **Candidate:** `SignalArchiveConcordancePartialRecoveryMemory`
  (`developmental_ai/signal_archive_concordance_partial_recovery.py`)
  — IDENTICAL to the graded
  `LongDisagreementReleaseRecoveryMemory` in every element
  except leg V (see the campaign state and the frozen
  protocol for the full carried inventory).
- **Repository branch and exact commits:** branch
  `developmental-ai/signal-archive-concordance-partial-recovery`,
  forked from `9fde5b2`. Protocol frozen at `bf13ba7`;
  implementation at `c624642`; evaluation at `5dd6553` (the
  commit graded here); this grading commit sits on top of
  `5dd6553`.
- **Frozen protocol:**
  `benchmarks/signal_archive_concordance_partial_recovery_protocol.json`.
- **Seeds:** development 582003 / 582021 / 582039; additional
  583001 / 583017 / 583041 — both cohorts NEW and uninspected
  at freeze, both now INSPECTED. Never re-tune any parameter
  against them (or any earlier inspected cohort).
- **Decisive baseline:** the graded long-disagreement
  candidate (identical but for leg V). **Simplest credible
  baseline:** recent8.

## Verification

- Unit tests: PASS — full suite re-run in the grading stage
  (2699 tests OK).
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
  `long_window_threshold` 1 everywhere; `concordant_count`
  recomputed exactly from the archive records (sum of
  `archive_concordant` over the signal pair's archive
  records); `abstention_disarmed_by_signal_concordance`
  recomputed exactly (gate blocked AND partial AND other
  legs pass AND support-agreement armed AND
  `concordant_count >= 1`); `long_disagreement` and
  `long_disagreement_release_fired` recomputed exactly as
  carried; the gate recomputed exactly everywhere (full:
  leg P alone; partial: leg P AND (leg R OR leg C) AND
  leg S AND leg L AND `concordant_count == 0`);
  `abstention_taken_through_long_window` false at every
  taken state, as carried; signal-concordance-rule ==
  candidate branch and long-disagreement-release-rule ==
  decisive branch everywhere; `singleton_release_fired`
  (2 firings dev, 0 add, all carried identical to decisive)
  and the `recovery_fired` composition recomputed
  everywhere; companion fields recomputable at every partial
  state and at fallback elsewhere; kind never widened;
  acting lists of 8 and newest lists of 4 with all counts
  recomputable everywhere and newest records == acting tail;
  `minority_model_archive_count == archive_events_count` and
  `minority_model_inverted` true everywhere; cross-check PASS
  at every minority-fired state 6/6 dev and 5/5 add;
  acquisition 0, training actions 0, additional requested
  observations 0.

## Learning evaluation

Leg V disarmed exactly TWO states across both cohorts, ZERO
on development and two on additional, every one a PARTIAL
S&L trigger the decisive baseline took, ZERO UNEXPECTED —
add 583017 B1 k=8 (UNGRADED checkpoint, supporting 2, stale
2, concordant 1, purity 0.821, candidate recent8 8/8 vs
decisive abstained 0/0) and add 583017 control k=8
(supporting 2, stale 2, concordant 1, purity 0.829,
candidate recent8 7/9 vs decisive abstained 0/0). Branch
diffs vs decisive: dev 0, add 2, ALL classified
leg_V_disarming; score diffs vs decisive 0/72 dev and 2/72
add. The one graded control disarming (583017 k=8) is the
sole candidate-vs-decisive difference on the additional
control arm: candidate [131, 109, 0] vs decisive
[124, 100, 16] there, and identical to recent8 [131, 109, 0].

Scores [successes, harm] (abstained episodes third where
graded): pooled onset candidate [87, 89] dev and [83, 93]
add, IDENTICAL to decisive on both, vs recent8 [44, 244]
dev / [55, 233] add. B1 candidate [1, 15] dev / [0, 0] add, identical
to decisive on both. B2 candidate [14, 50] dev / [27, 53]
add, identical to decisive on both. Return-A candidate
[72, 24] dev / [56, 40] add, identical to decisive on both.
Checkpoint-32 candidate [61, 83, 0] dev / [90, 54, 0] add,
identical to decisive AND recent8 on both. Control
candidate [117, 107, 16] dev IDENTICAL to decisive, vs
recent8 [123, 117, 0] (the one taken control abstention,
582003 k=2 partial S&L concordant 0, purity 0.825,
supporting 1, stale 3, abstained 0/0 vs recent8 6/10, kept
under leg V and carried identical); add candidate
[131, 109, 0] vs decisive [124, 100, 16] and recent8
[131, 109, 0]. Taken S&L partial abstentions under leg V
(concordant 0, kept): dev 3 (582003 B1 k=2, 582003 control
k=2, 582021 B2 k=2), add 2 (583017 B1 k=2 and k=4).

Per-criterion grading (development / additional), PRIMARY
criterion 24 first, then co-graded guards 23/17/4, 22/19/6,
21/9, 18/5, 1, 11, 2, 3, 7 — script-computed from the saved
detailed results at `5dd6553`:

- **C24 PRIMARY (= criterion 6's frozen stationary form):
  PASS / PASS.** Dev: abstentions 16/240 PASS (a);
  successes 117 vs recent8 123, line >= 117, PASS (b) AT
  the line — the entire remaining deficit is the ONE kept
  partial S&L firing, 582003 control k=2 (concordant 0,
  supporting 1, stale 3, purity 0.825, abstained 0/0 vs
  recent8 6/10); harm 107 vs recent8 117 PASS (c). Add:
  abstentions 0/240 PASS (a); successes 131 = recent8 131
  PASS (b); harm 109 = recent8 109 PASS (c) — the entire
  candidate-vs-decisive gap the one graded control leg-V
  disarming at 583017 k=8 (+7 successes, +9 harm, −16
  abstained episodes against decisive), without which
  decisive [124, 100, 16] would FAIL sub-condition (b)
  (124 < 125).
- **C23 / C17 / C4 (return-A harm, criterion 4's frozen
  form): PASS / PASS**, in full on both — dev harm 24 vs
  guard 84 and ceiling 0.60 × recent8 84 = 50.4; add harm
  40 vs guard 80 and ceiling 0.60 × recent8 80 = 48.0.
  Identical to decisive on both (leg V disarming zero
  return-A states, as frozen: leg Q's population requires
  abstention authority disarmed). This PASSes where the
  preceding cycle FAILed development on the ceiling alone —
  a draw difference on new cohorts, carried identical to
  decisive, not a leg-V effect.
- **C22 / C19 / C6 (stationary selectivity, the same
  computation in its guard positions): PASS / PASS**,
  exactly as C24.
- **C21 / C9 (B1 engagement): PASS / PASS.** Dev TAKEN 5/6
  (4 full + 1 partial, path C), harm 15 vs guard 33 and <
  recent8 74; add TAKEN 6/6 (4 full + 2 partial, paths
  R+C / R+C), harm 0 vs guard 32 and < recent8 81.
  Identical takings to decisive at onset on both (leg V's
  one B1 disarming is at ungraded k=8).
- **C18 / C5 (checkpoint-32 release): PASS / PASS**, in
  full on both — abstentions 0/144, successes 61 = recent8
  61 dev and 90 = 90 add, non-recent8 0/9, abstained 0/9;
  identical to decisive AND recent8 on both.
- **C1 (B2 protection): FAIL / FAIL.** Dev on (a) and (d)
  — minority 1/6 FAIL (a) (the one minority firing 582021
  k=4, 10/6); selectivity (b) PASS (B1 0/6, return-A 0/6);
  harm 50 vs guard 71 PASS and ceiling 0.60 × recent8 86
  = 51.6 PASS (c); successes 14 vs guard+16 = 25 FAIL (d).
  Add on (a) and (c) — minority 2/6 FAIL (a) (583001 k=4
  and 583041 k=4); selectivity PASS; harm 53 vs guard 44
  FAIL and ceiling 0.60 × recent8 72 = 43.2 FAIL (c);
  successes 27 vs guard+16 = 20 PASS (d). Carried identical
  to decisive on both cohorts at every B2 onset state —
  leg V disarmed zero B2 states and the minority branch is
  untouched by leg V.
- **C11 (conjunction of C6 and C9): PASS / PASS.**
- **C2 (return-A successes): PASS / PASS.** Dev successes
  72 vs frozen_A floor 0.40 × 72 = 28.8 and guard+16 = 28;
  add 56 vs floor 0.40 × 60 = 24.0 and guard+16 = 32.
  Note in full: frozen_A's return-A successes (72 dev /
  60 add) sit at or above the candidate's on both cohorts.
- **C3 (pooled onset): PASS / PASS** — harm 89 vs guard
  188 dev and 93 vs guard 156 add, cells 6/6 on both.
- **C7 (accounting / reproducibility): PASS / PASS** —
  replay 72/72 per cohort, all recomputations clean
  (above), acquisition 0.

**The grading cap is MET on the additional cohort and NOT
MET on development** — exactly ONE graded control leg-V
disarming occurs across both cohorts: additional 583017
control k=8, partial S&L (supporting 2, stale 2),
concordant 1, purity 0.829, candidate recent8 7/9 vs
decisive abstained 0/0, the sole candidate-vs-decisive
difference on the additional control arm and the state
that alone moves additional's PRIMARY from decisive's
(b)-failure to PASS. Any positive reading is a
PARTIAL-class verdict through the leg-V cap alone, on one
graded state, in one cohort — no full-class claim is made.
Development's PRIMARY PASS is a carried-profile pass at
the exact (b) line, with leg V disarming zero graded
control states there.

## Safety and evidence costs

- Harmful task actions: pooled onset 89 dev / 93 add (vs
  decisive 89 / 93 identical, and recent8 244 / 233);
  return-A 24 / 40; B1 15 / 0; B2 50 / 53; control harm
  107 / 109 (below / at recent8 117 / 109).
- Failed-by-abstention: control 16 abstained episodes dev
  (16/240, the one kept concordant-0 partial S&L firing at
  582003 k=2) and 0 add; onset abstentions dev B1 5 states
  and B2 2 states carried identical, add B1 6 states and
  B2 1 state carried identical; k32 abstentions 0.
- Additional requested observations / learner information
  acquisition / training actions: 0 / 0 / 0.
- False confidence and unnecessary abstention: leg V's
  graded control disarming converted a decisive abstention
  0/0 into a recent8 action at 7/9 on additional — a
  productive disarming on its designed population; its
  ungraded B1 k=8 disarming converted 0/0 into 8/8. The
  kept concordant-0 stationary firing on development is
  the cycle's remaining unnecessary-abstention cost,
  charged in full under C24/22/19/6 (it alone puts
  development AT, not above, the (b) line).
- Report integrity: all figures script-computed this pass
  from the saved detailed results at `5dd6553`; the
  evaluation analysis script was re-run in the grading
  stage with identical recomputations. No CI claimed for
  the evaluation or grading commits (Linux/Windows
  UNVERIFIED).

## Scientific conclusion

**FAILED, not a Regression**, under the protocol's own
definitions. The Failed clause triggers on the additional
cohort: criterion 1 FAILs there (criterion 7 PASSes both,
and every other criterion PASSes both). The Regression
clauses do not trigger — pooled onset harm 89/93 below
recent8 244/233, control successes −6 dev (AT, not past,
the more-than-6 line) and 0 add, k=32 successes 61/90 at
exact recent8 parity, suite + transfer pass. PRIMARY
criterion 24 PASSes on BOTH cohorts and the grading cap
is MET on additional, so leg V's mechanism is
demonstrated on its designed population on one cohort:
disarming the one graded concordant >= 1 partial S&L
stationary firing on additional moved that cohort's
stationary profile from decisive's (b)-failure to a full
PASS, at +7 successes / +9 harm against decisive there.
Development PASSes the PRIMARY as a carried profile at
the exact (b) line, its one kept concordant-0 firing
(582003 k=2, recent8 6/10) costing exactly the 6-success
deficit. Fifteen of sixteen criteria PASS on both
cohorts — the best per-criterion profile in this line —
and the sole failure, criterion 1, is carried identical
to the decisive baseline on a branch (minority) leg V
does not touch, on both cohorts. Generalization level:
handoff level 2–3 at most (choosing among / applying
designer-supplied rules); no novel-representation,
calibrated-uncertainty, or real-world-safety claim. Any
positive reading of leg V is a PARTIAL-class verdict
through the leg-V cap alone, stated in those words.

## Next limitation selected

**P1 second-switch (B2) protection of the carried minority
branch** — criterion 1 is now the SOLE failing criterion,
FAILing on BOTH cohorts (development on minority count
1/6 and successes; additional on minority count 2/6 and
harm vs guard and ceiling), while the other fifteen
criteria PASS on both, on an arm where the candidate is
identical to the decisive baseline at every B2 onset state
and leg V disarmed zero B2 states — no abstention-gate
condition can move it; the condition must be on the B2 /
minority population itself. Whether an evidence-derived
condition on that population can hold criterion 1's frozen
form on BOTH cohorts while holding stationary selectivity
(criteria 24/22/19/6, now PASSing both with the cap met on
additional), the return-A gains (criteria 23/17/4, PASSing
both), B1 engagement (criteria 21/9, PASSing both),
checkpoint-32 release (criteria 18/5, PASSing both), and
criteria 11/2/3 as co-graded guards, on NEW cohorts under
a NEW protocol. Recorded but not selected: development's
stationary (b) margin is exactly zero — its one kept
concordant-0 partial S&L firing costs the full 6-success
deficit, so the stationary question is answered only at
the line on that draw and a further stationary retry
would need a condition distinguishing kept concordant-0
firings, which the pooled evidence review found no
permitted quantity separating; criterion 1's failures
have recurred across cycles on the minority branch,
carried as a guard in each — it is now selected directly.
