#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Distribution-graphics stage: pinned Debian snapshot in,
sealed Mesa + Vulkan payload out.

The owner decision recorded in ADR 0027 (2026-11-07) stages
the graphics stack exactly the way the Wine stage stages
Wine (docs/WINDOWS_COMPAT_DESIGN.md, Graphics path option
(a)): a prebuilt distribution package set from the pinned
snapshot, never a from-source build and never a download
inside the guest. This is the prerequisite payload for any
Direct3D path under Wine (DXVK / vkd3d need Vulkan); on its
own it establishes the payload and that Vulkan/GL initialize
in the guest — under QEMU/TCG everything renders in
software, so it proves the layer works, never real-GPU
behaviour or game performance. This builder:

  1. resolves the install set (the Vulkan loader, the Mesa
     Vulkan drivers, the Mesa GL/EGL stack) with apt against
     snapshot.debian.org at the timestamp pinned in
     build/manifests/distro-graphics.json — the same snapshot
     the Wine and Chromium stages pin — starting from an
     EMPTY dpkg status so the closure is the full runtime
     closure, never the host's installed set;
  2. verifies the resolved closure equals the manifest's pin
     set exactly (name + version + sha256 + size), and every
     downloaded .deb's sha256 and size equal the snapshot's
     own Packages index entry;
  3. extracts the .debs and prunes to the real payload: the
     ELF DT_NEEDED graph rooted at the Vulkan loader, the
     lavapipe ICD, the GLVND dispatchers (libGL / libEGL /
     libGLESv2 / libGLX) and the software gallium drivers
     (swrast / kms_swrast — llvmpipe), plus the loader data
     the seal allows (the lavapipe ICD JSON, the GLVND EGL
     vendor JSON, Mesa's drirc defaults). Hardware Vulkan
     ICDs are pruned with their JSONs. Mesa 25's gallium is
     a single unified library (every driver compiled into
     libgallium, entered through one dril shim), so it
     cannot be split by driver; only the software entry
     points are sealed, and no GPU exists in the guest for
     any other driver to bind. The distribution's libc
     never enters the payload — the image runs the
     project's own glibc;
  4. seals the payload (tools/distro_graphics_assets.py) and
     writes validation.json. The seal MUST contain the
     lavapipe ICD and its loader JSON, the Mesa EGL vendor
     library and the swrast gallium driver: if any is
     missing, the build FAILS — a graphics payload that
     cannot initialize Vulkan or GL in the guest is not a
     payload.

Output identity is whatever the pin manifest records
(Mesa from Debian 13, snapshot 20261024T000000Z). The .deb
cache and staging live under out/distro-graphics/ and are
never committed.

Modes: --pin resolves the closure and writes the pin
manifest draft to out/distro-graphics/pin-draft.json
(reviewed, then installed as
build/manifests/distro-graphics.json); --build runs the
full verified build against the installed manifest.
"""
import argparse
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import distro_graphics_assets as assets
import native_libffi as ffi

OUT = ROOT / "out" / "distro-graphics"
LOCK = ROOT / "build" / "manifests" / "distro-graphics.json"
SNAPSHOT = "20261024T000000Z"
ARCHIVES = [
    {"name": "debian", "suite": "trixie",
     "url": f"https://snapshot.debian.org/archive/debian/{SNAPSHOT}/"},
    {"name": "debian-security", "suite": "trixie-security",
     "url": "https://snapshot.debian.org/archive/debian-security/"
            f"{SNAPSHOT}/"},
]
INSTALL = ["libvulkan1", "mesa-vulkan-drivers", "libgl1-mesa-dri",
           "libglx-mesa0", "libegl-mesa0", "libegl1", "libgl1",
           "libgles2"]

# Libraries the baseline rootfs already provides at compatible
# or newer versions (project glibc 2.44 vs Debian 13's 2.41;
# GCC 16 runtime vs Debian's GCC 14): the graph treats these
# sonames as satisfied so the distribution copies are pruned.
BASELINE_SONAMES = {
    "libc.so.6", "libm.so.6", "libdl.so.2", "libpthread.so.0",
    "librt.so.1", "libresolv.so.2", "libgcc_s.so.1", "libstdc++.so.6",
    "ld-linux-x86-64.so.2",
}
MULTIARCH = "usr/lib/x86_64-linux-gnu"
# ELF graph roots: the Vulkan loader and its software ICD,
# the GLVND dispatchers (whose providers are Mesa's vendor
# libraries), and the software gallium drivers — llvmpipe
# lives in the swrast driver; kms_swrast is its KMS twin.
ELF_ROOTS = (
    MULTIARCH + "/libvulkan.so.1",
    MULTIARCH + "/libvulkan_lvp.so",
    MULTIARCH + "/libGL.so.1",
    MULTIARCH + "/libEGL.so.1",
    MULTIARCH + "/libGLESv2.so.2",
    MULTIARCH + "/libGLX.so.0",
    # The GLVND vendor libraries are loaded BY NAME through
    # the vendor registry JSONs at runtime — invisible to any
    # dispatcher's DT_NEEDED — so they are graph roots too.
    MULTIARCH + "/libEGL_mesa.so.0",
    MULTIARCH + "/libGLX_mesa.so.0",
    MULTIARCH + "/dri/swrast_dri.so",
    MULTIARCH + "/dri/kms_swrast_dri.so",
)
LVP_SONAME_PATH = MULTIARCH + "/libvulkan_lvp.so"
LVP_JSON = "usr/share/vulkan/icd.d/lvp_icd.json"
EGL_MESA = MULTIARCH + "/libEGL_mesa.so.0"
GLX_MESA = MULTIARCH + "/libGLX_mesa.so.0"
SWRAST = MULTIARCH + "/dri/swrast_dri.so"
# Data files the payload carries wholesale: the lavapipe
# loader JSON (the ONLY ICD JSON — hardware ICD libraries
# are pruned, so their JSONs must not ship), the GLVND EGL
# vendor registry, and Mesa's drirc defaults.
DATA_FILES = (
    LVP_JSON,
    "usr/share/glvnd/egl_vendor.d/50_mesa.json",
)
DATA_DIRS = (
    "usr/share/drirc.d/",
)


def source_pin():
    data = json.loads(LOCK.read_text())
    if data.get("schema") != "synveil.distro-graphics/v1" \
            or data.get("target") != ffi.TARGET:
        raise ValueError("unreviewed distro-graphics pin manifest")
    pins = data.get("packages") or []
    if len(pins) < 20 or not data.get("mesa_version"):
        raise ValueError("distro-graphics pin manifest looks truncated")
    return data


def run(argv, **kwargs):
    subprocess.run([str(a) for a in argv], check=True, **kwargs)


def resolve_closure():
    """apt update + download-only against the pinned snapshot,
    from an empty dpkg status. Returns (deb paths, apt dir)."""
    apt = OUT / "apt"
    (apt / "state/lists/partial").mkdir(parents=True, exist_ok=True)
    (apt / "cache/archives/partial").mkdir(parents=True, exist_ok=True)
    (apt / "etc").mkdir(parents=True, exist_ok=True)
    (apt / "status").touch()
    sources = apt / "sources.list"
    sources.write_text("".join(
        f"deb [trusted=yes] {a['url']} {a['suite']} main\n"
        for a in ARCHIVES))
    opts = [
        "-o", f"Dir::State={apt}/state",
        "-o", f"Dir::Cache={apt}/cache",
        "-o", f"Dir::Etc::sourcelist={sources}",
        "-o", "Dir::Etc::sourceparts=-",
        "-o", f"Dir::Etc::dpkg={apt}/etc",
        "-o", f"Dir::State::status={apt}/status",
        "-o", "APT::Architecture=amd64",
        "-o", "Acquire::Languages=none",
        "-o", "APT::Sandbox::User=root",
        # The snapshot is immutable and every downloaded .deb is
        # sha256-verified against both the manifest and the
        # snapshot's own Packages index (verify_closure); a
        # Valid-Until check on a pinned historical snapshot can
        # only fire spuriously. Freshness is not a property this
        # stage takes from apt.
        "-o", "Acquire::Check-Valid-Until=false",
    ]
    env = dict(os.environ, LC_ALL="C")
    run(["apt-get", *opts, "update"], env=env,
        stdout=subprocess.DEVNULL)
    run(["apt-get", *opts, "-y", "--download-only",
         "--no-install-recommends", "install", *INSTALL], env=env,
        stdout=subprocess.DEVNULL)
    return sorted((apt / "cache/archives").glob("*.deb")), apt


def packages_index(apt):
    """filename -> pin-shaped entry, from the fetched indices."""
    index = {}
    for path in (apt / "state/lists").glob("*_Packages*"):
        raw = path.read_bytes()
        if path.suffix == ".xz":
            raw = lzma.decompress(raw)
        elif path.suffix == ".gz":
            raw = gzip.decompress(raw)
        for stanza in raw.decode("utf-8", "replace").split("\n\n"):
            fields, key = {}, None
            for line in stanza.splitlines():
                if line.startswith(" ") and key:
                    fields[key] += "\n" + line
                elif ": " in line:
                    key, _, value = line.partition(": ")
                    fields[key] = value
            if "Package" in fields and "SHA256" in fields:
                index[fields["Filename"]] = {
                    "package": fields["Package"],
                    "version": fields["Version"],
                    "filename": fields["Filename"],
                    "sha256": fields["SHA256"],
                    "size": int(fields["Size"]),
                }
    return index


def index_entries(debs, apt):
    """Match every downloaded .deb to its snapshot index entry
    by content (sha256 + size). Raises on any unmatched .deb."""
    index = packages_index(apt)
    seen = {}
    for deb in debs:
        data = deb.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        entry = next((e for e in index.values()
                      if e["sha256"] == sha and e["size"] == len(data)),
                     None)
        if entry is None:
            raise ValueError(f"{deb.name}: not in the snapshot index")
        seen[entry["filename"]] = entry
    return seen


def verify_closure(pin, debs, apt):
    seen = index_entries(debs, apt)
    # Identity is content (package, version, sha256, size): the
    # same .deb can appear under pool/main and pool/updates paths
    # in different archives, and the filename is not the identity.
    pins = {(p["package"], p["version"], p["sha256"], p["size"])
            for p in pin["packages"]}
    identities = {(e["package"], e["version"], e["sha256"], e["size"])
                  for e in seen.values()}
    if identities != pins:
        raise ValueError("closure does not equal the pin manifest")
    return seen


def pin():
    if os.geteuid() == 0:
        raise ValueError("refusing privileged distro-graphics pin")
    OUT.mkdir(parents=True, mode=0o700, exist_ok=True)
    debs, apt = resolve_closure()
    seen = index_entries(debs, apt)
    mesa = next((e for e in seen.values()
                 if e["package"] == "mesa-vulkan-drivers"), None)
    if mesa is None:
        raise ValueError("closure carries no mesa-vulkan-drivers")
    packages = sorted(seen.values(),
                      key=lambda e: (e["package"], e["filename"]))
    manifest = {
        "schema": "synveil.distro-graphics/v1",
        "target": ffi.TARGET,
        "snapshot": SNAPSHOT,
        "archives": ARCHIVES,
        "install": INSTALL,
        "mesa_version": mesa["version"],
        "packages": packages,
    }
    draft = OUT / "pin-draft.json"
    draft.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"pin draft: {len(packages)} packages, "
          f"mesa={mesa['version']} -> {draft}")


def extract_all(debs, raw):
    if raw.exists():
        shutil.rmtree(raw)
    raw.mkdir(parents=True)
    for deb in debs:
        run(["dpkg-deb", "-x", str(deb), str(raw)],
            stdout=subprocess.DEVNULL)


def _elf_needed(readelf, path):
    try:
        out = subprocess.check_output(
            [str(readelf), "-d", str(path)], text=True,
            stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        return None  # not a dynamic ELF
    needed = []
    soname = None
    for line in out.splitlines():
        if "NEEDED" in line:
            needed.append(line.split("[", 1)[1].rstrip("]\n"))
        if "SONAME" in line:
            soname = line.split("[", 1)[1].rstrip("]\n")
    return needed, soname


def prune(raw, staging, readelf):
    """Copy the payload subset of raw into staging."""
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    multiarch = raw / MULTIARCH
    providers = {}
    for path in multiarch.rglob("*"):
        if path.is_file() and not path.is_symlink():
            info = _elf_needed(readelf, path)
            if info and info[1]:
                providers[info[1]] = path
            providers.setdefault(path.name, path)
    keep = set()

    def keep_file(path):
        if path in keep or not path.exists():
            return
        keep.add(path)
        if path.is_symlink():
            # Several graph roots are soname links (libvulkan.so.1,
            # libGL.so.1) and the gallium drivers may link into
            # mesa-libgallium: keep the link AND walk its target.
            target = Path(os.path.normpath(path.parent
                                           / path.readlink()))
            if target.exists():
                keep_file(target)
            return
        info = _elf_needed(readelf, path) if path.is_file() else None
        if info:
            for soname in info[0]:
                if soname in BASELINE_SONAMES:
                    continue
                target = providers.get(soname)
                if target is not None:
                    keep_file(target)

    for relative in ELF_ROOTS:
        root = raw / relative
        if not root.exists():
            raise ValueError(f"graphics graph root missing: {relative}")
        keep_file(root)
    # Loader data: exact files plus the drirc defaults tree.
    copied = 0
    wanted_data = set()
    for relative in DATA_FILES:
        if (raw / relative).is_file():
            wanted_data.add(raw / relative)
    for prefix in DATA_DIRS:
        for path in (raw / prefix.rstrip("/")).rglob("*"):
            if path.is_file():
                wanted_data.add(path)
    for path in sorted(raw.rglob("*")):
        relative = path.relative_to(raw).as_posix()
        if path.is_dir():
            continue
        if path in keep:
            wanted = True
        elif relative.startswith(MULTIARCH + "/"):
            wanted = False
        else:
            wanted = path in wanted_data
        if not wanted:
            continue
        dest = staging / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            dest.symlink_to(path.readlink())
        else:
            shutil.copy2(path, dest)
        copied += 1
    # Symlinks into kept library files (soname links) whose targets
    # were kept: recreate any the copy step skipped. DRI driver
    # links are the exception: every *_dri.so in this Mesa build
    # links to the one dril shim, so the rule "target kept" would
    # recreate every hardware driver's entry point. Only the
    # rooted software drivers (swrast, kms_swrast) are sealed.
    rooted = set(ELF_ROOTS)
    for path in sorted(multiarch.rglob("*")):
        if not path.is_symlink():
            continue
        relative = path.relative_to(raw).as_posix()
        if relative.startswith(MULTIARCH + "/dri/") \
                and relative not in rooted:
            continue
        target = (path.parent / path.readlink())
        if target in keep:
            dest = staging / path.relative_to(raw).as_posix()
            if not dest.exists() and not dest.is_symlink():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(path.readlink())
                copied += 1
    return copied


def build():
    pin_data = source_pin()
    if os.geteuid() == 0:
        raise ValueError("refusing privileged distro-graphics build")
    OUT.mkdir(parents=True, mode=0o700, exist_ok=True)
    debs, apt = resolve_closure()
    seen = verify_closure(pin_data, debs, apt)
    tools, _sysroot = ffi.target_tools()
    raw = OUT / "staging-raw"
    staging = OUT / "staging"
    extract_all(debs, raw)
    copied = prune(raw, staging, tools["readelf"])
    entries = assets.seal(staging)
    if len(entries) < 40:
        raise ValueError(f"payload seal implausibly small: {len(entries)}")
    # The initialization gate: the payload exists so Vulkan and
    # GL can initialize in the guest. If the software drivers
    # are not in the seal, there is nothing to initialize with —
    # stop, exactly as the Wine stage stops without
    # winewayland.drv.
    required = {
        "vulkan_loader": MULTIARCH + "/libvulkan.so.1",
        "lavapipe_icd": LVP_SONAME_PATH,
        "lavapipe_icd_json": LVP_JSON,
        "egl_mesa": EGL_MESA,
        "glx_mesa": GLX_MESA,
        "swrast_gallium": SWRAST,
    }
    missing = [name for name, rel in required.items()
               if rel not in entries]
    if missing:
        raise ValueError(
            "graphics payload lacks " + ", ".join(missing) +
            " — stopping: a payload that cannot initialize "
            "Vulkan/GL is not a payload (ADR 0027)")
    # The payload is system data the unprivileged session reads:
    # nothing in it may be sealed without other-read.
    unreadable = [name for name, e in entries.items()
                  if e["kind"] == "file" and not int(e["mode"], 8) & 0o004]
    if unreadable:
        raise ValueError("payload files not world-readable: "
                         + ", ".join(sorted(unreadable)[:5]))
    payload_bytes = sum(e.get("size", 0) for e in entries.values())
    (OUT / "assets.json").write_text(
        json.dumps(entries, indent=1, sort_keys=True) + "\n")
    validation = {
        "schema": "synveil.distro-graphics-stage/v1",
        "target": ffi.TARGET,
        "snapshot": pin_data["snapshot"],
        "mesa_version": pin_data["mesa_version"],
        "deb_packages": len(seen),
        "deb_bytes": sum(p["size"] for p in pin_data["packages"]),
        "payload_files": len(entries),
        "payload_bytes": payload_bytes,
        "payload_files_copied": copied,
        "assets_sha256": assets.seal_digest(entries),
        "software_drivers": {
            "vulkan": "lavapipe (libvulkan_lvp.so, Mesa)",
            "opengl": "llvmpipe (swrast gallium driver, Mesa)",
        },
        "required_present": sorted(required),
        "scope": "software rendering only (llvmpipe/lavapipe); "
                 "hardware Vulkan ICDs pruned; gallium sealed "
                 "whole (Mesa 25 unified libgallium) with only "
                 "the swrast/kms_swrast entry points; Direct3D "
                 "itself (DXVK/vkd3d) not included — this "
                 "payload is its prerequisite (ADR 0027)",
        "glibc": "baseline project glibc (distribution libc pruned)",
        "marker": "SYNVEIL_DISTRO_GRAPHICS_STAGED_NOT_BOOTED",
    }
    (OUT / "validation.json").write_text(
        json.dumps(validation, indent=1, sort_keys=True) + "\n")
    print(validation["marker"])
    print(f"mesa={pin_data['mesa_version']} debs={len(seen)} "
          f"payload_files={len(entries)} "
          f"payload_mb={payload_bytes // 1048576} "
          f"lavapipe=present llvmpipe=present")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--pin", action="store_true")
    mode.add_argument("--build", action="store_true")
    args = parser.parse_args()
    if args.pin:
        pin()
    else:
        build()


if __name__ == "__main__":
    main()
