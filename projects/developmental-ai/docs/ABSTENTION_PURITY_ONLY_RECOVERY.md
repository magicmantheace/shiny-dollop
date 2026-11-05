# Abstention purity-only recovery — support leg removed from the abstention gate

**4 November 2026 protocol / 5 November 2026 graded. Status: optional, simulated,
unpromoted. No default-controller promotion, no PR merge, no D1–D10 or
V2A/V2B roadmap change, no AthenZ/Synveil integration.**

## Experiment identity

- **Name and purpose:** `abstention_purity_only_recovery` — whether
  removing the abstention release gate's support leg (leg S)
  entirely — so the abstention branch is gated only by reference
  purity (leg P, >= 0.70) on top of its carried-over trigger and
  authority arming — can restore first-switch (B1) onset protection
  without giving back stationary selectivity or checkpoint-32
  release. The limitation it targets is the one the graded
  abstention-higher-corroboration experiment selected: at B1
  neither recovery branch can protect (regular recovery is
  archive-blocked; the minority branch was unarmed at every B1
  onset state), so abstention is B1's only protective response,
  and the two release-gate generations had thinned it generation
  by generation (B1 pooled onset harm across the purity / release
  / higher-corroboration generations: 31 / 47 / 63 development and
  58 / 88 / 88 additional, the last exactly equal to recent8).
  Build Order Priority 1 (Independent Learning), items 2 + 3 + 4;
  handoff §8 weak uncertainty calibration / excessive abstention
  and slow or incorrect recovery of old knowledge. This
  protocol's PRIMARY criterion is criterion 8, first-switch B1
  onset protection restored; criteria 6 (stationary selectivity),
  5 (release by checkpoint 32, including sub-condition (d),
  abstained branch in 0 of 9 states), 1 (B2 protection), and 4
  (return-A harm) are its co-graded guards, reported second,
  third, fourth, and fifth below.
- **Candidate:** `AbstentionPurityOnlyRecoveryMemory`
  (`developmental_ai/abstention_purity_only_recovery.py`) —
  IDENTICAL to the graded
  `AbstentionHigherCorroborationRecoveryMemory` in acting model
  (recent8 exactly), extended signal (newest 2 vs 50-event
  reference, opposed_count), retained archive (events[:N-26]),
  archive concordance, joint test (joint_count >= 1), recovery
  model, abstention trigger (opposed_count == 2), the full
  three-leg authority condition, the minority branch in full, and
  the reference-purity gate (>= 0.70) on BOTH recovery branches
  and as leg P of the abstention gate. The SINGLE changed element
  is the abstention gate's composition: leg S (acting-window
  opposition support) is REMOVED entirely, leaving leg P as the
  gate's sole leg — abstention_gate_armed == purity_armed at
  every checkpoint in both cohorts (script-verified),
  abstention_disarmed_by_support always false, support_threshold
  and abstention_support_threshold recorded as null. The
  acting-window opposition records are still computed and
  recorded at every checkpoint exactly as in the graded release
  candidates — RECORDS ONLY, never a decision input — so the
  >= 4, >= 3, and ungated rules remain derivable from the records
  alone. Minimum 52 events, else all-available fallback (never
  exercised in evaluation; all checkpoints >= 240 events).
  Separate optional learner; the default controller and all
  existing learners are untouched; the graded
  higher-corroboration candidate and every earlier candidate
  appear only as baselines.
- **Branch and commits:** `developmental-ai/abstention-purity-only-recovery`
  (forked from `developmental-ai/abstention-higher-corroboration-recovery` @
  `3654778`, the grading commit of the
  abstention-higher-corroboration experiment). Protocol frozen at
  `3cf4aef`; implementation at `721f314`; evaluation at `684dbd3`.
  This grading report is committed on top of the evaluation
  commit.
- **Frozen protocol:** `benchmarks/abstention_purity_only_recovery_protocol.json`
  (schema `developmental-ai.abstention-purity-only-recovery-protocol/v1`,
  frozen 2026-11-04, before any implementation, unit test, harness,
  or score inspection for this experiment).
- **Cohorts:** development 422003/422021/422039 and additional
  423001/423017/423041 — NEW at freeze, disjoint from every
  earlier cohort. Both cohorts are now **INSPECTED** and must
  never be re-tuned against. Detailed results:
  `benchmarks/abstention_purity_only_recovery_results.json`
  (development) and
  `benchmarks/abstention_purity_only_recovery_additional_results.json`
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
  tests`: 1153 tests OK in the implementation and evaluation stages,
  and 1153 tests OK again in this grading stage (run this pass; the
  grading-stage changes are documentation only, no code changed).
  Focused candidate tests: 37/37 PASS in the implementation stage.
- Historical regressions: **PASS** — `python -m
  benchmarks.transfer_benchmark` (unchanged) exited 0 in the
  evaluation stage, and exited 0 again when re-run in this grading stage.
- Frozen cohorts: **PASS (ran exactly as registered)** — both cohorts
  were run with no change to any frozen parameter, threshold, seed, or
  checkpoint. Every checkpoint entry carries the candidate's full
  decision record (extended-reference signal records, legacy
  reference-24 signal records (records-only), archive concordance
  records, per-event joint and legacy joint flags/records, the full
  authority record, the full minority record, the full purity
  record, AND the full abstention-gate record — per-event
  acting-window opposition records over the last 8 events
  (records-only), acting matched/opposed counts,
  supporting_opposed_count, support threshold recorded as null,
  abstention_gate_armed, abstention_disarmed_by_purity,
  abstention_disarmed_by_support (always false) — plus every count,
  branch, recovery-fired / minority-fired / abstained /
  gate-evaluable flags, acting source, and the records-only
  abstention-higher-corroboration-rule (>= 4),
  abstention-release-rule (>= 3), reference-purity-rule (ungated),
  minority-rule, extended-rule, legacy-long-rule,
  unexpired-joint-rule, and bounded-authority-rule derivations), a
  checkpoint SHA256, and restore-replay identity verified true at
  every checkpoint in both cohorts (script-verified again in this
  grading stage — 72/72 entries per cohort; no criterion-7 field
  missing anywhere; support_threshold null at 72/72 entries per
  cohort and abstention_gate_armed == purity_armed at every entry).
- Linux validation: **UNVERIFIED** — no GitHub Actions run on the
  evaluation or grading commit was checked; no CI is claimed for
  `684dbd3` or for this grading commit.
- Windows validation: **UNVERIFIED** — same reason as above.

## Per-criterion grading (precommitted, graded individually, per cohort)

All figures below were script-computed from the saved detailed results
in this grading stage, not hand-copied (script and output kept with the
campaign records). Denominators are exact episode counts (48 per
stage-checkpoint cell; 96 per pooled B1, B2 or return-A onset figure;
288 per pooled all-stage onset figure); decision-record denominators
are seed-checkpoint states (3 per stage per cohort at checkpoint 2
alone; 6 per stage per cohort pooled at checkpoints 2 and 4; 9
switch-stage states per cohort at checkpoint 32; 15 graded control
states per cohort). Criterion 8, this experiment's PRIMARY criterion,
is reported first, and criteria 6, 5, 1, and 4, its co-graded guards,
next, as the protocol requires.

| # | Criterion | Development | Additional |
| --- | --- | --- | --- |
| 8 | PRIMARY first-switch B1 onset protection ((a) abstention TAKEN ≥2/6 pooled B1 onset states; (b) B1 harm ≤ guard; (c) B1 harm < recent8) | **PASS** | **FAIL** |
| 6 | Stationary control selectivity not given back (abstentions ≤32/240; successes ≥ recent8 −6; harm ≤ recent8) | **PASS** | **PASS** |
| 5 | Release/productivity by k=32 (abstentions ≤36/144; successes ≥ recent8 −8; non-recent8 branch in ≤1 of 9 k=32 states; (d) abstained branch in 0 of 9 states) | **PASS** | **FAIL** |
| 1 | Second-switch B2 protection preserved ((a) minority recovery TAKEN ≥3/6 pooled B2 onset states; (b) minority TAKEN ≤1/6 B1 and ≤1/6 return-A; (c) B2 harm ≤ guard AND ≤60% of recent8; (d) B2 successes ≥ guard + 16) | **FAIL** | **PASS** |
| 4 | Return-A onset harm preserved (≤ guard AND ≤60% of recent8, pooled k=2,4) | **PASS** | **FAIL** |
| 2 | Return-A recovery successes preserved (≥40% of frozen_A AND ≥ guard + 16, pooled k=2,4) | **PASS** | **PASS** |
| 3 | Pooled onset harm (≤ guard same-cohort; ≥5/6 cells ≤ recent8) | **PASS** | **PASS** |
| 7 | Full accounting in the saved detailed results | **PASS** | **PASS** |

### Criterion 8 (PRIMARY) — first-switch B1 onset protection restored (PASS development, FAIL additional — on trigger sparsity, not gate blockage)

Development: **(a) ENGAGEMENT** — the abstention branch was TAKEN
at **3 of 6** pooled B1 onset states (1/3 at checkpoint 2, 2/3 at
checkpoint 4; required ≥ 2). The three taken states: seed 422003
checkpoint 2 (acting_opposed_count 3, supporting 1, realized
purity 0.857), seed 422003 checkpoint 4 (acting_opposed_count 5,
supporting 3, purity 0.833), and seed 422021 checkpoint 4
(acting_opposed_count 3, supporting 1, purity 0.829) — each scored
0 successes / 0 harm / 16 abstentions against recent8's 10/6, 13/3,
and 0/16 at the same states. **(b) HARM vs GUARD** — candidate B1
pooled onset harm **43** vs the guard's **59** — passes. **(c)
HARM vs RECENT8** — 43 < recent8's **68** — passes. B1 successes,
reported in full as the protocol requires: candidate **5** vs
recent8 **28** vs the guard's **5** — the candidate's B1
productivity is the guard's, not recent8's: the restored
protection is abstention, and its success cost is stated, not
hidden (it is not always_abstain's 0 successes / 0 harm either:
the candidate abstained at 48 of 96 B1 onset episode-checkpoints,
not 96). Against the records-only derivations at the same states:
the reference-purity-rule (ungated) derivation also took 3, the
abstention-release-rule (>= 3) derivation also took 3, and the
abstention-higher-corroboration-rule (>= 4) derivation took only
1 — the removed leg would have blocked **zero** development
firings beyond what the >= 3 gate already took, and the >= 4 gate
would have blocked 2 of the 3 (both acting_opposed_count-3
states). No B1 onset abstention was disarmed by leg P on either
cohort (purity was armed at all 12 B1 onset states across
cohorts, realized 0.757–0.881). Additional: **(a) FAILS** — the
abstention branch was TAKEN at only **1 of 6** pooled B1 onset
states (1/3 at checkpoint 2, 0/3 at checkpoint 4; required ≥ 2).
The sole taken state is seed 423041 checkpoint 2
(acting_opposed_count 2, supporting_opposed_count **0**, realized
purity 0.806) — exactly the zero-support configuration BOTH
graded release gates blocked — scoring 0/0/16 against recent8's
1/15 there. **(b)** candidate B1 harm **63** vs the guard's **78**
— passes. **(c)** 63 < recent8's **78** — passes. B1 successes:
candidate **17** vs recent8 **18** vs the guard's **18** — near
parity, because only one state abstained. Attribution, exact
from the records, as pre-registered: the ungated
reference-purity-rule derivation ALSO took only that 1 state, so
leg P blocked nothing on this cohort; the other five B1 onset
states never triggered at all (opposed_count 1, 1, 0, 1, 1 — the
trigger requires both newest events opposed). This is the
protocol's pre-registered **trigger-sparsity** failure mode,
charged against criterion 8 as registered, not excused: with
leg S removed, the gate is no longer what thins B1 — on both
cohorts the candidate took EVERY triggered, authority-armed B1
state (4 of 4 across cohorts) — but a gate cannot restore
firings the trigger never produces, and on the additional cohort
the trigger produced one.

### Criterion 6 — stationary control selectivity not given back (PASS, both cohorts — a no-trigger PASS on the abstention side)

Development: pooled graded control checkpoints (2, 4, 8, 16, 32)
abstentions **0/240** — (a) passes — successes **129** vs recent8
**126** (required ≥ 120) — (b) passes — harm **111** vs recent8
**114** — (c) passes. Additional: abstentions **0/240**,
successes **106** = recent8 **106** (required ≥ 100), harm **134**
= recent8 **134** — all three sub-conditions pass. As the
protocol requires, this PASS is reported as what it is: on
neither control arm did any stationary abstention trigger occur
— no control state had abstention_would_fire set, none was
gate-disarmed, and the candidate's taken branch differs from the
records-only abstention-higher-corroboration-rule,
abstention-release-rule, AND reference-purity-rule derivations
at **0 of 15** graded control states per cohort. The
pre-registered central cost-side risk — a stationary false pair
passing leg P, which is armed by design on stationary evidence —
was therefore **not realized and not tested** on these cohorts:
leg P was armed at all 15 graded control states per cohort
(realized purity 0.775–0.878 development, 0.750–0.905 additional),
so had a trigger occurred, nothing in this candidate would have
released it; the cohorts simply drew no graded stationary
trigger, exactly as in the preceding cycle. The one non-recent8
control state is productive and is not an abstention: development
control checkpoint 8, seed 422039, a retained_archive recovery
scoring 11/5 against recent8's 8/8 (the source of the control
arm's +3 successes / −3 harm against recent8 there); the
additional control arm is downstream-identical to recent8 at
every checkpoint. The minority branch never fired on either
control arm (fractions 0.134–0.159 development, 0.143–0.192
additional, unarmed throughout).

### Criterion 5 — release and productivity by checkpoint 32 (PASS development, FAIL additional — on the carried recovery branches' records)

Development: k=32 abstentions **0/144** — (a) passes — successes
**63** vs recent8 **62** (required ≥ 54) — (b) passes —
non-recent8 branch in **1 of 9** switch-stage k=32 states — (c)
passes — abstained branch in **0 of 9** — (d) passes. The one
non-recent8 state is a productive return-A retained_archive
routing, seed 422003 at realized purity 0.703 (armed), scoring
10/6 against recent8's 9/7. No k=32 abstention trigger was
present at any development state, so sub-condition (d) holds
there without any leg-P release being exercised. Additional:
abstentions **0/144** — (a) passes — successes **71** vs recent8
**70** (required ≥ 62) — (b) passes — abstained branch in **0 of
9** — (d) passes — but the candidate takes a non-recent8 branch
in **3 of 9** states — (c) **fails** (allowance 1). The three
states: B2 minority_archive seed 423001 at purity 0.733 (armed),
scoring 9/7 against recent8's 8/8; B2 minority_archive seed
423017 at purity 0.719 (armed), scoring 11/5 against recent8's
9/7; and return-A retained_archive seed 423041 at purity exactly
0.700 (armed), scoring 12/4 against recent8's 14/2. All three are
carried recovery branches released by the carried purity gate —
the abstention gate sits below them and is not involved; the
candidate's branch differs from the records-only
higher-corroboration-rule and release-rule derivations at 0 of 9
additional k=32 states. Sub-condition (d) deserves its own
sentence, because it was the exposed one: at return-A checkpoint
32, seed 423017, a late abstention trigger WAS present
(opposed_count 2) and leg P **disarmed** it (realized purity
0.643 < 0.70, abstention_disarmed_by_purity recorded) — the
candidate fell through to recent8 at 1/15 where the records-only
reference-purity-rule derivation abstained — so on this cohort
(d) holds by an exercised leg-P release, not by the absence of a
trigger. The failure is (c) alone: three purity-armed late
recovery routings against a 1-of-9 records allowance, two of
them minority routings scoring better than recent8 at their
states and one retained routing scoring worse on both axes —
the records condition grades the routing count, not its local
productivity, and it is charged as recorded.

### Criterion 1 — second-switch B2 protection preserved (FAIL development, PASS additional — the harm ceiling, not engagement)

Development: **(a) ENGAGEMENT** — minority recovery was TAKEN at
**3 of 6** pooled B2 onset states (1/3 at checkpoint 2, 2/3 at
checkpoint 4; required ≥ 3 — exactly at the threshold). Realized
minority fractions at the B2 onset states were 0.251–0.299 and
realized purity was armed at every state (0.800–0.943). **(b)
SELECTIVITY** — minority TAKEN at **0 of 6** B1 onset states and
**0 of 6** return-A onset states — passes. **(c) HARM** —
candidate B2 pooled onset harm **63** vs the guard's **94** —
the guard comparison passes — but vs recent8's **94** the 60%
ceiling is **56.4** — **fails by 6.6**. **(d) PRODUCTIVITY** —
B2 pooled successes **33** vs guard + 16 = **18** (guard scored
2) — passes. Decomposition: the three minority-taken states
scored 11/5, 11/5, and 11/5; the cohort's B2 harm sits in the
three non-engaged states, which ran through recent8 at 16 harm
each (seeds 422021 checkpoint 2 and 422039 checkpoints 2 and 4,
minority_joint_count 0 at each). Engagement at exactly the
threshold with harm above the ceiling is the graded outcome —
the minority branch protected where it fired and the criterion
still fails, charged not softened. The abstention gate changed
no B2 figure: the candidate abstained at 0/6 B2 onset states on
both cohorts and no B2 onset abstention was disarmed. Additional:
**(a)** minority TAKEN at **5 of 6** pooled B2 onset states (3/3
at checkpoint 2, 2/3 at checkpoint 4), fractions 0.290–0.317,
purity armed at every state (0.800–0.909); **(b)** 0/6 B1 and
0/6 return-A; **(c)** B2 harm **42** vs the guard's **66** and
vs recent8's **81** (ceiling 48.6) — passes both; **(d)**
successes **54** vs guard + 16 = **30** (guard 14) — passes.

### Criterion 4 — return-A onset harm preserved (PASS development, FAIL additional — inherited from the carried profile)

Development: pooled return-A harm candidate **37** vs guard
**55** — (a) passes — and vs recent8 **77** the 60% ceiling is
**46.2** — (b) passes. Additional: candidate **56** vs guard
**47** — (a) **fails by 9** — and vs recent8 **92** the ceiling
is **55.2** — (b) **fails by 0.8**. Attribution, from the
records: regular recovery was TAKEN at 4 of 6 return-A onset
states on both cohorts, minority at 0/6, abstention at 0/6, and
the candidate is identical to BOTH the
abstention-higher-corroboration and abstention-release baseline
methods on every return-A onset figure on the additional cohort
(40 successes / 56 harm) — the failure is the carried recovery
profile measured against this cohort's guard and ceiling, not
an effect of removing leg S, exactly the pre-registered carried
failure mode. Charged unchanged, as in the preceding gradings —
neither excused nor misattributed to the one changed parameter.
(Development return-A figures differ across the gate generations
only through the B1-independent recovery records: candidate 59
successes / 37 harm there, identical to all three gated baseline
methods.)

### Criterion 2 — return-A recovery successes preserved (PASS, both cohorts)

Development: candidate pooled return-A (k=2,4) successes **59**
against frozen_A **64** — the 40% floor passes (59 × 5 = 295 ≥
64 × 2 = 128) — and against the guard-relative floor of
guard + 16 = **25** (guard scored 9) — passes. Additional:
candidate **40** against frozen_A **60** (200 ≥ 120) and
guard + 16 = **17** (guard scored 1) — passes. Reported in full,
as the protocol requires — and with the same prominence as the
PASS: plain cumulative scored **64 / 68** return-A successes at
**32 / 28** harm and frozen_A **64 / 60** at **32 / 36** harm,
so on BOTH cohorts BOTH simple retention baselines again beat
the candidate on both axes at return-A (candidate 59 at 37 harm
development; 40 at 56 additional). The joint / bounded / long
baselines scored 62 / 62 / 62 successes (development) and 50 /
50 / 50 (additional) at return-A — above the candidate on
additional, where the carried profile's return-A engagement is
thinner. Cumulative's and frozen_A's first-return dominance
over every gated variant in this line is now recorded on five
consecutive graded cohort pairs.

### Criterion 3 — pooled onset harm not above the guard (PASS, both cohorts)

Development: pooled onset (B1, return-A, B2 × k=2,4) candidate
harm **143** vs guard **208** — (a) passes — with candidate harm
≤ recent8 in **6 of 6** individual cells — (b) passes (vs
recent8 pooled 239). Additional: candidate **161** vs guard
**191** — (a) passes — with **6 of 6** cells ≤ recent8 (vs
recent8 pooled 251; the tightest cell is B1 checkpoint 4, 31 =
31, which the criterion's ≤ form passes). Per-stage decomposition
against the guard: development B1 43 vs 59 (−16), return-A 37 vs
55 (−18), B2 63 vs 94 (−31) — every stage below the guard, the
first cohort in this gate line of which that is true. Additional
B1 63 vs 78 (−15), return-A 56 vs 47 (**+9** — the criterion-4
failure, absorbed here by the other stages), B2 42 vs 66 (−24).
Restoring B1 below the guard on both cohorts is what brings the
pooled figure back under the guard on additional, where the
preceding candidate failed this criterion by 24.

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
8 events (records-only), acting matched/opposed counts,
supporting_opposed_count, support threshold recorded as null,
abstention_gate_armed, abstention_disarmed_by_purity,
abstention_disarmed_by_support (false at every entry) — plus
every count, branch, recovery-fired / minority-fired / abstained
/ gate-evaluable flags, acting source, and the records-only
abstention-higher-corroboration-rule, abstention-release-rule,
reference-purity-rule, minority-rule, extended-rule,
legacy-long-rule, unexpired-joint-rule, and
bounded-authority-rule derivations) at every checkpoint;
checkpoint SHA256; and restore-replay identity (true at every
checkpoint in both cohorts, script-verified in this stage —
72/72 entries per cohort; no field missing anywhere). Learner
information-acquisition actions = 0, additional requested
observations = 0, and learner training actions = 0 throughout,
as frozen.

## Learning evaluation

Candidate vs recent8 (successes / harmful TEST actions / abstentions,
48 episodes per cell).

| Stage-ckpt | Dev candidate | Dev recent8 | Add candidate | Add recent8 |
| --- | --- | --- | --- | --- |
| B1-0 † | 2 / 46 / 0 | 2 / 46 | 3 / 45 / 0 | 3 / 45 |
| B1-2 | 2 / 30 / 16 | 12 / 36 | 0 / 32 / 16 | 1 / 47 |
| B1-4 | 3 / 13 / 32 | 16 / 32 | 17 / 31 / 0 | 17 / 31 |
| B1-8 | 30 / 18 / 0 | 30 / 18 | 12 / 20 / 16 | 20 / 28 |
| B1-16 | 17 / 31 / 0 | 17 / 31 | 29 / 19 / 0 | 29 / 19 |
| B1-32 | 19 / 29 / 0 | 19 / 29 | 17 / 31 / 0 | 17 / 31 |
| return-A-0 † | 0 / 48 / 0 | 0 / 48 | 21 / 27 / 0 | 1 / 47 |
| return-A-2 | 26 / 22 / 0 | 0 / 48 | 20 / 28 / 0 | 0 / 48 |
| return-A-4 | 33 / 15 / 0 | 19 / 29 | 20 / 28 / 0 | 4 / 44 |
| return-A-8 | 24 / 24 / 0 | 21 / 27 | 32 / 16 / 0 | 33 / 15 |
| return-A-16 | 30 / 18 / 0 | 31 / 17 | 29 / 19 / 0 | 15 / 33 |
| return-A-32 | 29 / 19 / 0 | 28 / 20 | 24 / 24 / 0 | 26 / 22 |
| B2-0 † | 0 / 48 / 0 | 0 / 48 | 0 / 48 / 0 | 0 / 48 |
| B2-2 | 11 / 37 / 0 | 0 / 48 | 33 / 15 / 0 | 2 / 46 |
| B2-4 | 22 / 26 / 0 | 2 / 46 | 21 / 27 / 0 | 13 / 35 |
| B2-8 | 24 / 24 / 0 | 11 / 37 | 34 / 14 / 0 | 24 / 24 |
| B2-16 | 24 / 24 / 0 | 23 / 25 | 35 / 13 / 0 | 19 / 29 |
| B2-32 | 15 / 33 / 0 | 15 / 33 | 30 / 18 / 0 | 27 / 21 |
| control-0 † | 27 / 21 / 0 | 27 / 21 | 17 / 31 / 0 | 17 / 31 |
| control-2 | 23 / 25 / 0 | 23 / 25 | 23 / 25 / 0 | 23 / 25 |
| control-4 | 34 / 14 / 0 | 34 / 14 | 15 / 33 / 0 | 15 / 33 |
| control-8 | 26 / 22 / 0 | 23 / 25 | 24 / 24 / 0 | 24 / 24 |
| control-16 | 29 / 19 / 0 | 29 / 19 | 23 / 25 / 0 | 23 / 25 |
| control-32 | 17 / 31 / 0 | 17 / 31 | 21 / 27 / 0 | 21 / 27 |

† Checkpoint 0 is a reported diagnostic, not graded. k=0 candidate
harm per switch stage is 46 / 48 / 48 (development, B1 / return-A /
B2) and 45 / 27 / 48 (additional).

**Removing leg S, isolated (candidate vs the records-only
derivations and the baseline methods):** across both cohorts the
candidate's taken branch differs from the ungated
reference-purity-rule derivation at exactly **ONE** graded state —
additional return-A checkpoint 32, seed 423017, where leg P
disarmed a late abstention (criterion 5) — and from the
abstention-release-rule (>= 3) and higher-corroboration-rule
(>= 4) derivations at exactly the B1 states leg S used to block:
development B1 checkpoints 2 and 4 (seeds 422003 and 422021, both
acting_opposed_count 3 — differences against the >= 4 rule only;
the >= 3 rule took both) and additional B1 checkpoint 2, seed
423041 (acting_opposed_count 2, supporting 0 — a difference
against BOTH combined rules). In scores, the candidate differs
from the abstention-higher-corroboration baseline method at 2/72
checkpoints (development) and 1/72 (additional), from the
abstention-release baseline method at 0/72 and 1/72, and from the
reference-purity baseline method at 0/72 and 1/72. On development
the candidate is score-identical to both the release and purity
baseline methods on every aggregate — development's B1 triggers
all carried at least one supporting event, so leg S was not the
binding constraint there either; the restoration on development
(43 vs the higher-corroboration candidate's 65 B1 harm) is
against the >= 4 generation, and the >= 3 generation had already
achieved it on that cohort profile. The one state in either
cohort where removing leg S changed an outcome against BOTH
combined gates is the additional zero-support state — worth
−15 harm at that state (0/0 abstained vs recent8's 1/15) — and
it was not enough: criterion 8(a) needs two taken states and the
additional trigger produced one. **The gate question this line
has pursued for three generations is now answered in both
directions: no composition of the abstention gate binds B1 any
longer — leg P blocked zero B1 firings across both cohorts, and
every triggered state was taken — what binds B1 is the trigger
itself (opposed_count == 2 on the newest pair), which fired at
4 of 12 B1 onset states across cohorts.**

Reference points on the same cohorts (pooled onset, k=2,4, all
stages; successes / harm / abstentions): `abstention_release_gated_recovery`
(leg P + leg S ≥ 3) scored **97/143/48** (development) and
**112/176/0** (additional); `reference_purity_gated_recovery`
(the ungated-abstention generation) scored 97/143/48 and
111/161/16 — identical to the candidate on development and, on
additional, differing only at the checkpoint-32 abstention the
candidate's purity record disarms (its k=32 line is 70/58/16
against the candidate's 71/73/0, an abstention that removed 15
harm and 1 success at that state while failing the records
condition in its own generation's form); the decisive
`abstention_higher_corroboration_recovery` (leg S ≥ 4) scored
107/165/16 and 112/176/0 — note its higher development successes
(107 vs 97) come entirely from acting through the two B1 states
this candidate abstains at (10 successes there against the
candidate's 0 — the whole pooled difference), the productivity
price of the restored protection, stated plainly. The harm comparator
`evidence_opposition_guard` scored pooled onset harm 208
(development) and 191 (additional). `cumulative` and `frozen_A`
dominate the candidate at return-A on both axes on both cohorts
(criterion 2, reported in full there). The privileged expected
oracle pooled onset successes/harm were 182/106 (development)
and 202/86 (additional): onset tasks remain largely solvable,
and every realizable learner here remains far from that.

**Persistence note (checkpoints 8 and 16, reported not graded):**
pooled switch-stage successes/harm/abstentions at k=8 were
78/66/0 (development) and 78/50/16 (additional), identical to all
three gated baseline methods on both cohorts; at k=16, 71/73/0
(development) and 93/51/0 (additional), also identical. Realized
purity at the switch-stage k=32 states was 0.632–0.742
(development, armed 4/9) and 0.630–0.733 (additional, armed 6/9)
— again above the 0.5675 global-composition design value at the
armed states, the pre-registered self-fit compression.

**Retention note:** what removing leg S retained is everything
the combined gates had won — no checkpoint-32 abstention state
on either cohort (and on additional, an exercised leg-P release
of the one late trigger that occurred), a control arm with no
abstention at all, and the B2 / return-A carried profile intact.
What it restored is B1 harm below the guard and below recent8 on
BOTH cohorts for the first time in the gate line (43 < 59 < 68;
63 < 78 = 78 — the guard and recent8 coincide on additional).
What it could not restore is B1 engagement volume on a cohort
whose trigger draws are sparse: the abstention branch's ceiling
is now set by the newest pair's own information content, the
same upstream binding constraint two earlier cycles found for
recovery engagement at return-A k=2.

**Generalization level:** at most handoff level 2–3 (choosing among
/ applying already-supplied representations under a rule change,
plus designer-supplied signal, concordance, minority, routing,
expiry, disagreement-age, reference-width, reference-purity, and
abstention-gate rules at any of their graded compositions). No
level-6 or novel-representation claim is made. The minority read
the candidate carries exploits this simulator's exact-inversion
structure, and leg P reads reference self-agreement in this
simulator's geometry — so even the PASSes are bounded: B1 onset
harm at or below the guard's and below recent8's on both cohorts
with the gate no longer blocking any triggered firing, in this
simulator only — not general first-contact handling, not
calibrated uncertainty, and not real-world safety.

## Safety and evidence costs

- Harmful TEST actions: reported per cell above and per criterion;
  pooled onset 143 (development) / 161 (additional) against
  recent8's 239 / 251 and the guard's 208 / 191.
- Harmful TRAIN acquisition actions by the learner: **0** — the
  learner issues no training interventions; all TRAIN evidence
  comes from the shared external actor stream, whose actual harmful
  / productive / neutral outcomes, reported harm, and label flips
  are published per seed in the saved results (criterion 7).
- Failed-by-abstention: pooled onset 48 / 288 (development) and
  16 / 288 (additional); checkpoint-32 0 / 144 on both cohorts;
  stationary control 0 / 240 on both cohorts. Abstentions are
  scored as failed tasks, never as successes.
- Additional requested observations: **0**.
- False confidence / unnecessary abstention: no unnecessary
  abstention occurred on either cohort (the control arms are
  abstention-free, and every onset abstention removed harm at its
  state); the cycle's false-confidence cost is instead the
  untriggered B1 onset harm the trigger never engaged — on
  additional, all 63 B1 harm sits at states where the candidate
  acted through recent8, 47 of it at checkpoint 2 alone — graded
  under criterion 8, not buried.
- Report integrity: frozen protocol committed before implementation
  (`3cf4aef`); cohorts inspected only through the registered
  evaluation; no parameter was re-tuned against the 422003-family /
  423001-family cohorts after inspection. Provenance limitation:
  developer-selected simulation seeds in one engineered two-feature
  simulator family; not independent external proof.

## Scientific conclusion

**Failed.** Per the protocol's own grading definitions: NOT
Demonstrated (criteria 8, 5, 1, and 4 FAIL); the **Failed**
clause is triggered on the additional cohort three times over —
criterion 8 FAILs there (engagement 1 of 6 against the required
2), criterion 5 FAILs there (non-recent8 branch in 3 of 9 k=32
states against the 1-of-9 allowance), and criterion 4 FAILs
there (return-A harm 56 vs the guard's 47 and the 55.2 ceiling)
— any one of which is sufficient under the clause (criterion 7
PASSes on both cohorts; criteria 6, 2, and 3 PASS on both;
criterion 1 FAILs only on development, which the clause does not
key on, and is charged in full above). The
Partially-demonstrated clause requires criterion 8 to PASS on
both cohorts; it does not, so that category is unavailable.
NOT a Regression (pooled onset harm 143 / 161 well below
recent8's 239 / 251 on both cohorts; control successes 129 / 106
against recent8's 126 / 106, not below by more than 6 on either;
checkpoint-32 successes 63 / 71 against the recent8 − 4 lines of
58 / 66; full unit suite and historical transfer benchmark pass
— see Verification). What the experiment establishes, stated as
prominently as the failure: the abstention gate's composition is
no longer a binding constraint anywhere it was graded — leg P
blocked zero B1 onset firings on either cohort, every triggered
and authority-armed B1 state was taken (4 of 4 across cohorts,
including the zero-support state both combined gates blocked),
B1 pooled onset harm is below the guard's and below recent8's on
both cohorts for the first time in this line, pooled onset harm
is below the guard's on both cohorts (criterion 3 PASS/PASS,
which the preceding candidate failed), and sub-condition 5(d)
holds on additional through an exercised leg-P release of a
late abstention rather than the absence of a trigger. What
failed is engagement volume and the carried records: the B1
trigger fired at only 1 of 6 additional onset states, so the
PRIMARY engagement floor cannot be met by any gate composition;
the carried recovery branches took 3 of 9 additional k=32 states
against a 1-of-9 records allowance; the carried return-A profile
missed this cohort's guard comparison and ceiling; and on
development the minority branch's exactly-threshold engagement
(3 of 6) left B2 harm above its 60%-of-recent8 ceiling.
Generalization level 2–3, simulator-bounded (see Learning
evaluation).

**Next limitation (selected for the next cycle, Priority 1):**
first-switch (B1) onset trigger sparsity — with the gate
composition settled (leg P alone blocked nothing at B1 on either
cohort and every triggered state was taken), B1's remaining
exposure is the trigger itself: opposed_count == 2 on the newest
pair fired at only 4 of 12 B1 onset states across cohorts (3/6
development, 1/6 additional), the five untriggered additional
states carrying all 63 of that cohort's B1 harm at recent8's
per-state level, and the minority branch was again unarmed at
every B1 onset state on both cohorts (fractions 0.134–0.185), so
no branch of the family engages at an untriggered B1 state.
Measurable: on NEW cohorts, whether a protective response at B1
onset that can engage on partial opposition evidence (the
opposed_count == 1 states the current trigger ignores, or an
equivalent widened onset signal) can reach the engagement floor
and hold B1 pooled onset harm at or below the guard's (and below
recent8's) on both cohorts, without giving back stationary
selectivity (criterion 6's form — partial-opposition evidence
occurs on stationary arms too, and its false-firing cost is the
hypothesis's priced risk) or the checkpoint-32 release
(criterion 5's form) — on NEW cohorts under a NEW protocol.
Recorded but not selected: criterion 5's additional failure is
the carried recovery branches' k=32 records (3/9 — two minority
routings that outscored recent8 at their states and one retained
routing that did not), not an abstention or gate effect;
criterion 4's additional failure is shared identically with
both combined-gate baseline methods at return-A onset;
criterion 1's development failure is B2 harm concentration at
the three non-engaged states (16 harm each through recent8)
with minority engagement at exactly its floor; and cumulative /
frozen_A dominate the candidate at return-A on both axes on
both cohorts for the fifth consecutive graded cohort pair —
plain retention's first-return dominance remains open and
unaddressed by gate or trigger tuning.

Keep the learner optional and unpromoted, default controller
unchanged, no merge, no AthenZ/Synveil integration, D1–D10/V2A/V2B
unchanged.
