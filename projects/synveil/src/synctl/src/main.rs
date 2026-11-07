// SPDX-License-Identifier: MPL-2.0

use serde_json::{Value, json};
use std::env;
use std::io::{self, BufReader, Write};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::process::ExitCode;
use std::time::Duration;
use veil_protocol::{Request, Response, decode_response, encode_line, read_frame};

const DEFAULT_SOCKET_PATH: &str = "/run/synveil/veil-core.sock";

fn main() -> ExitCode {
    match run() {
        Ok(code) => code,
        Err(error) => {
            eprintln!("synctl: {error}");
            ExitCode::FAILURE
        }
    }
}

fn run() -> Result<ExitCode, Box<dyn std::error::Error>> {
    let mut socket = env::var_os("SYNVEIL_CORE_SOCKET")
        .map(PathBuf::from)
        .unwrap_or_else(|| PathBuf::from(DEFAULT_SOCKET_PATH));
    let mut json_output = false;
    let mut command = None;

    let mut arguments = env::args_os().skip(1);
    while let Some(argument) = arguments.next() {
        match argument.to_string_lossy().as_ref() {
            "--socket" => {
                let value = arguments.next().ok_or_else(|| {
                    io::Error::new(io::ErrorKind::InvalidInput, "--socket requires a path")
                })?;
                socket = PathBuf::from(value);
            }
            "--json" => json_output = true,
            "--version" => {
                println!(
                    "synctl {} {}",
                    veil_protocol::BUILD_VERSION,
                    veil_protocol::BUILD_REVISION.unwrap_or("unknown")
                );
                return Ok(ExitCode::SUCCESS);
            }
            "--help" | "-h" => {
                print_help();
                return Ok(ExitCode::SUCCESS);
            }
            value if command.is_none() => command = Some(value.to_owned()),
            value => {
                return Err(io::Error::new(
                    io::ErrorKind::InvalidInput,
                    format!("unexpected argument: {value}"),
                )
                .into());
            }
        }
    }

    let command = command.unwrap_or_else(|| "status".to_owned());
    if command != "status" && command != "observe" && command != "observe-history" {
        return Err(io::Error::new(
            io::ErrorKind::InvalidInput,
            format!("unknown command: {command}"),
        )
        .into());
    }

    let request = Request::new(
        format!("synctl-{}", std::process::id()),
        &command,
        json!({}),
    );

    let mut stream = UnixStream::connect(&socket)?;
    stream.set_read_timeout(Some(Duration::from_secs(5)))?;
    stream.set_write_timeout(Some(Duration::from_secs(5)))?;
    stream.write_all(&encode_line(&request)?)?;
    stream.flush()?;

    let line = read_frame(&mut BufReader::new(stream))?
        .ok_or_else(|| io::Error::new(io::ErrorKind::UnexpectedEof, "core returned no response"))?;
    let response = decode_response(&line)?;
    validate_correlation(&response, &request.id)?;
    if command == "observe" && response.ok {
        validate_observe_result(response.result.as_ref().expect("validated response"))?;
    }
    if command == "observe-history" && response.ok {
        validate_history_result(response.result.as_ref().expect("validated response"))?;
    }

    if json_output {
        println!("{}", serde_json::to_string_pretty(&response)?);
    } else if response.ok {
        println!(
            "{}",
            serde_json::to_string_pretty(response.result.as_ref().expect("validated response"))?
        );
    } else {
        let error = response.error.as_ref().expect("validated response");
        eprintln!("synctl: {}: {}", error.code, error.message);
        return Ok(ExitCode::FAILURE);
    }

    Ok(response_exit_code(&response))
}

fn response_exit_code(response: &Response) -> ExitCode {
    if response.ok {
        ExitCode::SUCCESS
    } else {
        ExitCode::FAILURE
    }
}

fn validate_correlation(response: &Response, id: &str) -> io::Result<()> {
    if response.id != id {
        return Err(io::Error::new(
            io::ErrorKind::InvalidData,
            "core response id does not match request",
        ));
    }
    Ok(())
}

fn validate_observe_result(result: &Value) -> io::Result<()> {
    let invalid = || io::Error::new(io::ErrorKind::InvalidData, "invalid observe response");
    if result.get("schema").and_then(Value::as_str) != Some("synveil.observe/v1") {
        return Err(invalid());
    }
    let utilization = result
        .get("cpu")
        .and_then(|cpu| cpu.get("utilization"))
        .ok_or_else(invalid)?;
    match utilization.get("status").and_then(Value::as_str) {
        Some("unavailable") => Ok(()),
        Some("ready") => {
            if utilization
                .get("busy_basis_points")
                .and_then(Value::as_u64)
                .filter(|value| *value <= 10_000)
                .is_none()
                || utilization
                    .get("sample_window_ms")
                    .and_then(Value::as_u64)
                    .filter(|value| *value > 0)
                    .is_none()
                || utilization
                    .get("omitted_logical_cpus")
                    .and_then(Value::as_u64)
                    .is_none()
            {
                return Err(invalid());
            }
            let logical = utilization
                .get("logical_cpus")
                .and_then(Value::as_array)
                .filter(|cpus| !cpus.is_empty())
                .ok_or_else(invalid)?;
            let mut previous_id = None;
            let mut ready = 0usize;
            for cpu in logical {
                let id = cpu
                    .get("id")
                    .and_then(Value::as_u64)
                    .filter(|id| *id <= u64::from(u32::MAX))
                    .ok_or_else(invalid)?;
                if previous_id.is_some_and(|previous| id <= previous) {
                    return Err(invalid());
                }
                previous_id = Some(id);
                match cpu.get("status").and_then(Value::as_str) {
                    Some("ready") => {
                        if cpu
                            .get("busy_basis_points")
                            .and_then(Value::as_u64)
                            .filter(|value| *value <= 10_000)
                            .is_none()
                        {
                            return Err(invalid());
                        }
                        ready += 1;
                    }
                    Some("unavailable") if cpu.get("busy_basis_points").is_none() => {}
                    _ => return Err(invalid()),
                }
            }
            if ready == 0 {
                return Err(invalid());
            }
            Ok(())
        }
        _ => Err(invalid()),
    }?;

    let processes = result.get("processes").ok_or_else(invalid)?;
    let records = processes
        .get("records")
        .and_then(Value::as_array)
        .ok_or_else(invalid)?;
    if records.len() > 128 {
        return Err(invalid());
    }
    let unavailable = processes
        .get("unavailable_processes")
        .and_then(Value::as_u64)
        .ok_or_else(invalid)?;
    let omitted = processes
        .get("omitted_processes")
        .and_then(Value::as_u64)
        .ok_or_else(invalid)?;
    let scan_truncated = processes
        .get("scan_truncated")
        .and_then(Value::as_bool)
        .ok_or_else(invalid)?;
    match processes.get("status").and_then(Value::as_str) {
        Some("ready")
            if !records.is_empty() && unavailable == 0 && omitted == 0 && !scan_truncated => {}
        Some("partial")
            if !records.is_empty() && unavailable > 0 && omitted == 0 && !scan_truncated => {}
        Some("truncated") if omitted > 0 || scan_truncated => {}
        Some("unavailable") if records.is_empty() && omitted == 0 && !scan_truncated => {}
        Some("invalid")
            if records.is_empty() && unavailable == 0 && omitted == 0 && !scan_truncated =>
        {
            return Ok(());
        }
        _ => return Err(invalid()),
    }
    let mut previous_pid = None;
    for record in records {
        let pid = record
            .get("pid")
            .and_then(Value::as_u64)
            .filter(|pid| *pid > 0 && *pid <= u64::from(u32::MAX))
            .ok_or_else(invalid)?;
        if previous_pid.is_some_and(|previous| pid <= previous) {
            return Err(invalid());
        }
        previous_pid = Some(pid);
        for field in ["parent_pid", "process_group_id", "session_id"] {
            if record
                .get(field)
                .and_then(Value::as_u64)
                .filter(|value| *value <= u64::from(u32::MAX))
                .is_none()
            {
                return Err(invalid());
            }
        }
        let state = record.get("state").and_then(Value::as_str).filter(|state| {
            state.len() == 1
                && matches!(
                    state.as_bytes()[0],
                    b'R' | b'S'
                        | b'D'
                        | b'Z'
                        | b'T'
                        | b't'
                        | b'X'
                        | b'x'
                        | b'K'
                        | b'W'
                        | b'P'
                        | b'I'
                )
        });
        if state.is_none() {
            return Err(invalid());
        }
        for field in [
            "user_ticks",
            "system_ticks",
            "start_time_ticks",
            "virtual_memory_bytes",
            "resident_pages",
        ] {
            if record.get(field).and_then(Value::as_u64).is_none() {
                return Err(invalid());
            }
        }
        if record
            .get("thread_count")
            .and_then(Value::as_u64)
            .filter(|threads| *threads > 0)
            .is_none()
            || record
                .get("nice")
                .and_then(Value::as_i64)
                .filter(|nice| (-20..=19).contains(nice))
                .is_none()
        {
            return Err(invalid());
        }
    }

    // processes.utilization is an optional nested object
    // (absent on older cores); when present it must agree
    // with the snapshot it was derived from.
    if let Some(utilization) = result
        .get("processes")
        .and_then(|processes| processes.get("utilization"))
    {
        let processes = result.get("processes").ok_or_else(invalid)?;
        let records = utilization
            .get("records")
            .and_then(Value::as_array)
            .ok_or_else(invalid)?;
        if records.len() > 128 {
            return Err(invalid());
        }
        let window = utilization
            .get("sample_window_ms")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let unavailable = utilization
            .get("unavailable_processes")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let omitted = utilization
            .get("omitted_processes")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        // The producer mirrors the snapshot's omission count;
        // anything else means the objects disagree.
        if omitted
            != processes
                .get("omitted_processes")
                .and_then(Value::as_u64)
                .ok_or_else(invalid)?
        {
            return Err(invalid());
        }
        let snapshot_truncated = processes
            .get("scan_truncated")
            .and_then(Value::as_bool)
            .ok_or_else(invalid)?;
        match utilization.get("status").and_then(Value::as_str) {
            Some("ready") if window > 0 && !records.is_empty() && unavailable == 0 => {}
            Some("partial") if window > 0 && !records.is_empty() && unavailable > 0 => {}
            Some("truncated") if omitted > 0 || snapshot_truncated => {}
            Some("unavailable") if records.is_empty() => {}
            _ => return Err(invalid()),
        }
        let mut previous_pid = None;
        for record in records {
            let pid = record
                .get("pid")
                .and_then(Value::as_u64)
                .filter(|pid| *pid > 0)
                .ok_or_else(invalid)?;
            if previous_pid.is_some_and(|previous| pid <= previous) {
                return Err(invalid());
            }
            previous_pid = Some(pid);
            if record
                .get("start_time_ticks")
                .and_then(Value::as_u64)
                .is_none()
                || record
                    .get("busy_basis_points")
                    .and_then(Value::as_u64)
                    .filter(|points| *points <= 10_000)
                    .is_none()
            {
                return Err(invalid());
            }
        }
    }

    // disk.throughput is an optional object (absent when the
    // disk source itself is unavailable, and on older cores);
    // when present it must be internally consistent.
    if let Some(throughput) = result.get("disk").and_then(|disk| disk.get("throughput")) {
        let devices = throughput
            .get("devices")
            .and_then(Value::as_array)
            .ok_or_else(invalid)?;
        if devices.len() > 128 {
            return Err(invalid());
        }
        let window = throughput
            .get("sample_window_ms")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let unavailable = throughput
            .get("unavailable_devices")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let omitted = throughput
            .get("omitted_devices")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        match throughput.get("status").and_then(Value::as_str) {
            Some("ready") if window > 0 && !devices.is_empty() && unavailable == 0 => {}
            Some("partial") if window > 0 && !devices.is_empty() && unavailable > 0 => {}
            Some("truncated") if omitted > 0 => {}
            Some("unavailable") if devices.is_empty() => {}
            Some("invalid") if devices.is_empty() => {}
            _ => return Err(invalid()),
        }
        for device in devices {
            if device
                .get("name")
                .and_then(Value::as_str)
                .filter(|name| !name.is_empty())
                .is_none()
                || device
                    .get("read_bytes_per_sec")
                    .and_then(Value::as_u64)
                    .is_none()
                || device
                    .get("write_bytes_per_sec")
                    .and_then(Value::as_u64)
                    .is_none()
            {
                return Err(invalid());
            }
        }
    }

    // network.bandwidth follows the same optional-object
    // contract as disk.throughput, with interface naming.
    if let Some(bandwidth) = result
        .get("network")
        .and_then(|network| network.get("bandwidth"))
    {
        let interfaces = bandwidth
            .get("interfaces")
            .and_then(Value::as_array)
            .ok_or_else(invalid)?;
        if interfaces.len() > 32 {
            return Err(invalid());
        }
        let window = bandwidth
            .get("sample_window_ms")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let unavailable = bandwidth
            .get("unavailable_interfaces")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let omitted = bandwidth
            .get("omitted_interfaces")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        match bandwidth.get("status").and_then(Value::as_str) {
            Some("ready") if window > 0 && !interfaces.is_empty() && unavailable == 0 => {}
            Some("partial") if window > 0 && !interfaces.is_empty() && unavailable > 0 => {}
            Some("truncated") if omitted > 0 => {}
            Some("unavailable") if interfaces.is_empty() => {}
            Some("invalid") if interfaces.is_empty() => {}
            _ => return Err(invalid()),
        }
        for interface in interfaces {
            if interface
                .get("name")
                .and_then(Value::as_str)
                .filter(|name| !name.is_empty())
                .is_none()
                || interface
                    .get("rx_bytes_per_sec")
                    .and_then(Value::as_u64)
                    .is_none()
                || interface
                    .get("tx_bytes_per_sec")
                    .and_then(Value::as_u64)
                    .is_none()
            {
                return Err(invalid());
            }
        }
    }

    // energy.power is an optional object (absent when the
    // powercap source could not be scanned at all, and on
    // older cores); when present it must be consistent.
    if let Some(power) = result.get("energy").and_then(|energy| energy.get("power")) {
        let zones = power
            .get("zones")
            .and_then(Value::as_array)
            .ok_or_else(invalid)?;
        if zones.len() > 256 {
            return Err(invalid());
        }
        let window = power
            .get("sample_window_ms")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let unavailable = power
            .get("unavailable_zones")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let omitted = power
            .get("omitted_zones")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        let scan_truncated = power
            .get("scan_truncated")
            .and_then(Value::as_bool)
            .ok_or_else(invalid)?;
        match power.get("status").and_then(Value::as_str) {
            Some("ready") if window > 0 && !zones.is_empty() && unavailable == 0 => {}
            Some("partial") if window > 0 && !zones.is_empty() && unavailable > 0 => {}
            Some("truncated") if omitted > 0 || scan_truncated => {}
            Some("unavailable") if zones.is_empty() => {}
            _ => return Err(invalid()),
        }
        for zone in zones {
            if zone
                .get("id")
                .and_then(Value::as_str)
                .filter(|id| !id.is_empty())
                .is_none()
                || zone
                    .get("name")
                    .and_then(Value::as_str)
                    .filter(|name| !name.is_empty())
                    .is_none()
                || zone.get("avg_power_uw").and_then(Value::as_u64).is_none()
            {
                return Err(invalid());
            }
        }
    }
    Ok(())
}

/// Client-side validation of an `observe-history` response
/// (ADR 0026): the envelope family is shared with the audit
/// records, so every event must carry the observe-event
/// schema, a known lifecycle event name, a strictly
/// increasing sequence, and a process identity with
/// cumulative counters. The sampler object must account for
/// every retained event: the events array plus the count
/// the producer trimmed from this response equals the
/// ring's retained count.
fn validate_history_result(result: &Value) -> io::Result<()> {
    let invalid = || {
        io::Error::new(
            io::ErrorKind::InvalidData,
            "invalid observe-history response",
        )
    };
    if result.get("schema").and_then(Value::as_str) != Some("synveil.observe-history/v1") {
        return Err(invalid());
    }
    let sampler = result.get("sampler").ok_or_else(invalid)?;
    if sampler.get("enabled").and_then(Value::as_bool).is_none()
        || sampler
            .get("cadence_ms")
            .and_then(Value::as_u64)
            .is_none_or(|cadence| cadence == 0)
        || sampler
            .get("ring_capacity")
            .and_then(Value::as_u64)
            .is_none_or(|capacity| capacity == 0)
        || sampler
            .get("dropped_events")
            .and_then(Value::as_u64)
            .is_none()
    {
        return Err(invalid());
    }
    let retained = sampler
        .get("retained_events")
        .and_then(Value::as_u64)
        .ok_or_else(invalid)?;
    let omitted = sampler
        .get("response_omitted_events")
        .and_then(Value::as_u64)
        .ok_or_else(invalid)?;
    let events = result
        .get("events")
        .and_then(Value::as_array)
        .ok_or_else(invalid)?;
    if retained != events.len() as u64 + omitted {
        return Err(invalid());
    }
    let mut previous_sequence: Option<u64> = None;
    for event in events {
        if event.get("schema").and_then(Value::as_str) != Some("synveil.observe-event/v1")
            || !matches!(
                event.get("event").and_then(Value::as_str),
                Some("process_started" | "process_exited")
            )
        {
            return Err(invalid());
        }
        let sequence = event
            .get("sequence")
            .and_then(Value::as_u64)
            .ok_or_else(invalid)?;
        if previous_sequence.is_some_and(|previous| sequence <= previous) {
            return Err(invalid());
        }
        previous_sequence = Some(sequence);
        let process = event
            .get("fields")
            .and_then(|fields| fields.get("process"))
            .ok_or_else(invalid)?;
        for key in ["pid", "start_time_ticks", "user_ticks", "system_ticks"] {
            if process.get(key).and_then(Value::as_u64).is_none() {
                return Err(invalid());
            }
        }
    }
    Ok(())
}

fn print_help() {
    println!(
        "Usage: synctl [--socket PATH] [--json] [status|observe|observe-history]\n\
         \n\
         Commands:\n\
           status          Query veil-core deterministic service status\n\
           observe         Read bounded kernel resource and process counters\n\
           observe-history Read lifecycle events from the core's history sampler (ADR 0026)"
    );
}

#[cfg(test)]
mod tests {
    use super::*;
    use veil_protocol::{ErrorCode, ProtocolError};

    #[test]
    fn validates_response_correlation() {
        let response = Response::success("expected", json!({}));
        assert!(validate_correlation(&response, "expected").is_ok());
        assert_eq!(
            validate_correlation(&response, "other").unwrap_err().kind(),
            io::ErrorKind::InvalidData
        );
    }

    #[test]
    fn error_response_retains_failure_with_json_output() {
        let response = Response::failure(
            "expected",
            ProtocolError::new(ErrorCode::UnknownMethod, "unknown"),
        );
        assert!(response_exit_code(&response) == ExitCode::FAILURE);
        assert!(validate_correlation(&response, "expected").is_ok());
    }

    #[test]
    fn history_validation_accepts_a_well_formed_response() {
        let valid = json!({
            "schema": "synveil.observe-history/v1",
            "sampler": {
                "enabled": true,
                "cadence_ms": 5000,
                "ring_capacity": 1024,
                "retained_events": 2,
                "dropped_events": 0,
                "response_omitted_events": 0,
            },
            "events": [
                {
                    "schema": "synveil.observe-event/v1",
                    "event": "process_started",
                    "sequence": 0,
                    "fields": {"process": {
                        "pid": 42, "start_time_ticks": 100,
                        "user_ticks": 1, "system_ticks": 0}},
                },
                {
                    "schema": "synveil.observe-event/v1",
                    "event": "process_exited",
                    "sequence": 1,
                    "fields": {"process": {
                        "pid": 42, "start_time_ticks": 100,
                        "user_ticks": 3, "system_ticks": 1}},
                },
            ],
        });
        assert!(validate_history_result(&valid).is_ok());
        // A disabled sampler with an empty ring is valid.
        let disabled = json!({
            "schema": "synveil.observe-history/v1",
            "sampler": {
                "enabled": false,
                "cadence_ms": 5000,
                "ring_capacity": 1024,
                "retained_events": 0,
                "dropped_events": 0,
                "response_omitted_events": 0,
            },
            "events": [],
        });
        assert!(validate_history_result(&disabled).is_ok());
    }

    #[test]
    fn history_validation_rejects_malformed_responses() {
        let base = |events: Value, retained: u64, omitted: u64| {
            json!({
                "schema": "synveil.observe-history/v1",
                "sampler": {
                    "enabled": true,
                    "cadence_ms": 5000,
                    "ring_capacity": 1024,
                    "retained_events": retained,
                    "dropped_events": 0,
                    "response_omitted_events": omitted,
                },
                "events": events,
            })
        };
        let event = |sequence: u64, kind: &str| {
            json!({
                "schema": "synveil.observe-event/v1",
                "event": kind,
                "sequence": sequence,
                "fields": {"process": {
                    "pid": 42, "start_time_ticks": 100,
                    "user_ticks": 1, "system_ticks": 0}},
            })
        };
        // Retained count must account for the events carried.
        assert!(
            validate_history_result(&base(json!([event(0, "process_started")]), 2, 0)).is_err()
        );
        // Sequences must strictly increase.
        assert!(
            validate_history_result(&base(
                json!([event(1, "process_started"), event(1, "process_exited")]),
                2,
                0
            ))
            .is_err()
        );
        // Unknown lifecycle event names are refused.
        assert!(
            validate_history_result(&base(json!([event(0, "process_vanished")]), 1, 0)).is_err()
        );
        // A wrong document schema is refused.
        let mut wrong_schema = base(json!([]), 0, 0);
        wrong_schema["schema"] = json!("synveil.observe/v1");
        assert!(validate_history_result(&wrong_schema).is_err());
    }

    #[test]
    fn observe_validation_requires_sorted_per_cpu_measurements() {
        let processes = json!({
            "status": "ready",
            "records": [{
                "pid": 1, "parent_pid": 0, "process_group_id": 1,
                "session_id": 1, "state": "S", "user_ticks": 1,
                "system_ticks": 2, "start_time_ticks": 3,
                "virtual_memory_bytes": 4096, "resident_pages": 1,
                "thread_count": 1, "nice": 0
            }],
            "unavailable_processes": 0,
            "omitted_processes": 0,
            "scan_truncated": false
        });
        let valid = json!({
            "schema": "synveil.observe/v1",
            "cpu": {"utilization": {
                "status": "ready",
                "busy_basis_points": 5000,
                "sample_window_ms": 101,
                "logical_cpus": [
                    {"id": 0, "status": "ready", "busy_basis_points": 7500},
                    {"id": 2, "status": "unavailable"}
                ],
                "omitted_logical_cpus": 0
            }},
            "processes": processes.clone()
        });
        assert!(validate_observe_result(&valid).is_ok());

        for invalid in [
            json!({"schema": "synveil.observe/v1", "cpu": {"utilization": {
                "status": "ready", "busy_basis_points": 5000,
                "sample_window_ms": 101, "logical_cpus": [],
                "omitted_logical_cpus": 0
            }}, "processes": processes.clone()}),
            json!({"schema": "synveil.observe/v1", "cpu": {"utilization": {
                "status": "ready", "busy_basis_points": 5000,
                "sample_window_ms": 101,
                "logical_cpus": [{"id": 0, "status": "ready"}],
                "omitted_logical_cpus": 0
            }}, "processes": processes.clone()}),
            json!({"schema": "synveil.observe/v1", "cpu": {"utilization": {
                "status": "ready", "busy_basis_points": 5000,
                "sample_window_ms": 101,
                "logical_cpus": [
                    {"id": 2, "status": "ready", "busy_basis_points": 1},
                    {"id": 1, "status": "ready", "busy_basis_points": 1}
                ],
                "omitted_logical_cpus": 0
            }}, "processes": processes.clone()}),
        ] {
            assert!(validate_observe_result(&invalid).is_err());
        }
    }

    #[test]
    fn observe_validation_checks_process_utilization_when_present() {
        let record = json!({
            "pid": 7, "parent_pid": 1, "process_group_id": 7,
            "session_id": 7, "state": "R", "user_ticks": 10,
            "system_ticks": 2, "start_time_ticks": 100,
            "virtual_memory_bytes": 8192, "resident_pages": 2,
            "thread_count": 1, "nice": 0
        });
        let response = |utilization: Value| {
            json!({
                "schema": "synveil.observe/v1",
                "cpu": {"utilization": {"status": "unavailable"}},
                "processes": {
                    "status": "ready", "records": [record.clone()],
                    "unavailable_processes": 0,
                    "omitted_processes": 0, "scan_truncated": false,
                    "utilization": utilization,
                },
            })
        };
        let rated = json!({
            "pid": 7, "start_time_ticks": 100,
            "busy_basis_points": 300
        });
        for valid in [
            json!({"status": "ready", "sample_window_ms": 101,
                   "records": [rated.clone()],
                   "unavailable_processes": 0,
                   "omitted_processes": 0}),
            json!({"status": "unavailable", "sample_window_ms": 101,
                   "records": [], "unavailable_processes": 1,
                   "omitted_processes": 0}),
        ] {
            assert!(validate_observe_result(&response(valid)).is_ok());
        }
        for invalid in [
            // basis points above the whole machine
            json!({"status": "ready", "sample_window_ms": 101,
                   "records": [{"pid": 7, "start_time_ticks": 100,
                                "busy_basis_points": 10001}],
                   "unavailable_processes": 0,
                   "omitted_processes": 0}),
            // omission count disagreeing with the snapshot
            json!({"status": "ready", "sample_window_ms": 101,
                   "records": [rated.clone()],
                   "unavailable_processes": 0,
                   "omitted_processes": 1}),
            // truncated with no truncation anywhere
            json!({"status": "truncated", "sample_window_ms": 101,
                   "records": [rated.clone()],
                   "unavailable_processes": 0,
                   "omitted_processes": 0}),
            // unsorted PIDs
            json!({"status": "ready", "sample_window_ms": 101,
                   "records": [
                       {"pid": 9, "start_time_ticks": 1,
                        "busy_basis_points": 0},
                       {"pid": 7, "start_time_ticks": 1,
                        "busy_basis_points": 0}],
                   "unavailable_processes": 0,
                   "omitted_processes": 0}),
        ] {
            assert!(validate_observe_result(&response(invalid)).is_err());
        }
    }

    #[test]
    fn observe_validation_checks_disk_throughput_when_present() {
        let processes = json!({
            "status": "ready",
            "records": [{
                "pid": 7, "parent_pid": 1, "process_group_id": 7,
                "session_id": 7, "state": "R", "user_ticks": 10,
                "system_ticks": 2, "start_time_ticks": 100,
                "virtual_memory_bytes": 8192, "resident_pages": 2,
                "thread_count": 1, "nice": 0
            }],
            "unavailable_processes": 0, "omitted_processes": 0,
            "scan_truncated": false
        });
        let response = |disk: Value| {
            json!({
                "schema": "synveil.observe/v1",
                "cpu": {"utilization": {"status": "unavailable"}},
                "processes": processes.clone(),
                "disk": disk,
            })
        };
        let device = json!({
            "name": "sda", "read_bytes_per_sec": 1024,
            "write_bytes_per_sec": 0
        });
        // Absent throughput (older cores / no disk object detail)
        // stays acceptable.
        assert!(
            validate_observe_result(&response(json!({"status": "unavailable", "devices": []})))
                .is_ok()
        );
        for valid in [
            json!({"status": "ready", "sample_window_ms": 101,
                   "devices": [device.clone()],
                   "unavailable_devices": 0, "omitted_devices": 0}),
            json!({"status": "partial", "sample_window_ms": 101,
                   "devices": [device.clone()],
                   "unavailable_devices": 2, "omitted_devices": 0}),
            json!({"status": "truncated", "sample_window_ms": 101,
                   "devices": [device.clone()],
                   "unavailable_devices": 0, "omitted_devices": 3}),
            json!({"status": "unavailable", "sample_window_ms": 0,
                   "devices": [],
                   "unavailable_devices": 4, "omitted_devices": 0}),
        ] {
            let disk = json!({"status": "ready", "devices": [],
                              "throughput": valid});
            assert!(validate_observe_result(&response(disk)).is_ok());
        }
        for invalid in [
            // ready with unavailable devices is contradictory
            json!({"status": "ready", "sample_window_ms": 101,
                   "devices": [device.clone()],
                   "unavailable_devices": 1, "omitted_devices": 0}),
            // zero window cannot carry rates
            json!({"status": "ready", "sample_window_ms": 0,
                   "devices": [device.clone()],
                   "unavailable_devices": 0, "omitted_devices": 0}),
            // truncated without omissions
            json!({"status": "truncated", "sample_window_ms": 101,
                   "devices": [device.clone()],
                   "unavailable_devices": 0, "omitted_devices": 0}),
            // unavailable with rated devices
            json!({"status": "unavailable", "sample_window_ms": 101,
                   "devices": [device.clone()],
                   "unavailable_devices": 0, "omitted_devices": 0}),
            // negative / missing rates
            json!({"status": "ready", "sample_window_ms": 101,
                   "devices": [{"name": "sda",
                                "read_bytes_per_sec": -1,
                                "write_bytes_per_sec": 0}],
                   "unavailable_devices": 0, "omitted_devices": 0}),
            json!({"status": "ready", "sample_window_ms": 101,
                   "devices": [{"name": "sda",
                                "write_bytes_per_sec": 0}],
                   "unavailable_devices": 0, "omitted_devices": 0}),
            // unknown status
            json!({"status": "guessed", "sample_window_ms": 101,
                   "devices": [],
                   "unavailable_devices": 0, "omitted_devices": 0}),
        ] {
            let disk = json!({"status": "ready", "devices": [],
                              "throughput": invalid});
            assert!(validate_observe_result(&response(disk)).is_err());
        }
    }

    #[test]
    fn observe_validation_checks_network_bandwidth_when_present() {
        let processes = json!({
            "status": "ready",
            "records": [{
                "pid": 7, "parent_pid": 1, "process_group_id": 7,
                "session_id": 7, "state": "R", "user_ticks": 10,
                "system_ticks": 2, "start_time_ticks": 100,
                "virtual_memory_bytes": 8192, "resident_pages": 2,
                "thread_count": 1, "nice": 0
            }],
            "unavailable_processes": 0, "omitted_processes": 0,
            "scan_truncated": false
        });
        let response = |network: Value| {
            json!({
                "schema": "synveil.observe/v1",
                "cpu": {"utilization": {"status": "unavailable"}},
                "processes": processes.clone(),
                "network": network,
            })
        };
        let iface = json!({
            "name": "eth0", "rx_bytes_per_sec": 20000,
            "tx_bytes_per_sec": 10000
        });
        assert!(
            validate_observe_result(&response(
                json!({"status": "unavailable", "interfaces": []})
            ))
            .is_ok()
        );
        for valid in [
            json!({"status": "ready", "sample_window_ms": 101,
                   "interfaces": [iface.clone()],
                   "unavailable_interfaces": 0,
                   "omitted_interfaces": 0}),
            json!({"status": "partial", "sample_window_ms": 101,
                   "interfaces": [iface.clone()],
                   "unavailable_interfaces": 1,
                   "omitted_interfaces": 0}),
            json!({"status": "unavailable", "sample_window_ms": 0,
                   "interfaces": [],
                   "unavailable_interfaces": 2,
                   "omitted_interfaces": 0}),
        ] {
            let network = json!({"status": "ready", "interfaces": [],
                                 "bandwidth": valid});
            assert!(validate_observe_result(&response(network)).is_ok());
        }
        for invalid in [
            json!({"status": "partial", "sample_window_ms": 101,
                   "interfaces": [iface.clone()],
                   "unavailable_interfaces": 0,
                   "omitted_interfaces": 0}),
            json!({"status": "ready", "sample_window_ms": 101,
                   "interfaces": [{"name": "eth0",
                                   "rx_bytes_per_sec": 1.5,
                                   "tx_bytes_per_sec": 0}],
                   "unavailable_interfaces": 0,
                   "omitted_interfaces": 0}),
            json!({"status": "ready", "sample_window_ms": 101,
                   "interfaces": [{"name": "",
                                   "rx_bytes_per_sec": 0,
                                   "tx_bytes_per_sec": 0}],
                   "unavailable_interfaces": 0,
                   "omitted_interfaces": 0}),
        ] {
            let network = json!({"status": "ready", "interfaces": [],
                                 "bandwidth": invalid});
            assert!(validate_observe_result(&response(network)).is_err());
        }
    }

    #[test]
    fn observe_validation_checks_energy_power_when_present() {
        let processes = json!({
            "status": "ready",
            "records": [{
                "pid": 7, "parent_pid": 1, "process_group_id": 7,
                "session_id": 7, "state": "R", "user_ticks": 10,
                "system_ticks": 2, "start_time_ticks": 100,
                "virtual_memory_bytes": 8192, "resident_pages": 2,
                "thread_count": 1, "nice": 0
            }],
            "unavailable_processes": 0, "omitted_processes": 0,
            "scan_truncated": false
        });
        let response = |energy: Value| {
            json!({
                "schema": "synveil.observe/v1",
                "cpu": {"utilization": {"status": "unavailable"}},
                "processes": processes.clone(),
                "energy": energy,
            })
        };
        let zone = json!({
            "id": "intel-rapl:0", "name": "package-0",
            "avg_power_uw": 10000
        });
        // No power object (unscannable source / older core).
        assert!(
            validate_observe_result(&response(json!({"status": "unavailable", "zones": []})))
                .is_ok()
        );
        for valid in [
            json!({"status": "ready", "sample_window_ms": 101,
                   "zones": [zone.clone()], "unavailable_zones": 0,
                   "omitted_zones": 0, "scan_truncated": false}),
            json!({"status": "unavailable", "sample_window_ms": 101,
                   "zones": [], "unavailable_zones": 0,
                   "omitted_zones": 0, "scan_truncated": false}),
            json!({"status": "truncated", "sample_window_ms": 101,
                   "zones": [zone.clone()], "unavailable_zones": 0,
                   "omitted_zones": 0, "scan_truncated": true}),
        ] {
            let energy = json!({"status": "ready", "zones": [],
                                "power": valid});
            assert!(validate_observe_result(&response(energy)).is_ok());
        }
        for invalid in [
            // truncated with no truncation evidence
            json!({"status": "truncated", "sample_window_ms": 101,
                   "zones": [zone.clone()], "unavailable_zones": 0,
                   "omitted_zones": 0, "scan_truncated": false}),
            // ready over a zero window
            json!({"status": "ready", "sample_window_ms": 0,
                   "zones": [zone.clone()], "unavailable_zones": 0,
                   "omitted_zones": 0, "scan_truncated": false}),
            // invalid is a snapshot status, never a power status
            json!({"status": "invalid", "sample_window_ms": 101,
                   "zones": [], "unavailable_zones": 0,
                   "omitted_zones": 0, "scan_truncated": false}),
            // missing scan_truncated field
            json!({"status": "ready", "sample_window_ms": 101,
                   "zones": [zone.clone()], "unavailable_zones": 0,
                   "omitted_zones": 0}),
        ] {
            let energy = json!({"status": "ready", "zones": [],
                                "power": invalid});
            assert!(validate_observe_result(&response(energy)).is_err());
        }
    }

    #[test]
    fn observe_validation_requires_sorted_process_identity_and_counters() {
        let valid_record = json!({
            "pid": 7, "parent_pid": 1, "process_group_id": 7,
            "session_id": 7, "state": "R", "user_ticks": 10,
            "system_ticks": 2, "start_time_ticks": 100,
            "virtual_memory_bytes": 8192, "resident_pages": 2,
            "thread_count": 1, "nice": 0
        });
        let response = |processes: Value| {
            json!({
                "schema": "synveil.observe/v1",
                "cpu": {"utilization": {"status": "unavailable"}},
                "processes": processes,
            })
        };
        assert!(
            validate_observe_result(&response(json!({
                "status": "ready", "records": [valid_record.clone()],
            "unavailable_processes": 0, "omitted_processes": 0,
            "scan_truncated": false
            })))
            .is_ok()
        );

        for invalid in [
            json!({"status": "ready", "records": [],
                "unavailable_processes": 0, "omitted_processes": 0,
                "scan_truncated": false}),
            json!({"status": "ready", "records": [valid_record.clone(), valid_record.clone()],
                "unavailable_processes": 0, "omitted_processes": 0,
                "scan_truncated": false}),
            json!({"status": "partial", "records": [valid_record.clone()],
                "unavailable_processes": 0, "omitted_processes": 0,
                "scan_truncated": false}),
            json!({"status": "truncated", "records": [valid_record.clone()],
                "unavailable_processes": 0, "omitted_processes": 0,
                "scan_truncated": false}),
            json!({"status": "ready", "records": [{
                "pid": 7, "parent_pid": 1, "process_group_id": 7,
                "session_id": 7, "state": "?", "user_ticks": 10,
                "system_ticks": 2, "start_time_ticks": 100,
                "virtual_memory_bytes": 8192, "resident_pages": 2,
                "thread_count": 0, "nice": 25
            }], "unavailable_processes": 0, "omitted_processes": 0,
                "scan_truncated": false}),
        ] {
            assert!(validate_observe_result(&response(invalid)).is_err());
        }

        let too_many_records = (1..=129u32)
            .map(|pid| {
                json!({
                    "pid": pid, "parent_pid": 1, "process_group_id": pid,
                    "session_id": pid, "state": "S", "user_ticks": 0,
                    "system_ticks": 0, "start_time_ticks": u64::from(pid),
                    "virtual_memory_bytes": 4096, "resident_pages": 1,
                    "thread_count": 1, "nice": 0
                })
            })
            .collect::<Vec<_>>();
        assert!(
            validate_observe_result(&response(json!({
                "status": "truncated", "records": too_many_records,
                "unavailable_processes": 0, "omitted_processes": 1,
                "scan_truncated": false
            })))
            .is_err()
        );
    }
}
