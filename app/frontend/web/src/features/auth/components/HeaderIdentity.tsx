// ABOUTME: Header identity cluster — login link when anonymous; portrait + name + logout when authenticated.
// ABOUTME: Login is a FULL navigation to the backend redirect, with next=encodeURIComponent(path+search), sso stripped.
import { useLocation } from '@tanstack/react-router'
import { Button, buttonClasses } from '../../../components/Button'
import { NotificationBell } from '../../notifications/components/NotificationBell'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { useLogout } from '../hooks/useLogout'

export function HeaderIdentity() {
  const location = useLocation()
  const { data: user, isPending } = useCurrentUser()
  const logout = useLogout()

  if (isPending) return <div className="ml-auto h-8" aria-hidden="true" />

  if (!user) {
    // Strip a transient ?sso=denied|error before it gets baked into `next` — otherwise a
    // successful login round-trips the user right back to the stale SSO notice (the
    // param is only ever meant to be read once, by SsoNotice, then dismissed).
    const params = new URLSearchParams(location.searchStr)
    params.delete('sso')
    const search = params.toString()
    const next = encodeURIComponent(location.pathname + (search ? `?${search}` : ''))
    return (
      // Full navigation (not an SPA route): the browser must leave the app to hit the
      // backend redirect. encodeURIComponent keeps a query-bearing next intact (§4.1).
      <a href={`/api/v1/auth/sso/login?next=${next}`} className={buttonClasses('ghost', 'ml-auto')}>
        Log in with EVE
      </a>
    )
  }

  return (
    <div className="ml-auto flex items-center gap-3">
      <NotificationBell />
      <img
        src={`https://images.evetech.net/characters/${user.character_id}/portrait?size=64`}
        alt=""
        width={24}
        height={24}
        className="h-6 w-6 rounded-full"
      />
      <span className="text-ink text-sm">{user.character_name}</span>
      <Button variant="ghost" onClick={() => logout.mutate()} disabled={logout.isPending}>
        Log out
      </Button>
    </div>
  )
}
