import { Select, Table } from 'antd'
import { GitCompare } from 'lucide-react'
import { useMemo } from 'react'

import type { AnalyticsRow } from '../../api/types'
import { formatMs, formatNumber, formatPercent, formatSpeed, NO_VALUE } from '../../lib/format'
import { ChartCard } from '../ui/Chart'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import styles from './Analytics.module.css'
import { useSchoolReport } from './queries'
import { compareChart } from './report'
import type { AnalyticsView } from './view'

// Rows of the comparison table: caption and the value of one school.
const METRICS: { key: string; title: string; value: (row: AnalyticsRow) => string }[] = [
  { key: 'measurements', title: 'Замеров', value: (row) => formatNumber(row.measurementsCount, 0) },
  { key: 'problems', title: 'Проблемных', value: (row) => formatPercent(row.problemPct) },
  { key: 'download', title: 'Download, ср.', value: (row) => formatSpeed(row.downloadMbps?.avg) },
  { key: 'downloadMin', title: 'Download, мин.', value: (row) => formatSpeed(row.downloadMbps?.min) },
  { key: 'upload', title: 'Upload, ср.', value: (row) => formatSpeed(row.uploadMbps?.avg) },
  { key: 'ping', title: 'Ping, ср.', value: (row) => formatMs(row.pingMs?.avg) },
  { key: 'pingMax', title: 'Ping, макс.', value: (row) => formatMs(row.pingMs?.max) },
  { key: 'availability', title: 'Доступность', value: (row) => formatPercent(row.availabilityPct, 2) },
  { key: 'contract', title: 'Ниже договора', value: (row) => formatPercent(row.belowContractPct) },
]

interface SchoolComparisonProps {
  view: AnalyticsView
  /** Schools to choose from: the rows of the school level under the filters. */
  schools: readonly AnalyticsRow[]
  onChange: (compare: number[]) => void
}

/** «Сравнение школ» (ТЗ п. 5): two schools side by side over the period of the screen. */
export function SchoolComparison({ view, schools, onChange }: SchoolComparisonProps) {
  const [firstId, secondId]: (number | undefined)[] = view.compare
  const first = useSchoolReport(view, firstId)
  const second = useSchoolReport(view, secondId)
  // A compared school outside the current filters keeps its name from its own report.
  const options = useMemo(() => {
    const rows = [...schools, ...[first.data?.rows[0], second.data?.rows[0]].filter((row) => row !== undefined)]
    const names = new Map(rows.filter((row) => row.id !== null).map((row) => [row.id as number, row.name ?? '']))
    return [...names].map(([value, label]) => ({ value, label }))
  }, [schools, first.data, second.data])

  const pick = (index: number, id: number | undefined) => {
    const next: (number | undefined)[] = [firstId, secondId]
    next[index] = id
    onChange(next.filter((value): value is number => value !== undefined))
  }
  const picker = (index: number, value: number | undefined, other: number | undefined) => (
    <Select<number>
      className={styles.school}
      aria-label={index === 0 ? 'Первая школа' : 'Вторая школа'}
      placeholder={index === 0 ? 'Первая школа' : 'Вторая школа'}
      value={value}
      options={options.filter((option) => option.value !== other)}
      onChange={(id) => pick(index, id ?? undefined)}
      allowClear
      showSearch
      optionFilterProp="label"
    />
  )

  const reports = [first, second]
  const failed = reports.find((report) => report.isError)
  const loaded = reports.map((report) => report.data?.rows[0])
  let body
  if (firstId === undefined || secondId === undefined) {
    body = <EmptyState icon={GitCompare} title="Выберите две школы" description="Показатели встанут рядом за период экрана." />
  } else if (failed) {
    body = <ErrorState error={failed.error} onRetry={() => reports.forEach((report) => void report.refetch())} />
  } else if (!first.data || !second.data || !loaded[0] || !loaded[1]) {
    body = <ContentSkeleton rows={6} />
  } else {
    const [a, b] = loaded
    const compared = [
      { name: a.name ?? NO_VALUE, report: first.data },
      { name: b.name ?? NO_VALUE, report: second.data },
    ]
    const chart = compareChart(compared)
    body = (
      <div className={styles.compare}>
        <Table
          rowKey="key"
          size="small"
          pagination={false}
          dataSource={METRICS}
          columns={[
            { key: 'title', title: 'Показатель', dataIndex: 'title' },
            ...[a, b].map((row, index) => ({
              key: String(index),
              title: row.name,
              align: 'right' as const,
              render: (_: unknown, metric: (typeof METRICS)[number]) => (
                <span className={styles.number}>{metric.value(row)}</span>
              ),
            })),
          ]}
        />
        <ChartCard
          title="Download и Ping"
          fileName={`compare-${firstId}-${secondId}-${view.period}`}
          data={chart}
          placeholder={
            chart.moments.length === 0 ? (
              <EmptyState title="Замеров за период нет" description="Выберите другой период." />
            ) : undefined
          }
        />
      </div>
    )
  }

  return (
    <section aria-label="Сравнение школ">
      <h2 className={styles.section}>Сравнение школ</h2>
      <div className={styles.picker}>
        {picker(0, firstId, secondId)}
        {picker(1, secondId, firstId)}
      </div>
      {body}
    </section>
  )
}
