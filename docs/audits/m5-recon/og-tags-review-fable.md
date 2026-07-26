# Adversarial review — OG / link-preview tags (`claude/m5-og-tags`)

Reviewer: Fable (adversarial pass), 2026-07-26.
Scope: `git diff origin/dev` on `/Users/sam/Code/hangar-bay/.claude/worktrees/m5-og-tags/` — `app/frontend/web/index.html` (+20), `app/frontend/web/public/og-card.png` (new, 4,367 bytes), `app/frontend/web/src/index-html.test.ts` (new, 12 tests).

Verification actually performed (not assumed): ran the vitest file (12/12 pass), `npx eslint` on the test (clean), full `npm run build` (clean; inspected `dist/`), decoded the PNG header (1200x630, 8-bit RGB), and live-probed production: `curl -I` against `https://hangarbay.app/` , `/index.html`, `/contracts`, `/favicon.svg`, `/og-card.png`.

## Verdict

No BLOCKER. One MAJOR (a test gap whose failure mode is silent). Several MINOR. The core design decisions — tag set, `og:url` omission, `public/` placement — are correct.

---

## MAJOR

### M1. Nothing couples `og:image` to the asset actually shipped — the exact failure the PR exists to prevent is untested

Every test asserts against the *string* `https://hangarbay.app/og-card.png` in `index.html`. No test asserts that `public/og-card.png` exists, is a PNG, or is 1200x630. Delete or rename the file (a plausible future `public/` cleanup — it sits next to `favicon.svg`) and all 12 tests, eslint, tsc, and the full CI frontend lane stay green while every embed silently loses its image.

The failure is doubly silent in production: live probe shows Render's `/* -> /index.html` rewrite does **not** apply to extensioned paths — `GET https://hangarbay.app/og-card.png` today returns `404 text/plain`, not the SPA shell. Nothing in the app or suite would ever notice; only a pasted Discord link would.

Same gap, smaller blast radius: `og:image:width`/`og:image:height` declare 1200/630. I verified the binary is exactly 1200x630 today, but nothing keeps the declaration honest if the card is regenerated at different dimensions (crawlers lay the embed out from the declared dims before/without sniffing).

**Fix:** an e2e fixture-lane check is the clean shape — request `/og-card.png` from the Vite dev server, assert 200 + `content-type: image/png` (and, cheaply, read the IHDR bytes for 1200x630 and compare against the declared meta values). A vitest/node alternative works too but collides with the app tsconfig's deliberate lack of node types (`"types": ["vite/client"]`); e2e already runs under a node-typed config.

---

## MINOR

### m2. Overstated comment claim: "a hashed URL would break every embed already posted"

(`index.html` comment, duplicated in the test.) Discord proxies embed images through `media.discordapp.net` and serves already-posted embeds from that cache; most existing Discord embeds *survive* the origin 404ing a hashed URL. What actually breaks: re-fetches on cache expiry, re-shares, and platforms that revalidate (Slack, iMessage, X). The conclusion — stable `public/` path — is right; the absolute "every embed" is wrong. Per the verify-mechanism-before-writing-claims rule, soften to "breaks embeds as caches expire and on every re-share."

### m3. The 8-line internal comment ships to production

Verified: `dist/index.html` after `npm run build` contains the full "og:url is deliberately absent… render.yaml serves it immutable…" comment. Vite does not strip HTML comments. That's ~0.7 KB of internal architecture discussion delivered on every page load of a document served `max-age=0`, and the same reasoning already lives (better) in the test file. Consider trimming the shipped comment to one line and letting the test carry the essay.

### m4. `metaContent` extraction is fragile against apostrophes, and most tag *values* are never pinned

`content=["']([^"']*)["']` stops at the first `'` inside double-quoted content. No current value contains one, but a future description like "your corp's hangar" would silently truncate — the `.each` truthiness tests still pass on the fragment. Separately, only `og:image`, `twitter:card`, and `og:title` have their values asserted; `og:type` could become `content="webiste"` and the suite stays green. Cheap fix: pin `og:type === 'website'` and use `content="([^"]*)"|content='([^']*)'` alternation.

### m5. The new `meta name="description"` is untested

The diff adds the plain SEO description tag; the `.each` list covers only `og:*`/`twitter:*`. Add `['description']` to the list (the helper already matches `name=`).

### m6. Source-vs-served gap: tests pin `index.html`, crawlers get `dist/index.html`

Today's build passes the tags through verbatim (verified: 11 `og:` occurrences in `dist/index.html`). But any future `transformIndexHtml` plugin could rewrite the head with the suite green. Low likelihood; the e2e check from M1 would incidentally close it, since the dev server serves the transformed document. The `?raw` import itself is robust — if `index.html` moves, module resolution fails loudly at transform time; it cannot go stale silently.

### m7. X/Twitter alt text likely dropped

X's documented og fallbacks cover `twitter:title ← og:title`, `description`, and `image` — not `image:alt`. If alt text on X matters, add `<meta name="twitter:image:alt" …>`. Cosmetic; Discord/Slack ignore alt anyway.

---

## Sound (checked, no defect)

- **Tag set completeness (Q1).** `og:title`/`og:description`/`og:type`/`og:site_name`/`og:image` (+ `type`/`width`/`height`/`alt`) + `twitter:card: summary_large_image` is exactly what Discord, Slack, and iMessage read; X falls back to the og tags for title/description/image. The pre-existing `theme-color: #0d1211` doubles as Discord's embed accent strip. Nothing missing that these crawlers need; nothing redundant. `charset` precedes the tags; head is tiny (crawler byte-limits irrelevant).
- **`og:url` omission (Q2).** The author's reasoning is correct, and stronger than stated: besides Discord repointing every deep-link embed's click target at whatever fixed URL was hardcoded, Facebook-family crawlers treat `og:url` as *canonical* and read metadata against it, collapsing all deep-link shares onto one object. With it absent, crawlers use the requested URL — the desired behavior for a one-shell SPA. Only downside missed: the OGP spec nominally lists `og:url` as required, so validators (FB Sharing Debugger, opengraph.xyz) will emit a warning. Cosmetic; every real crawler tolerates the omission. Correct call for the static stage.
- **Image constraints (Q3).** Verified binary: PNG, 1200x630 (1.91:1), 8-bit RGB, 4.4 KB — inside every platform limit (Discord ≤8 MB, X `summary_large_image` ≥300x157 and ≤5 MB, iMessage fine). Absolute https URL on the apex the site owns.
- **Caching / `render.yaml` interaction (Q3, Q5).** Live-probed: files beat the `/* -> /index.html` rewrite (`/favicon.svg` serves as `image/svg+xml` on prod today), so `og-card.png` will serve, and un-ruled `public/` files get Render's default `cache-control: public, max-age=0, s-maxage=300` — sensible for a stable-URL embed image (a redesigned card propagates within ~5 min; no immutable trap). The comment's claim that `render.yaml` serves `/assets/*` `immutable` for a year is accurate (`headers` block, `max-age=31536000, immutable`), and the `public/`-not-`/assets/` decision is right (modulo m2's overstatement).
- **Deploy-time (Q5).** Build verified clean; `dist/og-card.png` present; no route/header conflict; CI's `changes` classifier routes `app/frontend/web/*` (including `public/` and `index.html`) into the frontend lane, which runs the new test; the only e2e touching titles asserts the *dynamic* `document.title` (`useDocumentTitle`), unaffected by static-head changes. Pre-existing observation, not this PR: the `path: /index.html` `no-cache` header matches only literal `/index.html` requests — SPA-rewritten routes serve `s-maxage=300` (live-probed on `/contracts`), so embeds go live at most ~5 min after the dev→main release. Post-release, paste a link in Discord once: prod sits behind Cloudflare (`server: cloudflare` on every probe), and an aggressive bot-mitigation setting there could block Discordbot — unverifiable from the repo.
- **Comment fact-check (Q6).** "`types": ["vite/client"]` / no node types in the app tsconfig" — verified true (`tsconfig.app.json`; `@types/node` exists only for the node-side config). "Discord does not render SVG embeds" — true. "Relative og:image URLs resolved inconsistently / dropped" — true (Discord and WhatsApp historically drop them). "Crawlers never run the SPA's JavaScript" — true for Discord/Slack/iMessage. The one false-leaning claim is m2.
- **Test mechanics (Q4).** jsdom env is configured (`vite.config.ts`), so `DOMParser` exists; vitest's default include picks up `src/index-html.test.ts`; 12/12 pass. Mutation-adequacy spot-check: deleting a tag, emptying content, an `/assets/` URL, an `.svg` image, a relative URL, and head-breaking markup each fail at least one assertion. The DOMParser test is genuinely load-bearing (regexes can't see a prematurely-closed head) and its ≥6 threshold plus exact-value pins are non-vacuous. The suite's one real hole is M1.

## Recommended before merge

1. M1 — add the asset-existence/content-type check (e2e fixture lane is the natural home).
2. m2 — soften the "every embed" claim in both the HTML comment and the test comment.
3. m4/m5 — pin `og:type`'s value, add `description` to the `.each` list (two-line change).

m3, m6, m7 are judgment calls; none blocks.

Sources consulted for crawler behavior: [Discord link preview meta tags overview](https://wildandfreetools.com/blog/discord-open-graph-meta-tags/), [Share Preview: Discord embeds](https://share-preview.com/blog/discord-embed), [PreviewOG: Discord link previews](https://previewog.com/discord-link-preview/), plus live probes of `hangarbay.app` recorded above.
