import { createRootRoute, Link, Outlet } from '@tanstack/react-router'
import { AccountNav } from '../features/auth/components/AccountNav'
import { HeaderIdentity } from '../features/auth/components/HeaderIdentity'
import { SsoNotice } from '../features/auth/components/SsoNotice'

export const Route = createRootRoute({
  component: () => (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        {/* flex-wrap so the account nav + identity cluster drop to a second row on narrow
            viewports instead of overflowing and overlapping (the header never wraps at desktop
            widths, where there is ample room). */}
        <div className="mx-auto flex w-full max-w-[1400px] flex-wrap items-baseline gap-3 px-4 py-3 sm:px-6">
          <Link
            to="/contracts"
            className="font-mono text-sm font-semibold tracking-[0.18em] text-ink"
          >
            HANGAR<span className="text-brand">BAY</span>
          </Link>
          <span className="hidden text-meta text-ink-dim sm:inline">
            EVE Online ship contract market
          </span>
          <AccountNav />
          <HeaderIdentity />
        </div>
        <SsoNotice />
      </header>
      <main className="mx-auto w-full max-w-[1400px] flex-1 px-4 py-5 sm:px-6">
        <Outlet />
      </main>
    </div>
  ),
})
