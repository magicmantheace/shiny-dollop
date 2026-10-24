// @vitest-environment jsdom
import '@testing-library/jest-dom/vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import { describe, it, expect, afterEach } from 'vitest';
import ItemsView from '../../renderer/src/components/ItemsView';
import { installInvMock, itemFixture } from './inv-mock';

afterEach(() => cleanup());

describe('ItemsView search/filter', () => {
  it('narrows the item table when the search box is used', async () => {
    const mock = installInvMock();
    const washer = itemFixture({ id: 'a', name: 'Washing Machine', category: 'Appliances' });
    const fridge = itemFixture({ id: 'b', name: 'Fridge', category: 'Appliances' });
    mock.items.list.mockImplementation(async (filter: { search?: string } = {}) => {
      const q = (filter.search ?? '').toLowerCase();
      return [washer, fridge].filter((i) => i.name.toLowerCase().includes(q));
    });
    mock.categories.list.mockResolvedValue(['Appliances']);

    render(<ItemsView onSelectItem={() => undefined} />);

    // Both rows appear on initial load.
    await waitFor(() => expect(screen.getByText('Washing Machine')).toBeInTheDocument());
    expect(screen.getByText('Fridge')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('Search name, serial, notes…'), {
      target: { value: 'wash' },
    });

    // Debounced filter narrows the table; the mock records the server-side filter.
    await waitFor(() => {
      expect(screen.queryByText('Fridge')).not.toBeInTheDocument();
      expect(screen.getByText('Washing Machine')).toBeInTheDocument();
    });
    const calls = mock.items.list.mock.calls;
    expect(calls[calls.length - 1][0]).toMatchObject({ search: 'wash' });
  });

  it('filters by category through the dropdown', async () => {
    const mock = installInvMock();
    const drill = itemFixture({ id: 'a', name: 'Drill', category: 'Tools' });
    const lamp = itemFixture({ id: 'b', name: 'Lamp', category: 'Lighting' });
    mock.items.list.mockImplementation(async (filter: { category?: string } = {}) =>
      [drill, lamp].filter((i) => !filter.category || i.category === filter.category),
    );
    mock.categories.list.mockResolvedValue(['Tools', 'Lighting']);

    render(<ItemsView onSelectItem={() => undefined} />);
    await waitFor(() => expect(screen.getByText('Drill')).toBeInTheDocument());

    fireEvent.change(screen.getByLabelText('Category'), { target: { value: 'Tools' } });

    await waitFor(() => {
      expect(screen.queryByText('Lamp')).not.toBeInTheDocument();
      expect(screen.getByText('Drill')).toBeInTheDocument();
    });
  });
});
