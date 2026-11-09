// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, vi, afterEach } from 'vitest';
import ItemFormModal from '../../renderer/src/components/ItemFormModal';
import { installInvMock } from './inv-mock';

afterEach(() => cleanup());

describe('ItemFormModal validation', () => {
  it('blocks submission with an empty name', () => {
    const mock = installInvMock();
    render(
      <ItemFormModal initial={null} categories={['Appliances']} onClose={() => undefined} onSaved={() => undefined} />,
    );

    fireEvent.click(screen.getByRole('button', { name: 'Add item' }));

    expect(screen.getByText('name is required')).toBeInTheDocument();
    expect(mock.items.create).not.toHaveBeenCalled();
  });

  it('blocks a warranty end date before the start date', () => {
    const mock = installInvMock();
    render(
      <ItemFormModal initial={null} categories={['Appliances']} onClose={() => undefined} onSaved={() => undefined} />,
    );

    fireEvent.change(screen.getByLabelText('Name *'), { target: { value: 'Fridge' } });
    fireEvent.change(screen.getByLabelText('Category *'), { target: { value: 'Appliances' } });
    fireEvent.change(screen.getByLabelText('Warranty start'), { target: { value: '2026-01-10' } });
    fireEvent.change(screen.getByLabelText('Warranty end'), { target: { value: '2026-01-05' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add item' }));

    expect(screen.getByText('warranty end must be on or after warranty start')).toBeInTheDocument();
    expect(mock.items.create).not.toHaveBeenCalled();
  });

  it('submits a valid form, converting dollars to integer cents', async () => {
    const mock = installInvMock();
    const onSaved = vi.fn();
    render(
      <ItemFormModal initial={null} categories={['Appliances']} onClose={() => undefined} onSaved={onSaved} />,
    );

    fireEvent.change(screen.getByLabelText('Name *'), { target: { value: 'Fridge' } });
    fireEvent.change(screen.getByLabelText('Category *'), { target: { value: 'Appliances' } });
    fireEvent.change(screen.getByLabelText(/purchase price/i), { target: { value: '899.99' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add item' }));

    expect(mock.items.create).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Fridge', purchasePriceCents: 89999 }),
    );
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });
});
