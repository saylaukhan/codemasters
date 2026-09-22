import type { MonitoringPointDetail } from '../../api/types'
import { NO_VALUE } from '../../lib/format'
import { LINE_STATUS_LABELS, MONITORING_POINT_LABELS } from '../../lib/labels'
import { Button } from '../ui/Button'
import { ResponsiveTable, type ResponsiveColumn } from '../ui/ResponsiveTable'
import styles from './SchoolCard.module.css'

// Four short columns fit at every width (DESIGN.md §9.3); the wrapper is here for step 3 only.
const columns: readonly ResponsiveColumn<MonitoringPointDetail>[] = [
  {
    key: 'name',
    title: 'Точка',
    priority: 'primary',
    fixed: 'left',
    render: (_, point) => (
      <span className={styles.stack}>
        <span className={point.isPrimary ? styles.strong : undefined}>{point.name}</span>
        {point.isPrimary && <span className={styles.muted}>{MONITORING_POINT_LABELS.primary}</span>}
      </span>
    ),
  },
  { key: 'room', title: 'Кабинет', render: (_, point) => point.room ?? NO_VALUE },
  {
    key: 'line',
    title: 'Линия',
    render: (_, point) => `${LINE_STATUS_LABELS[point.lineStatus]} · ${point.providerName}`,
  },
  {
    key: 'devices',
    title: 'Компьютеров',
    align: 'right',
    render: (_, point) => <span className={styles.number}>{point.devicesCount}</span>,
  },
]

interface PointTableProps {
  items: MonitoringPointDetail[]
  /** «Изменить» of a row, for a role that sets up the monitoring. */
  onEdit?: (point: MonitoringPointDetail) => void
}

/** Monitoring points of the school (ТЗ п. 10): where the computers measure and which line. */
export function PointTable({ items, onEdit }: PointTableProps) {
  return (
    <ResponsiveTable<MonitoringPointDetail>
      rowKey="id"
      size="middle"
      columns={
        onEdit
          ? [
              ...(columns ?? []),
              {
                key: 'edit',
                priority: 'primary',
                align: 'right',
                render: (_, point) => (
                  <Button kind="flat" size="small" onClick={() => onEdit(point)}>
                    Изменить
                  </Button>
                ),
              },
            ]
          : columns
      }
      dataSource={items}
      scroll={{ x: 'max-content' }}
      card={{
        title: (point) => <span className={point.isPrimary ? styles.strong : undefined}>{point.name}</span>,
        description: (point) => (point.isPrimary ? MONITORING_POINT_LABELS.primary : undefined),
        action: onEdit
          ? (point) => (
              <Button kind="flat" size="small" onClick={() => onEdit(point)}>
                Изменить
              </Button>
            )
          : undefined,
      }}
      pagination={false}
    />
  )
}
