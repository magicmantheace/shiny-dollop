# Crawl v0.10 — Slice 30.5.7 Headless Local Image Production

## Status

Implementation slice: **30.5.7 — Headless Local Image Production**

Phase: `"30.5"` (string, never floating point)

Base: accepted **30.5.6 — Presentation Identity System**.

Protocol: `underreach.headless-image-production.v1`

This slice is downstream presentation infrastructure only. It does not gain gameplay authority.

---

# 1. Purpose

30.5.7 is the first Phase 30.5 slice that actually invokes an executable image provider and writes image files.

It consumes accepted media-owned state from:

- 30.5.1 `MediaEnvelope`,
- 30.5.2 durable media jobs / attempts / artifacts / provider routing,
- 30.5.4 Delver profiles and Chronicle chapters,
- 30.5.6 `presentation_identity.v1` identity and equipment-reference revisions.

It produces:

- deterministic image-production specifications,
- durable image jobs,
- provider execution records,
- real PNG artifacts,
- deterministic JSON sidecars,
- restart-safe retries,
- scene/reference provenance.

No generated image is canonical truth.

---

# 2. Authority Boundary

Frozen invariants:

```text
Deterministic Crawl Simulation / Canonical Ledger
        |
        | read-only export
        v
MediaEnvelope / Chronicle / Presentation Identity
        |
        v
30.5.7 Image Job + Provider Router
        |
        v
Headless Image Provider
        |
        v
PNG + JSON Sidecar + Media Artifact Records
```

30.5.7 MUST NOT:

- open or mutate the canonical simulation database,
- append or alter canonical Ledger events,
- change health, survival, inventory, relationships, parties, alliances, combat, movement, progression, or social memory,
- feed provider output back into canonical gameplay,
- invoke Unreal,
- require a GUI,
- require cloud AI,
- require a paid API,
- silently turn a failed local request into a billable request.

Every image spec, artifact, and sidecar declares presentation-only authority.

---

# 3. Durable Job Contract

30.5.7 reuses the accepted 30.5.2 `MediaPersistence` queue. It does not introduce a parallel job system.

Job type:

```text
underreach.image.generate
```

Each job persists a frozen `ImageProductionSpec` containing at minimum:

- protocol / implementation / phase,
- deterministic `spec_id`,
- image purpose,
- Crawl ID,
- profile / Delver ID,
- presentation identity ID/version,
- equipment revision when applicable,
- source MediaEnvelope ID,
- canonical source event IDs,
- presentation reference ID/kind when applicable,
- Chronicle chapter ID for scene stills,
- prior generated reference artifact IDs when supplied,
- deterministic image seed,
- bounded width / height,
- prompt-template version,
- deterministic prompt / negative prompt,
- provider capability request,
- policy digest,
- authority flags.

The 30.5.2 durable job identity remains the restart/idempotency owner.

Re-enqueuing an identical completed image spec MUST reuse the same durable job rather than produce another generation.

---

# 4. Image Purposes

30.5.7 freezes three purposes:

```text
identity_reference
equipment_reference
scene_still
```

## Identity references

Static 30.5.6 reference kinds such as portrait, face reference, three-quarter, full-body, and combat reference are coupled to the presentation identity only.

They MUST NOT be invalidated merely because visible equipment changes.

This preserves the accepted 30.5.6 separation:

```text
face/body presentation identity != current equipment revision
```

## Equipment reference

`current_equipment_reference` is explicitly tied to the accepted active equipment-reference revision.

A meaningful canonical-backed equipment change therefore produces a different equipment image spec while preserving the same presentation identity.

## Scene still

A scene still is tied to:

- an exact persisted Chronicle chapter,
- the active presentation identity,
- the current equipment revision,
- source MediaEnvelope / canonical event provenance,
- optional already-generated image artifact references.

The scene prompt uses structured Chronicle trigger/title codes rather than unverified generated prose.

---

# 5. Provider Router & Resource Policy

30.5.7 uses the accepted 30.5.2 `MediaProviderRouter`.

Default image policy:

```text
local_required = true
paid_allowed = false
explicit_paid_authorization = false
max_vram_mb = 12288
max_attempts = 2
```

Image requests require:

- provider kind `image`,
- `headless_image` capability,
- `png_output` capability,
- deterministic seed support,
- requested resolution support,
- configured VRAM bound.

A provider requiring more than 12 GB VRAM is ineligible under the default target-PC policy even if it advertises better quality.

Paid routing still requires every 30.5.2 paid-provider gate:

- global paid providers enabled,
- request permits paid provider,
- explicit authorization when required,
- remote/cloud allowed,
- positive daily paid budget,
- estimated cost inside remaining budget.

An API key by itself remains insufficient authorization.

---

# 6. Executable Provider Contract

30.5.7 introduces an executable `HeadlessImageProvider` contract paired with 30.5.2 `ProviderDescriptor` metadata.

A provider receives an immutable `ImageRenderRequest` and returns an `ImageRenderOutput`.

Provider implementations are replaceable presentation backends.

The architecture does not hard-code a vendor or model name.

A future/current local ComfyUI adapter can therefore register its descriptor and executor without changing the image-spec, MediaEnvelope, Chronicle, or simulation architecture.

---

# 7. Guaranteed Zero-Dependency Local Acceptance Renderer

30.5.7 includes `DeterministicLocalPngProvider`.

It is deliberately a **zero-dependency headless acceptance/fallback renderer**, not the intended production-quality art model.

Properties:

- local,
- offline,
- free,
- deterministic seed support,
- no GUI,
- no Unreal,
- no network,
- no GPU requirement,
- produces a valid RGB PNG through the Python standard library,
- deterministic bytes for the same provider/spec/reference inputs.

Its purpose is to guarantee that the complete production pipeline can always prove:

- executable provider invocation,
- real file production,
- hashing,
- durable artifacts,
- sidecar provenance,
- retry/restart behavior,
- routing/resource policy,

without making acceptance dependent on whether a large local diffusion model is installed on the validation machine.

Production-quality local engines remain providers behind the same contract.

---

# 8. File-Backed Artifact Contract

Successful image execution writes:

```text
<output_root>/
  images/
    <crawl_id>/
      <delver_id>/
        v###/
          <purpose>-<spec_id>.png
          <purpose>-<spec_id>.png.json
```

The media database stores relative URIs, not machine-specific absolute output roots.

This preserves semantic proof reproducibility across working directories.

The PNG artifact records:

- content SHA-256,
- durable media job ID,
- spec ID,
- presentation identity ID,
- equipment revision when applicable,
- reference ID or Chronicle chapter ID,
- source MediaEnvelope / canonical event provenance,
- provider ID,
- presentation-only flag.

The sidecar records the same production provenance plus:

- attempt ID,
- deterministic seed,
- resolution,
- prompt-template version,
- provider local/paid flags,
- provider metadata,
- PNG SHA-256.

Both PNG and sidecar are durable media artifacts.

---

# 9. Provider Execution & Failure

A successful provider attempt records one 30.5.2 provider-execution record and completes the durable media job.

A provider exception:

- records a failed provider execution,
- fails the active attempt,
- moves the job to `retry` while attempts remain,
- moves the job to `failed` when the bounded attempt count is exhausted,
- writes no successful artifact,
- never affects canonical simulation advancement or truth.

A missing executable provider for an already-routed job is a retryable media-only failure.

---

# 10. Restart Safety

A machine/process restart may leave a durable image job in `running`.

30.5.7 relies on the accepted 30.5.2 restart recovery contract:

```text
RUNNING attempt
  -> interrupted
same durable job
  -> RETRY
next deterministic attempt
  -> provider execution
  -> COMPLETED or bounded failure
```

The proof requires the interrupted image job to finish under the same `job_id` on attempt 2.

No duplicate export or image job is created.

---

# 11. Deterministic Prompt Boundary

30.5.7 prompts are structured presentation instructions, not canonical narrative.

Static identity prompts explicitly avoid asserting:

- current equipment,
- injury,
- status,
- gameplay outcome.

Equipment prompts use only the active canonical-backed equipment-reference revision.

Scene prompts use:

- stable Delver ID,
- presentation visual profile,
- structured Chronicle title code,
- structured trigger codes,
- current canonical-backed equipment context.

They instruct providers not to add a new gameplay fact.

Generated facial/body details and scene staging remain noncanonical even when visually consistent.

---

# 12. Focused Acceptance Tests

The focused suite freezes at least these behaviors:

1. static reference specs are deterministic and equipment-independent,
2. the default local provider writes a real PNG + JSON sidecar,
3. generated artifacts retain provider/canonical provenance,
4. image execution does not mutate canonical state or Ledger truth,
5. re-enqueuing a completed identical reference reuses the same job/artifacts,
6. equipment changes alter equipment image specs but not static portrait specs,
7. a 16 GB provider is rejected under the default 12 GB policy,
8. paid remote routing is blocked by default,
9. paid remote routing succeeds only when every explicit paid gate is enabled,
10. a file-backed interrupted image job resumes under the same durable job ID,
11. scene stills retain exact Chronicle and prior-reference provenance,
12. provider failure retries and then fails without artifacts or canonical mutation.

---

# 13. Deterministic Proof

Proof generator:

```text
scripts/generate-underreach-headless-local-image-production-proof.py
```

Proof protocol:

```text
underreach.headless-local-image-production-proof.v1
```

The proof uses:

- a real accepted canonical Underreach stack,
- a real Relic obtained through the survival-aware cache path,
- a real 30.5.1 MediaEnvelope,
- a real 30.5.3 highlight,
- a real 30.5.4 Chronicle chapter/profile,
- a real accepted 30.5.6 presentation identity/equipment revision,
- a file-backed media SQLite database,
- executable local image jobs,
- real PNG and JSON files,
- an injected worker-restart boundary,
- deterministic routing probes.

Expected semantic totals:

```text
image jobs = 4
PNG artifacts = 4
JSON sidecars = 4
media artifacts total = 8
provider executions = 4
restart recovered jobs = 1
restart final attempt_count = 2
```

The four completed image jobs are:

1. portrait reference,
2. current-equipment reference,
3. Chronicle scene still,
4. face-reference restart probe.

The proof also requires:

- completed portrait re-enqueue reuses the original job,
- every output file exists,
- every image has a PNG signature,
- all acceptance executions use the local deterministic provider,
- the 16 GB routing probe is rejected under the 12 GB cap,
- paid provider is blocked without global permission,
- paid provider can be selected only when all explicit gates are enabled,
- canonical state/fingerprint/history/Ledger are unchanged during image production.

Two independent proof databases with the same seed must produce equal semantic proof/media digests.

---

# 14. One-Command Local Gate

Validator:

```powershell
.\scripts\run-underreach-headless-local-image-production-validation.ps1
```

It runs:

1. accepted 30A.1 through 30.5.6 regressions,
2. focused 30.5.7 tests,
3. deterministic file-backed proof twice,
4. exact proof assertions,
5. full repository pytest regression suite.

Acceptance ends exactly:

```text
[30.5.7] PASS
```

No GitHub Actions or GitHub Actions minutes are used.

---

# 15. Explicit Non-Goals

30.5.7 does not add:

- narration or TTS,
- captions,
- music or SFX,
- FFmpeg assembly,
- video diffusion,
- I2V scheduling,
- publishing,
- website/blog generation,
- canonical visual identity truth,
- simulation feedback from generated media.

Those remain downstream slices.

---

# 16. Next Slice

After explicit local acceptance of 30.5.7, the next frozen canonical slice is:

**30.5.8 — Narration, Captions & Audio**.
