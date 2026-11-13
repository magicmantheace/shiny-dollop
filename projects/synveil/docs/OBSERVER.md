# Read-only local observer (developer v1)

`synctl --json observe` queries `veil-core` through its local read-only
Unix socket. This does not authorize process mutation, privileged actions,
AI recommendations or operating-system policy changes.

## Schema: `synveil.observe/v1`

- `cpu.logical_count`: logical CPUs from `/proc/stat`.
- `cpu.total_ticks`, `cpu.idle_ticks`: cumulative kernel counters from the
  later sample. `total_ticks` excludes `guest` and `guest_nice`, which Linux
  already includes in `user` and `nice`; `idle_ticks` includes iowait.
- `cpu.utilization`: aggregate and per-logical-CPU busy time derived from two `/proc/stat`
  samples separated by at least 100 ms. A ready result contains integer
  `busy_basis_points` from 0 through 10000 and the measured monotonic
  `sample_window_ms`; 2500 means 25.00 percent busy across all logical CPUs.
  Its numerically sorted `logical_cpus` records report the same fixed-point
  measurement for each stable CPU ID and are bounded to 4096 entries. A CPU
  with no counter delta or decreasing iowait is explicitly `unavailable`.
  Zero total delta, a topology change, or an iowait decrease returns
  `{"status":"unavailable"}` without inventing a percentage. A backward
  non-guest counter other than iowait is invalid.
  `synctl` validates the versioned utilization object, strictly increasing CPU
  IDs, per-CPU status and basis-point bounds before accepting a successful
  observe response.
- `cpu.frequency`: kernel-reported current per-logical-CPU frequency from Linux
  cpufreq sysfs, in integer kHz. It is not an independent hardware measurement.
  `scaling_cur_freq` is preferred and `cpuinfo_cur_freq` is the fallback.
  Systems without a cpufreq driver report `status: unavailable`;
  offline, temporarily busy or unsupported logical CPUs make an otherwise
  populated result `partial`. Output is numerically sorted and bounded to 4096
  logical CPUs.
- `memory.total_bytes`, `memory.available_bytes`: Linux MemTotal and
  MemAvailable read from `/proc/meminfo`, converted from kB to bytes with
  overflow checks.
- `thermal`: bounded Linux thermal-zone snapshots. A ready or truncated result
  contains numerically sorted zones with kernel `type` labels and signed
  `temperature_millicelsius` values. Systems without thermal zones report
  `status: unavailable`; unreadable zones are counted and make a populated
  result `partial`, while malformed zone data reports `invalid` without
  discarding the other observation fields.
- `energy`: bounded Linux powercap zones with stable sysfs IDs, bounded names,
  cumulative `energy_uj` and `max_energy_range_uj`. Counters may wrap at the
  reported range and do not represent instantaneous power. Missing or unreadable
  zones are explicit; malformed counters invalidate only this optional object.
- `uptime_seconds`: kernel time since boot from `/proc/uptime`.
- `load.average_1m`, `load.average_5m`, `load.average_15m`:
  Linux scheduler load averages from `/proc/loadavg`. These are neither
  CPU percentages nor normalized by logical processor count.
- `load.runnable`, `load.total_threads`: scheduler entities from
  the runnable/total field in `/proc/loadavg`. Total refers to threads,
  not distinct processes, and includes the current procfs context.
- `processes`: a point-in-time, PID-sorted `/proc/<pid>/stat` snapshot. Up to
  128 records report PID, parent/process-group/session IDs, kernel state,
  cumulative user/system ticks, start time in boot ticks, virtual bytes,
  resident pages, thread count and nice value. PID plus `start_time_ticks`
  distinguishes PID reuse. Directory scanning is capped at 16384 entries;
  disappearing or unreadable processes are counted instead of failing the
  required CPU/memory snapshot. `synctl` validates status/count relationships,
  strict PID ordering, identifiers, states and counter types before accepting a
  successful response. The observer never opens command lines, environments or
  executable paths. The command name embedded in `stat` is used only to locate
  the following fields and is not returned; it need not be valid UTF-8. If the
  full response would exceed the 64 KiB protocol frame, the core removes
  highest-PID records and increments `omitted_processes` until it fits.
- `processes.utilization`: per-process CPU attribution over the same
  ≥100 ms window as `cpu.utilization`. For each snapshot record, the
  process's user+system tick delta is expressed in basis points of the
  aggregate `/proc/stat` total tick delta (same denominator and rounding
  as the aggregate busy figure, so the rated processes sum to at most
  that figure plus rounding). Identity is PID plus `start_time_ticks`:
  a reused PID is a different process and is withheld, as are processes
  born inside the window and any tick decrease; withheld processes are
  counted in `unavailable_processes`, never estimated. `synctl`
  validates the object when present, including agreement with the
  snapshot's `omitted_processes` and `scan_truncated`.

The core validates required fields, finite nonnegative numeric values,
CPU and memory consistency and runnable/total bounds. Bad or unavailable
required procfs input returns a structured error; it never silently
substitutes fake zero values. The implementation reads kernel files
directly without starting shell commands.

Host tests cover valid parsing and malformed/inconsistent counters. The native
QEMU `observe` guest gate passed at exact revision `255101d`, requiring the
versioned schema and live utilization fields from the real command response.
See the [retained evidence](validation/native-255101d/README.md).
The frequency extension passed host and native QEMU validation at exact revision
`376e2b4`; QEMU required the frequency object but exposed no cpufreq driver, so
positive and partial readings remain host-fixture evidence. See the
[frequency evidence](validation/native-376e2b4/README.md).
Per-logical-CPU utilization and the native client's structural checks passed at
exact revision `23f3233`. See the
[per-CPU evidence](validation/native-23f3233/README.md).
The thermal extension passed host and native QEMU validation at exact revision
`b5f5cae`; QEMU required the thermal object but exposed no zones, so positive
and partial readings remain host-fixture evidence. See the
[thermal evidence](validation/native-b5f5cae/README.md).
The bounded process snapshot and the native client's structural checks,
including rejection above the 128-record cap, passed host and native QEMU
validation after composition with energy at exact revision `316f745`. See the
[process evidence](validation/native-316f745/README.md).
The powercap energy extension passed host and native QEMU validation at exact
revision `bca81e5`; QEMU required the energy object but exposed no zones, so
positive hierarchical readings remain host-fixture evidence. See the
[energy evidence](validation/native-bca81e5/README.md).

## Deliberately not claimed

Resource history and long-term aggregation are separate roadmap
items. The process snapshot does not retain state between requests
or infer process purpose. (Per-process interval utilization and
interval power, once listed here, are implemented: see
`processes.utilization` above and the Energy section below.
Process lifecycle events are also implemented — as the separate
sampler-fed `observe-history` ring, not as snapshot state: see
the History section below.)

## Linux pressure stall information (PSI)

The `pressure.cpu`, `pressure.memory`, and `pressure.io` objects
report the kernel's `/proc/pressure/{cpu,memory,io}` values when present.
A ready record contains `some` and optional `full` groups with
`avg10_pct`, `avg60_pct`, `avg300_pct` (stall time percentages over
10/60/300 seconds), and `total_stall_us` (cumulative microseconds).

CPU's `full` record is optional; memory and I/O require both records
when PSI is available. Unsupported kernels return `status: unavailable`.
Malformed, oversized, duplicate, or out-of-range PSI records return
`status: invalid`, without inventing zero-pressure measurements or
breaking unrelated CPU/memory observation. No sampling daemon, historical
recording, process control, or inference authorization is introduced.

Native QEMU validation passed 2026-11-07
(`tests/smoke-native-observe.py`, `SYNVEIL_OBSERVE_QEMU_PASS`):
on the CONFIG_PSI=y guest kernel all three pressure objects
reported `ready` in a real observe response, with the client
accepting it (empty synctl stderr). The system core's socket
is root-only, so the gate exercised the compiled code through
a user-level fixture core against the real guest /proc — see
[retained evidence](validation/observe-psi-d526e55/README.md).

## Disk I/O

The `disk` object reports raw cumulative per-device counters
from `/proc/diskstats` (reads/writes completed, 512-byte
sector counters, in-flight I/O, busy time). A strict parser
rejects malformed counters and bounds the device list;
whole devices and partitions are separate rows and are never
summed.

`disk.throughput` adds interval rates over the same
≥100 ms window used for CPU utilization: the observer reads
diskstats before and after the window and reports, per
device, integer `read_bytes_per_sec` / `write_bytes_per_sec`
(sector delta × 512 × 1000 / window, floored), with
`sample_window_ms`. A device is rated only when it appears
in both samples with non-decreasing sector counters; a
device that appeared, vanished, or reset inside the window
is counted in `unavailable_devices` instead of being
assigned an invented rate. Status is `ready` when every
device was rated, `partial` when some were not,
`truncated` when the device cap dropped rows, and
`unavailable` when nothing could be rated (including a
zero-length window). A missing or malformed first sample
degrades only the throughput object (`unavailable` /
`invalid`); the cumulative snapshot keeps its own strict
behaviour. `synctl` validates the object for internal
consistency when present.

Host tests cover the rate arithmetic, churn/decrease
withholding, and the zero-window and truncation cases.
Native QEMU validation passed 2026-11-07 on the joined
guest (all 11 devices rated `ready`; the guest was idle in
the sample window, so the captured rates are honestly
zero) — see
[evidence](validation/observe-disk-e532ad9/README.md).
Persistent history remains a separate open roadmap item.

## Network

The `network` object reports raw cumulative per-interface
counters from `/proc/net/dev` (RX/TX bytes, packets, errors,
drops). No interface is opened, configured, or mutated, and
interfaces are never summed; a VPN or virtual NIC stays a
separate row.

`network.bandwidth` adds interval rates over the same
≥100 ms window: per interface, integer `rx_bytes_per_sec` /
`tx_bytes_per_sec` (byte delta × 1000 / window, floored),
with the same rating rules as disk throughput — an
interface is rated only when present in both samples with
non-decreasing byte counters; churn and resets are counted
in `unavailable_interfaces`. Statuses mirror
`disk.throughput` (`ready` / `partial` / `truncated` /
`unavailable`, plus `invalid` when the first sample is
malformed), and `synctl` validates the object when present.

Host tests cover the arithmetic and edge cases. Native QEMU
validation passed 2026-11-07 on the joined guest (both
guest interfaces rated `ready`; idle window, honestly zero
rates) — see
[evidence](validation/observe-network-1761759/README.md).
Connection inventory, traffic inspection, and history
remain separate open roadmap items.

## Energy and interval power

The `energy` object reports cumulative per-zone powercap
counters (`energy_uj` with its `max_energy_range_uj` wrap
range) from a bounded hierarchical scan of
`/sys/class/powercap`.

`energy.power` adds interval power over the same ≥100 ms
window: per zone, `avg_power_uw` = energy delta × 1000 /
window (µJ/s = µW, floored). A counter decrease with an
unchanged wrap range is accounted as exactly one wrap. A
zone is rated only when present in both scans with an
unchanged wrap range; anything else is counted in
`unavailable_zones`. When either scan cannot run (the
powercap root is missing or the data is malformed), the
response carries no `power` object at all — the same
absence contract as `disk.throughput`. `synctl` validates
the object when present.

The rating arithmetic is host-proven (constructed scans and
fixture trees, including the wrap case). Native QEMU
validation on 2026-11-07 exercised the absence path only —
the guest exposes no powercap sysfs, so `energy` is bare
unavailable and `power` coherently absent — see
[evidence](validation/observe-power-95ede21/README.md). A
positive in-guest power reading awaits hardware (or an
emulation) that exposes RAPL zones.

## History — process lifecycle events (ADR 0026)

The `observe-history` request (separate from `observe`,
schema `synveil.observe-history/v1`) serves process lifecycle
events produced by a sampler inside veil-core. The sampler is
**off by default** (owner amendment to the accepted history
design): it runs only when the `SYNVEIL_OBSERVE_HISTORY`
policy variable is present in the core's environment. When it
runs, every 5 s it diffs consecutive full process snapshots
by (pid, start_time) identity and appends normalized records
(schema `synveil.observe-event/v1`) to a bounded in-memory
ring of 1024 events:

- `process_started` — pid, parent pid, start time, and the
  cumulative user/system counters at first observation.
- `process_exited` — the same identity with the **last
  observed** cumulative counters, so an exit preserves the
  process's final accounted CPU.

Events are telemetry only: they never enter the hash-chained
audit journal, nothing is written to disk, and a core restart
clears the ring. Processes that start and exit between
samples are missed by construction (documented; no eBPF or
netlink collector, per ADR 0026). The response's `sampler`
block reports the enabled state, cadence, ring capacity,
retained/dropped counts; because one response cannot carry
the whole ring within the protocol's 64 KiB wire limit, it
carries the newest events that fit and counts the omitted
older ones in `response_omitted_events`. A disabled sampler
is a reported state, not an error: the response carries
`enabled: false` and an empty ring.

Host proof: unit tests over fixture snapshot pairs (baseline
silence, start/exit identity and final counters, pid-reuse
ordering, ring bound with drop counting, malformed records)
plus dispatch and response-trim tests; `synctl` validates the
history envelope client-side. Native QEMU validation on
2026-11-07: the observe gate starts a known `sleep 12` probe
between samples and requires its `process_started` event in
the alive snapshot and its `process_exited` event (same
identity, later sequence) after it exits — see
[evidence](validation/observe-history-bb422ea/README.md)
(`SYNVEIL_OBSERVE_QEMU_PASS`, probe pid 219, started
sequence 1, exited sequence 3).

### Aggregation — 1-minute buckets (ADR 0026)

The same sampler series now also feeds a windowed
aggregation store (in-memory only, like the ring). At each
tick the sampler folds its own **rated** values into
1-minute buckets keyed by (metric, series):

- `cpu.busy` (basis points, series `aggregate`) from the
  CPU utilization rating;
- `memory.used` (bytes, series `system`) = total −
  available;
- `disk.throughput.bps` (bytes/second, one series per
  block device) and `net.throughput.bps` (one series per
  interface), summed per source from the interval ratings.

Devices and interfaces are never summed into a system
total — a partition and its whole device would
double-count, exactly as the snapshot refuses to. A source
whose rating was withheld or invalid folds no point. Each
bucket carries its sample count, the floored mean and the
max; at most 60 buckets are retained per series (one hour)
under the ADR 0026 storage bound (64 series by name, never
silently merged — overflow is counted in
`omitted_series`), and out-of-order samples (clock stepped
back) are skipped: history is append-only.

`observe-history` serves the store as an `aggregates`
object beside the events: bucket size, retention,
store-wide `dropped_buckets`, and per-series bucket lists.
Because responses share the 64 KiB wire limit, the oldest
aggregate buckets are trimmed (counted in
`response_omitted_buckets`) before any event is dropped.
`synctl` validates the aggregate block client-side (known
metric/unit pairs, minute-aligned strictly increasing
bucket starts, mean ≤ max, bucket accounting). Aggregates
are telemetry: they never enter the hash-chained audit
journal, nothing is written to disk, and a core restart
clears the store. "Storage" in the ADR 0026 design means
this ephemeral store only — durable storage is not part
of the design.

Host proof: unit tests over the aggregator (bucket
folding, mean/max, hour retention with drop counting,
out-of-order skip, series cap, snapshot trim accounting)
and the dispatcher's response fitting. Native QEMU
validation on 2026-11-08: the observe gate requires the
aggregates block in all three snapshots and, in the final
one, all four metric families with sane ranges (cpu.busy
max ≤ 10,000 bp; memory.used > 0) — see
[evidence](validation/observe-aggregation-abaeef7/README.md)
(`SYNVEIL_OBSERVE_QEMU_PASS`, probe pid 225; the cpu.busy
bucket accumulates 2 → 4 → 6 samples across the three
snapshots of the same boot).
