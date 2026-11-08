# Quarantined candidate review (`candidate-review/v1`)

**Simulation only.** A saved model candidate can no longer be installed with just its model SHA-256 digest. A separate, **frozen held-out predictive review** must pass, then an explicit call must supply that *review's* exact checksum. There is no unattended promotion, real-person authentication, physical control, network transport, or AthenZ/Synveil permission escalation.

## Implemented workflow and migration

1. An immutable `ModelBank` already contains validated prior models. A `CandidateStore` binds itself to the seed and complete bank fingerprint, collects capped ordinary observation histories, and `propose()` fits a new model from its frozen training set (latent-state inference, known topology, initial beacon).
2. A caller produces **distinct** held-out sensor histories and calls `stage.review(bank, histories, min_gain=0.02, min_holdout=24)`. The review refuses exact duplicate histories, training overlap, malformed/privileged observations, insufficient samples, mismatched bank fingerprints and reused reviews. The benchmark uses `train` indices `5000..`, separate from existing-model training `0..` and candidate training `2000..`.
3. Review computes average per-observation predictive log likelihood for the candidate **and every** currently approved model on the *same* held-out data. It passes only if the candidate beats the **best** existing model by at least 0.02 nats/observation. Failure is immutable and blocks promotion; gather better evidence and start a new candidate review cycle, never silently alter a failed record.
4. SQLite stores held-out histories and a checksum-verified review receipt transactionally. Reopen validates the schema, seed, bank, number/digests of histories, candidate and scores by **recomputing the whole evaluation**. Corrupted or incompatible reviews fail closed. Existing candidate stores gain two tables via safe additive `CREATE TABLE IF NOT EXISTS` migrations; no old candidate can bypass the new gate.
5. Only `stage.promote(bank, name, approval_digest=review['review_digest'])` can install a **passed** candidate. The old model checksum is deliberately insufficient. Promotion is a separate explicit act; a checksum is not proof of owner consent. Existing active monitors reject the modified bank fingerprint and must be restarted for reviewed deployment.

```sh
python -m unittest discover -s tests -v
python -m benchmarks.candidate_review_benchmark --seeds 17 23 41 1009 1013 1031 --out benchmarks/candidate_review_results.json
python -m benchmarks.transfer_benchmark
```

## Results — inspected research seeds, not blind

Fixed **before** reviewing test results: 75 histories for each existing model, 80 candidate-training histories, 40 *separate* review histories, 60 **additional test** histories, five EM iterations, acceptance improvement 0.02 nats/observation. The independent test is used for reporting only, not for review or threshold selection. All six listed seeds were inspected; no new independently administered blind audit has been performed.

| Scenario | Held-out review passes | Separate test confirms >=0.02 improvement | Automatic promotions |
|---|---:|---:|---:|
| Known bank lacks standard/fixed, candidate learns standard/fixed | 6/6 | 6/6 | 0 |
| Known bank already covers standard/fixed and high/shifted, candidate learns high/fixed | 0/6 | 0/6 | 0 |

For the **useful missing-regime** scenario, per-seed review likelihood improvements ranged from +0.0792 to +0.1600; independent test improvements +0.0906 to +0.1776. For the **marginal mixed-regime** scenario, review gain ranged from -0.0082 to +0.0149, and no candidate reached the +0.02 gate on the independent test. Every seed and exact receipt is in [`benchmarks/candidate_review_results.json`](../benchmarks/candidate_review_results.json). These results demonstrate an acceptance rule on controlled simulator cases, not broad predictive superiority or performance gains to actual navigation.

## Important limits / next work

- **Cannot authenticate evaluation source:** The API checks exact duplicates and hashes, but independently supplied observations could be deliberately mislabeled, selectively chosen or generated from a contaminated distribution. A hash is not a signature; owner-signed audit receipts and data lineage must be implemented in AthenZ before treating approval as real authority.
- **Small and correlated environment family:** Both scenarios use the same known 9/11-ring geometry, sensors and simulation physics family. A held-out predictive likelihood advantage is not a bound on downstream navigation success or harm.
- **No online safe learning:** This does not change the detector's low coverage or its tendency to misselect regimes, and it does not address runtime distribution shift or unknown-world novelty. Candidate training remains separate and supervised by code, not an independent agent.
- **One-shot review:** A candidate's acceptance gate is immutable. Multiple independently replicated holdout batches, uncertainty intervals, action-level evaluation and monitored rollback remain open.
- **Reproducibility:** The repository itself still has additional `continuous_dynamics` tests. A complete repository test run should include those alongside the candidate tests before any release claim. The historical frozen transfer, detector and abstention baselines must not be tuned to these review results.
