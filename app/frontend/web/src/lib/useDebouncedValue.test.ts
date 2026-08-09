// ABOUTME: Unit tests for the trailing-edge debounce behind the contracts search box.
// ABOUTME: Fake timers throughout — a sleep-based test here would be the flake TEST-2 forbids.
import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { useDebouncedValue } from './useDebouncedValue'

const DELAY = 300

describe('useDebouncedValue', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns the first value immediately, so a cold load waits for nothing', () => {
    const { result } = renderHook(() => useDebouncedValue('rifter', DELAY))
    expect(result.current).toBe('rifter')
  })

  it('withholds a changed value until it has held still for the whole delay', () => {
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, DELAY), {
      initialProps: { value: 'a' },
    })

    rerender({ value: 'ab' })
    expect(result.current).toBe('a')

    // One tick short of the window: still the old value. The boundary is the point.
    act(() => {
      vi.advanceTimersByTime(DELAY - 1)
    })
    expect(result.current).toBe('a')

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(result.current).toBe('ab')
  })

  it('restarts the window on every change, so continuous typing never settles mid-word', () => {
    // This is the property the effect's clearTimeout cleanup exists for, and the one
    // no test at any level asserted. Without it the FIRST keystroke's timer survives
    // and publishes a stale prefix mid-word — which downstream is a corpus-scale
    // request under text the reader has already moved past.
    const { result, rerender } = renderHook(({ value }) => useDebouncedValue(value, DELAY), {
      initialProps: { value: 'a' },
    })

    for (const value of ['ab', 'abc', 'abcd']) {
      rerender({ value })
      act(() => {
        vi.advanceTimersByTime(DELAY - 1)
      })
      expect(result.current).toBe('a')
    }

    // Only once typing actually stops does the LATEST value land — never a prefix.
    act(() => {
      vi.advanceTimersByTime(DELAY)
    })
    expect(result.current).toBe('abcd')
  })

  it('re-arms against the new delay when ONLY delayMs changes', () => {
    // delayMs has to be in the effect's dependencies. Changing the value at the same
    // time would re-run the effect anyway and prove nothing about delayMs — so this
    // holds the value fixed and moves only the delay, mid-window.
    const { result, rerender } = renderHook(
      ({ value, delay }) => useDebouncedValue(value, delay),
      { initialProps: { value: 'a', delay: DELAY } },
    )

    rerender({ value: 'ab', delay: DELAY })
    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(result.current).toBe('a')

    // Same value, longer delay: the pending 300ms timer must be replaced, not left
    // to fire on its old schedule.
    rerender({ value: 'ab', delay: 1000 })
    act(() => {
      vi.advanceTimersByTime(250)
    })
    // 350ms of wall time has passed — past the ORIGINAL window, inside the new one.
    expect(result.current).toBe('a')

    act(() => {
      vi.advanceTimersByTime(750)
    })
    expect(result.current).toBe('ab')
  })

  it('drops its pending timer on unmount', () => {
    const { rerender, unmount } = renderHook(({ value }) => useDebouncedValue(value, DELAY), {
      initialProps: { value: 'a' },
    })
    rerender({ value: 'ab' })
    expect(vi.getTimerCount()).toBe(1) // armed, so the assertion below is not vacuous
    unmount()

    // Checked IMMEDIATELY: advancing first would let the timer fire and remove
    // itself, after which React silently swallows the post-unmount state update and
    // the count reads 0 whether or not the cleanup ran at all.
    expect(vi.getTimerCount()).toBe(0)
  })
})
