import type { ReactNode } from 'react'

import type { SchoolDay } from '../../api/types'
import { formatDayMonth, formatDuration } from '../../lib/format'
import { CABINET_DAY_LABELS, CABINET_LABELS, SCHOOL_STATUS_LABELS } from '../../lib/labels'
import { DayStrip } from '../ui/DayStrip'
import { daySummary, worstDay } from './cabinet'
import styles from './SchoolCabinet.module.css'

interface CabinetDaysProps {
  days: readonly SchoolDay[]
  /** Loading, error or empty state instead of the strip (DESIGN.md §2.7). */
  placeholder?: ReactNode
}

/** «2 сен · без связи 3 ч»: the day the caption under the strip annotates (DESIGN.md §3.27). */
function worstCaption(days: readonly SchoolDay[]): string {
  const worst = worstDay(days)
  if (!worst) return ''
  const what =
    worst.status === 'offline' && worst.downtimeS > 0
      ? `${CABINET_DAY_LABELS.offline} ${formatDuration(worst.downtimeS)}`
      : SCHOOL_STATUS_LABELS[worst.status]
  return `${formatDayMonth(worst.date)} · ${what}`
}

/** Card «Последние 30 дней»: one cell per local day, coloured by the status of that day (T-61). */
export function CabinetDays({ days, placeholder }: CabinetDaysProps) {
  return (
    <section className={styles.card} aria-label={CABINET_LABELS.days}>
      <div className={styles.head}>
        <h2 className={styles.title}>{CABINET_LABELS.days}</h2>
        {!placeholder && <span className={styles.summary}>{daySummary(days).text}</span>}
      </div>
      {placeholder ?? (
        <DayStrip
          days={days}
          label={CABINET_LABELS.days}
          captions={[formatDayMonth(days[0]?.date), worstCaption(days), CABINET_LABELS.today]}
        />
      )}
    </section>
  )
}
