// SPDX-License-Identifier: MPL-2.0
//! Observer lifecycle history (ADR 0026, docs/OBSERVER_HISTORY_DESIGN.md).
//!
//! A sampler thread inside veil-core, enabled only when the
//! `SYNVEIL_OBSERVE_HISTORY` policy variable is present in the
//! core's environment (the same opt-in idiom as the audit
//! journal's `SYNVEIL_AUDIT_PATH`), takes a full process
//! snapshot every 5 s and diffs consecutive snapshots by
//! (pid, start_time_ticks) identity. The diff becomes
//! `synveil.observe-event/v1` lifecycle records —
//! `process_started` / `process_exited`, exits carrying the
//! final observed cumulative counters — kept in a bounded
//! in-memory ring (1024 events) and served read-only by the
//! `observe-history` request.
//!
//! Events are telemetry, not audit: they never enter the
//! hash-chained audit journal, nothing is written to disk,
//! and a core restart clears the ring. Processes that start
//! and exit between samples are missed by construction;
//! catching them would need eBPF or netlink process events,
//! which ADR 0026 explicitly does not authorize.
//!
//! The sampler is OFF BY DEFAULT (owner amendment,
//! 2026-11-07): it stays off until a consumer exists, and
//! accepting the design did not switch it on.
use crate::observer;
use serde_json::{Value, json};
use std::collections::{HashMap, VecDeque};
use std::sync::{Mutex, Once, OnceLock};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub const HISTORY_SCHEMA_V1: &str = "synveil.observe-history/v1";
pub const EVENT_SCHEMA_V1: &str = "synveil.observe-event/v1";
pub const SAMPLE_CADENCE: Duration = Duration::from_secs(5);
pub const RING_CAPACITY: usize = 1024;
const ENABLE_ENV: &str = "SYNVEIL_OBSERVE_HISTORY";

/// Policy gate for the sampler: the variable's presence in
/// the core's environment enables it, mirroring
/// `SYNVEIL_AUDIT_PATH`. Unset means off — the default state.
pub fn sampler_enabled() -> bool {
    std::env::var_os(ENABLE_ENV).is_some()
}

/// The process-wide history store the sampler fills and the
/// `observe-history` handler reads.
pub fn global() -> &'static History {
    static HISTORY: OnceLock<History> = OnceLock::new();
    HISTORY.get_or_init(History::new)
}

/// Start the sampler thread if policy enables it. Called
/// once from `serve_path`, which every core mode (plain,
/// `--once`, supervised worker) funnels through. A no-op
/// when the sampler is off or already running.
pub fn start_sampler_if_enabled() {
    static START: Once = Once::new();
    if !sampler_enabled() {
        return;
    }
    START.call_once(|| {
        thread::spawn(|| {
            let history = global();
            loop {
                // A failed scan leaves the previous snapshot
                // untouched: a transient /proc failure must
                // not manufacture a ring of false exits.
                if let Some(records) = observer::current_process_records() {
                    history.record_sample(&records, unix_time_ms_now());
                }
                thread::sleep(SAMPLE_CADENCE);
            }
        });
    });
}

fn unix_time_ms_now() -> Option<u64> {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .ok()
        .and_then(|duration| u64::try_from(duration.as_millis()).ok())
}

type ProcessIdentity = (u64, u64);

fn identity_of(record: &Value) -> Option<ProcessIdentity> {
    Some((
        record.get("pid")?.as_u64()?,
        record.get("start_time_ticks")?.as_u64()?,
    ))
}

struct State {
    events: VecDeque<Value>,
    next_sequence: u64,
    dropped_events: u64,
    previous: Option<HashMap<ProcessIdentity, Value>>,
}

/// The bounded lifecycle event ring plus the last snapshot
/// it diffed against. All state is in memory only.
pub struct History {
    state: Mutex<State>,
}

impl Default for History {
    fn default() -> Self {
        Self::new()
    }
}

impl History {
    pub fn new() -> Self {
        History {
            state: Mutex::new(State {
                events: VecDeque::new(),
                next_sequence: 0,
                dropped_events: 0,
                previous: None,
            }),
        }
    }

    /// Diff one full process snapshot against the previous
    /// one and append the lifecycle events. The first sample
    /// only establishes the baseline — processes already
    /// alive when the sampler starts are not "started".
    /// Returns the number of events appended.
    pub fn record_sample(&self, records: &[Value], unix_time_ms: Option<u64>) -> usize {
        let mut current: HashMap<ProcessIdentity, Value> = HashMap::with_capacity(records.len());
        for record in records {
            if let Some(identity) = identity_of(record) {
                current.insert(identity, record.clone());
            }
        }
        let mut state = self.state.lock().expect("history state poisoned");
        let Some(previous) = state.previous.take() else {
            state.previous = Some(current);
            return 0;
        };
        // Exits first: when a PID is reused inside one
        // interval, the old process's exit precedes the new
        // process's start for the same pid. Both sets are
        // PID-ordered so the emitted order is deterministic.
        let mut exited: Vec<&Value> = previous
            .iter()
            .filter(|(identity, _)| !current.contains_key(*identity))
            .map(|(_, record)| record)
            .collect();
        exited.sort_by_key(|record| record.get("pid").and_then(Value::as_u64).unwrap_or(0));
        let mut started: Vec<&Value> = current
            .iter()
            .filter(|(identity, _)| !previous.contains_key(*identity))
            .map(|(_, record)| record)
            .collect();
        started.sort_by_key(|record| record.get("pid").and_then(Value::as_u64).unwrap_or(0));
        let mut appended = 0usize;
        for record in exited {
            self.push_event(&mut state, "process_exited", record, unix_time_ms);
            appended += 1;
        }
        for record in started {
            self.push_event(&mut state, "process_started", record, unix_time_ms);
            appended += 1;
        }
        state.previous = Some(current);
        appended
    }

    fn push_event(
        &self,
        state: &mut State,
        event: &str,
        record: &Value,
        unix_time_ms: Option<u64>,
    ) {
        let sequence = state.next_sequence;
        state.next_sequence += 1;
        let value = json!({
            "schema": EVENT_SCHEMA_V1,
            "component": "veil-core",
            "pid": std::process::id(),
            "sequence": sequence,
            "unix_time_ms": unix_time_ms,
            "version": veil_protocol::BUILD_VERSION,
            "git_revision": veil_protocol::BUILD_REVISION,
            "event": event,
            "fields": {
                "process": {
                    "pid": record.get("pid").cloned().unwrap_or(Value::Null),
                    "parent_pid": record.get("parent_pid").cloned().unwrap_or(Value::Null),
                    "start_time_ticks": record.get("start_time_ticks").cloned().unwrap_or(Value::Null),
                    "user_ticks": record.get("user_ticks").cloned().unwrap_or(Value::Null),
                    "system_ticks": record.get("system_ticks").cloned().unwrap_or(Value::Null),
                },
            },
        });
        if state.events.len() == RING_CAPACITY {
            state.events.pop_front();
            state.dropped_events += 1;
        }
        state.events.push_back(value);
    }

    /// The `observe-history` response document. `events` is
    /// the retained ring, oldest first; the dispatcher trims
    /// it from the front when the wire limit requires (and
    /// reports the trim in the sampler object).
    pub fn response(&self, enabled: bool) -> Value {
        let state = self.state.lock().expect("history state poisoned");
        json!({
            "schema": HISTORY_SCHEMA_V1,
            "sampler": {
                "enabled": enabled,
                "cadence_ms": u64::try_from(SAMPLE_CADENCE.as_millis()).unwrap_or(u64::MAX),
                "ring_capacity": RING_CAPACITY,
                "retained_events": state.events.len(),
                "dropped_events": state.dropped_events,
                "response_omitted_events": 0,
            },
            "events": Value::Array(state.events.iter().cloned().collect()),
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn record(pid: u64, start: u64, user: u64, system: u64) -> Value {
        json!({
            "pid": pid,
            "parent_pid": 1,
            "process_group_id": pid,
            "session_id": 1,
            "state": "S",
            "user_ticks": user,
            "system_ticks": system,
            "start_time_ticks": start,
            "virtual_memory_bytes": 4096,
            "resident_pages": 10,
            "thread_count": 1,
            "nice": 0,
        })
    }

    fn events_of(history: &History) -> Vec<Value> {
        history
            .state
            .lock()
            .unwrap()
            .events
            .iter()
            .cloned()
            .collect()
    }

    #[test]
    fn first_sample_is_a_silent_baseline() {
        let history = History::new();
        let appended = history.record_sample(&[record(10, 100, 3, 1)], Some(1000));
        assert_eq!(appended, 0);
        assert!(events_of(&history).is_empty());
    }

    #[test]
    fn start_and_exit_events_carry_identity_and_final_counters() {
        let history = History::new();
        history.record_sample(&[record(10, 100, 3, 1), record(11, 200, 0, 0)], Some(1000));
        // pid 11 exits (last seen with user 5 / system 2),
        // pid 12 starts; pid 10 persists unchanged.
        let appended = history.record_sample(&[record(10, 100, 4, 1)], Some(6000));
        assert_eq!(appended, 1);
        let appended =
            history.record_sample(&[record(10, 100, 4, 1), record(12, 300, 1, 0)], Some(11000));
        assert_eq!(appended, 1);
        let events = events_of(&history);
        assert_eq!(events.len(), 2);
        let exited = &events[0];
        assert_eq!(exited["schema"], EVENT_SCHEMA_V1);
        assert_eq!(exited["event"], "process_exited");
        assert_eq!(exited["unix_time_ms"], 6000);
        assert_eq!(exited["fields"]["process"]["pid"], 11);
        assert_eq!(exited["fields"]["process"]["start_time_ticks"], 200);
        assert_eq!(exited["fields"]["process"]["user_ticks"], 0);
        let started = &events[1];
        assert_eq!(started["event"], "process_started");
        assert_eq!(started["fields"]["process"]["pid"], 12);
        assert_eq!(started["fields"]["process"]["start_time_ticks"], 300);
        assert!(started["sequence"].as_u64().unwrap() > exited["sequence"].as_u64().unwrap());
    }

    #[test]
    fn exit_counters_are_the_last_observed_values() {
        let history = History::new();
        history.record_sample(&[record(11, 200, 0, 0)], Some(1000));
        history.record_sample(&[record(11, 200, 5, 2)], Some(6000));
        let appended = history.record_sample(&[], Some(11000));
        assert_eq!(appended, 1);
        let events = events_of(&history);
        assert_eq!(events[0]["event"], "process_exited");
        assert_eq!(events[0]["fields"]["process"]["user_ticks"], 5);
        assert_eq!(events[0]["fields"]["process"]["system_ticks"], 2);
    }

    #[test]
    fn pid_reuse_is_an_exit_then_a_start() {
        let history = History::new();
        history.record_sample(&[record(10, 100, 3, 1)], Some(1000));
        let appended = history.record_sample(&[record(10, 999, 0, 0)], Some(6000));
        assert_eq!(appended, 2);
        let events = events_of(&history);
        assert_eq!(events[0]["event"], "process_exited");
        assert_eq!(events[0]["fields"]["process"]["start_time_ticks"], 100);
        assert_eq!(events[1]["event"], "process_started");
        assert_eq!(events[1]["fields"]["process"]["start_time_ticks"], 999);
    }

    #[test]
    fn ring_is_bounded_and_counts_drops() {
        let history = History::new();
        history.record_sample(&[], Some(0));
        let mut pid = 100u64;
        for index in 0..(RING_CAPACITY + 10) {
            pid += 1;
            // One start, then one exit, per iteration.
            history.record_sample(&[record(pid, pid * 10, 0, 0)], Some(index as u64));
            history.record_sample(&[], Some(index as u64));
        }
        let response = history.response(true);
        assert_eq!(response["sampler"]["ring_capacity"], RING_CAPACITY);
        assert_eq!(
            response["sampler"]["retained_events"].as_u64().unwrap(),
            RING_CAPACITY as u64
        );
        assert!(response["sampler"]["dropped_events"].as_u64().unwrap() > 0);
        let events = response["events"].as_array().unwrap();
        assert_eq!(events.len(), RING_CAPACITY);
        // Sequences in the retained window are strictly
        // increasing and end at the newest event.
        let sequences: Vec<u64> = events
            .iter()
            .map(|event| event["sequence"].as_u64().unwrap())
            .collect();
        assert!(sequences.windows(2).all(|pair| pair[0] < pair[1]));
    }

    #[test]
    fn response_reports_sampler_state() {
        let history = History::new();
        let response = history.response(false);
        assert_eq!(response["schema"], HISTORY_SCHEMA_V1);
        assert_eq!(response["sampler"]["enabled"], false);
        assert_eq!(response["sampler"]["cadence_ms"], 5000);
        assert_eq!(response["events"].as_array().unwrap().len(), 0);
    }

    #[test]
    fn malformed_records_are_ignored_by_the_diff() {
        let history = History::new();
        history.record_sample(&[json!({"pid": 5})], Some(0));
        let appended = history.record_sample(&[json!({"pid": 5})], Some(5000));
        assert_eq!(appended, 0);
    }
}
