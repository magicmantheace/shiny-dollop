import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { GameDetailView } from '../src/components/GameDetailView';
import {
  installGmmMock,
  makeArtwork,
  makeChange,
  makeCollection,
  makeGame,
  makeTag,
  uninstallGmmMock,
} from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
});

function renderDetail() {
  const mock = installGmmMock();
  const game = makeGame({
    id: 'g1',
    title: 'Doom Eternal',
    originalTitle: 'DOOM Eternal',
    description: 'Rip and tear.',
    installPath: 'C:\\Games\\DoomEternal',
    tagIds: [],
    collectionIds: [],
  });
  const tags = [makeTag({ id: 't1', name: 'Shooter' })];
  const collections = [makeCollection({ id: 'c1', name: 'Favorites' })];
  const artworks = [makeArtwork({ id: 'a1', fileName: 'cover.png', provenance: 'box scan' })];
  const onChanged = vi.fn();
  render(
    <GameDetailView
      game={game}
      tags={tags}
      collections={collections}
      artworks={artworks}
      onBack={() => undefined}
      onChanged={onChanged}
    />,
  );
  return { mock, game, onChanged };
}

describe('GameDetailView', () => {
  it('shows the missing-install warning with the install path', () => {
    installGmmMock();
    const game = makeGame({ id: 'g9', title: 'Gone', missing: true, installPath: 'D:\\Lost\\Gone' });
    render(
      <GameDetailView
        game={game}
        tags={[]}
        collections={[]}
        artworks={[]}
        onBack={() => undefined}
        onChanged={() => undefined}
      />,
    );
    const banner = screen.getByRole('alert');
    expect(banner).toHaveTextContent(/install not found at/i);
    expect(banner).toHaveTextContent('D:\\Lost\\Gone');
    expect(banner).toHaveTextContent(/nothing was deleted/i);
  });

  it('does not show the warning for present installs', () => {
    renderDetail();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('rejects an empty title and does not call update', async () => {
    const user = userEvent.setup();
    const { mock } = renderDetail();
    await user.clear(screen.getByLabelText('Game title'));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Title cannot be empty.')).toBeInTheDocument();
    expect(mock.game.update).not.toHaveBeenCalled();
  });

  it('saves title, description, tags and collections via game:update', async () => {
    const user = userEvent.setup();
    const { mock, onChanged } = renderDetail();
    await user.clear(screen.getByLabelText('Game title'));
    await user.type(screen.getByLabelText('Game title'), 'Doom Eternal II');
    await user.clear(screen.getByLabelText('Game description'));
    await user.type(screen.getByLabelText('Game description'), 'More ripping.');
    await user.click(screen.getByRole('checkbox', { name: 'Shooter' }));
    await user.click(screen.getByRole('checkbox', { name: 'Favorites' }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(mock.game.update).toHaveBeenCalledTimes(1);
    expect(mock.game.update).toHaveBeenCalledWith(
      'g1',
      expect.objectContaining({
        title: 'Doom Eternal II',
        description: 'More ripping.',
        tagIds: ['t1'],
        collectionIds: ['c1'],
      }),
    );
    expect(await screen.findByText('Saved.')).toBeInTheDocument();
    expect(onChanged).toHaveBeenCalled();
  });

  it('assigns artwork from the picker', async () => {
    const user = userEvent.setup();
    const { mock } = renderDetail();
    await user.click(screen.getByRole('radio', { name: /cover\.png/ }));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(mock.game.update).toHaveBeenCalledWith(
      'g1',
      expect.objectContaining({ artworkId: 'a1' }),
    );
  });

  it('shows provenance for the selected artwork', async () => {
    const user = userEvent.setup();
    renderDetail();
    await user.click(screen.getByRole('radio', { name: /cover\.png/ }));
    expect(await screen.findByText(/Provenance: box scan/)).toBeInTheDocument();
  });

  it('adds new artwork from a file path and selects it', async () => {
    const user = userEvent.setup();
    const { mock } = renderDetail();
    await user.type(screen.getByLabelText('Artwork file path'), 'C:\\art\\new.png');
    await user.type(screen.getByLabelText('Artwork provenance'), 'fan art');
    await user.click(screen.getByRole('button', { name: 'Add artwork' }));
    expect(mock.artwork.add).toHaveBeenCalledWith('C:\\art\\new.png', 'fan art');
    expect(await screen.findByRole('radio', { name: /new\.png/ })).toBeInTheDocument();
  });

  it('rejects an empty artwork path', async () => {
    const user = userEvent.setup();
    const { mock } = renderDetail();
    await user.click(screen.getByRole('button', { name: 'Add artwork' }));
    expect(await screen.findByText('Enter a file path for the artwork.')).toBeInTheDocument();
    expect(mock.artwork.add).not.toHaveBeenCalled();
  });

  it('syncs the draft when the persisted game is reverted by undo while staying in detail view', async () => {
    const user = userEvent.setup();
    const mock = installGmmMock();
    const tags: never[] = [];
    const collections: never[] = [];
    const artworks: never[] = [];
    const game = makeGame({
      id: 'g1',
      title: 'Original Title',
      updatedAt: '2026-10-23T00:00:00.000Z',
    });
    const { rerender } = render(
      <GameDetailView
        game={game}
        tags={tags}
        collections={collections}
        artworks={artworks}
        onBack={() => undefined}
        onChanged={() => undefined}
      />,
    );
    // Save a new title and stay in the detail view.
    await user.clear(screen.getByLabelText('Game title'));
    await user.type(screen.getByLabelText('Game title'), 'Saved Title');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(await screen.findByText('Saved.')).toBeInTheDocument();
    expect(screen.getByLabelText('Game title')).toHaveValue('Saved Title');

    // Header Undo reverts the persisted title; App refreshes with the same
    // game-id key, so the mounted view receives the reverted game as a prop.
    rerender(
      <GameDetailView
        game={{ ...game, title: 'Original Title', updatedAt: '2026-10-24T00:00:00.000Z' }}
        tags={tags}
        collections={collections}
        artworks={artworks}
        onBack={() => undefined}
        onChanged={() => undefined}
      />,
    );
    expect(screen.getByLabelText('Game title')).toHaveValue('Original Title');

    // Saving again must write the reverted value, not resurrect the undone one.
    mock.game.update.mockClear();
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    expect(mock.game.update).toHaveBeenCalledWith(
      'g1',
      expect.objectContaining({ title: 'Original Title' }),
    );
  });

  it('preserves unsaved edits during an artwork-only refresh', async () => {
    const user = userEvent.setup();
    installGmmMock();
    const game = makeGame({ id: 'g1', title: 'Persisted Title' });
    const a1 = makeArtwork({ id: 'a1', fileName: 'cover.png' });
    const a2 = makeArtwork({ id: 'a2', fileName: 'new-cover.png' });
    const { rerender } = render(
      <GameDetailView
        game={game}
        tags={[]}
        collections={[]}
        artworks={[a1]}
        onBack={() => undefined}
        onChanged={() => undefined}
      />,
    );
    await user.clear(screen.getByLabelText('Game title'));
    await user.type(screen.getByLabelText('Game title'), 'Unsaved Title');

    // A refresh that only brings new artwork (persisted game unchanged) must
    // not discard the unsaved title, and the new artwork must appear.
    rerender(
      <GameDetailView
        game={{ ...game }}
        tags={[]}
        collections={[]}
        artworks={[a1, a2]}
        onBack={() => undefined}
        onChanged={() => undefined}
      />,
    );
    expect(screen.getByLabelText('Game title')).toHaveValue('Unsaved Title');
    expect(screen.getByRole('radio', { name: /new-cover\.png/ })).toBeInTheDocument();
  });

  it('preserves an unsaved field while syncing a reverted clean field', async () => {
    const user = userEvent.setup();
    installGmmMock();
    const game = makeGame({
      id: 'g1',
      title: 'Saved Title',
      description: 'Persisted description',
      updatedAt: '2026-10-23T00:00:00.000Z',
    });
    const { rerender } = render(
      <GameDetailView
        game={game}
        tags={[]}
        collections={[]}
        artworks={[]}
        onBack={() => undefined}
        onChanged={() => undefined}
      />,
    );
    await user.clear(screen.getByLabelText('Game description'));
    await user.type(screen.getByLabelText('Game description'), 'Unsaved description draft');

    // Undo reverts only the (clean) title; the dirty description draft stays.
    rerender(
      <GameDetailView
        game={{ ...game, title: 'Title Before Save', updatedAt: '2026-10-24T00:00:00.000Z' }}
        tags={[]}
        collections={[]}
        artworks={[]}
        onBack={() => undefined}
        onChanged={() => undefined}
      />,
    );
    expect(screen.getByLabelText('Game title')).toHaveValue('Title Before Save');
    expect(screen.getByLabelText('Game description')).toHaveValue('Unsaved description draft');
  });

  it('shows the change history for the game', async () => {
    const mock = installGmmMock();
    mock.changes.list.mockResolvedValue([
      makeChange({ id: 7, field: 'title', before: 'Doom', after: 'Doom Eternal' }),
    ]);
    const game = makeGame({ id: 'g1', title: 'Doom Eternal' });
    render(
      <GameDetailView
        game={game}
        tags={[]}
        collections={[]}
        artworks={[]}
        onBack={() => undefined}
        onChanged={() => undefined}
      />,
    );
    expect(mock.changes.list).toHaveBeenCalledWith('g1');
    expect(await screen.findByText('Doom')).toBeInTheDocument();
    expect(screen.getByText('Doom Eternal', { selector: 'td' })).toBeInTheDocument();
  });
});
