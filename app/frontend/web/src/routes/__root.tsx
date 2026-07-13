import { createRootRoute, Link, Outlet } from '@tanstack/react-router'
import { HeaderIdentity } from '../features/auth/components/HeaderIdentity'
import { SsoNotice } from '../features/auth/components/SsoNotice'

export const Route = createRootRoute({
  component: () => (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex w-full max-w-[1400px] items-baseline gap-3 px-4 py-3 sm:px-6">
          <Link
            to="/contracts"
            className="font-mono text-sm font-semibold tracking-[0.18em] text-ink"
          >
            HANGAR<span className="text-brand">BAY</span>
          </Link>
          <span className="hidden text-meta text-ink-dim sm:inline">
            EVE Online ship contract market
          </span>
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
