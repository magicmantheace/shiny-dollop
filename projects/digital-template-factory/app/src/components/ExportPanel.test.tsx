import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ExportPanel } from './ExportPanel';
import { invoiceManifest, mockDtf, unmockDtf } from '../test-utils';

const licenseRecord = {
  templateId: 'simple-invoice',
  templateVersion: '1.0.0',
  manifestVersion: '1.0.0',
  format: 'html' as const,
  contentHash:
    '9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08',
  exportedAt: '2026-10-23T15:05:00.000Z',
};

afterEach(() => {
  unmockDtf();
  vi.restoreAllMocks();
});

function renderPanel(onSelectErrorField = vi.fn()) {
  return {
    onSelectErrorField,
    ...render(
      <ExportPanel
        docId="doc-1"
        manifest={invoiceManifest}
        onSelectErrorField={onSelectErrorField}
      />,
    ),
  };
}

describe('ExportPanel', () => {
  it('lists named validation errors, each linking to its field', async () => {
    const dtf = mockDtf();
    dtf.export.generate.mockResolvedValue({
      ok: false,
      errors: ['FIELD_REQUIRED:clientName', 'FIELD_INVALID:amount'],
    });
    const onSelectErrorField = vi.fn();
    const user = userEvent.setup();
    renderPanel(onSelectErrorField);

    await user.click(screen.getByRole('button', { name: 'Generate export' }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('FIELD_REQUIRED');
    expect(alert).toHaveTextContent('FIELD_INVALID');
    // Error buttons carry the human field label…
    expect(screen.getByRole('button', { name: /FIELD_REQUIRED.*Client name/ })).toBeInTheDocument();
    // …and jump to the offending field when clicked.
    await user.click(screen.getByRole('button', { name: /FIELD_REQUIRED.*Client name/ }));
    expect(onSelectErrorField).toHaveBeenCalledWith('clientName');
    expect(dtf.export.generate).toHaveBeenCalledWith({
      id: 'doc-1',
      format: 'html',
    });
  });

  it('sends the selected format to the backend', async () => {
    const dtf = mockDtf();
    dtf.export.generate.mockResolvedValue({ ok: false, errors: [] });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByLabelText('Print'));
    await user.click(screen.getByRole('button', { name: 'Generate export' }));

    await waitFor(() => {
      expect(dtf.export.generate).toHaveBeenCalledWith({
        id: 'doc-1',
        format: 'print',
      });
    });
  });

  it('shows the license record and content hash on success, then saves', async () => {
    const dtf = mockDtf();
    const html = '<html><body>invoice</body></html>';
    dtf.export.generate.mockResolvedValue({
      ok: true,
      html,
      errors: [],
      licenseRecord,
    });
    dtf.export.save.mockResolvedValue({
      canceled: false,
      filePath: '/tmp/simple-invoice.html',
    });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Generate export' }));

    // License record + content hash are shown verbatim from the backend.
    expect(await screen.findByText('Export ready')).toBeInTheDocument();
    expect(screen.getByText(licenseRecord.contentHash)).toBeInTheDocument();
    expect(screen.getByText('simple-invoice')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Save file' }));
    await waitFor(() => {
      expect(dtf.export.save).toHaveBeenCalledWith({
        html,
        suggestedName: 'simple-invoice.html',
      });
    });
    expect(await screen.findByRole('status')).toHaveTextContent(
      '/tmp/simple-invoice.html',
    );
  });

  it('reports a cancelled save without treating it as an error', async () => {
    const dtf = mockDtf();
    dtf.export.generate.mockResolvedValue({
      ok: true,
      html: '<html></html>',
      errors: [],
      licenseRecord,
    });
    dtf.export.save.mockResolvedValue({ canceled: true });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Generate export' }));
    await user.click(await screen.findByRole('button', { name: 'Save file' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('cancelled');
  });

  it('shows backend transport failures verbatim', async () => {
    mockDtf({
      export: { generate: vi.fn().mockRejectedValue(new Error('EXPORT_IPC_DOWN')) },
    });
    const user = userEvent.setup();
    renderPanel();

    await user.click(screen.getByRole('button', { name: 'Generate export' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('EXPORT_IPC_DOWN');
  });
});
