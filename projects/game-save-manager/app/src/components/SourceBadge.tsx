import type { GameSource } from '../../shared/types';

const LABELS: Record<GameSource, string> = {
  manual: 'Manual',
  steam: 'Steam',
  epic: 'Epic',
  battlenet: 'Battle.net',
  discovered: 'Discovered',
};

/** Small badge showing where a tracked game entry came from. */
export default function SourceBadge({ source }: { source: GameSource }): React.ReactNode {
  return (
    <span className={`gsm-badge gsm-badge-${source}`} title={`Source: ${LABELS[source]}`}>
      {LABELS[source]}
    </span>
  );
}
