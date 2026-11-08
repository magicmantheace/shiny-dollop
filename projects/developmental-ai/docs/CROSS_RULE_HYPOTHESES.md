# Precommitted cross-rule feature-hypothesis research

**23 October 2026 — optional Developmental AI simulation, not a promoted agent.**
[Protocol](../benchmarks/cross_rule_protocol.json) committed at `9d649d7` **before** learner, benchmark, tests or results. Six frozen developer-chosen seed IDs (development 232003/232021/232039; additional 233001/233017/233041) are now all inspected; not an independent blind evaluation. A test-fixture correction (`38040f8`) made an intentionally corrupt outcome unconditionally inconsistent, without changing the protocol, learner, simulator or success criteria.

## What changed scientifically

Prior experiments inverted the effects of a *single* numeric max-minus-min relation. This study authored two **different asymmetric causal mappings**, retaining exactly the same `inlet`/`outlet` public integer keys, anonymous candidate actions, budget six and target three productive steps:

- **Source A and its return:** range `abs(a-b)` with a hidden per-seed band k in {2,4,6}; progress at k/k+1, harm at very small/large gaps, otherwise neutral.
- **Checksum:** `(2*a+b+hidden_seed_salt)%5`: progress residues 0/1, harm 2/3, neutral 4.
- **Ordered:** `(a+3*b+hidden_seed_salt)%7`: progress 0/1, harm 2/3/4, neutral 5/6.

The two target rules are not just reversed span relations. The simulator secretly stratifies every task's 12 unique anonymous actions into **five productive, four harmful and three neutral** candidates. This artificial mixture favors finding successful actions and must not be mistaken for natural environments.

The learner sees no simulator mode, salt, band, stage name or TRUE rule label. External independent random actor collects **one first-action public outcome** in each disposable TRAIN episode. Per seed: source240, checksum96, return-source48, ordered96. TEST uses held-out episode indices 230000–230019, 240000–240019, 250000–250019, **reused across checkpoints** (not independent checkpoint outcomes). Simulator outcomes here are deterministic and truthful: earlier stochastic/noisy-report limitations remain.

## Opt-in FeatureHypothesisMemory

The learner estimates progress/damage/neutral bucket frequencies with 0.25 Laplace smoothing for **four predefined feature hypotheses**: frozen first-192 source span; recent24 span; recent24 residue `(2*a+b)%5`; recent24 residue `(a+3*b)%7`. Unknown hidden salts are not supplied; the per-residue class frequencies must be estimated. The formulas themselves **are supplied by the developer**.

It selects a hypothesis by maximum summed log-likelihood over the latest eight public outcomes. Each predictive scoring model is fit strictly **before** its scored example (rolling preceding-24 examples for recent candidates). The selected recent action model then uses the latest 24 reports and chooses the action maximizing inherited `3*p(progress)-10*p(damage)`; this is training on current evidence for action, not fitting on prequential scoring labels. Exact predictive ties favor frozen source then span, checksum, ordered. It has **no abstention**. Checkpoint/restart uses append-only public `features/progress/damage` events and SHA256 deterministic replay, with source-truth authenticity **not** assured.

## Verification and full observed results

[**Focused GitHub Actions 39993563381 PASS**](https://github.com/magicmantheace/Developmental-AI/actions/runs/39993563381): **34 regression tests, both preregistered three-seed cohorts**, immutable held-out TEST scoring and downloadable per-seed JSON.

Successes out of **120 held-out TEST tasks** per checkpoint (six seeds × 20), no selected-policy abstentions:

| New observed feedback | Checksum | Return source | Ordered |
|---:|---:|---:|---:|
| 0 | 10 | 12 | 12 |
| 4 | 10 | 35 | 27 |
| 8 | **80** | **120** | 49 |
| 16 | **120** | **120** | 106 |
| 32 | **120** | **120** | **120** |
| 48 | — | **120** | — |
| 64 | **120** | — | **120** |
| 96 | **120** | — | **120** |

All **three preregistered goals passed** (checksum32 >=70/120; ordered32 >=70/120; return-source8 >=70/120). At checksum8, all six seeds selected the developer-supplied checksum hypothesis; at ordered16 all six selected the developer-supplied ordered hypothesis; at source-return8 all six reselected the frozen source hypothesis.

**Strong controls and limits:** at checksum32, the frozen source achieved **10/120**, recent8 span **10/120**, recent32 span **16/120**, while the model that was **privately told which transform was correct** and trained on the same last24 data scored **120/120**—exactly tying the selector. At ordered32, frozen span **12/120**, recent8 span **12/120**, recent32 span **14/120**, privileged correct transform **120/120**, selector **120/120**. At checksum8 the selector **80/120** ties the known-correct transform 80; ordered8 selector **49/120** trails known correct ordered transform **77/120**. The benchmark-only perfect action oracle succeeds 120/120 throughout. These comparisons show selection within a prewritten adequate library, **not discovery of formulas absent from it**.

**Harmful early negative transfer:** checksum zero evidence **110 harmful TEST actions /120**, ordered zero **108/120**, return-source zero **108/120** even though frozen source achieves 120/120 there. After four source-return observations the selector still succeeds only **35/120**. At ordered8 it incurs **71 harmful TEST actions/120**, worse than the privileged correct transform's 43. Every task without abstention ends upon its first damaging action. Always-abstain controls have zero harmful actions but **zero completed tasks**, 120 failures by abstention.

## External TRAIN acquisition harms (NOT repeated TEST harms)

| TRAIN stage | Unique observations/actions | Harmful | Productive | Neutral |
|---|---:|---:|---:|---:|
| Source | 1,440 | **487** | 567 | 386 |
| Checksum | 576 | **179** | 237 | 160 |
| Source returns | 288 | **84** | 129 | 75 |
| Ordered | 576 | **195** | 227 | 154 |
| **Total** | **2,880** | **945** | **1,160** | **775** |

The learner initiated **zero** TRAIN interventions. Every harmful source-actor action and harmful simulated TEST action has been counted separately.

## Falsification limits / next gate

This establishes **predictive choice among manually supplied feature laws** and retention of the source archive after different causal tasks, not independent D3 discovery of unknown physics, reliable first-contact behavior, proof of evidence truth, general purpose cognition, or real-world safe autonomy. Later perfect outcomes depend on the candidate formulas already matching the private simulator and artificially abundant productive actions.

A stronger new preregistered study must include truly **unrepresented** laws outside the provided hypothesis set, decoy/irrelevant feature transforms, evidence corruption, and tests of composing new features; score negative transfer and failed-by-abstention tasks separately. Do not tune on inspected seeds.

Reproduce:

```bash
python -m unittest tests.test_cross_rule tests.test_regret_switch tests.test_relation_transfer tests.test_stochastic_prequential -v
python -m benchmarks.cross_rule_benchmark --cohort development
python -m benchmarks.cross_rule_benchmark --cohort additional
```

Keep PR #2 draft/unmerged, existing default unchanged, and D1–D10/V2A/V2B roadmap and AthenZ/Synveil work separate. Focused CI PASS does not substitute for final-commit full Linux/Windows tests.
