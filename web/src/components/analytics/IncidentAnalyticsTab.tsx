import { Table, type TableColumnType } from 'antd'
import { SearchX } from 'lucide-react'
import { Link } from 'react-router'

import type { IncidentAnalyticsRow } from '../../api/types'
import { schoolCardPath } from '../../app/sections'
import { formatDuration, formatNumber } from '../../lib/format'
import { ANALYTICS_ENTITY_LABELS } from '../../lib/labels'
import { KpiCard } from '../overview/KpiCard'
import { Button } from '../ui/Button'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import styles from './Analytics.module.css'
import { useIncidentAnalytics } from './queries'
import { byValue, incidentTotals } from './report'
import { isFiltered, type AnalyticsView } from './view'

interface IncidentAnalyticsTabProps {
  view: AnalyticsView
  report: ReturnType<typeof useIncidentAnalytics>
  onResetFilters: () => void
}

type Duration = 'totalDurationS' | 'avgDurationS' | 'maxDurationS'
type Count = 'incidentsCount' | 'openCount' | 'linesCount'

const number = (text: string, alert = false) => (
  <span className={alert ? `${styles.number} ${styles.below}` : styles.number}>{text}</span>
)

/**
 * «Инциденты» of the analytics (ТЗ п. 19, plan.md §7): how many incidents a school, a district or a
 * provider had over the period, how long they lasted and how often they come back. Only a restored
 * incident has a length, so an open one counts but lengthens nothing (ADR-007).
 */
export function IncidentAnalyticsTab({ view, report, onResetFilters }: IncidentAnalyticsTabProps) {
  const data = report.data
  if (report.isError) {
    return <ErrorState error={report.error} onRetry={() => void report.refetch()} />
  }
  if (!data) {
    return <ContentSkeleton rows={8} />
  }

  const totals = incidentTotals(data)
  const counted = (key: Count, title: string): TableColumnType<IncidentAnalyticsRow> => ({
    key,
    title,
    align: 'right',
    sorter: byValue((row: IncidentAnalyticsRow) => row[key]),
    render: (_, row) => number(formatNumber(row[key], 0), key === 'openCount' && row[key] > 0),
  })
  const duration = (key: Duration, title: string): TableColumnType<IncidentAnalyticsRow> => ({
    key,
    title,
    align: 'right',
    sorter: byValue((row: IncidentAnalyticsRow) => row[key]),
    render: (_, row) => number(formatDuration(row[key])),
  })

  const columns: TableColumnType<IncidentAnalyticsRow>[] = [
    {
      key: 'name',
      title: ANALYTICS_ENTITY_LABELS[view.level],
      width: 280,
      sorter: (a, b) => (a.name ?? '').localeCompare(b.name ?? '', 'ru'),
      render: (_, row) =>
        view.level === 'school' && row.id !== null ? (
          <Link to={schoolCardPath(row.id)}>{row.name}</Link>
        ) : (
          (row.name ?? 'Вся ВКО')
        ),
    },
    { ...counted('incidentsCount', 'Инцидентов'), defaultSortOrder: 'descend' },
    counted('openCount', 'Открытых'),
    duration('totalDurationS', 'Суммарно'),
    duration('avgDurationS', 'В среднем'),
    duration('maxDurationS', 'Самый долгий'),
    {
      key: 'repeatability',
      title: 'Повторяемость',
      align: 'right',
      sorter: byValue((row: IncidentAnalyticsRow) => row.incidentsPerLine30d),
      render: (_, row) => number(formatNumber(row.incidentsPerLine30d, 2)),
    },
    counted('linesCount', 'Линий'),
  ]

  const empty = isFiltered(view) ? (
    <EmptyState
      icon={SearchX}
      title="Ничего не найдено по фильтрам"
      description="Измените или сбросьте фильтры."
      action={<Button onClick={onResetFilters}>Сбросить фильтры</Button>}
    />
  ) : (
    <EmptyState title="Данных пока нет" description="В вашей области видимости нет ни одной записи этого уровня." />
  )

  return (
    <>
      <div className={styles.kpis}>
        <KpiCard label="Инцидентов" value={formatNumber(totals.incidentsCount, 0)} />
        <KpiCard label="Открытых" value={formatNumber(totals.openCount, 0)} alert={totals.openCount > 0} />
        <KpiCard label="Устранённых" value={formatNumber(totals.restoredCount, 0)} />
        <KpiCard label="Длительность, ср." value={formatDuration(totals.avgDurationS)} />
        <KpiCard label="На линию за 30 дней" value={formatNumber(totals.incidentsPerLine30d, 2)} />
        <KpiCard label="Линий" value={formatNumber(totals.linesCount, 0)} />
      </div>
      <h2 className={styles.section}>Инциденты: {ANALYTICS_ENTITY_LABELS[view.level].toLowerCase()}</h2>
      <p className={styles.caption}>
        Инцидент попадает в период по началу. Длительность — от начала до восстановления показателей, поэтому открытые
        инциденты считаются, но длительность не увеличивают. Повторяемость — инцидентов на линию за{' '}
        {data.repeatabilityWindowDays} дней.
      </p>
      <Table<IncidentAnalyticsRow>
        rowKey={(row) => row.id ?? 0}
        size="middle"
        columns={view.level === 'region' ? columns.slice(1) : columns}
        dataSource={data.rows}
        loading={report.isFetching && report.isPlaceholderData}
        scroll={{ x: 'max-content' }}
        locale={{ emptyText: empty }}
        showSorterTooltip={false}
        pagination={
          data.rows.length > 25 && {
            defaultPageSize: 25,
            pageSizeOptions: ['25', '50', '100'],
            showSizeChanger: true,
            showTotal: (count, [from, to]) => `${from}–${to} из ${count}`,
          }
        }
      />
    </>
  )
}
