import type { TableColumnsType } from 'antd'
import { Plus } from 'lucide-react'

import type { ScheduleDetail } from '../../api/types'
import styles from '../../components/admin/Admin.module.css'
import { AdminLayout } from '../../components/admin/AdminLayout'
import { AdminTable } from '../../components/admin/AdminTable'
import { formatSlots } from '../../components/admin/hours'
import { useSchedules } from '../../components/admin/queries'
import { ScheduleDrawer } from '../../components/admin/ScheduleDrawer'
import { useAdminListView } from '../../components/admin/useAdminListView'
import { useDrawer } from '../../components/admin/useDrawer'
import { Button } from '../../components/ui/Button'
import { CONFIG_ACTIVITY_LABELS, SCHEDULE_SCOPE_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

const COLUMNS: TableColumnsType<ScheduleDetail> = [
  { key: 'scope', title: 'Уровень', render: (_, schedule) => SCHEDULE_SCOPE_LABELS[schedule.scope] },
  {
    key: 'target',
    title: 'Для чего',
    render: (_, schedule) =>
      schedule.scope === 'global' ? (
        <span className={styles.muted}>Все школы без своего расписания</span>
      ) : (
        <span className={styles.name}>{schedule.regionName ?? schedule.schoolName}</span>
      ),
  },
  { key: 'count', title: 'Замеров в день', render: (_, schedule) => schedule.slots.length },
  { key: 'slots', title: 'Слоты, Asia/Almaty', render: (_, schedule) => formatSlots(schedule.slots) },
  {
    key: 'active',
    title: 'Состояние',
    render: (_, schedule) =>
      schedule.isActive ? (
        CONFIG_ACTIVITY_LABELS.active
      ) : (
        <span className={styles.muted}>{CONFIG_ACTIVITY_LABELS.disabled}</span>
      ),
  },
]

/**
 * Schedules of measurements (ТЗ п. 2, п. 20): 3–5 slots a day for the whole oblast, a district or a school; the agent
 * takes the most specific active one with its next configuration.
 */
export function SchedulesPage() {
  const [view, setView] = useAdminListView()
  const schedules = useSchedules(view)
  const drawer = useDrawer<ScheduleDetail>()
  const base = schedules.data?.items.find((schedule) => schedule.scope === 'global')

  return (
    <AdminLayout
      tab="schedules"
      action={
        <Button
          kind="action"
          icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
          onClick={() => drawer.show()}
        >
          Добавить расписание
        </Button>
      }
    >
      <p className={styles.lead}>
        Агент берёт самое конкретное действующее расписание: школа → район → вся область, и делает замер в случайный
        момент внутри каждого слота. Переустанавливать агенты не нужно.
      </p>
      <AdminTable
        query={schedules}
        columns={COLUMNS}
        view={view}
        onChange={setView}
        empty={{ title: 'Расписаний пока нет', description: 'Глобальное расписание создаётся при установке системы.' }}
        onEdit={(schedule) => drawer.show(schedule)}
      />
      <ScheduleDrawer key={drawer.key} open={drawer.open} schedule={drawer.item} base={base} onClose={drawer.close} />
    </AdminLayout>
  )
}
