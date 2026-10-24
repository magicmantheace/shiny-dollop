import { useEffect, useMemo, useState } from 'react';
import type { Backup, Game } from '../../shared/types';
import { useStore } from '../store';
import { IpcError, unwrap } from '../api';
import { errorSummary } from '../errorMessages';
import { formatBytes, formatDateTime } from '../format';
import SourceBadge from './SourceBadge';
import BackupDetail from './BackupDetail';

interface GameDetailProps {
  game: Game;
  onBack: () => void;
}

/**
 * Game detail: backup history (searchable), "Back up now" with live progress,
 * per-backup detail with file list, verify, and restore.
 */
export default function GameDetail({ game, onBack }: GameDetailProps): React.ReactNode {
  const { progress, backupRevision, pushToast, removeGame } = useStore();
  const [backups, setBackups] = useState<Backup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [label, setLabel] = useState('');
  const [backingUp, setBackingUp] = useState(false);
  const [backupNote, setBackupNote] = useState<string | null>(null);
  const [confirmRemove, setConfirmRemove] = useState(false);

  const activeProgress = progress[game.id];

  const load = async (): Promise<void> => {
    setLoading(true);
    setError(null);
    try {
      setBackups(unwrap(await window.saveManager.backups.list({ gameId: game.id })));
    } catch (err) {
      setError(
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not load backup history.',
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    setSelectedId(null);
    setSearch('');
    setBackupNote(null);
    void load();
  }, [game.id]);

  // Refresh when any backup for this game completes or fails.
  useEffect(() => {
    if (backupRevision > 0) {
      void load();
    }
  }, [backupRevision]);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) {
      return backups;
    }
    return backups.filter((b) => {
      const labelText = (b.label ?? '').toLowerCase();
      const stamp = formatDateTime(b.createdAt).toLowerCase();
      return labelText.includes(q) || stamp.includes(q) || b.createdAt.toLowerCase().includes(q);
    });
  }, [backups, search]);

  const selected = selectedId !== null ? (backups.find((b) => b.id === selectedId) ?? null) : null;

  const backupNow = async (): Promise<void> => {
    setBackingUp(true);
    setBackupNote(null);
    try {
      const result = unwrap(
        await window.saveManager.backups.create(
          label.trim() ? { gameId: game.id, label: label.trim() } : { gameId: game.id },
        ),
      );
      if (result.skipped) {
        setBackupNote(
          `No changes since last backup — kept the existing backup${result.backup.label ? ` "${result.backup.label}"` : ''}.`,
        );
        pushToast(
          'info',
          'No changes since last backup',
          `"${game.name}": saves are unchanged, so no new backup was created.`,
        );
      }
      setLabel('');
      await load();
    } catch (err) {
      const message =
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Backup failed.';
      setBackupNote(message);
      pushToast('error', `Backup failed for "${game.name}"`, message);
    } finally {
      setBackingUp(false);
    }
  };

  const doRemove = async (): Promise<void> => {
    try {
      await removeGame(game.id);
      pushToast('success', 'Game removed', `"${game.name}" was removed from the library.`);
      onBack();
    } catch (err) {
      pushToast(
        'error',
        'Could not remove game',
        err instanceof IpcError ? errorSummary(err.code, err.message) : 'Could not remove the game.',
      );
      setConfirmRemove(false);
    }
  };

  const progressPct =
    activeProgress && activeProgress.total > 0
      ? Math.min(100, Math.round((activeProgress.done / activeProgress.total) * 100))
      : 0;

  return (
    <section className="gsm-view" aria-label={`Backups for ${game.name}`}>
      <button type="button" className="gsm-btn gsm-btn-ghost" onClick={onBack}>
        ← Back to library
      </button>

      <div className="gsm-detail-header">
        <div>
          <h2>
            {game.name} <SourceBadge source={game.source} />
          </h2>
          <p className="gsm-muted gsm-path" title={game.savePath}>
            {game.savePath}
          </p>
        </div>
        {confirmRemove ? (
          <span className="gsm-inline-confirm">
            <span className="gsm-muted">Remove this game? Backups stay on disk.</span>
            <button type="button" className="gsm-btn gsm-btn-danger" onClick={() => void doRemove()}>
              Yes, remove
            </button>
            <button type="button" className="gsm-btn" onClick={() => setConfirmRemove(false)}>
              Keep
            </button>
          </span>
        ) : (
          <button type="button" className="gsm-btn gsm-btn-danger-ghost" onClick={() => setConfirmRemove(true)}>
            Remove game
          </button>
        )}
      </div>

      <div className="gsm-backup-actions">
        <div className="gsm-field-row">
          <label className="gsm-sr-only" htmlFor="backup-label">
            Backup label (optional)
          </label>
          <input
            id="backup-label"
            type="text"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label for this backup (optional)"
            maxLength={120}
            disabled={backingUp || activeProgress !== undefined}
          />
          <button
            type="button"
            className="gsm-btn gsm-btn-primary"
            onClick={() => void backupNow()}
            disabled={backingUp || activeProgress !== undefined}
          >
            {backingUp || activeProgress ? 'Backing up…' : 'Back up now'}
          </button>
        </div>

        {activeProgress && (
          <div
            className="gsm-progress"
            role="progressbar"
            aria-valuenow={progressPct}
            aria-valuemin={0}
            aria-valuemax={100}
            aria-label={`Backup ${activeProgress.phase === 'hash' ? 'hashing' : 'copying'} files`}
          >
            <div className="gsm-progress-bar">
              <div className="gsm-progress-fill" style={{ width: `${progressPct}%` }} />
            </div>
            <p className="gsm-progress-text">
              {activeProgress.phase === 'hash' ? 'Hashing' : 'Copying'} {activeProgress.done} of{' '}
              {activeProgress.total} files
              {activeProgress.currentFile ? (
                <>
                  {' — '}
                  <span title={activeProgress.currentFile}>{activeProgress.currentFile}</span>
                </>
              ) : null}
            </p>
          </div>
        )}

        {backupNote && !activeProgress && (
          <p className="gsm-note" role="status">
            {backupNote}
          </p>
        )}
      </div>

      <div className="gsm-view-header">
        <h3>Backup history</h3>
        <label className="gsm-search">
          <span className="gsm-sr-only">Search backup history</span>
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search labels or dates…"
            aria-label="Search backup history"
          />
        </label>
      </div>

      {loading && (
        <p className="gsm-muted" aria-busy="true">
          Loading backups…
        </p>
      )}

      {error && (
        <div className="gsm-error" role="alert">
          <strong>Couldn&apos;t load backup history.</strong>
          <p>{error}</p>
          <button type="button" className="gsm-btn" onClick={() => void load()}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && backups.length === 0 && (
        <p className="gsm-muted">No backups yet — press “Back up now” to create the first one.</p>
      )}

      {!loading && !error && backups.length > 0 && filtered.length === 0 && (
        <p className="gsm-muted">No backups match “{search}”.</p>
      )}

      {!loading && !error && filtered.length > 0 && (
        <ul className="gsm-backup-list">
          {filtered.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                className={`gsm-backup-row${selectedId === b.id ? ' gsm-backup-row-selected' : ''}`}
                onClick={() => setSelectedId(selectedId === b.id ? null : b.id)}
                aria-expanded={selectedId === b.id}
                aria-label={`Backup ${b.label ?? formatDateTime(b.createdAt)}`}
              >
                <span className="gsm-backup-row-main">
                  <strong>{b.label ?? formatDateTime(b.createdAt)}</strong>
                  <span className="gsm-muted">
                    {formatDateTime(b.createdAt)} · {b.fileCount} file{b.fileCount === 1 ? '' : 's'} ·{' '}
                    {formatBytes(b.totalBytes)}
                  </span>
                </span>
                <span className="gsm-game-row-chevron" aria-hidden="true">
                  {selectedId === b.id ? '▾' : '›'}
                </span>
              </button>
              {selectedId === b.id && <BackupDetail backup={b} game={game} />}
            </li>
          ))}
        </ul>
      )}

      {/* Keep the selected detail mounted even when a search hides its row. */}
      {selected && !filtered.includes(selected) && <BackupDetail backup={selected} game={game} />}
    </section>
  );
}
