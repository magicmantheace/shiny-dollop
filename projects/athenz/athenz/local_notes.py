"""Reference local connector: notes in ONE owner-configured directory.

This is the working reference implementation for the v0.8 local
connectors framework (see :mod:`athenz.local_connectors`). It is a
real connector, not a mock:

- **Read tier** lists and reads text/markdown files from the single
  directory the owner named at opt-in time. Reads are confined to
  that directory: note names are bare file names (no separators, no
  ``..``), symlinks are refused rather than followed, and the
  resolved target must stay inside the configured directory.
- **Write tier** — only when separately approved — creates a NEW
  note file in the same directory. Creation is exclusive
  (``O_CREAT | O_EXCL``): an existing file is never overwritten,
  truncated or appended to.

Every operation passes the registry gate first
(``LocalConnectorStore.require``), so an integration that was never
opted into, or was disabled a second ago, refuses here with the
gate's distinct reason. Only ``.txt`` / ``.md`` / ``.markdown`` files
count as notes, and note content is size-bounded. Nothing here opens
a network connection or touches any path outside the one configured
directory.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat

from .local_connectors import (ConnectorError, LOCAL_NOTES_ID,
                               LocalConnectorStore)

MAX_NOTE_BYTES = 256 * 1024
TEXT_EXTENSIONS = frozenset({'.txt', '.md', '.markdown'})


class LocalNotes:
    """Gate-checked access to the owner's configured notes directory."""

    def __init__(self, home: Path | None = None):
        self.store = LocalConnectorStore(home)

    # -- gate + configuration ---------------------------------------------

    def _gate(self, tier: str) -> None:
        decision = self.store.require(LOCAL_NOTES_ID, tier)
        if not decision['allowed']:
            raise ConnectorError(
                f"local-notes {tier} refused: {decision['reason']}"
                f" (integration state: {decision['state']})")

    def _directory(self) -> Path:
        view = self.store.get(LOCAL_NOTES_ID)
        directory = (view or {}).get('config', {}).get('directory')
        if not directory:
            raise ConnectorError(
                'local-notes has no configured directory; opt in with'
                ' --directory first')
        root = Path(directory).resolve()
        if not root.is_dir():
            raise ConnectorError(
                'The configured notes directory is unavailable')
        return root

    # -- path discipline -----------------------------------------------------

    @staticmethod
    def _target(root: Path, name: str) -> Path:
        """Resolve a bare note name to a confined, symlink-free target."""
        if not isinstance(name, str) or not name.strip():
            raise ConnectorError('A note name is required')
        name = name.strip()
        if name in ('.', '..') or '/' in name or '\\' in name \
                or name.startswith('.'):
            raise ConnectorError(
                f'Note names are bare file names inside the notes'
                f' directory: {name!r}')
        if Path(name).suffix.lower() not in TEXT_EXTENSIONS:
            raise ConnectorError(
                f'Only text/markdown notes are supported'
                f' ({", ".join(sorted(TEXT_EXTENSIONS))}): {name!r}')
        candidate = root / name
        if candidate.is_symlink():
            raise ConnectorError(
                f'Symbolic links are refused, not followed: {name!r}')
        resolved = candidate.resolve()
        if resolved.parent != root:
            raise ConnectorError(
                f'Note escapes the configured directory: {name!r}')
        return resolved

    # -- read tier -------------------------------------------------------------

    def list_notes(self) -> list[dict]:
        """Metadata for every readable note in the directory (no content)."""
        self._gate('read')
        root = self._directory()
        out = []
        for entry in sorted(root.iterdir(), key=lambda p: p.name):
            if entry.is_symlink() or not entry.is_file():
                continue
            if entry.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            try:
                size = entry.stat().st_size
            except OSError:
                continue
            out.append({'name': entry.name, 'bytes': size,
                        'readable': size <= MAX_NOTE_BYTES})
        return out

    def read_note(self, name: str) -> dict:
        """Read one note's text; bounded, confined, symlink-free."""
        self._gate('read')
        root = self._directory()
        target = self._target(root, name)
        try:
            info = target.stat()
        except OSError:
            raise ConnectorError(f'No such note: {name!r}') from None
        if not stat.S_ISREG(info.st_mode):
            raise ConnectorError(f'Not a regular file: {name!r}')
        if info.st_size > MAX_NOTE_BYTES:
            raise ConnectorError(
                f'Note exceeds the {MAX_NOTE_BYTES}-byte bound: {name!r}')
        try:
            payload = target.read_bytes()
        except OSError:
            raise ConnectorError(f'Note is unreadable: {name!r}') from None
        try:
            text = payload.decode('utf-8', errors='strict')
        except UnicodeDecodeError:
            raise ConnectorError(
                f'Note is not valid UTF-8 text: {name!r}') from None
        return {'name': target.name, 'bytes': len(payload), 'text': text}

    # -- write tier ------------------------------------------------------------

    def append_note(self, name: str, text: str) -> dict:
        """Create a NEW note file with ``text``; never overwrites.

        "Append" is at the collection level: the note is added to the
        directory. An existing file with the same name is a refusal,
        not an overwrite, and its bytes are left untouched.
        """
        self._gate('write')
        if not isinstance(text, str) or not text:
            raise ConnectorError('Note text is required')
        payload = text.encode('utf-8')
        if len(payload) > MAX_NOTE_BYTES:
            raise ConnectorError(
                f'Note text exceeds the {MAX_NOTE_BYTES}-byte bound')
        root = self._directory()
        target = self._target(root, name)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL \
            | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
        try:
            handle = os.open(target, flags, 0o644)
        except FileExistsError:
            raise ConnectorError(
                f'Note already exists and is never overwritten:'
                f' {name!r}') from None
        except OSError:
            raise ConnectorError(
                f'Note could not be created: {name!r}') from None
        try:
            with os.fdopen(handle, 'wb') as stream:
                stream.write(payload)
        except OSError:
            raise ConnectorError(
                f'Note could not be written: {name!r}') from None
        return {'name': target.name, 'bytes': len(payload), 'created': True}
