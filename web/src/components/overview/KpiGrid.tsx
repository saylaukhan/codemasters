import type { DashboardSummary } from '../../api/types'
import { MS_UNIT, SPEED_UNIT, formatNumber } from '../../lib/format'
import { KpiCard } from './KpiCard'
import styles from './KpiGrid.module.css'

const count = (value: number | undefined) => formatNumber(value, 0)

/** The eight KPIs of ТЗ п. 4 in their order; measurement values — main lines, no Wi-Fi (ADR-012). */
export function KpiGrid({ summary, loading }: { summary: DashboardSummary | undefined; loading: boolean }) {
  const cards = [
    { label: 'Подключённые школы', value: count(summary?.schoolsCount) },
    { label: 'Компьютеры', value: count(summary?.devicesCount) },
    { label: 'Активные устройства', value: count(summary?.activeDevicesCount) },
    { label: 'Замеры за период', value: count(summary?.measurementsCount) },
    { label: 'Средний Download', value: formatNumber(summary?.avgDownloadMbps), unit: SPEED_UNIT },
    { label: 'Средний Upload', value: formatNumber(summary?.avgUploadMbps), unit: SPEED_UNIT },
    { label: 'Средний Ping', value: formatNumber(summary?.avgPingMs, 0), unit: MS_UNIT },
    { label: 'Проблемные устройства', value: count(summary?.problemDevicesCount) },
  ]
  return (
    <div className={styles.grid}>
      {cards.map((card) => (
        <KpiCard key={card.label} {...card} loading={loading} />
      ))}
    </div>
  )
}
