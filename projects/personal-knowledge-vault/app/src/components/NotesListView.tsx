import { useEffect, useState } from 'react';
import { NOTE_STATUSES, getPkv, type Note, type NoteStatus, type SearchFilters } from '../types';
import { formatDateTime } from '../lib/format';
import { styles, theme } from '../styles';
import StatusBadge from './StatusBadge';
import SourceLabel from './SourceLabel';

type StatusFilter = NoteStatus | 'all';

interface NotesListViewProps {
  onOpenNote: (id: string) => void;
}

export default function NotesListView({ onOpenNote }: NotesListViewProps) {
  const [query, setQuery] = useState('');
  const [status, setStatus] = useState<StatusFilter>('all');
  const [tag, setTag] = useState('');
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    const filter: SearchFilters = {
      ...(status === 'all' ? {} : { status }),
      ...(tag.trim().length > 0 ? { tag: tag.trim() } : {}),
    };
    const request =
      query.trim().length > 0
        ? getPkv().notes.search(query.trim(), filter)
        : getPkv().notes.list(filter);
    request
      .then((result) => {
        if (!cancelled) {
          setNotes(result);
          setLoading(false);
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : 'Failed to load notes.');
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [query, status, tag]);

  return (
    <section aria-label="Notes">
      <div style={styles.toolbar} role="search">
        <div style={{ flex: '1 1 220px' }}>
          <label htmlFor="notes-search" style={styles.label}>
            Search
          </label>
          <input
            id="notes-search"
            type="search"
            style={styles.input}
            placeholder="Search titles, bodies, tags…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <div>
          <label htmlFor="notes-status-filter" style={styles.label}>
            Status
          </label>
          <select
            id="notes-status-filter"
            style={styles.select}
            value={status}
            onChange={(e) => setStatus(e.target.value as StatusFilter)}
          >
            <option value="all">All statuses</option>
            {NOTE_STATUSES.map((s) => (
              <option key={s} value={s}>
                {s[0]?.toUpperCase()}{s.slice(1)}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label htmlFor="notes-tag-filter" style={styles.label}>
            Tag
          </label>
          <input
            id="notes-tag-filter"
            type="text"
            style={styles.input}
            placeholder="Filter by tag…"
            value={tag}
            onChange={(e) => setTag(e.target.value)}
          />
        </div>
      </div>

      {error && (
        <div style={styles.alertError} role="alert">
          {error}
        </div>
      )}

      {loading ? (
        <p style={styles.muted}>Loading notes…</p>
      ) : notes.length === 0 ? (
        <p style={styles.muted}>No notes match. Try a different search or filter.</p>
      ) : (
        <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {notes.map((note) => (
            <li key={note.id}>
              <button
                type="button"
                style={styles.noteRow}
                onClick={() => onOpenNote(note.id)}
                aria-label={`Open note: ${note.title}`}
              >
                <span style={styles.noteRowTitle}>{note.title}</span>
                <span style={{ ...styles.muted, display: 'block', marginTop: '4px' }}>
                  {note.body.length > 160 ? `${note.body.slice(0, 160)}…` : note.body}
                </span>
                <span style={styles.rowMeta}>
                  <StatusBadge status={note.status} />
                  <SourceLabel sourceTitle={note.source?.title ?? null} />
                  {note.tags.map((t) => (
                    <span key={t} style={styles.tagChip}>
                      {t}
                    </span>
                  ))}
                  <span style={{ ...styles.muted, color: theme.muted }}>
                    Updated {formatDateTime(note.updatedAt)}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}

      <p style={{ ...styles.muted, marginTop: '12px' }} aria-live="polite">
        {loading ? '' : `${notes.length} note${notes.length === 1 ? '' : 's'} shown.`}
      </p>
    </section>
  );
}
