import type { Capability, ChangeKind } from '../../shared/gpp-types';

interface Props {
  kind: ChangeKind;
  capabilities: Capability[];
}

/**
 * Supported / unsupported / unknown badge for one change kind.
 *
 * Capability lookup is by capability id; ids are expected to match the
 * ChangeKind strings. A missing capability renders as "unknown", never as
 * supported — the UI must not imply a change will work when the backend
 * did not report it.
 */
export function CapabilityBadge({ kind, capabilities }: Props) {
  const cap = capabilities.find((c) => c.id === kind);
  if (!cap) {
    return (
      <span className="badge badge-unknown" title={`No capability report for ${kind}`}>
        unknown
      </span>
    );
  }
  if (cap.supported) {
    return (
      <span className="badge badge-ok" title={cap.description}>
        supported
      </span>
    );
  }
  return (
    <span
      className="badge badge-bad"
      title={cap.reason ?? 'Not supported on this machine'}
    >
      unsupported
    </span>
  );
}
