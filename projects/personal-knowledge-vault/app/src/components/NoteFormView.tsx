import { useEffect, useState } from 'react';
import {
  EMPTY_FORM,
  hasErrors,
  parseTags,
  validateNoteForm,
  type FormErrors,
  type NoteFormValues,
} from '../lib/validation';
import { getPkv, type Note, type NoteInput } from '../types';
import { styles } from '../styles';
import StatusBadge from './StatusBadge';
import SourceLabel from './SourceLabel';

interface NoteFormViewProps {
  onCreated: (id: string) => void;
}

type SourceInput = NonNullable<NoteInput['source']>;

function buildSource(values: NoteFormValues): SourceInput | undefined {
  if (values.sourceTitle.trim().length === 0) {
    return undefined;
  }
  const source: SourceInput = { title: values.sourceTitle.trim() };
  if (values.sourceAuthor.trim()) source.author = values.sourceAuthor.trim();
  if (values.sourceUrl.trim()) source.url = values.sourceUrl.trim();
  if (values.sourceDocPointer.trim()) source.docPointer = values.sourceDocPointer.trim();
  if (values.sourceAccessedAt.trim()) source.accessedAt = values.sourceAccessedAt.trim();
  return source;
}

export default function NoteFormView({ onCreated }: NoteFormViewProps) {
  const [form, setForm] = useState<NoteFormValues>(EMPTY_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [candidates, setCandidates] = useState<Note[]>([]);
  const [selectedLinks, setSelectedLinks] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Link picker: offer existing notes to link from the new note.
  useEffect(() => {
    let cancelled = false;
    getPkv()
      .notes.list({})
      .then((notes) => {
        if (!cancelled) setCandidates(notes);
      })
      .catch(() => {
        if (!cancelled) setCandidates([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const setField = (field: keyof NoteFormValues) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>,
  ) => {
    setForm((prev) => ({ ...prev, [field]: e.target.value }));
  };

  const toggleLink = (id: string) => {
    setSelectedLinks((prev) =>
      prev.includes(id) ? prev.filter((l) => l !== id) : [...prev, id],
    );
  };

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validation = validateNoteForm(form, { requireChangeSummary: false });
    setErrors(validation);
    if (hasErrors(validation)) return;
    setSaving(true);
    setSubmitError(null);
    try {
      const source = buildSource(form);
      const created = await getPkv().notes.create({
        title: form.title.trim(),
        body: form.body.trim(),
        tags: parseTags(form.tagsText),
        links: selectedLinks,
        ...(source ? { source } : {}),
      });
      setForm(EMPTY_FORM);
      setSelectedLinks([]);
      onCreated(created.id);
    } catch (err: unknown) {
      setSubmitError(err instanceof Error ? err.message : 'Failed to create the note.');
    } finally {
      setSaving(false);
    }
  };

  const fieldError = (name: string) =>
    errors[name] ? (
      <p style={styles.fieldError} role="alert">
        {errors[name]}
      </p>
    ) : null;

  return (
    <section aria-label="New note">
      <h2 style={styles.h2}>New note</h2>
      <p style={styles.muted}>
        New notes enter the vault as <strong>candidates</strong> — unverified until
        approved in review.
      </p>

      {submitError && (
        <div style={styles.alertError} role="alert">
          {submitError}
        </div>
      )}

      <form onSubmit={submit} noValidate>
        <div style={styles.panel}>
          <div style={styles.field}>
            <label htmlFor="new-title" style={styles.label}>
              Title
            </label>
            <input
              id="new-title"
              type="text"
              style={styles.input}
              value={form.title}
              onChange={setField('title')}
              aria-describedby={errors.title ? 'new-title-error' : undefined}
            />
            {errors.title && (
              <p id="new-title-error" style={styles.fieldError} role="alert">
                {errors.title}
              </p>
            )}
          </div>
          <div style={styles.field}>
            <label htmlFor="new-body" style={styles.label}>
              Body
            </label>
            <textarea
              id="new-body"
              style={styles.textarea}
              value={form.body}
              onChange={setField('body')}
            />
            {fieldError('body')}
          </div>
          <div style={styles.field}>
            <label htmlFor="new-tags" style={styles.label}>
              Tags (comma-separated)
            </label>
            <input
              id="new-tags"
              type="text"
              style={styles.input}
              placeholder="e.g. gardening, soil, reference"
              value={form.tagsText}
              onChange={setField('tagsText')}
            />
          </div>
        </div>

        <div style={styles.panel} aria-label="Source">
          <h3 style={styles.h3}>Source</h3>
          <div style={styles.field}>
            <label htmlFor="new-source-title" style={styles.label}>
              Source title
            </label>
            <input
              id="new-source-title"
              type="text"
              style={styles.input}
              placeholder="Book, article, document…"
              value={form.sourceTitle}
              onChange={setField('sourceTitle')}
            />
          </div>
          <div style={styles.field}>
            <label htmlFor="new-source-author" style={styles.label}>
              Author
            </label>
            <input
              id="new-source-author"
              type="text"
              style={styles.input}
              value={form.sourceAuthor}
              onChange={setField('sourceAuthor')}
            />
          </div>
          <div style={styles.field}>
            <label htmlFor="new-source-url" style={styles.label}>
              URL
            </label>
            <input
              id="new-source-url"
              type="text"
              style={styles.input}
              placeholder="https://…"
              value={form.sourceUrl}
              onChange={setField('sourceUrl')}
            />
            {fieldError('sourceUrl')}
          </div>
          <div style={styles.field}>
            <label htmlFor="new-source-doc" style={styles.label}>
              Document pointer
            </label>
            <input
              id="new-source-doc"
              type="text"
              style={styles.input}
              placeholder="e.g. shelf-3/binder-2 or file path"
              value={form.sourceDocPointer}
              onChange={setField('sourceDocPointer')}
            />
          </div>
          <div style={styles.field}>
            <label htmlFor="new-source-accessed" style={styles.label}>
              Accessed date
            </label>
            <input
              id="new-source-accessed"
              type="text"
              style={styles.input}
              placeholder="YYYY-MM-DD"
              value={form.sourceAccessedAt}
              onChange={setField('sourceAccessedAt')}
            />
          </div>
        </div>

        <div style={styles.panel} aria-label="Link picker">
          <h3 style={styles.h3}>Link to existing notes</h3>
          {candidates.length === 0 ? (
            <p style={styles.muted}>No existing notes to link to yet.</p>
          ) : (
            <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
              {candidates.map((c) => (
                <li key={c.id} style={{ marginBottom: '6px' }}>
                  <label style={{ display: 'flex', gap: '8px', alignItems: 'center', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={selectedLinks.includes(c.id)}
                      onChange={() => toggleLink(c.id)}
                    />
                    <span style={{ fontWeight: 600 }}>{c.title}</span>
                    <StatusBadge status={c.status} />
                    <SourceLabel sourceTitle={c.source?.title ?? null} />
                  </label>
                </li>
              ))}
            </ul>
          )}
        </div>

        <button
          type="submit"
          style={{ ...styles.buttonPrimary, ...(saving ? styles.buttonDisabled : {}) }}
          disabled={saving}
        >
          {saving ? 'Creating…' : 'Create note'}
        </button>
      </form>
    </section>
  );
}
