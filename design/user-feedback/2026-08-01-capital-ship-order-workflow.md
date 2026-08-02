<!-- ABOUTME: The only direct user feedback Hangar Bay has received — an EVE capital-ship builder describing a -->
<!-- ABOUTME: build-to-order workflow, with technical assessment of his suggestions and the questions sent back. -->

# User feedback: a capital-ship builder

**Received:** before 2026-08-01 (relayed 2026-08-01)
**Source:** direct conversation, in response to Sam asking "would anyone even plausibly use this?"
**Status:** follow-up questions sent 2026-08-02; awaiting reply

## Why this document exists

This is **the only demand-side evidence the project has.** Every argument for the contract-browsing direction, including the [contract-coverage gap analysis](../../docs/superpowers/specs/2026-08-01-contract-coverage-gap-analysis.md) and [F008](../features/F008-Type-Aware-Contract-Browsing.md), is supply-side: we already ingest the data, therefore we should display it. No user has asked for it. One user has asked for something else, and this is that record.

It lived only in a chat log until it was written down here.

## What he said

Asked whether anyone would plausibly use Hangar Bay, he answered that building and selling capital ships is essentially all he does in game, and that he would use it for that. He then described a workflow that is **not** contract browsing:

> His alliance members sign in with EVE SSO, get authorized on the basis of alliance membership, and from there order ships and track status. Order placed on the web, deposit sent in game, deposit verified via ESI, order confirmed.

Sketched as a flow: buyer fills an order form → backend creates an order → buyer sends ISK → backend polls ESI and detects the deposit → order status moves to confirmed → buyer is notified → builder delivers.

His five refinements:

1. Take the deposit as a **direct wallet transfer** rather than a contract, using the transfer's comment field to carry a tracking code.
2. Notify the builders via **Discord webhook**.
3. Notify the buyer of status changes the same way.
4. **Poll for the delivery contract** to move the order to complete automatically.
5. Deliveries land in a station other than Jita IV-4, and **may be in a citadel**, which requires authorization.

## Assessment

### This is a different product

Hangar Bay is a public marketplace browser: read-only, public ESI, no per-user auth in the core loop. What he described is a **build-to-order shop management system** — alliance-gated auth, orders for ships that do not exist yet, deposit verification, status tracking, delivery confirmation.

They share infrastructure — EVE SSO (M2, shipped), ESI polling, PostgreSQL, notifications (M3, shipped) — and almost no product surface.

Read the exchange carefully: he did not say he would browse contracts. He said he would use *it* for *his capital ship business*, and then described something else. That is a redirect, not validation of the current direction.

### One genuine bridge

The gap analysis names **capital-component blueprints** as one of the two largest clusters in the non-ship corpus. A capital builder is exactly the audience for F008's blueprint surface — runs, ME, TE columns and blueprint filtering. So the only real user the project has sits inside the target audience for F008's biggest cluster, even though that is not what he asked for. Whether he would actually use it for sourcing is the single most decision-relevant open question below.

### It justifies a decision that looked shaky

Four permanently-NULL columns (`status`, `date_completed`, `raw_quantity`, `is_singleton`) were approved for removal and then kept, on the grounds that character/corp contract ingestion was likely to matter. This is the player behind that signal, and his flow needs exactly those authenticated routes — his suggestion 4 is character/corp contract polling. See gap analysis §4.2; that reversal was correct.

### Technical assessment of his suggestions

**(1) Right idea, wrong endpoint — and the difference would break an implementation.** Verified against the live ESI spec:

| Route | Relevant fields |
|---|---|
| `/characters/{id}/wallet/journal` | `amount`, **`reason`**, `id`, `first_party_id`, `second_party_id`, `ref_type`, `date`, `context_id` |
| `/characters/{id}/wallet/transactions` | `client_id`, `is_buy`, `type_id`, `unit_price`, `quantity`, `transaction_id` |

He said "transactions have a comments field." **`/wallet/transactions` has no `reason` field** — it covers market fills only. The `reason` field is on `/wallet/journal`, where player-to-player transfers land. Anyone following his wording literally would poll transactions, find nothing, and conclude the design is impossible. The substance of the idea is sound and better than contract-based deposits.

Two things he did not mention:
- The journal entry `id` is the correct idempotency key. **Matching on amount alone is a bug** — two buyers sending 1B ISK collide.
- Corp wallets need `esi-wallet.read_corporation_wallets.v1` plus an Accountant or Director role. That is an onboarding constraint on his side, and it can kill the automatic-verification design outright.

**(2) and (3) Sound, and cheaper than what exists.** A Discord webhook is one unauthenticated POST. Simpler than the email path in F007 and better matched to how alliances communicate.

**(4) This is where it meets the existing pipeline** — and it needs the authenticated character/corp contract routes, the direction already on the roadmap.

**(5) Correct, and he identified a constraint the project has already measured.** Player structures need `esi-universe.read_structures.v1` with ACL access; the [courier spike](../../docs/superpowers/specs/2026-08-01-courier-route-jumps-spike.md) measured ~9–10% of couriers unresolvable for exactly this reason. That he raised it unprompted suggests he knows the API.

**Easier than he would expect:** alliance gating needs no extra scope. Character → corporation → alliance is all public ESI.

**Harder than a browse view:** this is money-adjacent. A false "deposit confirmed" costs someone a billion ISK. That is a materially higher correctness bar than a wrong row in a table.

## Questions sent back (2026-08-02)

1. Still building and selling caps? Is the alliance still who would be ordering?
2. Walk through how an order works today. Which part is most annoying?
3. How many orders a month, and how many people placing them?
4. **Would he use a public contract browser with ME/TE/runs filtering to source capital component BPCs, or does he get those another way?**
5. Deposit tracking needs read access to whichever wallet receives the ISK. If that is a corp wallet, someone with Accountant has to authorize. Realistic or a non-starter?
6. Where are finished ships handed over — station or citadel?

**Q4 is the decisive one.** If yes, F008 and his request converge and the current direction is validated by the only user who has expressed one. If no, they are two products competing for the same time, and the choice should be made deliberately rather than by momentum.

**Q5 can kill the design.** No director authorization means no automatic deposit verification, and the flow degrades to manual confirmation.

**Q2 and Q3 test whether the pain is real.** Three orders a month in a spreadsheet does not need a web application.

## What this does not establish

One player in one alliance is not product-market fit, and this feedback predates its relay by an unknown interval. It is recorded because it is the only signal of its kind, not because it settles anything.
