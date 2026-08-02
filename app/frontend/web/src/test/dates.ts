// ABOUTME: Clock-relative timestamp builders for test fixtures, so no fixture date can rot into the past.
// ABOUTME: Use for any field a clock-dependent renderer reads (date_expired -> timeRemaining, created_at -> timeAgo).

/**
 * Wire-format UTC timestamp `days` from now (negative for the past).
 *
 * Fixture dates that feed a clock-dependent renderer MUST be built from the
 * clock, never written as literals. `timeRemaining()` and `timeAgo()` read the
 * real `Date.now()`, so a literal renders one thing the day it is written and
 * something else later — silently, with nothing in the repo changing on the day
 * it flips (testing-pitfalls TEST-17).
 *
 * This is for fixtures only. Assertions on the formatters themselves stay
 * literal-vs-literal by injecting `now` (see src/features/contracts/format.test.ts).
 */
export function daysFromNow(days: number): string {
  return minutesFromNow(days * 1_440)
}

/** Wire-format UTC timestamp `minutes` from now (negative for the past). */
export function minutesFromNow(minutes: number): string {
  return new Date(Date.now() + minutes * 60_000).toISOString().replace(/\.\d{3}Z$/, 'Z')
}
