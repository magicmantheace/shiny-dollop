# Crawl v0.10 — Slice 30.5.1 Canonical Media Event Export

## Status

**Canonical phase:** `30.5` — Headless Chronicle & Promotion System

**Slice:** `30.5.1` — Canonical Media Event Export

**Accepted simulation baseline:** Phase 30C complete at `729570fb6b8d517a3976cbc660b55059157f258e`.

**Canonical Phase 30.5 roadmap commit:** `d9a70aef3548352a38f2e612aa1212321e45914d`.

This slice implements only the read-only simulation-to-media export membrane.

---

# Purpose

Convert bounded canonical Ledger history plus relevant presentation-safe canonical context into deterministic immutable `MediaEnvelope` objects.

The exporter is a downstream reader only.

It must prove that media extraction itself cannot become a mutation path into canonical simulation truth.

---

# Protocol

```text
underreach.media-envelope.v1
```

Implementation version:

```text
30.5.1
```

Phase value is the string:

```text
30.5
```

It must not be represented as a floating-point version value.

---

# Authority Boundary

```text
Accepted 30C.6 Descent
        |
        v
Canonical Ledger / persisted CrawlEvent rows
        |
        | READ ONLY
        v
CanonicalMediaEventExporter
        |
        v
MediaEnvelope
```

30.5.1 may not:

- append a Ledger event,
- change `history_event_ids`,
- change a Crawl/Descent field,
- change canonical social state,
- change canonical social memory,
- change party/alliance state,
- change conflict state,
- change inventory or encounter state,
- write a media database,
- invoke an AI provider,
- invoke Unreal,
- generate prose,
- generate images,
- generate video,
- invoke paid APIs.

---

# MediaEnvelope Contract

Every envelope includes:

- schema/protocol,
- exporter implementation version,
- phase string,
- deterministic envelope ID,
- deterministic idempotency key,
- Descent ID and seed,
- export tick,
- Stratum/Sector context,
- ordered canonical source event IDs,
- ordered source event types,
- source-event payload digest,
- participating Delver IDs,
- bounded participant export-state context,
- bounded item context,
- bounded directed relationship/social-memory context,
- party/alliance context,
- encounter/combat context,
- deterministic semantic Ledger metadata,
- empty future visual-identity reference collection,
- normalized allowed facts,
- canonical simulation fingerprint,
- full canonical state digest,
- canonical history-prefix count/last-event/digest,
- context-truncation flag,
- explicit false authority/dependency flags,
- deterministic envelope digest.

---

# Canonical Source Ordering

Callers may request source IDs in any order.

The exporter must normalize them to the order of `Descent.history_event_ids` before loading or hashing them.

Duplicate source IDs are rejected.

Missing source IDs are rejected.

The first implementation supports bounded windows of up to 32 source events.

---

# Allowed Facts

30.5.1 creates normalized allowed facts only from the source canonical events.

Every source event contributes facts for:

- event type,
- tick,
- Stratum,
- Sector,
- actor IDs,
- canonical event summary,
- bounded recursively flattened structured `event.data` values including canonical state changes and semantic annotations.

Every allowed fact has:

- deterministic fact ID,
- scope,
- subject,
- predicate,
- value,
- canonical source event IDs.

The later 30.5.5 narrative verifier may consume this fact vocabulary. 30.5.1 does not generate or verify prose.

---

# Presentation-Safe Context

Context is captured **as of export time** and is not silently represented as event-time state.

Bounded context may include:

- participant status/current location/health/current party/current objective,
- current canonical injuries/status/equipment/progression,
- item ownership/provenance,
- directed 30C social relationship values among source actors,
- event-linked social memories touching source actors,
- party/alliance structures touching source actors,
- encounter state touching source actors/source locations.

If richer Character DNA does not exist in accepted canonical state, the exporter does not invent it.

`visual_identity_refs` therefore remains empty in this slice.

---

# Read-Only Proof

For every export call, the implementation captures before-state values and verifies after export:

1. canonical JSON state is byte-equivalent under canonical JSON serialization,
2. `Descent.fingerprint()` is unchanged,
3. `history_event_ids` is unchanged,
4. full canonical state digest is unchanged.

Formal proof additionally compares persisted Ledger rows before and after export.

No mutation event is emitted to prove read-only behavior; emitting one would itself violate the contract.

---

# Idempotency

The envelope idempotency key deterministically binds:

- protocol,
- exporter version,
- Descent ID,
- ordered source event IDs,
- source event payload digest,
- export-time canonical fingerprint,
- full canonical state digest,
- canonical history-prefix digest.

Equivalent export requests against equivalent canonical state produce identical envelope IDs, idempotency keys, facts, context, and digests.

Later 30.5.2 durable media persistence owns database-level duplicate suppression.

---

# Explicit Deferrals

The following are intentionally deferred:

- media SQLite database — 30.5.2,
- durable media jobs/retries — 30.5.2,
- provider router — 30.5.2,
- paid-provider policy execution — 30.5.2,
- highlight scoring — 30.5.3,
- Chronicle writing — 30.5.4,
- claim verification — 30.5.5,
- presentation identity generation — 30.5.6,
- image generation — 30.5.7,
- narration/audio — 30.5.8,
- FFmpeg motion-story production — 30.5.9,
- video enhancement/GPU scheduling — 30.5.10,
- website generation — 30.5.11,
- unattended promotion soak — 30.5.12,
- dialogue/commentary — Phase 31.

---

# Focused Test Requirements

Focused tests cover at minimum:

- deterministic repeat export,
- strict read-only canonical state equality,
- durable Ledger row equality before/after export,
- source-event request reordering into canonical Ledger order,
- social context and memory provenance,
- semantic Ledger context,
- normalized event/data allowed facts,
- missing-event rejection without mutation,
- duplicate-event rejection without mutation,
- independent identical-run reproducibility,
- explicit absence of provider/generation dependencies.

---

# Deterministic Proof Requirements

The generated proof must demonstrate:

- accepted Phase 30C stack initializes normally,
- at least two real canonical social source events exist,
- source requests supplied in reverse order normalize to canonical order,
- repeat envelope export is exactly equal,
- envelope digest is reproducible,
- idempotency key is reproducible,
- canonical fingerprint is unchanged,
- full canonical state digest is unchanged,
- canonical history digest is unchanged,
- persisted Ledger digest/count are unchanged,
- social relationship/memory context is present,
- allowed facts retain canonical source-event provenance,
- all presentation/cloud/paid authority flags remain false.

---

# Local Acceptance Gate

Run:

```powershell
.\scripts\run-underreach-media-event-export-validation.ps1
```

Acceptance requires terminal output:

```text
[30.5.1] PASS
```

The slice is not accepted until the local gate passes.

---

# Next Canonical Slice

After acceptance, the next frozen Phase 30.5 slice is exactly:

**30.5.2 — Media DB, Durable Queue & Provider Router**
