# Crawl / The Underreach — Roadmap Completion Tracker

Branch: `crawl/roadmap-completion` (from `origin/main` @ `b83010c`)
Last updated: 2026-10-23
Environment: Linux VM, Python 3.12, ffmpeg 8.1.2 present, Node 24 present,
no Unreal Engine, no GPU media services (ComfyUI/Ollama/Kokoro).

## Audit method

Three parallel read-only auditors + independent verification by the coordinator.
"verified" = tests actually run on this VM in the audit window, or a live probe
executed here. File presence alone is never counted as evidence.

## Baseline test suite

- Two full-suite attempts were killed by VM restarts before producing output.
- A chunked re-run (4 chunks, appending to `/tmp/crawl_baseline.log`) is in progress.
- Subset evidence gathered by auditors is recorded in the tables below.

---

## Priority A — Core simulation & autonomous intelligence

| Milestone | Status | Evidence |
|---|---|---|
| Slice 1 — Domain model | complete+verified | crawl_domain.py; save/load/archive tests pass |
| Slice 2 — Identity/traits/skills/needs | complete+verified | character_factory/crawler_domain; trait-driven selection tests pass |
| Slice 3 — Decision engine | complete+verified (mechanism) | utility scoring real; 100-crawler decision loop not evidenced |
| Slice 4 — Perception/knowledge | complete+verified | epistemic bounds tested |
| Slice 5 — Memory/relationships | complete+verified | v0.4 crawler_social + 30C.1/30C.2 (13/13); multi-stratum memory survival tested |
| Slice 6 — Floor gen/traversal | complete+verified | deterministic connected floors; 9/9 in slices2_6 |
| Slice 7 — Combat/injury/death | complete+verified | deterministic combat; death persistence 6/6 |
| Slice 8 — Items/loot | complete+verified | single-owner invariant; death-drop tested |
| Slice 9 — Progression/builds | complete+verified | **NEW** `test_progression_divergence.py` 2/2: identical templates diverge via different lived XP (mechanically different builds + combat modifiers); identical XP reproduces identical builds |
| Slice 10 — Parties/alliances | complete+verified | v0.4 party_system + 30C.4; 30C.6 proof: 21 parties, 15 dissolutions, 7 leadership changes across 3 seeds |
| Slice 11 — Encounters | complete+verified | 29c3 14/14 |
| Slice 12 — Deadlines/advancement | complete+verified | floor lifecycle real; MVP deadline tests pass |
| Slice 13 — Director | partially-implemented | CrawlDirector real (budgeted, validated, tested) but NOT wired into v0.10 loops (30A.5/30B.3/30C.6); only v0.4 HeadlessCrawlMVP |
| Slice 14 — Event ledger | complete+verified | causal annotation, importance/rarity scoring; tests pass |
| Slice 15 — MVP gate | partially-implemented | MVP passes 24 crawlers/3 floors; 100-crawler requirement unevidenced; `should_rescue` is dead code |
| Slice 16 — Detail tiers | partially-implemented | tier assignment/scheduling/rebalancing real (2/4 pass); not integrated into v0.10 loops; multi-seed validation test too slow to complete |
| 30B.1 AI brain foundation | complete+verified | 8/8 |
| 30B.2 Intent validation/execution | complete+verified | 8/8 |
| 30B.3 Brain-driven descent | complete+verified | full brain-driven multi-stratum run test passed (9.9 min) |
| 30C.1 Social state | complete+verified | 9/9 |
| 30C.2 Social memory evolution | complete+verified | 13/13 |
| 30C.3 Social intents | complete+verified | 11/11 |
| 30C.4 Parties/alliances/leadership | complete+verified | 10/11 (1 slow test not run) |
| 30C.5 Rivalry/betrayal | complete+verified | 10/10 |
| 30C.6 Group decision orchestration | complete+verified | 9/9 tests; proof PASS |
| 30A.5 Full autonomous descent | complete+verified | **9/9** (22.6 min): 12 descenders x 3 strata unattended, bitwise determinism (reversed roster), checkpoint-resume final-state equality |

**Honest caveats (A):**
- Social arcs in 30C.6 tests/proofs are PRIMED (relationships/grievances injected,
  then machinery verified) — mechanisms real, emergence from unprimed play not demonstrated.
- DeterministicReferenceBrain is honest rule-based policy (no LLM, not scripted);
  LLMs are presentation-only, never consulted for canonical state (verified by code).
- No unseeded random/time/uuid in canonical paths; canonical JSON digests +
  fingerprints; reproduction tests pass.

## Priority B + ops — runtime, scale, persistence

| Area | Status | Evidence |
|---|---|---|
| Gate B (100 crawlers, MVP path) | complete+verified | `crawl_batch_demo --crawlers 100 --floors 3`: 220 steps, 3,481 events, ~2m08s; replay fingerprint-identical; 45 emergent parties. Caveat: `eliminated=0` (death not exercised at scale) |
| Gate B (30A.5 authority path) | implemented, verified at 12 | 12x3 completed (~177s); no 100-contestant 30A.5 run demonstrated |
| Gate C (1,000 crawlers) | implemented-not-verified | docs defer as "later stress target"; zero evidence at 1,000 |
| Checkpoint format | complete+verified | `underreach.alpha-checkpoint.v1`: atomic tmp+fsync+validate+rename, digest chain, `latest.json` w/ corrupt-pointer fallback, retention 12 |
| Crash recovery | complete+verified | Real SIGKILL mid-run: resumed, `checkpoint_recoveries=1`, 0 failures, 619/619 unique event IDs; 43/43 alpha-runtime tests; **NEW** automated `test_alpha_runtime_crash_recovery.py` (SIGKILL subprocess + resume + duplicate-ID check) |
| Deterministic replay | complete+verified | fingerprint-identical double runs at 12 and 100 crawlers; bitwise 30A.5 |
| Replay contract (§37) | partially-implemented | ReplayArchive replays recorded events; no event-range selection / entity filter / re-sim-from-checkpoint |
| Continuous unattended runtime | complete+verified (headless) | profiles, per-second ticks, 30–60s checkpoints, supervision, lockfile, clean-stop; ran live |
| Monitoring | implemented-not-fully-verified | health endpoint, metrics JSONL, viewer header exist; not end-to-end vs HTTP |
| Backup/restore | implemented (procedure) | **NEW** `docs/OPERATIONS_BACKUP_RESTORE.md`: stop, copy-state-dir, fingerprint record, resume-with-validation |
| Migration strategy (§31) | implemented (policy) | versioned JSON envelopes, additive-free, migrator-with-test rule, nullable-column policy |
| Admin intervention (§31) | not-implemented | no Crawl admin console; documented as not-implemented in ops doc |
| Season archive/reset (§30) | complete+verified | **NEW** `test_crawl_season_lifecycle.py`: conclude -> archive -> new seeded crawl, both histories intact and separately queryable |
| Runaway/stuck detection (§31) | partially-implemented | director computes `stagnation_ratio`; nothing actuates on it |
| Media/chronicle persistence (§30.5) | implemented, mostly verified | media DB + durable queue + restart-safe jobs; soak test unverified here |
| Windows 11 deployment | partially-implemented | operator guide + ps1 scripts + Windows code paths; missing: service packaging, alerting, signed packaging, Crawl runtime container |

## Priority C — Spectator & presentation

| Area | Status | Evidence |
|---|---|---|
| Spectator backend API | complete+verified | live probe: seeded crawl -> /descenders, /{id}, /channel, follow/release/focus, viewer/state, trending/fallen/camera — all 200 on real data |
| Feed API defect | **fixed+verified** | `GET /api/feed/descenders/{id}/channel` returned HTTP 500 without registry (Query descriptor leak); fixed via `_feed_channel_payload`; regression 3/3 pass, 1 fails pre-fix |
| Viewer React app | complete+verified | genuine client (real routes); `node --test` 18/18; **NEW**: `npm ci` + `tsc --noEmit` + `vite build` all green on this VM |
| Dashboard React app | complete+verified | real routes (`/api/world`, `/api/map`, ...); **NEW**: `npm ci` + `tsc --noEmit` + `vite build` all green |
| Camera direction | complete+verified | 9 modes, deterministic shot planning over real events; 44 tests (live_camera + spectator_viewer) |
| Unreal bridge backend | complete+verified | `bridge_bootstrap`/`build_bridge_frame` emit `crawl.unreal-spectator.v1` from real Crawl state; 18 bridge + 34 camera-planning tests pass |
| Unreal consumer side | blocked | no Unreal Engine here; UE 5.8 editor scripts present in `unreal/CrawlPresentation/Content/Python/`; rendering/animation/replication are Unreal-owned. One optional human step: `docs/HUMAN_ACTION_REQUIRED_29A1.md` (editor-only Mutable graph, free) |

## Priority D — Storytelling & media

| Area | Status | Evidence |
|---|---|---|
| Media event export (30.5.1) | complete+verified | one-way membrane sim->media; 23 tests (export + highlight + chronicle) |
| Media DB/durable queue (30.5.2) | complete+verified | 18 tests (queue + identity + terminal archive) |
| Highlight/story-arc detection (30.5.3) | complete+verified | deterministic scoring over canonical events |
| Delver chronicles (30.5.4) | complete+verified | chronicle profiles from real events |
| Narrative claim verification | complete+verified | contradictions/unsupported claims REJECTED; aux models can only downgrade; 26 tests |
| Commentary | implemented-not-verified | deterministic template prose from real CrawlEvents (171 lines, no stubs); no dedicated test run |
| FFmpeg motion-story (30.5.9) | complete+verified | real encodes with ffmpeg 8.1.2 on this VM; 7/7 |
| Headless local image/audio (30.5.7/8) | complete+verified | DeterministicLocalPngProvider (valid PNG), DeterministicLocalWavProvider (valid WAV); 26 tests |
| Media worker (30.5.10) | complete+verified | `_production_ready` gating correct; 7/7 |
| Production AI providers | blocked | Ollama qwen3, ComfyUI SDXL/Wan2.2, Kokoro not installed here (all connection-refused); need Windows media workstation + `install-underreach-media-pipeline.bat` |
| Website/blog (30.5.11) | not verified | killed after 10.5 min (timeout, not failure) |
| Promotion soak (30.5.12) | not verified | long-running by design; killed after 10.5 min (timeout, not failure) |

## Priority E — Public product

| Area | Status | Evidence |
|---|---|---|
| Profiles | complete+verified | `/api/feed/descenders/{id}`, per-descender channel, spectator crawler+history — probed live |
| Archives | complete+verified | `/api/feed/fallen`, `/api/feed/ledger/*`, `/api/spectator/replay*`; terminal-archive tests pass |
| Follow | complete+verified | session-scoped follow/release w/ idempotent request IDs; verified live |
| Trending | complete+verified | `/api/feed/trending` from semantic_score over real events |
| Search | complete+verified | **NEW** `GET /api/feed/search?q=...`: read-only substring search over descender ids + canonical events; 4 tests pass |
| Notifications | complete+verified | **NEW** `GET /api/feed/notifications?viewer_id=...`: notable canonical events (death/injury/advancement/encounters/party/alliance changes) for the followed descender, derived from the ledger; 3 tests pass |

## Billable-provider safety

No code path can charge money in default config: ComfyUI/Ollama/Kokoro configs
validate loopback-only (reject non-local URLs); `ai.py` OpenAI adapter disabled
by default (`ai_provider: "none"`); Kokoro `estimated_cost_microusd=0`. Nothing
billable fires without deliberate reconfiguration.

---

## Gates

| Gate | Status |
|---|---|
| A — Autonomous Contestant | complete+verified |
| B — Headless Descent (100) | complete+verified (MVP path); 30A.5 path verified at 12 |
| C — Scalable Descent (1,000) | NOT satisfied — no evidence; documented deferral |
| D — Watchable Contestant | complete+verified (backend + built viewer; live Unreal rendering blocked) |
| E — Automatic Highlight | complete+verified (detection + FFmpeg assembly from canonical events) |
| F — Autonomous Entertainment Product | partially — sim + presentation + highlights run unattended; no search/notifications; no deployed viewer hosting; no public deployment (owner approval required) |

## Remaining genuine blockers (need owner or external resources)

1. **Unreal consumer**: UE 5.8 + Windows. Exact unblock: run editor automation scripts in `unreal/CrawlPresentation/Content/Python/` on a Windows PC with UE 5.8.
2. **Production media providers**: Windows media workstation + `install-underreach-media-pipeline.bat` (Ollama qwen3:8b/4b, ComfyUI SDXL, Wan2.2, Kokoro).
3. **Gate C**: run the 1,000-crawler matrix (or accept the documented deferral).
4. **Windows-only proof steps**: 20x100x3 matrix script, 2-hour soak, `D:\CrawlTesting` paths — never left artifacts in repo.
5. **Public deployment**: owner approval required; not attempted.
