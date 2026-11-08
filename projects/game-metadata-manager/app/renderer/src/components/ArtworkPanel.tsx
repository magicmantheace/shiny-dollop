import type { Artwork } from '../gmm';
import { ArtworkThumb } from './ArtworkThumb';
import { ArtworkAddForm } from './ArtworkAddForm';

interface Props {
  artworks: Artwork[];
  onChanged: () => void;
}

/** Cached artwork grid with provenance labels. */
export function ArtworkPanel({ artworks, onChanged }: Props) {
  return (
    <section className="panel" aria-label="Cached artwork">
      <h2>Cached artwork</h2>
      <p className="muted">
        {artworks.length} cached {artworks.length === 1 ? 'item' : 'items'}.
      </p>
      <div className="artwork-grid">
        {artworks.map((a) => (
          <figure key={a.id} className="artwork-card">
            <ArtworkThumb artworkId={a.id} title={a.fileName} size={120} />
            <figcaption>
              <span className="artwork-name">{a.fileName}</span>
              <span className="muted small">Provenance: {a.provenance}</span>
              <span className="muted small">{a.mime}</span>
            </figcaption>
          </figure>
        ))}
      </div>
      {artworks.length === 0 && <p className="muted">No artwork cached yet.</p>}
      <ArtworkAddForm onAdded={() => onChanged()} />
    </section>
  );
}
