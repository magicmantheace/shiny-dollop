//! S13 — co-op foundations: the lockstep session layer.
//!
//! The sim has always been a pure function of its initial state and
//! command sequence (docs/MUSE_HANDOFF.md, Architecture). This
//! module makes that property usable by more than one player:
//!
//! - [`Command`] is a typed, serializable version of the player-action
//!   vocabulary the file bridge exposes (`sim/src/bin/bridge.rs`).
//!   It is a second front-end to the same operations: `apply`
//!   dispatches to exactly the `Sim` methods the bridge's handler
//!   calls, with the same arguments the bridge passes. The bridge's
//!   choreography scripts (`light_the_way`, `light_the_deep`,
//!   `open_floor1`) are *not* commands — they are multi-step founding
//!   scripts, not single sim operations, and stay bridge/scenario
//!   side.
//! - [`merge_streams`] combines per-player command streams into one
//!   canonical order — sort by `(tick, player, seq)` — independent
//!   of the order the streams arrived in.
//! - [`Session`] drives a live sim from attributed entries, and
//!   [`replay`] reconstructs a session from its [`SessionLog`] (the
//!   founding save plus the attributed entries) to the identical
//!   state hash. The canonical save + SHA-256 hash that has existed
//!   since S1 is the desync check: two peers who applied the same
//!   log hold the same hash, or one of them diverged.
//!
//! There is deliberately **no networking here** — no sockets, no
//! transport, no pacing. This is the headless-verifiable foundation
//! only; what co-op still needs beyond it is recorded in
//! `docs/COOP_ASSESSMENT.md`.
//!
//! Player ids are 1..=4 (the design's co-op size, decision: 1–4
//! co-op, not an MMO). Each player's `seq` starts at 0 and
//! increments by 1 per command that player issues.

use serde::{Deserialize, Serialize};

use crate::sim::{Job, LedgerKind, Sim};
use crate::world::Pos;

/// The design's co-op size: players are numbered 1..=4.
pub const MAX_PLAYERS: u8 = 4;

fn valid_player(player: u8) -> bool {
    (1..=MAX_PLAYERS).contains(&player)
}

/// A typed player action — the bridge's command vocabulary as a
/// serializable enum. Each variant mirrors one bridge command and
/// dispatches to the same `Sim` method with the same arguments:
///
/// | Command | Bridge `cmd` | Sim call |
/// |---|---|---|
/// | `Carve` | `carve` | `carve(pos)` |
/// | `Lantern` | `lantern` | `place_lantern(pos, tier, fuel)` (bridge: tier from the command, default 1; fuel fixed at 5,000) |
/// | `Job` | `job` | `set_job(id, job)` |
/// | `Plant` | `plant` | `plant_plot(pos)` |
/// | `CraftMask` | `craft_mask` | `craft_mask()` |
/// | `Support` | `support` | `place_support(pos)` |
/// | `Vent` | `vent` | `place_vent(pos)` |
/// | `Pump` | `pump` | `place_pump(pos)` |
/// | `CraftCooling` | `craft_cooling` | `craft_cooling_gear()` |
/// | `Descend` | `descend` | `descend()` |
/// | `Ascend` | `ascend` | `ascend()` |
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub enum Command {
    Carve { pos: Pos },
    Lantern { pos: Pos, tier: u8, fuel: f32 },
    Job { id: u32, job: Job },
    Plant { pos: Pos },
    CraftMask,
    Support { pos: Pos },
    Vent { pos: Pos },
    Pump { pos: Pos },
    CraftCooling,
    Descend,
    Ascend,
}

impl Command {
    /// Apply this command to `sim`, exactly as the bridge's handler
    /// would. Returns whether the command took effect: the `Sim`
    /// method's own `bool` where it returns one; for `carve`,
    /// whether a cell was actually carved (the bridge discards
    /// `carve`'s `Option`, but a session log needs the outcome);
    /// for `plant_plot` (which returns `()`), whether a new plot
    /// now stands at the position.
    pub fn apply(&self, sim: &mut Sim) -> bool {
        match self {
            Command::Carve { pos } => sim.carve(*pos).is_some(),
            Command::Lantern { pos, tier, fuel } => sim.place_lantern(*pos, *tier, *fuel),
            Command::Job { id, job } => sim.set_job(*id, *job),
            Command::Plant { pos } => {
                let already = sim.plots.iter().any(|p| p.pos == *pos);
                sim.plant_plot(*pos);
                !already && sim.plots.iter().any(|p| p.pos == *pos)
            }
            Command::CraftMask => sim.craft_mask(),
            Command::Support { pos } => sim.place_support(*pos),
            Command::Vent { pos } => sim.place_vent(*pos),
            Command::Pump { pos } => sim.place_pump(*pos),
            Command::CraftCooling => sim.craft_cooling_gear(),
            Command::Descend => sim.descend(),
            Command::Ascend => sim.ascend(),
        }
    }
}

/// One attributed entry in a session log: who issued what, when,
/// and whether it took effect.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct SessionEntry {
    pub tick: u64,
    pub player: u8,
    pub seq: u32,
    pub command: Command,
    pub applied: bool,
}

/// A complete, serializable record of a session: the founding
/// sim's canonical save JSON plus every attributed entry, and the
/// tick the session had reached when the log was taken (entries
/// alone do not record trailing ticks after the last command, and
/// replay must reproduce them).
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct SessionLog {
    pub founding_save: String,
    pub end_tick: u64,
    pub entries: Vec<SessionEntry>,
}

impl SessionLog {
    /// Canonical JSON (serde field order is fixed by the struct
    /// definitions; the founding save is itself canonical).
    pub fn to_json(&self) -> String {
        serde_json::to_string(self).expect("session log serialization is infallible")
    }

    pub fn from_json(s: &str) -> Result<Self, serde_json::Error> {
        serde_json::from_str(s)
    }
}

/// One command in a single player's not-yet-merged stream.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct PlayerCommand {
    pub tick: u64,
    pub seq: u32,
    pub command: Command,
}

/// A command with its attribution attached — the merge output and
/// the input a [`Session`] consumes.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct AttributedCommand {
    pub tick: u64,
    pub player: u8,
    pub seq: u32,
    pub command: Command,
}

/// Why a merge refused the streams it was given. A merge never
/// silently repairs a stream: duplicates and gaps are surfaced.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum MergeError {
    InvalidPlayer(u8),
    DuplicateSeq { player: u8, seq: u32 },
    SeqGap { player: u8, expected: u32, found: u32 },
}

impl std::fmt::Display for MergeError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            MergeError::InvalidPlayer(p) => {
                write!(f, "player id {p} is outside 1..={MAX_PLAYERS}")
            }
            MergeError::DuplicateSeq { player, seq } => {
                write!(f, "player {player} issued seq {seq} twice")
            }
            MergeError::SeqGap { player, expected, found } => {
                write!(f, "player {player}'s stream jumps from expected seq {expected} to {found}")
            }
        }
    }
}

impl std::error::Error for MergeError {}

/// Merge per-player command streams into ONE canonical order:
/// sort by `(tick, player, seq)`. The result is a total,
/// deterministic order that does not depend on the order the
/// streams arrived in — two peers merging the same streams get
/// the same sequence, which is the whole lockstep bargain.
///
/// Each stream is `(player, commands)`; a player's `seq` values
/// must start at 0 and increment by 1 with no duplicates and no
/// gaps, or the merge fails with the specific error.
pub fn merge_streams(
    streams: &[(u8, Vec<PlayerCommand>)],
) -> Result<Vec<AttributedCommand>, MergeError> {
    // Combine (a player may in principle arrive in more than one
    // delivery) and validate per player before ordering anything.
    let mut by_player: Vec<(u8, Vec<PlayerCommand>)> = Vec::new();
    for (player, cmds) in streams {
        if !valid_player(*player) {
            return Err(MergeError::InvalidPlayer(*player));
        }
        match by_player.iter_mut().find(|(p, _)| p == player) {
            Some((_, acc)) => acc.extend(cmds.iter().cloned()),
            None => by_player.push((*player, cmds.clone())),
        }
    }
    let mut merged: Vec<AttributedCommand> = Vec::new();
    for (player, mut cmds) in by_player {
        cmds.sort_by_key(|c| c.seq);
        for (i, c) in cmds.iter().enumerate() {
            if i > 0 && c.seq == cmds[i - 1].seq {
                return Err(MergeError::DuplicateSeq { player, seq: c.seq });
            }
            if c.seq != i as u32 {
                return Err(MergeError::SeqGap {
                    player,
                    expected: i as u32,
                    found: c.seq,
                });
            }
        }
        merged.extend(cmds.into_iter().map(|c| AttributedCommand {
            tick: c.tick,
            player,
            seq: c.seq,
            command: c.command,
        }));
    }
    merged.sort_by_key(|e| (e.tick, e.player, e.seq));
    Ok(merged)
}

/// Why a session refused an entry, or a replay refused a log.
#[derive(Clone, PartialEq, Eq, Debug)]
pub enum SessionError {
    InvalidPlayer(u8),
    SeqOutOfOrder { player: u8, expected: u32, found: u32 },
    TickInPast { tick: u64, current: u64 },
    EndTickBeforeEntries { end_tick: u64, last_entry_tick: u64 },
    /// Replay only: a command did something different than the
    /// log recorded — the definition of a desync.
    AppliedMismatch { player: u8, seq: u32, recorded: bool, replayed: bool },
}

impl std::fmt::Display for SessionError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            SessionError::InvalidPlayer(p) => {
                write!(f, "player id {p} is outside 1..={MAX_PLAYERS}")
            }
            SessionError::SeqOutOfOrder { player, expected, found } => {
                write!(f, "player {player}'s next seq must be {expected}, got {found}")
            }
            SessionError::TickInPast { tick, current } => {
                write!(f, "entry tick {tick} is behind the session's tick {current}")
            }
            SessionError::EndTickBeforeEntries { end_tick, last_entry_tick } => {
                write!(f, "log end_tick {end_tick} precedes its last entry at tick {last_entry_tick}")
            }
            SessionError::AppliedMismatch { player, seq, recorded, replayed } => {
                write!(f, "desync: player {player} seq {seq} recorded applied={recorded} but replays as applied={replayed}")
            }
        }
    }
}

impl std::error::Error for SessionError {}

/// A live lockstep session: one sim, driven by attributed entries
/// in canonical (merged) order, recording everything into a log
/// that [`replay`] can reconstruct exactly.
pub struct Session {
    sim: Sim,
    founding_save: String,
    entries: Vec<SessionEntry>,
}

impl Session {
    /// Found a session on `sim`. The sim's current save becomes
    /// the log's founding save.
    pub fn new(sim: Sim) -> Self {
        let founding_save = sim.save_json();
        Session { sim, founding_save, entries: Vec::new() }
    }

    /// Resume a session on a sim loaded from a mid-session save,
    /// keeping the original log (its founding save still names the
    /// session's true founding, so replay is unaffected). The
    /// loaded sim must stand exactly at the log's `end_tick` —
    /// the tick the log was snapshot at.
    pub fn resume(sim: Sim, log: SessionLog) -> Result<Self, SessionError> {
        if let Some(last) = log.entries.last() {
            if log.end_tick < last.tick {
                return Err(SessionError::EndTickBeforeEntries {
                    end_tick: log.end_tick,
                    last_entry_tick: last.tick,
                });
            }
        }
        if sim.tick_count != log.end_tick {
            return Err(SessionError::TickInPast {
                tick: log.end_tick,
                current: sim.tick_count,
            });
        }
        for e in &log.entries {
            if !valid_player(e.player) {
                return Err(SessionError::InvalidPlayer(e.player));
            }
        }
        Ok(Session { sim, founding_save: log.founding_save, entries: log.entries })
    }

    pub fn sim(&self) -> &Sim {
        &self.sim
    }

    /// The session's log so far, snapshot at the sim's current
    /// tick.
    pub fn log(&self) -> SessionLog {
        SessionLog {
            founding_save: self.founding_save.clone(),
            end_tick: self.sim.tick_count,
            entries: self.entries.clone(),
        }
    }

    /// Advance the sim to `tick` without recording anything (the
    /// run between commands). A target in the past is a no-op —
    /// time does not run backwards.
    pub fn run_to(&mut self, tick: u64) {
        while self.sim.tick_count < tick {
            self.sim.tick();
        }
    }

    /// Apply one attributed entry: advance the sim to the entry's
    /// tick, apply its command, and record the outcome. Refuses
    /// (error, nothing recorded, sim untouched) a player outside
    /// 1..=4, a `seq` that is not that player's next, or a tick in
    /// the past. A command the sim itself refuses is *not* an
    /// error: it is recorded with `applied: false`, exactly as a
    /// refused move must appear in every peer's log identically.
    pub fn apply_entry(&mut self, entry: &AttributedCommand) -> Result<bool, SessionError> {
        if !valid_player(entry.player) {
            return Err(SessionError::InvalidPlayer(entry.player));
        }
        let expected = self
            .entries
            .iter()
            .filter(|e| e.player == entry.player)
            .count() as u32;
        if entry.seq != expected {
            return Err(SessionError::SeqOutOfOrder {
                player: entry.player,
                expected,
                found: entry.seq,
            });
        }
        if entry.tick < self.sim.tick_count {
            return Err(SessionError::TickInPast {
                tick: entry.tick,
                current: self.sim.tick_count,
            });
        }
        self.run_to(entry.tick);
        let applied = entry.command.apply(&mut self.sim);
        self.entries.push(SessionEntry {
            tick: entry.tick,
            player: entry.player,
            seq: entry.seq,
            command: entry.command.clone(),
            applied,
        });
        Ok(applied)
    }

    /// Apply a merged stream in order (see [`merge_streams`]).
    pub fn apply_merged(&mut self, merged: &[AttributedCommand]) -> Result<(), SessionError> {
        for e in merged {
            self.apply_entry(e)?;
        }
        Ok(())
    }
}

/// Reconstruct a session from its log: load the founding save,
/// apply every entry in log order (advancing to each entry's
/// tick), then run on to the log's `end_tick`. A log whose stored
/// `applied` flags disagree with what the commands actually do is
/// rejected — that disagreement *is* a desync, and replay names it
/// rather than papering over it.
pub fn replay(log: &SessionLog) -> Result<Sim, SessionError> {
    if let Some(last) = log.entries.last() {
        if log.end_tick < last.tick {
            return Err(SessionError::EndTickBeforeEntries {
                end_tick: log.end_tick,
                last_entry_tick: last.tick,
            });
        }
    }
    let mut session = Session {
        sim: Sim::load_json(&log.founding_save),
        founding_save: log.founding_save.clone(),
        entries: Vec::new(),
    };
    for e in &log.entries {
        let applied = session.apply_entry(&AttributedCommand {
            tick: e.tick,
            player: e.player,
            seq: e.seq,
            command: e.command.clone(),
        })?;
        if applied != e.applied {
            return Err(SessionError::AppliedMismatch {
                player: e.player,
                seq: e.seq,
                recorded: e.applied,
                replayed: applied,
            });
        }
    }
    session.run_to(log.end_tick);
    Ok(session.sim)
}

// ---------------------------------------------------------------------------
// S15 — co-op rules (owner rulings 2026-11-24, docs/COOP_ASSESSMENT.md)
//
// S13 built the neutral lockstep foundation; this section implements
// the owner's five rulings on top of it, at the session layer only.
// `Sim` is untouched, so every pre-S15 scenario hash is unchanged.
//
// Ruling summary (full text in docs/COOP_ASSESSMENT.md (c)):
// 1. Every player has full frontier rights; Deep Ledger credit for
//    first light and rescues is SHARED by the colony — `SharedCredit`
//    has no rescuer/planter field by construction.
// 2. Any player may run a lantern-clock rescue, plant light to extend
//    the clock, or split the search; the line-bell is an event every
//    joined player sees (`CoopSession::events_visible_to`).
// 3. Hardcore is ONE colony-wide setup rule (`CoopConfig::hardcore`).
//    A downed player's rescue plays out when enabled at setup or
//    allowed by a per-incident pop-up decision
//    (`CoopSession::resolve_popup`); otherwise solo rules apply.
//    Non-hardcore solo fallback: return to the CLOSEST camp/colony,
//    gear lost. Last standing player down: non-hardcore — the clock
//    runs out and the same solo fallback applies; hardcore — the
//    run is OVER (`run_over`).
// 4. Contested same-tick actions: HOST first, then join order
//    (`merge_coop_streams`); the loser is recorded `applied: false`
//    — a quiet failure, no claim/queue system.
// 5. The host owns the game. Players join/leave a running colony
//    freely; a non-host leaving never ends it. If the HOST leaves,
//    the session pauses for everyone (commands and time itself are
//    refused) until the host returns. Authority: the host-attributed
//    canonical log order is the record `replay` reconstructs from —
//    the host's copy is the authoritative one by definition.
//
// Modelling assumptions where the rulings were silent (named in
// docs/TEST_PLAN.md S15 and the handoff): a rescue clock that runs
// out unrescued is a failed rescue — non-hardcore falls back to the
// solo return, hardcore loses the player (decision 1: permadeath
// when a rescue fails); the pop-up decision is modelled as pending
// state and the incident clock does not run while it is pending;
// a rescued player keeps their gear and wakes at the closest camp;
// players are session-layer actors (they issue `Command`s), distinct
// from the colony's delvers, so downing state lives here, not in
// `Sim`.

/// Ticks on a downed player's lantern clock (mirrors the delver
/// rescue clock, `crate::sim::DOWNED_CLOCK`).
pub const PLAYER_RESCUE_CLOCK: u32 = 900;
/// Ticks a rescue light-planting adds to a downed player's clock.
pub const LIGHT_EXTENSION_TICKS: u32 = 300;

/// Colony-wide co-op setup (ruling 3/5): chosen once, at setup.
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub struct CoopConfig {
    /// The host: owner of the game, first in contested priority.
    pub host: u8,
    /// ONE hardcore rule for the whole colony, never per-player.
    pub hardcore: bool,
    /// Lantern-clock player rescues pre-enabled at setup. When
    /// false, each downing offers the pop-up decision instead.
    pub rescue_at_setup: bool,
}

impl Default for CoopConfig {
    fn default() -> Self {
        CoopConfig { host: 1, hardcore: false, rescue_at_setup: false }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum PlayerStatus {
    Standing,
    Downed,
    Lost,
}

/// Session-layer state of one player (ruling 5's roster).
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct PlayerState {
    pub player: u8,
    /// Currently in the session. A player who left keeps their
    /// join-order slot (and may rejoin); they issue no commands
    /// while absent.
    pub present: bool,
    pub status: PlayerStatus,
    /// Gear is lost on a solo-fallback return (ruling 3), kept
    /// when rescued.
    pub has_gear: bool,
    pub pos: Pos,
}

/// Colony-shared Deep Ledger credit (ruling 1). There is
/// deliberately no field naming who planted the light or ran the
/// rescue: the credit belongs to the colony. A rescue entry names
/// only who was rescued — the Ledger's subject, as it names the
/// lost and rescued delvers — never the rescuer.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub enum SharedCredit {
    FirstLight { detail: String },
    Rescue { downed_player: u8 },
}

/// A session event. Every event is visible to every joined player
/// (ruling 2's line-bell is the load-bearing case; the rest follow
/// the same everyone-hears-it rule).
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub enum CoopEvent {
    PlayerJoined { player: u8 },
    PlayerLeft { player: u8 },
    HostLeft,
    HostReturned,
    PlayerDowned { player: u8, pos: Pos },
    /// The line-bell: rung the moment a player goes down, heard
    /// by everyone.
    LineBell { downed_player: u8, pos: Pos },
    PopupResolved { incident: u32, allowed: bool },
    RescueClockExtended { incident: u32, by: u8, clock: u32 },
    PlayerRescued { player: u8, rescuer: u8 },
    /// Solo fallback: the player woke at the closest colony/camp,
    /// gear lost.
    PlayerReturned { player: u8, camp: Pos },
    PlayerLost { player: u8 },
    RunOver,
}

/// How a downed-player incident is proceeding (ruling 3).
#[derive(Clone, Copy, PartialEq, Eq, Debug, Serialize, Deserialize)]
pub enum IncidentMode {
    /// Rescue not pre-enabled at setup: waiting on the pop-up
    /// decision. The clock does not run while pending.
    AwaitingPopup,
    /// A lantern-clock rescue may play out.
    Rescue,
    /// Last standing player down in a non-hardcore colony: no
    /// rescuer exists, so the clock simply runs out into the
    /// solo fallback.
    SoloAfterClock,
}

/// One downed-player incident.
#[derive(Clone, PartialEq, Debug, Serialize, Deserialize)]
pub struct DownedIncident {
    pub id: u32,
    pub player: u8,
    pub pos: Pos,
    /// Ticks left on the lantern clock.
    pub clock: u32,
    pub mode: IncidentMode,
    pub resolved: bool,
}

#[derive(Clone, PartialEq, Eq, Debug)]
pub enum CoopError {
    Session(SessionError),
    Merge(MergeError),
    InvalidPlayer(u8),
    AlreadyPresent(u8),
    NotPresent(u8),
    SessionFull,
    /// The host is away: the colony is paused for everyone.
    HostAbsent,
    RunOver,
    PlayerDowned(u8),
    PlayerNotStanding(u8),
    NoSuchIncident(u32),
    IncidentResolved(u32),
    IncidentNotAwaitingPopup(u32),
    IncidentNotRescuable(u32),
    CannotRescueSelf(u8),
}

impl From<SessionError> for CoopError {
    fn from(e: SessionError) -> Self {
        CoopError::Session(e)
    }
}

impl From<MergeError> for CoopError {
    fn from(e: MergeError) -> Self {
        CoopError::Merge(e)
    }
}

impl std::fmt::Display for CoopError {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        match self {
            CoopError::Session(e) => write!(f, "{e}"),
            CoopError::Merge(e) => write!(f, "{e}"),
            CoopError::InvalidPlayer(p) => {
                write!(f, "player id {p} is outside 1..={MAX_PLAYERS}")
            }
            CoopError::AlreadyPresent(p) => write!(f, "player {p} is already in the session"),
            CoopError::NotPresent(p) => write!(f, "player {p} is not in the session"),
            CoopError::SessionFull => write!(f, "the session already has {MAX_PLAYERS} players"),
            CoopError::HostAbsent => {
                write!(f, "the host has left: the colony is paused for everyone")
            }
            CoopError::RunOver => write!(f, "the run is over"),
            CoopError::PlayerDowned(p) => write!(f, "player {p} is down and cannot act"),
            CoopError::PlayerNotStanding(p) => write!(f, "player {p} is not standing"),
            CoopError::NoSuchIncident(id) => write!(f, "no downed incident {id}"),
            CoopError::IncidentResolved(id) => write!(f, "incident {id} is already resolved"),
            CoopError::IncidentNotAwaitingPopup(id) => {
                write!(f, "incident {id} is not waiting on a pop-up decision")
            }
            CoopError::IncidentNotRescuable(id) => {
                write!(f, "incident {id} has no rescue in play")
            }
            CoopError::CannotRescueSelf(p) => write!(f, "player {p} cannot rescue themselves"),
        }
    }
}

impl std::error::Error for CoopError {}

/// Merge per-player streams under ruling 4's priority: within a
/// tick, the HOST's commands come first, then the other players in
/// join order (`join_order`, host excluded), then any player not in
/// the order by id. Validation (duplicates, `seq` gaps, player
/// range) is exactly `merge_streams`' — this only re-prioritises
/// its canonical output with a stable sort, so per-player `seq`
/// order is preserved.
pub fn merge_coop_streams(
    streams: &[(u8, Vec<PlayerCommand>)],
    host: u8,
    join_order: &[u8],
) -> Result<Vec<AttributedCommand>, MergeError> {
    if !valid_player(host) {
        return Err(MergeError::InvalidPlayer(host));
    }
    let mut merged = merge_streams(streams)?;
    let priority = |p: u8| -> (usize, u8) {
        if p == host {
            (0, 0)
        } else if let Some(i) = join_order.iter().position(|j| *j == p) {
            (1 + i, 0)
        } else {
            (usize::MAX, p)
        }
    };
    merged.sort_by_key(|e| (e.tick, priority(e.player), e.seq));
    Ok(merged)
}

fn manhattan(a: Pos, b: Pos) -> i32 {
    (a.x - b.x).abs() + (a.y - b.y).abs() + (a.z - b.z).abs()
}

/// A live co-op session: an S13 [`Session`] plus the S15 rules
/// layer (roster, host pause, downed-player incidents, shared
/// credit, session events).
pub struct CoopSession {
    session: Session,
    config: CoopConfig,
    join_order: Vec<u8>,
    players: std::collections::BTreeMap<u8, PlayerState>,
    camps: Vec<Pos>,
    incidents: Vec<DownedIncident>,
    events: Vec<CoopEvent>,
    credits: Vec<SharedCredit>,
    run_over: bool,
    next_incident: u32,
}

impl CoopSession {
    /// Found a co-op session on `sim` under `config`. The host is
    /// joined first (first in join order); the founding stockpile
    /// is the colony's first camp.
    pub fn new(sim: Sim, config: CoopConfig) -> Result<Self, CoopError> {
        if !valid_player(config.host) {
            return Err(CoopError::InvalidPlayer(config.host));
        }
        let camp = sim.stockpile;
        let mut players = std::collections::BTreeMap::new();
        players.insert(
            config.host,
            PlayerState {
                player: config.host,
                present: true,
                status: PlayerStatus::Standing,
                has_gear: true,
                pos: camp,
            },
        );
        Ok(CoopSession {
            session: Session::new(sim),
            config,
            join_order: vec![config.host],
            players,
            camps: vec![camp],
            incidents: Vec::new(),
            events: vec![CoopEvent::PlayerJoined { player: config.host }],
            credits: Vec::new(),
            run_over: false,
            next_incident: 1,
        })
    }

    pub fn sim(&self) -> &Sim {
        self.session.sim()
    }

    pub fn log(&self) -> SessionLog {
        self.session.log()
    }

    pub fn config(&self) -> CoopConfig {
        self.config
    }

    pub fn run_over(&self) -> bool {
        self.run_over
    }

    /// Paused for everyone: the host is away (ruling 5).
    pub fn is_paused(&self) -> bool {
        !self.players[&self.config.host].present
    }

    pub fn player(&self, player: u8) -> Option<&PlayerState> {
        self.players.get(&player)
    }

    pub fn join_order(&self) -> &[u8] {
        &self.join_order
    }

    pub fn events(&self) -> &[CoopEvent] {
        &self.events
    }

    pub fn shared_credits(&self) -> &[SharedCredit] {
        &self.credits
    }

    pub fn incidents(&self) -> &[DownedIncident] {
        &self.incidents
    }

    /// The events a player can see. Ruling 2: the line-bell — and
    /// every session event — is visible to every player who has
    /// joined; a player who never joined sees nothing.
    pub fn events_visible_to(&self, player: u8) -> Vec<CoopEvent> {
        if self.join_order.contains(&player) {
            self.events.clone()
        } else {
            Vec::new()
        }
    }

    /// Register another colony/camp a downed player could wake at
    /// (forward camps are colonies for ruling 3's "closest").
    pub fn register_camp(&mut self, pos: Pos) {
        if !self.camps.contains(&pos) {
            self.camps.push(pos);
        }
    }

    /// The closest registered colony/camp to `pos` (Manhattan;
    /// ties break by registration order).
    pub fn closest_camp(&self, pos: Pos) -> Pos {
        self.camps
            .iter()
            .copied()
            .min_by_key(|c| manhattan(*c, pos))
            .expect("the founding camp is always registered")
    }

    /// Stage a player's position (delve movement itself is the
    /// frontend's/transport's concern in later slices).
    pub fn set_player_pos(&mut self, player: u8, pos: Pos) -> Result<(), CoopError> {
        let p = self
            .players
            .get_mut(&player)
            .ok_or(CoopError::NotPresent(player))?;
        p.pos = pos;
        Ok(())
    }

    // -- Roster (ruling 5) ------------------------------------------------

    /// Join a running colony (drop-in). A player who left rejoins
    /// into their original join-order slot.
    pub fn join(&mut self, player: u8) -> Result<(), CoopError> {
        if !valid_player(player) {
            return Err(CoopError::InvalidPlayer(player));
        }
        if self.run_over {
            return Err(CoopError::RunOver);
        }
        if let Some(p) = self.players.get_mut(&player) {
            if p.present {
                return Err(CoopError::AlreadyPresent(player));
            }
            p.present = true;
            if p.status == PlayerStatus::Lost {
                p.status = PlayerStatus::Standing;
                p.has_gear = true;
            }
        } else {
            if self.join_order.len() >= MAX_PLAYERS as usize {
                return Err(CoopError::SessionFull);
            }
            self.join_order.push(player);
            self.players.insert(
                player,
                PlayerState {
                    player,
                    present: true,
                    status: PlayerStatus::Standing,
                    has_gear: true,
                    pos: self.session.sim().stockpile,
                },
            );
        }
        self.events.push(CoopEvent::PlayerJoined { player });
        Ok(())
    }

    /// Leave the session (drop-out). A non-host leaving never ends
    /// the colony and play continues without them; the HOST
    /// leaving pauses the colony for everyone.
    pub fn leave(&mut self, player: u8) -> Result<(), CoopError> {
        let p = self
            .players
            .get_mut(&player)
            .filter(|p| p.present)
            .ok_or(CoopError::NotPresent(player))?;
        p.present = false;
        if player == self.config.host {
            self.events.push(CoopEvent::HostLeft);
        } else {
            self.events.push(CoopEvent::PlayerLeft { player });
        }
        Ok(())
    }

    /// The host returns: the pause lifts and play resumes.
    pub fn host_return(&mut self) -> Result<(), CoopError> {
        let host = self.config.host;
        let p = self
            .players
            .get_mut(&host)
            .ok_or(CoopError::NotPresent(host))?;
        if p.present {
            return Err(CoopError::AlreadyPresent(host));
        }
        p.present = true;
        self.events.push(CoopEvent::HostReturned);
        Ok(())
    }

    // -- Commands (rulings 1, 4, 5) ----------------------------------------

    fn guard_actor(&self, player: u8) -> Result<(), CoopError> {
        if self.run_over {
            return Err(CoopError::RunOver);
        }
        if self.is_paused() {
            return Err(CoopError::HostAbsent);
        }
        match self.players.get(&player) {
            Some(p) if p.present => {}
            _ => return Err(CoopError::NotPresent(player)),
        }
        if self.players[&player].status == PlayerStatus::Downed {
            return Err(CoopError::PlayerDowned(player));
        }
        if self.players[&player].status == PlayerStatus::Lost {
            return Err(CoopError::PlayerNotStanding(player));
        }
        Ok(())
    }

    /// Apply one attributed entry under the co-op rules. Frontier
    /// rights are universal (ruling 1): any present, standing
    /// player may issue any `Command` — carve, plant first light,
    /// place kit, assign jobs, spend colony goods. While the host
    /// is away every command is refused (ruling 5's pause). First
    /// light produced by the command is credited to the COLONY
    /// (`SharedCredit::FirstLight`), never to the player.
    pub fn apply_entry(&mut self, entry: &AttributedCommand) -> Result<bool, CoopError> {
        self.guard_actor(entry.player)?;
        let first_light_before = self
            .session
            .sim()
            .ledger
            .iter()
            .filter(|e| e.kind == LedgerKind::FirstLight)
            .count();
        let applied = self.session.apply_entry(entry)?;
        let new_first_light: Vec<String> = self
            .session
            .sim()
            .ledger
            .iter()
            .filter(|e| e.kind == LedgerKind::FirstLight)
            .skip(first_light_before)
            .map(|e| e.detail.clone())
            .collect();
        for detail in new_first_light {
            self.credits.push(SharedCredit::FirstLight { detail });
        }
        if let Some(p) = self.players.get_mut(&entry.player) {
            // Frontier work moves the acting player to the work:
            // carve/lantern/kit commands carry their position.
            match &entry.command {
                Command::Carve { pos }
                | Command::Lantern { pos, .. }
                | Command::Support { pos }
                | Command::Vent { pos }
                | Command::Pump { pos }
                | Command::Plant { pos } => p.pos = *pos,
                _ => {}
            }
        }
        Ok(applied)
    }

    /// Merge streams under ruling 4's priority and apply them in
    /// that order. A contested loser is recorded `applied: false`
    /// in the log — the quiet failure, exactly as S13 recorded
    /// refusals.
    pub fn apply_streams(
        &mut self,
        streams: &[(u8, Vec<PlayerCommand>)],
    ) -> Result<Vec<AttributedCommand>, CoopError> {
        let merged = merge_coop_streams(streams, self.config.host, &self.join_order)?;
        for e in &merged {
            self.apply_entry(e)?;
        }
        Ok(merged)
    }

    /// Advance the session, running downed-player clocks as time
    /// passes. Refused while the host is away — the colony pauses
    /// for everyone, time included — and after the run is over.
    pub fn run_to(&mut self, tick: u64) -> Result<(), CoopError> {
        if self.run_over {
            return Err(CoopError::RunOver);
        }
        if self.is_paused() {
            return Err(CoopError::HostAbsent);
        }
        while self.session.sim().tick_count < tick {
            let next = self.session.sim().tick_count + 1;
            self.session.run_to(next);
            self.tick_incidents();
        }
        Ok(())
    }

    // -- Downed players (rulings 2, 3) --------------------------------------

    /// A player goes down at `pos`: the line-bell rings for
    /// everyone and an incident opens. Returns the incident id.
    pub fn player_goes_down(&mut self, player: u8, pos: Pos) -> Result<u32, CoopError> {
        if self.run_over {
            return Err(CoopError::RunOver);
        }
        if self.is_paused() {
            return Err(CoopError::HostAbsent);
        }
        let p = self
            .players
            .get_mut(&player)
            .filter(|p| p.present)
            .ok_or(CoopError::NotPresent(player))?;
        if p.status != PlayerStatus::Standing {
            return Err(CoopError::PlayerNotStanding(player));
        }
        p.status = PlayerStatus::Downed;
        p.pos = pos;
        self.events.push(CoopEvent::PlayerDowned { player, pos });
        self.events.push(CoopEvent::LineBell { downed_player: player, pos });

        let id = self.next_incident;
        self.next_incident += 1;
        let last_standing = !self
            .players
            .values()
            .any(|o| o.player != player && o.present && o.status == PlayerStatus::Standing);
        let incident = if last_standing && self.config.hardcore {
            // Ruling 3, hardcore: the run is OVER.
            self.run_over = true;
            self.events.push(CoopEvent::RunOver);
            DownedIncident {
                id,
                player,
                pos,
                clock: PLAYER_RESCUE_CLOCK,
                mode: IncidentMode::SoloAfterClock,
                resolved: true,
            }
        } else if last_standing {
            DownedIncident {
                id,
                player,
                pos,
                clock: PLAYER_RESCUE_CLOCK,
                mode: IncidentMode::SoloAfterClock,
                resolved: false,
            }
        } else if self.config.rescue_at_setup {
            DownedIncident {
                id,
                player,
                pos,
                clock: PLAYER_RESCUE_CLOCK,
                mode: IncidentMode::Rescue,
                resolved: false,
            }
        } else {
            DownedIncident {
                id,
                player,
                pos,
                clock: PLAYER_RESCUE_CLOCK,
                mode: IncidentMode::AwaitingPopup,
                resolved: false,
            }
        };
        self.incidents.push(incident);
        Ok(id)
    }

    fn incident_mut(&mut self, id: u32) -> Result<&mut DownedIncident, CoopError> {
        self.incidents
            .iter_mut()
            .find(|i| i.id == id)
            .ok_or(CoopError::NoSuchIncident(id))
    }

    /// The pop-up decision (ruling 3): at the moment of a downing,
    /// the session is asked whether a lantern-clock rescue plays
    /// out. `allowed: false` applies the solo rules immediately.
    pub fn resolve_popup(&mut self, incident: u32, allowed: bool) -> Result<(), CoopError> {
        {
            let inc = self
                .incidents
                .iter()
                .find(|i| i.id == incident)
                .ok_or(CoopError::NoSuchIncident(incident))?;
            if inc.resolved {
                return Err(CoopError::IncidentResolved(incident));
            }
            if inc.mode != IncidentMode::AwaitingPopup {
                return Err(CoopError::IncidentNotAwaitingPopup(incident));
            }
        }
        self.events.push(CoopEvent::PopupResolved { incident, allowed });
        if allowed {
            self.incident_mut(incident)?.mode = IncidentMode::Rescue;
        } else {
            self.apply_solo_fallback(incident);
        }
        Ok(())
    }

    /// Solo rules (decision 6 via ruling 3): non-hardcore, the
    /// player wakes at the closest colony/camp with no gear;
    /// hardcore, a player no rescue saves is lost.
    fn apply_solo_fallback(&mut self, incident: u32) {
        let (player, pos) = {
            let inc = self
                .incidents
                .iter_mut()
                .find(|i| i.id == incident)
                .expect("incident exists");
            inc.resolved = true;
            (inc.player, inc.pos)
        };
        if self.config.hardcore {
            if let Some(p) = self.players.get_mut(&player) {
                p.status = PlayerStatus::Lost;
                p.has_gear = false;
            }
            self.events.push(CoopEvent::PlayerLost { player });
        } else {
            let camp = self.closest_camp(pos);
            if let Some(p) = self.players.get_mut(&player) {
                p.status = PlayerStatus::Standing;
                p.has_gear = false;
                p.pos = camp;
            }
            self.events.push(CoopEvent::PlayerReturned { player, camp });
        }
    }

    fn tick_incidents(&mut self) {
        let mut expired: Vec<u32> = Vec::new();
        for inc in self.incidents.iter_mut() {
            if inc.resolved {
                continue;
            }
            match inc.mode {
                IncidentMode::Rescue | IncidentMode::SoloAfterClock => {
                    inc.clock = inc.clock.saturating_sub(1);
                    if inc.clock == 0 {
                        expired.push(inc.id);
                    }
                }
                IncidentMode::AwaitingPopup => {}
            }
        }
        for id in expired {
            // A rescue clock that runs out is a failed rescue:
            // the solo fallback decides what that means.
            self.apply_solo_fallback(id);
        }
    }

    fn guard_rescuer(&self, rescuer: u8, incident: u32) -> Result<u8, CoopError> {
        if self.run_over {
            return Err(CoopError::RunOver);
        }
        if self.is_paused() {
            return Err(CoopError::HostAbsent);
        }
        let inc = self
            .incidents
            .iter()
            .find(|i| i.id == incident)
            .ok_or(CoopError::NoSuchIncident(incident))?;
        if inc.resolved {
            return Err(CoopError::IncidentResolved(incident));
        }
        if inc.mode != IncidentMode::Rescue {
            return Err(CoopError::IncidentNotRescuable(incident));
        }
        if rescuer == inc.player {
            return Err(CoopError::CannotRescueSelf(rescuer));
        }
        match self.players.get(&rescuer) {
            Some(p) if p.present && p.status == PlayerStatus::Standing => Ok(inc.player),
            Some(p) if p.present => Err(CoopError::PlayerNotStanding(rescuer)),
            _ => Err(CoopError::NotPresent(rescuer)),
        }
    }

    /// Plant light to stretch a downed player's clock (ruling 2):
    /// any standing player, through the ordinary typed `Lantern`
    /// command (so the planting is in the canonical log and itself
    /// earns the colony its shared first-light credit). A lantern
    /// the sim refuses does not stretch the clock.
    pub fn rescue_plant_light(
        &mut self,
        rescuer: u8,
        incident: u32,
        pos: Pos,
        tier: u8,
        fuel: f32,
    ) -> Result<bool, CoopError> {
        self.guard_rescuer(rescuer, incident)?;
        let seq = self
            .session
            .log()
            .entries
            .iter()
            .filter(|e| e.player == rescuer)
            .count() as u32;
        let applied = self.apply_entry(&AttributedCommand {
            tick: self.session.sim().tick_count,
            player: rescuer,
            seq,
            command: Command::Lantern { pos, tier, fuel },
        })?;
        if applied {
            let inc = self.incident_mut(incident)?;
            inc.clock += LIGHT_EXTENSION_TICKS;
            let clock = inc.clock;
            self.events
                .push(CoopEvent::RescueClockExtended { incident, by: rescuer, clock });
        }
        Ok(applied)
    }

    /// Run the rescue (ruling 2): any standing player carries the
    /// downed player home before their clock runs out. The rescued
    /// player wakes standing at the closest camp, gear kept, and
    /// the rescue is credited to the COLONY (`SharedCredit`), not
    /// to the rescuer.
    pub fn run_rescue(&mut self, rescuer: u8, incident: u32) -> Result<(), CoopError> {
        let downed = self.guard_rescuer(rescuer, incident)?;
        let (pos, clock) = {
            let inc = self.incident_mut(incident)?;
            inc.resolved = true;
            (inc.pos, inc.clock)
        };
        debug_assert!(clock > 0, "an expired incident is already resolved");
        let camp = self.closest_camp(pos);
        if let Some(p) = self.players.get_mut(&downed) {
            p.status = PlayerStatus::Standing;
            p.pos = camp;
        }
        self.credits.push(SharedCredit::Rescue { downed_player: downed });
        self.events.push(CoopEvent::PlayerRescued { player: downed, rescuer });
        Ok(())
    }
}
