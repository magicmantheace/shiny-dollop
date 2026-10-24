import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { BusinessProfile, Site } from '../../shared/types';
import { getApi } from '../api';
import {
  SEO_DESCRIPTION_LIMIT,
  SEO_TITLE_LIMIT,
  validateOptionalEmail,
  validateOptionalPhone,
  validateOptionalUrl,
  validateRequiredName,
} from '../validation';
import { TextAreaField, TextField } from './fields';

const AUTOSAVE_DELAY_MS = 800;

interface ProfileEditorProps {
  site: Site;
  onSaved: (site: Site) => void;
  /** Section anchor id to scroll to + focus (used by export-issue links). */
  focusSectionId: string | null;
  onFocusSectionDone: () => void;
}

function cloneProfile(p: BusinessProfile): BusinessProfile {
  return structuredClone(p);
}

type Errors = Record<string, string>;

function collectErrors(draft: BusinessProfile, isRestaurant: boolean): Errors {
  const errors: Errors = {};
  const nameErr = validateRequiredName(draft.name);
  if (nameErr) errors['name'] = nameErr;

  const emailErr = validateOptionalEmail(draft.contact.email);
  if (emailErr) errors['contact.email'] = emailErr;
  const urlErr = validateOptionalUrl(draft.contact.website);
  if (urlErr) errors['contact.website'] = urlErr;
  const phoneErr = validateOptionalPhone(draft.contact.phone);
  if (phoneErr) errors['contact.phone'] = phoneErr;

  draft.services.forEach((s, i) => {
    if (s.title.trim() === '') errors[`services.${i}.title`] = 'Service title is required.';
  });
  draft.social.forEach((s, i) => {
    const e = validateOptionalUrl(s.url);
    if (e) errors[`social.${i}.url`] = e;
  });
  if (isRestaurant) {
    draft.menuSections.forEach((ms, i) => {
      if (ms.name.trim() === '') errors[`menuSections.${i}.name`] = 'Section name is required.';
      ms.items.forEach((item, j) => {
        if (item.name.trim() === '')
          errors[`menuSections.${i}.items.${j}.name`] = 'Item name is required.';
      });
    });
  }
  return errors;
}

export function ProfileEditor({ site, onSaved, focusSectionId, onFocusSectionDone }: ProfileEditorProps) {
  const [draft, setDraft] = useState<BusinessProfile>(() => cloneProfile(site.profile));
  const [touched, setTouched] = useState<Set<string>>(new Set());
  const [saveState, setSaveState] = useState<'saved' | 'dirty' | 'saving'>('saved');
  const [saveError, setSaveError] = useState<string | null>(null);
  const savedJsonRef = useRef<string>(JSON.stringify(site.profile));
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const sectionRefs = useRef<Record<string, HTMLElement | null>>({});

  const isRestaurant = site.businessType === 'restaurant';
  const errors = useMemo(() => collectErrors(draft, isRestaurant), [draft, isRestaurant]);
  const hasErrors = Object.keys(errors).length > 0;
  const draftJson = JSON.stringify(draft);
  const isDirty = draftJson !== savedJsonRef.current;

  // Adopt externally-updated profiles (e.g. after a save round-trip) when
  // the user has no unsaved edits of their own.
  useEffect(() => {
    const incoming = JSON.stringify(site.profile);
    if (incoming !== savedJsonRef.current && !isDirty) {
      savedJsonRef.current = incoming;
      setDraft(cloneProfile(site.profile));
      setTouched(new Set());
    }
  }, [site.profile, isDirty]);

  const touch = useCallback((key: string) => {
    setTouched((prev) => {
      if (prev.has(key)) return prev;
      const next = new Set(prev);
      next.add(key);
      return next;
    });
  }, []);

  const doSave = useCallback(async () => {
    const errs = collectErrors(draft, isRestaurant);
    if (Object.keys(errs).length > 0) {
      // Invalid values stay local: mark everything touched so the inline
      // messages appear, and keep the dirty indicator.
      setTouched(new Set(Object.keys(errs)));
      setSaveState('dirty');
      return;
    }
    setSaveState('saving');
    setSaveError(null);
    try {
      const updated = await getApi().sites.updateProfile(site.id, draft);
      savedJsonRef.current = JSON.stringify(updated.profile);
      setDraft(cloneProfile(updated.profile));
      setTouched(new Set());
      setSaveState('saved');
      onSaved(updated);
    } catch (e) {
      setSaveState('dirty');
      setSaveError(e instanceof Error ? e.message : 'Save failed.');
    }
    // deps intentionally limited: save uses the latest draft snapshot
  }, [draft, isRestaurant, site.id]);

  // Debounced autosave.
  useEffect(() => {
    if (!isDirty) return;
    setSaveState('dirty');
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      void doSave();
    }, AUTOSAVE_DELAY_MS);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [draftJson, isDirty, doSave]);

  // Focus a section when an export issue links to it.
  useEffect(() => {
    if (!focusSectionId) return;
    const el = sectionRefs.current[focusSectionId];
    if (el) {
      el.scrollIntoView({ block: 'start' });
      const heading = el.querySelector<HTMLElement>('h3');
      heading?.focus();
    }
    onFocusSectionDone();
  }, [focusSectionId, onFocusSectionDone]);

  const setSectionRef = (id: string) => (el: HTMLElement | null) => {
    sectionRefs.current[id] = el;
  };

  const err = (key: string): string | null => (touched.has(key) ? (errors[key] ?? null) : null);

  const saveStatusText =
    saveState === 'saving'
      ? 'Saving…'
      : isDirty
        ? hasErrors
          ? 'Unsaved changes — fix the highlighted fields'
          : 'Unsaved changes…'
        : 'All changes saved';

  return (
    <div className="profile-editor">
      <div className="editor-statusbar" role="status" aria-live="polite">
        <span className={`save-indicator save-${saveState}${isDirty && hasErrors ? ' save-blocked' : ''}`}>
          {saveStatusText}
        </span>
        {saveError && <span className="field-error">{saveError}</span>}
      </div>

      {/* Identity */}
      <section id="section-identity" ref={setSectionRef('section-identity')} aria-labelledby="h-identity" className="editor-section">
        <h3 id="h-identity" tabIndex={-1}>Identity</h3>
        <TextField
          id="profile-name"
          label="Business name"
          value={draft.name}
          error={err('name')}
          onChange={(e) => setDraft({ ...draft, name: e.target.value })}
          onBlur={() => touch('name')}
          required
        />
        <TextField
          id="profile-tagline"
          label="Tagline"
          value={draft.tagline}
          onChange={(e) => setDraft({ ...draft, tagline: e.target.value })}
        />
        <TextAreaField
          id="profile-about"
          label="About"
          value={draft.about}
          onChange={(e) => setDraft({ ...draft, about: e.target.value })}
        />
      </section>

      {/* Contact */}
      <section id="section-contact" ref={setSectionRef('section-contact')} aria-labelledby="h-contact" className="editor-section">
        <h3 id="h-contact" tabIndex={-1}>Contact</h3>
        <TextField
          id="profile-phone"
          label="Phone"
          hint="Digits, spaces and + - ( ) . — e.g. +1 403-555-0123"
          value={draft.contact.phone}
          error={err('contact.phone')}
          onChange={(e) => setDraft({ ...draft, contact: { ...draft.contact, phone: e.target.value } })}
          onBlur={() => touch('contact.phone')}
          inputMode="tel"
        />
        <TextField
          id="profile-email"
          label="Email"
          hint="e.g. hello@example.com"
          value={draft.contact.email}
          error={err('contact.email')}
          onChange={(e) => setDraft({ ...draft, contact: { ...draft.contact, email: e.target.value } })}
          onBlur={() => touch('contact.email')}
          inputMode="email"
        />
        <TextField
          id="profile-address"
          label="Address"
          value={draft.contact.address}
          onChange={(e) => setDraft({ ...draft, contact: { ...draft.contact, address: e.target.value } })}
        />
        <TextField
          id="profile-website"
          label="Website"
          hint="Must start with http:// or https://"
          value={draft.contact.website}
          error={err('contact.website')}
          onChange={(e) => setDraft({ ...draft, contact: { ...draft.contact, website: e.target.value } })}
          onBlur={() => touch('contact.website')}
          inputMode="url"
        />
      </section>

      {/* Hours */}
      <section id="section-hours" ref={setSectionRef('section-hours')} aria-labelledby="h-hours" className="editor-section">
        <h3 id="h-hours" tabIndex={-1}>Hours</h3>
        <TextField
          id="profile-hours-label"
          label="Hours label"
          value={draft.hours.label}
          onChange={(e) => setDraft({ ...draft, hours: { ...draft.hours, label: e.target.value } })}
        />
        <fieldset className="dynamic-list">
          <legend>Hours lines</legend>
          {draft.hours.lines.map((line, i) => (
            <div key={i} className="dynamic-row">
              <TextField
                id={`profile-hours-line-${i}`}
                label={`Hours line ${i + 1}`}
                value={line}
                onChange={(e) => {
                  const lines = [...draft.hours.lines];
                  lines[i] = e.target.value;
                  setDraft({ ...draft, hours: { ...draft.hours, lines } });
                }}
              />
              <button
                type="button"
                className="button button-danger-ghost"
                aria-label={`Remove hours line ${i + 1}`}
                onClick={() => {
                  const lines = draft.hours.lines.filter((_, j) => j !== i);
                  setDraft({ ...draft, hours: { ...draft.hours, lines } });
                }}
              >
                Remove
              </button>
            </div>
          ))}
          <button
            type="button"
            className="button"
            onClick={() =>
              setDraft({ ...draft, hours: { ...draft.hours, lines: [...draft.hours.lines, ''] } })
            }
          >
            Add hours line
          </button>
        </fieldset>
      </section>

      {/* Services */}
      <section id="section-services" ref={setSectionRef('section-services')} aria-labelledby="h-services" className="editor-section">
        <h3 id="h-services" tabIndex={-1}>Services</h3>
        <div className="dynamic-list">
          {draft.services.map((s, i) => (
            <div key={i} className="card-row">
              <TextField
                id={`profile-service-${i}-title`}
                label={`Service ${i + 1} title`}
                value={s.title}
                error={err(`services.${i}.title`)}
                onChange={(e) => {
                  const services = [...draft.services];
                  services[i] = { ...services[i]!, title: e.target.value };
                  setDraft({ ...draft, services });
                }}
                onBlur={() => touch(`services.${i}.title`)}
              />
              <TextAreaField
                id={`profile-service-${i}-desc`}
                label={`Service ${i + 1} description`}
                value={s.description}
                onChange={(e) => {
                  const services = [...draft.services];
                  services[i] = { ...services[i]!, description: e.target.value };
                  setDraft({ ...draft, services });
                }}
              />
              <button
                type="button"
                className="button button-danger-ghost"
                aria-label={`Remove service ${i + 1}`}
                onClick={() => setDraft({ ...draft, services: draft.services.filter((_, j) => j !== i) })}
              >
                Remove service
              </button>
            </div>
          ))}
          <button
            type="button"
            className="button"
            onClick={() => setDraft({ ...draft, services: [...draft.services, { title: '', description: '' }] })}
          >
            Add service
          </button>
        </div>
      </section>

      {/* Menu sections — restaurants only */}
      {isRestaurant && (
        <section id="section-menu" ref={setSectionRef('section-menu')} aria-labelledby="h-menu" className="editor-section">
          <h3 id="h-menu" tabIndex={-1}>Menu sections</h3>
          <div className="dynamic-list">
            {draft.menuSections.map((ms, i) => (
              <div key={i} className="card-row">
                <TextField
                  id={`profile-menu-${i}-name`}
                  label={`Menu section ${i + 1} name`}
                  value={ms.name}
                  error={err(`menuSections.${i}.name`)}
                  onChange={(e) => {
                    const menuSections = [...draft.menuSections];
                    menuSections[i] = { ...menuSections[i]!, name: e.target.value };
                    setDraft({ ...draft, menuSections });
                  }}
                  onBlur={() => touch(`menuSections.${i}.name`)}
                />
                {ms.items.map((item, j) => (
                  <div key={j} className="menu-item-row">
                    <TextField
                      id={`profile-menu-${i}-item-${j}-name`}
                      label={`Item ${j + 1} name`}
                      value={item.name}
                      error={err(`menuSections.${i}.items.${j}.name`)}
                      onChange={(e) => {
                        const menuSections = [...draft.menuSections];
                        const items = [...menuSections[i]!.items];
                        items[j] = { ...items[j]!, name: e.target.value };
                        menuSections[i] = { ...menuSections[i]!, items };
                        setDraft({ ...draft, menuSections });
                      }}
                      onBlur={() => touch(`menuSections.${i}.items.${j}.name`)}
                    />
                    <TextField
                      id={`profile-menu-${i}-item-${j}-desc`}
                      label={`Item ${j + 1} description`}
                      value={item.description}
                      onChange={(e) => {
                        const menuSections = [...draft.menuSections];
                        const items = [...menuSections[i]!.items];
                        items[j] = { ...items[j]!, description: e.target.value };
                        menuSections[i] = { ...menuSections[i]!, items };
                        setDraft({ ...draft, menuSections });
                      }}
                    />
                    <TextField
                      id={`profile-menu-${i}-item-${j}-price`}
                      label={`Item ${j + 1} price`}
                      value={item.price}
                      onChange={(e) => {
                        const menuSections = [...draft.menuSections];
                        const items = [...menuSections[i]!.items];
                        items[j] = { ...items[j]!, price: e.target.value };
                        menuSections[i] = { ...menuSections[i]!, items };
                        setDraft({ ...draft, menuSections });
                      }}
                    />
                    <button
                      type="button"
                      className="button button-danger-ghost"
                      aria-label={`Remove item ${j + 1} from menu section ${i + 1}`}
                      onClick={() => {
                        const menuSections = [...draft.menuSections];
                        menuSections[i] = {
                          ...menuSections[i]!,
                          items: menuSections[i]!.items.filter((_, k) => k !== j),
                        };
                        setDraft({ ...draft, menuSections });
                      }}
                    >
                      Remove item
                    </button>
                  </div>
                ))}
                <div className="row-actions">
                  <button
                    type="button"
                    className="button"
                    onClick={() => {
                      const menuSections = [...draft.menuSections];
                      menuSections[i] = {
                        ...menuSections[i]!,
                        items: [...menuSections[i]!.items, { name: '', description: '', price: '' }],
                      };
                      setDraft({ ...draft, menuSections });
                    }}
                  >
                    Add menu item
                  </button>
                  <button
                    type="button"
                    className="button button-danger-ghost"
                    aria-label={`Remove menu section ${i + 1}`}
                    onClick={() =>
                      setDraft({ ...draft, menuSections: draft.menuSections.filter((_, k) => k !== i) })
                    }
                  >
                    Remove section
                  </button>
                </div>
              </div>
            ))}
            <button
              type="button"
              className="button"
              onClick={() =>
                setDraft({ ...draft, menuSections: [...draft.menuSections, { name: '', items: [] }] })
              }
            >
              Add menu section
            </button>
          </div>
        </section>
      )}

      {/* Social links */}
      <section id="section-social" ref={setSectionRef('section-social')} aria-labelledby="h-social" className="editor-section">
        <h3 id="h-social" tabIndex={-1}>Social links</h3>
        <div className="dynamic-list">
          {draft.social.map((s, i) => (
            <div key={i} className="card-row">
              <TextField
                id={`profile-social-${i}-label`}
                label={`Link ${i + 1} label`}
                value={s.label}
                onChange={(e) => {
                  const social = [...draft.social];
                  social[i] = { ...social[i]!, label: e.target.value };
                  setDraft({ ...draft, social });
                }}
              />
              <TextField
                id={`profile-social-${i}-url`}
                label={`Link ${i + 1} URL`}
                hint="Must start with http:// or https://"
                value={s.url}
                error={err(`social.${i}.url`)}
                onChange={(e) => {
                  const social = [...draft.social];
                  social[i] = { ...social[i]!, url: e.target.value };
                  setDraft({ ...draft, social });
                }}
                onBlur={() => touch(`social.${i}.url`)}
                inputMode="url"
              />
              <button
                type="button"
                className="button button-danger-ghost"
                aria-label={`Remove social link ${i + 1}`}
                onClick={() => setDraft({ ...draft, social: draft.social.filter((_, j) => j !== i) })}
              >
                Remove link
              </button>
            </div>
          ))}
          <button
            type="button"
            className="button"
            onClick={() => setDraft({ ...draft, social: [...draft.social, { label: '', url: '' }] })}
          >
            Add social link
          </button>
        </div>
      </section>

      {/* SEO */}
      <section id="section-seo" ref={setSectionRef('section-seo')} aria-labelledby="h-seo" className="editor-section">
        <h3 id="h-seo" tabIndex={-1}>SEO</h3>
        <TextField
          id="profile-seo-title"
          label="Page title"
          value={draft.seo.title}
          onChange={(e) => setDraft({ ...draft, seo: { ...draft.seo, title: e.target.value } })}
        />
        <p className="char-counter" aria-live="polite">
          {draft.seo.title.length} / {SEO_TITLE_LIMIT} characters
          {draft.seo.title.length > SEO_TITLE_LIMIT && ' — over the recommended length'}
        </p>
        <TextAreaField
          id="profile-seo-description"
          label="Meta description"
          value={draft.seo.description}
          onChange={(e) => setDraft({ ...draft, seo: { ...draft.seo, description: e.target.value } })}
        />
        <p className="char-counter" aria-live="polite">
          {draft.seo.description.length} / {SEO_DESCRIPTION_LIMIT} characters
          {draft.seo.description.length > SEO_DESCRIPTION_LIMIT && ' — over the recommended length'}
        </p>
      </section>
    </div>
  );
}
