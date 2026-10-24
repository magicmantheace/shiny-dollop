import { describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ListEditor } from './ListEditor';
import { invoiceManifest } from '../test-utils';
import { coerceFieldValue } from '../../electron/main/validation';
import type { ListItemFieldDef } from '../../shared/types';

const lineItemsField = invoiceManifest.fields.find((f) => f.key === 'lineItems')!;

/** Stateful harness so row edits accumulate like they do inside Editor. */
function StatefulListEditor({
  initial,
  useSchema = true,
  onChange,
}: {
  initial: unknown[];
  useSchema?: boolean;
  onChange: (value: unknown[]) => void;
}) {
  const [value, setValue] = useState<unknown[]>(initial);
  return (
    <ListEditor
      inputId="field-lineItems"
      itemSchema={useSchema ? lineItemsField.itemSchema : undefined}
      minItems={0}
      value={value}
      disabled={false}
      onChange={(v) => {
        setValue(v);
        onChange(v);
      }}
    />
  );
}

describe('ListEditor', () => {
  it('adds a row with valid bounds-aware defaults for numeric sub-fields', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ListEditor
        inputId="field-lineItems"
        itemSchema={lineItemsField.itemSchema}
        minItems={0}
        value={[]}
        disabled={false}
        onChange={onChange}
      />,
    );

    expect(screen.getByText('No rows yet.')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Add row' }));

    expect(onChange).toHaveBeenCalledTimes(1);
    // Fixture schema: qty has min 1, price has min 0 — numeric cells must
    // start at those bounds, not '' (which coerceFieldValue rejects, so a
    // later successful save silently dropped the optimistic row).
    expect(onChange).toHaveBeenCalledWith([{ desc: '', qty: 1, price: 0 }]);
  });

  it('adds a row that coerceFieldValue accepts without further edits', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <ListEditor
        inputId="field-lineItems"
        itemSchema={lineItemsField.itemSchema}
        minItems={0}
        value={[]}
        disabled={false}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Add row' }));

    const added = onChange.mock.calls[0]![0] as unknown[];
    expect(() =>
      coerceFieldValue(invoiceManifest, 'lineItems', added),
    ).not.toThrow();
  });

  it('clamps numeric defaults into [min, max] and keeps other defaults', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    const schema: ListItemFieldDef[] = [
      { key: 'n', label: 'N', type: 'number', required: true, min: 3, max: 10 },
      { key: 'capped', label: 'Capped', type: 'number', required: false, max: 5 },
      { key: 'flag', label: 'Flag', type: 'boolean', required: false },
      { key: 'tags', label: 'Tags', type: 'string-list', required: false },
      { key: 'when', label: 'When', type: 'date', required: false },
    ];
    render(
      <ListEditor
        inputId="field-custom"
        itemSchema={schema}
        minItems={0}
        value={[]}
        disabled={false}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Add row' }));

    expect(onChange).toHaveBeenCalledWith([
      { n: 3, capped: 0, flag: false, tags: [], when: '' },
    ]);
  });

  it('removes a row by index', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    const rows = [
      { desc: 'Widgets', qty: 2, price: 125 },
      { desc: 'Gadgets', qty: 1, price: 50 },
    ];
    render(
      <ListEditor
        inputId="field-lineItems"
        itemSchema={lineItemsField.itemSchema}
        minItems={0}
        value={rows}
        disabled={false}
        onChange={onChange}
      />,
    );

    await user.click(screen.getByRole('button', { name: 'Remove row 1' }));

    expect(onChange).toHaveBeenCalledWith([{ desc: 'Gadgets', qty: 1, price: 50 }]);
  });

  it('disables removal at minItems', () => {
    const onChange = vi.fn();
    render(
      <ListEditor
        inputId="field-lineItems"
        itemSchema={lineItemsField.itemSchema}
        minItems={1}
        value={[{ desc: 'Widgets', qty: 2, price: 125 }]}
        disabled={false}
        onChange={onChange}
      />,
    );

    expect(screen.getByRole('button', { name: 'Remove row 1' })).toBeDisabled();
    expect(onChange).not.toHaveBeenCalled();
  });

  it('edits sub-fields of a schema row', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <StatefulListEditor
        initial={[{ desc: 'Widgets', qty: 2, price: 125 }]}
        onChange={onChange}
      />,
    );

    const desc = screen.getByLabelText(/Description/);
    await user.clear(desc);
    await user.type(desc, 'Sprockets');

    expect(desc).toHaveValue('Sprockets');
    expect(onChange).toHaveBeenLastCalledWith([
      { desc: 'Sprockets', qty: 2, price: 125 },
    ]);
  });

  it('renders plain text rows when no item schema is declared', async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(
      <StatefulListEditor initial={['alpha']} useSchema={false} onChange={onChange} />,
    );

    const row = screen.getByLabelText('Row 1');
    expect(row).toHaveValue('alpha');
    await user.clear(row);
    await user.type(row, 'beta');
    expect(row).toHaveValue('beta');
    expect(onChange).toHaveBeenLastCalledWith(['beta']);
  });
});
