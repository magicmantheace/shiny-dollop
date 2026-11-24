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
  the authoritative log/save and resync. (Whose copy is
  authoritative is no longer open: ruling 5, decided 2026-11-24
  and modelled in S15 — the host's. The recovery *protocol*
  remains unbuilt.)
- **Playing with 2–4 real clients on real machines.** Never
  done, in any form. Every S13 proof is one process applying a
  scripted merged stream to itself.

## (c) OWNER design questions — all DECIDED 2026-11-24, implemented in S15

These were the owner's calls. The session layer was built to be
neutral on all of them (attribution is recorded; no permission
is enforced anywhere), and none should be settled by an
implementer guessing. **The owner decided all five on
2026-11-24 (each ruling is recorded verbatim under its question
below), and S15 (branch `underreach-delving-colony/coop-rules`)
implements all five in the headless sim/session layer — see
section (e).**

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
   **DECIDED 2026-11-24 (owner):** hardcore is ONE rule for
   the whole colony — per-colony, never per-player. When a
   player goes down, a lantern-clock rescue is an option: it
   is either pre-chosen at game setup or offered as a pop-up
   when the downing happens, letting a lantern clock play out
   (any player may rescue, per question 2). If that option is
   not in play, a non-hardcore downing follows the normal solo
   rules (decision 6): the player wakes at the closest
   colony/camp with no gear. In a HARDCORE colony, when the
   last standing player goes down, **the run is over**.
4. **Contradictory same-tick commands.** Canonical order
   resolves conflicts deterministically (e.g. two players spend
   the same last goods in one tick: the earlier in `(tick,
   player, seq)` order applies, the other is recorded refused).
   Is that silent resolution the desired feel, or should
   contested actions need a claim/confirmation first?
   **DECIDED 2026-11-24 (owner):** priority order is HOST
   first, then everyone else in player order. On an exact tie
   over the same resource or action, the loser simply fails —
   silent refusal, no claim or confirmation mechanic. (This
   maps onto the canonical `(tick, player, seq)` order if the
   host is player 1.)
5. **Drop-in / drop-out and host authority.** Can a player join
   a session already running (their client would replay the log
   or take a save snapshot — the foundation supports either) or
   leave without ending the colony? If a peer disconnects
   mid-session, does the colony pause for everyone, or play on
   without them? Who hosts, and does the host's copy win a
   desync dispute by definition?
   **DECIDED 2026-11-24 (owner):** the host is the owner of
   the game. Players may join and leave freely; a non-host
   leaving never ends the session and play continues without
   them. If the HOST leaves, the game pauses for everyone —
   no one can play until the host returns, because the
   session lives on the host's machine.

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

## (e) S15 — the five rulings implemented (2026-11-24, VM headless)

Branch `underreach-delving-colony/coop-rules`. The rulings are
implemented as an additive rules layer in `sim/src/session.rs`
(`CoopSession`, wrapping the S13 `Session`); `Sim` is untouched,
so every pre-S15 scenario number and state hash reproduces
exactly. Verified by `sim/tests/scenario_s15.rs` (11 tests);
full suite `cargo test` **98/98** (87 pre-existing + 11 new),
0 failed. Ruling by ruling:

1. **Frontier rights / shared credit.** Any present, standing
   player may issue any typed `Command` — carve, plant first
   light, place supports/vents/pumps, assign jobs, spend colony
   goods; there is no permission check anywhere. First light
   planted through the session and every successful player
   rescue record a `SharedCredit` — a type with **no
   planter/rescuer field by construction** (a rescue credit
   names only who was rescued, the Ledger's subject). The sim's
   own `FirstLight` ledger text names no player.
2. **Multi-rescuer lantern clock.** A downing opens a
   `DownedIncident` on a 900-tick lantern clock
   (`PLAYER_RESCUE_CLOCK`, the delver clock's value) and rings
   the line-bell: a `CoopEvent::LineBell` that
   `events_visible_to` returns for **every** joined player (and
   for no one who never joined). Any standing player may plant
   light through the ordinary `Lantern` command to extend the
   clock (+300 ticks per successful planting,
   `LIGHT_EXTENSION_TICKS`) or run the rescue outright; a
   rescued player wakes standing at the closest camp, gear
   kept.
3. **Downed players.** `CoopConfig` carries the setup choices:
   `hardcore` (one colony-wide flag — there is no per-player
   hardcore state to set) and `rescue_at_setup`. Without the
   setup option, an incident waits in `AwaitingPopup` until
   `resolve_popup` decides it (the clock does not run while the
   pop-up is pending). Declined/never-enabled → solo rules:
   non-hardcore wakes the player at the **closest** registered
   camp (Manhattan over the founding stockpile plus any
   `register_camp` forward camps), gear lost. Last standing
   player down: non-hardcore → `SoloAfterClock`, the clock runs
   out and the same solo fallback applies; hardcore →
   `run_over`, and commands and time are refused from then on.
   Assumptions where the rulings were silent, named here and in
   TEST_PLAN: a rescue clock that expires unrescued is a failed
   rescue — non-hardcore falls back to the solo return,
   hardcore loses the player (decision 1's permadeath on a
   failed rescue), short of the last player so play continues.
4. **Contested actions.** `merge_coop_streams` validates exactly
   as S13's merge, then orders each tick host-first, then join
   order (a stable re-prioritisation; per-player `seq` order is
   preserved). Applied through `CoopSession`, the winner's spend
   lands and the loser is recorded `applied: false` in the
   canonical log — the quiet failure, no claim/queue — and the
   contested log replays to the live hash.
5. **Drop-in/drop-out and authority.** The roster is join-ordered
   (host first, max 4). `join` works mid-session (a returner
   reclaims their slot); a non-host `leave` never ends or pauses
   the colony, and an absent player issues no commands. The
   host leaving sets the pause: `apply_entry` and `run_to` both
   refuse with `HostAbsent` and the state hash does not move
   until `host_return`. Authority is modelled as S13 built it:
   the canonical, host-priority-ordered session log is the
   record, and `replay` reconstructs the authoritative state
   from it — the host's copy wins by definition because the
   host's ordered log *is* the copy of record.

**Slice A is the rules layer the future loopback transport will
carry.** S15 is deliberately transport-free: no sockets, no
pacing, no discovery (all still section (b)). The loopback
slice (Slice B) will move exactly these artefacts between two
processes — `CoopSession` command streams in, the canonical
log and state hash back — and its state-agreement checks will
compare the same hashes S13/S15 already pin. Nothing in the
rules layer needs to change for transport to carry it.

## (f) S17 — loopback transport (2026-11-24, VM headless)

Branch `underreach-delving-colony/loopback-transport`,
stacked on S15. This is section (d)'s recommended first
real-machine step, run as its headless form: two *processes*
on one machine (the owner's-PC run remains a hardware step;
nothing here claims a second machine, a LAN, or latency).
Verified by `sim/tests/scenario_s17.rs` (4 tests); full
suite `cargo test` **102/102** (98 pre-existing + 4 new),
0 failed, every S1–S13 scenario hash unchanged.

**What the transport carries.** Exactly the S15 artefacts,
as designed in section (e): client → host, per-player typed
command windows (the S13 `Command` vocabulary) and
lantern-clock rescue actions (`rescue_plant_light` /
`run_rescue` requests); host → clients, one `Sync` message —
the full canonical `SessionLog`, the sim's SHA-256 state
hash, and a `CoopSnapshot` of the rules layer (roster and
join order, incidents and clocks, the event feed including
the line-bell, colony-shared credit). The protocol is
newline-delimited JSON over TCP, bound to 127.0.0.1 only,
std library only (`sim/src/net.rs`; binaries `net_host` /
`net_client`).

**The authority model as implemented.** The host process is
the sole authority (ruling 5): it owns the one live
`CoopSession`, validates every incoming batch as a `seq`
continuation (the no-duplicate, no-gap rule, applied
incrementally — a gapped batch is refused to the sender
only and never enters the log), orders each delivery window
host-first then join order (ruling 4's rule, as
`merge_coop_streams` defines it), applies the window, and
broadcasts the resulting `Sync`. A client holds no state of
its own: its sim is the *replay* of the last host log it
received, accepted only when the replayed hash equals the
host's hash (a mismatch is a desync; the client exits
naming it). Proven consequences, all in the tests: host and
client finish the scripted session — ordinary commands from
both players, a contested same-tick spend over one good, a
lantern-clock rescue — with **equal hashes and byte-equal
logs**; a drop-in joiner converges from the join `Sync`
alone (the full log is the join mechanism; there is no
separate snapshot path); a client that privately applies a
divergent command stream locally is overwritten wholesale
by the next sync, and its private carve is absent from the
canonical world.

**Assumptions made (the rulings were silent).** TCP over
UDP (the log must arrive complete and ordered; simplest
std-only option); full-log syncs rather than deltas;
downings and pop-up resolutions are host-side inputs, not
wire messages (a downing is a session event, not a player
command; rescue actions *are* wire messages, per ruling 2);
a dropped socket is not a `leave` — connection loss does
not touch the roster, so the S15 host-pause is not yet
exercised over the wire; the host player is co-located with
the authority and does not use a socket. Full list in
`docs/TEST_PLAN.md` S17.

**What section (b) still lists, unchanged:** session
discovery/invitation, lockstep pacing under real latency,
Godot-side multiplayer, a desync-recovery handshake (S17's
convergence-by-next-sync is not one), and play with real
clients on real machines. The next honest step remains
section (d)'s: the same two processes on the owner's PC,
then a second machine.
