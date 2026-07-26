// ABOUTME: Pins the document shell's Open Graph / Twitter card tags — the only link-preview
// ABOUTME: metadata a crawler sees, since Discord and friends never execute the SPA's JavaScript.
import { describe, expect, it } from 'vitest'
// Vite's ?raw import keeps this typed via "types": ["vite/client"] — reading the file with
// node:fs instead would drag @types/node into a frontend tsconfig that deliberately lacks it.
import html from '../index.html?raw'

/** Everything Vite will copy verbatim into dist/. Resolved at build time, so a deleted or
 *  renamed file changes this list rather than failing silently at runtime. */
const publicFiles = Object.keys(import.meta.glob('../public/*', { eager: true }))

/** Attribute order inside the tag varies with formatting; match on the pair, not the literal string. */
function metaContent(property: string): string | undefined {
  const pattern = new RegExp(
    `<meta[^>]*(?:property|name)=["']${property.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}["'][^>]*>`,
    'i',
  )
  const tag = html.match(pattern)?.[0]
  return tag?.match(/content=["']([^"']*)["']/i)?.[1]
}

describe('document shell link-preview metadata', () => {
  // Crawlers read only the served HTML. Without these the SPA unfurls as a bare link.
  it.each([
    ['og:title'],
    ['og:description'],
    ['og:image'],
    ['og:type'],
    ['og:site_name'],
    ['twitter:card'],
  ])('declares %s with non-empty content', (property) => {
    expect(metaContent(property), `missing or empty <meta ${property}>`).toBeTruthy()
  })

  it('omits og:url, because every route serves this one shell', () => {
    // Crawlers treat og:url as the embed's canonical link target. This document is served for
    // EVERY route (render.yaml rewrites /* -> /index.html), so any fixed og:url would point
    // shared deep links — /contracts/123 included — back at whatever URL is hardcoded here.
    // Omitting it makes crawlers fall back to the URL they actually requested, which is correct.
    // A per-URL og:url only becomes possible with server-rendered tags.
    expect(metaContent('og:url')).toBeUndefined()
  })

  it('serves og:image from a stable path, never a content-hashed build asset', () => {
    const image = metaContent('og:image')!
    // Vite content-hashes /assets/* on every build and render.yaml serves them immutable for a
    // year. Discord caches embeds by URL at post time, so a hashed image URL silently breaks
    // every previously-posted embed on the next frontend deploy.
    expect(image).not.toMatch(/\/assets\//)
  })

  it('serves og:image as a raster format crawlers actually render', () => {
    // Discord does not render SVG embeds; the existing favicon.svg is not a usable og:image.
    expect(metaContent('og:image')).toMatch(/\.(png|jpe?g|webp)$/i)
  })

  it('actually ships the file og:image points at', () => {
    // Without this, deleting or renaming the card leaves every assertion above green while
    // every embed silently loses its image — and the 404 surfaces nowhere in the app, since
    // Render's SPA rewrite does not cover extensioned paths: /og-card.png just 404s.
    // Deriving the expected path from the tag means renaming EITHER side fails.
    const url = new URL(metaContent('og:image')!)
    expect(publicFiles).toContain(`../public${url.pathname}`)
  })

  it('pins the declared image dimensions to the card that is actually shipped', () => {
    // These two numbers are what crawlers lay the embed out from before fetching the image.
    // They are only meaningful if they match the real file; regenerating the card at another
    // size without updating them yields a mis-sized embed that no other test would catch.
    expect(metaContent('og:image:width')).toBe('1200')
    expect(metaContent('og:image:height')).toBe('630')
  })

  it('declares the exact values crawlers key off, not merely non-empty ones', () => {
    expect(metaContent('og:type')).toBe('website')
    expect(metaContent('og:site_name')).toBe('Hangar Bay')
    expect(metaContent('twitter:card')).toBe('summary_large_image')
  })

  it('carries a plain meta description for crawlers that ignore Open Graph', () => {
    const description = metaContent('description')
    expect(description).toBeTruthy()
    expect(description).toBe(metaContent('og:description'))
  })

  it('gives og:image an absolute URL', () => {
    // Relative og:image URLs are resolved inconsistently across crawlers; several drop them.
    expect(metaContent('og:image')).toMatch(/^https?:\/\//)
  })

  it('parses into real head elements, not just matching text', () => {
    // A regex match proves the characters are present; it does not prove the document parses
    // or that the tags land in <head> where a crawler looks. Malformed markup earlier in the
    // head could push them into <body>, and every regex assertion above would still pass.
    const doc = new DOMParser().parseFromString(html, 'text/html')
    const og = doc.head.querySelectorAll('meta[property^="og:"]')
    expect(og.length).toBeGreaterThanOrEqual(6)
    expect(doc.head.querySelector('meta[property="og:image"]')?.getAttribute('content'))
      .toBe('https://hangarbay.app/og-card.png')
    expect(doc.head.querySelector('meta[name="twitter:card"]')?.getAttribute('content'))
      .toBe('summary_large_image')
    // The omission must hold at the DOM level too — a commented-out tag is not a tag.
    expect(doc.querySelector('meta[property="og:url"]')).toBeNull()
  })

  it('keeps the human-facing title and the preview title in agreement', () => {
    const title = html.match(/<title>([^<]*)<\/title>/i)?.[1]
    expect(title).toBeTruthy()
    expect(metaContent('og:title')).toBe(title)
  })
})
