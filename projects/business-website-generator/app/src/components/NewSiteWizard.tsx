import { useEffect, useState } from 'react';
import type { BusinessType, Site, ThemeInfo } from '../../shared/types';
import { BUSINESS_TYPE_LABELS } from '../labels';
import { getApi } from '../api';
import { Modal } from './Modal';
import { TextField } from './fields';
import { validateRequiredName } from '../validation';

interface NewSiteWizardProps {
  onClose: () => void;
  onCreated: (site: Site) => void;
}

const BUSINESS_TYPES: BusinessType[] = ['trades', 'author', 'restaurant', 'localbiz'];

/**
 * New-site wizard: 1) name → 2) business-type cards → 3) theme picker
 * (filtered to themes supporting the chosen type) → Create.
 */
export function NewSiteWizard({ onClose, onCreated }: NewSiteWizardProps) {
  const [step, setStep] = useState(1);
  const [name, setName] = useState('');
  const [nameTouched, setNameTouched] = useState(false);
  const [businessType, setBusinessType] = useState<BusinessType | null>(null);
  const [themes, setThemes] = useState<ThemeInfo[] | null>(null);
  const [themeId, setThemeId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getApi()
      .themes.list()
      .then((list) => setThemes(list))
      .catch((e) => setError(e instanceof Error ? e.message : 'Could not load themes.'));
  }, []);

  const nameError = nameTouched ? validateRequiredName(name) : null;
  const canNextFromName = validateRequiredName(name) === null;
  const compatibleThemes = (themes ?? []).filter(
    (t) => businessType && t.businessTypes.includes(businessType),
  );

  const create = async () => {
    if (!businessType || !themeId || creating) return;
    setCreating(true);
    setError(null);
    try {
      const created = await getApi().sites.create({ name: name.trim(), businessType, themeId });
      onCreated(created);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the site.');
      setCreating(false);
    }
  };

  return (
    <Modal title="New site" onClose={onClose}>
      <ol className="wizard-steps" aria-label="Wizard progress">
        <li aria-current={step === 1 ? 'step' : undefined} className={step >= 1 ? 'active' : ''}>
          Name
        </li>
        <li aria-current={step === 2 ? 'step' : undefined} className={step >= 2 ? 'active' : ''}>
          Business type
        </li>
        <li aria-current={step === 3 ? 'step' : undefined} className={step >= 3 ? 'active' : ''}>
          Theme
        </li>
      </ol>

      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}

      {step === 1 && (
        <div>
          <TextField
            id="wizard-name"
            label="Site name"
            value={name}
            error={nameError}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => setNameTouched(true)}
            required
            autoFocus
          />
          <div className="row-actions">
            <button type="button" className="button" onClick={onClose}>
              Cancel
            </button>
            <button
              type="button"
              className="button button-primary"
              disabled={!canNextFromName}
              onClick={() => {
                setNameTouched(true);
                if (canNextFromName) setStep(2);
              }}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {step === 2 && (
        <div>
          <div className="type-cards" role="radiogroup" aria-label="Business type">
            {BUSINESS_TYPES.map((t) => (
              <button
                key={t}
                type="button"
                role="radio"
                aria-checked={businessType === t}
                className={`type-card${businessType === t ? ' type-card-selected' : ''}`}
                onClick={() => {
                  setBusinessType(t);
                  setThemeId(null);
                }}
              >
                {BUSINESS_TYPE_LABELS[t]}
              </button>
            ))}
          </div>
          <div className="row-actions">
            <button type="button" className="button" onClick={() => setStep(1)}>
              Back
            </button>
            <button
              type="button"
              className="button button-primary"
              disabled={!businessType}
              onClick={() => setStep(3)}
            >
              Next
            </button>
          </div>
        </div>
      )}

      {step === 3 && (
        <div>
          {!themes && !error && <p className="empty-state">Loading themes…</p>}
          {compatibleThemes.length === 0 && themes && (
            <p className="empty-state">
              No themes support {businessType ? BUSINESS_TYPE_LABELS[businessType] : 'this type'} yet.
            </p>
          )}
          <ul className="theme-grid" aria-label="Themes">
            {compatibleThemes.map((theme) => (
              <li key={theme.id} className={`theme-card${themeId === theme.id ? ' theme-card-selected' : ''}`}>
                <button
                  type="button"
                  className="theme-card-button"
                  aria-pressed={themeId === theme.id}
                  onClick={() => setThemeId(theme.id)}
                >
                  <span className="theme-card-name">{theme.name}</span>
                  <span className="theme-description">{theme.description}</span>
                  <span className="theme-pages">Pages: {theme.pages.join(', ')}</span>
                </button>
              </li>
            ))}
          </ul>
          <div className="row-actions">
            <button type="button" className="button" onClick={() => setStep(2)}>
              Back
            </button>
            <button
              type="button"
              className="button button-primary"
              disabled={!themeId || creating}
              onClick={() => void create()}
            >
              {creating ? 'Creating…' : 'Create site'}
            </button>
          </div>
        </div>
      )}
    </Modal>
  );
}
