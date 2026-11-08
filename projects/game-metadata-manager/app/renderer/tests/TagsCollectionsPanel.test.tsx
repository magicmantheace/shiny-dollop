import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { TagsCollectionsPanel } from '../src/components/TagsCollectionsPanel';
import { installGmmMock, makeCollection, makeTag, uninstallGmmMock } from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
});

function renderPanel() {
  const mock = installGmmMock();
  const tags = [makeTag({ id: 't1', name: 'RPG' })];
  const collections = [makeCollection({ id: 'c1', name: 'Backlog' })];
  const onChanged = vi.fn();
  render(<TagsCollectionsPanel tags={tags} collections={collections} onChanged={onChanged} />);
  return { mock, onChanged };
}

describe('TagsCollectionsPanel', () => {
  it('lists existing tags and collections', () => {
    renderPanel();
    expect(screen.getByText('RPG')).toBeInTheDocument();
    expect(screen.getByText('Backlog')).toBeInTheDocument();
  });

  it('adds a tag', async () => {
    const user = userEvent.setup();
    const { mock, onChanged } = renderPanel();
    await user.type(screen.getByLabelText('New tag name'), 'Roguelike');
    await user.click(screen.getByRole('button', { name: 'Add tag' }));
    expect(mock.tags.add).toHaveBeenCalledWith('Roguelike');
    expect(onChanged).toHaveBeenCalled();
  });

  it('rejects an empty tag name', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    await user.click(screen.getByRole('button', { name: 'Add tag' }));
    expect(await screen.findByText('Tag name cannot be empty.')).toBeInTheDocument();
    expect(mock.tags.add).not.toHaveBeenCalled();
  });

  it('removes a tag', async () => {
    const user = userEvent.setup();
    const { mock, onChanged } = renderPanel();
    await user.click(screen.getByRole('button', { name: 'Remove tag RPG' }));
    expect(mock.tags.remove).toHaveBeenCalledWith('t1');
    expect(onChanged).toHaveBeenCalled();
  });

  it('adds a collection', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    await user.type(screen.getByLabelText('New collection name'), 'Co-op night');
    await user.click(screen.getByRole('button', { name: 'Add collection' }));
    expect(mock.collections.add).toHaveBeenCalledWith('Co-op night');
  });

  it('rejects an empty collection name', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    await user.click(screen.getByRole('button', { name: 'Add collection' }));
    expect(await screen.findByText('Collection name cannot be empty.')).toBeInTheDocument();
    expect(mock.collections.add).not.toHaveBeenCalled();
  });

  it('removes a collection', async () => {
    const user = userEvent.setup();
    const { mock } = renderPanel();
    await user.click(screen.getByRole('button', { name: 'Remove collection Backlog' }));
    expect(mock.collections.remove).toHaveBeenCalledWith('c1');
  });
});
