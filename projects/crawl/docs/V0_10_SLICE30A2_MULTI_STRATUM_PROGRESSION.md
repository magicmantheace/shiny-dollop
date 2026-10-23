# Underreach v0.10 — Slice 30A.2 Multi-Stratum Progression

## Purpose

30A.2 extends the accepted 30A.1 Descent Run State across multiple deterministic Strata.

The authoritative architecture remains:

```text
Deterministic Crawl Simulation
        ↓
Canonical Descent / Ledger
        ↓
Presentation manifests
        ↓
Unreal Engine 5.8
```

Unreal and presentation systems remain unable to mutate canonical progression.

## Accepted baseline

30A.2 branches from accepted 30A.1:

- accepted SHA: `b811f49ca5282903def49b9f717db8a0a8b61b10`
- 30A.1 protocol: `underreach.descent-run-state.v1`
- 30A.1 remains unchanged and continues to own the single-Stratum foundation.

30A.2 adds a new protocol instead of rewriting the accepted 30A.1 implementation.

## Protocol

- protocol: `underreach.multi-stratum-progression.v1`
- implementation: `30a2.1`
- portable serialization: `underreach.multi-stratum-serialization.v1`
- proof protocol: `underreach.multi-stratum-progression-proof.v1`

## Canonical state

The existing `Crawl` model, exposed through `underreach_domain.Descent`, remains the only mutable canonical truth object.

30A.2 does **not** introduce:

- a parallel Descent state tree,
- a second database,
- Unreal-owned progression,
- presentation-owned traversal,
- generated prose as gameplay truth.

The existing deterministic `CrawlLifecycleService` remains responsible for the actual floor/Stratum lifecycle mutation.

## Deterministic run identity

A 30A.2 Descent ID is derived from:

- Descent seed,
- ruleset ID,
- ruleset version,
- configured Stratum count,
- sorted Descender roster digest.

Therefore two runs with the same seed and roster but different configured Stratum counts cannot silently share the same canonical identity.

Character art, Unreal assets, animation assets, presentation materials, and camera configuration do not participate in Descent identity.

## Stratum configuration

30A.2 requires at least two Strata.

All configured Strata are generated deterministically at Descent creation through the already-proven floor generator.

At creation:

- current Stratum is 1,
- every Stratum is `pending`,
- all Descenders begin at the Stratum-1 entrance,
- transition history is empty.

At start:

- exactly Stratum 1 becomes `active`,
- all future Strata remain `pending`.

## Sequential progression invariant

While a Descent is running:

- every Stratum before the current Stratum must be `completed`,
- exactly the current Stratum must be `active`,
- every future Stratum must remain `pending`.

Advancement is always one Stratum at a time.

A transition from Stratum N can only produce Stratum N+1.

Skipping or rewinding Strata is invalid canonical state.

## Advancement gate

`MultiStratumProgressionService.advance()` requires:

1. the Descent is running,
2. the current Stratum is not the final Stratum,
3. at least one active survivor exists,
4. every active survivor has reached an exit Sector.

The wrapper does not invent the transition itself. It calls the established authoritative `CrawlLifecycleService.complete_current_floor()` operation.

The existing lifecycle service then:

- completes the current Stratum,
- marks active survivors as advanced,
- increments the current Stratum,
- returns survivors to active status,
- moves survivors to the next Stratum entrance,
- resets per-Stratum statistics/agent short plans,
- activates the next Stratum,
- preserves eliminated/dead Descenders on the Stratum where they stopped participating.

## Survivor-selective advancement

Dead or eliminated Descenders never move forward merely because the Descent advances.

The 30A.2 proof deliberately eliminates one Descender before the first transition.

Acceptance requires:

- the eliminated Descender remains on Stratum 1,
- all surviving Descenders arrive at the Stratum-2 entrance,
- survivor count remains stable through later transitions unless another authoritative elimination occurs.

## Canonical transition records

Each non-final advancement appends one ordered progression record containing:

- transition index,
- from Stratum index/number,
- to Stratum index/number,
- tick before transition,
- tick after transition,
- tick advance amount,
- exact sorted survivor Descender IDs,
- survivor roster digest,
- survivor count,
- eliminated count,
- pre-completion source Stratum state digest,
- activated destination Stratum state digest,
- destination entrance Sector,
- transition digest,
- canonical Ledger event ID.

Transition history must remain contiguous:

```text
1 → 2
2 → 3
3 → 4
...
```

## Canonical Ledger events

30A.2 adds:

- `MULTI_STRATUM_PROGRESSION_INITIALIZED`
- `STRATUM_ADVANCED`
- `MULTI_STRATUM_DESCENT_COMPLETED`

Existing lifecycle events such as `FLOOR_COMPLETED` and `FLOOR_STARTED` are retained for backward compatibility.

`STRATUM_ADVANCED` binds the transition digest and survivor roster digest into the authoritative Ledger.

## Descender positions

Every participating Descender retains canonical:

- participation status,
- Stratum number/index,
- Sector ID.

Active Descenders must be on the current active Stratum.

Dead/eliminated Descenders may remain on an earlier completed Stratum but may never exist on a future Stratum.

After final Descent completion, surviving Descenders remain `advanced` on the final completed Stratum.

## Snapshots

`build_multi_stratum_snapshot()` records deterministic canonical state including:

- Descent identity and lifecycle,
- configured/completed Stratum counts,
- current Stratum,
- every Stratum seed/theme/status/digest,
- exact Descender positions,
- participation counts,
- transition history,
- transition-history digest,
- Ledger ID digest,
- canonical Descent fingerprint.

The snapshot receives a canonical SHA-256 digest using the existing checkpoint JSON/hash implementation.

## Portable serialization

30A.2 provides deterministic portable serialization for exact state reconstruction.

The envelope includes:

- canonical Descent model,
- canonical Descent fingerprint,
- progression snapshot digest,
- transition-history digest,
- Ledger-ID digest,
- outer payload digest.

Tampering is rejected.

Portable serialization is not a replacement for the unattended runtime checkpoint system.

## Durable checkpoint compatibility

30A.2 continues to use the accepted `AlphaCheckpointStore` for durable operational checkpoints.

The formal proof writes a checkpoint immediately after the first real Stratum transition and proves that restore preserves:

- canonical Descent state,
- current Stratum = 2,
- transition history,
- exact Ledger prefix,
- canonical fingerprint.

The restored state then remains valid under the 30A.2 progression validator.

## Formal deterministic proof

Default acceptance configuration:

- seed: `underreach-30a2-multi-stratum-progression-proof`
- Descenders: 8
- Strata: 4
- one Descender eliminated before first advancement
- expected survivors: 7
- expected transitions: 3

Required sequence:

```text
planned
  ↓
Stratum 1 active
  ↓
1 Descender eliminated
  ↓
7 survivors reach exit
  ↓
Stratum 1 → Stratum 2
  ↓
checkpoint + portable restore proof
  ↓
Stratum 2 → Stratum 3
  ↓
Stratum 3 → Stratum 4
  ↓
7 survivors reach final exit
  ↓
completed
```

The proof is generated twice. Both outputs must have identical canonical digests and Descent IDs.

## Regression boundary

Focused validation runs both:

- accepted 30A.1 tests,
- new 30A.2 tests.

The full repository regression suite runs afterward.

No GitHub Actions are required.

## Explicit non-goals

30A.2 does not implement:

- loot caches,
- relics,
- inventory reward generation,
- survival resource pressure,
- autonomous full-Descent orchestration,
- LLM cognition,
- social intelligence,
- Unreal authority.

Those remain later roadmap slices.

In particular:

**30A.3 owns Loot, Cache & Relic Foundation.**

## Acceptance command

```powershell
.\scripts\run-underreach-multi-stratum-progression-validation.ps1
```

The slice is accepted only when local validation ends with:

```text
[30A.2] PASS
```

## Next canonical slice after acceptance

**30A.3 — Loot, Cache & Relic Foundation**

30A.3 will add deterministic canonical loot/reward objects and acquisition foundations without allowing presentation assets or sponsorship to determine gameplay truth.
