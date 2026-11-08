export interface ErrorBannerProps {
  message: string;
  onDismiss: () => void;
}

/** Dismissible error banner with an accessible alert role. */
export function ErrorBanner({ message, onDismiss }: ErrorBannerProps) {
  return (
    <div className="error-banner" role="alert">
      <span>{message}</span>
      <button type="button" onClick={onDismiss} aria-label="Dismiss error">
        Dismiss
      </button>
    </div>
  );
}
