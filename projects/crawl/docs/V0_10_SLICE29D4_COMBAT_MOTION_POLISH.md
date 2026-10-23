# Underreach v0.10 — Slice 29D.4 Combat Motion Polish

## Purpose

29D.4 sits strictly downstream of the accepted 29D.3 real attack/reaction/death binding stack. It improves how canonical combat is presented without giving presentation code any authority over simulation truth.

The slice derives deterministic presentation directives for:

- bounded attacker/target spacing correction;
- contact-centered weapon/hand/foot refinement;
- support-foot locking during strike contact;
- bounded stagger/knockback presentation on canonical hits;
- deterministic transition blend windows;
- exact preservation of accepted facing and Feed camera intent;
- short action-aware camera contact holds;
- terminal death pose and corpse root locking;
- aftermath camera hold timing.

## Authority boundary

The canonical simulation remains authoritative for hit/miss, damage, death, positions, participant identity, event order, and encounter outcome. 29D.4 may only derive non-authoritative presentation motion.

The polish manifest therefore requires:

- `authoritative: false`
- `canonical_state_mutation_allowed: false`
- `simulation_time_independent: true`
- exact binding to the accepted 29D.3, 29D.2, 29D.1, and canonical source digests.

## Bounds

- pair alignment correction: <= 120 cm
- knockback presentation: <= 32 cm
- stagger presentation: <= 18 cm
- support-foot slide budget: <= 3 cm
- blend windows: 0.06–0.18 s
- reaction contact synchronization: <= 1 ms
- attack contact camera hold: 0.10 s
- death aftermath camera hold: 0.45 s

These values are presentation limits, not canonical movement.

## Validation

Run locally on the accepted Unreal 5.8 environment:

```powershell
.\scripts\run-underreach-combat-motion-polish-validation.ps1
```

The runner:

1. runs focused 29D.1–29D.4 deterministic tests plus attack/transition regressions;
2. freshly measures the four accepted Manny attack assets;
3. freshly discovers/measures the accepted real hit-reaction/death assets;
4. generates the 29D.4 proof twice and requires an identical digest;
5. runs a headless Unreal `-NullRHI -NoSound` consumer proof;
6. verifies all real assets load, contact/spacing/reaction/transition bounds hold, corpse locks exist, and the source proof file remains unchanged;
7. runs the full repository pytest suite.

## Acceptance

29D.4 is accepted only when the runner ends with:

```text
[29D.4] PASS
```

No GitHub Actions are required or permitted by this slice's workflow.
