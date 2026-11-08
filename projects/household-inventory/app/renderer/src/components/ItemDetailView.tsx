import { useEffect, useRef, useState } from 'react';
import { styles } from '../styles';
import {
  formatCents,
  formatBytes,
  todayISO,
  parseDollarsToCents,
  shortHash,
  MAX_ATTACHMENT_BYTES,
} from '../format';
import type { Attachment, AttachmentKind, ItemDetail, MaintenanceEvent } from '../../../shared/types';

interface ItemDetailViewProps {
  itemId: string;
  onBack: () => void;
}

const ATTACHMENT_KINDS: AttachmentKind[] = ['receipt', 'photo', 'manual', 'other'];

const ALLOWED_LABEL = 'JPEG, PNG, WebP, or PDF';

export default function ItemDetailView({ itemId, onBack }: ItemDetailViewProps) {
  const [detail, setDetail] = useState<ItemDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Attachments
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadKind, setUploadKind] = useState<AttachmentKind>('receipt');
  const [uploadWarn, setUploadWarn] = useState<string | null>(null);
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Maintenance
  const [mDate, setMDate] = useState(todayISO());
  const [mDesc, setMDesc] = useState('');
  const [mCost, setMCost] = useState('');
  const [mError, setMError] = useState<string | null>(null);
  const [mBusy, setMBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setLoading(true);
    try {
      const d = await window.inv.items.get(itemId);
      if (!d) {
        setError('This item no longer exists.');
        setDetail(null);
      } else {
        setDetail(d);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [itemId]);

  function handleFilePick(e: React.ChangeEvent<HTMLInputElement>) {
    setUploadError(null);
    const f = e.target.files?.[0] ?? null;
    setUploadFile(f);
    if (f && f.size > MAX_ATTACHMENT_BYTES) {
      setUploadWarn(
        `“${f.name}” is ${formatBytes(f.size)} — over the 20 MB limit. ` +
          'It will be rejected by the server. Pick a smaller file or compress it before uploading.',
      );
    } else {
      setUploadWarn(null);
    }
  }

  function readFileAsBase64(file: File): Promise<string> {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => {
        const dataUrl = String(reader.result ?? '');
        const comma = dataUrl.indexOf(',');
        resolve(comma >= 0 ? dataUrl.slice(comma + 1) : dataUrl);
      };
      reader.onerror = () => reject(new Error('could not read the selected file'));
      reader.readAsDataURL(file);
    });
  }

  async function handleUpload() {
    if (!uploadFile) {
      setUploadError('Choose a file first.');
      return;
    }
    if (uploadFile.size > MAX_ATTACHMENT_BYTES) {
      setUploadError('File is over the 20 MB limit and cannot be uploaded.');
      return;
    }
    setUploadBusy(true);
    setUploadError(null);
    try {
      const dataBase64 = await readFileAsBase64(uploadFile);
      await window.inv.attachments.add(itemId, {
        fileName: uploadFile.name,
        mime: uploadFile.type as 'image/jpeg' | 'image/png' | 'image/webp' | 'application/pdf',
        dataBase64,
        kind: uploadKind,
      });
      setUploadFile(null);
      setUploadWarn(null);
      if (fileInputRef.current) fileInputRef.current.value = '';
      await load();
    } catch (e) {
      setUploadError(e instanceof Error ? e.message : String(e));
    } finally {
      setUploadBusy(false);
    }
  }

  async function handleViewAttachment(att: Attachment) {
    setActionError(null);
    try {
      const file = await window.inv.attachments.get(att.id);
      if (!file) {
        setActionError(`Attachment “${att.originalName}” is missing from storage.`);
        return;
      }
      const bytes = Uint8Array.from(atob(file.dataBase64), (c) => c.charCodeAt(0));
      const blob = new Blob([bytes], { type: file.mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.target = '_blank';
      a.rel = 'noopener';
      // Downloads get a real filename; images/PDFs open in the browser tab.
      a.download = att.originalName;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleRemoveAttachment(att: Attachment) {
    setActionError(null);
    try {
      await window.inv.attachments.remove(att.id);
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    }
  }

  async function handleAddMaintenance(e: React.FormEvent) {
    e.preventDefault();
    setMError(null);
    if (!mDesc.trim()) {
      setMError('description is required');
      return;
    }
    let costCents: number | null = null;
    try {
      costCents = parseDollarsToCents(mCost);
    } catch (err) {
      setMError(err instanceof Error ? err.message : String(err));
      return;
    }
    setMBusy(true);
    try {
      await window.inv.maintenance.add(itemId, {
        eventDate: mDate,
        description: mDesc.trim(),
        costCents,
      });
      setMDesc('');
      setMCost('');
      setMDate(todayISO());
      await load();
    } catch (err) {
      setMError(err instanceof Error ? err.message : String(err));
    } finally {
      setMBusy(false);
    }
  }

  async function handleRemoveMaintenance(ev: MaintenanceEvent) {
    setActionError(null);
    try {
      await window.inv.maintenance.remove(ev.id);
      await load();
    } catch (e) {
      setActionError(e instanceof Error ? e.message : String(e));
    }
  }

  if (loading) {
    return (
      <div>
        <button style={styles.buttonSecondary} onClick={onBack}>← Back to items</button>
        <p style={styles.muted}>Loading item…</p>
      </div>
    );
  }

  if (error || !detail) {
    return (
      <div>
        <button style={styles.buttonSecondary} onClick={onBack}>← Back to items</button>
        <div style={styles.errorBox}>{error ?? 'Item not found.'}</div>
      </div>
    );
  }

  const { item, attachments, maintenance } = detail;
  const sortedMaintenance = [...maintenance].sort((a, b) => b.eventDate.localeCompare(a.eventDate));

  const field = (label: string, value: string) => (
    <div>
      <div style={styles.label}>{label}</div>
      <div style={{ fontSize: '14px' }}>{value}</div>
    </div>
  );

  return (
    <div>
      <div style={{ marginBottom: '16px' }}>
        <button style={styles.buttonSecondary} onClick={onBack}>← Back to items</button>
      </div>

      {actionError && <div style={styles.errorBox}>{actionError}</div>}

      <div style={styles.card}>
        <h2 style={styles.cardTitle}>{item.name}</h2>
        <div style={{ ...styles.formGrid, marginTop: 0 }}>
          {field('Category', item.category)}
          {field('Location', item.location || '—')}
          {field('Purchase price', formatCents(item.purchasePriceCents))}
          {field('Purchase date', item.purchaseDate ?? '—')}
          {field('Serial number', item.serialNumber ?? '—')}
          {field('Warranty start', item.warrantyStart ?? '—')}
          {field('Warranty end', item.warrantyEnd ?? '—')}
        </div>
        {item.notes && (
          <div style={{ marginTop: '12px' }}>
            <div style={styles.label}>Notes</div>
            <div style={{ fontSize: '14px', whiteSpace: 'pre-wrap' }}>{item.notes}</div>
          </div>
        )}
      </div>

      <div style={styles.card}>
        <h2 style={styles.cardTitle}>Attachments ({attachments.length})</h2>
        <p style={styles.muted}>
          Receipts, photos, and manuals are stored locally with the app. Allowed types: {ALLOWED_LABEL}.
          Max 20 MB per file.
        </p>
        <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '12px' }}>
          <div style={{ flex: '2 1 220px' }}>
            <label style={styles.label} htmlFor="inv-file">File</label>
            <input
              id="inv-file"
              ref={fileInputRef}
              type="file"
              accept="image/*,.pdf"
              onChange={handleFilePick}
              style={{ ...styles.input, padding: '6px 10px' }}
            />
          </div>
          <div style={{ flex: '1 1 140px' }}>
            <label style={styles.label} htmlFor="inv-kind">Kind</label>
            <select id="inv-kind" style={styles.select} value={uploadKind} onChange={(e) => setUploadKind(e.target.value as AttachmentKind)}>
              {ATTACHMENT_KINDS.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
          </div>
          <button style={styles.button} onClick={handleUpload} disabled={uploadBusy || !uploadFile}>
            {uploadBusy ? 'Uploading…' : 'Upload'}
          </button>
        </div>
        {uploadWarn && <div style={{ ...styles.banner, ...styles.bannerWarn }}>{uploadWarn}</div>}
        {uploadError && <div style={styles.errorBox}>{uploadError}</div>}
        {attachments.length === 0 ? (
          <p style={styles.muted}>No attachments yet.</p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Name</th>
                <th style={styles.th}>Kind</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>Size</th>
                <th style={styles.th}>SHA-256</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {attachments.map((a) => (
                <tr key={a.id}>
                  <td style={styles.td}>{a.originalName}</td>
                  <td style={styles.td}>{a.kind}</td>
                  <td style={styles.tdRight}>{formatBytes(a.sizeBytes)}</td>
                  <td style={{ ...styles.td, fontFamily: 'monospace', fontSize: '12px' }} title={a.sha256}>
                    {shortHash(a.sha256)}
                  </td>
                  <td style={styles.td}>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <button style={styles.buttonSecondary} onClick={() => handleViewAttachment(a)}>
                        View / download
                      </button>
                      <button style={styles.buttonDanger} onClick={() => handleRemoveAttachment(a)}>
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div style={styles.card}>
        <h2 style={styles.cardTitle}>Maintenance ({maintenance.length})</h2>
        <form onSubmit={handleAddMaintenance} noValidate>
          <div style={{ display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end', marginBottom: '12px' }}>
            <div style={{ flex: '0 1 160px' }}>
              <label style={styles.label} htmlFor="invm-date">Date *</label>
              <input id="invm-date" type="date" style={styles.input} value={mDate} onChange={(e) => setMDate(e.target.value)} />
            </div>
            <div style={{ flex: '2 1 240px' }}>
              <label style={styles.label} htmlFor="invm-desc">Description *</label>
              <input
                id="invm-desc"
                style={styles.input}
                value={mDesc}
                onChange={(e) => setMDesc(e.target.value)}
                placeholder="e.g. Replaced water filter"
                maxLength={1000}
              />
            </div>
            <div style={{ flex: '0 1 120px' }}>
              <label style={styles.label} htmlFor="invm-cost">Cost ($)</label>
              <input id="invm-cost" style={styles.input} value={mCost} onChange={(e) => setMCost(e.target.value)} placeholder="0.00" inputMode="decimal" />
            </div>
            <button type="submit" style={styles.button} disabled={mBusy}>
              {mBusy ? 'Adding…' : 'Add event'}
            </button>
          </div>
          {mError && <div style={styles.fieldError}>{mError}</div>}
        </form>
        {sortedMaintenance.length === 0 ? (
          <p style={styles.muted}>No maintenance events recorded.</p>
        ) : (
          <table style={styles.table}>
            <thead>
              <tr>
                <th style={styles.th}>Date</th>
                <th style={styles.th}>Description</th>
                <th style={{ ...styles.th, textAlign: 'right' }}>Cost</th>
                <th style={styles.th}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {sortedMaintenance.map((ev) => (
                <tr key={ev.id}>
                  <td style={styles.td}>{ev.eventDate}</td>
                  <td style={styles.td}>{ev.description}</td>
                  <td style={styles.tdRight}>{formatCents(ev.costCents)}</td>
                  <td style={styles.td}>
                    <button style={styles.buttonDanger} onClick={() => handleRemoveMaintenance(ev)}>
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
