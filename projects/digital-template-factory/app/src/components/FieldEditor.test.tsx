import { describe, expect, it, vi } from 'vitest';
import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FieldEditor } from './FieldEditor';
import { invoiceManifest, makeDoc } from '../test-utils';

/**
 * Stateful harness: mirrors how Editor owns the data, so typing into a
 * controlled input accumulates the way a real user experiences it.
 */
function StatefulFieldEditor({
  onFieldChange,
}: {
  onFieldChange: (key: string, value: unknown) => void;
}) {
  const [data, setData] = useState<Record<string, unknown>>(makeDoc().data);
  return (
    <FieldEditor
      fields={invoiceManifest.fields}
      data={data}
      onFieldChange={(k, v) => {
        setData((d) => ({ ...d, [k]: v }));
        onFieldChange(k, v);
      }}
    />
  );
}

describe('FieldEditor', () => {
  it('generates the correct input type for each schema field', () => {
    const onFieldChange = vi.fn();
    render(
      <FieldEditor
        fields={invoiceManifest.fields}
        data={makeDoc().data}
        onFieldChange={onFieldChange}
      />,
    );

    // text field
    const clientName = screen.getByLabelText(/Client name/);
    expect(clientName).toHaveAttribute('type', 'text');
    expect(clientName).toHaveValue('Acme Corp');

    // number field with min/max from the manifest
    const amount = screen.getByLabelText(/Amount/);
    expect(amount).toHaveAttribute('type', 'number');
    expect(amount).toHaveAttribute('min', '0');
    expect(amount).toHaveAttribute('max', '1000000');
    expect(amount).toHaveValue(250);

    // date field
    const dueDate = screen.getByLabelText(/Due date/);
    expect(dueDate).toHaveAttribute('type', 'date');
    expect(dueDate).toHaveValue('2026-11-01');

    // list field renders the row editor
    expect(screen.getByRole('button', { name: 'Add row' })).toBeInTheDocument();
  });

  it('marks required fields', () => {
    render(
      <FieldEditor
        fields={invoiceManifest.fields}
        data={{}}
        onFieldChange={() => {}}
      />,
    );
    // Required marker is announced via aria-label on the asterisk span.
    expect(screen.getAllByLabelText('required').length).toBeGreaterThan(0);
  });

  it('forwards text changes with the field key', async () => {
    const onFieldChange = vi.fn();
    const user = userEvent.setup();
    render(<StatefulFieldEditor onFieldChange={onFieldChange} />);

    const clientName = screen.getByLabelText(/Client name/);
    await user.clear(clientName);
    await user.type(clientName, 'Globex');

    expect(clientName).toHaveValue('Globex');
    expect(onFieldChange).toHaveBeenLastCalledWith('clientName', 'Globex');
  });

  it('forwards number changes as numbers', async () => {
    const onFieldChange = vi.fn();
    const user = userEvent.setup();
    render(<StatefulFieldEditor onFieldChange={onFieldChange} />);

    const amount = screen.getByLabelText(/Amount/);
    await user.clear(amount);
    await user.type(amount, '99');

    expect(amount).toHaveValue(99);
    expect(onFieldChange).toHaveBeenLastCalledWith('amount', 99);
  });
});
