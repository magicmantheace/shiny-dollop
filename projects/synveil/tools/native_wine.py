#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Build the Wine proof image: the joined baseline rootfs plus
the sealed distribution-Wine payload, the sealed Mesa +
Vulkan graphics payload (ADR 0027), and the proof launchers.

Style follows the A/B browser proof (tools/native_ab.py): the
baseline rootfs is copied, each sealed payload is overlaid
file by file (sha256-verified, never replacing a differing
baseline file), the ELF link closure of everything added is
checked on the host, and the result is packed into the same
UKI + GPT image shape the joined build produces (build.sh
kernel + image). There is deliberately no A/B overlay, no
publisher key, and no Start-menu entry: the accepted design
scopes this slice to proving that the sealed Wine runs a
bundled Win32 GUI program under the shell, with Start-menu
presence later and marker-gated (docs/WINDOWS_COMPAT_DESIGN.md).

The graphics payload is the prerequisite for any Direct3D
path under Wine: Mesa's software stack (lavapipe Vulkan ICD,
llvmpipe GL) staged by tools/distro_graphics.py. The image
carries the guest probe /usr/libexec/synveil/gfx-probe
(compiled here from src/graphics-probe/gfx-probe.c), which
initializes Vulkan and EGL/GL against the payload and
reports GFX_* lines; staging it proves the payload is
present and initializes in the guest under QEMU/TCG
software rendering — never Direct3D, real-GPU behaviour,
or performance.

The image carries the markers /etc/synveil/wine and
/etc/synveil/graphics (future gates for session presence)
and the launcher /usr/libexec/synveil/wine-notepad. Proof
prefixes live on tmpfs; nothing about the prefix persists.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import distro_graphics_assets as gfx_assets
import distro_wine_assets as assets
import native_joined as joined

OUT = ROOT / "out" / "wine-proof"
ESP_SIZE_MB = 1024
STATE_SIZE_MB = 128


def run(argv, **kwargs):
    subprocess.run([str(a) for a in argv], check=True, **kwargs)


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git_commit():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()


def wine_stage():
    """Verify the distro-Wine stage's identity and return
    (staging_tree, assets, validation_receipt): the stage is
    only ever consumed through its sealed, digest-verified
    asset list (tools/distro_wine.py)."""
    wout = ROOT / "out" / "distro-wine"
    receipt = json.loads(joined.regular(wout / "validation.json").read_text())
    if (receipt.get("schema") != "synveil.distro-wine-stage/v1" or
            receipt.get("target") != joined.ffi.TARGET):
        raise ValueError("distro wine stage identity mismatch")
    if not (receipt.get("winewayland") or {}).get("present"):
        raise ValueError("distro wine stage lacks winewayland — "
                         "the proof does not proceed without it")
    staging = wout / "staging"
    entries = json.loads(joined.regular(wout / "assets.json").read_text())
    if assets.seal_digest(entries) != receipt.get("assets_sha256"):
        raise ValueError("distro wine seal digest mismatch")
    if not assets.verified(staging, entries):
        raise ValueError("distro wine staging does not match its seal")
    return staging, entries, receipt


def graphics_stage():
    """Verify the distro-graphics stage's identity and return
    (staging_tree, assets, validation_receipt): the stage is
    only ever consumed through its sealed, digest-verified
    asset list (tools/distro_graphics.py)."""
    gout = ROOT / "out" / "distro-graphics"
    receipt = json.loads(joined.regular(gout / "validation.json").read_text())
    if (receipt.get("schema") != "synveil.distro-graphics-stage/v1" or
            receipt.get("target") != joined.ffi.TARGET):
        raise ValueError("distro graphics stage identity mismatch")
    staging = gout / "staging"
    entries = json.loads(joined.regular(gout / "assets.json").read_text())
    if gfx_assets.seal_digest(entries) != receipt.get("assets_sha256"):
        raise ValueError("distro graphics seal digest mismatch")
    if not gfx_assets.verified(staging, entries):
        raise ValueError("distro graphics staging does not match its seal")
    return staging, entries, receipt


def copy_wine_asset(source, destination, name, identity):
    """Sealed-payload copy with the standing rule: never replace
    a file the baseline rootfs already owns unless the bytes are
    identical. Packaged modes are applied from the seal."""
    return copy_payload_asset(source, destination, name, identity,
                              assets.allowed, "wine")


def copy_graphics_asset(source, destination, name, identity):
    """The copy_wine_asset rule, for the graphics payload."""
    return copy_payload_asset(source, destination, name, identity,
                              gfx_assets.allowed, "graphics")


def copy_payload_asset(source, destination, name, identity,
                       allowed, label):
    relative = Path(name)
    if not allowed(name):
        raise ValueError(f"forbidden {label} asset")
    target = destination / relative
    parent = destination
    for part in relative.parts[:-1]:
        parent = parent / part
        if parent.is_symlink():
            raise ValueError("asset destination parent is a symlink")
        parent.mkdir(exist_ok=True)
        parent.chmod(0o755)
    if identity["kind"] == "symlink":
        if target.is_symlink() and \
                target.readlink().as_posix() == identity["target"]:
            return "identical"
        if target.exists() or target.is_symlink():
            raise ValueError("refusing to replace rootfs entry: " + name)
        target.symlink_to(identity["target"])
        return "copied"
    data = (source / relative).read_bytes()
    if hashlib.sha256(data).hexdigest() != identity["sha256"]:
        raise ValueError("sealed asset bytes changed: " + name)
    if target.exists() or target.is_symlink():
        if target.is_file() and not target.is_symlink() and \
                target.read_bytes() == data:
            return "identical"
        raise ValueError("refusing to replace rootfs file: " + name)
    with target.open("xb") as output:
        output.write(data)
    target.chmod(int(identity["mode"], 8))
    return "copied"


def check_link_closure(rootfs, tools, added):
    """Every DT_NEEDED soname of every ELF the wine stage added
    must resolve inside the finished proof rootfs (baseline
    files + copied assets together). A library the loader
    cannot find is a Wine that fails at exec — catch it at
    build time, on the host."""
    libdirs = [rootfs / "usr/lib", rootfs / "usr/lib64",
               rootfs / "lib", rootfs / "lib64",
               rootfs / "usr/lib/wine",
               rootfs / "usr/lib/x86_64-linux-gnu"]
    present = set()
    for folder in libdirs:
        if folder.is_dir():
            for entry in folder.rglob("*"):
                present.add(entry.name)
    missing = {}
    checked = 0
    for relative in added:
        path = rootfs / relative
        result = subprocess.run([str(tools["readelf"]), "-d", str(path)],
                                capture_output=True, text=True)
        if "NEEDED" not in result.stdout:
            continue
        checked += 1
        for line in result.stdout.splitlines():
            if "NEEDED" not in line:
                continue
            soname = line.split("[", 1)[1].rstrip("]\n")
            if soname not in present:
                missing.setdefault(soname, []).append(relative)
    if missing:
        raise ValueError("wine link closure incomplete: " +
                         json.dumps(missing, indent=1))
    return checked


def compile_gfx_probe(rootfs, tools):
    """Compile the graphics probe (src/graphics-probe/gfx-probe.c)
    for the guest, the native_joined way: the target compiler
    against the sealed native-dependency staging sysroot, with
    the binary proven to target the native glibc."""
    weston = joined.weston
    alias = weston.OUT / "build/staging"
    if not alias.is_dir() or \
            not alias.resolve().is_relative_to(weston.OUT.resolve()):
        raise ValueError("private native dependency sysroot missing")
    staging = alias.resolve()
    output = rootfs / "usr/libexec/synveil/gfx-probe"
    output.parent.mkdir(parents=True, exist_ok=True)
    run([tools["gcc"], "--sysroot=" + str(staging), "-std=c11",
         "-Wall", "-Wextra", "-Werror",
         ROOT / "src/graphics-probe/gfx-probe.c",
         "-ldl", "-o", output])
    header = subprocess.check_output(
        [str(tools["readelf"]), "-h", str(output)], text=True)
    program = subprocess.check_output(
        [str(tools["readelf"]), "-l", str(output)], text=True)
    if "Advanced Micro Devices X86-64" not in header or \
            "/lib64/ld-linux-x86-64.so.2" not in program:
        raise ValueError("graphics probe did not link to native "
                         "target glibc")
    output.chmod(0o755)
    return output


def build():
    staging, entries, receipt = wine_stage()
    gfx_staging, gfx_entries, gfx_receipt = graphics_stage()
    baseline_rootfs = ROOT / "out" / "native-joined" / "work" / "rootfs"
    if not (baseline_rootfs / "usr/sbin/veil-core").is_file():
        raise ValueError("joined baseline rootfs missing; "
                         "build the joined image first")
    if OUT.exists():
        shutil.rmtree(OUT)
    work = OUT / "work"
    work.mkdir(parents=True)
    rootfs = work / "rootfs"
    shutil.copytree(baseline_rootfs, rootfs, symlinks=True)

    tools, _sysroot = joined.ffi.target_tools()
    counts = {"copied": 0, "identical": 0}
    added = []
    for name, identity in sorted(entries.items()):
        outcome = copy_wine_asset(staging, rootfs, name, identity)
        counts[outcome] += 1
        if outcome == "copied" and identity["kind"] == "file":
            added.append(name)
    closure_files = check_link_closure(rootfs, tools, added)

    gfx_counts = {"copied": 0, "identical": 0}
    gfx_added = []
    for name, identity in sorted(gfx_entries.items()):
        outcome = copy_graphics_asset(gfx_staging, rootfs, name,
                                      identity)
        gfx_counts[outcome] += 1
        if outcome == "copied" and identity["kind"] == "file":
            gfx_added.append(name)
    gfx_closure_files = check_link_closure(rootfs, tools, gfx_added)
    compile_gfx_probe(rootfs, tools)

    launcher = rootfs / "usr/libexec/synveil/wine-notepad"
    shutil.copyfile(ROOT / "build/rootfs/wine-notepad", launcher)
    launcher.chmod(0o755)
    config = rootfs / "etc/synveil"
    marker = config / "wine"
    marker.write_text("")
    marker.chmod(0o644)
    gfx_marker = config / "graphics"
    gfx_marker.write_text("")
    gfx_marker.chmod(0o644)

    # Directory and file modes must not depend on the builder's
    # umask (the joined build's normalization).
    for folder, subdirs, files in os.walk(rootfs):
        Path(folder).chmod(0o755)
        for name in subdirs:
            entry = Path(folder) / name
            if not entry.is_symlink():
                entry.chmod(0o755)
        for name in files:
            entry = Path(folder) / name
            if entry.is_symlink() or entry == rootfs / 'etc/shadow':
                continue
            entry.chmod(0o755 if entry.stat().st_mode & 0o111 else 0o644)

    tmp = OUT / "tmp"
    tmp.mkdir()
    env = joined.base_env(OUT, work)
    env.update(SYNVEIL_BOOT_TARGET="qemu",
               SYNVEIL_KERNEL_SEED_WORK=str(ROOT / "build/work"),
               TMPDIR=str(tmp))
    with (OUT / "synveil-initramfs.cpio").open("wb") as archive:
        run(["bash", "-o", "pipefail", "-c",
             "find . -print0 | sort -z | cpio --null -o "
             "--format=newc --owner=0:0"],
            cwd=rootfs, stdout=archive, env=env)
    run(["bash", str(ROOT / "build.sh"), "kernel"], cwd=ROOT, env=env)
    image_env = dict(env)
    image_env.update(SYNVEIL_ESP_SIZE_MB=str(ESP_SIZE_MB),
                     SYNVEIL_STATE_SIZE_MB=str(STATE_SIZE_MB))
    run(["bash", str(ROOT / "build.sh"), "image"], cwd=ROOT,
        env=image_env)

    image = OUT / "synveil-x86_64.img"
    proof = {
        "schema": "synveil.wine-proof-build/v1",
        "source_commit": git_commit(),
        "stage_schema": receipt["schema"],
        "stage_validation_sha256": sha256(
            ROOT / "out" / "distro-wine" / "validation.json"),
        "wine_version": receipt["wine_version"],
        "winewayland": receipt["winewayland"],
        "payload_files": receipt["payload_files"],
        "payload_bytes": receipt["payload_bytes"],
        "assets_copied": counts["copied"],
        "assets_identical_to_baseline": counts["identical"],
        "link_closure_files_checked": closure_files,
        "graphics": {
            "stage_schema": gfx_receipt["schema"],
            "stage_validation_sha256": sha256(
                ROOT / "out" / "distro-graphics" / "validation.json"),
            "mesa_version": gfx_receipt["mesa_version"],
            "payload_files": gfx_receipt["payload_files"],
            "payload_bytes": gfx_receipt["payload_bytes"],
            "assets_copied": gfx_counts["copied"],
            "assets_identical_to_baseline": gfx_counts["identical"],
            "link_closure_files_checked": gfx_closure_files,
            "software_drivers": gfx_receipt["software_drivers"],
            "probe": "usr/libexec/synveil/gfx-probe",
            "decision": "ADR 0027 (owner, 2026-11-07)",
        },
        "image_sha256": sha256(image),
        "image_bytes": image.stat().st_size,
        "esp_size_mb": ESP_SIZE_MB,
        "state_size_mb": STATE_SIZE_MB,
        "physical_boot_validated": False,
    }
    (OUT / "validation.json").write_text(
        json.dumps(proof, indent=2) + "\n")
    print("SYNVEIL_WINE_PROOF_BUILT_NOT_BOOT_VALIDATED")
    print(f"image_mb={proof['image_bytes'] // 1048576} "
          f"assets_copied={counts['copied']} "
          f"closure_checked={closure_files} "
          f"gfx_copied={gfx_counts['copied']} "
          f"gfx_closure_checked={gfx_closure_files}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", required=True)
    parser.parse_args()
    build()


if __name__ == "__main__":
    main()
