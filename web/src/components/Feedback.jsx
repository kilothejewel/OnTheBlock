import { CircleCheck, TriangleAlert, CircleX, Info } from 'lucide-react';

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
