// ABOUTME: Shared auth-gate prompt for the M3 pages — a sign-in card whose login link deep-links back to the current path.
// ABOUTME: Login is a FULL navigation (not an SPA Link) to the backend redirect; next=encoded path+search with ?sso stripped (mirrors HeaderIdentity).
import { useLocation } from '@tanstack/react-router'
import { buttonClasses } from '../../../components/Button'

export function RequireSignIn({ feature }: { feature: string }) {
  const location = useLocation()
  // Strip a transient ?sso=denied|error before baking it into next, or a successful
  // login round-trips the user back to a stale SSO notice (same as HeaderIdentity §4.1).
  const params = new URLSearchParams(location.searchStr)
  params.delete('sso')
  const search = params.toString()
  const next = encodeURIComponent(location.pathname + (search ? `?${search}` : ''))
  return (
    <div className="flex flex-col items-start gap-3 rounded-md border border-line bg-surface px-5 py-8">
      <h2 className="text-base font-medium text-ink">Sign in to use {feature}</h2>
      <p className="max-w-[52ch] text-sm text-ink-dim">
        Log in with your EVE character to view and manage {feature}.
      </p>
      {/* Full navigation (not an SPA route): the browser must leave the app to hit the backend redirect. */}
      <a href={`/api/v1/auth/sso/login?next=${next}`} className={buttonClasses('primary')}>
        Log in with EVE
      </a>
    </div>
  )
}
