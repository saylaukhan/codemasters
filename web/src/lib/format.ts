// Numbers, units, dates and durations for the panel (ADR-014, DESIGN.md §5): the API speaks
// RFC 3339 in UTC, the panel shows Asia/Almaty. The only place in web/ that formats them.

export const TIME_ZONE = 'Asia/Almaty'
export const NO_VALUE = '—'

const LOCALE = 'ru-RU'
// Non-breaking space: «45,3 Мбит/с» never wraps between the number and the unit.
const NBSP = ' '

const dateFormat = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
})

const timeFormat = new Intl.DateTimeFormat(LOCALE, {
  timeZone: TIME_ZONE,
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

const numberFormats = new Map<number, Intl.NumberFormat>()

function numberFormat(fractionDigits: number): Intl.NumberFormat {
  let format = numberFormats.get(fractionDigits)
  if (!format) {
    format = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: fractionDigits })
    numberFormats.set(fractionDigits, format)
  }
  return format
}

type DateInput = string | number | Date | null | undefined

function toDate(value: DateInput): Date | null {
  if (value === null || value === undefined || value === '') return null
  const date = value instanceof Date ? value : new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

/** «12.09.2026» in Asia/Almaty. */
export function formatDate(value: DateInput): string {
  const date = toDate(value)
  return date ? dateFormat.format(date) : NO_VALUE
}

/** «14:05» in Asia/Almaty. */
export function formatTime(value: DateInput): string {
  const date = toDate(value)
  return date ? timeFormat.format(date) : NO_VALUE
}

/** «12.09.2026 14:05» in Asia/Almaty. */
export function formatDateTime(value: DateInput): string {
  const date = toDate(value)
  return date ? `${dateFormat.format(date)} ${timeFormat.format(date)}` : NO_VALUE
}

/** «45,3», «12 480»; at most `fractionDigits` digits after the comma. */
export function formatNumber(value: number | null | undefined, fractionDigits = 1): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return NO_VALUE
  return numberFormat(fractionDigits).format(value)
}

const withUnit = (value: number | null | undefined, unit: string, fractionDigits: number): string => {
  const number = formatNumber(value, fractionDigits)
  return number === NO_VALUE ? NO_VALUE : `${number}${NBSP}${unit}`
}

export const SPEED_UNIT = 'Мбит/с'
export const MS_UNIT = 'мс'

/** «45,3 Мбит/с». */
export const formatSpeed = (mbps: number | null | undefined): string => withUnit(mbps, SPEED_UNIT, 1)

/** «18,2 / 50 Мбит/с»: a speed next to the one it is compared with; without the second — «18,2 Мбит/с». */
export function formatSpeedPair(value: number | null | undefined, reference: number | null | undefined): string {
  if (reference === null || reference === undefined || !Number.isFinite(reference)) return formatSpeed(value)
  return `${formatNumber(value, 1)} / ${formatSpeed(reference)}`
}

/** «18 мс». */
export const formatMs = (ms: number | null | undefined): string => withUnit(ms, MS_UNIT, 0)

/** «62%», «0,4%». */
export function formatPercent(value: number | null | undefined, fractionDigits = 1): string {
  const number = formatNumber(value, fractionDigits)
  return number === NO_VALUE ? NO_VALUE : `${number}%`
}

/** «4 ч 12 мин», «2 д 3 ч», «15 мин»; less than a minute is «меньше минуты». */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) {
    return NO_VALUE
  }
  const minutes = Math.floor(seconds / 60)
  if (minutes < 1) return 'меньше минуты'
  const days = Math.floor(minutes / 1440)
  const hours = Math.floor((minutes % 1440) / 60)
  const rest = minutes % 60
  if (days > 0) return hours > 0 ? `${days}${NBSP}д ${hours}${NBSP}ч` : `${days}${NBSP}д`
  if (hours > 0) return rest > 0 ? `${hours}${NBSP}ч ${rest}${NBSP}мин` : `${hours}${NBSP}ч`
  return `${rest}${NBSP}мин`
}

/** «только что», «2 мин назад», «3 ч назад»; older than a day — the date in Asia/Almaty. */
export function formatRelative(value: DateInput, now: Date = new Date()): string {
  const date = toDate(value)
  if (!date) return NO_VALUE
  const minutes = Math.floor((now.getTime() - date.getTime()) / 60_000)
  if (minutes < 1) return 'только что'
  if (minutes < 60) return `${minutes}${NBSP}мин назад`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}${NBSP}ч назад`
  return formatDate(date)
}
