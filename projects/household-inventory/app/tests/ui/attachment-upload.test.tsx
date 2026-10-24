// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import ItemDetailView from '../../renderer/src/components/ItemDetailView';
import { installInvMock, itemFixture } from './inv-mock';

afterEach(() => cleanup());

describe('ItemDetailView attachments', () => {
  function renderDetail() {
    const mock = installInvMock();
    mock.items.get.mockResolvedValue({
      item: itemFixture(),
      attachments: [],
      maintenance: [],
    });
    render(<ItemDetailView itemId="item-1" onBack={() => undefined} />);
    return mock;
  }

  it('warns when an oversized file is selected and blocks the upload', async () => {
    const mock = renderDetail();
    await waitFor(() => expect(screen.getByText('Washing Machine')).toBeInTheDocument());

    const big = new File([new Uint8Array(21 * 1024 * 1024)], 'huge-receipt.pdf', {
      type: 'application/pdf',
    });
    fireEvent.change(screen.getByLabelText('File'), { target: { files: [big] } });

    expect(screen.getByText(/over the 20 MB limit/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    expect(screen.getByText(/cannot be uploaded/i)).toBeInTheDocument();
    expect(mock.attachments.add).not.toHaveBeenCalled();
  });

  it('uploads a small file without warnings', async () => {
    const mock = renderDetail();
    await waitFor(() => expect(screen.getByText('Washing Machine')).toBeInTheDocument());

    const small = new File([new Uint8Array(1024)], 'receipt.pdf', { type: 'application/pdf' });
    fireEvent.change(screen.getByLabelText('File'), { target: { files: [small] } });

    expect(screen.queryByText(/over the 20 MB limit/i)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Upload' }));
    await waitFor(() => expect(mock.attachments.add).toHaveBeenCalled());
    const [, payload] = mock.attachments.add.mock.calls[0] as [string, { fileName: string; mime: string; dataBase64: string; kind: string }];
    expect(payload.fileName).toBe('receipt.pdf');
    expect(payload.mime).toBe('application/pdf');
    expect(payload.kind).toBe('receipt');
    expect(typeof payload.dataBase64).toBe('string');
  });

  it('shows the sha256 short hash for each attachment', async () => {
    const mock = installInvMock();
    mock.items.get.mockResolvedValue({
      item: itemFixture(),
      attachments: [
        {
          id: 'att-1',
          itemId: 'item-1',
          originalName: 'receipt.pdf',
          storedName: 'uuid.pdf',
          mime: 'application/pdf',
          sizeBytes: 1234,
          sha256: 'abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789',
          kind: 'receipt',
          createdAt: '2024-03-15T00:00:00Z',
        },
      ],
      maintenance: [],
    });
    render(<ItemDetailView itemId="item-1" onBack={() => undefined} />);

    await waitFor(() => expect(screen.getByText('receipt.pdf')).toBeInTheDocument());
    expect(screen.getByText('abcdef0123456789…')).toBeInTheDocument();
  });
});
