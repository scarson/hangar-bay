// ABOUTME: Header notification bell — a Link to /notifications with an unread-count badge; the badge is hidden at zero.
// ABOUTME: The unread count comes from useUnreadCount (60s poll, authed-only); the accessible name always announces the count.
import { Link } from '@tanstack/react-router'
import { useUnreadCount } from '../hooks/useNotifications'

export function NotificationBell() {
  const { data } = useUnreadCount()
  const count = data ?? 0
  return (
    <Link
      to="/notifications"
      aria-label={`Notifications (${count} unread)`}
      className="relative inline-flex h-8 w-8 items-center justify-center rounded-md text-ink-body hover:bg-raised"
    >
      <svg viewBox="0 0 20 20" width={18} height={18} fill="currentColor" aria-hidden="true">
        <path d="M10 2a5 5 0 0 0-5 5v3l-1.5 2.5A.5.5 0 0 0 4 15h12a.5.5 0 0 0 .4-.8L15 12V7a5 5 0 0 0-5-5Zm0 16a2.5 2.5 0 0 0 2.45-2h-4.9A2.5 2.5 0 0 0 10 18Z" />
      </svg>
      {count > 0 ? (
        <span className="absolute -top-1 -right-1 inline-flex min-w-4 items-center justify-center rounded-full border border-brand-dim bg-brand-wash px-1 font-mono text-micro text-brand">
          {count}
        </span>
      ) : null}
    </Link>
  )
}
