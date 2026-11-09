import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react';

interface FieldProps {
  id: string;
  label: string;
  hint?: string;
  error?: string | null;
}

/** Labeled text input with hint and inline error, wired for accessibility. */
export function TextField({
  id,
  label,
  hint,
  error,
  ...inputProps
}: FieldProps & InputHTMLAttributes<HTMLInputElement>) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return (
    <div className={`field${error ? ' field-invalid' : ''}`}>
      <label htmlFor={id}>{label}</label>
      <input
        id={id}
        aria-describedby={[hintId, errorId].filter(Boolean).join(' ') || undefined}
        aria-invalid={error ? true : undefined}
        {...inputProps}
      />
      {hint && (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

/** Labeled textarea with hint and inline error. */
export function TextAreaField({
  id,
  label,
  hint,
  error,
  ...areaProps
}: FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const hintId = hint ? `${id}-hint` : undefined;
  const errorId = error ? `${id}-error` : undefined;
  return (
    <div className={`field${error ? ' field-invalid' : ''}`}>
      <label htmlFor={id}>{label}</label>
      <textarea
        id={id}
        rows={3}
        aria-describedby={[hintId, errorId].filter(Boolean).join(' ') || undefined}
        aria-invalid={error ? true : undefined}
        {...areaProps}
      />
      {hint && (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      )}
      {error && (
        <p id={errorId} className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
