// Times of day of the administration (T-37): working hours and schedule slots are local Asia/Almaty times
// without an offset, "HH:MM:SS" in the API (ADR-014). The pickers hold them as Dayjs of today.
import dayjs, { type Dayjs } from 'dayjs'

import type { ScheduleSlot, Weekday, WorkingHours } from '../../api/types'
import { WEEKDAY_ORDER } from '../../lib/labels'

/** A pair of the range picker: start and end of a slot or of the working day. */
export type TimeRange = [Dayjs, Dayjs]

/** "08:30:00" of the API → the picker value. */
export const timeOf = (value: string): Dayjs => {
  const [hour = 0, minute = 0] = value.split(':').map(Number)
  return dayjs().hour(hour).minute(minute).second(0).millisecond(0)
}

/** The picker value → "08:30:00" of the API; seconds are not set in the panel. */
export const clockOf = (value: Dayjs): string => value.format('HH:mm:00')

/** "08:30:00" → "08:30". */
export const shortClock = (value: string): string => value.slice(0, 5)

export const rangeOf = ({ start, end }: { start: string; end: string }): TimeRange => [timeOf(start), timeOf(end)]

export const slotOf = ([start, end]: TimeRange): ScheduleSlot => ({ start: clockOf(start), end: clockOf(end) })

/** Slots of a schedule in one line: «08:30–09:00, 11:00–11:30». */
export const formatSlots = (slots: readonly ScheduleSlot[]): string =>
  slots.map(({ start, end }) => `${shortClock(start)}–${shortClock(end)}`).join(', ')

/** Values of the working-hours fields of a form. */
export interface HoursValues {
  weekdays: Weekday[]
  hours: TimeRange
}

export const hoursValues = (hours: WorkingHours): HoursValues => ({
  weekdays: WEEKDAY_ORDER.filter((day) => hours.weekdays.includes(day)),
  hours: rangeOf(hours),
})

export const hoursOf = ({ weekdays, hours: [start, end] }: HoursValues): WorkingHours => ({
  weekdays: WEEKDAY_ORDER.filter((day) => weekdays.includes(day)),
  start: clockOf(start),
  end: clockOf(end),
})

/** Slots that overlap another one, by index; the API rejects them too (422). */
export function overlappingSlots(slots: readonly ScheduleSlot[]): number[] {
  const order = slots.map((slot, index) => ({ ...slot, index })).sort((a, b) => a.start.localeCompare(b.start))
  const overlapping = new Set<number>()
  order.forEach((slot, position) => {
    const next = order.at(position + 1)
    if (next && next.start < slot.end) {
      overlapping.add(slot.index)
      overlapping.add(next.index)
    }
  })
  return [...overlapping].sort((a, b) => a - b)
}
