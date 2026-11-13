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
//! The same sampler tick also folds each observe snapshot's
//! windowed metrics into ephemeral 1-minute aggregates
//! (ADR 0026 decision 3): per-series buckets of mean/max for
//! `cpu.busy`, `memory.used`, `disk.throughput.bps` and
//! `net.throughput.bps`, extracted from the producer's own
//! rated values — no new kernel parsing, and a metric the
//! producer withheld is withheld here too, never invented.
//! Aggregates live in memory only, beside the event ring,
//! are served by the same `observe-history` response, and
//! are cleared by a core restart exactly like the ring.
//!
//! The sampler is OFF BY DEFAULT (owner amendment,
//! 2026-11-07): it stays off until a consumer exists, and
//! accepting the design did not switch it on.
use crate::observer;
use serde_json::{Value, json};
use std::collections::{BTreeMap, HashMap, VecDeque};
use std::sync::{Mutex, Once, OnceLock};
use std::thread;
use std::time::{Duration, SystemTime, UNIX_EPOCH};

pub const HISTORY_SCHEMA_V1: &str = "synveil.observe-history/v1";
pub const EVENT_SCHEMA_V1: &str = "synveil.observe-event/v1";
pub const SAMPLE_CADENCE: Duration = Duration::from_secs(5);
pub const RING_CAPACITY: usize = 1024;
/// Aggregation bucket width (ADR 0026: 1-minute buckets).
pub const BUCKET_MS: u64 = 60_000;
/// Buckets retained per aggregate series: one hour of
/// 1-minute buckets, hard-bounded like the event ring.
pub const AGGREGATE_BUCKETS_PER_SERIES: usize = 60;
/// Aggregate series bound: the two system series plus
/// device/interface series. Series beyond the bound are
/// counted in `omitted_series`, never silently merged.
pub const MAX_AGGREGATE_SERIES: usize = 64;
pub const METRIC_CPU_BUSY: &str = "cpu.busy";
pub const METRIC_MEMORY_USED: &str = "memory.used";
pub const METRIC_DISK_THROUGHPUT_BPS: &str = "disk.throughput.bps";
pub const METRIC_NET_THROUGHPUT_BPS: &str = "net.throughput.bps";
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
                // Metrics degrade independently, exactly as
                // the observe snapshot's own objects do: a
                // failed sample folds nothing this tick.
                if let Ok(snapshot) = observer::sample() {
                    history.record_snapshot_metrics(&snapshot, unix_time_ms_now());
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

/// One 1-minute aggregate bucket: the folded samples whose
/// timestamps fall in `[start_ms, start_ms + BUCKET_MS)`.
/// The mean is derived at response time as `sum / count`
/// (floored); the sum is u128 so a full bucket of u64 rates
/// cannot overflow.
#[derive(Clone, Copy)]
struct Bucket {
    start_ms: u64,
    sum: u128,
    count: u64,
    max: u64,
}

/// One aggregate series: a (metric, name) pair — the device
/// or interface name for the throughput metrics, a fixed
/// name for the two system metrics — with its bucket ring.
struct Series {
    unit: &'static str,
    buckets: VecDeque<Bucket>,
}

/// One metric value extracted from an observe snapshot.
struct MetricPoint {
    metric: &'static str,
    unit: &'static str,
    name: String,
    value: u64,
}

/// Extract the aggregate points from one observe snapshot,
/// using only values the producer itself rated. A metric
/// whose source is unavailable or invalid in the snapshot
/// yields no point — the aggregate store never invents a
/// value the snapshot withheld. Disk and network points are
/// per device/interface (read+write / rx+tx bytes per
/// second): devices are never summed into a system total,
/// because a partition and its whole device would
/// double-count, exactly as the snapshot itself refuses to.
fn metric_points(snapshot: &Value) -> Vec<MetricPoint> {
    let mut points = Vec::new();
    let utilization = &snapshot["cpu"]["utilization"];
    if utilization["status"] == "ready"
        && let Some(busy) = utilization["busy_basis_points"].as_u64()
    {
        points.push(MetricPoint {
            metric: METRIC_CPU_BUSY,
            unit: "basis_points",
            name: "aggregate".to_owned(),
            value: busy,
        });
    }
    if let (Some(total), Some(available)) = (
        snapshot["memory"]["total_bytes"].as_u64(),
        snapshot["memory"]["available_bytes"].as_u64(),
    ) && let Some(used) = total.checked_sub(available)
    {
        points.push(MetricPoint {
            metric: METRIC_MEMORY_USED,
            unit: "bytes",
            name: "system".to_owned(),
            value: used,
        });
    }
    if let Some(devices) = snapshot["disk"]["throughput"]["devices"].as_array() {
        for device in devices {
            let (Some(name), Some(read), Some(write)) = (
                device["name"].as_str(),
                device["read_bytes_per_sec"].as_u64(),
                device["write_bytes_per_sec"].as_u64(),
            ) else {
                continue;
            };
            let Some(total) = read.checked_add(write) else {
                continue;
            };
            points.push(MetricPoint {
                metric: METRIC_DISK_THROUGHPUT_BPS,
                unit: "bytes_per_second",
                name: name.to_owned(),
                value: total,
            });
        }
    }
    if let Some(interfaces) = snapshot["network"]["bandwidth"]["interfaces"].as_array() {
        for interface in interfaces {
            let (Some(name), Some(rx), Some(tx)) = (
                interface["name"].as_str(),
                interface["rx_bytes_per_sec"].as_u64(),
                interface["tx_bytes_per_sec"].as_u64(),
            ) else {
                continue;
            };
            let Some(total) = rx.checked_add(tx) else {
                continue;
            };
            points.push(MetricPoint {
                metric: METRIC_NET_THROUGHPUT_BPS,
                unit: "bytes_per_second",
                name: name.to_owned(),
                value: total,
            });
        }
    }
    points
}

struct State {
    events: VecDeque<Value>,
    next_sequence: u64,
    dropped_events: u64,
    previous: Option<HashMap<ProcessIdentity, Value>>,
    /// Aggregate series keyed by (metric, name); BTreeMap
    /// so the response order is deterministic.
    aggregates: BTreeMap<(String, String), Series>,
    dropped_buckets: u64,
    omitted_series: u64,
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
                aggregates: BTreeMap::new(),
                dropped_buckets: 0,
                omitted_series: 0,
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

    /// Fold one observe snapshot's metric points into the
    /// 1-minute aggregate buckets. A sample without a
    /// timestamp cannot be bucketed and folds nothing; a
    /// sample stamped into an already-closed bucket (the
    /// clock stepped backwards) is skipped rather than
    /// rewriting a closed bucket. Returns the number of
    /// points folded.
    pub fn record_snapshot_metrics(&self, snapshot: &Value, unix_time_ms: Option<u64>) -> usize {
        let Some(now_ms) = unix_time_ms else {
            return 0;
        };
        let points = metric_points(snapshot);
        if points.is_empty() {
            return 0;
        }
        let bucket_start = now_ms / BUCKET_MS * BUCKET_MS;
        let mut state = self.state.lock().expect("history state poisoned");
        let mut folded = 0usize;
        for point in points {
            let key = (point.metric.to_owned(), point.name);
            if !state.aggregates.contains_key(&key) {
                if state.aggregates.len() >= MAX_AGGREGATE_SERIES {
                    state.omitted_series += 1;
                    continue;
                }
                state.aggregates.insert(
                    key.clone(),
                    Series {
                        unit: point.unit,
                        buckets: VecDeque::new(),
                    },
                );
            }
            let mut evicted = false;
            {
                let series = state
                    .aggregates
                    .get_mut(&key)
                    .expect("aggregate series just inserted or present");
                match series.buckets.back_mut() {
                    Some(bucket) if bucket.start_ms == bucket_start => {
                        bucket.sum += u128::from(point.value);
                        bucket.count += 1;
                        bucket.max = bucket.max.max(point.value);
                    }
                    Some(bucket) if bucket.start_ms > bucket_start => {
                        // Stale sample: its bucket is already
                        // closed. Skip it; history is append-only.
                        continue;
                    }
                    _ => {
                        if series.buckets.len() == AGGREGATE_BUCKETS_PER_SERIES {
                            series.buckets.pop_front();
                            evicted = true;
                        }
                        series.buckets.push_back(Bucket {
                            start_ms: bucket_start,
                            sum: u128::from(point.value),
                            count: 1,
                            max: point.value,
                        });
                    }
                }
            }
            if evicted {
                state.dropped_buckets += 1;
            }
            folded += 1;
        }
        folded
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
    /// reports the trim in the sampler object). `aggregates`
    /// carries the ephemeral 1-minute buckets beside the
    /// ring; the dispatcher trims its oldest buckets the
    /// same way once the events no longer need trimming
    /// (counted in `response_omitted_buckets`).
    pub fn response(&self, enabled: bool) -> Value {
        let state = self.state.lock().expect("history state poisoned");
        let mut retained_buckets = 0u64;
        let series = state
            .aggregates
            .iter()
            .map(|((metric, name), series)| {
                retained_buckets += series.buckets.len() as u64;
                let buckets = series
                    .buckets
                    .iter()
                    .map(|bucket| {
                        json!({
                            "start_unix_ms": bucket.start_ms,
                            "samples": bucket.count,
                            "mean": u64::try_from(bucket.sum / u128::from(bucket.count))
                                .unwrap_or(u64::MAX),
                            "max": bucket.max,
                        })
                    })
                    .collect::<Vec<_>>();
                json!({
                    "metric": metric,
                    "unit": series.unit,
                    "name": name,
                    "buckets": buckets,
                })
            })
            .collect::<Vec<_>>();
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
            "aggregates": {
                "bucket_ms": BUCKET_MS,
                "buckets_per_series": AGGREGATE_BUCKETS_PER_SERIES,
                "retained_buckets": retained_buckets,
                "dropped_buckets": state.dropped_buckets,
                "omitted_series": state.omitted_series,
                "response_omitted_buckets": 0,
                "series": series,
            },
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

    /// A minimal observe snapshot fixture with one rated
    /// disk device and one rated network interface.
    fn snapshot(busy: u64, used: u64, disk_read: u64, disk_write: u64, rx: u64, tx: u64) -> Value {
        json!({
            "schema": "synveil.observe/v1",
            "cpu": {"utilization": {
                "status": "ready",
                "busy_basis_points": busy,
                "sample_window_ms": 100,
            }},
            "memory": {
                "total_bytes": used + 1000,
                "available_bytes": 1000,
            },
            "disk": {"throughput": {
                "status": "ready",
                "devices": [{
                    "name": "sda",
                    "read_bytes_per_sec": disk_read,
                    "write_bytes_per_sec": disk_write,
                }],
            }},
            "network": {"bandwidth": {
                "status": "ready",
                "interfaces": [{
                    "name": "eth0",
                    "rx_bytes_per_sec": rx,
                    "tx_bytes_per_sec": tx,
                }],
            }},
        })
    }

    fn series_of<'a>(response: &'a Value, metric: &str, name: &str) -> &'a Value {
        response["aggregates"]["series"]
            .as_array()
            .unwrap()
            .iter()
            .find(|series| series["metric"] == metric && series["name"] == name)
            .expect("series present")
    }

    #[test]
    fn metric_points_extract_only_producer_rated_values() {
        let points = metric_points(&snapshot(2500, 4000, 100, 50, 30, 20));
        assert_eq!(points.len(), 4);
        let by_metric: std::collections::HashMap<&str, u64> = points
            .iter()
            .map(|point| (point.metric, point.value))
            .collect();
        assert_eq!(by_metric[METRIC_CPU_BUSY], 2500);
        assert_eq!(by_metric[METRIC_MEMORY_USED], 4000);
        // Per-device read+write, never summed across devices.
        assert_eq!(by_metric[METRIC_DISK_THROUGHPUT_BPS], 150);
        assert_eq!(by_metric[METRIC_NET_THROUGHPUT_BPS], 50);
        // Withheld sources yield no point at all.
        let mut withheld = snapshot(0, 0, 0, 0, 0, 0);
        withheld["cpu"]["utilization"] = json!({"status": "unavailable"});
        withheld["disk"]["throughput"] = json!({"status": "unavailable", "devices": []});
        withheld["network"]["bandwidth"] = json!({"status": "unavailable", "interfaces": []});
        let points = metric_points(&withheld);
        assert_eq!(points.len(), 1);
        assert_eq!(points[0].metric, METRIC_MEMORY_USED);
        // Inconsistent memory (available above total) is
        // withheld too, not clamped into a fake value.
        let mut inconsistent = snapshot(0, 0, 0, 0, 0, 0);
        inconsistent["memory"]["available_bytes"] = json!(u64::MAX);
        assert!(
            metric_points(&inconsistent)
                .iter()
                .all(|point| point.metric != METRIC_MEMORY_USED)
        );
    }

    #[test]
    fn metrics_fold_into_one_minute_buckets_with_mean_and_max() {
        let history = History::new();
        let base = 1_700_000_040_000u64; // exactly on a minute boundary
        let folded = history.record_snapshot_metrics(&snapshot(1000, 100, 0, 0, 0, 0), Some(base));
        assert_eq!(folded, 4);
        // Same minute: folds into the open bucket.
        let folded =
            history.record_snapshot_metrics(&snapshot(3000, 300, 0, 0, 0, 0), Some(base + 5_000));
        assert_eq!(folded, 4);
        // Next minute: a new bucket opens.
        history.record_snapshot_metrics(&snapshot(2000, 200, 0, 0, 0, 0), Some(base + BUCKET_MS));
        let response = history.response(true);
        let cpu = series_of(&response, METRIC_CPU_BUSY, "aggregate");
        assert_eq!(cpu["unit"], "basis_points");
        let buckets = cpu["buckets"].as_array().unwrap();
        assert_eq!(buckets.len(), 2);
        assert_eq!(buckets[0]["start_unix_ms"], base);
        assert_eq!(buckets[0]["samples"], 2);
        assert_eq!(buckets[0]["mean"], 2000);
        assert_eq!(buckets[0]["max"], 3000);
        assert_eq!(buckets[1]["start_unix_ms"], base + BUCKET_MS);
        assert_eq!(buckets[1]["samples"], 1);
        assert_eq!(buckets[1]["mean"], 2000);
        let memory = series_of(&response, METRIC_MEMORY_USED, "system");
        assert_eq!(memory["buckets"][0]["mean"], 200);
        assert_eq!(memory["buckets"][0]["max"], 300);
        let disk = series_of(&response, METRIC_DISK_THROUGHPUT_BPS, "sda");
        assert_eq!(disk["unit"], "bytes_per_second");
        // Four series (cpu, memory, sda, eth0) x two buckets.
        assert_eq!(response["aggregates"]["retained_buckets"], 8);
        assert_eq!(response["aggregates"]["bucket_ms"], BUCKET_MS);
        assert_eq!(response["aggregates"]["dropped_buckets"], 0);
    }

    #[test]
    fn metrics_without_a_timestamp_or_from_a_closed_bucket_fold_nothing() {
        let history = History::new();
        let base = 1_700_000_040_000u64;
        assert_eq!(
            history.record_snapshot_metrics(&snapshot(1000, 100, 0, 0, 0, 0), None),
            0
        );
        history.record_snapshot_metrics(&snapshot(1000, 100, 0, 0, 0, 0), Some(base + BUCKET_MS));
        // A sample stamped in the earlier, now-closed bucket
        // is skipped rather than rewriting history.
        let folded = history.record_snapshot_metrics(&snapshot(9000, 900, 0, 0, 0, 0), Some(base));
        assert_eq!(folded, 0);
        let response = history.response(true);
        let cpu = series_of(&response, METRIC_CPU_BUSY, "aggregate");
        assert_eq!(cpu["buckets"].as_array().unwrap().len(), 1);
        assert_eq!(cpu["buckets"][0]["max"], 1000);
    }

    #[test]
    fn aggregate_buckets_are_bounded_per_series() {
        let history = History::new();
        let base = 1_700_000_040_000u64;
        for index in 0..(AGGREGATE_BUCKETS_PER_SERIES as u64 + 5) {
            history.record_snapshot_metrics(
                &snapshot(1000, 100, 0, 0, 0, 0),
                Some(base + index * BUCKET_MS),
            );
        }
        let response = history.response(true);
        let cpu = series_of(&response, METRIC_CPU_BUSY, "aggregate");
        let buckets = cpu["buckets"].as_array().unwrap();
        assert_eq!(buckets.len(), AGGREGATE_BUCKETS_PER_SERIES);
        // The retained window is the newest hour.
        assert_eq!(buckets[0]["start_unix_ms"], base + 5 * BUCKET_MS);
        // dropped_buckets is store-wide: all four series in
        // the fixture (cpu, memory, sda, eth0) evicted five
        // buckets each.
        assert_eq!(response["aggregates"]["dropped_buckets"], 20);
    }

    #[test]
    fn aggregate_series_are_bounded_and_counted() {
        let history = History::new();
        let mut crowded = snapshot(1000, 100, 0, 0, 0, 0);
        let devices: Vec<Value> = (0..70)
            .map(|index| {
                json!({
                    "name": format!("sd{index}"),
                    "read_bytes_per_sec": 1,
                    "write_bytes_per_sec": 2,
                })
            })
            .collect();
        crowded["disk"]["throughput"]["devices"] = Value::Array(devices);
        history.record_snapshot_metrics(&crowded, Some(1_700_000_040_000));
        let response = history.response(true);
        let series = response["aggregates"]["series"].as_array().unwrap();
        assert_eq!(series.len(), MAX_AGGREGATE_SERIES);
        // cpu + memory + eth0 + 70 disks = 73 candidate
        // series; 64 fit, 9 are counted as omitted.
        assert_eq!(response["aggregates"]["omitted_series"], 9);
    }

    #[test]
    fn response_reports_empty_aggregates_before_any_sample() {
        let history = History::new();
        let response = history.response(false);
        let aggregates = &response["aggregates"];
        assert_eq!(aggregates["bucket_ms"], BUCKET_MS);
        assert_eq!(aggregates["retained_buckets"], 0);
        assert_eq!(aggregates["response_omitted_buckets"], 0);
        assert!(aggregates["series"].as_array().unwrap().is_empty());
    }
}
