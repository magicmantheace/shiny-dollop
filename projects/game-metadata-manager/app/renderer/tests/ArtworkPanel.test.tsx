import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ArtworkPanel } from '../src/components/ArtworkPanel';
import { installGmmMock, makeArtwork, uninstallGmmMock } from './mock-gmm';

afterEach(() => {
  uninstallGmmMock();
});

describe('ArtworkPanel', () => {
  it('renders cached artwork with provenance labels', () => {
    installGmmMock();
    const artworks = [
      makeArtwork({ id: 'a1', fileName: 'cover.png', provenance: 'box scan', mime: 'image/png' }),
      makeArtwork({ id: 'a2', fileName: 'hero.jpg', provenance: 'press kit', mime: 'image/jpeg' }),
    ];
    render(<ArtworkPanel artworks={artworks} onChanged={() => undefined} />);
    expect(screen.getByText('2 cached items.')).toBeInTheDocument();
    expect(screen.getByText('cover.png')).toBeInTheDocument();
    expect(screen.getByText(/Provenance: box scan/)).toBeInTheDocument();
    expect(screen.getByText('hero.jpg')).toBeInTheDocument();
    expect(screen.getByText(/Provenance: press kit/)).toBeInTheDocument();
  });

  it('shows an empty state when nothing is cached', () => {
    installGmmMock();
    render(<ArtworkPanel artworks={[]} onChanged={() => undefined} />);
    expect(screen.getByText('No artwork cached yet.')).toBeInTheDocument();
  });

  it('adds artwork from a file path with provenance', async () => {
    const user = userEvent.setup();
    const mock = installGmmMock();
    const onChanged = vi.fn();
    render(<ArtworkPanel artworks={[]} onChanged={onChanged} />);
    await user.type(screen.getByLabelText('Artwork file path'), 'D:\\art\\cover.png');
    await user.type(screen.getByLabelText('Artwork provenance'), 'scanned manual');
    await user.click(screen.getByRole('button', { name: 'Add artwork' }));
    expect(mock.artwork.add).toHaveBeenCalledWith('D:\\art\\cover.png', 'scanned manual');
    // The panel asks the parent to reload the grid rather than appending locally.
    expect(onChanged).toHaveBeenCalled();
  });

  it('rejects an empty artwork path', async () => {
    const user = userEvent.setup();
    const mock = installGmmMock();
    render(<ArtworkPanel artworks={[]} onChanged={() => undefined} />);
    await user.click(screen.getByRole('button', { name: 'Add artwork' }));
    expect(await screen.findByText('Enter a file path for the artwork.')).toBeInTheDocument();
    expect(mock.artwork.add).not.toHaveBeenCalled();
  });
});
