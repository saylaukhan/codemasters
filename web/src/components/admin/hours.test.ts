import { describe, expect, it } from 'vitest'

import { clockOf, formatSlots, hoursOf, hoursValues, overlappingSlots, timeOf } from './hours'

describe('times of day', () => {
  it('round-trips a time of the API through the picker', () => {
    expect(clockOf(timeOf('08:30:00'))).toBe('08:30:00')
    expect(clockOf(timeOf('18:05'))).toBe('18:05:00')
  })

  it('keeps working hours through the form in the order of the week', () => {
    expect(hoursOf(hoursValues({ weekdays: ['sat', 'mon', 'tue'], start: '08:00:00', end: '18:00:00' }))).toEqual({
      weekdays: ['mon', 'tue', 'sat'],
      start: '08:00:00',
      end: '18:00:00',
    })
  })
})

describe('formatting', () => {
  it('writes slots without seconds', () => {
    expect(
      formatSlots([
        { start: '08:30:00', end: '09:00:00' },
        { start: '11:00:00', end: '11:30:00' },
      ]),
    ).toBe('08:30–09:00, 11:00–11:30')
  })
})

describe('overlappingSlots', () => {
  it('finds the slots that overlap, whatever their order', () => {
    expect(
      overlappingSlots([
        { start: '13:00:00', end: '13:30:00' },
        { start: '08:30:00', end: '09:00:00' },
        { start: '13:15:00', end: '13:45:00' },
      ]),
    ).toEqual([0, 2])
    expect(
      overlappingSlots([
        { start: '08:30:00', end: '09:00:00' },
        { start: '09:00:00', end: '09:30:00' },
      ]),
    ).toEqual([])
  })
})
