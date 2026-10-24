import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { LibraryView } from '../src/components/LibraryView';
import { installGmmMock, makeCollection, makeGame, makeTag, uninstallGmmMock } from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
});

function renderLibrary() {
  const mock = installGmmMock();
  const games = [
    makeGame({ id: 'g1', title: 'Doom Eternal', tagIds: ['t1'], collectionIds: ['c1'] }),
    makeGame({ id: 'g2', title: 'Stardew Valley', tagIds: ['t2'], missing: true }),
    makeGame({ id: 'g3', title: 'Doom 1993', tagIds: ['t1'] }),
  ];
  const tags = [makeTag({ id: 't1', name: 'Shooter' }), makeTag({ id: 't2', name: 'Cozy' })];
  const collections = [makeCollection({ id: 'c1', name: 'Favorites' })];
  const onChanged = vi.fn();
  render(
    <LibraryView
      games={games}
      tags={tags}
      collections={collections}
      onSelect={() => undefined}
      onChanged={onChanged}
    />,
  );
  return { mock, games, onChanged };
}

describe('LibraryView', () => {
  it('renders the full game list with titles', () => {
    renderLibrary();
    expect(screen.getByText('Doom Eternal')).toBeInTheDocument();
    expect(screen.getByText('Stardew Valley')).toBeInTheDocument();
    expect(screen.getByText('Doom 1993')).toBeInTheDocument();
    expect(screen.getByText('3 of 3 games')).toBeInTheDocument();
  });

  it('shows a MISSING badge for games whose install is missing', () => {
    renderLibrary();
    const item = screen.getByText('Stardew Valley').closest('button');
    expect(item).not.toBeNull();
    expect(within(item as HTMLElement).getByText('MISSING')).toBeInTheDocument();
    const present = screen.getByText('Doom Eternal').closest('button');
    expect(within(present as HTMLElement).queryByText('MISSING')).not.toBeInTheDocument();
  });

  it('filters by search text (case-insensitive)', async () => {
    const user = userEvent.setup();
    renderLibrary();
    await user.type(screen.getByLabelText('Search games'), 'doom');
    expect(screen.getByText('Doom Eternal')).toBeInTheDocument();
    expect(screen.getByText('Doom 1993')).toBeInTheDocument();
    expect(screen.queryByText('Stardew Valley')).not.toBeInTheDocument();
    expect(screen.getByText('2 of 3 games')).toBeInTheDocument();
  });

  it('filters by tag', async () => {
    const user = userEvent.setup();
    renderLibrary();
    await user.selectOptions(screen.getByLabelText('Filter by tag'), 't2');
    expect(screen.getByText('Stardew Valley')).toBeInTheDocument();
    expect(screen.queryByText('Doom Eternal')).not.toBeInTheDocument();
    expect(screen.queryByText('Doom 1993')).not.toBeInTheDocument();
  });

  it('filters by collection', async () => {
    const user = userEvent.setup();
    renderLibrary();
    await user.selectOptions(screen.getByLabelText('Filter by collection'), 'c1');
    expect(screen.getByText('Doom Eternal')).toBeInTheDocument();
    expect(screen.queryByText('Stardew Valley')).not.toBeInTheDocument();
  });

  it('missing-only toggle shows just the missing games', async () => {
    const user = userEvent.setup();
    renderLibrary();
    await user.click(screen.getByLabelText('Missing only'));
    expect(screen.getByText('Stardew Valley')).toBeInTheDocument();
    expect(screen.queryByText('Doom Eternal')).not.toBeInTheDocument();
    expect(screen.queryByText('Doom 1993')).not.toBeInTheDocument();
    expect(screen.getByText('1 of 3 games')).toBeInTheDocument();
  });

  it('combines search and missing-only filters', async () => {
    const user = userEvent.setup();
    renderLibrary();
    await user.click(screen.getByLabelText('Missing only'));
    await user.type(screen.getByLabelText('Search games'), 'doom');
    expect(screen.queryByText('Stardew Valley')).not.toBeInTheDocument();
    expect(screen.getByText('No games match these filters.')).toBeInTheDocument();
  });

  it('rescan reports the missing count and refreshes', async () => {
    const user = userEvent.setup();
    const { mock, onChanged } = renderLibrary();
    mock.lib.rescan.mockResolvedValue({ missingIds: ['g2'] });
    await user.click(screen.getByRole('button', { name: /detect missing installs/i }));
    expect(mock.lib.rescan).toHaveBeenCalledTimes(1);
    expect(await screen.findByText('Rescan complete — 1 missing install detected.')).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it('rescan reports when nothing is missing', async () => {
    const user = userEvent.setup();
    const { mock } = renderLibrary();
    mock.lib.rescan.mockResolvedValue({ missingIds: [] });
    await user.click(screen.getByRole('button', { name: /detect missing installs/i }));
    expect(
      await screen.findByText('Rescan complete — every install path was found.'),
    ).toBeInTheDocument();
  });

  it('selects a game when its row is clicked', async () => {
    const user = userEvent.setup();
    installGmmMock();
    const games = [makeGame({ id: 'g1', title: 'Doom Eternal' })];
    let selected: string | null = null;
    render(
      <LibraryView
        games={games}
        tags={[]}
        collections={[]}
        onSelect={(id) => {
          selected = id;
        }}
        onChanged={() => undefined}
      />,
    );
    await user.click(screen.getByText('Doom Eternal'));
    expect(selected).toBe('g1');
  });
});
