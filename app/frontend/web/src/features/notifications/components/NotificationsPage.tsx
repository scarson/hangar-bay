// ABOUTME: F007 notifications page — auth-gated paginated list, mark-read-on-click (+deep-link), mark-all-read, and the watchlist-alerts settings checkbox.
// ABOUTME: Unread rows are visually distinct; row activation marks read then (when a contract is present) navigates to it.
import { useState } from 'react'
import { Link } from '@tanstack/react-router'
import { Button } from '../../../components/Button'
import { CheckboxField } from '../../../components/Checkbox'
import type { Notification } from '../../../lib/api/client'
import { useDocumentTitle } from '../../../lib/useDocumentTitle'
import { RequireSignIn } from '../../auth/components/RequireSignIn'
import { useCurrentUser } from '../../auth/hooks/useCurrentUser'
import { Pagination } from '../../contracts/components/Pagination'
import { timeAgo } from '../format'
import {
  useMarkAllRead,
  useMarkRead,
  useNotificationSettings,
  useNotifications,
  useUpdateNotificationSettings,
} from '../hooks/useNotifications'

const PAGE_SIZE = 20

export function NotificationsPage() {
  useDocumentTitle('Notifications')
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return (
      <div role="status" aria-label="Loading account" className="mx-auto max-w-3xl">
        <span className="skeleton block h-7 w-48" />
        <span className="sr-only">Loading…</span>
      </div>
    )
  }
  if (!user) return <RequireSignIn feature="notifications" />
  return <NotificationsBody />
}

function NotificationsBody() {
  const [page, setPage] = useState(1)
  const { data, isPending, isError } = useNotifications({ page, size: PAGE_SIZE })
  const markAll = useMarkAllRead()

  return (
    <div className="mx-auto max-w-3xl">
      <p className="sr-only" role="status" aria-live="polite" />
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="text-h1 font-semibold">Notifications</h1>
        <Button className="ml-auto" onClick={() => markAll.mutate()} disabled={markAll.isPending}>
          Mark all as read
        </Button>
      </div>

      <SettingsToggle />

      {isPending ? (
        <div role="status" aria-label="Loading notifications" className="mt-4">
          <span className="skeleton block h-16 w-full" />
          <span className="sr-only">Loading notifications…</span>
        </div>
      ) : isError ? (
        <div role="alert" className="mt-4 rounded-md border border-danger/40 bg-danger-wash px-4 py-4 text-sm text-ink">
          Couldn’t load your notifications. Reload the page to try again.
        </div>
      ) : data.items.length === 0 ? (
        <div className="mt-4 rounded-md border border-line bg-surface px-5 py-8">
          <h2 className="text-base font-medium text-ink">No notifications yet</h2>
          <p className="mt-1 max-w-[52ch] text-sm text-ink-dim">
            When a ship on your watchlist appears in a contract at or below your max price, you’ll see it here.
          </p>
        </div>
      ) : (
        <>
          <ul className="mt-4 flex flex-col gap-2">
            {data.items.map((n) => (
              <NotificationRow key={n.id} n={n} />
            ))}
          </ul>
          <div className="mt-4">
            <Pagination page={page} size={data.size ?? PAGE_SIZE} total={data.total} onPage={setPage} unitLabel="notifications" />
          </div>
        </>
      )}
    </div>
  )
}

function SettingsToggle() {
  const settingsQuery = useNotificationSettings()
  const update = useUpdateNotificationSettings()
  return (
    <div className="rounded-md border border-line bg-surface px-4 py-3">
      <CheckboxField
        label="Watchlist alerts"
        checked={settingsQuery.data?.watchlist_alerts_enabled ?? false}
        // Disabled until settings load so a click can't PUT a value derived from the `?? false`
        // fallback rather than the user's persisted state; also locked during an in-flight write.
        disabled={settingsQuery.isPending || update.isPending}
        onChange={(checked) => update.mutate({ watchlist_alerts_enabled: checked })}
      />
    </div>
  )
}

function NotificationRow({ n }: { n: Notification }) {
  const markRead = useMarkRead()
  const activate = () => {
    if (!n.is_read) markRead.mutate(n.id)
  }
  const className = `flex flex-col gap-1 rounded-md border px-4 py-3 text-left ${
    n.is_read ? 'border-line bg-surface' : 'border-l-2 border-l-brand border-line bg-raised'
  }`
  const body = (
    <>
      {!n.is_read ? <span className="sr-only">Unread. </span> : null}
      <span className="text-sm text-ink">{n.message}</span>
      <span className="text-xs text-ink-dim">{timeAgo(n.created_at)}</span>
    </>
  )
  if (n.contract_id != null) {
    return (
      <li>
        <Link
          to="/contracts/$contractId"
          params={{ contractId: String(n.contract_id) }}
          onClick={activate}
          className={`${className} hover:border-brand-dim`}
        >
          {body}
        </Link>
      </li>
    )
  }
  return (
    <li>
      <button type="button" onClick={activate} className={`${className} w-full`}>
        {body}
      </button>
    </li>
  )
}
