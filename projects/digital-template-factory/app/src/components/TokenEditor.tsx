import { useState } from 'react';
import type { ThemeTokens, TokenUpdate } from '../../shared/types';
import { FONT_STACKS, isKnownFontStack } from '../fonts';

interface TokenEditorProps {
  tokens: ThemeTokens;
  onApply: (partial: TokenUpdate) => void;
  disabled?: boolean;
}

const HEX_RE = /^#[0-9a-fA-F]{6}$/;
const MAX_SPACING = 64;

type TokenKey = 'bg' | 'text' | 'accent' | 'headingFont' | 'bodyFont' | 'spacing';

const COLOR_TOKENS: Array<{ key: 'bg' | 'text' | 'accent'; label: string }> = [
  { key: 'bg', label: 'Background' },
  { key: 'text', label: 'Text' },
  { key: 'accent', label: 'Accent' },
];

/**
 * Design-token editor. Colour tokens get a native colour picker plus a hex
 * text field; fonts are selects over system stacks only; spacing is a
 * number. Invalid values show inline errors and are NEVER forwarded to the
 * backend — `onApply` fires only for valid values.
 */
export function TokenEditor({ tokens, onApply, disabled = false }: TokenEditorProps) {
  const [hexDrafts, setHexDrafts] = useState<Record<string, string>>({});
  const [spacingDraft, setSpacingDraft] = useState<string | null>(null);
  const [errors, setErrors] = useState<Partial<Record<TokenKey, string>>>({});

  function setError(key: TokenKey, message: string | null) {
    setErrors((prev) => {
      if (message === null) {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      }
      if (prev[key] === message) return prev;
      return { ...prev, [key]: message };
    });
  }

  function hexValue(key: 'bg' | 'text' | 'accent'): string {
    return hexDrafts[key] ?? tokens[key];
  }

  function handleHexChange(key: 'bg' | 'text' | 'accent', raw: string) {
    setHexDrafts((prev) => ({ ...prev, [key]: raw }));
    if (!HEX_RE.test(raw)) {
      setError(key, 'Enter a 6-digit hex colour, e.g. #1a2b3c.');
      return; // invalid: do not send to backend
    }
    setError(key, null);
    onApply({ [key]: raw } as TokenUpdate);
  }

  function handlePickerChange(key: 'bg' | 'text' | 'accent', raw: string) {
    // Native colour pickers always produce valid #rrggbb values.
    setHexDrafts((prev) => ({ ...prev, [key]: raw }));
    setError(key, null);
    onApply({ [key]: raw } as TokenUpdate);
  }

  function handleFontChange(key: 'headingFont' | 'bodyFont', raw: string) {
    if (!isKnownFontStack(raw)) {
      setError(key, 'Choose one of the provided system font stacks.');
      return;
    }
    setError(key, null);
    onApply({ [key]: raw } as TokenUpdate);
  }

  function handleSpacingChange(raw: string) {
    setSpacingDraft(raw);
    const n = Number(raw);
    if (raw.trim() === '' || !Number.isFinite(n) || n < 0 || n > MAX_SPACING) {
      setError('spacing', `Enter a number between 0 and ${MAX_SPACING}.`);
      return; // invalid: do not send to backend
    }
    setError('spacing', null);
    onApply({ spacing: n });
  }

  return (
    <fieldset className="tokens" disabled={disabled}>
      <legend>Design tokens</legend>
      {COLOR_TOKENS.map(({ key, label }) => (
        <div key={key} className="token-row" data-token-key={key}>
          <label htmlFor={`token-${key}`} className="field-label">
            {label}
          </label>
          <div className="token-color-inputs">
            <input
              id={`token-${key}-picker`}
              type="color"
              className="color-picker"
              value={HEX_RE.test(tokens[key]) ? tokens[key] : '#000000'}
              disabled={disabled}
              onChange={(e) => handlePickerChange(key, e.target.value)}
              aria-label={`${label} colour picker`}
            />
            <input
              id={`token-${key}`}
              type="text"
              className={`input input-hex${errors[key] ? ' input-invalid' : ''}`}
              value={hexValue(key)}
              disabled={disabled}
              onChange={(e) => handleHexChange(key, e.target.value)}
              aria-describedby={errors[key] ? `token-${key}-error` : undefined}
              aria-invalid={!!errors[key]}
              spellCheck={false}
              maxLength={7}
            />
          </div>
          {errors[key] && (
            <p id={`token-${key}-error`} role="alert" className="inline-error">
              {errors[key]}
            </p>
          )}
        </div>
      ))}

      {(
        [
          { key: 'headingFont', label: 'Heading font' },
          { key: 'bodyFont', label: 'Body font' },
        ] as const
      ).map(({ key, label }) => (
        <div key={key} className="token-row" data-token-key={key}>
          <label htmlFor={`token-${key}`} className="field-label">
            {label}
          </label>
          <select
            id={`token-${key}`}
            className="input"
            value={tokens[key]}
            disabled={disabled}
            onChange={(e) => handleFontChange(key, e.target.value)}
            aria-describedby={errors[key] ? `token-${key}-error` : undefined}
            aria-invalid={!!errors[key]}
          >
            {FONT_STACKS.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
          {errors[key] && (
            <p id={`token-${key}-error`} role="alert" className="inline-error">
              {errors[key]}
            </p>
          )}
        </div>
      ))}

      <div className="token-row" data-token-key="spacing">
        <label htmlFor="token-spacing" className="field-label">
          Spacing (px)
        </label>
        <input
          id="token-spacing"
          type="number"
          className={`input input-number${errors.spacing ? ' input-invalid' : ''}`}
          value={spacingDraft ?? String(tokens.spacing)}
          min={0}
          max={MAX_SPACING}
          step={1}
          disabled={disabled}
          onChange={(e) => handleSpacingChange(e.target.value)}
          aria-describedby={errors.spacing ? 'token-spacing-error' : undefined}
          aria-invalid={!!errors.spacing}
        />
        {errors.spacing && (
          <p id="token-spacing-error" role="alert" className="inline-error">
            {errors.spacing}
          </p>
        )}
      </div>
    </fieldset>
  );
}
