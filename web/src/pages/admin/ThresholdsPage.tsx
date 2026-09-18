import type { TableColumnsType } from 'antd'
import { Plus } from 'lucide-react'

import type { ThresholdProfileDetail } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { useThresholdProfiles } from '../../components/admin/queries'
import { ThresholdDrawer } from '../../components/admin/ThresholdDrawer'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { formatMs, formatPercent, formatSpeed } from '../../lib/format'
import { CONFIG_ACTIVITY_LABELS, LINE_STATUS_LABELS, PROFILE_SCOPE_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

/** What the profile is for: the district, or the school and the provider of the line. */
const target = (profile: ThresholdProfileDetail) => {
  if (profile.scope === 'district') return profile.regionName
  if (profile.scope === 'line') {
    const role = profile.lineStatus ? ` · ${LINE_STATUS_LABELS[profile.lineStatus]}` : ''
    return `${profile.schoolName} · ${profile.providerName}${role}`
  }
  return <span className={styles.muted}>Все школы без своего профиля</span>
}

const COLUMNS: TableColumnsType<ThresholdProfileDetail> = [
  { key: 'scope', title: 'Уровень', render: (_, profile) => PROFILE_SCOPE_LABELS[profile.scope] },
  { key: 'target', title: 'Для чего', render: (_, profile) => <span className={styles.name}>{target(profile)}</span> },
  { key: 'download', title: 'Download ≥', render: (_, { thresholds }) => formatSpeed(thresholds.downloadMinMbps) },
  { key: 'upload', title: 'Upload ≥', render: (_, { thresholds }) => formatSpeed(thresholds.uploadMinMbps) },
  { key: 'ping', title: 'Ping ≤', render: (_, { thresholds }) => formatMs(thresholds.pingMaxMs) },
  { key: 'jitter', title: 'Jitter ≤', render: (_, { thresholds }) => formatMs(thresholds.jitterMaxMs) },
  { key: 'loss', title: 'Packet Loss ≤', render: (_, { thresholds }) => formatPercent(thresholds.packetLossMaxPct) },
  { key: 'unstable', title: 'Нестабильно до', render: (_, profile) => formatPercent(profile.unstableDeviationPct, 0) },
  {
    key: 'active',
    title: 'Состояние',
    render: (_, profile) =>
      profile.isActive ? (
        CONFIG_ACTIVITY_LABELS.active
      ) : (
        <span className={styles.muted}>{CONFIG_ACTIVITY_LABELS.disabled}</span>
      ),
  },
]

/**
 * Threshold profiles (ТЗ п. 11, ADR-004): the whole oblast, a district or one line; a measurement is judged by the
 * most specific active one and keeps the thresholds it was judged by.
 */
export function ThresholdsPage() {
  const [view, setView] = useAdminListView()
  const profiles = useThresholdProfiles(view)
  const drawer = useDrawer<ThresholdProfileDetail>()
  const base = profiles.data?.items.find((profile) => profile.scope === 'global')

  return (
    <AdminLayout
      tab="thresholds"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить профиль
        </Button>
      }
    >
      <p className={styles.lead}>
        Замер оценивается по самому конкретному действующему профилю: линия → район → вся область. Новые значения
        действуют со следующего замера, сохранённые замеры не пересчитываются.
      </p>
      <AdminTable
        query={profiles}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{ title: 'Профилей пока нет', description: 'Глобальный профиль создаётся при установке системы.' }}
        onEdit={(profile) => drawer.show(profile)}
      />
      <ThresholdDrawer key={drawer.key} open={drawer.open} profile={drawer.item} base={base} onClose={drawer.close} />
    </AdminLayout>
  )
}
