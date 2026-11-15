# Long-window support partial recovery — leg L, a long-window supporting-opposition leg on partial abstention triggers only

**14 November 2026 protocol frozen; 14 November 2026
implementation; 14 November 2026 evaluation; graded 14 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `long_window_support_partial_recovery`
  — whether ONE changed element, leg L, a long-window
  supporting-opposition leg on PARTIAL abstention triggers only
  (partial gate leg P AND (leg R OR leg C) AND (leg S OR leg L),
  leg L armed iff `stale_opposed_count >= 1` over the stale
  window `events[-26:-8]`, `long_window_threshold` 1 carried
  unchanged from leg S's `support_threshold`; full gate leg P
  alone, exactly the graded partial-scoped candidate's full
  gate), can hold criterion 9's frozen B1 form on BOTH cohorts —
  the partial-scoped grading's selected limitation (criterion
  20/9 FAILed on BOTH cohorts on sub-condition (a) with harm
  passing both comparisons on both, and the partial class
  contributed ZERO taken B1 states on either cohort despite
  three partial B1 triggers drawn per cohort) — while holding
  stationary selectivity (criteria 19/6, a LIVE guard under leg
  L, not a preserved parity), checkpoint-32 release (criteria
  18/5, including leg L's late-partial exposure at k=32), B2
  protection (criterion 1), and return-A profiles (criteria
  17/4/2) as co-graded guards. Leg P, leg R, leg C, leg S, leg
  T, leg W, leg N, and leg D were explicitly NOT re-tuned.
  Build Order Priority 1 (Independent Learning); handoff §8
  excessive abstention / inconsistent adaptation to changing
  rules. This protocol's PRIMARY criterion is criterion 21,
  criterion 9's frozen B1 form promoted to PRIMARY. The
  protocol froze ONE grading cap: a Demonstrated verdict
  requires at least one graded B1 state in at least one cohort
  where the decisive baseline was disarmed by leg S on a
  PARTIAL trigger (`abstention_disarmed_by_support` true in the
  decisive baseline's records) with `stale_opposed_count >= 1`
  while the candidate took the abstention through leg L
  (`abstention_taken_through_long_window` true); any
  Demonstrated verdict would in any case be a PARTIAL-class
  verdict through the leg-L cap alone (the scoping hypothesis
  remains untested; no full-class claim).
- **Candidate:** `LongWindowSupportPartialRecoveryMemory`
  (`developmental_ai/long_window_support_partial_recovery.py`)
  — IDENTICAL to the graded
  `PartialScopedSupportAbstentionRecoveryMemory` in every
  element except leg L (see the campaign state and the frozen
  protocol for the full carried inventory). New decision-record
  fields: `stale_opposed_count` / `long_window_threshold` /
  `long_window_armed` /
  `abstention_taken_through_long_window`;
  `abstention_disarmed_by_support` in this candidate is true
  exactly when BOTH support legs fail a partial trigger
  (supporting 0 AND stale 0) with every other gate leg passing.
- **Repository branch and exact commits:** branch
  `developmental-ai/long-window-support-partial-recovery`,
  forked from `a476147`. Protocol frozen at `96c7c6e`;
  implementation at `58b1541`; evaluation at `63ec15b` (the
  commit graded here); this grading commit sits on top of
  `63ec15b`.
- **Frozen protocol:**
  `benchmarks/long_window_support_partial_recovery_protocol.json`.
- **Seeds:** development 552003 / 552021 / 552039; additional
  553001 / 553017 / 553041 — both cohorts NEW and uninspected
  at freeze, both now INSPECTED. Never re-tune any parameter
  against them (or any earlier inspected cohort).
- **Decisive baseline:** the graded partial-scoped candidate
  (identical but for leg L). **Simplest credible baseline:**
  recent8.

## Verification

- Unit tests: PASS — full suite re-run in the grading stage
  (2241 tests; see the grading-stage run recorded in the
  campaign state).
- Historical regressions: PASS — historical transfer benchmark
  re-run in the grading stage, exit 0.
- Frozen cohorts: graded below, per criterion, per cohort.
- Linux validation: UNVERIFIED (no CI claimed for the grading
  commit).
- Windows validation: UNVERIFIED (no CI claimed for the
  grading commit).
- Replay identity: script-verified true at every checkpoint in
  both cohorts (72/72 entries per cohort) in the grading stage;
  no criterion-7 field missing; `support_threshold` 1 and
  `long_window_threshold` 1 everywhere;
  `stale_opposed_count` recomputed exactly from the
  `stale_joint_events` opposed flags everywhere;
  `long_window_armed` and
  `abstention_taken_through_long_window` recomputed exactly
  everywhere; `abstention_disarmed_by_support` recomputed
  exactly under its new formula (true exactly when BOTH support
  legs fail a partial trigger — exactly ONE such state across
  both cohorts, development 552039 B2 k=2 at stale 0); the gate
  recomputed exactly everywhere (full: leg P alone; partial:
  leg P AND (leg R OR leg C) AND (leg S OR leg L));
  long-window-rule == candidate branch and
  partial-scoped-rule == decisive branch everywhere;
  `singleton_release_fired` and the `recovery_fired` leg-N-or-
  leg-D composition recomputed everywhere with 0 mismatches;
  companion fields recomputable at every partial state (28 dev
  / 23 add) and at fallback elsewhere; kind never widened;
  stale lists of 18, acting lists of 8 and newest lists of 4
  with all counts recomputable everywhere and newest records ==
  acting tail; thresholds as registered;
  `minority_model_archive_count == archive_events_count` and
  `minority_model_inverted` true everywhere; cross-check PASS
  at every minority-fired state (7/7 dev, 6/6 add);
  acquisition 0, training actions 0, additional observations 0.

## Per-criterion grading (precommitted, graded individually, per cohort)

PRIMARY criterion 21 first, then co-graded guards 9, 19, 6,
18, 5, 1, 11, 17, 4, 2, 3, 7. Development / additional.

- **C21 PRIMARY (= C9 form): PASS / PASS — as a CARRIED
  PROFILE only (grading cap NOT MET, below).** Development
  TAKEN 5/6 (k2 3, k4 2; 2 full + 3 partial, paths R+C / R+C /
  R), non-full credit 3, harm 12 <= guard 46 and < recent8 72,
  B1 successes 4 (recent8 24, guard 18). Additional TAKEN 5/6
  (k2 2, k4 3; 2 full + 3 partial, paths R+C / R+C / R),
  non-full credit 3, harm 16 <= guard 49 and < recent8 71, B1
  successes 0 (recent8 25, guard 15). Every graded B1 taking is
  carried identical to the decisive baseline on both cohorts;
  ZERO leg-L takings at graded B1 states on either cohort. The
  one untaken B1 state per cohort: development 552003 k=4 (no
  trigger); additional 553017 k=2 (partial, supporting 0, stale
  2, blocked by BOTH leg R and leg C — population Y, not by the
  support legs).
- **C9 (same computation as C21): PASS / PASS** — carried
  profile, as above.
- **C19 (= C6 form): FAIL / FAIL.** Development on (b) alone:
  abstentions 16/240 PASS, successes 113 vs recent8 121,
  required >= 115, FAIL by 2 — the entire deficit is leg L's
  ONE graded stationary firing (552021 control k=2, partial
  through leg C, supporting 0, stale 3, purity 0.875, candidate
  abstained 0/0 vs recent8 / decisive 8/8); harm 111 <= 119
  PASS. This is leg L's pre-registered stationary tail,
  realized exactly as priced (criterion-6(b) single-firing
  tail). Additional on (a) AND (b): abstentions 48/240 FAIL,
  successes 100 vs recent8 111, required >= 105, FAIL by 6
  (net -11); harm 92 <= 129 PASS — entirely CARRIED: three
  partial firings identical to the decisive baseline (553001
  k=16 supporting 1, 553017 k=8 supporting 1 stale 0, 553041
  k=16 supporting 2), branch diffs vs decisive 0/15 graded
  control states, leg L fired ZERO graded control states on
  additional.
- **C6 (same computation as C19): FAIL / FAIL.**
- **C18 (= C5 form): PASS / PASS.** Abstentions 0/144,
  successes 71 = recent8 71 dev and 65 = recent8 65 add,
  non-recent8 0/9, abstained 0/9 on both — identical to the
  decisive baseline and to recent8 on both; leg L's
  late-partial exposure at k=32 did not occur (zero abstained
  k=32 states on either cohort; no k=32 routing of any kind
  drawn).
- **C5 (same computation as C18): PASS / PASS.**
- **C1 (B2 protection): FAIL / PASS.** Development on (a),
  (c)-ceiling, and (d): minority 1/6, selectivity 0/6 / 0/6
  PASS, harm 68 vs guard 76 PASS but ceiling 55.2 FAIL,
  successes 12 vs guard+16 = 20 — carried identical to the
  decisive baseline (B2 decisive 12/68, minority 1/6).
  Additional in full: minority 3/6 at the floor, harm 24 vs
  guard 35 / ceiling 44.4, successes 40 vs 29 — the candidate's
  one graded onset leg-L taking sits here (553041 B2 k=2,
  partial through leg C, supporting 0, stale 1, purity 0.921,
  candidate abstained 0/0 vs decisive / recent8 0/16), worth
  exactly -16 harm vs decisive at identical successes; leg L's
  B2 abstention does NOT count toward minority engagement, as
  registered.
- **C11 (conjunction of C6 and C9): FAIL / FAIL** — on its
  stationary side only, both cohorts.
- **C17 (= C4 form): FAIL / FAIL.** Development on ceiling
  (b) alone: harm 74 vs guard 94 PASS, ceiling 56.4 FAIL.
  Additional on BOTH halves: harm 32 vs guard 23 FAIL and
  ceiling 30.6 FAIL. Carried identical to the decisive
  baseline on both cohorts (decisive return-A 22/74 dev,
  64/32 add); leg L changed no return-A state on either
  cohort.
- **C4 (same computation as C17): FAIL / FAIL.**
- **C2 (return-A successes): FAIL / PASS.** Development 22 vs
  frozen_A floor 28.8 FAIL on (a) alone (guard+16 = 18 PASS);
  additional 64 vs floor 28.0 and guard+16 = 41 PASS both.
  Frozen_A / cumulative both-axes return-A dominance holds on
  development again (72 / 41 vs candidate 22/74); on additional
  frozen_A 70 successes sit above the candidate's 64 with
  lower harm.
- **C3 (pooled onset harm): PASS / PASS.** Development 154 vs
  guard 216, cells 6/6; additional 72 vs guard 107, cells 6/6.
  Pooled onset identical to decisive on development
  ([38, 154] vs recent8 [30, 258]) and above decisive's
  successes-identical line on additional only through the B2
  leg-L taking ([104, 72] vs decisive [104, 88], recent8
  [92, 196]).
- **C7 (full accounting): PASS / PASS.** Replay 72/72 per
  cohort and every recomputation clean, as itemized under
  Verification; branch diffs vs decisive 2 dev / 1 add, ALL
  classified `leg_L_taking`, zero UNEXPECTED; score diffs vs
  decisive 2/72 dev and 1/72 add.

**Grading cap: NOT MET.** Zero leg-L takings at graded B1
states on either cohort, so no Demonstrated verdict is
available and the C21/9 PASSes are carried-profile passes,
never leg-L demonstrations. Leg L took exactly THREE
abstentions across both cohorts at any checkpoint: development
552003 B1 k=16 (an UNGRADED checkpoint, partial through leg C,
supporting 0, stale 6, purity 0.737, candidate abstained 0/0 vs
decisive / recent8 8/8 — productive in shape, not graded);
development 552021 control k=2 (graded CONTROL state — the
C19/6 development failure above); additional 553041 B2 k=2
(graded B2 onset state — the -16 harm inside additional's C1
PASS). Leg T disarmed ZERO states on development and one
minority state on additional; it changed no graded branch or
score in the cap's population.

## Learning evaluation

- The candidate differs from the decisive baseline at exactly
  3 of 288 seed-checkpoint entries across both cohorts, every
  one a leg-L taking of exactly the designed shape (partial
  trigger, supporting 0, stale >= 1, every other gate leg
  passing). At graded B1 states the candidate is identical to
  the decisive baseline on both cohorts: the designed graded-B1
  population (a leg-S-disarmed partial trigger drawn at k=2 or
  k=4) did not occur — development's graded partial takings all
  carry supporting >= 2 (taken through leg S, carried), and
  additional's one supporting-0 graded B1 partial (553017 k=2)
  is population Y, blocked by both corroboration legs.
- Checkpoint profile (candidate successes / harm / abstained,
  pooled per stage-checkpoint; full table in the saved detailed
  results): B1 pooled onset [4, 12] dev and [0, 16] add against
  recent8 [24, 72] / [25, 71] and the guard [18, 46] /
  [15, 49]; control pooled [113, 111, 16] dev vs recent8
  [121, 119, 0] and [100, 92, 48] add vs recent8 [111, 129, 0];
  k=32 pooled [71, 73, 0] dev and [65, 79, 0] add, identical to
  decisive and recent8 on both.
- Generalization level: at most handoff level 2–3, as frozen.
  No novel-representation claim.

## Safety and evidence costs

- Harmful TEST actions are counted per criterion above;
  pooled onset harm 154 dev / 72 add vs recent8 258 / 196 and
  the guard 216 / 107.
- Failed-by-abstention: pooled onset abstained episodes 96 dev
  / 112 add (candidate), of which leg L contributes exactly
  one graded onset abstention (additional B2) and one graded
  stationary abstention (development control).
- Acquisition cost: 0 learner training actions, 0 additional
  requested observations, on both cohorts. All TRAIN evidence
  comes from the shared external actor stream, counted in the
  saved detailed results.
- False confidence / unnecessary abstention: leg L's one
  graded stationary firing converted a recent8 8/8 cell into
  0/0 at zero harm — an unnecessary abstention under the
  stationary arm's own accounting, charged in full under
  C19/6.

## Scientific conclusion

**Failed / Regression (stationary clause), under the
protocol's own definitions.**

- **Failed:** the Failed clause triggers on the additional
  cohort several times over — criteria 19, 6, 11, 17, and 4
  FAIL there — and criterion 21 PASSes on both cohorts only as
  a carried profile with the grading cap NOT MET, so no
  Demonstrated or Partially-demonstrated-through-leg-L reading
  is available for the PRIMARY's mechanism: leg L demonstrated
  nothing at graded B1 states on these draws.
- **Regression:** the stationary clause triggers — control
  successes fall below recent8 by more than 6 on BOTH cohorts
  (113 vs 121, -8 development; 100 vs 111, -11 additional).
  Attribution stated in full: development's -8 is entirely leg
  L's one graded control firing; additional's -11 is entirely
  carried firings identical to the decisive baseline, with leg
  L firing zero graded control states there. The other
  Regression clauses do not trigger: pooled onset harm 154 /
  72 below recent8 258 / 196 on both; k=32 successes 71 / 65 at
  exact recent8 parity, above the recent8 - 4 lines of 67 /
  61; suite and transfer pass.
- The leg-L hypothesis is neither confirmed nor refuted at its
  designed graded-B1 population, which did not occur; what
  these cohorts DO establish is leg L's realized price and
  shape: three takings, all of the designed shape, one
  productive-but-ungraded (B1 k=16), one beneficial at B2
  onset (-16 harm), and one stationary firing that single-
  handedly fails development's C19/6(b) and supplies this
  cycle's Regression on the development side.

**Next limitation selected (Priority 1): stationary
selectivity of the support-gated abstention classes under leg
L** — criteria 19/6 FAIL on BOTH cohorts and carry this
cycle's Regression; development's failure is leg L's own
stationary tail (one firing, -8 successes at volume inside
budget), additional's is the carried partial class's three
firings (48/240 volume, -11 successes) on an arm where leg L
is inert. Whether an evidence-derived condition on the partial
abstention class — one that distinguishes the stationary
population leg L and the carried legs fire on from the onset
population C21/9 now holds — can hold criterion 6's frozen
form on BOTH cohorts while holding B1 engagement (criteria
21/9, PASSing both as a carried profile), checkpoint-32
release (criteria 18/5), B2 protection (criterion 1), and
return-A profiles (criteria 17/4/2) as co-graded guards, on NEW
cohorts under a NEW protocol. Recorded but not selected:
criteria 17/4 FAIL on both cohorts, carried identical to the
decisive baseline with leg L changing no return-A state — a
further return-A retry needs a condition on the non-engaged
fall-through population, which no graded population this cycle
sizes; criterion 1 FAILs development only, carried identical,
with additional PASSing in full through leg L's B2 taking;
the leg-L B1 hypothesis is untested at graded checkpoints,
not refuted — its only B1 taking was at ungraded k=16, and a
retry would need a cohort design that actually draws graded
leg-S-disarmed partial triggers, which no graded population
this cycle sizes.
