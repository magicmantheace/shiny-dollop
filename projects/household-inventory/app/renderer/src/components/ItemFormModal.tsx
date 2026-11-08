import { useState } from 'react';
import { styles, theme } from '../styles';
import { parseDollarsToCents } from '../format';
import type { Item } from '../../../shared/types';
import type { ItemInput } from '../../../shared/schemas';

interface ItemFormModalProps {
  initial: Item | null;
  categories: string[];
  onClose: () => void;
  onSaved: () => void;
}

function centsToInput(cents: number | null): string {
  if (cents === null || cents === undefined) return '';
  return (cents / 100).toFixed(2);
}

export default function ItemFormModal({ initial, categories, onClose, onSaved }: ItemFormModalProps) {
  const [name, setName] = useState(initial?.name ?? '');
  const [category, setCategory] = useState(initial?.category ?? '');
  const [location, setLocation] = useState(initial?.location ?? '');
  const [price, setPrice] = useState(centsToInput(initial?.purchasePriceCents ?? null));
  const [purchaseDate, setPurchaseDate] = useState(initial?.purchaseDate ?? '');
  const [serialNumber, setSerialNumber] = useState(initial?.serialNumber ?? '');
  const [notes, setNotes] = useState(initial?.notes ?? '');
  const [warrantyStart, setWarrantyStart] = useState(initial?.warrantyStart ?? '');
  const [warrantyEnd, setWarrantyEnd] = useState(initial?.warrantyEnd ?? '');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function validate(): ItemInput | null {
    const errs: Record<string, string> = {};
    if (!name.trim()) errs.name = 'name is required';
    if (!category.trim()) errs.category = 'category is required';
    let priceCents: number | null = null;
    try {
      priceCents = parseDollarsToCents(price);
    } catch (e) {
      errs.price = e instanceof Error ? e.message : String(e);
    }
    // Mirror of the server-side cross-field rule in shared/schemas.ts.
    if (warrantyStart && warrantyEnd && warrantyEnd < warrantyStart) {
      errs.warrantyEnd = 'warranty end must be on or after warranty start';
    }
    setErrors(errs);
    if (Object.keys(errs).length > 0) return null;
    return {
      name: name.trim(),
      category: category.trim(),
      location: location.trim(),
      purchasePriceCents: priceCents,
      purchaseDate: purchaseDate || null,
      serialNumber: serialNumber.trim() || null,
      notes,
      warrantyStart: warrantyStart || null,
      warrantyEnd: warrantyEnd || null,
    };
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);
    const input = validate();
    if (!input) return;
    setBusy(true);
    try {
      if (initial) {
        await window.inv.items.update(initial.id, input);
      } else {
        await window.inv.items.create(input);
      }
      onSaved();
    } catch (err) {
      setSubmitError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={overlayStyle} role="dialog" aria-modal="true" aria-label={initial ? 'Edit item' : 'Add item'}>
      <div style={boxStyle}>
        <h2 style={styles.cardTitle}>{initial ? 'Edit item' : 'Add item'}</h2>
        <form onSubmit={handleSubmit} noValidate>
          <div style={styles.formGrid}>
            <div>
              <label style={styles.label} htmlFor="invf-name">Name *</label>
              <input id="invf-name" style={styles.input} value={name} onChange={(e) => setName(e.target.value)} maxLength={200} />
              {errors.name && <div style={styles.fieldError}>{errors.name}</div>}
            </div>
            <div>
              <label style={styles.label} htmlFor="invf-category">Category *</label>
              <input
                id="invf-category"
                style={styles.input}
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                list="invf-category-list"
                maxLength={80}
              />
              <datalist id="invf-category-list">
                {categories.map((c) => (
                  <option key={c} value={c} />
                ))}
              </datalist>
              {errors.category && <div style={styles.fieldError}>{errors.category}</div>}
            </div>
            <div>
              <label style={styles.label} htmlFor="invf-location">Location</label>
              <input id="invf-location" style={styles.input} value={location} onChange={(e) => setLocation(e.target.value)} maxLength={120} />
            </div>
            <div>
              <label style={styles.label} htmlFor="invf-price">Purchase price ($)</label>
              <input
                id="invf-price"
                style={styles.input}
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="0.00"
                inputMode="decimal"
              />
              {errors.price && <div style={styles.fieldError}>{errors.price}</div>}
            </div>
            <div>
              <label style={styles.label} htmlFor="invf-purchased">Purchase date</label>
              <input id="invf-purchased" type="date" style={styles.input} value={purchaseDate} onChange={(e) => setPurchaseDate(e.target.value)} />
            </div>
            <div>
              <label style={styles.label} htmlFor="invf-serial">Serial number</label>
              <input id="invf-serial" style={styles.input} value={serialNumber} onChange={(e) => setSerialNumber(e.target.value)} maxLength={100} />
            </div>
            <div>
              <label style={styles.label} htmlFor="invf-wstart">Warranty start</label>
              <input id="invf-wstart" type="date" style={styles.input} value={warrantyStart} onChange={(e) => setWarrantyStart(e.target.value)} />
            </div>
            <div>
              <label style={styles.label} htmlFor="invf-wend">Warranty end</label>
              <input id="invf-wend" type="date" style={styles.input} value={warrantyEnd} onChange={(e) => setWarrantyEnd(e.target.value)} />
              {errors.warrantyEnd && <div style={styles.fieldError}>{errors.warrantyEnd}</div>}
            </div>
          </div>
          <div style={{ marginTop: '12px' }}>
            <label style={styles.label} htmlFor="invf-notes">Notes</label>
            <textarea
              id="invf-notes"
              style={{ ...styles.input, minHeight: '70px', resize: 'vertical' }}
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={5000}
            />
          </div>
          {submitError && <div style={{ ...styles.errorBox, marginTop: '12px', marginBottom: 0 }}>Save failed: {submitError}</div>}
          <div style={{ display: 'flex', gap: '12px', marginTop: '16px', justifyContent: 'flex-end' }}>
            <button type="button" style={styles.buttonSecondary} onClick={onClose} disabled={busy}>
              Cancel
            </button>
            <button type="submit" style={styles.button} disabled={busy}>
              {busy ? 'Saving…' : initial ? 'Save changes' : 'Add item'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

const overlayStyle: React.CSSProperties = {
  position: 'fixed',
  inset: 0,
  background: 'rgba(0,0,0,0.6)',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  zIndex: 1000,
  padding: '16px',
};

const boxStyle: React.CSSProperties = {
  background: theme.panel,
  border: `1px solid ${theme.border}`,
  borderRadius: theme.radius,
  padding: '20px',
  width: 'min(640px, 100%)',
  maxHeight: '90vh',
  overflowY: 'auto',
};
