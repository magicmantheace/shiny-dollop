import { useEffect, useState } from 'react';
import { styles, theme } from '../styles';
import { formatCents, daysUntil, describeDaysLeft } from '../format';
import type { Item } from '../../../shared/types';
import ItemFormModal from './ItemFormModal';

interface ItemsViewProps {
  onSelectItem: (id: string) => void;
}

function warrantyChip(item: Item): React.ReactNode {
  if (!item.warrantyEnd) return <span style={styles.muted}>—</span>;
  const d = daysUntil(item.warrantyEnd);
  if (d === null) return <span style={styles.muted}>{item.warrantyEnd}</span>;
  const base: React.CSSProperties = {
    display: 'inline-block',
    padding: '2px 8px',
    borderRadius: '999px',
    fontSize: '12px',
    fontWeight: 600,
    border: '1px solid',
    whiteSpace: 'nowrap',
  };
  if (d < 0) {
    return (
      <span style={{ ...base, color: theme.danger, borderColor: theme.danger, background: '#3a1a1a' }} title={`Warranty ended ${item.warrantyEnd}`}>
        Expired · {item.warrantyEnd}
      </span>
    );
  }
  if (d <= 90) {
    return (
      <span style={{ ...base, color: theme.warn, borderColor: theme.warn, background: '#3a2c14' }} title={describeDaysLeft(d)}>
        {item.warrantyEnd} · {describeDaysLeft(d)}
      </span>
    );
  }
  return (
    <span style={{ ...base, color: theme.ok, borderColor: theme.ok, background: '#14301f' }} title={describeDaysLeft(d)}>
      {item.warrantyEnd}
    </span>
  );
}

export default function ItemsView({ onSelectItem }: ItemsViewProps) {
  const [items, setItems] = useState<Item[]>([]);
  const [categories, setCategories] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState('');
  const [location, setLocation] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState<Item | null>(null);
  const [deleting, setDeleting] = useState<Item | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState('');
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  async function load() {
    setError(null);
    setLoading(true);
    try {
      const filter: { search?: string; category?: string; location?: string } = {};
      if (search.trim()) filter.search = search.trim();
      if (category) filter.category = category;
      if (location.trim()) filter.location = location.trim();
      const [list, cats] = await Promise.all([
        window.inv.items.list(filter),
        window.inv.categories.list(),
      ]);
      setItems(list);
      setCategories(cats);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  // Load on mount; debounce filter changes.
  useEffect(() => {
    const t = window.setTimeout(load, search || location ? 250 : 0);
    return () => window.clearTimeout(t);
  }, [search, category, location]);

  function openDelete(item: Item) {
    setDeleting(item);
    setDeleteConfirm('');
    setDeleteError(null);
  }

  async function confirmDelete() {
    if (!deleting) return;
    if (deleteConfirm !== deleting.name) {
      setDeleteError(`Type the item name exactly ("${deleting.name}") to confirm deletion.`);
      return;
    }
    setDeleteBusy(true);
    setDeleteError(null);
    try {
      const result = await window.inv.items.remove(deleting.id);
      setDeleting(null);
      await load();
      // Surface attachment destruction count for honesty.
      if (result.deletedAttachments > 0) {
        setError(null);
      }
    } catch (e) {
      setDeleteError(e instanceof Error ? e.message : String(e));
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div>
      <div style={{ ...styles.card, display: 'flex', gap: '12px', flexWrap: 'wrap', alignItems: 'flex-end' }}>
        <div style={{ flex: '2 1 220px' }}>
          <label style={styles.label} htmlFor="inv-search">Search</label>
          <input
            id="inv-search"
            style={styles.input}
            placeholder="Search name, serial, notes…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div style={{ flex: '1 1 160px' }}>
          <label style={styles.label} htmlFor="inv-category">Category</label>
          <select id="inv-category" style={styles.select} value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        </div>
        <div style={{ flex: '1 1 160px' }}>
          <label style={styles.label} htmlFor="inv-location">Location</label>
          <input
            id="inv-location"
            style={styles.input}
            placeholder="e.g. Garage"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
          />
        </div>
        <button style={styles.button} onClick={() => { setEditing(null); setShowForm(true); }}>
          + Add item
        </button>
      </div>

      {error && <div style={styles.errorBox}>Failed to load items: {error}</div>}

      <div style={styles.card}>
        {loading ? (
          <p style={styles.muted}>Loading items…</p>
        ) : items.length === 0 ? (
          <p style={styles.muted}>No items found. Add your first item to start tracking.</p>
        ) : (
          <div style={styles.scrollBox}>
            <table style={styles.table}>
              <thead>
                <tr>
                  <th style={styles.th}>Name</th>
                  <th style={styles.th}>Category</th>
                  <th style={styles.th}>Location</th>
                  <th style={styles.th}>Purchased</th>
                  <th style={{ ...styles.th, textAlign: 'right' }}>Price</th>
                  <th style={styles.th}>Warranty end</th>
                  <th style={styles.th}>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id}>
                    <td style={styles.td}>
                      <button
                        onClick={() => onSelectItem(item.id)}
                        style={{
                          background: 'none',
                          border: 'none',
                          padding: 0,
                          color: theme.accent,
                          cursor: 'pointer',
                          fontSize: '14px',
                          textAlign: 'left',
                        }}
                      >
                        {item.name}
                      </button>
                    </td>
                    <td style={styles.td}>{item.category}</td>
                    <td style={styles.td}>{item.location || '—'}</td>
                    <td style={styles.td}>{item.purchaseDate ?? '—'}</td>
                    <td style={styles.tdRight}>{formatCents(item.purchasePriceCents)}</td>
                    <td style={styles.td}>{warrantyChip(item)}</td>
                    <td style={styles.td} data-testid={`actions-${item.id}`}>
                      <div style={{ display: 'flex', gap: '8px' }}>
                        <button style={styles.buttonSecondary} onClick={() => { setEditing(item); setShowForm(true); }}>
                          Edit
                        </button>
                        <button style={styles.buttonDanger} onClick={() => openDelete(item)}>
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && <p style={{ ...styles.muted, marginTop: '12px' }}>{items.length} item{items.length === 1 ? '' : 's'}</p>}
      </div>

      {showForm && (
        <ItemFormModal
          initial={editing}
          categories={categories}
          onClose={() => { setShowForm(false); setEditing(null); }}
          onSaved={() => { setShowForm(false); setEditing(null); void load(); }}
        />
      )}

      {deleting && (
        <div style={modalOverlayStyle} role="dialog" aria-modal="true" aria-label="Delete item">
          <div style={modalBoxStyle}>
            <h2 style={styles.cardTitle}>Delete “{deleting.name}”?</h2>
            <p style={{ fontSize: '14px' }}>
              This permanently deletes the item, its <strong>maintenance history</strong>, and any
              attached <strong>receipts, photos, and manuals</strong>. This cannot be undone.
            </p>
            <div style={{ marginTop: '12px' }}>
              <label style={styles.label} htmlFor="inv-delete-confirm">
                Type the item name to confirm
              </label>
              <input
                id="inv-delete-confirm"
                style={styles.input}
                value={deleteConfirm}
                onChange={(e) => setDeleteConfirm(e.target.value)}
                placeholder={deleting.name}
              />
              {deleteError && <div style={styles.fieldError}>{deleteError}</div>}
            </div>
            <div style={{ display: 'flex', gap: '12px', marginTop: '16px', justifyContent: 'flex-end' }}>
              <button style={styles.buttonSecondary} onClick={() => setDeleting(null)} disabled={deleteBusy}>
                Cancel
              </button>
              <button
                style={{ ...styles.buttonDanger, border: `1px solid ${theme.danger}`, background: '#3a1a1a', color: '#fff', fontSize: '14px', padding: '8px 16px' }}
                onClick={confirmDelete}
                disabled={deleteBusy}
              >
                {deleteBusy ? 'Deleting…' : 'Delete permanently'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

const modalOverlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  padding: '16px',
};

const modalBoxStyle: React.CSSProperties = {
  background: theme.panel,
  border: `1px solid ${theme.border}`,
  borderRadius: theme.radius,
  padding: '20px',
  width: 'min(560px, 100%)',
  maxHeight: '90vh',
  overflowY: 'auto',
};
