#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Native QEMU acceptance for the durable audit record format v2
(docs/DURABLE_AUDIT_V2_DESIGN.md, slice 3; ADR 0023 Decision 3).

Boots a private copy of the joined image whose state partition was
seeded (host-side, through debugfs on the extracted ext4) with a
three-record v1 journal — the exact line form the pre-v2 writer
emitted — then drives the joined smoke's graphical enrollment and
two-boot login flow against it. The in-guest core must append
hash-chained v2 records continuing from the seeded v1 tail (the
v1 record's link hash is SHA-512 of its raw line bytes).

After the boots, the journal is extracted from the state partition
and verified on the host with the PACKAGED veil-audit taken from
the image's own rootfs staging: `check` must accept the chain with
its anchor equal to the boundary digest; `export` must produce a
receipt pinning that anchor and the final head; and the host-built
veil-audit must verify the exported snapshot against the receipt
(`verify --receipt`), with a truncated copy refused as a negative
control. The export is produced by the packaged tool from the
guest-written journal; nothing here claims the export ran inside
the guest. QEMU evidence only; no physical hardware is claimed.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

_spec = importlib.util.spec_from_file_location(
    "smoke_native_joined", ROOT / "tests" / "smoke-native-joined.py")
joined = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(joined)

IMAGE_DIR = ROOT / "out" / "native-joined"
OUT = ROOT / "out" / "audit-v2-proof"
STATE_PARTUUID = "7c9e2d41-8b3a-4f5e-a6d1-2e8c4b7f9053"
SEED_RECORDS = 3


def run(argv, **kwargs):
    return subprocess.run(argv, check=True, capture_output=True, **kwargs)


def seed_journal_bytes() -> bytes:
    """The v1 line form, as the pre-chain writer emitted it: one
    JSON record per line, envelope fields only. Disclosed fixture:
    these three records were generated host-side for this gate,
    not by a guest boot (their `fields` say so)."""
    lines = []
    for index in range(SEED_RECORDS):
        record = {
            "schema": "synveil.audit/v1",
            "component": "veil-core",
            "pid": 1,
            "sequence": index + 1,
            "unix_time_ms": 1793700000000 + index,
            "version": "0.1.0-dev",
            "git_revision": None,
            "event": "audit-v2-native-seed",
            "fields": {"fixture": "durable-audit-v2-slice3", "index": index},
        }
        lines.append(json.dumps(record, separators=(",", ":"), sort_keys=True))
    return ("\n".join(lines) + "\n").encode()


def state_partition(image: Path) -> tuple[int, int]:
    """(byte offset, byte size) of the state partition (GPT #2)."""
    info = subprocess.check_output(
        ["sgdisk", "-i", "2", str(image)], text=True)
    first = last = None
    for line in info.splitlines():
        if "First sector:" in line:
            first = int(line.split(":")[1].split()[0])
        if "Last sector:" in line:
            last = int(line.split(":")[1].split()[0])
    if first is None or last is None:
        raise ValueError("state partition bounds not found")
    return first * 512, (last - first + 1) * 512


def extract_state(image: Path, dest: Path) -> None:
    offset, size = state_partition(image)
    with image.open("rb") as source, dest.open("wb") as target:
        source.seek(offset)
        remaining = size
        while remaining:
            chunk = source.read(min(1 << 20, remaining))
            if not chunk:
                raise ValueError("short read on state partition")
            target.write(chunk)
            remaining -= len(chunk)


def inject_state(image: Path, state: Path) -> None:
    offset, _ = state_partition(image)
    blob = state.read_bytes()
    with image.open("r+b") as target:
        target.seek(offset)
        target.write(blob)


def debugfs(state: Path, commands: list[str]) -> str:
    script = "\n".join(commands) + "\n"
    result = subprocess.run(
        ["/usr/sbin/debugfs", "-w", "-f", "-", str(state)],
        input=script.encode(), capture_output=True)
    if result.returncode != 0:
        raise ValueError("debugfs failed: " + result.stderr.decode(errors="replace"))
    return result.stdout.decode(errors="replace")


def seed_state(state: Path, seed_file: Path) -> None:
    debugfs(state, [
        "mkdir log",
        "mkdir log/synveil",
        f"write {seed_file} log/synveil/core-audit.jsonl",
        "sif log/synveil/core-audit.jsonl mode 0100600",
    ])
    listing = debugfs(state, ["ls -l log/synveil"])
    if "core-audit.jsonl" not in listing:
        raise ValueError("seed journal not present in state filesystem")


def replay_journal(state: Path) -> None:
    """Replay the ext4 journal on the extracted scratch copy.

    The QEMU boots end by killing the emulator (a power cut), so
    the guest's journal writes are not checkpointed into the
    filesystem body; raw debugfs reads would see a stale tree
    (this hid a healthy 2.9 KB guest journal during development).
    e2fsck on the copy performs exactly the replay a mounting
    kernel would. Exit codes 0-2 are success-with-corrections."""
    result = subprocess.run(["/usr/sbin/e2fsck", "-y", str(state)],
                            capture_output=True)
    if result.returncode >= 4:
        raise ValueError("e2fsck journal replay failed")


def dump_journal(state: Path, dest: Path) -> bytes:
    with tempfile.NamedTemporaryFile(delete=False) as handle:
        raw = Path(handle.name)
    try:
        debugfs(state, [f"dump log/synveil/core-audit.jsonl {raw}"])
        return raw.read_bytes()
    finally:
        raw.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=float, default=1200)
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("audit v2 smoke requires a non-root runner")
    proof = json.loads((IMAGE_DIR / "validation.json").read_text())
    source_image = IMAGE_DIR / "synveil-x86_64.img"
    if (proof.get("schema") != "synveil.native-joined-image/v1"
            or proof.get("boot_target") != "qemu"
            or proof.get("state_partuuid") != STATE_PARTUUID
            or source_image.is_symlink() or not source_image.is_file()
            or hashlib.sha256(source_image.read_bytes()).hexdigest()
            != proof.get("image_sha256")):
        parser.error("joined image missing or changed since build")
    packaged_audit = IMAGE_DIR / "work" / "rootfs" / "usr" / "sbin" / "veil-audit"
    if not packaged_audit.is_file():
        parser.error("packaged veil-audit missing from the image rootfs staging")
    host_audit = ROOT / "target" / "debug" / "veil-audit"
    if not host_audit.is_file():
        parser.error("host veil-audit missing; run cargo build -p veil-core first")

    evidence_dir = OUT / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    seed = seed_journal_bytes()
    seed_lines = seed.decode().splitlines()
    boundary = hashlib.sha512(seed_lines[-1].encode()).hexdigest()

    test_password = secrets.token_hex(16)
    # The graphical harness types through QMP; under TCG a dropped
    # keystroke occasionally desyncs an enrollment typing. That is
    # a harness/environment flake, not audit behaviour: retry the
    # whole boot pair on a fresh seeded copy (a failed enrollment
    # may already have persisted a credential, so copies are never
    # reused). The audit assertions below never retry — a failed
    # assertion fails the run. Attempts are reported in result.json.
    journal = None
    attempts = 0
    for attempt in range(1, 4):
        attempts = attempt
        attempt_dir = evidence_dir / f"attempt-{attempt}"
        attempt_dir.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="synveil-audit-v2-") as temp:
            work = Path(temp)
            image = work / "synveil-x86_64.img"
            shutil.copyfile(source_image, image)
            state = work / "state.img"
            extract_state(image, state)
            seed_file = work / "seed.jsonl"
            seed_file.write_bytes(seed)
            seed_state(state, seed_file)
            inject_state(image, state)
            if not joined.guest_boot(work, test_password, fresh=True,
                                     timeout=args.timeout,
                                     evidence_dir=attempt_dir):
                print(f"[synveil] attempt {attempt}: first boot failed")
                continue
            if not joined.guest_boot(work, test_password, fresh=False,
                                     timeout=args.timeout,
                                     evidence_dir=attempt_dir):
                print(f"[synveil] attempt {attempt}: cold reboot failed")
                continue
            extract_state(image, state)
            replay_journal(state)
            journal = dump_journal(state, work / "journal.jsonl")
        for name in ("joined-first.log", "joined-reboot.log"):
            shutil.copyfile(attempt_dir / name, evidence_dir / name)
        break
    if journal is None:
        print("[synveil] audit v2 boots failed on all attempts")
        return 1
    (evidence_dir / "journal.jsonl").write_bytes(journal)
    # The inspector refuses anything but a private regular file.
    os.chmod(evidence_dir / "journal.jsonl", 0o600)

    lines = journal.decode().splitlines()
    if [line for line in lines[:SEED_RECORDS]] != seed_lines:
        print("[synveil] seeded v1 records were not preserved verbatim")
        return 1
    records = [json.loads(line) for line in lines]
    v2_records = [r for r in records if r["schema"] == "synveil.audit/v2"]
    if not v2_records:
        print("[synveil] guest core wrote no v2 records")
        return 1
    if v2_records[0]["prev_digest"] != boundary:
        print("[synveil] first v2 record does not chain from the v1 tail")
        return 1
    head = v2_records[-1]["record_digest"]

    def invoke(binary: Path, argv: list[str]) -> subprocess.CompletedProcess:
        return subprocess.run([str(binary), *argv], capture_output=True, text=True)

    checked = invoke(packaged_audit, ["check", "--path",
                                      str(evidence_dir / "journal.jsonl")])
    if checked.returncode != 0:
        print("[synveil] packaged veil-audit check refused the guest journal")
        return 1
    check_report = json.loads(checked.stdout)
    (evidence_dir / "check.json").write_text(checked.stdout)
    if (check_report["chain"]["anchor"] != boundary
            or check_report["chain"]["tail"] != head):
        print("[synveil] packaged check chain anchor/tail mismatch")
        return 1

    copies = OUT / "copies"
    copies.mkdir(mode=0o700, exist_ok=True)
    snapshot = copies / "guest-journal-snapshot"
    snapshot.unlink(missing_ok=True)
    exported = invoke(packaged_audit, [
        "export", "--path", str(evidence_dir / "journal.jsonl"),
        "--output", str(snapshot)])
    if exported.returncode != 0:
        print("[synveil] packaged veil-audit export failed")
        return 1
    receipt = json.loads(exported.stdout)
    (evidence_dir / "receipt.json").write_text(exported.stdout)
    chain = receipt["chain"]
    if (chain["anchor"] != boundary or chain["head_digest"] != head
            or chain["chained_records"] != len(v2_records)
            or chain["records"] != len(records)):
        print("[synveil] export receipt chain does not pin the guest segment")
        return 1

    receipt_file = copies / "receipt.json"
    receipt_file.write_text(exported.stdout)
    verified = invoke(host_audit, [
        "verify", "--path", str(snapshot), "--receipt", str(receipt_file)])
    (evidence_dir / "verify-host.txt").write_text(
        verified.stdout + verified.stderr)
    if verified.returncode != 0:
        print("[synveil] host verify --receipt refused the guest export")
        return 1
    verified_packaged = invoke(packaged_audit, [
        "verify", "--path", str(snapshot), "--receipt", str(receipt_file)])
    if verified_packaged.returncode != 0:
        print("[synveil] packaged verify --receipt refused the guest export")
        return 1
    # Negative control: a truncated snapshot must fail verification.
    truncated = copies / "truncated-snapshot"
    truncated.write_bytes(b"\n".join(
        journal.decode().splitlines()[:-1]).encode() + b"\n")
    os.chmod(truncated, 0o600)
    refused = invoke(host_audit, [
        "verify", "--path", str(truncated), "--receipt", str(receipt_file)])
    if refused.returncode == 0:
        print("[synveil] truncated snapshot passed verification (must not)")
        return 1

    result = {
        "schema": "synveil.audit-v2-native/v1",
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "image_sha256": proof["image_sha256"],
        "seed_v1_records": SEED_RECORDS,
        "total_records": len(records),
        "v2_records_written_in_guest": len(v2_records),
        "boundary_prev_digest": boundary,
        "head_digest": head,
        "packaged_check_accepted": True,
        "export_receipt_chain_matches": True,
        "host_verify_receipt": True,
        "packaged_verify_receipt": True,
        "truncated_snapshot_refused": True,
        "export_ran_inside_guest": False,
        "boot_pair_attempts": attempts,
        "physical_hardware_tested": False,
    }
    (evidence_dir / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    print("SYNVEIL_AUDIT_V2_NATIVE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
