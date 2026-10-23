# The Underreach

**The Underreach** is the product/world identity built on the deterministic LivingWorld simulation engine. **The Descent** is the organized competition taking place within it; its participants are **Descenders**, who progress through **Strata** and their local **Sectors**.

The underlying engine remains server-authoritative and continues to simulate kingdoms, settlements, economies, wars, NPCs, history, and world state independently of presentation. Existing `crawl`/`crawler`/`floor` identifiers are retained only where changing them would risk persisted-state, replay, seed, or fingerprint compatibility.

New viewer-facing systems use the Underreach vocabulary:

- **The Arbiter** — deterministic rule/enforcement authority
- **The Ledger** — authoritative record and standings
- **The Feed** — spectator-facing broadcast/data surface
- **Echoes** — noteworthy story sequences discovered from Ledger truth
- **Echo Reels** — rendered highlight packages
- **Houses / Patrons / Boons** — the planned bounded backing/support vocabulary
- **Refuges / Caches / Relics** — safe areas and reward vocabulary

See [docs/UNDERREACH_LEXICON.md](docs/UNDERREACH_LEXICON.md) for the canonical terminology and migration policy.

## Procedural Descenders

Slice 29A.1 adds versioned, deterministic Character DNA for Human and Dwarf
Descenders. Renderer-neutral identity is translated by the Character Factory
into disposable Unreal presentation manifests, authored through Blender/MPFB,
and consumed by the existing live bridge, camera, Feed, Follow, and terminal
state systems. See [docs/CHARACTER_DNA.md](docs/CHARACTER_DNA.md) and
[docs/CHARACTER_ASSET_PIPELINE.md](docs/CHARACTER_ASSET_PIPELINE.md).

## Living World simulation engine

The LivingWorld engine is intentionally separate from the Unreal presentation/client layer. Kingdoms, settlements, economies, wars, NPCs, history, and world state continue to exist whether viewers or presentation clients are connected or not.

## Living World Simulator v0.1 target

The initial target generates and simulates:

- 1 procedural strategic region
- 2 autonomous kingdoms
- 5 towns
- 20 villages
- 10,000 statistical inhabitants
- 100 persistent NPCs
- Humans, Elves, Dwarves, Gnomes, Halflings, Orcs, and Goblins
- resources, magic, culture, religion, economy, production, and trade
- NPC families, goals, memories, relationships, aging, and mortality
- kingdom planning, diplomacy, succession, rebellion, armies, and war
- immutable historical events and human-readable chronicles
- external FastAPI world-state and command APIs
- React/TypeScript administrative dashboard
- API-key protected god-mode commands
- optional OpenAI-compatible/local LLM enhancement hooks; the simulation never requires an LLM

## Architecture

```text
Unreal / The Feed ───────┐
                         │
React Admin Dashboard ───┼──► FastAPI / Command Gateway
External Tools ──────────┘              │
                                        ▼
                               Living World Engine
                        ┌───────────────┼───────────────┐
                        ▼               ▼               ▼
                     Kingdoms          NPCs        Settlements
                        │               │               │
                        └────── Economy / Trade ────────┘
                                        │
                              Politics / Warfare
                                        │
                            Authoritative History
                                        │
                                Persistence Layer
                                   │           │
                                 SQLite    PostgreSQL
```

For Descent presentation, the architectural rule is:

```text
Deterministic simulation
        ↓
The Ledger records truth
        ↓
The Feed presents truth
        ↓
Echoes discover stories in truth
```

The AI layer may propose intent. The deterministic simulation validates and executes actions. AI and presentation are never the database, physics authority, combat authority, or canonical event ledger.

## Preferred public API vocabulary

Slice 28B and later viewer clients should use the new Feed API surface under `/api/feed/...`, including concepts such as `descent_id`, `descender_id`, `stratum_number`, and `sector_id`.

Legacy spectator routes and legacy serialized simulation names remain available for compatibility while public-facing development moves to the Underreach vocabulary.

## Quick start

Requirements:

- Python 3.12+
- Node.js 20+ for the dashboard

Backend:

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -e .
cp .env.example .env
livingworld
```

The API defaults to `http://127.0.0.1:8000` and Swagger UI is available at `/docs`.

Dashboard:

```bash
cd dashboard
npm install
npm run dev
```

The dashboard defaults to `http://127.0.0.1:5173` and proxies `/api` to the FastAPI server.

## Generate a fresh world

```bash
curl -X POST http://127.0.0.1:8000/api/admin/world/generate \
  -H "X-Admin-Key: change-me"
```

The generator is seeded and reproducible. The default seed, counts, time scale, database URL, and admin key are configurable through environment variables.

## Simulation controls

The API supports pause/resume, configurable speed, and deterministic stepping by hours, days, months, or years. Long-range simulation runs through the same engine as normal ticks; there is no special fake-history generator.

## External commands

All administrative intervention is routed through a command gateway and recorded in history. Supported commands include kingdom priorities and diplomacy, NPC travel and mortality, settlement resources, disasters, ruler changes, and world-time advancement.

## Persistence

SQLite is the zero-setup default. PostgreSQL is supported through the same SQLAlchemy persistence layer by changing `LIVINGWORLD_DATABASE_URL`.

## Docker

Docker support is optional. The repository does not require Docker to run locally.

## Testing policy

The repository test suite is local-only unless that policy is explicitly changed later. **Do not use GitHub Actions for the current Crawl/Underreach development workflow.**

See [ROADMAP.md](ROADMAP.md), [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), and [docs/UNDERREACH_LEXICON.md](docs/UNDERREACH_LEXICON.md) for the broader design and terminology contract.
