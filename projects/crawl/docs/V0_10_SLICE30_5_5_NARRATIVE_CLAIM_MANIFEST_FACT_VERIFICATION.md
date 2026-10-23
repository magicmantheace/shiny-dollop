# Underreach v0.10 — Phase 30.5 Slice 5

## Narrative Claim Manifest & Fact Verification

Status: implementation candidate; local validation required before acceptance.

Protocol: `underreach.narrative-claim-verification.v1`

Implementation version: `30.5.5`

Accepted baseline: 30.5.4 — Delver Chronicle & Profile System.

Next canonical slice on acceptance: **30.5.6 — Presentation Identity System**.

---

## Purpose

30.5.5 is the first Phase 30.5 slice where generated narrative prose may exist in durable media state.

Generated prose remains presentation-only. It cannot become canonical truth and cannot become review-ready merely because a writer or model says it is correct.

The governing flow is:

```text
Deterministic Crawl Simulation
        ↓
Canonical Ledger
        ↓
30.5.1 MediaEnvelope.allowed_facts
        ↓
30.5.4 ChronicleChapter.allowed_fact_ids
        ↓
30.5.5 NarrativeDraft
        ↓
ClaimManifest
        ↓
Deterministic Fact Verification
        ↓
REVIEW_READY | NEEDS_REVIEW | REJECTED
```

---

## Authority boundary

The following are frozen:

- canonical gameplay truth remains owned only by the deterministic simulation;
- 30.5.5 writes only to the separate media SQLite database;
- prose, claim manifests, model assessments, and verification results cannot mutate the simulation or Ledger;
- writer self-certification is never trusted;
- deterministic contradictions cannot be overridden by a model;
- unsupported factual claims are rejected;
- stylistic text may pass only under bounded rules that detect no factual signal;
- no Unreal process is required;
- no local model is required for deterministic verification;
- no cloud API is required;
- no paid provider is required;
- 30.5.5 does not itself invoke a provider or enqueue generation work.

Snapshot contract:

```text
authoritative = false
canonical_owner = deterministic_simulation
presentation_can_mutate_simulation = false
writer_self_certification_trusted = false
auxiliary_model_can_override_deterministic_checks = false
local_model_required = false
cloud_api_required = false
paid_provider_required = false
provider_invocation_used = false
```

Paid or remote writer output may be ingested later only after the accepted 30.5.2 provider policy explicitly permits that execution. Merely recording provider provenance does not execute or authorize a provider.

---

## Durable media records

30.5.5 adds three presentation-only tables:

```text
media_narrative_drafts
media_claim_manifests
media_narrative_verifications
```

They live on the media engine established by 30.5.2 and never appear in canonical Crawl persistence.

---

## NarrativeDraft

A draft stores generated text before authority is granted to any factual assertion.

Fields include:

- deterministic draft ID;
- Chronicle chapter ID;
- prose;
- deterministic sentence segmentation;
- optional writer provider provenance;
- local/paid provider provenance flags when known;
- `generated_prose = true`;
- `presentation_can_mutate_simulation = false`;
- `canonical_authority = false`.

Draft identity includes the exact prose and provider provenance. Re-registering the same draft is idempotent.

Changing prose creates a different draft identity.

---

## ClaimManifest

The writer output must be accompanied by a structured manifest.

Initial claim vocabulary:

```text
claim_type = factual | stylistic
sentence_index
subject
predicate
target_or_value
supporting_allowed_fact_ids
confidence
```

Every claim is tied to one exact deterministically segmented sentence from the draft.

Factual claims require:

- subject;
- predicate;
- target/value;
- one or more normalized supporting allowed-fact IDs.

Stylistic claims carry no subject, predicate, target/value, or factual support.

The manifest cannot mark itself authoritative and cannot authorize a model to override deterministic checks.

---

## Allowed fact authority

30.5.5 does not independently reinterpret raw simulation state.

For each Chronicle chapter it loads only facts that satisfy both:

1. the fact exists in a registered source `MediaEnvelope.allowed_facts`;
2. the fact ID is present in the chapter's `allowed_fact_ids`.

This means richer MediaEnvelope context is not silently converted into claimable truth.

If an ownership, party, alliance, injury, death, social-memory, location, outcome, or other factual claim has no allowed fact supporting it, the claim is rejected.

This is intentionally conservative.

---

## Deterministic factual verification

A factual claim passes only when:

- every cited fact belongs to the chapter allowlist;
- the canonical allowed-fact key exactly matches `subject + predicate`;
- at least one cited fact has an exactly equal canonical value;
- the cited support set contains no unrelated fact IDs.

Outcomes:

### Exact match

```text
ClaimStatus = VERIFIED
reason = exact_allowed_fact_match
```

### Same canonical subject/predicate, wrong value

```text
ClaimStatus = REJECTED
reason = deterministic_fact_contradiction
```

This is the primary protection against wrong Stratum, wrong Sector, wrong event outcome, wrong actor, or any other supported predicate with a contradictory value.

### No canonical subject/predicate support

```text
ClaimStatus = REJECTED
reason = unsupported_factual_claim
```

This rejects invented item ownership, invented relationships, invented party/alliance state, and other facts when the chapter does not contain supporting allowed truth.

---

## Sentence coverage

By default every draft sentence must be represented by at least one claim.

An uncovered sentence causes the entire draft to be rejected.

This prevents a writer from submitting a valid manifest for one sentence while hiding unclassified prose elsewhere in the draft.

Multiple factual claims may refer to the same sentence when one sentence contains multiple assertions.

---

## Bounded stylistic language

Stylistic language is permitted only when deterministic structural checks find no obvious factual assertion.

The initial bounded guard rejects stylistic sentences containing signals such as:

- death/killing;
- attacks/injuries;
- Stratum/Sector/Floor;
- party/alliance/leadership;
- betrayal/rescue/survival/retreat;
- ownership/items/Relics;
- boss/victory/defeat;
- numeric claims;
- canonical-style IDs appearing as prose facts.

Examples of safe style:

```text
The silence felt heavier afterward.
The moment lingered.
```

Examples that may not be hidden as style:

```text
He died alone in Sector alpha.
She carried the Relic into Stratum 3.
```

Those must be represented as factual claims and independently supported.

---

## Optional local auxiliary assessment

A smaller local model may optionally assist with sentence extraction/classification.

Its assessment may classify a sentence as:

```text
factual
stylistic
ambiguous
contradiction
```

The assessment is advisory only.

Rules:

- `contradiction` may reject a draft;
- `ambiguous` may downgrade a deterministic pass to `NEEDS_REVIEW`;
- finding an unmanifested factual sentence may reject a draft;
- a model saying `stylistic` cannot override a deterministic factual contradiction;
- a model can never turn a rejected deterministic claim into `REVIEW_READY`.

No model is required for the deterministic path.

---

## Verification states

### `REVIEW_READY`

All required sentences are covered, every factual claim is exactly supported, every stylistic sentence passes bounded style rules, and no auxiliary ambiguity/contradiction remains.

### `NEEDS_REVIEW`

Deterministic checks pass, but optional auxiliary evidence flags ambiguity requiring human or later automated review.

### `REJECTED`

Any deterministic contradiction, unsupported claim, unsafe stylistic sentence, missing required sentence coverage, or auxiliary contradiction causes rejection.

Verification failure affects only presentation/media state.

---

## Idempotency and restart behavior

Draft, claim, manifest, and verification identities are deterministic.

Consequences:

- duplicate draft ingestion does not create another draft;
- duplicate manifest ingestion does not create another manifest;
- duplicate verification does not create another result;
- reopening the same media SQLite database preserves exact semantic snapshots;
- repeated verification after restart returns the same result;
- independent equivalent proof runs produce equivalent digests.

---

## Focused validation

The focused suite must prove:

1. exact allowed factual claims plus bounded style can become `REVIEW_READY`;
2. a wrong Stratum is a deterministic contradiction;
3. invented item ownership is rejected as unsupported;
4. factual death/location language cannot be hidden as stylistic text;
5. every sentence must be covered by the manifest;
6. an auxiliary model cannot override a deterministic contradiction;
7. auxiliary ambiguity can only downgrade a valid result to `NEEDS_REVIEW`;
8. narrative tables exist only in the media database and canonical state/Ledger remain unchanged;
9. file-backed SQLite restart preserves exact draft/manifest/verification identities.

---

## Deterministic proof

The acceptance proof must create and preserve all of these outcomes:

```text
exact allowed claim + safe style -> REVIEW_READY
wrong Stratum claim -> REJECTED
factual sentence disguised as style -> REJECTED
valid claim + auxiliary ambiguity -> NEEDS_REVIEW
```

It must additionally prove:

- local writer provenance can be recorded without requiring a local model to be installed for verification;
- no provider execution occurs;
- no media generation job is enqueued;
- no cloud or paid provider is required;
- writer self-certification is never trusted;
- auxiliary assessments cannot override deterministic checks;
- media SQLite reopen is exact;
- duplicate verification is idempotent;
- canonical state, fingerprint, history IDs, and Ledger rows are unchanged;
- two independent proof runs produce identical semantic digests.

---

## Acceptance gate

Local acceptance requires the validator to end with exactly:

```text
[30.5.5] PASS
```

Until that line is observed, 30.5.5 is not accepted.

---

## On acceptance

Accepted 30.5.5 means Crawl may safely retain generated Chronicle prose as presentation data and distinguish verified review-ready narrative from ambiguous or false narrative without granting the writer, verifier model, or media pipeline canonical authority.

The next frozen slice is:

**30.5.6 — Presentation Identity System**
