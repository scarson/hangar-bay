# Expired Contracts Are Served As Browsable Results

ABOUTME: Production finding — ~12% of served contracts have already expired, and the natural "expiring soonest" sort surfaces them first.
ABOUTME: Discovered 2026-07-26 while scoping the trust & shareability milestone; measured against live production, not inferred.

## The finding

Nothing removes a contract once it leaves ESI's public list or passes its expiry, and the browse query never filters on expiry. `services/background_aggregation.py` has no prune or delete path for contracts, and `services/contract_service.py` references `date_expired` only as a **sortable field** — there is no `WHERE date_expired > now()` anywhere in the list path.

Measured against production on 2026-07-26:

- **51,365** contracts served in total
- **~6,200 already expired and still browsable — ~12% of the dataset**
- Oldest expiry still served: **2026-07-21T09:16:09Z** (five days stale)

Method: binary search over pages of `/api/v1/contracts/?sort_by=date_expired&sort_direction=asc&size=100`, comparing each page's first `date_expired` against now. Crossover near page 63 of 514.

## Why it matters, stated accurately

This is **not** a case of the UI lying. `format.ts`'s `timeRemaining()` returns the string `'Expired'` for any past date, and that renders in the table's "Time left" column and on the detail page. A user looking at a specific row can see its state.

The damage is relevance, and it is concentrated in one very natural path:

- `ContractsPage.tsx`'s `DEFAULT_DIRECTION` maps `date_expired: 'asc'`, so **clicking the "Time left" column — the obvious "what's expiring soonest?" move for a deal hunter — sorts expired contracts to the top.** Verified: 20 of 20 results on that page are dead.
- In any unsorted result set, roughly 1 in 8 rows is a contract that cannot be accepted.
- The `total` count (51,365) overstates what is actually available, and pagination walks the user through the dead rows.

For a product whose stated success criterion is that a user "finds a candidate ship in under a minute and **trusts the numbers**", a default view where an eighth of the rows are unavailable — and where the most natural sort returns nothing else — undercuts precisely the thing the product sells.

## The `status` field is a separate, smaller instance of the same theme

`Contract.status` is populated as `c.get("status", "unknown")` (`background_aggregation.py:108`) and is **always** the literal `"unknown"`, because ESI's *public* contracts route returns no status field — that exists only on character/corp contract routes. Verified against production: every row in a 100-item sample has `status: "unknown"`.

The frontend never reads it (a grep for `.status` in the SPA finds only HTTP error statuses). It is dead weight in the API response and in the `ix_contracts_type_status` index.

## Recommended direction (for the trust & shareability design)

1. **Exclude expired contracts from list results by default** — a `date_expired > now()` predicate in the list query. This also corrects `total`.
2. **Keep serving expired contracts on the detail page, clearly marked** — do not 404 them. This is load-bearing for link previews: a link pasted into Discord will routinely be clicked *after* the contract expires, and the preview and page must say so honestly rather than 404 or, worse, present it as available.
3. **Stop exposing `status`** in the API response, since it carries no information. Removing the field is an OpenAPI change requiring a client regeneration; both sides are ours.

Deliberately **not** recommended here: deleting expired rows. Filtering fixes correctness without losing history, and deletion interacts with saved searches and notifications that may reference those contracts.

## Related follow-up, out of scope

Expired contracts accumulate with no prune path, so the table grows without bound — 51k after roughly a week of ingestion, on a `basic-256mb` Postgres. Filtering at query time does not address storage growth. A retention policy deserves its own decision (there is precedent: `NOTIFICATION_RETENTION_DAYS` already prunes notifications).
