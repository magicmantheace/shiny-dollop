import { afterEach, describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { getGmm, useArtworkUrl } from '../src/gmm';
import { installFlatGmmMock, installGmmMock, uninstallGmmMock } from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
});

function Probe({ artworkId }: { artworkId: string | null }) {
  const url = useArtworkUrl(artworkId);
  return <span data-testid="url">{url ?? 'none'}</span>;
}

describe('gmm bridge', () => {
  it('throws a helpful error when window.gmm is absent', () => {
    expect(() => getGmm()).toThrow('window.gmm is not available');
  });

  it('throws on an unrecognized bridge shape', () => {
    Object.defineProperty(window, 'gmm', {
      value: { notAnApi: true },
      configurable: true,
      writable: true,
    });
    expect(() => getGmm()).toThrow('unrecognized shape');
  });

  it('uses a nested bridge directly when present', async () => {
    const mock = installGmmMock();
    const api = getGmm();
    await api.lib.list();
    expect(mock.lib.list).toHaveBeenCalledTimes(1);
  });

  it('adapts the flat preload bridge to the nested API', async () => {
    const flat = installFlatGmmMock();
    const api = getGmm();

    await api.lib.importRoots(['C:\\Games']);
    expect(flat.importRoots).toHaveBeenCalledWith(['C:\\Games']);

    await api.lib.list();
    expect(flat.list).toHaveBeenCalledTimes(1);

    await api.lib.rescan();
    expect(flat.rescan).toHaveBeenCalledTimes(1);

    await api.game.update('g1', { title: 'New' });
    expect(flat.updateGame).toHaveBeenCalledWith('g1', { title: 'New' });

    await api.artwork.add('C:\\a.png', 'box scan');
    expect(flat.addArtwork).toHaveBeenCalledWith('C:\\a.png', 'box scan');

    await api.artwork.list();
    expect(flat.listArtwork).toHaveBeenCalledTimes(1);

    await api.tags.add('RPG');
    expect(flat.addTag).toHaveBeenCalledWith('RPG');
    await api.tags.remove('t1');
    expect(flat.removeTag).toHaveBeenCalledWith('t1');

    await api.collections.add('Backlog');
    expect(flat.addCollection).toHaveBeenCalledWith('Backlog');

    await api.bundle.export();
    expect(flat.exportBundle).toHaveBeenCalledTimes(1);
    await api.bundle.import('{}');
    expect(flat.importBundle).toHaveBeenCalledWith('{}');

    await api.changes.list('g1');
    expect(flat.listChanges).toHaveBeenCalledWith('g1');
    await api.changes.undo();
    expect(flat.undo).toHaveBeenCalledTimes(1);
  });

  it('useArtworkUrl resolves the async flat fileUrl', async () => {
    installFlatGmmMock();
    render(<Probe artworkId="a1" />);
    expect(await screen.findByText('file:///artwork-cache/a1')).toBeInTheDocument();
  });

  it('useArtworkUrl tolerates the sync spec-shaped fileUrl', async () => {
    installGmmMock();
    render(<Probe artworkId="a1" />);
    expect(await screen.findByText('file:///artwork-cache/a1')).toBeInTheDocument();
  });

  it('useArtworkUrl yields null without an artwork id', () => {
    installGmmMock();
    render(<Probe artworkId={null} />);
    expect(screen.getByTestId('url')).toHaveTextContent('none');
  });

  it('useArtworkUrl yields null when the bridge is absent', () => {
    render(<Probe artworkId="a1" />);
    expect(screen.getByTestId('url')).toHaveTextContent('none');
  });
});
