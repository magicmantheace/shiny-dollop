// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import WarrantiesView from '../../renderer/src/components/WarrantiesView';
import { installInvMock, itemFixture } from './inv-mock';

afterEach(() => cleanup());

describe('WarrantiesView', () => {
  it('renders separate expired and expiring sections', async () => {
    const mock = installInvMock();
    mock.warranties.expiring.mockResolvedValue([
      {
        item: itemFixture({ id: 'e1', name: 'Old Toaster', warrantyEnd: '2020-01-01' }),
        daysLeft: -100,
        status: 'expired',
      },
      {
        item: itemFixture({ id: 'x1', name: 'New Dryer', warrantyEnd: '2030-12-31' }),
        daysLeft: 20,
        status: 'expiring',
      },
    ]);

    render(<WarrantiesView onSelectItem={() => undefined} />);

    await waitFor(() => expect(screen.getByRole('heading', { name: /expired \(1\)/i })).toBeInTheDocument());
    expect(screen.getByRole('heading', { name: /expiring within 90 days \(1\)/i })).toBeInTheDocument();
    expect(screen.getByText('Old Toaster')).toBeInTheDocument();
    expect(screen.getByText('New Dryer')).toBeInTheDocument();
    expect(screen.getByText('expired 100 days ago')).toBeInTheDocument();
    expect(screen.getByText('expires in 20 days')).toBeInTheDocument();
  });

  it('shows the empty state when no warranties are tracked', async () => {
    const mock = installInvMock();
    mock.warranties.expiring.mockResolvedValue([]);

    render(<WarrantiesView onSelectItem={() => undefined} />);

    await waitFor(() =>
      expect(screen.getByText(/no warranties are being tracked/i)).toBeInTheDocument(),
    );
    // Default window is 90 days.
    expect(mock.warranties.expiring).toHaveBeenCalledWith(90);
  });

  it('passes the selected window to the backend', async () => {
    const mock = installInvMock();
    mock.warranties.expiring.mockResolvedValue([]);

    render(<WarrantiesView onSelectItem={() => undefined} />);
    await waitFor(() => expect(screen.getByText(/no warranties are being tracked/i)).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText(/show warranties expiring within/i), {
      target: { value: '30' },
    });

    await waitFor(() => expect(mock.warranties.expiring).toHaveBeenCalledWith(30));
  });
});
