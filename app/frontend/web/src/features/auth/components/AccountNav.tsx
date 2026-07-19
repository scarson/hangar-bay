// ABOUTME: Authed-only header nav linking to the saved-searches and watchlist management pages.
// ABOUTME: Hidden entirely while the identity is pending or anonymous, so anonymous users see no dead links.
import { Link } from '@tanstack/react-router'
import { useCurrentUser } from '../hooks/useCurrentUser'

// Header text tokens: dim by default, brighten on hover; the router marks the active route
// with the full-strength ink color via activeProps.
const linkClass = 'text-sm text-ink-dim hover:text-ink'
const activeProps = { className: 'text-ink' }

export function AccountNav() {
  const { data: user, isPending } = useCurrentUser()
  if (isPending || !user) return null
  return (
    <nav aria-label="Account" className="flex items-center gap-3">
      <Link to="/saved-searches" className={linkClass} activeProps={activeProps}>
        Saved searches
      </Link>
      <Link to="/watchlist" className={linkClass} activeProps={activeProps}>
        Watchlist
      </Link>
    </nav>
  )
}
