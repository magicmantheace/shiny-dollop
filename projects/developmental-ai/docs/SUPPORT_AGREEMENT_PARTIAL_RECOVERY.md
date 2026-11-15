# Support-agreement partial recovery — leg A, a conjunctive support-agreement leg on partial abstention triggers only

**15 November 2026 protocol frozen; 15 November 2026
implementation; 15 November 2026 evaluation; graded 15 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `support_agreement_partial_recovery`
  — whether ONE changed element, leg A, a conjunctive
  support-agreement leg on PARTIAL abstention triggers only
  (the graded long-window candidate's support condition
  (leg S OR leg L) becomes the conjunction leg S AND leg L;
  partial gate leg P AND (leg R OR leg C) AND leg S AND leg L;
  leg S = `supporting_opposed_count >= 1` over the supporting
  window, leg L = `stale_opposed_count >= 1` over
  `events[-26:-8]`, both thresholds 1 carried unchanged, the
  two windows disjoint; full gate leg P alone, exactly the
  graded long-window candidate's full gate), can hold
  criterion 6's frozen stationary form on BOTH cohorts — the
  long-window grading's selected limitation (criteria 19/6
  FAILed on BOTH cohorts and carried that cycle's Regression:
  development on sub-condition (b) alone, its entire deficit
  leg L's one graded control firing, an L-only partial;
  additional on (a) AND (b), entirely three carried partial
  firings) — while holding B1 engagement (criteria 21/9, a
  LIVE priced guard: leg A is NOT engagement-preserving in
  expectation, pooled inspected B1 price +180 harm),
  checkpoint-32 release (criteria 18/5, including leg A's
  late-partial exposure at k=32), B2 protection (criterion 1,
  pooled inspected B2 price +112 harm), and return-A profiles
  (criteria 17/4/2) as co-graded guards. Leg P, leg R, leg C,
  leg S, leg L, leg T, leg W, leg N, and leg D were explicitly
  NOT re-tuned. Build Order Priority 1 (Independent
  Learning); handoff §8 excessive abstention / inconsistent
  adaptation to changing rules. This protocol's PRIMARY
  criterion is criterion 22, criterion 6's frozen stationary
  form promoted to PRIMARY. The protocol froze ONE grading
  cap: a Demonstrated verdict requires at least one graded
  control state in at least one cohort where the decisive
  baseline took a PARTIAL abstention through exactly one
  support leg (S-only or L-only) while the candidate was
  disarmed by leg A (`abstention_disarmed_by_support_agreement`
  true) and fell through to recent8; any Demonstrated verdict
  would in any case be a PARTIAL-class verdict through the
  leg-A cap alone (the leg-L B1 hypothesis remains untested;
  no leg-L or full-class claim).
- **Candidate:** `SupportAgreementPartialRecoveryMemory`
  (`developmental_ai/support_agreement_partial_recovery.py`)
  — IDENTICAL to the graded
  `LongWindowSupportPartialRecoveryMemory` in every element
  except leg A (see the campaign state and the frozen
  protocol for the full carried inventory). New
  decision-record fields: `support_agreement_armed` /
  `abstention_disarmed_by_support_agreement` (the latter true
  exactly when a partial trigger taken by the decisive
  baseline through exactly one support leg — S-only or
  L-only — is disarmed by leg A with every other gate leg
  passing); `abstention_disarmed_by_support` in this
  candidate is true exactly when the conjunction fails a
  partial trigger (supporting 0 OR stale 0) with every other
  gate leg passing; `abstention_taken_through_long_window`
  keeps its graded formula and is therefore false at every
  taken state of this candidate.
- **Repository branch and exact commits:** branch
  `developmental-ai/support-agreement-partial-recovery`,
  forked from `966c120`. Protocol frozen at `be1cbc3`;
  implementation at `06a7a79`; evaluation at `b3a213b` (the
  commit graded here); this grading commit sits on top of
  `b3a213b`.
- **Frozen protocol:**
  `benchmarks/support_agreement_partial_recovery_protocol.json`.
- **Seeds:** development 562003 / 562021 / 562039; additional
  563001 / 563017 / 563041 — both cohorts NEW and uninspected
  at freeze, both now INSPECTED. Never re-tune any parameter
  against them (or any earlier inspected cohort).
- **Decisive baseline:** the graded long-window candidate
  (identical but for the conjunction). **Simplest credible
  baseline:** recent8.

## Verification

- Unit tests: PASS — full suite re-run in the grading stage
  (2384 tests; see the grading-stage run recorded in the
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
  stage; no criterion-7 field missing; `support_threshold` 1
  and `long_window_threshold` 1 everywhere;
  `supporting_opposed_count` recomputable as
  `acting_opposed_count - opposed_count` everywhere;
  `stale_opposed_count` recomputed exactly from the
  `stale_joint_events` per-event opposed flags (stale lists
  of 18); `support_agreement_armed` recomputed exactly
  (supporting >= 1 AND stale >= 1);
  `abstention_disarmed_by_support_agreement` recomputed
  exactly under its exactly-one-leg form (the 9 leg-A
  disarmings below); `abstention_disarmed_by_support`
  recomputed exactly under the conjunction-failure form
  (partial trigger, other legs pass, supporting 0 OR
  stale 0 — 10 states: the 9 leg-A disarmings plus ONE
  both-legs-fail state, additional 563001 B2 k=2 supporting
  0 stale 0, a recent8 fall-through shared identically with
  the decisive baseline); the gate recomputed exactly
  everywhere (full: leg P alone; partial: leg P AND
  (leg R OR leg C) AND leg S AND leg L);
  `abstention_taken_through_long_window` false at every
  taken state, as registered; support-agreement-rule ==
  candidate branch and long-window-support-rule == decisive
  branch everywhere; `singleton_release_fired` (2 firings
  dev, 1 add, all carried identical to decisive) and the
  `recovery_fired` leg-N-or-leg-D composition recomputed
  everywhere; companion fields recomputable at every partial
  state (33 dev / 30 add) and at fallback elsewhere; kind
  never widened; acting lists of 8 and newest lists of 4
  with all counts recomputable everywhere and newest records
  == acting tail; `minority_model_archive_count ==
  archive_events_count` and `minority_model_inverted` true
  everywhere; cross-check PASS at every minority-fired state
  (4/4 dev, 5/5 add); acquisition 0, training actions 0,
  additional observations 0.

## Per-criterion grading (precommitted, graded individually, per cohort)

PRIMARY criterion 22 first, then co-graded guards 19, 6, 21,
9, 18, 5, 1, 11, 17, 4, 2, 3, 7. Development / additional.

- **C22 PRIMARY (= criterion 6's frozen stationary form):
  PASS / PASS.** Development: abstentions 16/240, successes
  111 vs recent8 116 (line >= 110), harm 113 <= 124 — all
  three sub-conditions hold on the raw numbers as a CARRIED
  profile: candidate identical to the decisive baseline on
  the control arm (decisive [111, 113, 16]); the one taken
  control abstention, 562021 k=32 partial S&L (supporting 2,
  stale 2, purity 0.756, through leg R), is carried
  identical; leg A disarmed ZERO graded control states on
  development. Additional: abstentions 16/240, successes 110
  vs recent8 111 (line >= 105), harm 114 <= 129 — all three
  sub-conditions hold, and the entire candidate-vs-decisive
  gap is the ONE graded control leg-A disarming (below):
  decisive [102, 106, 32], so without leg A sub-condition
  (b) would FAIL there (102 < 105) at volume AT the budget.
- **C19 / C6 (same computation, carried forms): PASS /
  PASS** — identical numbers to C22 on both cohorts.
- **C21 (= C9 form) / C9 B1 engagement: PASS / PASS.**
  Development TAKEN 4/6 (2 full + 2 partial S&L, paths C /
  R; harm 32 vs guard 65 and recent8 81, successes 0) —
  identical takings to decisive. Additional TAKEN 3/6 AT the
  floor (1 full + 2 partial S&L, paths R / R+C; harm 47 vs
  guard 88 and recent8 88, successes 1) — decisive took 5/6;
  its two extra takings are exactly the graded B1 leg-A
  disarmings (563001 k=2 L-only, recent8 1/15 vs decisive
  abstained 0/0; 563017 k=4 L-only, 0/16 vs 0/0): leg A's
  pre-registered B1 price realized, pooled onset harm +31
  dev / +63 add against decisive at +1 success each cohort,
  and the criterion still holds on both cohorts.
- **C18 (= C5 form) / C5 checkpoint-32 release: PASS /
  FAIL.** Development in full: abstentions 0/144, successes
  65 = recent8 65, non-recent8 0/9, abstained 0/9 — identical
  to decisive and recent8. Additional FAILs on
  sub-condition (c) alone: non-recent8 2/9 against the
  at-most-1 allowance — the two carried retained firings at
  return-A k=32 (563017 full, 8/8; 563041 partial, 7/9),
  both identical to the decisive baseline; (a) 0/144, (b)
  successes 72 vs recent8 73 (line >= 65), (d) abstained 0/9
  all PASS. Leg A's late-partial exposure at k=32 did NOT
  occur on the switch stages (zero abstained k=32 states on
  either cohort); the one k=32 leg-A disarming is on the
  control arm (the cap state, below), where the candidate
  fell through to recent8 exactly as recent8 scored (8/8).
- **C1 B2 protection: FAIL / FAIL.** Development on
  sub-condition (a) alone: minority 2/6; selectivity (b)
  PASS (B1 0/6, return-A 0/6); harm 40 vs guard 63 AND
  ceiling 48.6 PASS both halves of (c); successes 24 vs
  guard+16 = 17 PASS (d). Additional on (a), (c)-ceiling,
  and (d): minority 0/6; harm 96 = guard 96 PASS but ceiling
  57.6 FAIL; successes 0 vs guard+16 = 16 FAIL. Leg A's B2
  disarmings are charged in full: development 562003 k=2
  L-only (0/16 vs decisive 0/0) and 562039 k=2 S-only (1/15
  vs 0/0); additional 563001 k=4 S-only and 563041 k=4
  L-only (0/16 each vs 0/0) — B2 pooled [24, 40] dev vs
  decisive [23, 9] and [0, 96] add vs decisive [0, 64]; the
  minority count itself is untouched by leg A on both
  cohorts (candidate minority firings identical to
  decisive's), so development's (a) failure is a carried
  count draw and additional's is a zero-firing draw, with
  leg A's share exactly the harm-ceiling gap on additional.
- **C11 conjunction (C6 AND C9): PASS / PASS.**
- **C17 (= C4 form) / C4 return-A onset harm: FAIL /
  FAIL.** Development on ceiling (b) alone: harm 78 vs
  guard 89 PASS, ceiling 0.60 x recent8 89 = 53.4 FAIL.
  Additional on BOTH halves: harm 66 vs guard 43 FAIL and
  ceiling 0.60 x 91 = 54.6 FAIL. Carried identical to the
  decisive baseline on both cohorts — return-A [18, 78] dev
  and [30, 66] add under candidate and decisive alike; leg A
  disarmed ZERO return-A states at any checkpoint.
  frozen_A / cumulative beat the candidate on BOTH axes at
  return-A on development again (60/36 and 70/26 vs 18/78);
  on additional frozen_A 56 successes sit above the
  candidate's 30 with harm below its 66 as well.
- **C2 return-A recovery successes: FAIL / PASS.**
  Development on BOTH halves: successes 18 vs frozen_A
  floor 24.0 FAIL and guard+16 = 23 FAIL. Additional in
  full: 30 vs floor 22.4 and guard+16 = 21. Carried
  identical to decisive on both.
- **C3 pooled onset harm: PASS / PASS.** Development harm
  150 vs guard 217, cells 6/6 at or below recent8;
  additional harm 209 vs guard 227, cells 6/6. Pooled onset
  ABOVE decisive on both (150 vs 119 dev; 209 vs 146 add),
  entirely through leg A's nine disarmings, stated in full;
  below recent8 on both (251 / 275).
- **C7 full accounting: PASS / PASS** — see Verification
  above: replay 72/72 per cohort, every recomputation clean
  including the two new leg-A fields, acquisition 0.

## Grading cap

**MET on the additional cohort; NOT MET on development.**
Exactly ONE graded control leg-A disarming occurs across
both cohorts: additional 563041 control k=32 — partial
trigger, L-only (supporting 0, stale 2), purity 0.875,
candidate fell through to recent8 8/8 vs decisive abstained
0/0. It is the sole difference between candidate and
decisive on the additional control arm, and it alone moves
additional's PRIMARY from decisive's failing profile
(successes 102 vs the >= 105 line, volume 32/240 at the
budget) to the candidate's PASS (110, 16/240). Development
drew zero graded control leg-A disarmings; its PRIMARY pass
is a carried profile. Any positive reading of this cycle is
therefore a PARTIAL-class verdict through the leg-A cap
alone, on ONE graded state, in the additional cohort only —
the leg-L B1 hypothesis remains untested and no leg-L or
full-class claim is made.

## Leg A's realized effect, in full

Leg A disarmed exactly NINE states across both cohorts,
every one a PARTIAL trigger the decisive baseline took
through exactly one support leg, ZERO UNEXPECTED (branch
diffs vs decisive 4 dev / 5 add, ALL classified
leg_A_disarming; score diffs 4/72 dev, 5/72 add):

- Development (4): 562003 B2 k=2 (L-only, stale 4, purity
  0.806, candidate recent8 0/16 vs decisive abstained 0/0);
  562021 B1 k=8 (L-only, stale 2, purity 0.923, 9/7 vs 0/0,
  UNGRADED checkpoint); 562039 B1 k=8 (L-only, stale 4,
  purity 0.849, 11/5 vs 0/0, UNGRADED); 562039 B2 k=2
  (S-only, supporting 1, stale 0, purity 0.800, 1/15 vs 0/0).
- Additional (5): 563001 B1 k=2 (L-only, stale 1, purity
  0.824, 1/15 vs 0/0, GRADED B1 onset); 563001 B2 k=4
  (S-only, supporting 1, stale 0, purity 0.889, 0/16 vs
  0/0); 563017 B1 k=4 (L-only, stale 2, purity 0.833, 0/16
  vs 0/0, GRADED B1 onset); 563041 B2 k=4 (L-only, stale 2,
  purity 0.795, 0/16 vs 0/0); 563041 control k=32 (L-only,
  stale 2, purity 0.875, 8/8 vs 0/0, the ONE GRADED CONTROL
  disarming — the cap state).

Priced in full: pooled onset harm +31 dev (150 vs decisive
119, successes +1) and +63 add (209 vs 146, successes +1),
entirely the onset disarmings; the stationary disarming on
additional was PRODUCTIVE against recent8's own line
(+8 successes at +8 harm, converting a 0/0 abstention into
recent8's exact 8/8). B1 engagement held on both cohorts
despite the price; B2's harm ceiling on additional did not.

## Safety and evidence costs

- Harmful task actions: pooled onset candidate 150 dev /
  209 add (vs decisive 119 / 146, recent8 251 / 275);
  stationary control harm 113 dev / 114 add; checkpoint-32
  pooled successes/harm [65, 79] dev, [72, 72] add.
- Failed-by-abstention: stationary 16 episodes per cohort
  (one taken control abstention per cohort, both S&L /
  full carried); onset abstained episodes 96 dev / 48 add.
- Additional requested observations / acquisition actions:
  0 on both cohorts; learner training actions 0. External
  TRAIN actor costs are published in full in the saved
  detailed results, as in preceding cycles.
- False confidence / unnecessary abstention: leg A's nine
  disarmings are the cycle's entire candidate-vs-decisive
  difference; each is named above with its realized price.

## Scientific conclusion

**Failed, NOT a Regression** — under the protocol's own
definitions. The Failed clause triggers on the additional
cohort several times over: criteria 18/5, 1, 17, and 4 FAIL
there (criterion 7 PASSes both, PRIMARY criterion 22
PASSes both). No Regression clause triggers: pooled onset
harm 150/209 is below recent8 251/275 on both cohorts;
stationary-control successes fall below recent8 by 5 dev /
1 add, not more than 6 on both; checkpoint-32 successes 65
/ 72 are above the recent8 − 4 lines of 61 / 69; the full
unit suite and the historical transfer benchmark pass in
the grading stage.

What leg A genuinely demonstrated, within those limits:
the PRIMARY stationary form holds on BOTH cohorts for the
first time in this support-gated line, and on additional it
holds BECAUSE of leg A — the cap is met there on exactly
one graded control state, an L-only partial firing whose
0/0 abstention was the decisive baseline's entire
sub-condition-(b) deficit, disarmed to recent8's exact 8/8.
That is a PARTIAL-class demonstration through the leg-A cap
alone, on one state, in one cohort — not a general
stationary-selectivity mechanism. Development's PRIMARY
pass is a carried profile with zero graded control leg-A
disarmings. B1 engagement (21/9) also holds on both cohorts
with leg A's pre-registered price paid in full (+31 / +63
pooled onset harm against decisive). Against that: B2
protection fails on both cohorts (count on development,
count + ceiling + successes on additional, leg A's B2
disarmings supplying additional's ceiling gap), return-A
harm fails on both cohorts carried identical (leg A has no
return-A population), checkpoint-32 release fails
additional on two carried retained firings, and return-A
successes fail development carried identical with
frozen_A / cumulative both-axes dominance there again.
Generalization level: handoff level 2–3 at most (choosing
among / applying designer-supplied rules); no
novel-representation, calibrated-uncertainty, or
real-world-safety claim.

## Next limitation selected

**P1 return-A onset harm** — criteria 17/4 FAIL on BOTH
cohorts (development on the ceiling sub-condition (b)
alone, harm 78 vs ceiling 53.4 with the guard comparison
passing; additional on BOTH halves, 66 vs guard 43 and
ceiling 54.6), and criterion 2 FAILs development on both
halves alongside them (successes 18 vs floor 24.0 and
guard+16 = 23, with frozen_A / cumulative both-axes
dominance at return-A on development again). The mechanism
is entirely carried: the candidate is identical to the
decisive baseline at every return-A state on both cohorts
and leg A disarmed zero return-A states at any checkpoint,
so no support-leg condition can move this arm — whether an
evidence-derived condition on the return-A onset population
itself (the regular branch's engaged firings and the
non-engaged recent8 fall-throughs that dominate its harm)
can hold criterion 4's frozen form on BOTH cohorts while
holding stationary selectivity (criteria 22/19/6, now
PASSing both with the cap met on additional), B1 engagement
(criteria 21/9, PASSing both), checkpoint-32 release
(criteria 18/5), and B2 protection (criterion 1) as
co-graded guards, on NEW cohorts under a NEW protocol.
Recorded but not selected: criterion 1 FAILs on both
cohorts as well — development's failure is the minority
count alone on a branch leg A does not touch (harm passing
both comparisons there), and additional's count failure is
a zero-firing draw with leg A's share exactly its ceiling
gap; carried as a co-graded guard. Additional's criteria
18/5 failure is two carried retained firings at return-A
k=32, single-cohort — its return-A k=32 states are part of
the selected limitation's population, not a separate
release retry. The stationary question this cycle was
built to ask is answered on these draws (PRIMARY PASS
both, cap met on additional); a further stationary retry
would need a cohort design that draws more graded control
leg-A disarmings than the one state drawn here, which no
graded population this cycle sizes.
