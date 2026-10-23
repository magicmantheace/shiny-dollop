# Crawl v0.8 — Slices 25–27 Media Pipeline

## Status

Implementation branch: `agent/crawl-v0.8-slices25-27`

Base: cleaned and locally validated `main` at `5a9589d` (Slices 1–24).

No GitHub Actions dependency is introduced.

## Core rule

Simulation truth comes first. Commentary, edit decisions, render jobs, and optional AI dramatization are downstream presentation artifacts. None may mutate or replace canonical Crawl state.

## Slice 25 — Automated Commentary and Recaps

Implemented in `src/livingworld/commentary_system.py`.

The first implementation is deliberately deterministic rather than LLM-driven. It provides a safe baseline and a future adapter boundary.

Supported modes:

- play-by-play,
- analytical,
- documentary,
- crawler recap.

Every commentary line stores one or more canonical source event IDs. The generator only describes fields already present in `CrawlEvent` and does not infer motivation. `validate_commentary_grounding()` rejects scripts with missing/unknown event citations.

A future LLM may rewrite the grounded facts for style, but it must preserve citations and pass the same grounding contract before publication.

## Slice 26 — Automated Highlight Reels

Implemented in `src/livingworld/highlight_reels.py`.

The assembler connects:

1. a detected `StoryArc`,
2. canonical CrawlEvent history,
3. bounded pre/post replay context,
4. `AutomatedCameraDirector`,
5. grounded commentary,
6. a renderer-neutral edit timeline,
7. requested output profiles,
8. final Crawl fingerprint and source event IDs.

Default output profiles:

- `short_vertical`,
- `standard_horizontal`.

`deep_story` is also represented for longer future packages.

The render source uses an explicit canonical replay URI such as:

`replay://<crawl-id>?start_tick=<n>&end_tick=<n>&fingerprint=<sha>`

This is intentionally a render manifest, not a fabricated claim that an MP4 already exists. Actual Unreal rendering and media encoding remain downstream integration work.

`validate_highlight_package()` verifies that package and commentary evidence resolve to authoritative event IDs and that the package is based on canonical replay.

## Slice 27 — Optional AI Video Dramatization

Implemented in `src/livingworld/ai_dramatization.py`.

The planner creates provider-neutral generation jobs. It does **not** call a video provider.

Every job stores:

- highlight ID,
- crawl ID,
- exact canonical source event IDs,
- per-scene source event IDs,
- generated scene prompt,
- provider/model metadata when supplied,
- explicit `canonical = false`,
- relationship `optional_stylized_interpretation`.

Scene prompts explicitly instruct a future generator not to change participants, ordering, outcomes, deaths, injuries, items, or floor results.

`validate_dramatization_job()` rejects jobs that claim canonical status or reference events outside the authoritative set.

## Acceptance demo

`python -m livingworld.crawl_media_demo`

The demo runs a normal headless crawl, then inserts a deterministic NEAR_DEATH/RESCUE acceptance fixture through the canonical lifecycle event path so every seed exercises the media pipeline.

It validates:

- crawl completion,
- rescue story detection,
- nonempty grounded commentary,
- commentary citation validity,
- deterministic commentary,
- valid highlight package,
- deterministic highlight package digest,
- replay window containing the story,
- nonempty camera plan,
- nonempty edit timeline,
- horizontal + vertical output requests,
- fully traceable dramatization job,
- dramatization marked non-canonical,
- presentation pipeline leaves Crawl fingerprint unchanged.

## Local validation

From repository root:

```powershell
.\scripts\run-crawl-slices25-27-validation.ps1
```

Small checkpoint:

```powershell
.\scripts\run-crawl-slices25-27-validation.ps1 -Crawlers 25 -Floors 2 -MaxSteps 5000 -SkipFullRegression
```

Formal gate:

```powershell
.\scripts\run-crawl-slices25-27-validation.ps1 -Crawlers 100 -Floors 3 -MaxSteps 25000
```

Report:

`validation\crawl-v0.8-slices25-27-media.json`

## Carry-forward work

### COMMENTARY-001 — LLM style adapter

Add an optional provider/local-model adapter that receives only a grounded fact bundle, returns styled commentary, and must pass citation/fact validation before use.

### MEDIA-001 — Actual renderer/encoder integration

Connect highlight render manifests to Unreal replay rendering, audio/subtitle generation, media encoding, thumbnail generation, and persistent media storage.

### MEDIA-002 — Publication/review queue

Add draft/review/approved/rejected/published states, duplicate suppression across output formats, render cache reuse, and publication policy.

### DRAMA-001 — Video provider adapters

Add optional provider adapters only after storage, cost controls, provenance, and output labeling are in place. Canonical replay must remain visually and internally distinguishable from AI dramatization.

### REPLAY-001

Periodic exact state checkpoints remain future work. Batch 7 consumes the existing canonical event-ledger replay plus final-state fingerprint contract.
