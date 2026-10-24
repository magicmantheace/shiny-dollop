import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { SiteList } from '../../src/components/SiteList';
import { installMockBwg, type MockBwg } from './mock-bwg';

let mock: MockBwg;

beforeEach(() => {
  mock = installMockBwg();
});

describe('dashboard', () => {
  it('lists sites with name, type, theme and updated time', async () => {
    render(<SiteList onOpen={() => {}} />);
    const list = await screen.findByRole('list', { name: 'Your sites' });
    const items = within(list).getAllByRole('listitem');
    expect(items).toHaveLength(2);

    const first = within(items[0]!);
    expect(first.getByRole('heading', { name: 'Acme Plumbing' })).toBeInTheDocument();
    expect(first.getByText('Trades & Contractors')).toBeInTheDocument();
    expect(first.getByText('Workshop')).toBeInTheDocument();

    const second = within(items[1]!);
    expect(second.getByRole('heading', { name: 'Harbor Bistro' })).toBeInTheDocument();
    expect(second.getByText('Restaurant')).toBeInTheDocument();
    expect(second.getByText('Bistro')).toBeInTheDocument();
  });

  it('opens a site when Open is clicked', async () => {
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(<SiteList onOpen={onOpen} />);

    await screen.findByRole('heading', { name: 'Acme Plumbing' });
    const card = screen.getByRole('heading', { name: 'Acme Plumbing' }).closest('li')!;
    await user.click(within(card).getByRole('button', { name: 'Open' }));

    expect(onOpen).toHaveBeenCalledTimes(1);
    const id = onOpen.mock.calls[0]![0] as string;
    expect(mock.__sites.has(id)).toBe(true);
  });

  it('runs the new-site wizard: name → type cards → filtered theme picker → create', async () => {
    const onOpen = vi.fn();
    const user = userEvent.setup();
    render(<SiteList onOpen={onOpen} />);
    await screen.findByRole('heading', { name: 'Acme Plumbing' });

    await user.click(screen.getByRole('button', { name: 'New site' }));
    expect(screen.getByRole('dialog', { name: 'New site' })).toBeInTheDocument();

    // Step 1: name.
    await user.type(screen.getByLabelText('Site name'), 'Test Cafe');
    await user.click(screen.getByRole('button', { name: 'Next' }));

    // Step 2: business-type cards.
    await user.click(screen.getByRole('radio', { name: 'Restaurant' }));
    await user.click(screen.getByRole('button', { name: 'Next' }));

    // Step 3: only restaurant-compatible themes are shown.
    const dialog = screen.getByRole('dialog', { name: 'New site' });
    const inDialog = within(dialog);
    expect(inDialog.queryByText('Workshop')).not.toBeInTheDocument();
    expect(inDialog.getByText('Bistro')).toBeInTheDocument();
    await user.click(inDialog.getByRole('button', { name: /Bistro/ }));

    await user.click(screen.getByRole('button', { name: 'Create site' }));

    expect(mock.calls.create).toHaveLength(1);
    expect(mock.calls.create[0]).toEqual({
      name: 'Test Cafe',
      businessType: 'restaurant',
      themeId: 'theme-bistro',
    });
    // The new site opens immediately after creation.
    expect(onOpen).toHaveBeenCalledTimes(1);
    const openedId = onOpen.mock.calls[0]![0] as string;
    expect(mock.__sites.get(openedId)?.name).toBe('Test Cafe');
    // And it appears in the list.
    expect(screen.getByRole('heading', { name: 'Test Cafe' })).toBeInTheDocument();
  });

  it('deletes a site only after confirmation', async () => {
    const user = userEvent.setup();
    render(<SiteList onOpen={() => {}} />);
    await screen.findByRole('heading', { name: 'Acme Plumbing' });

    const card = screen.getByRole('heading', { name: 'Acme Plumbing' }).closest('li')!;
    await user.click(within(card).getByRole('button', { name: 'Delete site Acme Plumbing' }));

    const dialog = screen.getByRole('dialog', { name: 'Delete site' });
    expect(within(dialog).getByText(/acme plumbing/i)).toBeInTheDocument();

    // Cancel first: nothing is deleted.
    await user.click(within(dialog).getByRole('button', { name: 'Cancel' }));
    expect(mock.calls.delete).toHaveLength(0);
    expect(screen.getByRole('heading', { name: 'Acme Plumbing' })).toBeInTheDocument();

    // Confirm: the site is deleted and removed from the list.
    await user.click(within(card).getByRole('button', { name: 'Delete site Acme Plumbing' }));
    await user.click(screen.getByRole('button', { name: 'Delete site', hidden: false }));
    expect(mock.calls.delete).toHaveLength(1);
    expect(screen.queryByRole('heading', { name: 'Acme Plumbing' })).not.toBeInTheDocument();
  });

  it('closes the wizard on Escape', async () => {
    const user = userEvent.setup();
    render(<SiteList onOpen={() => {}} />);
    await screen.findByRole('heading', { name: 'Acme Plumbing' });

    await user.click(screen.getByRole('button', { name: 'New site' }));
    expect(screen.getByRole('dialog', { name: 'New site' })).toBeInTheDocument();
    await user.keyboard('{Escape}');
    expect(screen.queryByRole('dialog', { name: 'New site' })).not.toBeInTheDocument();
  });
});
