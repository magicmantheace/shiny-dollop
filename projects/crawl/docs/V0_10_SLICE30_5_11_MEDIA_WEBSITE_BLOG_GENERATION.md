# UNDERREACH • PHASE 30.5 • SLICE 30.5.11

## Media Website / Blog Generation

**Status:** implementation slice pending local acceptance

**Protocol:** `underreach.media-website-blog.v1`  
**Implementation version:** `30.5.11`  
**Phase identifier:** `"30.5"`

---

## 1. Purpose

30.5.11 turns accepted media-owned Underreach state into a portable static website/blog.

The website is downstream of the media database. It is not a simulation client and it is not allowed to query or mutate canonical Crawl truth.

The required direction remains:

```text
Canonical simulation / Ledger
        |
        v
read-only MediaEnvelope export
        |
        v
media SQLite + accepted presentation systems
        |
        v
30.5.11 static website build
        |
        v
portable HTML/CSS/media files
```

The finished static site must remain readable/servable after Python and SQLite are no longer running.

---

## 2. Primary acceptance target

The frozen Phase 30.5 roadmap defines 30.5.11 as:

> Regenerate public Delver/profile/Chronicle/highlight pages exclusively from media-owned data.

Primary acceptance requires:

- static pages rebuild deterministically from media SQLite state,
- no canonical simulation/database mutation path is opened or queried,
- Delver profile/status views are present,
- Chronicle entries are generated from accepted media-owned chapters,
- only verification-cleared prose is published,
- presentation imagery can be copied into the portable site,
- promotional video appears publicly only after explicit approval/publication state,
- no provider, Unreal process, network call, or live server is required for generation,
- restart and duplicate-build behavior remains durable and idempotent.

---

## 3. Authority boundary

30.5.11 is presentation-only.

The production module must report and preserve:

```text
authoritative = false
canonical_owner = deterministic_simulation
canonical_database_opened = false
live_simulation_query_used = false
presentation_can_mutate_simulation = false
provider_invocation_used = false
network_dependency = false
unreal_dependency = false
static_only = true
live_database_required_after_build = false
```

The module does not import `CrawlPersistence`, Crawl lifecycle/orchestration services, or other canonical mutation services.

The static site can express already accepted media state but cannot create new gameplay facts.

---

## 4. Media-owned inputs

30.5.11 consumes accepted media-layer state only.

### Delver profiles / Chronicles

From 30.5.4:

- `DelverProfile`
- `ChronicleChapter`
- ACTIVE / RETREATED / DEAD state
- current Stratum / Sector
- party / alliance IDs
- known allies and rivals
- notable equipment
- presentation identity reference
- Chronicle ordering and structured trigger metadata

### Narrative publication

From 30.5.5:

- `NarrativeDraft`
- `NarrativeVerification`

Only a verification with:

```text
status = REVIEW_READY
review_ready = true
```

may publish its draft prose.

`NEEDS_REVIEW` and `REJECTED` prose must never appear in public HTML.

If no verification-cleared prose exists, the chapter page degrades to structured Chronicle metadata and an explicit no-verified-prose state.

### Highlights

From 30.5.3:

- deterministic highlight records and scores may participate in the build's public semantic input digest.

### Presentation images

From 30.5.7:

- completed `identity_reference / portrait` PNG artifacts may be selected for profile pages.
- source file SHA-256 must still match the persisted media artifact before copying.

### Promotional video

From 30.5.9 / 30.5.10:

- completed motion-story MP4s,
- completed optional enhanced-shot MP4s.

By default a promotional MP4 is public only when both are true:

```text
review_status = approved
published = true
```

Pending review media is intentionally excluded.

---

## 5. Public semantic build identity

A website build is identified from public semantic inputs rather than the whole runtime queue.

The source digest includes normalized public-facing representations of:

- selected profiles,
- selected Chronicle chapters,
- selected REVIEW_READY narratives,
- persisted highlights in scope,
- selected profile portraits,
- selected approved/published promotional videos,
- crawl scope.

It intentionally excludes unrelated queue attempts or non-public pending media.

The deterministic build identity is derived from:

```text
source_digest
policy_digest
crawl scope
```

Unrelated media-worker activity therefore does not force a new public build.

A newly approved/published reel or changed public profile/Chronicle state does produce a new build identity.

---

## 6. Durable website job

Job type:

```text
underreach.website.generate
```

The build runs through accepted 30.5.2 `MediaPersistence`.

The durable job depends on the completed media jobs that own selected public binary assets.

The website worker:

1. leases the durable build job,
2. re-resolves current public media semantics,
3. rejects a stale plan if the source digest changed,
4. writes a temporary static tree,
5. copies selected media with digest verification,
6. renders deterministic HTML/CSS,
7. writes the static site manifest,
8. atomically installs the completed public tree,
9. records generated website artifacts in media SQLite,
10. completes the durable job.

A process restart may recover the same website job and retry it without creating a duplicate public build identity.

---

## 7. Portable static output

Default layout:

```text
<media-root>/
  website/
    <build-id>/
      public/
        index.html
        assets/
          site.css
          media/
            <artifact-id>.png
            <artifact-id>.mp4
        delvers/
          index.html
          <delver-slug>/
            index.html
        chronicles/
          index.html
          <chapter-slug>.html
        highlights/
          index.html
        status/
          active/
            index.html
          retreated/
            index.html
          dead/
            index.html
        site-manifest.json
```

The public output contains no required database connection string, API endpoint, or dynamic application runtime.

---

## 8. Delver directory and status views

The site includes:

- home directory summary,
- full Delver directory,
- ACTIVE filter/page,
- RETREATED filter/page,
- DEAD filter/page.

A profile page may show presentation-safe media fields already owned by 30.5.4:

- public name when present; otherwise stable Delver ID,
- status,
- current Stratum / Sector,
- current party,
- current alliance IDs,
- notable equipment,
- known allies,
- known rivals,
- selected presentation portrait,
- Chronicle links.

No new identity or biography facts are invented by the website formatter.

---

## 9. Chronicle publication boundary

Every media-owned Chronicle chapter receives a static page.

When REVIEW_READY prose exists:

- prose is copied verbatim from its persisted accepted draft,
- HTML escaping is applied,
- the page marks it as verification-cleared Chronicle prose.

When no REVIEW_READY prose exists:

- rejected/unreviewed draft text is not inspected into the public page,
- the page publishes only structured accepted chapter metadata,
- the page states that verification-cleared prose is not yet available.

This is a hard publication safety boundary, not a cosmetic preference.

---

## 10. Visual asset handling

30.5.11 does not link public pages directly to mutable media-workspace paths.

Selected assets are copied into the static build.

Before copying:

1. the source URI must be a safe relative media path,
2. the persisted file must exist,
3. its SHA-256 must match the media artifact digest.

The copied filename is based on the immutable media artifact ID.

The generated static site therefore remains portable even if it is served from a different directory or machine.

---

## 11. Promotional gallery publication policy

The public Highlights page consumes only explicitly public media.

Default public gate:

```text
job.status = completed
artifact.kind = video/mp4
artifact.review_status = approved
artifact.published = true
job type in:
  underreach.motion-story.assemble
  underreach.video-enhancement.shot
```

A pending review motion story or local video enhancement is not copied into the public tree and is not referenced in public HTML.

30.5.11 does not introduce a review UI or moderation workflow; it respects the media database's existing review/publication state.

---

## 12. Generated static manifest

Each build writes:

```text
site-manifest.json
```

The manifest includes deterministic build metadata such as:

- protocol/version/phase,
- build ID,
- source digest,
- policy digest,
- crawl scope,
- profile/chapter/verified-narrative counts,
- excluded unverified draft count,
- highlight count,
- portrait count,
- approved/published video count,
- page count,
- copied asset count,
- every static file path and SHA-256,
- authority/dependency zeroes.

Raw canonical event provenance does not need to be exposed on public pages. Canonical provenance remains retained in the media database and source artifacts.

---

## 13. Determinism and idempotency

For identical public semantic inputs and identical policy:

- build ID is identical,
- HTML bytes are identical,
- CSS bytes are identical,
- copied presentation bytes are identical,
- site manifest bytes are identical,
- static file digest is identical,
- durable website job ID is identical when enqueued with the same job priority,
- a completed re-enqueue does not duplicate website media state.

No wall-clock timestamp is embedded in the generated site.

---

## 14. Restart behavior

The acceptance proof deliberately leases the website job and simulates a process crash before generation.

Expected recovery:

```text
attempt 1 -> interrupted
MediaPersistence.recover_interrupted_jobs()
same website job -> retry
attempt 2 -> complete
```

Partial temporary output is discarded/rebuilt.

Recorded artifacts remain deterministic/idempotent if a prior attempt reached media-artifact recording before interruption.

---

## 15. Focused acceptance behaviors

The 30.5.11 focused suite covers at least:

1. public build planning uses only media-owned semantics,
2. three profile states appear in status views,
3. REVIEW_READY prose is published,
4. rejected prose cannot leak,
5. approved/published promo media is copied,
6. pending promo media cannot leak,
7. completed portrait media is copied portably,
8. the full static tree is generated,
9. identical completed re-enqueue is idempotent,
10. new approved public media changes build identity,
11. unverified chapters degrade to structured metadata,
12. file-backed restart recovers the same website job,
13. static output remains usable without a live database process.

---

## 16. Deterministic proof fixture

The proof fixture contains:

```text
3 Delver profiles:
  ACTIVE
  RETREATED
  DEAD

3 Chronicle chapters
1 persisted deterministic highlight
1 REVIEW_READY narrative draft
1 REJECTED narrative draft canary
1 completed portrait PNG
1 approved + published motion-story MP4
1 pending motion-story MP4 canary
```

Expected public website output:

```text
13 HTML pages
1 CSS file
1 copied portrait
1 copied published MP4
1 site manifest
= 17 recorded website artifacts/files
```

The rejected prose canary and pending-video canary must be completely absent from the public tree.

---

## 17. Validator

Run:

```powershell
.\scripts\run-underreach-media-website-blog-validation.ps1
```

The validator performs:

1. accepted 30A.1–30.5.10 regressions,
2. focused 30.5.11 tests,
3. production-source authority/dependency scan,
4. deterministic file-backed proof twice,
5. proof/source/static-file reproducibility checks,
6. REVIEW_READY publication gate checks,
7. rejected prose leak check,
8. pending media leak check,
9. status-page checks,
10. portable media-copy checks,
11. exact page/artifact count checks,
12. restart same-job/attempt-2 checks,
13. completed re-enqueue idempotency checks,
14. full repository `pytest -q` regression suite.

Acceptance ends with:

```text
[30.5.11] PASS
```

---

## 18. Explicit non-goals

30.5.11 does **not** add:

- a dynamic web server,
- public hosting/deployment automation,
- a CMS,
- user accounts,
- comments,
- analytics,
- external CDN uploads,
- canonical Crawl queries,
- canonical writeback,
- narrative generation,
- image generation,
- video generation,
- TTS,
- FFmpeg editing,
- AI/provider invocation,
- Unreal integration,
- a media review/moderation UI.

Those are outside this slice.

---

## 19. Acceptance boundary

30.5.11 is accepted only after the user's local validator reports:

```text
[30.5.11] PASS
```

Until then the branch is implemented but not accepted.

Nothing is merged automatically.

---

## 20. Next canonical slice

After 30.5.11 acceptance, the frozen Phase 30.5 roadmap continues with:

**30.5.12 — Unattended Promotion Soak**

That slice closes Phase 30.5 with one unattended local-first end-to-end run that produces Chronicle content and at least one review-ready vertical promotional artifact while surviving media-worker failure/restart and requiring no Unreal, cloud AI, paid API, or human intervention before review state.
