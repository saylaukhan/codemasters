import { Table, type TableProps } from 'antd'

import type { LineDetail } from '../../api/types'
import { NO_VALUE, formatDate, formatSpeed } from '../../lib/format'
import { LINE_STATUS_LABELS } from '../../lib/labels'
import { ConnectionStatusBadge } from '../ui/StatusBadge'
import styles from './SchoolCard.module.css'

const contract = (line: LineDetail): string => {
  if (!line.contractNumber && !line.contractDate) return NO_VALUE
  const date = line.contractDate ? `от ${formatDate(line.contractDate)}` : ''
  return [line.contractNumber ? `№ ${line.contractNumber}` : '', date].filter(Boolean).join(' ')
}

const columns: TableProps<LineDetail>['columns'] = [
  {
    key: 'status',
    title: 'Линия',
    fixed: 'left',
    render: (_, line) => (
      <span className={line.status === 'main' ? styles.strong : undefined}>{LINE_STATUS_LABELS[line.status]}</span>
    ),
  },
  { key: 'provider', title: 'Поставщик', render: (_, line) => line.providerName },
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
  { key: 'contract', title: 'Договор', render: (_, line) => contract(line) },
  {
    key: 'identifier',
    title: 'Идентификатор линии',
    render: (_, line) => (line.lineIdentifier ? <span className={styles.code}>{line.lineIdentifier}</span> : NO_VALUE),
  },
  {
    key: 'ip',
    title: 'IP-диапазоны',
    render: (_, line) =>
      line.ipRanges.length ? <span className={styles.code}>{line.ipRanges.join(', ')}</span> : NO_VALUE,
  },
  {
    key: 'quality',
    title: 'Качество',
    render: (_, line) => <ConnectionStatusBadge status={line.qualityStatus ?? 'no_data'} />,
  },
]

/** Lines of the school (ТЗ п. 10, п. 14): main and reserve, provider and contract values. */
export function LineTable({ items }: { items: LineDetail[] }) {
  return (
    <Table<LineDetail>
      rowKey="id"
      size="middle"
      columns={columns}
      dataSource={items}
      scroll={{ x: 'max-content' }}
      pagination={false}
    />
  )
}
