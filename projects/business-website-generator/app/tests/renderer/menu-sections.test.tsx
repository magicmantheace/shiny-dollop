import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it } from 'vitest';
import { ProfileEditor } from '../../src/components/ProfileEditor';
import type { Site } from '../../shared/types';
import { installMockBwg, restaurantSiteId, tradesSiteId, type MockBwg } from './mock-bwg';

let mock: MockBwg;

function editorFor(id: string) {
  const found = mock.__sites.get(id);
  if (!found) throw new Error('site missing');
  const site: Site = structuredClone(found);
  return render(
    <ProfileEditor
      site={site}
      onSaved={() => {}}
      focusSectionId={null}
      onFocusSectionDone={() => {}}
    />,
  );
}

beforeEach(() => {
  mock = installMockBwg();
});

describe('menu sections by business type', () => {
  it('shows menu sections for restaurants', async () => {
    const user = userEvent.setup();
    editorFor(restaurantSiteId(mock));

    const menuSection = screen.getByRole('heading', { name: 'Menu sections' }).closest('section')!;
    const inSection = within(menuSection);
    expect(inSection.getByLabelText('Menu section 1 name')).toHaveValue('Mains');
    expect(inSection.getByLabelText('Item 1 name')).toHaveValue('Burger');

    // Add a menu item to the first section.
    await user.click(inSection.getByRole('button', { name: 'Add menu item' }));
    expect(inSection.getByLabelText('Item 2 name')).toBeInTheDocument();

    // Add a whole new section.
    await user.click(screen.getByRole('button', { name: 'Add menu section' }));
    expect(inSection.getByLabelText('Menu section 2 name')).toBeInTheDocument();
  });

  it('does not show menu sections for trades', () => {
    editorFor(tradesSiteId(mock));
    expect(screen.queryByRole('heading', { name: 'Menu sections' })).not.toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Services' })).toBeInTheDocument();
  });
});
