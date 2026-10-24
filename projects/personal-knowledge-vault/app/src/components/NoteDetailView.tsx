import { useCallback, useEffect, useState } from 'react';
import {
  EMPTY_FORM,
  hasErrors,
  parseTags,
  validateNoteForm,
  type FormErrors,
  type NoteFormValues,
} from '../lib/validation';
import { diffLines, hasChanges, type DiffLine } from '../lib/diff';
import { formatDateTime } from '../lib/format';
import { getPkv, type Note, type Revision } from '../types';
import { styles } from '../styles';
import StatusBadge from './StatusBadge';
import SourceLabel from './SourceLabel';

interface NoteDetailViewProps {
  id: string;
  onBack: () => void;
  onOpenNote: (id: string) => void;
}

export default function NoteDetailView({ id, onBack, onOpenNote }: NoteDetailViewProps) {
  const [note, setNote] = useState<Note | null>(null);
  const [revisions, setRevisions] = useState<Revision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<NoteFormValues>(EMPTY_FORM);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const [saving, setSaving] = useState(false);

  const [rejectReason, setRejectReason] = useState('');
  const [reviewBusy, setReviewBusy] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setNotice(null);
    try {
      const pkv = getPkv();
      const record = await pkv.notes.get(id);
      if (!record) {
        setError('Note not found. It may have been deleted.');
        setNote(null);
        return;
      }
      setNote(record);
      // Revisions are returned oldest first by the backend.
      setRevisions(await pkv.revisions.list(id));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load the note.');
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const openEditor = () => {
    if (!note) return;
    setForm({
      ...EMPTY_FORM,
      title: note.title,
      body: note.body,
      tagsText: note.tags.join(', '),
      changeSummary: '',
    });
    setFormErrors({});
    setEditing(true);
  };

  const saveEdit = async () => {
    if (!note) return;
    const errors = validateNoteForm(form, { requireChangeSummary: true });
    setFormErrors(errors);
    if (hasErrors(errors)) return;
    setSaving(true);
    setError(null);
    try {
      // Canonical update patch: title/body/tags/links + required changeSummary.
      // Sources are write-once via notes.create in the current contract.
      const updated = await getPkv().notes.update(note.id, {
        title: form.title.trim(),
        body: form.body.trim(),
        tags: parseTags(form.tagsText),
        links: note.links.map((l) => l.id),
        changeSummary: form.changeSummary.trim(),
      });
      setNote(updated);
      setRevisions(await getPkv().revisions.list(note.id));
      setEditing(false);
      setNotice('Note updated. A revision was recorded with your change summary.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to save the note.');
    } finally {
      setSaving(false);
    }
  };

  const approve = async () => {
    if (!note) return;
    setReviewBusy(true);
    setError(null);
    try {
      const updated = await getPkv().review.approve(note.id);
      setNote(updated);
      setNotice('Note approved. It is now verified.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to approve the note.');
    } finally {
      setReviewBusy(false);
    }
  };

  const reject = async () => {
    if (!note) return;
    const reason = rejectReason.trim();
    if (reason.length === 0) return; // button is disabled; guard for safety
    setReviewBusy(true);
    setError(null);
    try {
      const updated = await getPkv().review.reject(note.id, reason);
      setNote(updated);
      setRejectReason('');
      setNotice('Note rejected with your reason.');
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to reject the note.');
    } finally {
      setReviewBusy(false);
    }
  };

  const setField = (field: keyof NoteFormValues) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  if (loading) {
    return <p style={styles.muted}>Loading note…</p>;
  }

  return (
    <section aria-label="Note detail">
      <button type="button" style={styles.button} onClick={onBack}>
        ← Back to notes
      </button>

      {error && (
        <div style={{ ...styles.alertError, marginTop: '12px' }} role="alert">
          {error}
        </div>
      )}
      {notice && (
        <div style={{ ...styles.alertOk, marginTop: '12px' }} role="status">
          {notice}
        </div>
      )}

      {note && (
        <>
          <div style={{ ...styles.panel, marginTop: '12px' }}>
            <div style={styles.rowMeta}>
              <StatusBadge status={note.status} />
              <SourceLabel sourceTitle={note.source?.title ?? null} />
              <span style={styles.muted}>
                {note.revisionCount} revision{note.revisionCount === 1 ? '' : 's'}
              </span>
              <span style={styles.muted}>Created {formatDateTime(note.createdAt)}</span>
              <span style={styles.muted}>Updated {formatDateTime(note.updatedAt)}</span>
            </div>
            <h2 style={{ ...styles.h2, marginTop: '10px' }}>{note.title}</h2>
            <p style={{ whiteSpace: 'pre-wrap' }}>{note.body}</p>
            {note.tags.length > 0 && (
              <div style={{ marginTop: '8px' }} aria-label="Tags">
                {note.tags.map((t) => (
                  <span key={t} style={styles.tagChip}>
                    {t}
                  </span>
                ))}
              </div>
            )}
            {note.status === 'rejected' && note.rejectionReason && (
              <p style={{ ...styles.alertError, marginTop: '12px', marginBottom: 0 }}>
                Rejected: {note.rejectionReason}
              </p>
            )}
          </div>

          <div style={styles.panel} aria-label="Source citation">
            <h3 style={styles.h3}>Source citation</h3>
            {note.source ? (
              <dl style={styles.citation}>
                {note.source.title && (
                  <>
                    <dt style={styles.label}>Title</dt>
                    <dd style={{ margin: '0 0 8px 0' }}>{note.source.title}</dd>
                  </>
                )}
                {note.source.author && (
                  <>
                    <dt style={styles.label}>Author</dt>
                    <dd style={{ margin: '0 0 8px 0' }}>{note.source.author}</dd>
                  </>
                )}
                {note.source.url && (
                  <>
                    <dt style={styles.label}>URL</dt>
                    <dd style={{ margin: '0 0 8px 0', overflowWrap: 'anywhere' }}>
                      {note.source.url}
                    </dd>
                  </>
                )}
                {note.source.docPointer && (
                  <>
                    <dt style={styles.label}>Document pointer</dt>
                    <dd style={{ margin: '0 0 8px 0' }}>{note.source.docPointer}</dd>
                  </>
                )}
                {note.source.accessedAt && (
                  <>
                    <dt style={styles.label}>Accessed</dt>
                    <dd style={{ margin: '0 0 8px 0' }}>{note.source.accessedAt}</dd>
                  </>
                )}
              </dl>
            ) : (
              <p style={styles.muted}>No source recorded for this note.</p>
            )}
          </div>

          <div style={styles.panel} aria-label="Linked records">
            <h3 style={styles.h3}>Linked records</h3>
            {note.links.length === 0 ? (
              <p style={styles.muted}>No linked records.</p>
            ) : (
              <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
                {note.links.map((l) => (
                  <li
                    key={l.id}
                    style={{ marginBottom: '6px', display: 'flex', gap: '8px', alignItems: 'center' }}
                  >
                    <button
                      type="button"
                      style={styles.linkButton}
                      onClick={() => onOpenNote(l.id)}
                    >
                      {l.title}
                    </button>
                    <StatusBadge status={l.status} />
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div style={styles.panel} aria-label="Review">
            <h3 style={styles.h3}>Review</h3>
            <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
              <button
                type="button"
                style={{
                  ...styles.buttonPrimary,
                  ...(reviewBusy || note.status === 'verified' ? styles.buttonDisabled : {}),
                }}
                disabled={reviewBusy || note.status === 'verified'}
                onClick={approve}
              >
                {note.status === 'verified' ? 'Already verified' : 'Approve'}
              </button>
              <div style={{ flex: '1 1 260px' }}>
                <label htmlFor="reject-reason" style={styles.label}>
                  Rejection reason (required to reject)
                </label>
                <input
                  id="reject-reason"
                  type="text"
                  style={styles.input}
                  placeholder="Why is this record being rejected?"
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                />
              </div>
              <button
                type="button"
                style={{
                  ...styles.buttonDanger,
                  ...(reviewBusy || rejectReason.trim().length === 0
                    ? styles.buttonDisabled
                    : {}),
                }}
                disabled={reviewBusy || rejectReason.trim().length === 0}
                onClick={reject}
              >
                Reject
              </button>
            </div>
            <p style={styles.muted}>
              Approving marks the record verified. Rejecting requires a reason so the
              decision stays auditable.
            </p>
          </div>

          <div style={styles.panel} aria-label="Edit note">
            {!editing ? (
              <button type="button" style={styles.button} onClick={openEditor}>
                Edit note
              </button>
            ) : (
              <>
                <h3 style={styles.h3}>Edit note</h3>
                <EditFormFields form={form} errors={formErrors} setField={setField} />
                <div style={{ display: 'flex', gap: '8px' }}>
                  <button
                    type="button"
                    style={{
                      ...styles.buttonPrimary,
                      ...(saving ? styles.buttonDisabled : {}),
                    }}
                    disabled={saving}
                    onClick={saveEdit}
                  >
                    {saving ? 'Saving…' : 'Save changes'}
                  </button>
                  <button
                    type="button"
                    style={styles.button}
                    disabled={saving}
                    onClick={() => setEditing(false)}
                  >
                    Cancel
                  </button>
                </div>
              </>
            )}
          </div>

          <RevisionHistoryPanel revisions={revisions} />
        </>
      )}
    </section>
  );
}

function EditFormFields({
  form,
  errors,
  setField,
}: {
  form: NoteFormValues;
  errors: FormErrors;
  setField: (
    field: keyof NoteFormValues,
  ) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => void;
}) {
  const fieldError = (name: string) =>
    errors[name] ? (
      <p style={styles.fieldError} role="alert">
        {errors[name]}
      </p>
    ) : null;
  return (
    <>
      <div style={styles.field}>
        <label htmlFor="edit-title" style={styles.label}>
          Title
        </label>
        <input id="edit-title" type="text" style={styles.input} value={form.title} onChange={setField('title')} />
        {fieldError('title')}
      </div>
      <div style={styles.field}>
        <label htmlFor="edit-body" style={styles.label}>
          Body
        </label>
        <textarea id="edit-body" style={styles.textarea} value={form.body} onChange={setField('body')} />
        {fieldError('body')}
      </div>
      <div style={styles.field}>
        <label htmlFor="edit-tags" style={styles.label}>
          Tags (comma-separated)
        </label>
        <input id="edit-tags" type="text" style={styles.input} value={form.tagsText} onChange={setField('tagsText')} />
      </div>
      <p style={styles.muted}>
        Sources are write-once: the source recorded at creation stays with the
        note&apos;s history.
      </p>
      <div style={styles.field}>
        <label htmlFor="edit-change-summary" style={styles.label}>
          Change summary (required)
        </label>
        <input
          id="edit-change-summary"
          type="text"
          style={styles.input}
          placeholder="What changed and why?"
          value={form.changeSummary}
          onChange={setField('changeSummary')}
        />
        {fieldError('changeSummary')}
      </div>
    </>
  );
}

export function RevisionHistoryPanel({ revisions }: { revisions: Revision[] }) {
  const sorted = [...revisions].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  return (
    <div style={styles.panel} aria-label="Revision history">
      <h3 style={styles.h3}>Revision history</h3>
      {sorted.length === 0 ? (
        <p style={styles.muted}>No revisions recorded yet.</p>
      ) : (
        <ol style={{ listStyle: 'none', padding: 0, margin: 0 }}>
          {sorted.map((rev, index) => {
            const prev = index === 0 ? { title: '', body: '' } : (sorted[index - 1] as Revision);
            const titleChanged = prev.title !== rev.title;
            const bodyDiff = diffLines(prev.body, rev.body);
            return (
              <li
                key={rev.id}
                style={{
                  borderTop: index === 0 ? 'none' : '1px solid #2c3a58',
                  padding: '10px 0',
                }}
              >
                <div style={styles.rowMeta}>
                  <strong>Revision {rev.revNo}</strong>
                  <span style={styles.muted}>{formatDateTime(rev.createdAt)}</span>
                </div>
                <p style={{ margin: '6px 0' }}>
                  <span style={styles.muted}>Change summary: </span>
                  {rev.changeSummary}
                </p>
                {titleChanged && (
                  <p style={{ margin: '6px 0' }}>
                    <span style={styles.muted}>Title: </span>
                    {prev.title ? <del>{prev.title}</del> : null}{' '}
                    <ins>{rev.title}</ins>
                  </p>
                )}
                {hasChanges(bodyDiff) && (
                  <div
                    style={{
                      fontFamily: 'ui-monospace, monospace',
                      fontSize: '12px',
                      background: '#0f1420',
                      borderRadius: '8px',
                      padding: '8px',
                      marginTop: '6px',
                    }}
                    aria-label={`Body diff for revision ${rev.revNo}`}
                  >
                    {bodyDiff.map((line: DiffLine, li: number) => (
                      <span
                        key={li}
                        style={
                          line.kind === 'add'
                            ? styles.diffAdd
                            : line.kind === 'del'
                              ? styles.diffDel
                              : styles.diffSame
                        }
                      >
                        {line.kind === 'add' ? '+ ' : line.kind === 'del' ? '− ' : '  '}
                        {line.text === '' ? '∅' : line.text}
                      </span>
                    ))}
                  </div>
                )}
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
