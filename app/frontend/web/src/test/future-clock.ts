// ABOUTME: Extra vitest setup for the future-clock lane — runs the suite with Date moved a year+ ahead.
// ABOUTME: Loaded only by vitest.future-clock.config.ts, which computes the instant and passes it in.
import { beforeEach, vi } from 'vitest'

// The instant comes from the config (one value shared by every worker, logged once,
// overridable via HB_FUTURE_CLOCK for a reproducible re-run). If it did not arrive,
// fail loudly: a lane that silently falls back to the real clock is a guard that
// reports green while testing nothing, which is worse than not having the lane.
const simulated = import.meta.env.HB_FUTURE_CLOCK
if (typeof simulated !== 'string' || Number.isNaN(Date.parse(simulated))) {
  throw new Error(
    `future-clock lane: HB_FUTURE_CLOCK missing or unparseable (got ${JSON.stringify(simulated)}). ` +
      'Run this lane through vitest.future-clock.config.ts, which sets it.',
  )
}

// Only Date is faked. Faking the timer functions too would change how the suite
// schedules work, so a failure could mean "the fixtures rotted" or "the timers
// behaved differently" and the lane would not tell you which.
const options = { toFake: ['Date'] as const, now: new Date(simulated) }

// Installed at module scope so module-level fixture constants — evaluated when the
// test file is imported, which happens after setup files run — are built from the
// simulated clock too.
vi.useFakeTimers({ ...options, toFake: [...options.toFake] })

// Re-installed per test because a test that calls vi.useRealTimers() in its own
// cleanup would otherwise hand the rest of its file back to the real clock.
beforeEach(() => {
  vi.useFakeTimers({ ...options, toFake: [...options.toFake] })
})
