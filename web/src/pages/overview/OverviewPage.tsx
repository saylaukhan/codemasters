import { OPEN_INCIDENT_STATUSES, type IncidentListView } from '../../components/incidents/incidents'
import { IncidentTable } from '../../components/incidents/IncidentTable'
import { useIncidents } from '../../components/incidents/queries'
import { NO_FILTERS } from '../../components/map/filters'
import { MapFilterBar } from '../../components/map/MapFilterBar'
import { useMapFilterOptions, useRegionBoundaries, useSchoolMap } from '../../components/map/queries'
import { SchoolMapView } from '../../components/map/SchoolMapView'
import { useMapFilters } from '../../components/map/useMapFilters'
import { AttentionCard } from '../../components/overview/AttentionCard'
import { OverviewSection } from '../../components/overview/OverviewSection'
import { useDashboardAttention, useDashboardSummary } from '../../components/overview/queries'
import { kpiStripItems, noDataFootnote, statusStripItems } from '../../components/overview/strips'
import { overviewVerdict, selectedSchools } from '../../components/overview/verdict'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { KpiStrip } from '../../components/ui/KpiStrip'
import { PageHeader } from '../../components/ui/PageHeader'
import { StatusStrip } from '../../components/ui/StatusStrip'
import { formatNumber, formatTime, plural } from '../../lib/format'
import { OVERVIEW_LABELS, SCHOOL_COUNT_FORMS, WHOLE_OBLAST_SCOPE_LABEL } from '../../lib/labels'
import styles from './OverviewPage.module.css'

/** The five newest incidents that still wait for a person; the server orders them by start (T-41). */
const LATEST_INCIDENTS: IncidentListView = {
  statuses: [...OPEN_INCIDENT_STATUSES],
  q: '',
  page: 1,
  pageSize: 5,
}

/**
 * Main screen of the oblast and of a district (ТЗ п. 4, п. 13; DESIGN.md §3.28): the verdict, the
 * status strip, the map with «Требуют внимания», the eight KPIs and the latest incidents — all
 * under one set of filters kept in the URL (§2.6).
 */
export function OverviewPage() {
  const [filters, setFilters] = useMapFilters()
  const summary = useDashboardSummary(filters)
  const attention = useDashboardAttention(filters)
  const schools = useSchoolMap(filters)
  const regions = useRegionBoundaries()
  const options = useMapFilterOptions()
  const incidents = useIncidents(LATEST_INCIDENTS)

  const data = summary.data
  const scope = options.data?.regions.find((region) => region.id === filters.regionId)?.name
  const judged = data ? selectedSchools(data) : 0
  const context = data
    ? OVERVIEW_LABELS.context(
        scope ?? WHOLE_OBLAST_SCOPE_LABEL,
        formatNumber(judged, 0),
        plural(judged, SCHOOL_COUNT_FORMS),
      )
    : (scope ?? WHOLE_OBLAST_SCOPE_LABEL)

  // One query, one error block (DESIGN.md §2.7): it stands in the strip and the KPIs step aside.
  const summaryError = summary.isError ? (
    <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
  ) : null

  return (
    <>
      <PageHeader
        context={context}
        title={overviewVerdict(data)}
        subtitle={data ? OVERVIEW_LABELS.subtitle(formatTime(data.periodTo)) : undefined}
      />
      <MapFilterBar filters={filters} options={options.data} onChange={setFilters} />
      <div className={styles.page}>
        {summaryError ??
          (data ? (
            <StatusStrip
              items={statusStripItems(data, filters)}
              label={OVERVIEW_LABELS.statusStrip}
              footnote={noDataFootnote(data)}
            />
          ) : (
            <ContentSkeleton rows={2} />
          ))}
        <div className={styles.row}>
          <OverviewSection
            title={OVERVIEW_LABELS.map}
            link={{ to: '/map', label: OVERVIEW_LABELS.mapOpen }}
            className={styles.mapCard}
          >
            <SchoolMapView
              schools={schools}
              regions={regions.data}
              filters={filters}
              onReset={() => setFilters(NO_FILTERS)}
              className={styles.map}
            />
          </OverviewSection>
          <AttentionCard attention={attention} className={styles.attentionCard} />
        </div>
        {!summary.isError && (
          <OverviewSection title={OVERVIEW_LABELS.kpi} note={OVERVIEW_LABELS.kpiCompare} card={false}>
            {data ? <KpiStrip items={kpiStripItems(data)} label={OVERVIEW_LABELS.kpi} /> : <ContentSkeleton rows={4} />}
          </OverviewSection>
        )}
        <OverviewSection
          title={OVERVIEW_LABELS.incidents}
          link={{ to: '/incidents', label: OVERVIEW_LABELS.incidentsAll }}
        >
          {incidents.isError ? (
            <ErrorState error={incidents.error} onRetry={() => void incidents.refetch()} />
          ) : incidents.isPending ? (
            <ContentSkeleton rows={5} />
          ) : (
            <IncidentTable
              items={incidents.data.items}
              total={incidents.data.total}
              page={LATEST_INCIDENTS.page}
              pageSize={LATEST_INCIDENTS.pageSize}
              loading={incidents.isFetching && incidents.isPlaceholderData}
              empty={
                <EmptyState
                  title={OVERVIEW_LABELS.incidentsEmpty}
                  description={OVERVIEW_LABELS.incidentsEmptyHint}
                />
              }
              pagination={false}
            />
          )}
        </OverviewSection>
      </div>
    </>
  )
}
