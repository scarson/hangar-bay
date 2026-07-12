# Product

## Register

product

## Users

EVE Online players hunting for ship deals on the public contract market. They are
spreadsheet-loving optimizers: comfortable with dense data, ruthless about speed, allergic to
fluff. Typical context: alt-tabbed out of a dark space game, often at night, mid-decision
("is this Rokh cheap enough to fly it back?"). The job to be done is compare, filter, and
commit — find the right hull at the right price in the right place, fast.

## Product Purpose

Hangar Bay aggregates EVE's public ship contracts (via ESI) into a browsable, filterable,
shareable marketplace view — the contract-browsing experience the in-game client makes tedious.
Success looks like: a player finds a candidate ship in under a minute, trusts the numbers,
and shares a filtered URL with a corpmate. The default view is **ship contracts only**
(per F002 Criterion 1.1); non-ship contracts are reachable by an explicit toggle, never the
default noise.

## Brand Personality

**Precise, fast, quietly sci-fi.** An instrument, not a brochure. The interface should feel
like a well-machined market terminal that happens to live in the EVE universe — confidence
through density done well, restraint everywhere else. Reference lineage: the good third-party
EVE tools (zKillboard's information density, EVE Ref's cleanliness) and terminal-grade market
tooling, not consumer marketplaces.

**Dark-first, by decree.** The primary theme is dark — the audience lives in a dark game, in
dark rooms. An optional light mode may exist as a courtesy, but it is second-class by design;
per the owner: "something is wrong with any EVE player who uses it and sears their eyes."

## Anti-references

- **Generic SaaS dashboard**: cream/sand body backgrounds, hero-metric cards, identical card
  grids, gradient accents. This is a market instrument, not an analytics pitch deck.
- **Consumer storefront**: Amazon/eBay-style merchandising, promotional banners, "deal" badges,
  artificial urgency. The data is the merchandising.
- **CCP/Photon UI cosplay**: evoke spacefaring precision without imitating the EVE client's
  actual chrome. Third-party tools earn trust by being better instruments, not skins.

## Design Principles

1. **Density is respect.** The audience reads tables for fun. Show more per screen than feels
   polite in consumer design; earn it with rigorous alignment, hierarchy, and scan patterns.
2. **The URL is the interface.** Every view state is shareable and restorable; filters, sorts,
   and pages live in the URL. Nothing important hides in ephemeral UI state.
3. **Numbers are the protagonists.** Prices, quantities, time-remaining: tabular figures,
   consistent formatting, ISK always legible. Typography choices serve numerals first.
4. **Fast is a feature.** Perceived speed beats decoration every time; skeletons, cached
   transitions, and zero layout shift. If a flourish costs a frame, cut the flourish.
5. **Quiet sci-fi, loud clarity.** The EVE-ness lives in restraint — spectral accents, dark
   depth, machined edges — never in noise that competes with the data.

## Accessibility & Inclusion

WCAG 2.1 AA per `design/specifications/accessibility-spec.md`: ≥4.5:1 body-text contrast
(hard on dark themes — verify, don't eyeball), full keyboard operability, visible focus,
semantic tables, `prefers-reduced-motion` honored on every animation. Color-blind-safe
signaling: never encode meaning in hue alone (price deltas, contract types get icons/text).
Tooling: eslint-plugin-jsx-a11y (active), vitest-axe assertions on key views (this phase).
