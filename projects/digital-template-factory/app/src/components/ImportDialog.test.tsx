import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ImportDialog } from './ImportDialog';
import { mockDtf, unmockDtf } from '../test-utils';

afterEach(() => {
  unmockDtf();
  vi.restoreAllMocks();
});

describe('ImportDialog', () => {
  it('shows the backend error verbatim when import fails', async () => {
    const dtf = mockDtf();
    dtf.templates.import.mockRejectedValue(
      new Error('TEMPLATE_INVALID: manifestVersion is required'),
    );
    const user = userEvent.setup();
    render(<ImportDialog onClose={() => {}} onImported={() => {}} />);

    // fireEvent avoids user-event's `{` key-descriptor parsing for JSON.
    fireEvent.change(screen.getByLabelText('Bundle JSON'), {
      target: { value: '{"templateId": "bogus"}' },
    });
    await user.click(screen.getByRole('button', { name: 'Import' }));

    const alert = await screen.findByRole('alert');
    // Verbatim: the backend error code must appear exactly as returned.
    expect(alert.textContent).toContain(
      'TEMPLATE_INVALID: manifestVersion is required',
    );
    expect(dtf.templates.import).toHaveBeenCalledWith({
      bundleJson: '{"templateId": "bogus"}',
    });
  });

  it('reports success and notifies the parent when import succeeds', async () => {
    const dtf = mockDtf();
    dtf.templates.import.mockResolvedValue({
      templateId: 'custom-1',
      name: 'Custom Sheet',
      description: 'Imported.',
      version: '1.0.0',
      fieldCount: 2,
      source: 'imported',
    });
    const onImported = vi.fn();
    const user = userEvent.setup();
    render(<ImportDialog onClose={() => {}} onImported={onImported} />);

    fireEvent.change(screen.getByLabelText('Bundle JSON'), {
      target: { value: '{"manifestVersion":"1.0.0"}' },
    });
    await user.click(screen.getByRole('button', { name: 'Import' }));

    await waitFor(() => {
      expect(screen.getByRole('status')).toHaveTextContent('Custom Sheet');
    });
    expect(onImported).toHaveBeenCalledTimes(1);
  });

  it('keeps the Import button disabled for empty input', async () => {
    mockDtf();
    render(<ImportDialog onClose={() => {}} onImported={() => {}} />);
    expect(screen.getByRole('button', { name: 'Import' })).toBeDisabled();
  });
});
