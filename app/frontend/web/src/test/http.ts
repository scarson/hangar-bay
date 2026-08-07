export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

/**
 * The contract-list envelope for a page with no rows. Tests outside the
 * contracts feature only need the list endpoint to answer something, but the
 * list view reads the whole envelope — a body carrying just items/total is a
 * response the API cannot produce, and stubbing one makes the view fail on a
 * shape it will never actually meet. An unstamped, region-less coverage block
 * is the honest empty case (nothing ingested yet), and needs no fixture date.
 */
export function emptyContractPage(): Record<string, unknown> {
  return {
    total: 0,
    page: 1,
    size: 50,
    items: [],
    segment_counts: { item_exchange: 0, auction: 0, courier: 0, loan: 0, unknown: 0 },
    coverage: { ingested_region_ids: [], as_of: null },
  }
}

// Wrap a fetch handler so /api/v1/me answers 401 (anonymous) by default. The header
// queries /me on every page now; without this, URL-agnostic stubs render a bogus
// authenticated header (name undefined, portrait src .../characters/undefined/...).
export function anonymousMe(handler: (url: string) => Response): (url: string) => Response {
  return (url) => (/\/api\/v1\/me$/.test(url) ? jsonResponse({ detail: 'unauthenticated' }, 401) : handler(url))
}
