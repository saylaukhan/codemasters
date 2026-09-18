import { Skeleton } from 'antd'

import { NO_VALUE } from '../../lib/format'
import styles from './KpiCard.module.css'

interface KpiCardProps {
  label: string
  /** Already formatted by format.ts. */
  value: string
  unit?: string
  loading?: boolean
}

/** KPI card, DESIGN.md §3.10: caption, large tabular number, unit. */
export function KpiCard({ label, value, unit, loading = false }: KpiCardProps) {
  return (
    <section className={styles.card} aria-label={label}>
      <p className={styles.label}>{label}</p>
      {loading ? (
        <Skeleton.Input active size="small" className={styles.skeleton} />
      ) : (
        <p className={styles.value}>
          <span className={styles.number}>{value}</span>
          {unit && value !== NO_VALUE && <span className={styles.unit}>{unit}</span>}
        </p>
      )}
    </section>
  )
}
