import type { NoteStatus } from '../types';
import { statusColors, styles } from '../styles';

const LABELS: Record<NoteStatus, string> = {
  candidate: 'Candidate',
  verified: 'Verified',
  rejected: 'Rejected',
};

/** Status badge — rendered on every note record so provenance is always visible. */
export default function StatusBadge({ status }: { status: NoteStatus }) {
  const colors = statusColors[status] ?? { bg: '#222', fg: '#fff' };
  return (
    <span
      style={{ ...styles.badge, background: colors.bg, color: colors.fg }}
      aria-label={`Status: ${LABELS[status]}`}
    >
      {LABELS[status]}
    </span>
  );
}
