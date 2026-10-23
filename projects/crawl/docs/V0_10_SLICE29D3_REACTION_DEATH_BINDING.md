# Underreach v0.10 — Slice 29D.3 Real Reaction & Death Binding

## Purpose

Replace the remaining 29D.2 semantic hit-reaction/death fallbacks with measured real Unreal animation assets while preserving the authoritative simulation boundary.

## Authority contract

29D.3 is presentation-only. It may select animation assets, synchronize reactions to already-canonical contacts, and hold a terminal death pose. It may not change hit/miss results, damage, death, actor position, Ledger order, or encounter outcome.

## Pipeline

Accepted 29C canonical truth → accepted 29D.1 combat windows → accepted 29D.2 real attack binding → fresh Unreal reaction/death asset discovery and AnimPose measurement → deterministic 29D.3 binding → Unreal consumer proof.

## Acceptance requirements

- At least one real Manny-compatible hit-reaction asset and one real Manny-compatible death asset must be discovered and measured.
- Frozen/incompatible candidate animations are rejected.
- Every canonical hit-reaction window is bound to a real measured asset.
- Every canonical death window is bound to a real measured asset.
- Reactions begin at the accepted 29D.1 attack contact time with <= 1 ms schedule error.
- Death bindings require canonical death truth and terminal-pose intent.
- 29D.2 attack bindings remain unchanged.
- Facing and Feed camera intent remain unchanged.
- Unreal can load every bound asset under NullRHI.
- Unreal does not modify the proof artifact.
- Identical inputs reproduce the same binding digest.
- Full repository regression suite passes.

## Validation

Run:

```powershell
.\scripts\run-underreach-reaction-death-validation.ps1
```

The slice is accepted only if the runner ends with `[29D.3] PASS`.

## Expected discovery failure

If the current Unreal content contains no compatible hit-reaction or death animation, validation intentionally fails and prints discovered/rejected candidates. That is a content dependency, not permission to label an unrelated animation as a reaction or death asset.
