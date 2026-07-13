// ABOUTME: Dismissible ?sso=denied|error notice under the header (polite live region).
// ABOUTME: Reads the RAW search (typed validateSearch drops sso); dismiss replace-strips only that param.
import { useLocation, useNavigate } from '@tanstack/react-router'

export function SsoNotice() {
  const location = useLocation()
  // `from` scopes the navigation to /contracts, which is where the notice is always
  // shown (spec §4.1's SSO redirects always land there). It is also required for the
  // types: without it, useNavigate()'s search-reducer resolves against the untyped
  // root route ("never") and `tsc -b` rejects the reducer regardless of the
  // runtime-safe cast below. Since dismiss only ever fires on /contracts, the
  // resolved-path behavior `from` drives matches the current route either way.
  const navigate = useNavigate({ from: '/contracts/' })
  const sso = new URLSearchParams(location.searchStr).get('sso')
  if (sso !== 'denied' && sso !== 'error') return null

  const message =
    sso === 'denied'
      ? 'EVE sign-in was cancelled. You can try again anytime.'
      : 'Something went wrong signing in with EVE. Please try again.'

  const dismiss = () =>
    navigate({
      // Strip only sso; preserve the rest of the query. Replace so refresh/back
      // and copied links don't re-show the notice (§5). Written delete-style, not
      // rest-destructuring: the repo eslint config reports an unused rest-sibling
      // binding (`_drop`) as @typescript-eslint/no-unused-vars at error level.
      search: (prev) => {
        const rest = { ...(prev as Record<string, unknown>) }
        delete rest.sso
        return rest
      },
      replace: true,
    })

  return (
    <div role="status" aria-live="polite" className="mx-auto flex w-full max-w-[1400px] items-center gap-3 px-4 py-2 text-sm text-ink sm:px-6">
      <span>{message}</span>
      <button type="button" onClick={dismiss} aria-label="Dismiss" className="ml-auto rounded px-2 text-ink-dim hover:text-ink">
        ×
      </button>
    </div>
  )
}
