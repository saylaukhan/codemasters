import type { ReactNode } from 'react'

import type { ProviderScoreRow } from '../../api/providers'
import { formatDuration, formatNumber, formatPercent, NO_VALUE } from '../../lib/format'
import { PROVIDER_COLUMN_LABELS, PROVIDER_LABELS, PROVIDER_VERDICT_LABELS } from '../../lib/labels'
import { Button } from '../ui/Button'
import { ResponsiveTable, type ResponsiveColumn } from '../ui/ResponsiveTable'
import styles from './Provider.module.css'

interface ProvidersTableProps {
  rows: readonly ProviderScoreRow[]
  /** Score below it is «ниже нормы»; the number comes from the settings, not from here (ТЗ п. 11). */
  passPct: number
  selectedId: number | null
  loading: boolean
  empty: ReactNode
  onSelect: (providerId: number) => void
}

const number = (text: string, alert = false) => (
  <span className={alert ? `${styles.number} ${styles.below}` : styles.number}>{text}</span>
)

const duration = (seconds: number | null) => (seconds === null ? NO_VALUE : formatDuration(seconds))

/** Score of every provider of the period (DESIGN.md §3.29): worst first, a row opens the card. */
export function ProvidersTable({ rows, passPct, selectedId, loading, empty, onSelect }: ProvidersTableProps) {
  const verdict = (row: ProviderScoreRow) =>
    row.verdict === null ? NO_VALUE : PROVIDER_VERDICT_LABELS[row.verdict]

  const columns: ResponsiveColumn<ProviderScoreRow>[] = [
    {
      key: 'name',
      title: PROVIDER_COLUMN_LABELS.name,
      priority: 'primary',
      fixed: 'left',
      width: 240,
      sorter: (a, b) => a.name.localeCompare(b.name, 'ru'),
      render: (_, row) => row.name,
    },
    {
      key: 'schools',
      title: PROVIDER_COLUMN_LABELS.schools,
      align: 'right',
      sorter: (a, b) => a.schoolsCount - b.schoolsCount,
      render: (_, row) => number(formatNumber(row.schoolsCount, 0)),
    },
    {
      key: 'belowContract',
      title: PROVIDER_COLUMN_LABELS.belowContract,
      align: 'right',
      sorter: (a, b) => (a.belowContractPct ?? 0) - (b.belowContractPct ?? 0),
      render: (_, row) => number(formatPercent(row.belowContractPct), (row.belowContractPct ?? 0) > 0),
    },
    {
      key: 'incidents',
      title: PROVIDER_COLUMN_LABELS.incidents,
      priority: 'minor',
      align: 'right',
      sorter: (a, b) => a.incidentsOpened - b.incidentsOpened,
      render: (_, row) => number(formatNumber(row.incidentsOpened, 0)),
    },
    {
      key: 'reaction',
      title: PROVIDER_COLUMN_LABELS.reaction,
      align: 'right',
      sorter: (a, b) => (a.reactionMedianS ?? 0) - (b.reactionMedianS ?? 0),
      render: (_, row) => number(duration(row.reactionMedianS)),
    },
    {
      key: 'restore',
      title: PROVIDER_COLUMN_LABELS.restore,
      priority: 'minor',
      align: 'right',
      sorter: (a, b) => (a.restoreAvgS ?? 0) - (b.restoreAvgS ?? 0),
      render: (_, row) => number(duration(row.restoreAvgS)),
    },
    {
      key: 'belowNorm',
      title: PROVIDER_COLUMN_LABELS.belowNorm,
      priority: 'minor',
      align: 'right',
      sorter: (a, b) => a.linesBelowNormCount - b.linesBelowNormCount,
      render: (_, row) => number(formatNumber(row.linesBelowNormCount, 0)),
    },
    {
      key: 'score',
      title: PROVIDER_COLUMN_LABELS.score,
      priority: 'primary',
      align: 'right',
      defaultSortOrder: 'ascend',
      sorter: (a, b) => (a.score ?? 0) - (b.score ?? 0),
      render: (_, row) =>
        number(row.score === null ? NO_VALUE : formatNumber(row.score, 0), row.verdict === 'below_norm'),
    },
  ]

  return (
    <ResponsiveTable<ProviderScoreRow>
      rowKey={(row) => row.id}
      size="middle"
      columns={columns}
      dataSource={[...rows]}
      loading={loading}
      scroll={{ x: 'max-content' }}
      locale={{ emptyText: empty }}
      showSorterTooltip={false}
      rowClassName={(row) => (row.id === selectedId ? 'ant-table-row-selected' : '')}
      onRow={(row) => ({ onClick: () => onSelect(row.id) })}
      card={{
        title: (row) => row.name,
        status: (row) => number(verdict(row), row.verdict === 'below_norm'),
        description: (row) =>
          PROVIDER_LABELS.scoreOf(
            row.score === null ? PROVIDER_LABELS.noScore : formatNumber(row.score, 0),
            formatNumber(passPct, 0),
          ),
        action: (row) => (
          <Button kind="link" onClick={() => onSelect(row.id)}>
            {PROVIDER_LABELS.open}
          </Button>
        ),
      }}
    />
  )
}
