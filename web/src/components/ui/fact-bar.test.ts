import { describe, expect, it } from 'vitest'

import { factBarGeometry } from './fact-bar'

describe('geometry of the bar «fact against the threshold»', () => {
  it('places the fill and both ticks on the track', () => {
    // Download 45,3 against a norm of 20 and a contract of 50, read on a scale of 60.
    expect(factBarGeometry({ value: 45.3, scale: 60, threshold: 20, contract: 50 })).toEqual({
      fillPct: 75.5,
      thresholdPct: expect.closeTo(33.33, 2),
      contractPct: expect.closeTo(83.33, 2),
    })
  })

  it('clamps a value above the scale instead of overflowing the card', () => {
    expect(factBarGeometry({ value: 180, scale: 60 }).fillPct).toBe(100)
    expect(factBarGeometry({ value: -5, scale: 60 }).fillPct).toBe(0)
    expect(factBarGeometry({ value: 90, scale: 60, threshold: 100 }).thresholdPct).toBe(100)
  })

  it('draws no tick without a threshold or a contract', () => {
    // Ping has a norm but no contract (DESIGN.md §3.27).
    const ping = factBarGeometry({ value: 27, scale: 100, threshold: 100 })
    expect(ping.contractPct).toBeNull()
    expect(ping.thresholdPct).toBe(100)

    const bare = factBarGeometry({ value: 27, scale: 100 })
    expect(bare.thresholdPct).toBeNull()
    expect(bare.contractPct).toBeNull()
  })

  it('shows an empty track when there is no measurement or no scale', () => {
    expect(factBarGeometry({ value: null, scale: 60 }).fillPct).toBe(0)
    expect(factBarGeometry({ value: 45, scale: 0, threshold: 20 })).toEqual({
      fillPct: 0,
      thresholdPct: null,
      contractPct: null,
    })
  })
})
