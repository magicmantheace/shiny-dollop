export default function EmptyState({
  title,
  body,
  actionLabel,
  onAction,
}: {
  title: string;
  body: string;
  actionLabel?: string;
  onAction?: () => void;
}) {
  return (
    <div className="empty">
      <h2>{title}</h2>
      <p className="muted">{body}</p>
      {actionLabel && onAction && (
        <button className="btn primary" onClick={onAction}>
          {actionLabel}
        </button>
      )}
    </div>
  );
}
