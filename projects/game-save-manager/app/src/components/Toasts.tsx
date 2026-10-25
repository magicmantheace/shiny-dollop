import { useStore } from '../store';

/** Global status area fed by backup events (completed / failed). */
export default function Toasts(): React.ReactNode {
  const { toasts, dismissToast } = useStore();

  return (
    <div className="gsm-toasts" role="status" aria-live="polite" aria-label="Notifications">
      {toasts.map((t) => (
        <div key={t.id} className={`gsm-toast gsm-toast-${t.kind}`} role={t.kind === 'error' ? 'alert' : 'status'}>
          <div className="gsm-toast-body">
            <strong>{t.title}</strong>
            <p>{t.message}</p>
          </div>
          <button
            type="button"
            className="gsm-toast-close"
            aria-label={`Dismiss notification: ${t.title}`}
            onClick={() => dismissToast(t.id)}
          >
            ×
          </button>
        </div>
      ))}
    </div>
  );
}
