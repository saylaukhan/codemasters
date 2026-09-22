import { afterEach, describe, expect, it, vi } from 'vitest'

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
  plural,
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

describe('Russian plural of a counted noun', () => {
  const SCHOOLS = ['школа', 'школы', 'школ'] as const

  it('picks the form by the last digits, as the status strip prints it', () => {
    expect(plural(1, SCHOOLS)).toBe('школа')
    expect(plural(21, SCHOOLS)).toBe('школа')
    expect(plural(3, SCHOOLS)).toBe('школы')
    expect(plural(312, SCHOOLS)).toBe('школ')
    expect(plural(0, SCHOOLS)).toBe('школ')
  })

  it('keeps the teens on the third form', () => {
    expect(plural(11, SCHOOLS)).toBe('школ')
    expect(plural(14, SCHOOLS)).toBe('школ')
    expect(plural(112, SCHOOLS)).toBe('школ')
  })

  it('ignores the sign of a delta', () => {
    expect(plural(-2, SCHOOLS)).toBe('школы')
  })
})

/**
 * The language is decided once, at module load (lib/locale.ts), so the Kazakh formatting is
 * checked on a fresh copy of the module with the locale mocked. Dates, numbers and the time
 * zone are the same in both languages; the words of a duration come from Intl (T-66).
 */
describe('Kazakh locale', () => {
  afterEach(() => {
    vi.doUnmock('./locale')
    vi.resetModules()
  })

  const kazakhFormat = async () => {
    vi.resetModules()
    vi.doMock('./locale', () => ({ activeLocale: () => 'kk' }))
    return import('./format')
  }

  it('keeps dates in Asia/Almaty and numbers with the comma', async () => {
    const format = await kazakhFormat()

    expect(format.formatDateTime('2026-09-12T19:30:00Z')).toBe('13.09.2026 00:30')
    expect(format.formatNumber(12480.34)).toBe(`12${NBSP}480,3`)
    expect(format.formatSpeed(45.28)).toBe(`45,3${NBSP}Мбит/с`)
    expect(format.TIME_ZONE).toBe('Asia/Almaty')
  })

  it('says a duration and a relative moment in Kazakh', async () => {
    const format = await kazakhFormat()
    const now = new Date('2026-09-12T12:00:00Z')

    expect(format.formatDuration(4 * 3600 + 12 * 60)).toBe('4 сағ 12 мин')
    expect(format.formatDuration(2 * 86400 + 3 * 3600)).toBe('2 күн 3 сағ')
    expect(format.formatRelative('2026-09-12T11:58:00Z', now)).toBe('2 минут бұрын')
    expect(format.formatRelative('2026-09-12T09:00:00Z', now)).toBe('3 сағат бұрын')
    expect(format.formatRelative(now, now)).toBe('қазір')
    // A Kazakh noun after a numeral keeps its form, so the dictionary's first one is used.
    expect(format.plural(5, ['мектеп', 'мектеп', 'мектеп'])).toBe('мектеп')
  })
})
