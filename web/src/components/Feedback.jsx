import { CircleCheck, TriangleAlert, CircleX, Info, LoaderCircle, RefreshCw } from 'lucide-react';

const TOAST_ICONS = { success: CircleCheck, warning: TriangleAlert, error: CircleX, info: Info };

export function Toast({ notification }) {
  if (!notification) return null;
  const Icon = TOAST_ICONS[notification.type] || Info;
  return (
    <div className={`toast toast--${notification.type}`} role="status" aria-live="polite">
      <Icon className="toast__icon" size={20} aria-hidden="true" />
      {notification.message}
    </div>
  );
}

// Shown at the top of every screen while a request is slow: the free API host
// sleeps when idle and takes up to a minute to wake (#27).
export function WakingBanner({ show }) {
  if (!show) return null;
  return (
    <div className="waking-banner" role="status" aria-live="polite">
      <LoaderCircle size={16} className="spinner" aria-hidden="true" />
      Waking up the server… The free host sleeps when it's quiet, so this can take up to a minute.
    </div>
  );
}

// A request that failed but can be tried again: the server's message and a Retry button.
export function RetryPanel({ message, onRetry, busy = false }) {
  return (
    <div className="retry-panel" role="alert">
      <TriangleAlert size={22} aria-hidden="true" className="retry-panel__icon" />
      <p className="retry-panel__message">{message}</p>
      <button type="button" className="btn btn--primary" onClick={onRetry} disabled={busy}>
        <RefreshCw size={16} aria-hidden="true" /> Retry
      </button>
    </div>
  );
}

export function EmptyState({ icon: Icon, title, children, action }) {
  return (
    <div className="empty">
      {Icon && (
        <div className="empty__icon"><Icon size={26} aria-hidden="true" /></div>
      )}
      <h3 className="empty__title">{title}</h3>
      {children && <p className="empty__text">{children}</p>}
      {action}
    </div>
  );
}
