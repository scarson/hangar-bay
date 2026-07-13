// ABOUTME: Header identity cluster — login link when anonymous; portrait + name + logout when authenticated.
// ABOUTME: Login is a FULL navigation to the backend redirect, with next=encodeURIComponent(path+search).
import { useLocation } from '@tanstack/react-router'
import { Button, buttonClasses } from '../../../components/Button'
import { useCurrentUser } from '../hooks/useCurrentUser'
import { useLogout } from '../hooks/useLogout'

export function HeaderIdentity() {
  const location = useLocation()
  const { data: user, isPending } = useCurrentUser()
  const logout = useLogout()

  if (isPending) return <div className="ml-auto h-8" aria-hidden="true" />

  if (!user) {
    const next = encodeURIComponent(location.pathname + location.searchStr)
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
