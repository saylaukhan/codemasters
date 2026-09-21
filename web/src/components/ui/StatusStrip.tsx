import type { ReactNode } from 'react'
import { Link } from 'react-router'

import type { QualityStatus } from '../../api/types'
import { formatNumber, plural } from '../../lib/format'
import { DAY_DELTA_LABELS, SCHOOL_COUNT_FORMS, SCHOOL_STATUS_LABELS } from '../../lib/labels'
import styles from './StatusStrip.module.css'

export interface StatusStripItem {
  /** One of the four quality statuses (ТЗ п. 13); «Нет данных» is not one of them (ADR-004). */
  status: QualityStatus
  count: number
  /** Where the column leads: the list of schools filtered by this status (DESIGN.md §3.10). */
  href: string
  /** Change over the last day; `0` prints «без изменений», `null` prints nothing. */
  delta?: number | null
}

export interface StatusStripProps {
  items: readonly StatusStripItem[]
  /** Read out by screen readers, e.g. «Школы по статусу». */
  label?: string
  /** Display-only «Нет данных» line under the columns; the caller composes it from labels.ts. */
  footnote?: ReactNode
}

/** «▲ 3 за сутки», «▼ 5 за сутки», «без изменений» — the arrows live in labels.ts (ADR-013). */
function deltaText(delta: number): string {
  if (delta === 0) return DAY_DELTA_LABELS.none
  const arrow = delta > 0 ? DAY_DELTA_LABELS.up : DAY_DELTA_LABELS.down
  return `${arrow} ${formatNumber(Math.abs(delta), 0)} ${DAY_DELTA_LABELS.period}`
}

/** More schools in a good status is good news; in a bad one it is bad news (DESIGN.md §3.10). */
function deltaTone(status: QualityStatus, delta: number): 'good' | 'bad' | 'neutral' {
  if (delta === 0) return 'neutral'
  const better = status === 'normal' ? delta > 0 : delta < 0
  return better ? 'good' : 'bad'
}

/**
 * Status strip of the main screen, DESIGN.md §3.10 and §3.28: four columns — dot, caption, count
 * 30/600 with its counted noun, and the change over the last day. The whole column is a link to
 * the list of schools with that status; at 1024px and narrower the four become 2 × 2 (§9.3).
 */
export function StatusStrip({ items, label, footnote }: StatusStripProps) {
  return (
    <div className={styles.strip}>
      <div className={styles.columns} role="group" aria-label={label}>
        {items.map((item) => (
          <Link key={item.status} to={item.href} className={styles.column} data-status={item.status}>
            <span className={styles.caption}>
              <span className={styles.dot} aria-hidden />
              <span className={styles.captionText}>{SCHOOL_STATUS_LABELS[item.status]}</span>
            </span>
            <span className={styles.figure}>
              <span className={styles.count}>{formatNumber(item.count, 0)}</span>
              <span className={styles.unit}>{plural(item.count, SCHOOL_COUNT_FORMS)}</span>
            </span>
            {item.delta != null && (
              <span className={styles.delta} data-tone={deltaTone(item.status, item.delta)}>
                {deltaText(item.delta)}
              </span>
            )}
          </Link>
        ))}
      </div>
      {footnote && <p className={styles.footnote}>{footnote}</p>}
    </div>
  )
}
