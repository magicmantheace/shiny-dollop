#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Distribution-Wine stage: pinned Debian snapshot in, sealed
Wine payload out.

The accepted compatibility design (docs/WINDOWS_COMPAT_DESIGN.md,
owner-accepted 2026-11-07) stages Wine exactly the way the
browser stage stages Chromium — a prebuilt distribution package
set, never a from-source build and never a download inside the
guest. This builder:

  1. resolves the install set (wine, wine64 — libwine and the
     runtime closure follow as dependencies) with apt against
     snapshot.debian.org at the timestamp pinned in
     build/manifests/distro-wine.json, starting from an EMPTY
     dpkg status so the closure is the full runtime closure,
     never the host's installed set;
  2. verifies the resolved closure equals the manifest's pin set
     exactly (name + version + sha256 + size), and every
     downloaded .deb's sha256 and size equal the snapshot's own
     Packages index entry — a moved snapshot, a substituted
     package, or an extra package all fail the build;
  3. extracts the .debs and prunes to the real payload: the ELF
     DT_NEEDED graph rooted at the Wine loaders/server and at
     every Unix-side module (.so) in the win64 module tree, the
     PE import closure rooted at the bundled programs the proof
     runs (notepad, wineboot, services, reg) and at the Wayland
     graphics driver, and the data trees the seal allows. The
     distribution's libc never enters the payload — the image
     runs the project's own glibc. The 32-bit module tree is
     pruned entirely (win64-only proof scope);
  4. seals the payload (tools/distro_wine_assets.py) and writes
     validation.json. The seal MUST contain the Wayland driver
     (x86_64-windows/winewayland.drv and its Unix half
     x86_64-unix/winewayland.so): if it does not, the build
     FAILS — the accepted design takes the winewayland.drv path
     or stops; there is no X11/XWayland fallback.

Output identity: Wine 10.0~repack-6 (Debian 13), snapshot
20261024T000000Z. The .deb cache and staging live under
out/distro-wine/ and are never committed.

Modes: --pin resolves the closure and writes the pin manifest
draft to out/distro-wine/pin-draft.json (reviewed, then
installed as build/manifests/distro-wine.json); --build runs
the full verified build against the installed manifest.
"""
import argparse
import gzip
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
import distro_wine_assets as assets
import native_libffi as ffi

OUT = ROOT / "out" / "distro-wine"
LOCK = ROOT / "build" / "manifests" / "distro-wine.json"
SNAPSHOT = "20261024T000000Z"
ARCHIVES = [
    {"name": "debian", "suite": "trixie",
     "url": f"https://snapshot.debian.org/archive/debian/{SNAPSHOT}/"},
    {"name": "debian-security", "suite": "trixie-security",
     "url": "https://snapshot.debian.org/archive/debian-security/"
            f"{SNAPSHOT}/"},
]
INSTALL = ["wine", "wine64"]

# Libraries the baseline rootfs already provides at compatible or
# newer versions (project glibc 2.44 vs Debian 13's 2.41; GCC 16
# runtime vs Debian's GCC 14): the graph treats these sonames as
# satisfied so the distribution copies are pruned.
BASELINE_SONAMES = {
    "libc.so.6", "libm.so.6", "libdl.so.2", "libpthread.so.0",
    "librt.so.1", "libresolv.so.2", "libgcc_s.so.1", "libstdc++.so.6",
    "ld-linux-x86-64.so.2",
}
WINE_MODULES = "usr/lib/x86_64-linux-gnu/wine"
WIN64_WINDOWS = WINE_MODULES + "/x86_64-windows"
WIN64_UNIX = WINE_MODULES + "/x86_64-unix"
ELF_ROOTS = (
    "usr/lib/wine/wine64",
    "usr/lib/wine/wineserver64",
    "usr/lib/wine/wineserver",
    "usr/lib/wine/wineapploader",
)
# PE roots: the bundled programs the proof runs plus the
# prefix machinery a first launch exercises, and the Wayland
# driver (loaded by name through the registry, invisible to
# any single program's import table).
PE_ROOTS = (
    "notepad.exe", "wineboot.exe", "services.exe", "reg.exe",
    "winewayland.drv",
)
# Programs Wine launches BY NAME during prefix creation and
# session startup — nothing imports them, so an import-only
# closure drops them and the session degrades (start.exe and
# rundll32.exe fail with c0000135; worse, a missing builtin
# DLL is silently replaced by an all-stub placeholder whose
# exports abort as "unimplemented function" when called —
# observed in the guest at shell32.SHGetFolderPathW and on
# the host at newdev.UpdateDriverForPlugAndPlayDevicesA).
PE_SESSION_PROGRAMS = (
    "start.exe", "explorer.exe", "winedevice.exe",
    "svchost.exe", "rpcss.exe", "plugplay.exe", "conhost.exe",
    "rundll32.exe", "control.exe", "msiexec.exe",
    "winebrowser.exe", "winemenubuilder.exe", "cmd.exe",
)
# DLLs Wine loads by name at runtime during startup/session
# (device setup, shell folders, themes, DWM probes): rooted
# when the tree carries them.
PE_SESSION_DLLS = (
    "newdev.dll", "cfgmgr32.dll", "shfolder.dll",
    "uxtheme.dll", "dwmapi.dll",
    # The API-set schema: imports naming api-ms-win-* are
    # resolved from apisetschema.dll at load time; without it
    # every apiset load fails with c000000f.
    "apisetschema.dll",
)
WAYLAND_DRV = WIN64_WINDOWS + "/winewayland.drv"
WAYLAND_UNIX = WIN64_UNIX + "/winewayland.so"


def source_pin():
    data = json.loads(LOCK.read_text())
    if data.get("schema") != "synveil.distro-wine/v1" \
            or data.get("target") != ffi.TARGET:
        raise ValueError("unreviewed distro-wine pin manifest")
    pins = data.get("packages") or []
    if len(pins) < 100 or not data.get("wine_version"):
        raise ValueError("distro-wine pin manifest looks truncated")
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
        raise ValueError("refusing privileged distro-wine pin")
    OUT.mkdir(parents=True, mode=0o700, exist_ok=True)
    debs, apt = resolve_closure()
    seen = index_entries(debs, apt)
    wine = next((e for e in seen.values()
                 if e["package"] == "libwine"), None)
    if wine is None:
        raise ValueError("closure carries no libwine")
    packages = sorted(seen.values(),
                      key=lambda e: (e["package"], e["filename"]))
    manifest = {
        "schema": "synveil.distro-wine/v1",
        "target": ffi.TARGET,
        "snapshot": SNAPSHOT,
        "archives": ARCHIVES,
        "install": INSTALL,
        "wine_version": wine["version"],
        "packages": packages,
    }
    draft = OUT / "pin-draft.json"
    draft.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"pin draft: {len(packages)} packages, "
          f"wine={wine['version']} -> {draft}")


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


def _pe_imports(path):
    """DLL names a PE file imports (regular + delay-load), or
    None when the file is not a PE image. Minimal read-only
    parser: headers, section table, import directories."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_off:pe_off + 4] != b"PE\0\0":
        return None
    coff = pe_off + 4
    sections = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic == 0x20B:  # PE32+
        dirs = opt + 112
    elif magic == 0x10B:  # PE32
        dirs = opt + 96
    else:
        return None
    sec_off = opt + opt_size
    spans = []
    for i in range(sections):
        base = sec_off + i * 40
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from(
            "<IIII", data, base + 8)
        spans.append((vaddr, max(vsize, raw_size), raw_ptr))

    def rva_to_off(rva):
        for vaddr, span, raw_ptr in spans:
            if vaddr <= rva < vaddr + span:
                return raw_ptr + (rva - vaddr)
        return None

    def read_cstr(off):
        end = data.find(b"\0", off)
        if end < 0:
            return None
        try:
            return data[off:end].decode("ascii")
        except UnicodeDecodeError:
            return None

    names = []
    for dir_index in (1, 13):  # imports, delay-load imports
        rva = struct.unpack_from("<I", data, dirs + dir_index * 8)[0]
        if not rva:
            continue
        off = rva_to_off(rva)
        if off is None:
            continue
        if dir_index == 1:
            step, name_field = 20, 12
        else:
            step, name_field = 32, 4
        for i in range(4096):
            desc = off + i * step
            if data[desc:desc + step] == b"\0" * step:
                break
            name_rva = struct.unpack_from(
                "<I", data, desc + name_field)[0]
            name_off = rva_to_off(name_rva) if name_rva else None
            if name_off is not None:
                name = read_cstr(name_off)
                if name:
                    names.append(name)
    return names


def _pe_forwarders(path):
    """DLL names this PE file's exports forward to (an export
    whose RVA lands inside the export directory is a forwarder
    string `DLL.function`; the runtime must load that DLL).
    None when not a PE image."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if len(data) < 0x40 or data[:2] != b"MZ":
        return None
    pe_off = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_off:pe_off + 4] != b"PE\0\0":
        return None
    coff = pe_off + 4
    sections = struct.unpack_from("<H", data, coff + 2)[0]
    opt_size = struct.unpack_from("<H", data, coff + 16)[0]
    opt = coff + 20
    magic = struct.unpack_from("<H", data, opt)[0]
    if magic == 0x20B:
        dirs = opt + 112
    elif magic == 0x10B:
        dirs = opt + 96
    else:
        return None
    sec_off = opt + opt_size
    spans = []
    for i in range(sections):
        base = sec_off + i * 40
        vsize, vaddr, raw_size, raw_ptr = struct.unpack_from(
            "<IIII", data, base + 8)
        spans.append((vaddr, max(vsize, raw_size), raw_ptr))

    def rva_to_off(rva):
        for vaddr, span, raw_ptr in spans:
            if vaddr <= rva < vaddr + span:
                return raw_ptr + (rva - vaddr)
        return None

    exp_rva, exp_size = struct.unpack_from("<II", data, dirs)
    if not exp_rva:
        return []
    exp_off = rva_to_off(exp_rva)
    if exp_off is None:
        return []
    n_funcs = struct.unpack_from("<I", data, exp_off + 20)[0]
    funcs_rva = struct.unpack_from("<I", data, exp_off + 28)[0]
    funcs_off = rva_to_off(funcs_rva)
    if funcs_off is None:
        return []
    out = []
    for index in range(n_funcs):
        frva = struct.unpack_from(
            "<I", data, funcs_off + index * 4)[0]
        if exp_rva <= frva < exp_rva + exp_size:
            foff = rva_to_off(frva)
            if foff is None:
                continue
            end = data.find(b"\0", foff)
            target = data[foff:end].decode("ascii", "replace")
            if "." in target:
                out.append(target.rsplit(".", 1)[0] + ".dll")
    return out


def prune(raw, staging, readelf):
    """Copy the payload subset of raw into staging."""
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)
    multiarch = raw / "usr/lib/x86_64-linux-gnu"
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
        info = _elf_needed(readelf, path) if path.is_file() \
            and not path.is_symlink() else None
        if info:
            for soname in info[0]:
                if soname in BASELINE_SONAMES:
                    continue
                target = providers.get(soname)
                if target is not None:
                    keep_file(target)

    # ELF graph: the loaders/server, then every Unix-side module
    # (the graphics/sound drivers are dlopen'd by name at runtime;
    # the tree is small and all of it is win64-relevant).
    for relative in ELF_ROOTS:
        keep_file(raw / relative)
    for path in (raw / WIN64_UNIX).rglob("*"):
        if path.is_file():
            keep_file(path)
    # The *-stable userland launchers (scripts/symlinks into
    # usr/lib/wine; the seal records them as-is).
    for name in assets.BINARIES:
        candidate = raw / name
        if candidate.exists() or candidate.is_symlink():
            keep.add(candidate)
    # PE import closure over the win64 Windows-side modules.
    windows = raw / WIN64_WINDOWS
    pe_by_name = {}
    for path in windows.iterdir():
        if path.is_file():
            pe_by_name[path.name.lower()] = path
    queue = [pe_by_name[name] for name in
             PE_ROOTS + PE_SESSION_PROGRAMS if name in pe_by_name]
    missing_roots = [name for name in
                     PE_ROOTS + PE_SESSION_PROGRAMS
                     if name not in pe_by_name]
    if missing_roots:
        raise ValueError("PE closure roots missing from libwine: "
                         + ", ".join(missing_roots))
    queue += [pe_by_name[name] for name in PE_SESSION_DLLS
              if name in pe_by_name]
    # Service DLLs: wine.inf registers svchost-hosted services
    # whose ServiceDll values name DLLs loaded by name at
    # service start (wevtsvc, qmgr, ...). Derive the set from
    # the pinned wine.inf rather than hand-listing it.
    inf = raw / "usr/share/wine/wine.inf"
    if inf.is_file():
        for line in inf.read_text(errors="replace").splitlines():
            if "ServiceDll" not in line:
                continue
            match = re.search(r"%11%\\([A-Za-z0-9_.\-]+\.dll)",
                              line)
            if match and match.group(1).lower() in pe_by_name:
                queue.append(pe_by_name[match.group(1).lower()])
    # Drivers join the WALK, not just the keep set: their own
    # imports must close too (ndis.sys needs iphlpapi.dll).
    # .drv: graphics/printer/audio drivers are loaded by name
    # from the registry. .sys: winedevice loads kernel drivers
    # by service name (mountmgr, nsiproxy, ...).
    for path in windows.iterdir():
        if path.is_file() and path.suffix.lower() in (".drv", ".sys"):
            queue.append(path)
    # A few closure imports live outside the wine tree in the
    # Debian layout: user32.dll imports zlib1.dll, which the
    # closure's libz-mingw-w64 package installs under the
    # mingw runtime dir. A real install presents it in the
    # module directory; stage it there.
    mingw_lib = raw / "usr/x86_64-w64-mingw32/lib"
    mingw_by_name = {}
    if mingw_lib.is_dir():
        for path in mingw_lib.iterdir():
            if path.is_file():
                mingw_by_name[path.name.lower()] = path
    placements = {}
    while queue:
        path = queue.pop()
        if path in keep:
            continue
        keep.add(path)
        deps = list(_pe_imports(path) or [])
        deps += _pe_forwarders(path) or []
        for imported in deps:
            target = pe_by_name.get(imported.lower())
            if target is not None and target not in keep:
                queue.append(target)
            elif target is None and imported.lower() in mingw_by_name:
                placements[imported.lower()] = \
                    mingw_by_name[imported.lower()]
    # Data trees wholesale (minus docs/man/info/locale): the
    # share/wine tree carries wine.inf (prefix creation reads
    # it), the NLS tables and the Wine fonts; share/fonts the
    # DejaVu faces the closure resolved.
    copied = 0
    for path in sorted(raw.rglob("*")):
        relative = path.relative_to(raw).as_posix()
        if path.is_dir():
            continue
        if relative.startswith(("usr/share/doc/", "usr/share/man/",
                                "usr/share/info/", "usr/share/locale/")):
            continue
        if relative.startswith(WIN64_WINDOWS + "/"):
            wanted = path in keep
        elif relative.startswith("usr/lib/x86_64-linux-gnu/wine/"
                                 "i386-windows/"):
            wanted = False
        elif relative.startswith(("usr/share/wine/", "usr/share/fonts/")):
            wanted = True
        else:
            wanted = path in keep
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
    # were kept: recreate any the copy step skipped.
    for path in sorted(multiarch.rglob("*")):
        if not path.is_symlink():
            continue
        target = (path.parent / path.readlink())
        if target in keep:
            dest = staging / path.relative_to(raw).as_posix()
            if not dest.exists() and not dest.is_symlink():
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.symlink_to(path.readlink())
                copied += 1
    # Out-of-tree imports (zlib1.dll) placed into the module
    # directory, as a real install presents them.
    for name, source in sorted(placements.items()):
        dest = staging / WIN64_WINDOWS / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        copied += 1
    return copied


def build():
    pin_data = source_pin()
    if os.geteuid() == 0:
        raise ValueError("refusing privileged distro-wine build")
    OUT.mkdir(parents=True, mode=0o700, exist_ok=True)
    debs, apt = resolve_closure()
    seen = verify_closure(pin_data, debs, apt)
    tools, _sysroot = ffi.target_tools()
    raw = OUT / "staging-raw"
    staging = OUT / "staging"
    extract_all(debs, raw)
    copied = prune(raw, staging, tools["readelf"])
    entries = assets.seal(staging)
    if len(entries) < 200:
        raise ValueError(f"payload seal implausibly small: {len(entries)}")
    # The winewayland gate (accepted design, 2026-11-07): the
    # manifest records whether the driver is present; absent
    # means STOP — no X11/XWayland fallback is taken.
    wayland = {
        "present": WAYLAND_DRV in entries and WAYLAND_UNIX in entries,
        "drv": WAYLAND_DRV if WAYLAND_DRV in entries else None,
        "unix": WAYLAND_UNIX if WAYLAND_UNIX in entries else None,
    }
    if not wayland["present"]:
        raise ValueError(
            "winewayland.drv absent from the sealed payload — "
            "stopping per docs/WINDOWS_COMPAT_DESIGN.md "
            "(no X11/XWayland fallback)")
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
        "schema": "synveil.distro-wine-stage/v1",
        "target": ffi.TARGET,
        "snapshot": pin_data["snapshot"],
        "wine_version": pin_data["wine_version"],
        "deb_packages": len(seen),
        "deb_bytes": sum(p["size"] for p in pin_data["packages"]),
        "payload_files": len(entries),
        "payload_bytes": payload_bytes,
        "payload_files_copied": copied,
        "assets_sha256": assets.seal_digest(entries),
        "winewayland": wayland,
        "scope": "win64 only; i386-windows pruned; Gecko/Mono not "
                 "installed (launcher disables the offers)",
        "glibc": "baseline project glibc (distribution libc pruned)",
        "marker": "SYNVEIL_DISTRO_WINE_STAGED_NOT_BOOTED",
    }
    (OUT / "validation.json").write_text(
        json.dumps(validation, indent=1, sort_keys=True) + "\n")
    print(validation["marker"])
    print(f"wine={pin_data['wine_version']} debs={len(seen)} "
          f"payload_files={len(entries)} "
          f"payload_mb={payload_bytes // 1048576} "
          f"winewayland=present")


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
