import { createFileRoute, redirect } from '@tanstack/react-router'

export const Route = createFileRoute('/')({
  beforeLoad: () => {
    // Forward the incoming search (e.g. ?sso=error from the state-missing callback
    // exit) — without `search: true` the redirect drops it entirely (§4.1).
    throw redirect({ to: '/contracts', search: true })
  },
})
