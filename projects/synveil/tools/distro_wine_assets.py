#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Closed payload seal for the distribution-Wine stage.

The stage (tools/distro_wine.py) resolves the Debian wine64
closure from a pinned snapshot, verifies every .deb against the
snapshot's own Packages index and the committed pin manifest,
extracts the closure, prunes it to the real payload (ELF
DT_NEEDED graph from the Wine loaders + PE import closure from
the bundled programs, per the stage builder), and seals what
remains with this module. The proof-image builder copies only
sealed files, byte-verified, and never lets a payload file
replace a differing baseline file.

Path discipline mirrors the Chromium seal: payload trees keep
their distribution layout (usr/lib/x86_64-linux-gnu included)
so Wine's compiled-in module paths keep working; the session
launcher puts the multiarch directory on LD_LIBRARY_PATH for
the Wine process only. Nothing from the distribution's system
directories (etc, var, sbin, systemd units) is ever sealed, and
the distribution libc is pruned by the graph: the sealed image
runs the project's own glibc, always.

The 32-bit module tree (i386-windows) is deliberately absent:
the accepted proof scope is win64 only (WINDOWS_COMPAT_DESIGN).
"""
import hashlib
import json
from pathlib import PurePosixPath

# The Wine userland entry points (the *-stable names are the
# distribution's alternatives-managed launchers) and the ELF
# loaders/server in usr/lib/wine.
BINARIES = frozenset((
    'usr/bin/msiexec-stable',
    'usr/bin/regedit-stable',
    'usr/bin/regsvr32-stable',
    'usr/bin/wine-stable',
    'usr/bin/wineboot-stable',
    'usr/bin/winecfg-stable',
    'usr/bin/wineconsole-stable',
    'usr/bin/winedbg-stable',
    'usr/bin/winefile-stable',
    'usr/bin/winepath-stable',
    'usr/bin/wineserver-stable',
    'usr/lib/wine/wine64',
    'usr/lib/wine/wineapploader',
    'usr/lib/wine/wineserver',
    'usr/lib/wine/wineserver64',
))
DATA = (
    'usr/lib/wine/',
    'usr/lib/x86_64-linux-gnu/wine/',
    'usr/lib/x86_64-linux-gnu/',
    'usr/share/wine/',
    'usr/share/fonts/',
)
GENERATED = frozenset()


def allowed(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name:
        return False
    if name.startswith('usr/lib/x86_64-linux-gnu/wine/i386-windows/'):
        return False  # win64-only proof scope
    if name in BINARIES or name in GENERATED or name.startswith(DATA):
        return True
    return name.endswith('.so') or '.so.' in name


def seal(root):
    """Hash every sealable file under the pruned staging root.
    Symlinks are recorded as links (their targets ship in the same
    payload or the baseline); regular files by content + mode."""
    entries = {}
    for path in sorted(root.rglob('*')):
        name = path.relative_to(root).as_posix()
        if path.is_symlink():
            if allowed(name):
                entries[name] = {'kind': 'symlink',
                                 'target': path.readlink().as_posix()}
            continue
        if not path.is_file() or not allowed(name):
            continue
        data = path.read_bytes()
        entries[name] = {
            'kind': 'file',
            'sha256': hashlib.sha256(data).hexdigest(),
            'size': len(data),
            'mode': oct(path.stat().st_mode & 0o7777),
        }
    return entries


def verified(root, entries):
    """Recompute the seal over root and compare exactly."""
    return seal(root) == entries


def seal_digest(entries):
    return hashlib.sha256(
        json.dumps(entries, sort_keys=True).encode()).hexdigest()
