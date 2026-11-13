# Stationary support abstention recovery — a supporting-opposition leg (leg S) on the abstention gate for both trigger classes

**12 November 2026 protocol frozen; 12 November 2026
implementation; 13 November 2026 evaluation; graded 13 November
2026. Status: optional, simulated, unpromoted. No
default-controller promotion, no PR merge, no D1–D10 or V2A/V2B
roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `stationary_support_abstention_recovery`
  — whether ONE changed element, leg S, a SUPPORTING-OPPOSITION
  leg on the abstention gate for BOTH trigger classes (the
  abstention branch fires only if supporting_opposed_count >= 1,
  support_threshold 1, where supporting_opposed_count =
  acting_opposed_count − opposed_count is a quantity already
  recorded records-only; the full gate becomes leg P AND leg S,
  the partial gate leg P AND (leg R OR leg C) AND leg S;
  abstention_disarmed_by_support recorded true exactly when leg
  S alone disarms a trigger whose other gate legs all pass and
  neither recovery branch fired), can hold criterion 6's frozen
  stationary form on BOTH cohorts — the singleton grading's
  selected limitation (criterion 6 FAILed on BOTH cohorts in
  that cycle — development on sub-condition (b) alone, successes
  86 vs the >= 88 line with volume AT the budget; additional on
  (a) AND (b), volume 48/240 and successes 89 vs the >= 95 line
  — and carried that cycle's Regression: control successes
  −8 / −12, both past the more-than-6 both-cohorts line, on five
  carried abstention firings identical to the decisive
  baseline's, whose supporting counts were 0, 1, 0, 1, 1) —
  while holding B1 engagement (criterion 9), checkpoint-32
  release (criteria 18/5, carried profile), B2 protection
  (criterion 1), and return-A profiles (criteria 17/4/2) as
  co-graded guards. Leg P, leg R, leg C, leg T, leg W, leg N,
  and leg D were explicitly NOT re-tuned. Build Order Priority
  1 (Independent Learning); handoff §8 excessive abstention /
  weak uncertainty calibration. This protocol's PRIMARY
  criterion is criterion 19, criterion 6's frozen stationary
  form promoted to PRIMARY; criteria 6, 9, 18, 5, 1, 11, 17, 4,
  2, 3, and 7 are its co-graded guards. The protocol also froze
  a grading cap: a Demonstrated verdict additionally requires
  at least one graded control state in at least one cohort at
  which the decisive baseline took an abstention with
  supporting_opposed_count == 0 while the candidate acted
  through leg S (abstention_disarmed_by_support true).
- **Candidate:** `StationarySupportAbstentionRecoveryMemory`
  (`developmental_ai/stationary_support_abstention_recovery.py`)
  — IDENTICAL to the graded
  `NewestSingletonReleaseRecoveryMemory` in every element
  (acting model recent8 exactly, extended signal, retained
  archive, archive concordance, joint test joint_count >= 1,
  recovery model, the full three-leg authority condition, the
  minority branch in full INCLUDING the inverted minority model
  and leg W on the minority branch, leg T on both recovery
  branches, leg N and leg D on the regular branch, leg P >=
  0.70, leg R and leg C on partial abstention triggers, and the
  full / retained-partial abstention classes with the widened
  class removed records-only, singleton_release_fired carried)
  — verified by a diff against the graded singleton candidate
  at implementation: the ONLY code differences are leg S (the
  abstention gate gains supporting_opposed_count >= 1,
  support_threshold 1 in place of the records-only null, for
  BOTH trigger classes; abstention_disarmed_by_support
  recorded true exactly when leg S alone disarms a trigger
  whose other gate legs all pass and neither recovery branch
  fired; the new reason string abstention_disarmed_by_support
  in the carried reason chain), its docstring, and
  names/schema. Separate optional learner; the default
  controller and all existing learners are untouched; the
  graded singleton candidate appears only as the decisive
  baseline.
- **Branch and commits:**
  `developmental-ai/stationary-support-abstention-recovery`
  (forked from `362a573`, the singleton grading commit).
  Protocol frozen at `53a7525` (BEFORE implementation);
  implementation at `2adf382`; evaluation at `9695ceb`. This
  grading report is committed on top of the evaluation commit.
- **Frozen protocol:**
  `benchmarks/stationary_support_abstention_recovery_protocol.json`
  (frozen 2026-11-12, before any implementation, unit test,
  harness, or score inspection for this experiment).
- **Cohorts:** development 532003/532021/532039 and additional
  533001/533017/533041 — NEW at freeze, verified disjoint from
  every earlier cohort. Both cohorts are now **INSPECTED** and
  must never be re-tuned against.
- **Decisive baseline:** `newest_singleton_release_recovery`
  (identical but for leg S on the abstention gate; branch
  selection differs only where a taken abstention trigger of
  the decisive baseline carries supporting_opposed_count == 0
  with every other gate leg passing, where the candidate falls
  through to recent8). `recent8` is the simplest credible
  baseline and the candidate's own acting model.

## Verification

- Unit tests: PASS — 120/120 new candidate tests at
  implementation; full suite 1968 tests OK in the
  implementation and evaluation stages, and re-run in this
  grading stage: 1968 tests OK (`python3 -m unittest discover
  -s tests`, run 2026-11-13 this pass). The new tests include
  the discriminating states: zero-support full and partial
  triggers the decisive singleton baseline took as abstentions
  and the candidate disarms to recent8 through leg S
  (abstention_disarmed_by_support true), and the
  supporting-exactly-1 rows on which the candidate abstains
  with a record identical to the decisive baseline's after
  stripping the support fields alone.
- Historical regressions: PASS — historical transfer benchmark
  (`python3 -m benchmarks.transfer_benchmark`) exit 0 in the
  evaluation stage and re-run in this grading stage, standard
  three-seed output (success gains 0.5567 / 0.50 / 0.51 on
  seeds 17 / 23 / 41).
- Frozen cohorts: PASS (run exactly as registered) — both
  cohorts evaluated at `9695ceb`; every checkpoint entry
  carries per-method successes / harmful TEST actions /
  abstentions, the candidate's full decision record (including
  the full support, singleton, newest-breadth, acting-breadth,
  companion, and stale records), checkpoint SHA256, and
  restore-replay identity (script-verified in this grading
  stage: true at every checkpoint in both cohorts, 72/72
  entries per cohort).
- Linux validation: UNVERIFIED (no GitHub Actions run on the
  grading commit was checked; no CI is claimed).
- Windows validation: UNVERIFIED (same).

## Per-criterion grading (precommitted, graded individually, per cohort)

Graded script-computed from the saved detailed results at
`9695ceb` (grading script and output kept with the campaign
records). PRIMARY criterion 19 first, then co-graded guards
6, 9, 18, 5, 1, 11, 17, 4, 2, 3, 7. Development / additional
throughout.

**Criterion 19 — PRIMARY (stationary control selectivity,
criterion 6's frozen form): PASS / PASS — as a carried
profile, with a stationary-support null result.** All three
sub-conditions pass on both cohorts. Development: (a)
abstentions 16/240 <= 32; (b) successes 119 vs recent8 119 —
at EXACT recent8 parity, required >= 113; (c) harm 105 vs
recent8 121. Additional: (a) abstentions 0/240; (b) successes
118 vs recent8 118 — at EXACT recent8 parity, required >=
112; (c) harm 122 vs recent8 122, at exact parity. But the
pass demonstrates nothing about leg S on the stationary arm,
and the report says so in those words: **a carried-profile
pass with a stationary-support null result — the leg
demonstrated nothing there on these draws.** Leg S's designed
stationary population — a decisive-baseline control abstention
with supporting_opposed_count == 0 — did not occur on either
cohort: development drew exactly ONE graded control trigger
(seed 532039, k=8, partial through leg R AND leg C, purity
0.892, supporting 2, acting_opposed 3), taken identically by
candidate and decisive baseline (0/0 vs recent8 0/16 at its
state), and additional drew NONE (zero taken control
abstentions, candidate line identical to recent8 in full:
118/122/0). The candidate is branch-identical to the decisive
baseline at 15/15 graded control states on both cohorts, so
**the grading cap is NOT MET on either cohort** and any
stationary PASS here is the carried profile's, never a
support-leg demonstration. The singleton cycle's stationary
Regression does not recur: control successes are at exact
recent8 parity on both cohorts (diff 0 / 0, against the
more-than-6 both-cohorts clause). All 15 graded control states
per cohort are accounted per state in the grading output:
development's sole non-recent8 control state is the taken
partial above; the other 14 are recent8 under candidate,
decisive baseline, and recent8 alike; additional's 15 are all
recent8 under all three. Leg S disarmed ZERO control states
on either cohort.

**Criterion 6 — stationary control selectivity (guard
position): PASS / PASS.** The same computation as PRIMARY
criterion 19, reported twice as registered, never two
thresholds — a carried-profile pass with the same
stationary-support null result stated under criterion 19.

**Criterion 9 — first-switch (B1) engagement: FAIL / PASS.**
Development FAILs on sub-condition (a) alone, and the failure
is leg S's own realized onset price: abstention TAKEN at 2/6
pooled B1 onset states (1 full + 1 retained partial through
leg C only), against the >= 3 floor; harm 57 <= guard 66 (b)
PASS and 57 < recent8 82 (c) PASS. The decisive baseline took
5/6 on the same states; leg S disarmed three of those five
takings, each a zero-support trigger falling through to
recent8 at exactly recent8's own scores: seed 532021 k=2
(partial through leg C, purity 0.941, supporting 0, candidate
0/16 vs decisive abstained 0/0), seed 532039 k=2 (partial
through leg C, purity 0.947, supporting 0, 1/15 vs 0/0), and
seed 532039 k=4 (full, purity 0.943, supporting 0, 1/15 vs
0/0). Candidate's two takings are seed 532003 k=2 (partial
through leg C, purity 0.767, supporting 3, 0/0) and seed
532021 k=4 (full, purity 0.941, supporting 1, 0/0). B1
successes 7 vs recent8 14 / guard 14, stated in full.
Additional PASSes at the floor: TAKEN 3/6 (1 full + 2 retained
partial, through leg C alone and leg R AND leg C), harm 47 <=
guard 58 and 47 < recent8 89. The decisive baseline took 5/6
there too; leg S disarmed two of its takings, both seed
533041 zero-support triggers falling through to recent8 0/16
vs abstentions 0/0: k=2 (full, purity 0.875) and k=4 (partial
through leg C, purity 0.868). Candidate's three takings are
seed 533001 k=4 (full, purity 0.897, supporting 3), seed
533017 k=2 (partial through leg C, purity 0.900, supporting
2), and seed 533017 k=4 (partial through leg R AND leg C,
purity 0.875, supporting 2). B1 successes 1 vs recent8 7 /
guard 6, stated in full. Per-state B1 onset reporting (all 6
pooled states per cohort, with trigger kind, corroboration
path, supporting count, and both methods' branches and
scores) is in the grading output.

**Criteria 18 / 5 — checkpoint-32 release (criterion 18 is
the preceding cycle's PRIMARY in guard position; criterion 5
is the same computation in its carried guard position):
PASS / FAIL.** Development PASSes in full: (a) abstentions
0/144; (b) successes 65 = recent8 65 (line 57); (c)
non-recent8 1/9 — the carried leg-D singleton firing at seed
532021 return-A k=32 (newest 1 / acting 3, stale 0, purity
0.703, retained 10/6, identical under the decisive baseline);
(d) abstained 0/9. Additional FAILs on sub-condition (d)
alone: (a) abstentions 16/144 PASS; (b) successes 60 vs
recent8 62, required >= 54, PASS; (c) non-recent8 1/9 PASS;
(d) abstained 1/9 against the frozen 0/9 FAIL — the one state
is a CARRIED partial abstention at seed 533017 return-A k=32
(partial, purity 0.714, stale 0, acting 2, newest 1,
supporting 1 — leg S armed, so the candidate took it
identically to the decisive baseline, 0/0 vs recent8 2/14).
Leg S neither caused nor could have disarmed that state. All
nine k=32 states per cohort are listed per state in the
grading output; every other k=32 state is recent8 under
candidate, decisive baseline, and recent8 alike on both
cohorts (development candidate k=32 pooled 65/79/0, identical
to decisive and to recent8 in successes; additional 60/68/16,
identical to decisive, vs recent8 62/82/0).

**Criterion 1 — second-switch (B2) protection: PASS / FAIL.**
Development PASSes in full: minority TAKEN 3/6 at the floor
(a); selectivity 0/6 at B1 and 0/6 at return-A (b); harm 43 vs
guard 70 and ceiling 0.60 × recent8 86 = 51.6 (c) PASS both;
successes 37 vs guard 10 + 16 = 26 (d). One of development's
B2 takings under the decisive baseline was disarmed by leg S
(seed 532021 k=2, full trigger, supporting 0, purity 0.947 —
decisive abstained 0/0, candidate recent8 0/16), which is
also the whole of development's B2 harm gap vs the decisive
baseline (candidate 43 vs decisive 27; successes identical
37 = 37, the disarmed state's recent8 action scoring 0/16
against the abstention's 0/0). Additional FAILs on (a),
(c)-ceiling, and (d): minority TAKEN 1/6 (a) FAIL — identical
to the decisive baseline's count; selectivity 0/6 / 0/6 (b)
PASS; harm 55 vs guard 87 PASS on the guard comparison but
ceiling 0.60 × recent8 87 = 52.2 FAIL on (c) — and the ceiling
failure IS leg S's: the decisive baseline's B2 harm is 39,
passing the ceiling, and leg S's single additional B2
disarming (seed 533041 k=2, partial through leg C, supporting
0, purity 0.816; decisive abstained 0/0, candidate recent8
0/16) contributes the entire +16 gap; successes 9 vs guard
9 + 16 = 25 (d) FAIL, identical to the decisive baseline's 9.
The minority-model cross-check PASSes at every minority-fired
state (5 development / 3 additional applicable), with
first-frame choices differing from the widened-window method
at 3 development and 1 additional minority-fired B2 onset
states checked.

**Criterion 11 — B1/stationary conjunction (carried): FAIL /
PASS.** Development fails on its B1 side alone (criterion 9
above; its stationary side passes); additional passes both
sides.

**Criteria 17 / 4 — return-A onset harm (criterion 17 is the
preceding-preceding cycle's PRIMARY form in guard position;
criterion 4 is the same computation in its carried guard
position): PASS / FAIL.** The candidate's return-A line is
identical to the decisive baseline's on both cohorts — leg S
disarmed no return-A state on either cohort. Development
PASSes both sub-conditions, narrowly: harm 46 vs guard 79 (a)
and ceiling 0.60 × recent8 79 = 47.4 (b), passing the ceiling
by 1.4; regular recovery TAKEN 3/6, return-A successes 50.
Additional FAILs both: harm 82 vs guard 77 (a) FAIL and
ceiling 0.60 × recent8 93 = 55.8 (b) FAIL; regular recovery
TAKEN 1/6, successes 14 — a carried profile identical to the
decisive baseline's at every return-A onset state. Stated in
full, as registered: frozen_A (68 successes / 28 harm) and
cumulative (58/38) beat the candidate (14/82) on BOTH axes at
return-A on additional, and frozen_A (62/34) and cumulative
(66/30) beat the candidate (50/46) on BOTH axes on
development as well — both-axes dominance on both cohorts
again.

**Criterion 2 — return-A recovery successes: PASS / FAIL.**
Development: successes 50 vs frozen_A 62 (floor 40% = 24.8)
PASS on (a) and guard 17 + 16 = 33 PASS on (b). Additional:
successes 14 vs frozen_A 68 (floor 27.2) FAIL on (a) and
guard 3 + 16 = 19 FAIL on (b) — the same carried return-A
population as criteria 17/4.

**Criterion 3 — pooled onset harm: PASS / PASS.** Pooled
onset harm 146 vs guard 215 development and 184 vs guard 222
additional (a); individual onset cells <= recent8 in 6/6 on
both cohorts (b). Stated in full: pooled onset harm is ABOVE
the decisive baseline's on both cohorts, entirely through leg
S's seven disarmings — development candidate 146 vs decisive
84 (+62, successes 94 vs 92), additional 184 vs decisive 136
(+48, successes 24 vs 24) — against recent8's 247 / 269, so
no Regression clause triggers on this arm (below). Every one
of the seven disarmings converted a decisive abstention's 0/0
into a recent8 action at exactly recent8's own scores (six of
the seven at 0/16, one at 1/15): leg S bought +2 successes on
development and +0 on additional for +62 / +48 harm.

**Criterion 7 — full accounting: PASS / PASS.** Replay
identity true at every checkpoint in both cohorts (72/72
entries per cohort); no criterion-7 field missing anywhere;
support_threshold 1 everywhere (the frozen leg-S value, in
place of the carried records-only null);
supporting_opposed_count recomputable as acting_opposed_count
− opposed_count everywhere with 0 mismatches;
abstention_disarmed_by_support recomputed exactly everywhere
(gate blocked, supporting < 1, every other gate leg passing)
with 0 mismatches; abstention gate recomputable everywhere
(incl. the leg-C composition AND leg S) with 0 mismatches;
companion_threshold null everywhere; widened_threshold 3,
staleness_pair_threshold 2, preceding_pair_threshold 1,
acting_joint_threshold 3, and newest_joint_threshold 2
everywhere; companion fields recomputable at every partial
state (26 development / 27 additional) and at fallback at
every non-partial state (46 / 45); stale lists of 18 with
both pair counts recomputable everywhere with 0 mismatches;
acting lists of 8 with both acting counts recomputable
everywhere with 0 mismatches; newest lists of 4 with the
newest count recomputable everywhere with 0 mismatches and
newest records == acting records' last four everywhere; both
acting breadth flags, the newest breadth flag,
singleton_release_fired, and the recovery_fired (leg N OR
leg D) composition recomputed everywhere with 0 mismatches;
stationary-support-rule == candidate branch everywhere;
singleton-release-rule == decisive baseline branch
everywhere; acting-breadth-rule == acting branch everywhere;
companion-rule == companion branch everywhere;
pre-acting-release-rule == pre-acting branch everywhere;
preceding-pair-rule == widened-removal-rule everywhere;
widened-rule == inverted branch everywhere; newest4 /
widened_armed recomputable everywhere;
abstention_trigger_kind in {full, partial, none} everywhere
— never widened, as the carried removal requires;
minority_model_archive_count == archive_events_count
everywhere; minority_model_inverted true everywhere;
minority-model cross-check PASS at every minority-fired state
(5/5 development, 3/3 additional applicable); learner
acquisition actions 0 throughout. Leg T disarmed ZERO states
on either cohort for the sixth consecutive cycle — recorded,
not hidden: the breadth-disarmed flags the grading output
lists at onset and checkpoint 32 are leg W's / leg N's carried
flags, identical under the decisive baseline.

## Learning evaluation

Candidate vs recent8 (simplest credible baseline), successes
/ harmful TEST actions per stage-checkpoint cell (candidate
first; abstention episodes in parentheses where nonzero):

Development — B1: k=0 9/39 vs 9/39; k=2 1/31 (16) vs 8/40;
k=4 6/26 (16) vs 6/42; k=8 22/10 (16) vs 32/16; k=16 29/19 vs
29/19; k=32 21/27 vs 21/27. return-A: k=0 14/34 vs 5/43; k=2
20/28 vs 11/37; k=4 30/18 vs 6/42; k=8 39/9 vs 34/14; k=16
19/29 vs 19/29; k=32 23/25 vs 23/25. B2: k=0 0/32 (16) vs
2/46; k=2 23/25 vs 7/41; k=4 14/18 (16) vs 3/45; k=8 25/23 vs
21/27; k=16 7/41 vs 7/41; k=32 21/27 vs 21/27. Control: k=0
19/29 vs 19/29; k=2 20/28 vs 20/28; k=4 24/24 vs 24/24; k=8
18/14 (16) vs 18/30; k=16 28/20 vs 28/20; k=32 29/19 vs
29/19.

Additional — B1: k=0 1/47 vs 1/47; k=2 1/31 (16) vs 5/43; k=4
0/16 (32) vs 2/46; k=8 11/5 (32) vs 32/16; k=16 32/16 vs
32/16; k=32 18/30 vs 18/30. return-A: k=0 1/47 vs 1/47; k=2
1/47 vs 1/47; k=4 13/35 vs 2/46; k=8 26/22 vs 18/30; k=16
29/19 vs 27/21; k=32 25/7 (16) vs 27/21. B2: k=0 2/46 vs
2/46; k=2 0/32 (16) vs 0/48; k=4 9/23 (16) vs 9/39; k=8 21/27
vs 22/26; k=16 9/39 vs 9/39; k=32 17/31 vs 17/31. Control:
k=0 22/26 vs 22/26; k=2 24/24 vs 24/24; k=4 26/22 vs 26/22;
k=8 23/25 vs 23/25; k=16 22/26 vs 22/26; k=32 23/25 vs
23/25 — identical to recent8 at every control checkpoint.

Pooled onset (checkpoints 2 and 4): candidate 94 successes /
146 harm development and 24/184 additional, vs decisive
baseline 92/84 and 24/136 (the differences are exactly leg
S's seven onset disarmings), vs guard 215 / 222 harm, vs
recent8 41/247 and 19/269. The candidate differs from the
decisive baseline in score at 4/72 development checkpoints
and 3/72 additional checkpoints (the seven disarmings, all at
graded onset states; there are no ungraded disarmings — the
disarming count at ALL checkpoints equals the graded count on
both cohorts), from the companion method at 9/72 and 11/72,
and from the inverted method at 11/72 and 11/72. Past
knowledge retention is graded by checkpoint-32 and stationary
behaviour above: checkpoint 32 carries one leg-D firing
(development, identical to decisive) and one carried partial
abstention (additional, identical to decisive), and the
stationary arm drew leg S's designed population zero times.
Generalization level: at most handoff level 2–3, as
registered — designer-supplied rules throughout; no
novel-representation claim.

## Safety and evidence costs

- Harmful TEST actions: pooled onset 146 development / 184
  additional (candidate), detailed per criterion above; B1
  pooled onset harm 57 / 47; B2 43 / 55; return-A 46 / 82;
  stationary control harm 105 / 122; checkpoint-32 harm 79
  development (= decisive = recent8) and 68 additional
  (= decisive; vs recent8 82).
- Failed-by-abstention: candidate onset abstention episodes
  48/288 development and 80/288 additional; stationary 16/240
  development and 0/240 additional; checkpoint-32 0/144
  development and 16/144 additional.
- Learner information-acquisition actions: 0 throughout.
  Additional requested observations: 0. Learner training
  actions: 0.
- External TRAIN actor costs (shared evidence stream,
  identical for all methods, published in full, never netted
  against TEST results): development — stage A 720 actions,
  260 actually harmful (263 reported harmful, 21 label
  flips); B1 192 actions, 81 harmful; B2 192, 82;
  return-A subset 144, 46; control continuation 192, 54.
  Additional — stage A 720 actions, 239 actually harmful (238
  reported, 23 flips); B1 192, 75; B2 192, 84; return-A subset
  144, 53; control continuation 192, 62.
- False confidence / unnecessary disarmings: leg S disarmed
  exactly seven states across both cohorts, ALL at onset and
  ZERO on the control arm it was designed for; every disarming
  replaced a 0/0 abstention with a recent8 action scoring at
  recent8's own (poor) onset scores — six at 0/16 and one at
  1/15 — for a pooled price of +110 harm against +2 successes
  across both cohorts. Its designed stationary population did
  not occur on these draws. Leg T disarmed zero states for the
  sixth consecutive cycle.
- Report integrity: all figures script-computed from the
  saved detailed results at `9695ceb` in this grading stage;
  the 532003-family / 533001-family cohorts are INSPECTED and
  no parameter was re-tuned against them or any earlier
  cohort.

## Scientific conclusion

**Failed, NOT a Regression.** Failed under the protocol's own
definitions (PRIMARY criterion 19 PASSes on BOTH cohorts —
but as a carried profile with a stationary-support null
result, cap NOT MET, so it is not a support-leg demonstration
— and the Failed clause triggers on the additional cohort
several times over: criteria 18/5 FAIL there on sub-condition
(d) alone, criterion 1 FAILs there, and criteria 17, 4, and 2
FAIL there; criterion 7 PASSes both, and criterion 19/6
PASSes both). Partially demonstrated does not
rescue the verdict: the Partially clause requires criterion
19 and 7 to pass on both (they do) with a guard failing on
either cohort, but the Failed clause triggers independently
on the additional cohort, as in the preceding gradings, and
governs. No Regression clause triggers: pooled onset harm
146 / 184 is below recent8's 247 / 269 on both cohorts;
stationary-control successes are at exact recent8 parity on
both (119 = 119, 118 = 118; diff 0 / 0 against the
more-than-6 both-cohorts clause — the singleton cycle's
stationary Regression does NOT recur); checkpoint-32
successes 65 vs the recent8 − 4 line of 61 development and 60
vs 58 additional both hold; the full unit suite (1968 tests)
and the historical transfer benchmark both pass in this
grading stage.

The honest summary of leg S itself, stated plainly: **on the
arm it was designed for, it was never exercised** — the
stationary draws contained exactly one control trigger across
both cohorts (supporting 2, taken identically) and zero
zero-support control abstentions, so the stationary hypothesis
remains UNTESTED by these cohorts, neither confirmed nor
refuted; the PRIMARY's PASS is the carried abstention profile
passing on draws where that profile happened to cost nothing
(one firing on development, none on additional, against the
singleton cycle's five). **Where leg S WAS exercised — at
switch onset — it was purely a cost on these draws:** seven
zero-support onset abstentions disarmed to recent8, five of
them B1 takings whose removal drops development's B1 count
below its floor (criterion 9 FAIL, development) and holds
additional's exactly at it, one B2 disarming per cohort each
worth +16 harm at 0 successes (pushing additional's B2 harm
past its ceiling, criterion 1(c)), and a pooled onset price
of +62 / +48 harm against the decisive baseline for +2 / +0
successes. The zero-support onset abstentions the leg removed
were, on these draws, protective: their decisive 0/0 outcomes
replaced recent8 actions scoring 0/16, 1/15, 1/15, 0/16,
0/16, 0/16, 0/16. A support condition that cannot tell a
stationary zero-support firing (the singleton cycle's harmful
population: supporting counts 0, 1, 0, 1, 1 at purities
0.846–0.889) from an onset zero-support firing (this cycle's
protective population: supporting 0 at purities 0.816–0.947)
does not hold the frozen forms together on these cohorts.

Next limitation selected: **P1 first-switch (B1) onset
engagement under the support-gated abstention classes** —
criterion 9 FAILs on development on sub-condition (a) alone
(TAKEN 2/6 against decisive 5/6, harm passing both
comparisons) entirely through leg S's three B1 disarmings, and
additional passes only at the floor (3/6) after two more;
whether an evidence-derived condition on the abstention gate
— one that distinguishes the onset zero-support population
from the stationary zero-support population the support leg
was designed for, without re-tuning leg S's threshold, leg P,
leg R, or leg C — can hold criterion 9's frozen form on BOTH
cohorts while holding stationary selectivity (criteria 19/6,
PASSing both as a carried profile), checkpoint-32 release
(criteria 18/5), B2 protection (criterion 1), and return-A
profiles (criteria 17/4/2) as co-graded guards, on NEW cohorts
under a NEW protocol. Recorded but not selected: additional's
criteria 18/5 failure is one carried partial abstention
(supporting 1, taken identically by the decisive baseline) —
no new population to retry; additional's return-A failures
(criteria 17/4/2) are a carried profile identical to the
decisive baseline with frozen_A / cumulative both-axes
dominance on both cohorts again; additional's criterion 1
count and successes failures are carried identical (minority
1/6 and 9 successes under both methods), with leg S's share
exactly its ceiling sub-condition via the one B2 disarming;
the stationary-support hypothesis itself is untested, not
refuted — its designed population did not occur, and a retry
would need a cohort design that actually draws zero-support
stationary triggers, which no graded population this cycle
sizes. Keep the learner optional and unpromoted, the default
controller unchanged, no merge, no AthenZ/Synveil integration,
D1–D10/V2A/V2B unchanged.
