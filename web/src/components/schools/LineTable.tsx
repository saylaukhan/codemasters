import type { LineDetail } from '../../api/types'
import { NO_VALUE, formatDate, formatSpeed } from '../../lib/format'
import { LINE_STATUS_LABELS } from '../../lib/labels'
import { Button } from '../ui/Button'
import { ResponsiveTable, type ResponsiveColumn } from '../ui/ResponsiveTable'
import { ConnectionStatusBadge } from '../ui/StatusBadge'
import styles from './SchoolCard.module.css'

const contract = (line: LineDetail): string => {
  if (!line.contractNumber && !line.contractDate) return NO_VALUE
  const date = line.contractDate ? `от ${formatDate(line.contractDate)}` : ''
  return [line.contractNumber ? `№ ${line.contractNumber}` : '', date].filter(Boolean).join(' ')
}

// Priorities of DESIGN.md §3.12: the contract number, the line identifier and the IP ranges are
// exactly the columns the step-1 «Колонки» button hides — they are `minor`.
const columns: readonly ResponsiveColumn<LineDetail>[] = [
  {
    key: 'status',
    title: 'Линия',
    priority: 'primary',
    fixed: 'left',
    render: (_, line) => (
      <span className={line.status === 'main' ? styles.strong : undefined}>{LINE_STATUS_LABELS[line.status]}</span>
    ),
  },
  { key: 'provider', title: 'Поставщик', priority: 'primary', render: (_, line) => line.providerName },
  { key: 'type', title: 'Тип подключения', render: (_, line) => line.connectionTypeName ?? NO_VALUE },
  {
    key: 'down',
    title: 'Договор Download',
    align: 'right',
    render: (_, line) => <span className={styles.number}>{formatSpeed(line.contractDownMbps)}</span>,
  },
  {
    key: 'up',
    title: 'Договор Upload',
    align: 'right',
    render: (_, line) => <span className={styles.number}>{formatSpeed(line.contractUpMbps)}</span>,
  },
  { key: 'contract', title: 'Договор', priority: 'minor', render: (_, line) => contract(line) },
  {
    key: 'identifier',
    title: 'Идентификатор линии',
    priority: 'minor',
    render: (_, line) => (line.lineIdentifier ? <span className={styles.code}>{line.lineIdentifier}</span> : NO_VALUE),
  },
  {
    key: 'ip',
    title: 'IP-диапазоны',
    priority: 'minor',
    render: (_, line) =>
      line.ipRanges.length ? <span className={styles.code}>{line.ipRanges.join(', ')}</span> : NO_VALUE,
  },
  {
    key: 'quality',
    title: 'Качество',
    priority: 'primary',
    render: (_, line) => <ConnectionStatusBadge status={line.qualityStatus ?? 'no_data'} />,
  },
]

interface LineTableProps {
  items: LineDetail[]
  /** «Изменить» of a row, for a role that sets up the monitoring (T-35). */
  onEdit?: (line: LineDetail) => void
}

/** Lines of the school (ТЗ п. 10, п. 14): main and reserve, provider and contract values. */
export function LineTable({ items, onEdit }: LineTableProps) {
  return (
    <ResponsiveTable<LineDetail>
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
                render: (_, line) => (
                  <Button kind="flat" size="small" onClick={() => onEdit(line)}>
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
        title: (line) => `${LINE_STATUS_LABELS[line.status]} · ${line.providerName}`,
        status: (line) => <ConnectionStatusBadge status={line.qualityStatus ?? 'no_data'} />,
        action: onEdit
          ? (line) => (
              <Button kind="flat" size="small" onClick={() => onEdit(line)}>
                Изменить
              </Button>
            )
          : undefined,
      }}
      pagination={false}
    />
  )
}
