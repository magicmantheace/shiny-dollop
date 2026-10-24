/**
 * Regression test for Codex finding (PR #5): creating an invoice from a job
 * must refresh the SHARED invoice store.
 *
 * Previously JobDetail's run() only called refresh('audit'), so the shared
 * store never learned about the new invoice: InvoiceDetail (which resolves
 * invoices exclusively from the shared store) showed "Invoice not found",
 * and the Invoices page / dashboard stayed stale.
 */
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { StoreProvider, useStore } from '../../src/store';
import { JobDetail } from '../../src/views/JobDetail';
import { installMockConcreteOps, SYNTHETIC_INVOICE } from './mockConcreteOps';
import type { Pour, Quote } from '../../shared/types';

const FINALIZED_POUR: Pour = {
  id: 1,
  jobId: 1,
  mixDesignId: 'C25/30',
  quotedLiters: 2500,
  deliveredLiters: 2480,
  createdAt: '2026-10-23T10:00:00.000Z',
};

const ISSUED_QUOTE: Quote = {
  id: 1,
  jobId: 1,
  version: 1,
  status: 'issued',
  lines: SYNTHETIC_INVOICE.lines,
  subtotalCents: SYNTHETIC_INVOICE.subtotalCents,
  taxLines: SYNTHETIC_INVOICE.taxLines,
  totalCents: SYNTHETIC_INVOICE.totalCents,
  taxExemptApplied: false,
  params: {
    concreteRateCentsPerM3: 18000,
    smallLoadThresholdLiters: 3000,
    smallLoadChargeCents: 15000,
    smallLoadApplied: true,
    deliveryMode: 'flat',
    deliveryFlatCents: 7500,
    deliveryPerKmCents: 0,
    distanceTenthsKm: 185,
    taxes: [{ name: 'GST', rateBps: 500 }],
    taxExempt: false,
    volumes: [{ pourId: 1, mixDesignId: 'C25/30', liters: 2500 }],
    fromDelivered: false,
  },
  notes: null,
  createdAt: '2026-10-23T11:00:00.000Z',
  issuedAt: '2026-10-23T11:30:00.000Z',
};

/** Probe that renders exactly what the shared store holds for invoices. */
function SharedInvoicesProbe() {
  const { invoices } = useStore();
  return (
    <div data-testid="shared-invoices">
      {invoices.length === 0 ? 'none' : invoices.map((i) => i.invoiceNumber).join(',')}
    </div>
  );
}

describe('JobDetail invoice creation', () => {
  it('refreshes the shared invoice store after creating an invoice', async () => {
    let created = false;
    const ok = <T,>(data: T) => ({ ok: true as const, data });
    installMockConcreteOps({
      pours: {
        listByJob: vi.fn().mockResolvedValue(ok([FINALIZED_POUR])),
        add: vi.fn(),
        update: vi.fn(),
        setDelivered: vi.fn(),
        remove: vi.fn().mockResolvedValue(ok({ removed: true })),
      },
      quotes: {
        listByJob: vi.fn().mockResolvedValue(ok([ISSUED_QUOTE])),
        get: vi.fn(),
        create: vi.fn(),
        updateDraft: vi.fn(),
        issue: vi.fn(),
        revise: vi.fn(),
        deleteDraft: vi.fn().mockResolvedValue(ok({ removed: true })),
      },
      invoices: {
        list: vi.fn().mockImplementation(async () => ok(created ? [SYNTHETIC_INVOICE] : [])),
        get: vi.fn().mockResolvedValue(ok(SYNTHETIC_INVOICE)),
        create: vi.fn().mockImplementation(async () => {
          created = true;
          return ok(SYNTHETIC_INVOICE);
        }),
        markPaid: vi.fn(),
        void: vi.fn(),
      },
    });

    render(
      <StoreProvider>
        <JobDetail jobId={1} />
        <SharedInvoicesProbe />
      </StoreProvider>,
    );

    // Shared store starts empty; the create button becomes available once
    // the issued quote and finalized pour have loaded.
    await waitFor(() => expect(screen.getByTestId('shared-invoices')).toHaveTextContent('none'));
    const createButton = await screen.findByRole('button', { name: /\+ Invoice from issued quote/ });
    await waitFor(() => expect(createButton).toBeEnabled());

    fireEvent.click(createButton);

    // The new invoice must land in the shared store (this is what
    // InvoiceDetail, the Invoices page and the dashboard read).
    await waitFor(() =>
      expect(screen.getByTestId('shared-invoices')).toHaveTextContent(SYNTHETIC_INVOICE.invoiceNumber),
    );
  });
});
