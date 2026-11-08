#!/usr/bin/env python3
"""Self-update mechanics for muse-pc-bridge (v1 §4) — stdlib only.

A release bundle is a `.zip` containing, at its root:

    bridge-release.json   {"version": "1.0.1", "files": ["agent/...", ...]}
    <the listed files, at install-root-relative paths>

Flow (the supervisor drives steps 2–4; the agent only stages):

  1. stage_update(): fetch/copy the bundle, verify its SHA-256 against
     the caller-supplied digest, extract it safely (zip-slip guarded)
     under <state>/staging/<version>/, and write the pending marker
     <state>/update-pending.json.
  2. apply_staged(): back up the current copies of every staged file
     to <state>/backup/<timestamp>/, copy staged files over the
     install root, record <state>/update-current.json.
  3. The supervisor restarts the agent and health-checks it.
  4. rollback(): if the health check failed, restore the backup and
     record the outcome in <state>/update-result.json.

Nothing here ever runs the agent or touches a live install by itself;
apply/rollback are file operations the supervisor calls at a restart
boundary.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
import urllib.request
import zipfile
from pathlib import Path

MANIFEST_NAME = "bridge-release.json"


# --------------------------------------------------------------------------
# State helpers
# --------------------------------------------------------------------------

def _read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def update_status(state_dir: Path) -> dict:
    state_dir = Path(state_dir)
    pending = _read_json(state_dir / "update-pending.json")
    current = _read_json(state_dir / "update-current.json")
    result = _read_json(state_dir / "update-result.json")
    return {"staged": pending, "current_update": current,
            "last_result": result}


# --------------------------------------------------------------------------
# Staging
# --------------------------------------------------------------------------

def _fetch_bundle(source: str, dest: Path) -> None:
    if source.startswith(("http://", "https://")):
        req = urllib.request.Request(source, headers={
            "User-Agent": "muse-pc-bridge-update"})
        with urllib.request.urlopen(req, timeout=120) as resp, \
                open(dest, "wb") as fh:
            shutil.copyfileobj(resp, fh, length=1024 * 1024)
    else:
        src = Path(source)
        if not src.exists():
            raise ValueError(f"update source not found: {source}")
        shutil.copyfile(src, dest)


def _safe_extract(bundle: Path, dest_dir: Path) -> dict:
    """Extract a release bundle; returns the parsed manifest."""
    with zipfile.ZipFile(bundle) as zf:
        names = zf.namelist()
        if MANIFEST_NAME not in names:
            raise ValueError(f"bundle has no {MANIFEST_NAME} at its root")
        manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
        files = manifest.get("files")
        if not isinstance(files, list) or not files:
            raise ValueError("manifest 'files' must be a non-empty list")
        dest_root = dest_dir.resolve()
        for name in names:
            if name.endswith("/"):
                continue
            target = (dest_root / name).resolve()
            if target != dest_root and dest_root not in target.parents:
                raise ValueError(f"bundle entry escapes staging dir: {name}")
        for name in files:
            if name not in names:
                raise ValueError(f"manifest lists a file not in the bundle: {name}")
        zf.extractall(dest_dir)
    return manifest


def _validate_version(version: str) -> None:
    """A version names exactly ONE directory under staging/.

    stage_update() rmtree()s the previous staging dir before the
    bundle is fetched or verified, so anything but a single safe
    path component — absolute paths, ``..``, separators — would aim
    that delete outside the staging root.
    """
    if not isinstance(version, str) or not version.strip():
        raise ValueError("version is required")
    if version in (".", "..") or "/" in version or "\\" in version \
            or "\x00" in version:
        raise ValueError(f"unsafe version (must be a single path "
                         f"component): {version!r}")


def stage_update(source: str, expected_sha256: str, version: str,
                 install_root: Path, state_dir: Path) -> dict:
    """Stage a release bundle for the supervisor to apply at restart."""
    _validate_version(version)
    state_dir = Path(state_dir)
    staging_root = state_dir / "staging"
    staging = staging_root / version
    if staging.resolve().parent != staging_root.resolve():
        raise ValueError(f"staging dir escapes the staging root: "
                         f"{version!r}")
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True, exist_ok=True)
    bundle_path = staging / "bundle.zip"
    _fetch_bundle(source, bundle_path)
    digest = hashlib.sha256()
    with open(bundle_path, "rb") as fh:
        for block in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(block)
    actual = digest.hexdigest()
    if actual != expected_sha256:
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError(f"bundle sha256 mismatch: expected "
                         f"{expected_sha256}, got {actual}")
    extract_dir = staging / "files"
    extract_dir.mkdir()
    manifest = _safe_extract(bundle_path, extract_dir)
    if str(manifest.get("version")) != version:
        shutil.rmtree(staging, ignore_errors=True)
        raise ValueError(f"manifest version {manifest.get('version')!r} "
                         f"does not match requested version {version!r}")
    pending = {
        "version": version,
        "files": manifest["files"],
        "bundle_sha256": actual,
        "staged_at": time.time(),
        "staging_dir": str(staging),
    }
    _write_json(state_dir / "update-pending.json", pending)
    return pending


# --------------------------------------------------------------------------
# Apply / rollback (called by the supervisor at a restart boundary)
# --------------------------------------------------------------------------

def apply_staged(state_dir: Path, install_root: Path) -> dict:
    """Copy the staged release over the install root, with backup."""
    state_dir = Path(state_dir)
    install_root = Path(install_root)
    pending = _read_json(state_dir / "update-pending.json")
    if pending is None:
        raise ValueError("no staged update is pending")
    staging = Path(pending["staging_dir"]) / "files"
    stamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
    backup_dir = state_dir / "backup" / f"{pending['version']}-{stamp}"
    backed_up: list[str] = []
    for rel in pending["files"]:
        src = staging / rel
        if not src.is_file():
            raise ValueError(f"staged file missing: {rel}")
        dst = install_root / rel
        if dst.exists():
            bak = backup_dir / rel
            bak.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(dst, bak)
            backed_up.append(rel)
    for rel in pending["files"]:
        src = staging / rel
        dst = install_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        tmp = dst.with_name(dst.name + ".update-tmp")
        shutil.copyfile(src, tmp)
        os.replace(tmp, dst)
    record = {
        "version": pending["version"],
        "files": pending["files"],
        "backed_up": backed_up,
        "backup_dir": str(backup_dir),
        "applied_at": time.time(),
    }
    _write_json(state_dir / "update-current.json", record)
    (state_dir / "update-pending.json").unlink(missing_ok=True)
    return record


def rollback(state_dir: Path, install_root: Path, reason: str = "") -> dict:
    """Restore the most recent backup taken by apply_staged()."""
    state_dir = Path(state_dir)
    install_root = Path(install_root)
    current = _read_json(state_dir / "update-current.json")
    if current is None:
        raise ValueError("no applied update to roll back")
    backup_dir = Path(current["backup_dir"])
    restored: list[str] = []
    removed: list[str] = []
    for rel in current["files"]:
        dst = install_root / rel
        bak = backup_dir / rel
        if bak.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            tmp = dst.with_name(dst.name + ".rollback-tmp")
            shutil.copyfile(bak, tmp)
            os.replace(tmp, dst)
            restored.append(rel)
        elif rel not in current.get("backed_up", []):
            # File was introduced by the update; remove it.
            if dst.exists():
                dst.unlink()
                removed.append(rel)
    result = {
        "rolled_back_version": current["version"],
        "restored": restored,
        "removed": removed,
        "reason": reason,
        "at": time.time(),
    }
    _write_json(state_dir / "update-result.json", result)
    (state_dir / "update-current.json").unlink(missing_ok=True)
    return result


def record_result(state_dir: Path, result: dict) -> None:
    result = dict(result)
    result.setdefault("at", time.time())
    _write_json(Path(state_dir) / "update-result.json", result)
