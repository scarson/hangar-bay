// ABOUTME: Dismissible ?sso=denied|error notice under the header (polite live region).
// ABOUTME: Reads the RAW search (typed validateSearch drops sso); dismiss replace-strips only that param.
import { useLocation, useRouter } from '@tanstack/react-router'

export function SsoNotice() {
  const location = useLocation()
  const router = useRouter()
  const sso = new URLSearchParams(location.searchStr).get('sso')
  if (sso !== 'denied' && sso !== 'error') return null

  const message =
    sso === 'denied'
      ? 'EVE sign-in was cancelled. You can try again anytime.'
      : 'Something went wrong signing in with EVE. Please try again.'

  const dismiss = () =>
    router.navigate({
      // The notice is mounted at root, so an SSO redirect (and therefore a dismiss) can
      // land on ANY route — the list, a contract detail page, wherever. `to` is the
      // CURRENT pathname (not a hard-coded route) so dismiss stays put instead of
      // falling back to some fixed location. `router.navigate` (not the typed
      // `useNavigate({ from })`) is used deliberately: a hard-coded `from` resolves the
      // search-reducer against ONE route, which silently drops the path segment on any
      // other route (e.g. /contracts/123 -> /contracts). `to: location.pathname` is a
      // plain string, not a literal from the generated route union, so it isn't subject
      // to that per-route resolution at all.
      to: location.pathname,
      // Strip only sso; preserve the rest of the query. Replace so refresh/back
      // and copied links don't re-show the notice (§5). Written delete-style, not
      // rest-destructuring: the repo eslint config reports an unused rest-sibling
      // binding (`_drop`) as @typescript-eslint/no-unused-vars at error level.
      search: (prev) => {
        const rest = { ...(prev as Record<string, unknown>) }
        delete rest.sso
        return rest
      },
      // Preserve any URL fragment (e.g. a deep-linked #anchor): TanStack Router
      // clears the hash on navigate unless it is carried forward explicitly.
      hash: true,
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
