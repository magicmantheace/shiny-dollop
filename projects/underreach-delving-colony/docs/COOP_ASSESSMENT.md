# Co-op assessment — Underreach: Delving Colony (S13, 2026-11-24)

The design record fixes the scope: **1–4 co-op** (Dragonwilds-sized),
not an MMO. S13 built the part of co-op that is headless-verifiable
— the **lockstep foundation** — and nothing else. This document
records what that foundation is, what co-op still needs that was
deliberately **not** built, the design questions that are the
owner's to answer, and the recommended first step on real hardware.

Honesty discipline, as in `docs/TEST_PLAN.md`: everything under
"verified" was run on this VM, headless, in this slice. Nothing
here claims a network, a second machine, or a human player was
involved in any test.

## (a) What now exists and is verified

The sim was already most of the way to lockstep before this slice:
it is deterministic (a pure function of its initial state and
command sequence), command-driven (every player action is a `Sim`
method), and its saves are canonical JSON + SHA-256 — a load must
reproduce the hash. What was missing was attribution, a command
history, and replay. S13 adds exactly those, as additive library
code in `sim/src/session.rs`; no existing behaviour changed (the
full scenario output is byte-identical to the pre-S13 run except
the new S13 section).

- **Typed command layer** (`Command`). A serializable enum
  covering the bridge's player-action vocabulary — carve, lantern
  (tier + fuel), job, plant, craft mask, support, vent, pump,
  craft cooling, descend, ascend — where `apply` dispatches to
  the *same* `Sim` methods the bridge handler calls, with the
  same arguments. The bridge's choreography scripts
  (`light_the_way`, `light_the_deep`, `open_floor1`) are
  deliberately **not** commands: they are multi-step founding
  scripts, not single sim operations, and stay bridge/scenario
  side. The bridge itself is unmodified.
- **Attributed session log** (`SessionLog`). The founding save
  (the founding sim's canonical save JSON) plus entries
  `{tick, player, seq, command, applied}` and the session's end
  tick. Players are numbered 1–4; ids outside that range are
  refused at every API. A command the sim refuses is recorded
  with `applied: false` — a refused move appears identically in
  every peer's log, which is what makes refusal itself
  deterministic.
- **Canonical merge** (`merge_streams`). Per-player streams
  merge into one order by sorting on `(tick, player, seq)` —
  total, deterministic, and independent of arrival order
  (proven: reversed stream order yields a byte-identical log
  and an identical final hash). Duplicate `(player, seq)` pairs
  and `seq` gaps are merge **errors**, surfaced, never silently
  repaired.
- **Live session + replay** (`Session`, `replay`). A session
  advances the sim to each entry's tick, applies the command,
  and records the outcome; an entry in the past, out of `seq`
  order, or from a non-existent player is refused. `replay`
  rebuilds the session from the log alone and reaches the
  **identical state hash** — and refuses a log whose recorded
  `applied` flags disagree with what the commands actually do
  (that disagreement is a desync, named as one). Logs roundtrip
  through JSON byte-identically without changing replay results.
  A mid-session save/load resumes a session (via
  `Session::resume`) and finishes at the uninterrupted hash.

Verified by `sim/tests/scenario_s13.rs` (7 tests) and the
scenario binary's S13 section: two players dividing the opening
labour on generated Floor 1 (P1's 10 lantern commands light the
way; P2 plants a plot and sets a support + vent) produce a
working colony — goods 22 at 6,200 ticks, nobody lost,
`replay_matches=true`, final hash
`11e30e9ddb3f6aa9b46e2fdd32df9a13ecf66f9d8c4dbfff4b4c6c332f2c787d`.
Full numbers in `docs/TEST_PLAN.md`.

**The desync check already exists**: the canonical save +
SHA-256 state hash, in place since S1. Two peers who applied the
same log hold the same hash; comparing hashes detects divergence
with certainty. What does not exist is any machinery that moves
bytes between peers or recovers from a detected divergence —
see (b).

## (b) What co-op still needs — NOT built, NOT headless-verifiable

None of the following exists in any form. Each needs real
machines, real latency, or real players, so none of it could be
proven in this environment, and per the slice rules none of it
was faked up unverifiable:

- **Network transport and host/join.** No sockets, no protocol,
  no peer discovery of any kind. Nothing in the codebase can
  move a command stream from one machine to another.
- **Session discovery / invitation.** No lobby, no join codes,
  no address exchange — a player cannot find a session to join.
- **Lockstep tick pacing under real latency.** The foundation
  assumes every peer has the full merged stream for a tick
  before anyone advances past it. How far ahead peers may run,
  what input delay hides the slowest connection, and what
  happens when a peer stalls are unimplemented and unmeasured.
- **Godot-side multiplayer integration.** The frontend speaks to
  one local bridge process. It has no notion of a second player,
  remote commands, or whose input is whose.
- **Desync recovery over a live connection.** Detection exists
  (hash comparison, and replay's applied-flag check). Recovery
  does not: there is no protocol for a diverged peer to fetch
  the authoritative log/save and resync, and no decision about
  whose copy is authoritative when hashes disagree.
- **Playing with 2–4 real clients on real machines.** Never
  done, in any form. Every S13 proof is one process applying a
  scripted merged stream to itself.

## (c) Open OWNER design questions

These are the owner's calls. The session layer was built to be
neutral on all of them (attribution is recorded; no permission
is enforced anywhere), and none should be settled by an
implementer guessing.

1. **Frontier rights and permissions.** The design record says
   "the player is the frontier" and "only the player plants
   first light past the frontier" — written for one player. With
   2–4, is *every* player the frontier (anyone may carve, plant
   first light, place kit, assign jobs, spend colony goods)? Or
   are there roles/permissions — and if so, whose? (The Deep
   Ledger already names depths and losses; should first light
   and rescues also be attributed by player name?)
   **DECIDED 2026-11-24 (owner):** every player is the
   frontier — anyone may carve, plant first light, place kit,
   assign jobs, and spend colony goods; there are no roles or
   permissions. Credit is **shared by the colony**: first
   light and rescues are NOT attributed by player name in the
   Deep Ledger. Session-log attribution stays mechanical —
   it exists for determinism and replay, not for credit.
2. **The lantern-clock rescue with multiple rescuers.** Decision
   1's rescue fantasy is one rescuer racing a delver's lantern
   clock, guided by a line-bell. Does it change when another
   *player* can run the rescue, plant light to stretch the
   clock, or split the search? Does every player get the
   line-bell, or only the nearest / the one who noticed?
   **DECIDED 2026-11-24 (owner):** it does not change — every
   player can run the rescue, plant light to stretch the
   clock, and split the search, and **every player hears the
   line-bell**.
3. **Player downing and rescue.** Decision 6 covers a single
   player: wake rescued at the last camp with no gear, with a
   hardcore option. In co-op, can a downed *player* be rescued
   by another player on the lantern clock (decision 1's
   mechanic, applied to players)? What happens when the last
   standing player goes down? Is hardcore per-player or
   per-colony?
4. **Contradictory same-tick commands.** Canonical order
   resolves conflicts deterministically (e.g. two players spend
   the same last goods in one tick: the earlier in `(tick,
   player, seq)` order applies, the other is recorded refused).
   Is that silent resolution the desired feel, or should
   contested actions need a claim/confirmation first?
5. **Drop-in / drop-out and host authority.** Can a player join
   a session already running (their client would replay the log
   or take a save snapshot — the foundation supports either) or
   leave without ending the colony? If a peer disconnects
   mid-session, does the colony pause for everyone, or play on
   without them? Who hosts, and does the host's copy win a
   desync dispute by definition?

## (d) Recommended first real-machine step

When the owner's PC is free, before any internet play or
frontend work: **run the S13 session as two live processes on
the owner's PC** — a host `Session` and a client `Session`,
each with its own sim, exchanging the two players' command
streams over a loopback socket (the smallest transport that can
exist), driving the exact S13 two-player script, and comparing
state hashes every 100 ticks with a hard stop on mismatch. That
single experiment exercises transport, pacing at zero real
latency, and live hash comparison end to end, and its failures
will say more about what (b) really costs than any design pass
from here. Only after loopback agreement is boring should a
second machine (LAN/Tailscale) and real latency enter the
picture.
