import type {
  ListItemFieldDef,
  TemplateFieldDef,
} from '../../shared/types';
import { ListEditor } from './ListEditor';

interface FieldEditorProps {
  fields: TemplateFieldDef[];
  data: Record<string, unknown>;
  onFieldChange: (key: string, value: unknown) => void;
  disabled?: boolean;
}

/**
 * Generates one labelled input per template manifest field:
 * text → text input, number → number input (with min/max when declared),
 * date → date picker, list → row editor with add/remove.
 */
export function FieldEditor({
  fields,
  data,
  onFieldChange,
  disabled = false,
}: FieldEditorProps) {
  return (
    <div className="field-list">
      {fields.map((field) => {
        const inputId = `field-${field.key}`;
        const value = data[field.key];
        return (
          <div
            key={field.key}
            className="field"
            data-field-key={field.key}
          >
            <label htmlFor={inputId} className="field-label">
              {field.label}
              {field.required && (
                <span className="required" aria-label="required">
                  *
                </span>
              )}
            </label>
            <FieldInput
              field={field}
              inputId={inputId}
              value={value}
              disabled={disabled}
              onChange={(v) => onFieldChange(field.key, v)}
            />
          </div>
        );
      })}
    </div>
  );
}

interface FieldInputProps {
  field: TemplateFieldDef;
  inputId: string;
  value: unknown;
  disabled: boolean;
  onChange: (value: unknown) => void;
}

function FieldInput({ field, inputId, value, disabled, onChange }: FieldInputProps) {
  switch (field.type) {
    case 'text':
      return (
        <input
          id={inputId}
          type="text"
          className="input"
          value={typeof value === 'string' ? value : ''}
          required={field.required}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case 'number':
      return (
        <input
          id={inputId}
          type="number"
          className="input input-number"
          value={typeof value === 'number' ? String(value) : ''}
          min={field.min}
          max={field.max}
          step="any"
          required={field.required}
          disabled={disabled}
          onChange={(e) =>
            onChange(e.target.value === '' ? '' : Number(e.target.value))
          }
        />
      );
    case 'date':
      return (
        <input
          id={inputId}
          type="date"
          className="input"
          value={typeof value === 'string' ? value : ''}
          required={field.required}
          disabled={disabled}
          onChange={(e) => onChange(e.target.value)}
        />
      );
    case 'list':
      return (
        <ListEditor
          inputId={inputId}
          itemSchema={field.itemSchema}
          minItems={field.minItems ?? 0}
          value={Array.isArray(value) ? value : []}
          disabled={disabled}
          onChange={onChange}
        />
      );
  }
}

export type { ListItemFieldDef };
