// SPDX-License-Identifier: MPL-2.0

use serde_json::{Value, json};
use std::fs;
use std::io::{self, BufReader, Read, Write};
use std::os::unix::fs::{DirBuilderExt, FileTypeExt, PermissionsExt};
use std::os::unix::net::{UnixListener, UnixStream};
use std::path::Path;
use std::time::{Duration, Instant};
use veil_protocol::{
    CORE_SCHEMA_V1, CoreStatus, ErrorCode, ProtocolError, Request, Response, decode_request,
    encode_line, read_frame,
};

pub const DEFAULT_SOCKET_PATH: &str = "/run/synveil/veil-core.sock";
pub mod ab;
pub mod audit;
pub mod audit_check;
pub mod audit_export;
mod audit_json;
pub mod audit_retention;
pub mod credential;
pub mod ed25519;
pub mod history;
pub mod observer;
pub mod recovery;
pub mod seat;
pub mod secret;
pub mod session;
pub mod sha256;
pub mod sha512;
pub mod supervision;
const CONNECTION_TIMEOUT: Duration = Duration::from_secs(5);
const MAX_REQUESTS_PER_CONNECTION: usize = 16;

pub fn dispatch(request: Request) -> Response {
    match request.method.as_str() {
        "status" => status(request),
        "observe" => observe(request),
        "observe-history" => observe_history(request),
        _ => Response::failure(
            request.id,
            ProtocolError::new(
                ErrorCode::UnknownMethod,
                "requested method is not registered",
            ),
        ),
    }
}

pub fn serve_path(path: &Path, max_connections: Option<usize>) -> io::Result<()> {
    // ADR 0026: the lifecycle sampler lives inside the core
    // and every serve mode funnels through here. It starts
    // only when policy enables it and is off by default.
    history::start_sampler_if_enabled();
    prepare_socket_path(path)?;
    let listener = UnixListener::bind(path)?;
    fs::set_permissions(path, fs::Permissions::from_mode(0o600))?;

    log_event(
        "socket_ready",
        json!({
            "socket": path,
            "protocol": CORE_SCHEMA_V1,
        }),
    );

    let mut accepted = 0usize;
    for incoming in listener.incoming() {
        match incoming {
            Ok(stream) => {
                accepted += 1;
                if let Err(error) = serve_connection(stream) {
                    log_event("connection_error", json!({ "error": error.to_string() }));
                }
            }
            Err(error) => {
                log_event("accept_error", json!({ "error": error.to_string() }));
            }
        }

        if max_connections.is_some_and(|limit| accepted >= limit) {
            break;
        }
    }

    drop(listener);
    match fs::remove_file(path) {
        Ok(()) => {}
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => return Err(error),
    }
    log_event("shutdown", json!({}));
    Ok(())
}

fn observe(request: Request) -> Response {
    if request
        .params
        .as_object()
        .is_some_and(|parameters| !parameters.is_empty())
    {
        return Response::failure(
            request.id,
            ProtocolError::new(
                ErrorCode::InvalidParameters,
                "observe does not accept parameters",
            ),
        );
    }
    match observer::sample() {
        Ok(value) => {
            let mut response = Response::success(request.id, value);
            if fit_observe_response(&mut response).is_err() {
                return Response::failure(
                    response.id,
                    ProtocolError::new(
                        ErrorCode::InternalFailure,
                        "kernel observation exceeds protocol response limit",
                    ),
                );
            }
            response
        }
        Err(_) => Response::failure(
            request.id,
            ProtocolError::new(
                ErrorCode::InternalFailure,
                "could not read kernel observations",
            ),
        ),
    }
}

/// Keep the actual response, including its caller-provided ID and every other
/// observation object, within the wire limit. Process records are PID-sorted,
/// so removing from the end preserves ordering and the lowest-PID prefix.
fn fit_observe_response(response: &mut Response) -> Result<(), ProtocolError> {
    loop {
        match encode_line(response) {
            Ok(_) => return Ok(()),
            Err(error) if error.code == ErrorCode::MessageTooLarge => {
                let Some(processes) = response
                    .result
                    .as_mut()
                    .and_then(|result| result.get_mut("processes"))
                    .and_then(Value::as_object_mut)
                else {
                    return Err(error);
                };
                let removed = processes
                    .get_mut("records")
                    .and_then(Value::as_array_mut)
                    .and_then(Vec::pop)
                    .is_some();
                if !removed {
                    return Err(error);
                }
                let Some(omitted) = processes
                    .get("omitted_processes")
                    .and_then(Value::as_u64)
                    .and_then(|count| count.checked_add(1))
                else {
                    return Err(error);
                };
                processes.insert("omitted_processes".to_owned(), json!(omitted));
                processes.insert("status".to_owned(), json!("truncated"));
            }
            Err(error) => return Err(error),
        }
    }
}

/// Read-only lifecycle history (ADR 0026). The sampler is
/// off by default; a disabled sampler is a state this
/// response reports, not a request failure.
fn observe_history(request: Request) -> Response {
    if request
        .params
        .as_object()
        .is_some_and(|parameters| !parameters.is_empty())
    {
        return Response::failure(
            request.id,
            ProtocolError::new(
                ErrorCode::InvalidParameters,
                "observe-history does not accept parameters",
            ),
        );
    }
    let mut response = Response::success(
        request.id,
        history::global().response(history::sampler_enabled()),
    );
    if fit_history_response(&mut response).is_err() {
        return Response::failure(
            response.id,
            ProtocolError::new(
                ErrorCode::InternalFailure,
                "lifecycle history exceeds protocol response limit",
            ),
        );
    }
    response
}

/// The 1024-event ring can exceed the wire limit, so the
/// response carries the newest events that fit: oldest
/// events are dropped from the response (never from the
/// ring) and the trim is counted in
/// `sampler.response_omitted_events`. Events are
/// sequence-ordered, so removing from the front preserves
/// order and keeps the newest window. The aggregate buckets
/// ride in the same response under the same discipline:
/// once no events remain to trim, the globally oldest
/// bucket is dropped from the response (never from the
/// store) and counted in
/// `aggregates.response_omitted_buckets`.
fn fit_history_response(response: &mut Response) -> Result<(), ProtocolError> {
    loop {
        match encode_line(response) {
            Ok(_) => return Ok(()),
            Err(error) if error.code == ErrorCode::MessageTooLarge => {
                let Some(result) = response.result.as_mut() else {
                    return Err(error);
                };
                let removed = match result.get_mut("events").and_then(Value::as_array_mut) {
                    Some(events) if !events.is_empty() => {
                        events.remove(0);
                        true
                    }
                    _ => false,
                };
                if removed {
                    let Some(omitted) = result
                        .get_mut("sampler")
                        .and_then(|sampler| sampler.get_mut("response_omitted_events"))
                        .and_then(|value| value.as_u64())
                        .and_then(|count| count.checked_add(1))
                    else {
                        return Err(error);
                    };
                    result["sampler"]["response_omitted_events"] = json!(omitted);
                    continue;
                }
                if !trim_oldest_aggregate_bucket(result) {
                    return Err(error);
                }
            }
            Err(error) => return Err(error),
        }
    }
}

/// Drop the globally oldest aggregate bucket from a
/// response copy (the store is untouched): the series whose
/// first bucket starts earliest loses that bucket, and a
/// series left empty leaves the response with it. The trim
/// is counted in `aggregates.response_omitted_buckets`.
/// Returns false when no bucket can be removed.
fn trim_oldest_aggregate_bucket(result: &mut Value) -> bool {
    let Some(aggregates) = result.get_mut("aggregates") else {
        return false;
    };
    let Some(series) = aggregates.get_mut("series").and_then(Value::as_array_mut) else {
        return false;
    };
    let mut target: Option<usize> = None;
    let mut oldest = u64::MAX;
    for (index, entry) in series.iter().enumerate() {
        if let Some(start) = entry
            .get("buckets")
            .and_then(Value::as_array)
            .and_then(|buckets| buckets.first())
            .and_then(|bucket| bucket.get("start_unix_ms"))
            .and_then(Value::as_u64)
            && start < oldest
        {
            oldest = start;
            target = Some(index);
        }
    }
    let Some(index) = target else {
        return false;
    };
    let became_empty = match series[index]
        .get_mut("buckets")
        .and_then(Value::as_array_mut)
    {
        Some(buckets) => {
            buckets.remove(0);
            buckets.is_empty()
        }
        None => false,
    };
    if became_empty {
        series.remove(index);
    }
    let Some(omitted) = aggregates
        .get_mut("response_omitted_buckets")
        .and_then(|value| value.as_u64())
        .and_then(|count| count.checked_add(1))
    else {
        return false;
    };
    aggregates["response_omitted_buckets"] = json!(omitted);
    true
}

fn status(request: Request) -> Response {
    if request
        .params
        .as_object()
        .is_some_and(|parameters| !parameters.is_empty())
    {
        return Response::failure(
            request.id,
            ProtocolError::new(
                ErrorCode::InvalidParameters,
                "status does not accept parameters",
            ),
        );
    }

    let status = CoreStatus {
        service: "veil-core".to_owned(),
        version: veil_protocol::BUILD_VERSION.to_owned(),
        protocol: CORE_SCHEMA_V1.to_owned(),
        state: "ready".to_owned(),
        persistent_audit: audit::persistent_status(),
        git_revision: veil_protocol::BUILD_REVISION.map(str::to_owned),
    };

    match serde_json::to_value(status) {
        Ok(value) => Response::success(request.id, value),
        Err(_) => Response::failure(
            request.id,
            ProtocolError::new(
                ErrorCode::InternalFailure,
                "could not serialize core status",
            ),
        ),
    }
}

fn serve_connection(stream: UnixStream) -> io::Result<()> {
    serve_connection_until(stream, Instant::now() + CONNECTION_TIMEOUT)
}

struct DeadlineReader {
    stream: UnixStream,
    deadline: Instant,
}

fn remaining(deadline: Instant) -> io::Result<Duration> {
    // Linux socket timeouts have microsecond-scale timeval granularity.
    // Refuse nearly expired deadlines rather than sending a sub-millisecond
    // duration that can round to zero or EINVAL in the OS timeout interface.
    deadline
        .checked_duration_since(Instant::now())
        .filter(|duration| *duration >= Duration::from_millis(1))
        .ok_or_else(|| io::Error::new(io::ErrorKind::TimedOut, "connection deadline exceeded"))
}

impl Read for DeadlineReader {
    fn read(&mut self, bytes: &mut [u8]) -> io::Result<usize> {
        self.stream
            .set_read_timeout(Some(remaining(self.deadline)?))?;
        self.stream.read(bytes)
    }
}

fn serve_connection_until(stream: UnixStream, deadline: Instant) -> io::Result<()> {
    let mut reader = BufReader::new(DeadlineReader {
        stream: stream.try_clone()?,
        deadline,
    });
    let mut writer = stream;

    for _ in 0..MAX_REQUESTS_PER_CONNECTION {
        remaining(deadline)?;
        let Some(line) = read_frame(&mut reader)? else {
            break;
        };
        let response = match decode_request(&line) {
            Ok(request) => {
                log_event(
                    "request",
                    json!({
                        "id": &request.id,
                        "method": &request.method,
                    }),
                );
                dispatch(request)
            }
            Err(error) => {
                log_event("request_rejected", json!({ "code": error.code.as_str() }));
                Response::failure("", error)
            }
        };

        let encoded = encode_line(&response)
            .map_err(|error| io::Error::other(format!("response encoding failed: {error}")))?;
        writer.set_write_timeout(Some(remaining(deadline)?))?;
        writer.write_all(&encoded)?;
        writer.flush()?;
    }

    Ok(())
}

fn prepare_socket_path(path: &Path) -> io::Result<()> {
    prepare_socket_path_with(path, |socket_path| UnixStream::connect(socket_path))
}

fn prepare_socket_path_with<F>(path: &Path, try_connect: F) -> io::Result<()>
where
    F: FnOnce(&Path) -> io::Result<UnixStream>,
{
    let Some(parent) = path.parent() else {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            "socket path has no parent directory",
        ));
    };
    fs::DirBuilder::new()
        .recursive(true)
        .mode(0o700)
        .create(parent)?;

    match fs::symlink_metadata(path) {
        Ok(metadata) if metadata.file_type().is_socket() => match try_connect(path) {
            Ok(_) => {
                return Err(io::Error::new(
                    io::ErrorKind::AlreadyExists,
                    "core socket is already active",
                ));
            }
            Err(error) if error.kind() == io::ErrorKind::ConnectionRefused => {
                fs::remove_file(path)?
            }
            Err(error) => return Err(error),
        },
        Ok(_) => {
            return Err(io::Error::new(
                io::ErrorKind::AlreadyExists,
                "refusing to replace non-socket path",
            ));
        }
        Err(error) if error.kind() == io::ErrorKind::NotFound => {}
        Err(error) => return Err(error),
    }

    Ok(())
}

fn log_event(event: &str, fields: serde_json::Value) {
    audit::emit(event, fields);
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;
    use std::io::{BufRead, BufReader, Write};
    use std::sync::atomic::{AtomicU64, Ordering};
    use std::thread;
    use std::time::Duration;
    use veil_protocol::{ErrorCode, Request, decode_response, encode_line};

    static NEXT_TEST_ID: AtomicU64 = AtomicU64::new(1);

    #[test]
    fn status_is_read_only_and_structured() {
        let response = dispatch(Request::new("status-1", "status", json!({})));
        assert!(response.ok);
        let result = response.result.expect("status result");
        assert_eq!(result["service"], "veil-core");
        assert_eq!(result["protocol"], CORE_SCHEMA_V1);
        assert_eq!(result["state"], "ready");
        assert_eq!(result["persistent_audit"]["configured"], false);
        assert_eq!(result["persistent_audit"]["state"], "disabled");
    }

    #[test]
    fn observe_rejects_parameters() {
        let response = dispatch(Request::new(
            "observe-bad",
            "observe",
            json!({"shell": true}),
        ));
        assert!(!response.ok);
        assert_eq!(
            response.error.expect("protocol error").code,
            ErrorCode::InvalidParameters
        );
    }

    #[test]
    fn observe_reports_kernel_values_when_procfs_available() {
        if Path::new("/proc/meminfo").is_file() && Path::new("/proc/stat").is_file() {
            let response = dispatch(Request::new("observe-1", "observe", json!({})));
            assert!(response.ok, "read-only kernel observation should succeed");
            let result = response.result.expect("observation result");
            assert_eq!(result["schema"], "synveil.observe/v1");
            assert!(result["memory"]["total_bytes"].as_u64().unwrap() > 0);
            assert!(result["cpu"]["total_ticks"].as_u64().unwrap() > 0);
        }
    }

    #[test]
    fn observe_truncates_processes_to_fit_the_complete_protocol_response() {
        let records = (1..=128)
            .map(|pid| json!({"pid": pid, "fixture": "x".repeat(256)}))
            .collect::<Vec<_>>();
        let mut response = Response::success(
            "\"\\\n".repeat(42),
            json!({
                "schema": "synveil.observe/v1",
                "fixture_other_metrics": "x".repeat(48 * 1024),
                "processes": {
                    "status": "ready",
                    "records": records,
                    "unavailable_processes": 0,
                    "omitted_processes": 0,
                    "scan_truncated": false,
                },
            }),
        );

        fit_observe_response(&mut response).unwrap();
        let encoded = encode_line(&response).unwrap();
        assert!(encoded.len() <= veil_protocol::MAX_MESSAGE_BYTES + 1);
        let processes = &response.result.as_ref().unwrap()["processes"];
        let retained = processes["records"].as_array().unwrap().len() as u64;
        let omitted = processes["omitted_processes"].as_u64().unwrap();
        assert!(retained < 128);
        assert_eq!(retained + omitted, 128);
        assert_eq!(processes["status"], "truncated");
    }

    #[test]
    fn observe_history_rejects_parameters() {
        let response = dispatch(Request::new(
            "history-bad",
            "observe-history",
            json!({"shell": true}),
        ));
        assert!(!response.ok);
        assert_eq!(
            response.error.expect("protocol error").code,
            ErrorCode::InvalidParameters
        );
    }

    #[test]
    fn observe_history_reports_the_sampler_state() {
        // The test environment does not set the policy
        // variable, so the sampler reports disabled with an
        // empty ring; the enabled path is covered by the
        // history module's own tests and the QEMU gate.
        let response = dispatch(Request::new("history-1", "observe-history", json!({})));
        assert!(response.ok);
        let result = response.result.expect("history result");
        assert_eq!(result["schema"], "synveil.observe-history/v1");
        assert_eq!(result["sampler"]["enabled"], history::sampler_enabled());
        assert_eq!(result["sampler"]["ring_capacity"], 1024);
        assert!(result["events"].is_array());
    }

    #[test]
    fn observe_history_trims_oldest_events_to_fit_the_wire_limit() {
        let events = (0..300u64)
            .map(|sequence| {
                json!({
                    "schema": "synveil.observe-event/v1",
                    "event": "process_started",
                    "sequence": sequence,
                    "fields": {"process": {"pid": sequence, "filler": "x".repeat(200)}},
                })
            })
            .collect::<Vec<_>>();
        let mut response = Response::success(
            "history-trim",
            json!({
                "schema": "synveil.observe-history/v1",
                "sampler": {
                    "enabled": true,
                    "cadence_ms": 5000,
                    "ring_capacity": 1024,
                    "retained_events": 300,
                    "dropped_events": 0,
                    "response_omitted_events": 0,
                },
                "events": events,
            }),
        );
        fit_history_response(&mut response).unwrap();
        let encoded = encode_line(&response).unwrap();
        assert!(encoded.len() <= veil_protocol::MAX_MESSAGE_BYTES + 1);
        let result = response.result.as_ref().unwrap();
        let retained = result["events"].as_array().unwrap().len() as u64;
        let omitted = result["sampler"]["response_omitted_events"]
            .as_u64()
            .unwrap();
        assert!(retained < 300);
        assert_eq!(retained + omitted, 300);
        // The retained window is the newest events.
        assert_eq!(result["events"][0]["sequence"], omitted);
    }

    #[test]
    fn observe_history_trims_oldest_aggregate_buckets_to_fit_the_wire_limit() {
        // Two series with fat buckets and no events: the fit
        // must fall through to bucket trimming, oldest first
        // across series, and account for every dropped bucket.
        let bucket = |start: u64| {
            json!({
                "start_unix_ms": start,
                "samples": 12,
                "mean": 1,
                "max": 2,
                "filler": "x".repeat(150),
            })
        };
        let series = |name: &str, starts: &[u64]| {
            json!({
                "metric": "disk.throughput.bps",
                "unit": "bytes_per_second",
                "name": name,
                "buckets": starts.iter().map(|start| bucket(*start)).collect::<Vec<_>>(),
            })
        };
        let starts_a: Vec<u64> = (0..200).map(|index| index * 60_000).collect();
        let starts_b: Vec<u64> = (0..200).map(|index| 30_000 + index * 60_000).collect();
        let mut response = Response::success(
            "history-trim-buckets",
            json!({
                "schema": "synveil.observe-history/v1",
                "sampler": {
                    "enabled": true,
                    "cadence_ms": 5000,
                    "ring_capacity": 1024,
                    "retained_events": 0,
                    "dropped_events": 0,
                    "response_omitted_events": 0,
                },
                "events": [],
                "aggregates": {
                    "bucket_ms": 60000,
                    "buckets_per_series": 60,
                    "retained_buckets": 400,
                    "dropped_buckets": 0,
                    "omitted_series": 0,
                    "response_omitted_buckets": 0,
                    "series": [series("sda", &starts_a), series("sdb", &starts_b)],
                },
            }),
        );
        fit_history_response(&mut response).unwrap();
        let encoded = encode_line(&response).unwrap();
        assert!(encoded.len() <= veil_protocol::MAX_MESSAGE_BYTES + 1);
        let result = response.result.as_ref().unwrap();
        let aggregates = &result["aggregates"];
        let retained: u64 = aggregates["series"]
            .as_array()
            .unwrap()
            .iter()
            .map(|entry| entry["buckets"].as_array().unwrap().len() as u64)
            .sum();
        let omitted = aggregates["response_omitted_buckets"].as_u64().unwrap();
        assert!(retained < 400);
        assert_eq!(retained + omitted, 400);
        // The retained buckets are the newest: the two
        // series' starts interleave every 30 s (0, 30000,
        // 60000, ...), so after `omitted` oldest-first trims
        // the earliest surviving start is exactly the
        // (omitted)-th merged start.
        let earliest = aggregates["series"]
            .as_array()
            .unwrap()
            .iter()
            .filter_map(|entry| {
                entry["buckets"]
                    .as_array()
                    .unwrap()
                    .first()
                    .map(|bucket| bucket["start_unix_ms"].as_u64().unwrap())
            })
            .min()
            .unwrap();
        assert_eq!(earliest, omitted * 30_000);
    }

    #[test]
    fn unknown_methods_are_rejected() {
        let response = dispatch(Request::new("bad-1", "root_shell", json!({})));
        assert!(!response.ok);
        assert_eq!(
            response.error.expect("protocol error").code,
            ErrorCode::UnknownMethod
        );
    }

    #[test]
    fn status_rejects_parameters() {
        let response = dispatch(Request::new("status-2", "status", json!({ "extra": true })));
        assert!(!response.ok);
        assert_eq!(
            response.error.expect("protocol error").code,
            ErrorCode::InvalidParameters
        );
    }

    #[test]
    fn connection_deadline_expires() {
        assert_eq!(
            remaining(Instant::now() - Duration::from_millis(1))
                .unwrap_err()
                .kind(),
            io::ErrorKind::TimedOut
        );
        assert!(remaining(Instant::now() + Duration::from_secs(1)).is_ok());
    }

    #[test]
    fn socket_path_refuses_regular_files_and_symlinks() {
        let path = test_socket_path();
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        fs::write(&path, "preserve").unwrap();
        assert_eq!(
            prepare_socket_path(&path).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        assert_eq!(fs::read_to_string(&path).unwrap(), "preserve");
        let link = path.with_extension("link");
        std::os::unix::fs::symlink(&path, &link).unwrap();
        assert_eq!(
            prepare_socket_path(&link).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }

    #[test]
    fn unix_socket_does_not_replace_an_active_listener() {
        let path = test_socket_path();
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        let listener = UnixListener::bind(&path).unwrap();
        assert_eq!(
            prepare_socket_path(&path).unwrap_err().kind(),
            io::ErrorKind::AlreadyExists
        );
        assert!(path.exists());
        drop(listener);
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }

    #[test]
    fn unix_socket_removes_stale_listener() {
        let path = test_socket_path();
        fs::create_dir_all(path.parent().unwrap()).unwrap();
        // Verify the refusal branch independently of kernel scheduling and
        // pending socket references in the test runner. Production still
        // probes with a real UnixStream::connect and never removes a listener
        // whose connect succeeds.
        let listener = UnixListener::bind(&path).unwrap();
        drop(listener);
        prepare_socket_path_with(&path, |_path| {
            Err(io::Error::new(
                io::ErrorKind::ConnectionRefused,
                "synthetic refused stale socket",
            ))
        })
        .expect("refused stale socket is removable");
        assert!(!path.exists());
        fs::remove_dir_all(path.parent().unwrap()).unwrap();
    }

    #[test]
    fn unix_socket_idle_peer_hits_deadline() {
        let (_client, server) = UnixStream::pair().unwrap();
        let started = Instant::now();
        let error =
            serve_connection_until(server, started + Duration::from_millis(30)).unwrap_err();
        assert!(matches!(
            error.kind(),
            io::ErrorKind::WouldBlock | io::ErrorKind::TimedOut
        ));
        assert!(started.elapsed() < Duration::from_secs(2));
    }

    #[test]
    fn unix_socket_oversize_peer_is_disconnected() {
        let (mut client, server) = UnixStream::pair().unwrap();
        let worker = thread::spawn(move || serve_connection(server));
        client
            .write_all(&vec![b'x'; veil_protocol::MAX_MESSAGE_BYTES + 1])
            .unwrap();
        assert_eq!(
            worker.join().unwrap().unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
    }

    #[test]
    fn unix_socket_rejects_unterminated_requests_and_supports_sequential_frames() {
        let (mut client, server) = UnixStream::pair().unwrap();
        let worker = thread::spawn(move || serve_connection(server));
        let request = Request::new("one", "status", json!({}));
        let mut reader = BufReader::new(client.try_clone().unwrap());
        for _ in 0..2 {
            client.write_all(&encode_line(&request).unwrap()).unwrap();
            let response = decode_response(&read_frame(&mut reader).unwrap().unwrap()).unwrap();
            assert!(response.ok);
        }
        client.write_all(b"{\"partial\":true}").unwrap();
        client.shutdown(std::net::Shutdown::Write).unwrap();
        assert_eq!(
            worker.join().unwrap().unwrap_err().kind(),
            io::ErrorKind::UnexpectedEof
        );
    }

    #[test]
    fn unix_socket_round_trip() {
        let path = test_socket_path();
        let server_path = path.clone();
        let server = thread::spawn(move || serve_path(&server_path, Some(1)));

        let mut stream = connect_with_retry(&path);
        let request = Request::new("roundtrip-1", "status", json!({}));
        stream
            .write_all(&encode_line(&request).expect("encode request"))
            .expect("write request");
        stream.flush().expect("flush request");

        let mut response_line = Vec::new();
        BufReader::new(stream)
            .read_until(b'\n', &mut response_line)
            .expect("read response");
        if response_line.last() == Some(&b'\n') {
            response_line.pop();
        }

        let response = decode_response(&response_line).expect("decode response");
        assert!(response.ok);
        assert_eq!(response.id, "roundtrip-1");

        server
            .join()
            .expect("server thread")
            .expect("server result");
        let _ = fs::remove_dir(path.parent().expect("test socket parent"));
    }

    fn test_socket_path() -> std::path::PathBuf {
        let id = NEXT_TEST_ID.fetch_add(1, Ordering::Relaxed);
        std::env::temp_dir()
            .join(format!(
                "synveil-veil-core-test-{}-{id}",
                std::process::id()
            ))
            .join("veil-core.sock")
    }

    fn connect_with_retry(path: &Path) -> UnixStream {
        for _ in 0..100 {
            match UnixStream::connect(path) {
                Ok(stream) => return stream,
                Err(error)
                    if matches!(
                        error.kind(),
                        io::ErrorKind::NotFound | io::ErrorKind::ConnectionRefused
                    ) =>
                {
                    thread::sleep(Duration::from_millis(5));
                }
                Err(error) => panic!("connect failed: {error}"),
            }
        }
        panic!("server socket was not created");
    }
}
