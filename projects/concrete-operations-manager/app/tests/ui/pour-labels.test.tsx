import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { StoreProvider } from '../../src/store';
import { JobDetail } from '../../src/views/JobDetail';
import { installMockConcreteOps } from './mockConcreteOps';
import type { Pour } from '../../shared/types';

const POURS: Pour[] = [
  {
    id: 1,
    jobId: 1,
    mixDesignId: 'C25/30',
    quotedLiters: 2500,
    deliveredLiters: 2480,
    createdAt: '2026-10-23T10:00:00.000Z',
  },
  {
    id: 2,
    jobId: 1,
    mixDesignId: 'C32/40',
    quotedLiters: 1500,
    deliveredLiters: null,
    createdAt: '2026-10-23T11:00:00.000Z',
  },
];

describe('JobDetail pours', () => {
  it('distinguishes quoted estimates from measured delivered volumes', async () => {
    installMockConcreteOps({
      pours: {
        listByJob: vi.fn().mockResolvedValue({ ok: true, data: POURS }),
        add: vi.fn(),
        update: vi.fn(),
        setDelivered: vi.fn(),
        remove: vi.fn(),
      },
    });
    render(
      <StoreProvider>
        <JobDetail jobId={1} />
      </StoreProvider>,
    );

    await waitFor(() => expect(screen.getByText('Pours')).toBeInTheDocument());

    // Estimates and measured values are visually distinct…
    expect(screen.getAllByText('estimate').length).toBeGreaterThan(0);
    expect(screen.getByText('measured')).toBeInTheDocument();
    // …with the actual numbers shown.
    expect(screen.getByText('2.500 m³')).toBeInTheDocument();
    expect(screen.getByText('2.480 m³')).toBeInTheDocument();
    // The unfinalized pour is called out.
    expect(screen.getByText('not finalized')).toBeInTheDocument();
  });

  it('labels mix design IDs as nominal, never as verified performance', async () => {
    installMockConcreteOps({
      pours: {
        listByJob: vi.fn().mockResolvedValue({ ok: true, data: POURS }),
        add: vi.fn(),
        update: vi.fn(),
        setDelivered: vi.fn(),
        remove: vi.fn(),
      },
    });
    render(
      <StoreProvider>
        <JobDetail jobId={1} />
      </StoreProvider>,
    );
    await waitFor(() => expect(screen.getByText('Pours')).toBeInTheDocument());
    const nominalLabels = screen.getAllByText('(nominal)');
    expect(nominalLabels.length).toBeGreaterThan(0);
    // The tooltip explains the nominal-only meaning.
    expect(nominalLabels[0]).toHaveAttribute(
      'title',
      expect.stringMatching(/not verified structural performance/i),
    );
  });
});
