import type { SchoolStatus } from '../../api/types'
import { formatDayMonth } from '../../lib/format'
import { SCHOOL_STATUS_LABELS } from '../../lib/labels'
import styles from './DayStrip.module.css'

export interface DayStripDay {
  /** RFC 3339 date of the day; printed as «DD.MM» in Asia/Almaty by format.ts. */
  date: string
  status: SchoolStatus
}

export interface DayStripProps {
  days: readonly DayStripDay[]
  /**
   * Three captions under the strip, in the order the mockup draws them: the first date, the worst
   * day annotated («2 сен · без связи 3 ч») and «сегодня». Composed by the caller, because only it
   * knows which day was the worst (DESIGN.md §3.27).
   */
  captions?: readonly [string, string, string]
  /** Read out by screen readers, e.g. «Последние 30 дней». */
  label?: string
}

/**
 * Day strip of the school cabinet, DESIGN.md §3.27: one cell per day coloured by the status of
 * that day, 40px tall with a 4px gap (32px on a phone, §9.3). Every cell carries its own title
 * «DD.MM · Норма», so the colour is never the only carrier of the status (DESIGN.md §1, rule 4).
 */
export function DayStrip({ days, captions, label }: DayStripProps) {
  return (
    <div className={styles.strip}>
      <div className={styles.days} role="list" aria-label={label}>
        {days.map((day) => (
          <span
            key={day.date}
            role="listitem"
            className={styles.day}
            data-status={day.status}
            title={`${formatDayMonth(day.date)} · ${SCHOOL_STATUS_LABELS[day.status]}`}
          />
        ))}
      </div>
      {captions && (
        <div className={styles.captions}>
          {captions.map((caption, index) => (
            <span key={index} className={styles.caption}>
              {caption}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
