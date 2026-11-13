#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Closed payload seal for the distribution-graphics stage.

The stage (tools/distro_graphics.py) resolves the Debian Mesa
+ Vulkan closure from the same pinned snapshot the Wine and
Chromium stages use, verifies every .deb against the
snapshot's own Packages index and the committed pin manifest,
extracts the closure, prunes it to the real payload (ELF
DT_NEEDED graph rooted at the Vulkan loader, the lavapipe
ICD, the GLVND dispatchers and the software gallium drivers,
per the stage builder), and seals what remains with this
module. The proof-image builder copies only sealed files,
byte-verified, and never lets a payload file replace a
differing baseline file.

Path discipline mirrors the Wine seal: payload trees keep
their distribution layout (usr/lib/x86_64-linux-gnu included)
so Mesa's compiled-in driver search paths and the Vulkan
loader's ICD discovery keep working; nothing from the
distribution's system directories (etc, var, sbin, systemd
units) is ever sealed, and the distribution libc is pruned
by the graph: the sealed image runs the project's own
glibc, always.

Only the software rendering drivers are sealed: lavapipe
(Vulkan) and llvmpipe (OpenGL/EGL via the swrast gallium
driver). Hardware Vulkan ICDs are pruned with their loader
JSONs. Mesa 25's gallium is a single unified library
entered through one dril shim, so the seal carries that
library whole but only the swrast / kms_swrast driver
entry points — and no GPU exists in the guest for any
other driver to bind. This payload is the QEMU/TCG
software stack the owner decision (ADR 0027) staged, not
a hardware graphics stack.
"""
import hashlib
import json
from pathlib import PurePosixPath

# The Vulkan loader, the lavapipe ICD and the GLVND
# dispatchers are the graph roots' public faces; the seal
# admits them plus everything under the payload trees.
BINARIES = frozenset((
    'usr/lib/x86_64-linux-gnu/libvulkan.so.1',
    'usr/lib/x86_64-linux-gnu/libvulkan_lvp.so',
))
DATA = (
    'usr/lib/x86_64-linux-gnu/',
    'usr/share/vulkan/icd.d/',
    'usr/share/glvnd/',
    'usr/share/drirc.d/',
)
GENERATED = frozenset()


def allowed(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name:
        return False
    if name in BINARIES or name in GENERATED or name.startswith(DATA):
        return True
    return name.endswith('.so') or '.so.' in name


def seal(root):
    """Hash every sealable file under the pruned staging root.
    Symlinks are recorded as links (their targets ship in the
    same payload or the baseline); regular files by content +
    mode."""
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
