import { useCallback, useEffect, useRef, useState } from 'react';
import type { DocumentRecord, TemplateManifest, TokenUpdate } from '../../shared/types';
import { api, errorText } from '../api';
import { upsertRecentDoc } from '../recentDocs';
import { FieldEditor } from './FieldEditor';
import { TokenEditor } from './TokenEditor';
import { PreviewPane } from './PreviewPane';
import { ExportPanel } from './ExportPanel';

interface EditorProps {
  docId: string;
  onBack: () => void;
}

/**
 * Document editor: left panel holds the schema-generated field editor and
 * the design-token editor; the right panel shows the live (approximate)
 * preview; the export panel sits below.
 */
export function Editor({ docId, onBack }: EditorProps) {
  const [manifest, setManifest] = useState<TemplateManifest | null>(null);
  const [doc, setDoc] = useState<DocumentRecord | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  // Failed saves, tracked per field/token key: an entry means the newest
  // local value for that key is visible in the editor but was REJECTED by
  // the backend, so it is not in the persisted document (and export would
  // not include it). An entry is cleared only when that key's newest edit
  // is successfully saved — never by an unrelated edit's save.
  const [saveErrors, setSaveErrors] = useState<ReadonlyMap<string, string>>(
    () => new Map(),
  );
  const [saving, setSaving] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  // Save-race bookkeeping: every local edit gets a monotonically increasing
  // sequence number, and the newest local value per field/token key is kept
  // here. A save response carries the snapshot from when ITS mutation was
  // applied, so it must never replace local edits with a higher sequence —
  // otherwise typing `a` then `ab` snaps back to `a` when the first response
  // lands, and the next keystroke submits text missing the `b`.
  const docRef = useRef<DocumentRecord | null>(null);
  const editSeqRef = useRef(0);
  const latestFieldEditsRef = useRef(new Map<string, { seq: number; value: unknown }>());
  const latestTokenEditsRef = useRef(new Map<string, { seq: number; value: unknown }>());
  const inFlightRef = useRef(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      setLoadError(null);
      setSaveErrors(new Map());
      docRef.current = null;
      latestFieldEditsRef.current.clear();
      latestTokenEditsRef.current.clear();
      try {
        const record = await api.getDocument(docId);
        if (cancelled) return;
        const tmpl = await api.getTemplate(record.templateId);
        if (cancelled) return;
        docRef.current = record;
        setDoc(record);
        setManifest(tmpl);
        upsertRecentDoc({
          id: record.id,
          templateId: record.templateId,
          templateName: tmpl.name,
          updatedAt: record.updatedAt,
        });
      } catch (err) {
        if (!cancelled) setLoadError(errorText(err));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [docId]);

  /**
   * Merge a save response into local state WITHOUT clobbering newer edits.
   *
   * A response snapshot is only authoritative for the slice its own
   * mutation changed — every other slice may predate local edits that are
   * still in flight, and responses can also arrive out of order. So: the
   * acknowledged key(s) take the server value only when no newer local
   * edit for that key exists; all other fields/tokens keep their local
   * (optimistic) values. Metadata (updatedAt/version) never regresses.
   */
  const finalizeRecord = useCallback(
    (record: DocumentRecord, tmpl: TemplateManifest, data: Record<string, unknown>, tokens: DocumentRecord['tokens']) => {
      const current = docRef.current;
      // A response for a document that is no longer open must not revive it.
      if (current && current.id !== record.id) return;
      const merged: DocumentRecord = {
        ...record,
        data,
        tokens,
        updatedAt:
          current && current.updatedAt > record.updatedAt ? current.updatedAt : record.updatedAt,
        version: current ? Math.max(current.version, record.version) : record.version,
      };
      docRef.current = merged;
      setDoc(merged);
      upsertRecentDoc({
        id: merged.id,
        templateId: merged.templateId,
        templateName: tmpl.name,
        updatedAt: merged.updatedAt,
      });
    },
    [],
  );

  const applyFieldRecord = useCallback(
    (record: DocumentRecord, tmpl: TemplateManifest, key: string, ackSeq: number) => {
      const current = docRef.current;
      if (!current || current.id !== record.id) return;
      const data = { ...current.data };
      const latest = latestFieldEditsRef.current.get(key);
      if (!latest || latest.seq <= ackSeq) {
        // No newer local edit for this key: the server value is canonical.
        data[key] = record.data[key];
      }
      // Tokens keep their local values: this response's token snapshot may
      // predate token edits that are still in flight.
      finalizeRecord(record, tmpl, data, current.tokens);
    },
    [finalizeRecord],
  );

  const applyTokenRecord = useCallback(
    (record: DocumentRecord, tmpl: TemplateManifest, keys: string[], ackSeq: number) => {
      const current = docRef.current;
      if (!current || current.id !== record.id) return;
      const tokens = { ...current.tokens } as unknown as Record<string, unknown>;
      for (const key of keys) {
        const latest = latestTokenEditsRef.current.get(key);
        if (!latest || latest.seq <= ackSeq) {
          tokens[key] = (record.tokens as unknown as Record<string, unknown>)[key];
        }
      }
      // Field data keeps its local values: this response's data snapshot
      // may predate field edits that are still in flight.
      finalizeRecord(record, tmpl, current.data, tokens as unknown as DocumentRecord['tokens']);
    },
    [finalizeRecord],
  );

  function recordSaveError(key: string, message: string) {
    setSaveErrors((prev) => {
      if (prev.get(key) === message) return prev;
      const next = new Map(prev);
      next.set(key, message);
      return next;
    });
  }

  function clearSaveError(key: string) {
    setSaveErrors((prev) => {
      if (!prev.has(key)) return prev;
      const next = new Map(prev);
      next.delete(key);
      return next;
    });
  }

  function beginSave() {
    inFlightRef.current += 1;
    setSaving(true);
    // Deliberately does NOT clear save errors: a failed save stays
    // reported until its own key is successfully saved (see saveErrors).
  }

  function endSave() {
    inFlightRef.current = Math.max(0, inFlightRef.current - 1);
    if (inFlightRef.current === 0) setSaving(false);
  }

  async function handleFieldChange(key: string, value: unknown) {
    const current = docRef.current;
    if (!current || !manifest) return;
    const seq = ++editSeqRef.current;
    latestFieldEditsRef.current.set(key, { seq, value });
    // Optimistic local update so typing stays responsive.
    const optimistic = { ...current, data: { ...current.data, [key]: value } };
    docRef.current = optimistic;
    setDoc(optimistic);
    beginSave();
    try {
      const record = await api.updateField(current.id, key, value);
      applyFieldRecord(record, manifest, key, seq);
      // The failure warning for this key clears only once its NEWEST local
      // edit has been acknowledged; if a newer edit is still in flight, its
      // own outcome decides (a stale success must not hide a newer value
      // that may yet be rejected).
      const latest = latestFieldEditsRef.current.get(key);
      if (!latest || latest.seq <= seq) clearSaveError(key);
    } catch (err) {
      // The local draft stays visible (and stays the newest local edit, so a
      // later response for another field cannot silently revert it either).
      // Record the failure only if this edit is still the key's newest —
      // a superseded edit's failure is governed by the newer edit's save.
      if (latestFieldEditsRef.current.get(key)?.seq === seq) {
        recordSaveError(key, `Could not save “${key}”: ${errorText(err)}`);
      }
    } finally {
      endSave();
    }
  }

  async function handleTokens(partial: TokenUpdate) {
    const current = docRef.current;
    if (!current || !manifest) return;
    const seq = ++editSeqRef.current;
    const entries = Object.entries(partial).filter(([, v]) => v !== undefined);
    for (const [key, v] of entries) {
      latestTokenEditsRef.current.set(key, { seq, value: v });
    }
    // Optimistic token update, mirroring field edits: a field-save response
    // arriving later must not snap the design tokens back either.
    const optimisticTokens = { ...current.tokens } as unknown as Record<string, unknown>;
    for (const [key, v] of entries) optimisticTokens[key] = v;
    const optimistic = {
      ...current,
      tokens: optimisticTokens as unknown as DocumentRecord['tokens'],
    };
    docRef.current = optimistic;
    setDoc(optimistic);
    beginSave();
    try {
      const record = await api.updateTokens(current.id, partial);
      applyTokenRecord(record, manifest, entries.map(([k]) => k), seq);
      // Same per-key rule as field saves: a token's failure warning clears
      // only when this save acknowledged that token's newest local edit.
      for (const [key] of entries) {
        const latest = latestTokenEditsRef.current.get(key);
        if (!latest || latest.seq <= seq) clearSaveError(key);
      }
    } catch (err) {
      const message = `Could not save design tokens: ${errorText(err)}`;
      for (const [key] of entries) {
        if (latestTokenEditsRef.current.get(key)?.seq === seq) {
          recordSaveError(key, message);
        }
      }
    } finally {
      endSave();
    }
  }

  /** Focus the field editor for a manifest field key (used by export errors). */
  function focusField(key: string) {
    const root = rootRef.current;
    if (!root) return;
    const container = root.querySelector(`[data-field-key="${CSS.escape(key)}"]`);
    const target =
      container?.querySelector<HTMLElement>('input, select, textarea, button') ??
      null;
    if (target) {
      target.scrollIntoView({ block: 'center', behavior: 'smooth' });
      target.focus({ preventScroll: true });
    }
  }

  if (loadError) {
    return (
      <section className="editor">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <p role="alert" className="alert alert-error">
          Could not open document: <code>{loadError}</code>
        </p>
      </section>
    );
  }

  if (!manifest || !doc) {
    return (
      <section className="editor">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <p className="muted">Loading document…</p>
      </section>
    );
  }

  return (
    <div className="editor" ref={rootRef}>
      <header className="editor-head">
        <button type="button" className="btn btn-secondary" onClick={onBack}>
          ← Back
        </button>
        <div className="editor-title">
          <h2>
            {manifest.name} <span className="muted">v{manifest.version}</span>
          </h2>
          <p className="muted editor-status" role="status">
            {saving ? 'Saving…' : `Last saved ${new Date(doc.updatedAt).toLocaleString()}`}
          </p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setShowExport((v) => !v)}
          aria-expanded={showExport}
        >
          {showExport ? 'Hide export' : 'Export'}
        </button>
      </header>

      {[...new Set(saveErrors.values())].map((message) => (
        <p key={message} role="alert" className="alert alert-error">
          <code>{message}</code>
        </p>
      ))}

      <div className="editor-layout">
        <div className="editor-left">
          <section aria-labelledby="fields-heading" className="panel">
            <h3 id="fields-heading">Content</h3>
            <FieldEditor
              fields={manifest.fields}
              data={doc.data}
              onFieldChange={(k, v) => void handleFieldChange(k, v)}
            />
          </section>
          <section aria-labelledby="tokens-heading" className="panel">
            <h3 id="tokens-heading" className="visually-hidden">
              Design tokens
            </h3>
            <TokenEditor
              tokens={doc.tokens}
              onApply={(p) => void handleTokens(p)}
            />
          </section>
        </div>
        <div className="editor-right">
          <PreviewPane manifest={manifest} doc={doc} />
        </div>
      </div>

      {showExport && (
        <ExportPanel
          docId={doc.id}
          manifest={manifest}
          onSelectErrorField={focusField}
        />
      )}
    </div>
  );
}
