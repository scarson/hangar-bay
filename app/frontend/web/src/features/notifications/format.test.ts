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
})
