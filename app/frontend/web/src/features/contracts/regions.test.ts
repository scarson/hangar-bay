import { describe, expect, it } from 'vitest'
import { REGIONS } from './regions'

describe('static region map', () => {
  it('contains The Forge with its canonical id', () => {
    expect(REGIONS.find((r) => r.name === 'The Forge')?.id).toBe(10000002)
  })

  it('is sorted by name and k-space only', () => {
    const names = REGIONS.map((r) => r.name)
    expect(names).toEqual([...names].sort((a, b) => a.localeCompare(b)))
    expect(REGIONS.every((r) => r.id < 11000000)).toBe(true)
  })
})
