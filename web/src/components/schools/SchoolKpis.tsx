import type { LatestMeasurement } from '../../api/types'
import { MS_UNIT, SPEED_UNIT, formatNumber } from '../../lib/format'
import { KpiCard } from '../overview/KpiCard'
import styles from './SchoolCard.module.css'

type Metric = number | null | undefined

const below = (value: Metric, min: Metric): boolean => value != null && min != null && value < min
const above = (value: Metric, max: Metric): boolean => value != null && max != null && value > max

interface SchoolKpisProps {
  /** Last measurement of the main line without Wi-Fi; red — worse than the thresholds it was judged by. */
  latest: LatestMeasurement | null | undefined
  availabilityPct?: Metric
  availabilityMinPct?: Metric
  /** «7 дней» — the period the availability is counted over; without it there is no availability card. */
  periodLabel?: string
  loading: boolean
}

/** KPI row of the school and device cards (DESIGN.md §3.15): current values and availability for the period. */
export function SchoolKpis({ latest, availabilityPct, availabilityMinPct, periodLabel, loading }: SchoolKpisProps) {
  const limits = latest?.thresholdsSnapshot
  const cards = [
    {
      label: 'Download',
      value: formatNumber(latest?.downloadMbps),
      unit: SPEED_UNIT,
      alert: below(latest?.downloadMbps, limits?.downloadMinMbps),
    },
    {
      label: 'Upload',
      value: formatNumber(latest?.uploadMbps),
      unit: SPEED_UNIT,
      alert: below(latest?.uploadMbps, limits?.uploadMinMbps),
    },
    {
      label: 'Ping',
      value: formatNumber(latest?.pingMs, 0),
      unit: MS_UNIT,
      alert: above(latest?.pingMs, limits?.pingMaxMs),
    },
    {
      label: 'Jitter',
      value: formatNumber(latest?.jitterMs, 0),
      unit: MS_UNIT,
      alert: above(latest?.jitterMs, limits?.jitterMaxMs),
    },
    {
      label: 'Packet Loss',
      value: formatNumber(latest?.packetLossPct),
      unit: '%',
      alert: above(latest?.packetLossPct, limits?.packetLossMaxPct),
    },
  ]
  if (periodLabel) {
    cards.push({
      label: `Доступность · ${periodLabel}`,
      value: formatNumber(availabilityPct),
      unit: '%',
      alert: below(availabilityPct, availabilityMinPct),
    })
  }
  return (
    <div className={styles.kpis}>
      {cards.map((card) => (
        <KpiCard key={card.label} {...card} loading={loading} />
      ))}
    </div>
  )
}
