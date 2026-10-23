# Underreach v0.10 — Phase 30.5 Slice 6

## Presentation Identity System

Status: implementation candidate; local validation required before acceptance.

Protocol: `presentation_identity.v1`

Implementation version: `30.5.6`

Accepted baseline: 30.5.5 — Narrative Claim Manifest & Fact Verification.

Next canonical slice on acceptance: **30.5.7 — Headless Local Image Production**.

---

## Purpose

30.5.6 establishes a durable presentation-only visual identity layer for media-relevant Delvers.

The slice solves identity continuity before image generation begins:

```text
Deterministic Crawl Simulation
        ↓
Canonical Ledger / state
        ↓
30.5.1 MediaEnvelope
        ↓
30.5.2 Media SQLite
        ↓
30.5.3 Highlight / Story Arc
        ↓
30.5.4 DelverProfile / Chronicle
        ↓
30.5.5 Verified Narrative
        ↓
30.5.6 Presentation Identity
        ↓
30.5.7 Local Image Production
```

30.5.6 does **not** generate pixels.

It defines deterministic identity versions, reference slots, equipment-reference revisions, and current media bindings so that later image workers can generate consistent character art without promoting generated appearance into canonical gameplay truth.

---

## Authority boundary

The deterministic simulation remains the only authority for gameplay and canonical identity facts.

30.5.6 may write only to media-owned tables.

It may not mutate:

- Delver health,
- injuries,
- inventory,
- equipped items,
- party/alliance state,
- relationships or memories,
- movement,
- combat,
- progression,
- canonical character identity,
- canonical Ledger history.

Generated or planned media appearance is never evidence that the canonical Delver has that face, body, hairstyle, scars, skin details, clothing details, or other visual features.

Snapshot invariants:

```text
authoritative = false
canonical_owner = deterministic_simulation
presentation_can_mutate_simulation = false
canonical_identity_fields_added = false
generated_visuals_used = false
provider_invocation_used = false
generation_jobs_created = false
unreal_dependency = false
cloud_api_required = false
paid_provider_required = false
```

---

## Media relevance gate

Presentation identities are allocated only after a Delver becomes media-relevant.

Initial deterministic relevance rule:

```text
DelverProfile has at least one Chronicle chapter
OR
DelverProfile Chronicle is terminally closed
```

A plain profile created from unpromoted background history does not automatically receive a presentation identity.

This prevents spending future image-generation work on every simulation participant before they matter to the public presentation layer.

---

## Three-record architecture

30.5.6 separates identity continuity from equipment continuity.

### 1. Immutable PresentationIdentity version

One identity version represents one stable presentation interpretation of a Delver under one visual/rendering profile.

It stores:

- profile/Crawl/Delver identity,
- integer presentation identity version,
- visual profile,
- renderer/capability profile,
- deterministic presentation seed,
- creation profile digest,
- creation envelope/event provenance,
- six static reference slots,
- empty presentation-trait map in this slice,
- explicit noncanonical authority flags.

The identity record is immutable after creation.

### 2. Immutable EquipmentReferenceRevision

Visible equipment is allowed to change without changing the underlying face/body identity.

Each unique normalized visible-equipment digest for one identity version gets one immutable equipment-reference revision.

It stores:

- identity/profile/Crawl/Delver identity,
- revision index,
- normalized visible equipment snapshot,
- equipment digest,
- source profile/envelope/event provenance,
- deterministic current-equipment reference slot.

Returning to an equipment digest already seen under the same identity version reuses the existing revision instead of creating another one.

### 3. Mutable PresentationIdentityBinding

One media-only binding per Delver profile points to:

```text
active_identity_id
current_equipment_revision_id
identity_version_count
```

The binding is presentation state only.

It does not rewrite the immutable identity or equipment-revision records.

---

## Identity versioning

Identity versions start at 1 and increase monotonically for one profile.

The initial visual/renderer profiles are policy-controlled.

Calling `ensure_identity` with the same visual and renderer profile returns the current identity exactly.

Changing either visual profile or renderer profile creates a new identity version.

This is how Crawl supports future image-model changes without changing canonical character identity:

```text
presentation identity v1
    renderer profile A

presentation identity v2
    renderer profile B
```

Both versions belong to the same canonical Delver.

Neither version becomes canonical.

The active binding points at the newest requested presentation version while older identity versions remain durable for provenance and already-generated media.

---

## Deterministic presentation seed

Every identity version receives a deterministic seed derived from stable media identity inputs.

The seed is presentation-only.

It must be reproducible across equivalent independent runs and restart-safe.

Changing the presentation identity version changes the seed.

Equipment-only changes do not change the identity seed because they do not create a new identity version.

---

## Static reference slots

Every identity version creates exactly six static pending reference slots:

```text
portrait
face_reference
three_quarter
full_body_front
full_body_side
combat_reference
```

Each slot has:

- deterministic reference ID,
- deterministic relative output path,
- kind,
- pending-generation status,
- no artifact ID,
- `generated = false`.

30.5.6 does not create files at those paths.

30.5.7 will own actual image generation and artifact binding.

---

## Planned media layout

Reference paths are deterministic and versioned, for example:

```text
media/
  delvers/
    <delver_id>/
      presentation_identity.v1/
        v001/
          portrait.png
          face-reference.png
          three-quarter.png
          full-body-front.png
          full-body-side.png
          combat-reference.png
          current-equipment-reference-<equipment-digest-prefix>.png
```

The path is a media plan, not proof that a generated artifact exists.

---

## Equipment-reference revisioning

30.5.6 derives visible equipment only from the accepted `DelverProfile.notable_equipment` structure.

The equipment snapshot is normalized by item ID before hashing.

Rules:

1. First identity sync creates one equipment revision, including an empty-equipment revision if no notable equipment is visible.
2. Reprocessing an unchanged profile reuses the same equipment revision.
3. A meaningful visible equipment change creates a new revision under the same identity version.
4. Equipment changes alone do **not** create a new face/body identity version.
5. Returning to a previous equipment digest reuses the old revision.
6. Creating a new identity version creates its own equipment-reference revision, even if the equipment happens to match an older presentation identity version.

This prevents unnecessary re-generation while keeping each identity version self-contained.

---

## Presentation traits

30.5.6 intentionally does not invent facial/body attributes.

Therefore:

```text
presentation_traits = {}
```

Later image generation may create noncanonical visual details, but those details must be stored as presentation state with generation provenance.

They may never silently write into canonical character DNA or simulation state.

---

## Provider boundary

30.5.6 stores renderer/capability profile names only as identity-version metadata.

It does not:

- invoke an image provider,
- check ComfyUI availability,
- load an image model,
- generate a prompt,
- generate an image,
- record provider execution,
- enqueue a generation job,
- spend money.

A renderer profile is not provider authorization.

Paid-provider policy remains owned by 30.5.2.

---

## Durable tables

30.5.6 adds three media-owned tables:

```text
media_presentation_identities
media_presentation_equipment_revisions
media_presentation_identity_bindings
```

They must exist only in the media database.

They must never appear in canonical Crawl persistence.

---

## Idempotency

Identity ID is deterministic from:

```text
crawl_id
delver_id
identity_version
visual_profile
renderer_profile
```

Equipment revision ID is deterministic from:

```text
identity_id
equipment_digest
```

Consequences:

- repeated identical sync does not duplicate records;
- restart/reopen does not duplicate records;
- already-seen equipment states are reusable;
- model/profile changes remain explicitly versioned;
- stable reference IDs survive restarts.

---

## Canonical safety proof

The acceptance proof must compare canonical state immediately before and after each presentation operation.

It must separately prove that:

1. first identity allocation does not change canonical state;
2. equipment-reference sync does not change canonical state;
3. renderer-profile version switch does not change canonical state.

Canonical equality includes:

- complete model state,
- simulation fingerprint,
- history event IDs,
- durable Ledger rows.

Canonical changes intentionally performed by the proof to create test source events are not attributed to the media layer.

---

## Focused validation

The focused test suite must prove:

1. media-relevant profile gets identity v1;
2. six static reference slots are deterministic and pending;
3. current-equipment reference exists separately;
4. generated visual/artifact fields remain absent;
5. repeat sync is idempotent;
6. renderer profile change creates identity v2;
7. renderer change does not mutate canonical state;
8. equipment change creates a new equipment revision without a new identity;
9. returning to a previous equipment state reuses its revision;
10. non-media-relevant profiles cannot allocate identity;
11. 30.5.6 tables are media-only;
12. SQLite restart preserves exact semantic state.

---

## Deterministic proof

The proof uses a real canonical important Relic so equipment context is not mocked.

Proof flow:

```text
canonical Relic acquired
    ↓
high-signal Chronicle profile
    ↓
presentation identity v1 + equipment revision 1
    ↓
canonical Relic dropped
    ↓
profile equipment update
    ↓
same presentation identity + equipment revision 2
    ↓
renderer profile switch
    ↓
presentation identity v2
    ↓
SQLite restart + repeat sync
```

The proof must show:

- two presentation identity versions;
- first identity receives two equipment revisions;
- equipment change does not change identity ID;
- renderer switch does change identity ID and seed;
- all reference slots remain pending generation;
- no presentation traits are invented;
- no provider executions;
- no media generation jobs;
- exact semantic snapshot after repeat;
- exact semantic snapshot after reopen;
- no canonical mutation during any presentation operation;
- deterministic proof reproduction across two independent runs.

---

## Acceptance gate

Local acceptance requires the PowerShell validator to end with exactly:

```text
[30.5.6] PASS
```

Until that line is observed, 30.5.6 is not accepted.

---

## On acceptance

Accepted 30.5.6 means Crawl has a restart-safe, deterministic visual continuity layer without generating media or converting generated appearance into canonical truth.

The next frozen development slice is:

**30.5.7 — Headless Local Image Production**

30.5.7 may materialize the pending reference slots using local image providers and the 30.5.2 durable job/router foundation, while preserving every authority boundary above.
