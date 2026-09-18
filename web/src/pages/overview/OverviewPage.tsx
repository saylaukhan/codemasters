import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { MapFilterBar } from '../../components/map/MapFilterBar'
import { NO_FILTERS } from '../../components/map/filters'
import { useMapFilterOptions, useRegionBoundaries, useSchoolMap } from '../../components/map/queries'
import { SchoolMapView } from '../../components/map/SchoolMapView'
import { useMapFilters } from '../../components/map/useMapFilters'
import { KpiGrid } from '../../components/overview/KpiGrid'
import { useDashboardSummary } from '../../components/overview/queries'
import { formatDateTime } from '../../lib/format'
import { SECTION_LABELS } from '../../lib/labels'
import styles from './OverviewPage.module.css'

/** Main screen (ТЗ п. 4, п. 13; plan.md §11): the eight KPIs and the map under one set of filters. */
export function OverviewPage() {
  const [filters, setFilters] = useMapFilters()
  const summary = useDashboardSummary(filters)
  const schools = useSchoolMap(filters)
  const regions = useRegionBoundaries()
  const options = useMapFilterOptions()

  const period = summary.data
    ? `${formatDateTime(summary.data.periodFrom)} — ${formatDateTime(summary.data.periodTo)}`
    : undefined

  return (
    <>
      <PageHeader title={SECTION_LABELS.overview} subtitle={period} />
      <MapFilterBar filters={filters} options={options.data} onChange={setFilters} />
      {summary.isError ? (
        <div className={styles.error}>
          <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
        </div>
      ) : (
        <KpiGrid summary={summary.data} loading={summary.isPending} />
      )}
      <SchoolMapView
        schools={schools}
        regions={regions.data}
        filters={filters}
        onReset={() => setFilters(NO_FILTERS)}
        className={styles.map}
      />
    </>
  )
}
