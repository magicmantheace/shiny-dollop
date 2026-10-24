import { sourceLabelText } from '../lib/format';
import { styles } from '../styles';

/** Source label — rendered on every note record so provenance is always visible. */
export default function SourceLabel({ sourceTitle }: { sourceTitle?: string | null }) {
  return <span style={styles.sourceLabel}>Source: {sourceLabelText(sourceTitle)}</span>;
}
