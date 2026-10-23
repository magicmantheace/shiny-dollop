# LivingWorld v0.3 Slice 1B — Political Balance Pass

## Why this pass exists

The first 25-year Slice 1 calibration was structurally healthy, but faction loyalty saturated at 1.000 across the continent by roughly year 10 and stayed there even while factions continued to report grievances. That made the political layer too self-stabilizing and prevented the rebellion pathway from being meaningfully exercised.

Slice 1B corrects that behavior without forcing unrest or adding arbitrary rebellion events.

## Core change: loyalty is an equilibrium

Faction loyalty no longer increases by a fixed amount whenever satisfaction is above a threshold. Each faction now has a target loyalty derived from current political conditions.

The target includes:

- faction satisfaction with food, stability, taxes, military readiness, trade and war conditions;
- direct penalties from active grievances;
- a small bonus when the faction is structurally favored by the current government form;
- a small bonus when the faction leader holds political office;
- a small deterministic modifier from the faction leader's loyalty disposition.

Ordinary politics cannot push faction loyalty above 0.94. Perfect 1.000 loyalty is therefore reserved for future exceptional systems rather than becoming the default end state of peaceful government.

## Grievances now matter directly

Active grievances reduce the loyalty target rather than merely appearing as descriptive state.

Current grievance weights intentionally make foundational failures more serious:

- weak legitimacy;
- food insecurity;
- local disorder;
- religious leadership disputes;
- excessive taxation;
- military neglect;
- restricted trade;
- regional neglect.

Multiple grievances stack up to a bounded penalty.

## Political hysteresis

Political trust is deliberately asymmetric:

- loyalty falls toward a worse equilibrium at 10% of the remaining gap per monthly political cycle;
- loyalty recovers at 5.5% of the remaining gap per monthly political cycle.

This means a government can damage faction support faster than it can rebuild it. Fixing a crisis works, but political scars persist long enough to matter historically.

## Influence remains separate from loyalty

An angry faction can still gain political influence. Grievances continue to increase political salience in the influence calculation even while reducing loyalty.

This distinction is intentional:

> a faction becoming hostile should not make it politically irrelevant.

It enables a dissatisfied bloc to become both influential and disloyal, which is the state required for meaningful coups, leadership crises, secession pressure and future civil conflicts.

## Rebellion remains emergent

Slice 1B does not directly increase rebellion probability.

The existing rebellion pathway still requires a combination of:

- weak kingdom legitimacy;
- low kingdom stability;
- an influential faction;
- low faction loyalty;
- unresolved grievances;
- deterministic probability after the pressure threshold is crossed.

The difference is that sustained political failure can now actually produce low faction loyalty.

## Regression coverage

`tests/test_politics_balance.py` verifies:

1. the balance strategy is installed into the authoritative political cycle;
2. a healthy faction starting at 1.0 converges below perfect loyalty;
3. grievances directly lower the faction loyalty target;
4. sustained severe conditions can drive a faction below 0.35 loyalty;
5. fixing the crisis restores loyalty gradually without returning to 1.0.

## Calibration acceptance targets

The next 25-year deterministic calibration should satisfy all existing structural and political invariants and should no longer show continent-wide loyalty saturation.

Preferred healthy-seed behavior:

- average faction loyalty normally below 0.95;
- minimum faction loyalty meaningfully different from the average;
- factions with grievances can lose loyalty;
- loyalty can recover after conditions improve;
- leadership transitions remain functional;
- rebellion is possible but is not required in every 25-year peaceful calibration;
- no runaway kingdom fragmentation;
- no regression in population, warfare or performance.

If the 25-year rerun is healthy, Slice 1 advances to a 200-year political history run. The 200-year run should demonstrate both long stable periods and at least some seeds/periods where political failure produces genuine internal crisis.
