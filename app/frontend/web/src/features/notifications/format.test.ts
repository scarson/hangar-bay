// ABOUTME: timeAgo formats a past ISO timestamp as a coarse relative span; now is injectable for determinism (TEST-3).
import { describe, expect, it } from 'vitest'
import { timeAgo } from './format'

describe('timeAgo', () => {
  const now = Date.parse('2026-07-17T12:00:00Z')
  it('returns "just now" under a minute', () => {
    expect(timeAgo('2026-07-17T11:59:30Z', now)).toBe('just now')
  })
  it('returns minutes, hours, and days', () => {
    expect(timeAgo('2026-07-17T11:30:00Z', now)).toBe('30m ago')
    expect(timeAgo('2026-07-17T09:00:00Z', now)).toBe('3h ago')
    expect(timeAgo('2026-07-14T12:00:00Z', now)).toBe('3d ago')
  })
  it('returns em dash for an unparseable input', () => {
    expect(timeAgo('not-a-date', now)).toBe('—')
  })

  const SECOND = 1_000
  const MINUTE = 60 * SECOND
  const HOUR = 60 * MINUTE
  const DAY = 24 * HOUR
  /** A timestamp `ms` before `now`, so offsets read as durations instead of ISO arithmetic. */
  const ago = (ms: number) => new Date(now - ms).toISOString()

  it('reads a future timestamp as "just now" rather than a negative span', () => {
    // The server stamps created_at; a few seconds of clock skew between it and
    // the browser must not surface as "-1m ago".
    expect(timeAgo(ago(0), now)).toBe('just now')
    expect(timeAgo(ago(-30 * SECOND), now)).toBe('just now')
    expect(timeAgo(ago(-2 * HOUR), now)).toBe('just now')
  })

  it('switches units only on the exact boundary', () => {
    expect(timeAgo(ago(59 * SECOND), now)).toBe('just now')
    expect(timeAgo(ago(MINUTE), now)).toBe('1m ago')
    expect(timeAgo(ago(HOUR - SECOND), now)).toBe('59m ago')
    expect(timeAgo(ago(HOUR), now)).toBe('1h ago')
    expect(timeAgo(ago(DAY - SECOND), now)).toBe('23h ago')
    expect(timeAgo(ago(DAY), now)).toBe('1d ago')
  })

  it('keeps counting in days past a month — there is no coarser bucket', () => {
    // Retention can leave old rows in the list; they read as "90d ago", not as a
    // wrapped or truncated span.
    expect(timeAgo(ago(90 * DAY), now)).toBe('90d ago')
    expect(timeAgo(ago(400 * DAY), now)).toBe('400d ago')
  })
})
