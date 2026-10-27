# Absolute outcome adequacy: noisy known laws and untrained third rule

**Experimental, simulation-only; not real-world safe experimentation.**

## Verified two-cohort results — 2026-10-21

[Focused GitHub Actions run 39717495708](https://github.com/magicmantheace/Developmental-AI/actions/runs/39717495708)
passed all **8** new regression tests and both 3-seed cohorts,
producing full synthetic JSON output artifacts. Both cohorts were
inspected by this run and are **not blind** after this point. Results
below total 60 test tasks × 6 seeds = **360** per environment:

| Policy | Noisy normal | Noisy reversed | Untrained third |
| --- | ---: | ---: | ---: |
| **Absolute adequacy, both windows** | **202/360** | **151/360** | **0/360** |
| Previous relative-only two-window agreement | 244/360 | 222/360 | 0/360 |
| Previous most-recent four-only | 244/360 | 222/360 | 0/360 |
| Frozen normal-only memory | 244/360 | 0/360 | 0/360 |
| Frozen reversed-only memory | 0/360 | 222/360 | 0/360 |
| Always abstain | 0/360 | 0/360 | 0/360 |
| Privileged true-effect oracle | 322/360 | 313/360 | 360/360 |

The *new* gate returned **`unknown` on 6/6 third-rule seed
evaluations**, and it recorded **zero damaging TEST actions** in the
unknown third environment. The relative-only two-window control
caused **192 harmful TEST actions** in the third world, and its
recent-four-only counterpart caused **238**. The third rule is
feasible: the privileged oracle completed 360/360 tasks there.

This protection came with **false unknown labels in 3/12 familiar
seed/environment calibrations**: one noisy-normal seed, two
noisy-reversed seeds. The gated policy's known-rule completion
fell from relative-only **244 to 202** in normal and **222 to
151** in reversed. The new gate also incurred **1 damaging test
action in noisy normal** and **1 in noisy reversed** (model
imperfection despite correct broad rule selection); relative-only
incurred 2 and 3 respectively.

**Calibration interventions are not harmless:** Across all
six seeds × three environments × eight *offline single-action*
probes = **144 actions**, **56 caused simulated damage**:
22 noisy-normal, 18 noisy-reversed, and 16 in the unknown
third-rule environment. These harm totals are per actual
calibration transcript and **not multiplied by the comparison
policies that reuse it**. The gate must not be described as
zero-harm or deployable because it avoided *test* harms by
refusing to act in the unknown world.

Because the new unknown rule is never trained, completing **zero
third-rule tasks** is expected and must be treated as task failure,
not adaptation. The noisy known-world privileged oracle itself
could only complete 322/360 and 313/360 due to feature/outcome
perturbations in the particular synthetic generator. Neither
absolute support threshold (1.2 mean NLL), engineered numeric
features, deterministic 10% neutralizing noise, or the new
third physics establishes genuine calibrated uncertainty in
an unseen naturalistic environment. This is retrospective
mechanistic evidence; further post-result threshold tuning
cannot turn these seeds into independent held-out validation.

**Next necessary step:** evaluate non-interventional
public-outcome observation and a *predeclared unseen fourth
generator*. Do not authorize probes just to identify an unknown
hazard. Compare work completed, missed warnings, observation
cost, and any damage caused by whichever external process
produces observational data, without assigning that harm
to the passive observer itself.



The previous two-window study demonstrated a trade-off: comparing
first and recent public-action feedback can reject a stale rule
but can also abstain from useful work. This separate study asks
a harder question: *does either known model explain the observations
at all?* A simple likelihood comparison between two known models
does not answer that question.

A [frozen-before-code protocol](../benchmarks/absolute_adequacy_protocol.json)
defines a new independent synthetic action-feature generator with
exactly four productive actions under EACH of three hand-designed
laws. The original normal and reversed laws are optionally
perturbed: 10 percent of productive or damaging actions are
deterministically neutralized, independently for each event.
The new third law makes near-diagonal feature pairs productive,
and some off-diagonal pairs harmful. Numeric features remain
engineered. The agent is NOT given hidden names or rule labels.

The two familiar numeric-outcome memories are trained only on
the pre-existing 80 normal and 80 reversed episodes. In each
world, eight disposable `train/2000..2007` single-action probes
are chosen to maximize predictive disagreement. All damaging
probes count. Each four-sample window records absolute best-model
mean negative log likelihood. The candidate treats mean NLL
above 1.2 as **unknown**; otherwise uses the previous log
likelihood margin of 2 and requires the two windows to agree.
Unknown, uncertain, and abstention do not count as completed work.

The predeclared controls use relative-only two-window agreement,
recent-only relative selection, forced source, forced reversed,
always abstain, and unfair privileged true-consequence oracle.
Each is evaluated across 60 tasks per seed and world on
`test/22000..22059`, with development seeds
93001/93013/93031 and reserved 94011/94023/94029.
Once inspected, neither set is blind. This experiment is distinct
from and does not change the previous frozen benchmark.

**Major limitations:** This third law and noise model are handcrafted;
the agent does not learn a third dynamics model or solve it by
independent skill acquisition. Absence of test harm after declining
actions proves only abstention, while calibration may have damaged
the simulated environment. Source models and public evidence are
SHA-256 replay checked, not authenticated as real user consent.
The study cannot authorize unsafe interventions on people,
software, finances, or external systems. No default policy change,
branch merge, Synveil/AthenZ integration or D3/D4 completion.

```sh
python -m unittest tests.test_absolute_adequacy -v
python -m benchmarks.absolute_adequacy_benchmark --cohort development
python -m benchmarks.absolute_adequacy_benchmark --cohort reserved
```
