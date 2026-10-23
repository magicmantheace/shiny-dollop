# Crawl v0.7 — Slices 22–24 Presentation Intelligence

Batch 6 turns canonical Crawl state/history into deterministic presentation instructions without moving simulation authority out of the backend.

## Authority boundary

The following remain authoritative:

- Crawl state and participant state
- gameplay/combat outcomes
- item ownership
- parties and progression
- canonical `CrawlEvent` ledger
- replay digest/final-state fingerprint

The following are derived presentation products only:

- camera plans
- crawler channel payloads
- viewer focus requests
- story/highlight candidates

None of the Batch 6 presentation systems call gameplay mutation methods.

---

## Slice 22 — Automated Camera Director

Module: `livingworld.camera_director`

`AutomatedCameraDirector` consumes canonical events and produces deterministic `CameraPlan` data.

### Camera modes

- `crawler_follow`
- `over_the_shoulder`
- `combat_tracking`
- `wide_establishing`
- `overhead_tactical`
- `party_shot`
- `enemy_reveal`
- `reaction_closeup`
- `slow_motion_replay`

### Scoring inputs

The director uses structured semantic metadata already stored on canonical events:

- importance
- danger
- rarity
- reversal
- actor count
- audience-interest tags
- optional selected/followed crawler
- continuity with the prior shot
- location continuity

### Anti-thrashing

The director applies:

- minimum hold duration
- switch margin
- continuity bonus
- same-subject shot extension

A nearby event does not automatically force a cut.

### Determinism

A plan has a SHA-256 digest. Reversing the input event list must still produce the same ordered plan and digest because canonical ordering is re-established internally.

### Current limitation

There is no Unreal geometry/visibility model yet. Line-of-sight, obstruction, lens choice, animation availability, and physical camera collision are therefore deferred to the Unreal rendering layer. The backend selects logical subjects, locations, timing, and shot intent.

---

## Slice 23 — Live Crawler Channels

Module: `livingworld.live_channels`

A crawler channel is a stateless public projection for watching one crawler.

It contains:

- public crawler profile/state
- party state if present
- nearby visible encounters
- recent canonical public events
- deterministic camera plan focused on the crawler
- a presentation detail-focus request

### Multiple viewers

`ViewerChannelRegistry` is presentation-session state outside `Crawl`.

Different viewers can independently select different crawlers while sharing the same authoritative simulation.

### Switching

Switching channels does not mutate Crawl state. It changes only the viewer-to-crawler selection.

### Detail-tier focus contract

`channel_focus_plan()` produces a pure scheduling request:

- watched crawler -> effective Tier A request
- same-location/party context -> effective Tier B request
- everyone else -> existing tier

The function does not call `set_tier()` and does not write to `crawl.modifiers`.

This avoids making viewer activity part of the deterministic simulation fingerprint.

Actual Tier C/D abstract execution remains SCALE-001. When the runtime scheduler consumes live focus overrides, this focus request is the integration contract.

---

## Slice 24 — Story Arc and Highlight Detection

Module: `livingworld.story_highlights`

`StoryArcDetector` performs deterministic graph/rule analysis over canonical `CrawlEvent` records.

It does not use an LLM and does not invent motivations.

Every `StoryArc` contains:

- stable story ID
- story type
- deterministic interest score
- start/end tick
- floors involved
- participant IDs
- exact canonical event IDs
- deterministic explanation
- evidence strings containing event type + event ID

### Recognized categories

Current classification includes:

- notable death
- betrayal
- rescue
- rescue/comeback
- repeated near-death
- boss outcome
- party collapse
- relationship reversal
- unlikely alliance
- progression sequence
- emergent sequence

### Connection rules

The analyzer groups events using:

1. semantic causal-parent links,
2. shared actors within bounded time windows,
3. event importance,
4. relationship impact/reversals,
5. cross-floor notable event history for the same crawler.

### Non-redundancy

Highly overlapping lower-score arcs are suppressed so one event cluster does not flood the highlight feed with nearly identical packages.

---

## Spectator API additions

The v0.7 Spectator API adds:

- `GET /api/spectator/channels/{npc_id}`
- `GET /api/spectator/camera/plan`
- `GET /api/spectator/highlights`
- `GET /api/spectator/highlights/{story_id}`

The existing spectator allow-list/public projection boundary remains in force.

---

## Validation

### Focused Batch 6 tests

```powershell
.\.venv\Scripts\python.exe -m pytest `
  tests/test_crawl_slices22_24.py `
  -q
```

Tests cover:

- deterministic camera plan/digest
- no camera mutation of Crawl state
- anti-thrashing/shot hold behavior
- pure watched-crawler focus planning
- independent multi-viewer channels
- rescue/comeback event grouping
- cross-floor relationship grouping
- public API camera/channel/highlight endpoints

### Small integrated checkpoint

```powershell
.\scripts\run-crawl-slices22-24-validation.ps1 `
  -Crawlers 25 `
  -Floors 2 `
  -MaxSteps 5000 `
  -SkipFullRegression
```

### Formal gate

```powershell
.\scripts\run-crawl-slices22-24-validation.ps1
```

Defaults:

- 50 crawlers
- 3 floors
- 10,000 max steps
- Slices 1–24 focused suite
- presentation acceptance demo
- full inherited regression suite

The presentation demo includes a deterministic structured NEAR_DEATH -> RESCUE fixture after the autonomous crawl completes. This fixture exists only to guarantee the analyzer's multi-event acceptance path is exercised regardless of the simulation seed. It is stored as canonical events and is clearly an acceptance fixture, not claimed as emergent simulation drama.

### Required acceptance checks

- crawl completed
- camera plan nonempty
- camera plan deterministic
- anti-thrashing check passed
- camera generation read-only
- multiple viewers can follow independently
- channel payload remains public-only
- focus request does not mutate authoritative state
- story arcs found
- rescue arc found from the acceptance fixture
- all story evidence references canonical event IDs
- channel/camera/highlight API endpoints respond successfully
- API reads preserve the persisted Crawl fingerprint

---

## Carried technical debt

### BALANCE-001

Formal scale runs still show unrealistically high survival. Tune mechanics later without scripting drama.

### SCALE-001

Tier C/D scheduling is validated, but abstract C/D execution is not yet the authoritative runtime path.

### REPLAY-001

Replay uses the complete canonical event ledger plus final-state verification. Periodic exact authoritative checkpoints remain future work.

### VERSION-001

The implementation milestone has advanced beyond the currently reported `crawl.standard` ruleset version `0.4.0`.

### CAMERA-001

Logical camera intent is headless. Unreal geometry-aware line-of-sight, obstruction, lens/collision, animation feasibility, and physical camera paths remain future renderer work.

### CHANNEL-001

Viewer focus requests are pure presentation scheduling requests. Runtime Tier C/D execution must later consume them without making viewer activity part of canonical game-state determinism.

### STORY-001

Current story detection is deterministic rule/graph analysis. Additional patterns and longer relationship models can be added after real crawl distributions show which sequences are common enough to warrant dedicated detectors.
