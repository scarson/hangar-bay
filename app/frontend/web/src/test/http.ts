export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// Wrap a fetch handler so /api/v1/me answers 401 (anonymous) by default. The header
// queries /me on every page now; without this, URL-agnostic stubs render a bogus
// authenticated header (name undefined, portrait src .../characters/undefined/...).
export function anonymousMe(handler: (url: string) => Response): (url: string) => Response {
  return (url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauthenticated' }, 401) : handler(url))
}
