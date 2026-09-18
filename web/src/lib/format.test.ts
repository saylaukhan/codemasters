import { describe, expect, it } from 'vitest'

import {
  NO_VALUE,
  formatDate,
  formatDateTime,
  formatDuration,
  formatMs,
  formatNumber,
  formatPercent,
  formatRelative,
  formatSpeed,
  formatSpeedPair,
  formatTime,
} from './format'

const NBSP = ' '

describe('dates in Asia/Almaty (UTC+5)', () => {
  // 19:30 UTC on the 12th is already 00:30 on the 13th in Almaty.
  const lateEvening = '2026-09-12T19:30:00Z'

  it('moves the date across midnight', () => {
    expect(formatDate(lateEvening)).toBe('13.09.2026')
    expect(formatTime(lateEvening)).toBe('00:30')
    expect(formatDateTime(lateEvening)).toBe('13.09.2026 00:30')
  })

  it('reads an RFC 3339 offset, not the time zone of the browser', () => {
    expect(formatDateTime('2026-09-12T14:05:00+05:00')).toBe('12.09.2026 14:05')
    expect(formatDateTime('2026-09-12T09:05:00Z')).toBe('12.09.2026 14:05')
  })

  it('shows a dash for an empty or broken value', () => {
    expect(formatDate(null)).toBe(NO_VALUE)
    expect(formatTime(undefined)).toBe(NO_VALUE)
    expect(formatDateTime('not a date')).toBe(NO_VALUE)
  })
})

describe('numbers and units', () => {
  it('uses the decimal comma and a space between thousands', () => {
    expect(formatNumber(45.34)).toBe('45,3')
    expect(formatNumber(12480)).toBe(`12${NBSP}480`)
    expect(formatNumber(Number.NaN)).toBe(NO_VALUE)
  })

  it('keeps the unit next to the number', () => {
    expect(formatSpeed(45.3)).toBe(`45,3${NBSP}Мбит/с`)
    expect(formatMs(18.4)).toBe(`18${NBSP}мс`)
    expect(formatPercent(62)).toBe('62%')
    expect(formatSpeed(null)).toBe(NO_VALUE)
  })

  it('puts a speed next to the contract one', () => {
    expect(formatSpeedPair(18.2, 50)).toBe(`18,2 / 50${NBSP}Мбит/с`)
    expect(formatSpeedPair(null, 50)).toBe(`${NO_VALUE} / 50${NBSP}Мбит/с`)
    expect(formatSpeedPair(18.2, null)).toBe(`18,2${NBSP}Мбит/с`)
    expect(formatSpeedPair(null, null)).toBe(NO_VALUE)
  })
})

describe('durations and relative time', () => {
  it('formats a duration in days, hours and minutes', () => {
    expect(formatDuration(4 * 3600 + 12 * 60)).toBe(`4${NBSP}ч 12${NBSP}мин`)
    expect(formatDuration(51 * 3600)).toBe(`2${NBSP}д 3${NBSP}ч`)
    expect(formatDuration(30)).toBe('меньше минуты')
  })

  it('says how long ago, then falls back to the Almaty date', () => {
    const now = new Date('2026-09-12T10:00:00Z')
    expect(formatRelative('2026-09-12T09:58:00Z', now)).toBe(`2${NBSP}мин назад`)
    expect(formatRelative('2026-09-12T07:00:00Z', now)).toBe(`3${NBSP}ч назад`)
    expect(formatRelative('2026-09-10T20:00:00Z', now)).toBe('11.09.2026')
  })
})
