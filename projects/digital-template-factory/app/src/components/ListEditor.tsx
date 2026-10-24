import type { ListItemFieldDef } from '../../shared/types';

interface ListEditorProps {
  inputId: string;
  itemSchema?: ListItemFieldDef[] | undefined;
  minItems: number;
  value: unknown[];
  disabled: boolean;
  onChange: (value: unknown[]) => void;
}

function emptyRow(itemSchema?: ListItemFieldDef[]): unknown {
  if (!itemSchema || itemSchema.length === 0) return '';
  const row: Record<string, unknown> = {};
  for (const col of itemSchema) {
    row[col.key] = col.type === 'boolean' ? false : col.type === 'string-list' ? [] : '';
  }
  return row;
}

function rowObject(row: unknown): Record<string, unknown> {
  return row !== null && typeof row === 'object'
    ? (row as Record<string, unknown>)
    : {};
}

/**
 * Editable row list for `list` fields. When the manifest declares an
 * `itemSchema`, each row is an object rendered as a sub-form; otherwise
 * rows are plain text values. Removing below `minItems` is disabled.
 */
export function ListEditor({
  inputId,
  itemSchema,
  minItems,
  value,
  disabled,
  onChange,
}: ListEditorProps) {
  const hasSchema = !!itemSchema && itemSchema.length > 0;

  function updateRow(index: number, next: unknown) {
    onChange(value.map((r, i) => (i === index ? next : r)));
  }

  function addRow() {
    onChange([...value, emptyRow(itemSchema)]);
  }

  function removeRow(index: number) {
    if (value.length <= minItems) return;
    onChange(value.filter((_, i) => i !== index));
  }

  return (
    <div className="list-editor" id={inputId}>
      {value.length === 0 && (
        <p className="muted list-empty">No rows yet.</p>
      )}
      <ul className="list-rows">
        {value.map((row, index) => (
          <li key={index} className="list-row">
            {hasSchema ? (
              <fieldset className="list-row-fields">
                <legend className="visually-hidden">
                  Row {index + 1}
                </legend>
                {itemSchema!.map((col) => (
                  <ListCellInput
                    key={col.key}
                    col={col}
                    inputId={`${inputId}-${index}-${col.key}`}
                    value={rowObject(row)[col.key]}
                    disabled={disabled}
                    onChange={(v) =>
                      updateRow(index, { ...rowObject(row), [col.key]: v })
                    }
                  />
                ))}
              </fieldset>
            ) : (
              <input
                type="text"
                className="input"
                aria-label={`Row ${index + 1}`}
                value={typeof row === 'string' ? row : ''}
                disabled={disabled}
                onChange={(e) => updateRow(index, e.target.value)}
              />
            )}
            <button
              type="button"
              className="btn btn-danger btn-sm"
              disabled={disabled || value.length <= minItems}
              onClick={() => removeRow(index)}
              aria-label={`Remove row ${index + 1}`}
              title={
                value.length <= minItems
                  ? `At least ${minItems} row(s) required`
                  : 'Remove row'
              }
            >
              Remove
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        className="btn btn-secondary btn-sm"
        disabled={disabled}
        onClick={addRow}
      >
        Add row
      </button>
    </div>
  );
}

interface ListCellInputProps {
  col: ListItemFieldDef;
  inputId: string;
  value: unknown;
  disabled: boolean;
  onChange: (value: unknown) => void;
}

function ListCellInput({
  col,
  inputId,
  value,
  disabled,
  onChange,
}: ListCellInputProps) {
  const label = (
    <span className="field-label field-label-inline">
      {col.label}
      {col.required && (
        <span className="required" aria-label="required">
          *
        </span>
      )}
    </span>
  );
  switch (col.type) {
    case 'boolean':
      return (
        <label className="check-label">
          <input
            id={inputId}
            type="checkbox"
            checked={value === true}
            disabled={disabled}
            onChange={(e) => onChange(e.target.checked)}
          />
          {label}
        </label>
      );
    case 'number':
      return (
        <label className="cell-label">
          {label}
          <input
            id={inputId}
            type="number"
            className="input input-number"
            value={typeof value === 'number' ? String(value) : ''}
            min={col.min}
            max={col.max}
            step="any"
            disabled={disabled}
            onChange={(e) =>
              onChange(e.target.value === '' ? '' : Number(e.target.value))
            }
          />
        </label>
      );
    case 'date':
      return (
        <label className="cell-label">
          {label}
          <input
            id={inputId}
            type="date"
            className="input"
            value={typeof value === 'string' ? value : ''}
            disabled={disabled}
            onChange={(e) => onChange(e.target.value)}
          />
        </label>
      );
    case 'string-list':
      return (
        <label className="cell-label">
          {label}
          <textarea
            id={inputId}
            className="textarea"
            rows={2}
            value={Array.isArray(value) ? value.join('\n') : ''}
            disabled={disabled}
            onChange={(e) =>
              onChange(
                e.target.value
                  .split('\n')
                  .map((s) => s.trim())
                  .filter((s) => s.length > 0),
              )
            }
            placeholder="One item per line"
          />
        </label>
      );
    case 'text':
    default:
      return (
        <label className="cell-label">
          {label}
          <input
            id={inputId}
            type="text"
            className="input"
            value={typeof value === 'string' ? value : ''}
            disabled={disabled}
            onChange={(e) => onChange(e.target.value)}
          />
        </label>
      );
  }
}
