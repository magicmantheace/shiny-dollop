import { describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { StoreProvider } from '../../src/store';
import { InvoiceDetail } from '../../src/views/Invoices';
import { installMockConcreteOps, SYNTHETIC_INVOICE } from './mockConcreteOps';

describe('InvoiceDetail', () => {
  it('shows every charge and every tax as its own line', async () => {
    installMockConcreteOps();
    render(
      <StoreProvider>
        <InvoiceDetail invoiceId={SYNTHETIC_INVOICE.id} />
      </StoreProvider>,
    );

    await waitFor(() => expect(screen.getByText('Invoice INV-000001')).toBeInTheDocument());

    // Each charge on its own line…
    expect(screen.getByText(/Concrete — mix C25\/30/)).toBeInTheDocument();
    expect(screen.getByText('Small-load charge')).toBeInTheDocument();
    expect(screen.getByText('Delivery fee (flat)')).toBeInTheDocument();
    // …each tax on its own line…
    expect(screen.getByText(/GST \(5\.00%\)/)).toBeInTheDocument();
    // …and the itemized amounts.
    expect(screen.getByText('$446.40')).toBeInTheDocument();
    expect(screen.getByText('$150.00')).toBeInTheDocument();
    expect(screen.getByText('$75.00')).toBeInTheDocument();
    expect(screen.getByText('$33.57')).toBeInTheDocument();
    expect(screen.getByText('$704.97')).toBeInTheDocument();
  });

  it('labels the invoice immutable and measured-volume based', async () => {
    installMockConcreteOps();
    render(
      <StoreProvider>
        <InvoiceDetail invoiceId={SYNTHETIC_INVOICE.id} />
      </StoreProvider>,
    );
    await waitFor(() => expect(screen.getByText('Invoice INV-000001')).toBeInTheDocument());
    expect(screen.getByText(/measured.*volumes/i)).toBeInTheDocument();
    expect(screen.getByText(/immutable/i)).toBeInTheDocument();
  });
});
