# UNDERREACH • PHASE 30.5.12 — UNATTENDED PROMOTION SOAK

Status: **Implementation slice — local acceptance required**

Phase: `"30.5"`

Protocol: `underreach.unattended-promotion-soak.v1`

Implementation: `30.5.12`

This is the Phase 30.5 capstone. It does not introduce a new gameplay authority or a new creative-authority shortcut. It composes the already accepted deterministic simulation and media systems into one unattended local-first production run and proves that the complete promotion path can reach human review without Unreal, cloud AI, paid APIs, or presentation feedback into canonical truth.

---

## 1. Purpose

One command must demonstrate this complete contract:

```text
Deterministic Underreach simulation
        ↓
20+ autonomous Delvers
        ↓
real canonical combat / social / progression Ledger history
        ↓
read-only MediaEnvelope export
        ↓
media-owned highlight / story arcs / profiles / Chronicles
        ↓
deterministically verified presentation prose
        ↓
presentation identity
        ↓
local still image production
        ↓
local narration + captions
        ↓
local FFmpeg 9:16 motion story
        ↓
durable REVIEW QUEUE
        ↓
static media website rebuild
```

The finished promotional MP4 stops at `review_status=pending` and `published=false`. No automatic publication is part of 30.5.12.

---

## 2. Immutable Authority Boundary

30.5.12 preserves the Phase 30.5 authority model:

- deterministic simulation owns canonical truth;
- accepted canonical/social services are the only systems allowed to mutate crawl truth;
- MediaEnvelope export is read-only;
- media SQLite is physically separate from canonical SQLite;
- generated prose is presentation-only;
- generated visual identity is presentation-only;
- generated image/audio/video is presentation-only;
- review-queue state is presentation-only;
- website output is presentation-only;
- website generation cannot query or mutate the canonical simulation;
- no presentation output may feed back into the simulation.

The soak snapshots canonical state before and after downstream media work and requires exact equality of:

- serialized canonical state;
- canonical fingerprint;
- history event IDs;
- history digest;
- Ledger digest;
- state digest.

The early bootstrap export is independently checked for no canonical mutation before the simulation continues.

---

## 3. Meaningful Canonical Soak

The default acceptance policy requires:

- at least **20 Delvers**;
- at least **3 Strata**;
- a bounded maximum simulation step count;
- at least **4 reinforced canonical promise-violation events** plus one evidence-backed canonical betrayal;
- at least one real combat event;
- at least one real floor/progression event;
- actual autonomous encounter resolution;
- completion of the unattended crawl.

The canonical run uses the accepted `BrainDrivenDescentService` plus accepted 30C group/social orchestration. It does not use a media model to choose gameplay actions.

### Required social history

The proof deterministically selects an ACTIVE, co-located Delver pair immediately after the accepted social stack is initialized and **before gameplay movement or combat can separate or eliminate either member**.

The canonical social proof then uses only already accepted authority layers:

```text
30C.3 recruit proposal
        ↓
30C.3 accepted recruitment response
        ↓
30C.4 form_from_accepted_recruitment
        ↓
shared active party
        ↓
4 × canonical PROMISE_VIOLATED events
        ↓
30C.2 memory / relationship processing
        ↓
reinforced negative source → target memory
        ↓
30C.5 propose betray_party
        ↓
30C.5 validate + execute evidence-backed BETRAYAL
```

The four promise violations are recorded with the promise violator first and the later betrayer second. Accepted 30C.2 direct-event semantics store the resulting negative memory on the affected party toward the actor, so the later betrayer accumulates the required source→target grievance evidence.

The betrayal uses the bounded canonical incentive:

```text
incentive_code = revenge
incentive_strength = 1.0
```

This is not a random betrayal roll and is not created by the media pipeline. The 30C.5 validator must accept the proposal from canonical relationship/memory evidence and the accepted conflict score must clear its threshold before execution.

The proof retains:

- `social_pair_ids`;
- `social_party_id`;
- `recruitment_offer_id`;
- `promise_violation_event_ids`;
- `betrayal_event_id`;
- `betrayal_conflict_score`;
- complete `social_event_ids`.

The featured media composite must include all four required promise violations and the canonical betrayal.

### Required combat history

The crawl must naturally produce accepted combat Ledger events such as:

- `COMBAT_STARTED`
- `COMBAT_ENDED`
- `CRAWLER_DAMAGED`
- `CRAWLER_INJURED`
- `ENEMY_DEFEATED`
- `CRAWLER_RETREATED` when a Delver withdraws from one encounter.

The proof does not manufacture combat purely for presentation.

For the featured promotional composite, only combat events whose actor IDs are entirely within the canonical Delver roster are eligible. Accepted combat records `COMBAT_STARTED` and `COMBAT_ENDED` with `actor_ids=crawler_ids`; enemy IDs remain in structured event data. Therefore those events provide real combat provenance and danger scoring without exposing enemies as media Delvers.

`CRAWLER_RETREATED` is retained as canonical encounter history but is **not** treated as a terminal biography event by 30.5.12. Accepted 30.5.4 interprets a `CRAWLER_RETREATED` envelope as terminal, while the combat system uses the same event name for an encounter-local withdrawal without ending canonical participation. Therefore encounter-retreat events are deliberately excluded from terminal Chronicle export. Only actual `CRAWLER_DIED` / `CRAWLER_ELIMINATED` events may enter the terminal-biography export path in this soak.

### Required progression history

The crawl must produce accepted progression evidence, including `FLOOR_COMPLETED`, `STRATUM_ADVANCED`, and/or accepted character/item progression events.

---

## 4. Media Export and Full Delver Directory

A bootstrap MediaEnvelope is exported from the canonical 30C.6 initialization event while the full roster is active. This makes the public media database aware of the full 20+ Delver roster without altering the simulation.

After canonical simulation finishes, the soak exports real social/combat/progression events and true terminal death/elimination events as media envelopes.

A composite high-value envelope contains only real canonical source event IDs and is scored by the accepted 30.5.3 deterministic highlight system.

### Delver-only featured provenance

`MediaEnvelope.delver_ids` is derived from canonical event actor IDs. Some legitimate combat Ledger events include enemy actor IDs, so 30.5.12 must not blindly use every combat event in the featured composite.

The featured composite therefore enforces all of the following before media registration:

- every selected source-event actor ID must belong to the canonical Delver roster;
- combat contribution is restricted to crawler-only canonical combat events;
- crawler/item progression events are accepted only when their actors are canonical Delvers;
- the exported composite is checked again after export;
- `composite_foreign_actor_ids` must be exactly empty.

If any non-Delver actor would be exposed as a media Delver, the soak fails instead of creating a false public profile.

### Deterministic 50-point highlight floor

30.5.12 does not rely on lucky loot, death, level-up, rarity, or seed-specific character significance to clear the Chronicle threshold.

The selected real canonical package must independently prove these accepted 30.5.3 score components:

```text
real crawler-only COMBAT_STARTED / COMBAT_ENDED  → danger >= 10
canonical BETRAYAL                              → social_stakes >= 20
4× reinforced PROMISE_VIOLATED memory           → continuity >= 15
real combat encounter context                   → visual_potential >= 5
                                                  --------------------
mandatory canonical floor                       = 50
```

Acceptance therefore requires:

```text
composite_highlight_floor = 50
components.danger >= 10
components.social_stakes >= 20
components.continuity >= 15
components.visual_potential >= 5
components.total >= 50
composite_highlight_score = components.total
```

Rarity, character significance, and other accepted score components may increase the result, but they are not needed to pass.

### Encounter retreat is not terminal biography state

The proof records canonical encounter retreats separately as `encounter_retreat_event_ids`. Events deliberately exported through the terminal biography path are recorded as `terminal_media_event_ids`.

Acceptance requires those sets to be disjoint. This protects the accepted 30.5.4 terminal-profile semantics without rewriting that accepted slice.

MediaEnvelope re-registration must remain idempotent.

---

## 5. Chronicle and Verification

The accepted 30.5.4 Chronicle/profile system consumes the registered media envelopes.

Acceptance requires:

- 20+ media-owned Delver profiles;
- at least one persisted highlight;
- at least one Chronicle chapter;
- canonical source event provenance retained by the featured chapter;
- zero foreign/non-Delver actor IDs in the featured composite;
- zero encounter-retreat event IDs in terminal media export;
- featured highlight score at or above the deterministic canonical 50-point floor.

### Acceptance writer

30.5.12 does **not** make an LLM installation a hard dependency.

The guaranteed local acceptance writer selects one `event_type` allowed fact from the featured Chronicle and emits one bounded sentence whose factual claim exactly matches that fact.

Writer metadata:

```text
provider_id: deterministic_allowed_fact_writer
local: true
paid: false
```

That draft is submitted to the accepted 30.5.5 claim-manifest verifier.

Acceptance requires:

```text
status = review_ready
deterministic_contradiction_count = 0
unsupported_claim_count = 0
```

This proves the fact-verification path end-to-end without pretending a generative model is installed. A later/local narrative provider can replace the acceptance writer while retaining the same verification boundary.

---

## 6. Presentation Identity and Local Images

The featured Delver receives the accepted `presentation_identity.v1` identity and equipment revision.

The guaranteed local image backend is the accepted deterministic PNG provider. It is an acceptance/fallback renderer, not the intended final art-quality backend.

The soak creates:

1. one portrait reference;
2. one Chronicle scene still.

Both retain canonical-event/media provenance and are presentation-only.

Production-quality ComfyUI or another local image engine remains replaceable behind the accepted image-provider contract.

---

## 7. Required Failure / Restart Injection

30.5.12 deliberately interrupts the scene-image worker after the durable scene job is leased.

The process then reconstructs the media stack from the same file-backed SQLite database and calls the accepted durable-job recovery path.

Acceptance requires:

```text
recovered jobs = 1
same scene job ID = true
scene completion attempt = 2
```

After completion, the exact same scene is re-enqueued with the same priority. It must resolve to the same completed durable job and leave the image snapshot unchanged.

This is the mandatory media-worker failure/restart proof for the capstone.

---

## 8. Local Narration and Captions

The accepted 30.5.8 system consumes only the REVIEW_READY narrative package.

The guaranteed local path produces:

- deterministic SRT captions;
- deterministic WebVTT captions;
- package metadata/provenance;
- local deterministic PCM WAV narration;
- WAV sidecar provenance.

Caption-only readiness exists before voice synthesis and remains the fallback if a production TTS provider is unavailable.

The capstone acceptance path also proves that the bundled local voice backend can complete successfully.

No speech-recognition pass is used to reconstruct captions.

---

## 9. Guaranteed Vertical Motion Story

The accepted 30.5.9 FFmpeg path is the guaranteed production tier.

The capstone uses a reduced acceptance resolution for runtime cost while retaining exact production semantics:

```text
270 × 480
12 fps
exact 9:16
H.264 / libx264
burned verified captions
local narration audio
```

Production defaults in the accepted motion-story system remain 1080 × 1920 / 30 fps.

The soak requires a real file-backed MP4 and verifies its artifact digest.

Local AI video enhancement remains optional. It is **not** a hard acceptance dependency. The accepted 30.5.10 scheduler and fallback contract remains intact and is covered by its existing regression suite.

---

## 10. Durable Review Queue

30.5.12 introduces only a media-owned review-queue package:

```text
underreach.review-queue.build
```

Schema:

```text
underreach.review-queue.v1
```

The review queue receives the finished motion-story MP4 after that motion-story job completes.

Each review item stores:

- deterministic queue item ID;
- MP4 artifact ID;
- source motion-story job ID;
- story ID;
- relative URI;
- MP4 digest;
- source canonical event IDs;
- `review_status=pending`;
- `published=false`;
- `review_ready=true`.

Rules:

- no automatic approval;
- no automatic publication;
- no canonical authority;
- no simulation writeback;
- reaching review requires no human intervention;
- publication still requires a human decision.

Re-enqueuing the exact same completed review item must reuse the completed durable job.

---

## 11. Static Website

After the review queue is ready, the accepted 30.5.11 static site is rebuilt from media-owned state only.

Acceptance requires:

- 20+ Delver profiles visible to the media website generator;
- at least one verified Chronicle narrative;
- at least one highlight;
- successful static build;
- no live database requirement after build.

The pending review MP4 must **not** appear as a published public video. This is intentional and protects the review boundary.

---

## 12. Provider / Cost Contract

Required acceptance providers are local/free:

```text
image: local_deterministic_png
voice: local_deterministic_wav
editor: local_ffmpeg
```

The acceptance result scans all media provider executions and requires:

```text
actual paid execution count = 0
non-local provider IDs = []
```

An API key alone never authorizes spending. Paid/video-generation providers are not required to close Phase 30.5.

---

## 13. Mandatory Zeroes

The final proof contains explicit booleans and all must be `true`:

```text
zero_unreal_calls
zero_required_cloud_api_calls
zero_required_paid_ai_dependencies
zero_generated_media_mutation_of_canonical_truth
zero_human_intervention_before_review
zero_automatic_paid_escalation
```

Any failed mandatory zero fails the slice.

---

## 14. Reproducibility

The local validator runs the full proof twice from independent clean runtime directories using the same seed.

It requires equality of at least:

- overall semantic result digest;
- final canonical state digest;
- final canonical Ledger digest;
- media semantic snapshot digest;
- final promotional MP4 digest;
- review-queue manifest digest;
- static website build ID.

Wall-clock timestamps and SQLite implementation details are not part of the semantic proof identity.

The proof also retains and validates:

- social pair, recruitment offer, and canonical party IDs;
- four reinforced promise-violation event IDs;
- evidence-backed betrayal event ID and accepted conflict score;
- exact inclusion of the promise/betrayal chain in the featured composite;
- explicit highlight component scores and the 50-point floor;
- `composite_foreign_actor_ids == []`;
- `encounter_retreat_event_ids` disjoint from `terminal_media_event_ids`.

Reproducibility therefore cannot hide a social-authority shortcut, actor-classification leak, score-luck dependency, or retreat-semantics error.

---

## 15. Files

Production:

```text
src/livingworld/underreach_unattended_promotion_soak.py
```

Focused tests:

```text
tests/test_underreach_30_5_12_unattended_promotion_soak.py
```

Deterministic proof generator / one-command soak entrypoint:

```text
scripts/generate-underreach-unattended-promotion-soak-proof.py
```

Local validation gate:

```text
scripts/run-underreach-unattended-promotion-soak-validation.ps1
```

Frozen contract:

```text
docs/V0_10_SLICE30_5_12_UNATTENDED_PROMOTION_SOAK.md
```

---

## 16. Acceptance Command

From the local repository:

```powershell
.\scripts\run-underreach-unattended-promotion-soak-validation.ps1
```

The final gate is:

```text
[30.5.12] PASS
```

The proof is written to:

```text
validation\underreach-30_5_12\unattended-promotion-soak-proof.json
```

The proof runtime also contains the real media workspace, finished MP4, review-queue JSON, and generated static website.

---

## 17. Final Phase 30.5 Acceptance Statement

30.5.12 is accepted only when local validation proves that one unattended local-first command can:

1. run a meaningful 20+ Delver Underreach crawl;
2. generate real canonical combat/social/progression history, including an accepted-service recruitment/party/promise/betrayal chain;
3. produce a featured highlight whose real canonical facts independently guarantee the 50-point Chronicle threshold;
4. export canonical history without mutation, actor-classification leakage, or false terminal retreat state;
5. build media profiles/Chronicles/highlights;
6. verify narrative factual claims;
7. create presentation identity and local stills;
8. survive an injected media-worker crash/restart;
9. create local captions/narration;
10. create a real vertical FFmpeg MP4;
11. place that MP4 in pending human review;
12. rebuild the static media website;
13. do all of the above with every mandatory zero intact.

After this slice is accepted, **Phase 30.5 is complete**.

The next canonical development phase is:

```text
Phase 31 — Dialogue / Commentary
```

Dialogue remains outside Phase 30.5 and must not be introduced by this soak.
