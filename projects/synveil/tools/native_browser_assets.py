#!/usr/bin/env python3
# SPDX-License-Identifier: MPL-2.0
"""Explicit dependency assets for the source-built browser stage.

Mirrors tools/native_weston_assets.py: every runtime file the
browser build contributes to an image is enumerated here with its
digest, and anything outside the policy is refused at seal time and
again at overlay time. The browser stage's own data directories
(NetSurf resources, GTK schemas/themes, gdk-pixbuf loaders) are
data, never code; executables are the browser binary alone.
"""
import hashlib
import json
from pathlib import Path, PurePosixPath
import posixpath
import re
import stat

DATA = ('usr/share/netsurf/', 'usr/share/gtk-3.0/', 'usr/share/glib-2.0/',
        'usr/share/icons/', 'usr/share/themes/', 'usr/share/mime/',
        'usr/lib/gtk-3.0/', 'usr/lib/gdk-pixbuf-2.0/', 'usr/lib/gio/')
BINARIES = frozenset(('usr/bin/netsurf-gtk3',))
ALIASES = frozenset(('lib64', 'usr/lib64'))


def allowed(name):
    path = PurePosixPath(name)
    if path.is_absolute() or '..' in path.parts or str(path) != name:
        return False
    # Mesa's DRI drivers are never sealed: Mesa is the build-time
    # EGL/GLES provider only, and the browser creates no GL context
    # (docs/BROWSER.md). Sealing a software rasterizer would put a
    # rendering stack in the image that nothing is allowed to use.
    if name.startswith('usr/lib/dri/'):
        return False
    if name in BINARIES or name in ALIASES or name.startswith(DATA):
        return True
    return (name.startswith(('lib/', 'lib64/', 'usr/lib/', 'usr/lib64/')) and
            re.search(r'\.so(?:\.[0-9]+)*$', path.name) is not None)


def safe_link(name, target):
    if not target or '\0' in target:
        raise ValueError('invalid dependency symlink')
    resolved = posixpath.normpath(target.lstrip('/') if target.startswith('/')
                                 else posixpath.join(posixpath.dirname(name), target))
    if resolved == '..' or resolved.startswith('../') or not allowed(resolved):
        # Directory aliases are allowed only to the actual library directories.
        if not (name in ALIASES and resolved in ('lib', 'usr/lib')):
            raise ValueError('dependency symlink escapes component asset policy')


def entry(path, name):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode):
        target = path.readlink().as_posix()
        safe_link(name, target)
        return {'kind': 'symlink', 'target': target}
    if name in ALIASES:
        raise ValueError('library directory alias must be a symlink')
    if not stat.S_ISREG(info.st_mode):
        raise ValueError('dependency asset is not a file or symlink')
    return {'kind': 'file', 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'executable': bool(info.st_mode & 0o111)}


def seal(target, destination):
    assets = {}
    for path in target.rglob('*'):
        name = path.relative_to(target).as_posix()
        if allowed(name) and (path.is_symlink() or path.is_file()):
            assets[name] = entry(path, name)
    required = ('usr/bin/netsurf-gtk3',)
    if not all(name in assets for name in required):
        raise ValueError('native browser assets incomplete')
    if not any(name.startswith('usr/share/netsurf/') for name in assets):
        raise ValueError('NetSurf resource assets missing')
    document = {'schema': 'synveil.native-browser-assets/v1', 'assets': assets}
    destination.write_text(json.dumps(document, sort_keys=True, indent=2) + '\n')
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def verified(target, manifest, expected):
    if manifest.is_symlink() or hashlib.sha256(manifest.read_bytes()).hexdigest() != expected:
        raise ValueError('native browser asset manifest changed')
    document = json.loads(manifest.read_text())
    if document.get('schema') != 'synveil.native-browser-assets/v1':
        raise ValueError('unreviewed native browser asset schema')
    assets = document['assets']
    for name, identity in assets.items():
        for parent in (target / name).parents:
            if parent == target:
                break
            if parent.is_symlink():
                raise ValueError('dependency source parent is a symlink')
        if not allowed(name) or entry(target / name, name) != identity:
            raise ValueError('native browser asset changed or is forbidden: ' + name)
    return assets
