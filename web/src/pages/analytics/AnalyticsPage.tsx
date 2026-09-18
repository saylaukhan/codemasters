import { SearchX } from 'lucide-react'

import { AnalyticsFilterBar } from '../../components/analytics/AnalyticsFilterBar'
import styles from '../../components/analytics/Analytics.module.css'
import { useAnalytics } from '../../components/analytics/queries'
import { RatingTable } from '../../components/analytics/RatingTable'
import { hoursChart, rankRows, reportTotals } from '../../components/analytics/report'
import { SchoolComparison } from '../../components/analytics/SchoolComparison'
import { isFiltered, useAnalyticsView } from '../../components/analytics/view'
import { useMapFilterOptions } from '../../components/map/queries'
import { KpiCard } from '../../components/overview/KpiCard'
import { speedChart } from '../../components/schools/speedChart'
import { Button } from '../../components/ui/Button'
import { ChartCard } from '../../components/ui/Chart'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { formatDate, formatMs, formatNumber, formatPercent, formatSpeed, MS_UNIT, SPEED_UNIT } from '../../lib/format'
import { ANALYTICS_LEVEL_LABELS, SECTION_LABELS } from '../../lib/labels'

const NO_MEASUREMENTS = (
  <EmptyState title="Замеров за период нет" description="Выберите другой период или снимите фильтры." />
)

/** Analytics (ТЗ п. 5, п. 13; plan.md §11): totals, charts, rating, slices and comparison of schools. */
export function AnalyticsPage() {
  const [view, setView] = useAnalyticsView()
  const options = useMapFilterOptions()
  const report = useAnalytics(view)
  // Choices of «Сравнение школ»; the same request as the report on the school level.
  const schools = useAnalytics(view, 'school')

  const data = report.data
  const period = data
    ? `${formatDate(data.periodFrom)} — ${formatDate(Date.parse(data.periodTo) - 1)}`
    : undefined
  const resetFilters = () => setView({ ...view, regionId: undefined, providerId: undefined, connectionTypeId: undefined })

  let content
  if (report.isError) {
    content = <ErrorState error={report.error} onRetry={() => void report.refetch()} />
  } else if (!data) {
    content = <ContentSkeleton rows={8} />
  } else {
    const totals = reportTotals(data)
    const limits = data.thresholds
    const minPct = data.availabilityMinPct
    const available = data.rows.filter((row) => row.availabilityPct !== null)
    const belowAvailability = available.filter((row) => (row.availabilityPct as number) < minPct).length
    const availability =
      view.level === 'region'
        ? {
            label: 'Доступность',
            value: formatNumber(data.rows[0]?.availabilityPct, 2),
            unit: '%',
            alert: (data.rows[0]?.availabilityPct ?? 100) < minPct,
          }
        : {
            label: `Доступность ниже ${formatPercent(minPct, 0)}`,
            value: available.length ? String(belowAvailability) : formatNumber(null),
            unit: `из ${available.length}`,
            alert: belowAvailability > 0,
          }
    const empty = isFiltered(view) ? (
      <EmptyState
        icon={SearchX}
        title="Ничего не найдено по фильтрам"
        description="Измените или сбросьте фильтры."
        action={<Button onClick={resetFilters}>Сбросить фильтры</Button>}
      />
    ) : (
      <EmptyState title="Данных пока нет" description="В вашей области видимости нет ни одной записи этого уровня." />
    )
    const fileName = `analytics-${view.level}-${view.period}`

    content = (
      <>
        <div className={styles.kpis}>
          <KpiCard label="Замеров" value={formatNumber(totals.measurementsCount, 0)} />
          <KpiCard label="Проблемных" value={formatNumber(totals.problemPct)} unit="%" />
          <KpiCard
            label="Download, ср."
            value={formatNumber(totals.avgDownloadMbps)}
            unit={SPEED_UNIT}
            alert={totals.avgDownloadMbps !== null && totals.avgDownloadMbps < limits.downloadMinMbps}
          />
          <KpiCard
            label="Upload, ср."
            value={formatNumber(totals.avgUploadMbps)}
            unit={SPEED_UNIT}
            alert={totals.avgUploadMbps !== null && totals.avgUploadMbps < limits.uploadMinMbps}
          />
          <KpiCard
            label="Ping, ср."
            value={formatNumber(totals.avgPingMs, 0)}
            unit={MS_UNIT}
            alert={totals.avgPingMs !== null && totals.avgPingMs > limits.pingMaxMs}
          />
          <KpiCard {...availability} />
        </div>
        <div className={styles.charts}>
          <ChartCard
            title="Скорость и задержка"
            fileName={`${fileName}-speed`}
            data={speedChart(data, undefined)}
            placeholder={data.series.length === 0 ? NO_MEASUREMENTS : undefined}
          />
          <ChartCard
            title="Часы ухудшения"
            fileName={`${fileName}-hours`}
            data={hoursChart(data)}
            placeholder={data.heatmap.length === 0 ? NO_MEASUREMENTS : undefined}
          />
        </div>
        <h2 className={styles.section}>
          {view.level === 'region'
            ? 'Показатели области'
            : `Рейтинг: ${ANALYTICS_LEVEL_LABELS[view.level].toLowerCase()}`}
        </h2>
        <p className={styles.caption}>
          Среднее за период, под ним — минимум и максимум. Пороги: Download от{' '}
          {formatSpeed(limits.downloadMinMbps)}, Upload от {formatSpeed(limits.uploadMinMbps)}, Ping до{' '}
          {formatMs(limits.pingMaxMs)}; доступность от {formatPercent(minPct, 0)} — ниже выделена красным.
        </p>
        <RatingTable
          level={view.level}
          rows={rankRows(data.rows)}
          availabilityMinPct={minPct}
          loading={report.isFetching && report.isPlaceholderData}
          empty={empty}
        />
        {schools.data && (
          <SchoolComparison
            view={view}
            schools={schools.data.rows}
            onChange={(compare) => setView({ ...view, compare })}
          />
        )}
      </>
    )
  }

  return (
    <>
      <PageHeader title={SECTION_LABELS.analytics} subtitle={period} />
      <AnalyticsFilterBar view={view} options={options.data} onChange={setView} />
      {content}
    </>
  )
}
