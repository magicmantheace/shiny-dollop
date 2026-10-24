import { useState } from 'react';
import { useArtworkUrl } from '../gmm';

interface Props {
  artworkId: string | null;
  title: string;
  size?: number;
}

/** Cached-artwork thumbnail; degrades to a labeled placeholder when missing. */
export function ArtworkThumb({ artworkId, title, size = 64 }: Props) {
  const [failed, setFailed] = useState(false);
  const url = useArtworkUrl(artworkId);

  if (!url || failed) {
    return (
      <span
        className="thumb thumb-placeholder"
        style={{ width: size, height: size }}
        role="img"
        aria-label={`No artwork for ${title}`}
      >
        ?
      </span>
    );
  }
  return (
    <img
      className="thumb"
      src={url}
      alt={`Artwork for ${title}`}
      width={size}
      height={size}
      onError={() => setFailed(true)}
    />
  );
}
