import { SearchX } from 'lucide-react'
import { useSearchParams } from 'react-router'

import { useProviderHint } from '../../app/useProviderHint'
import { MapFilterBar } from '../../components/map/MapFilterBar'
import { isFiltered, NO_FILTERS, writeFilters } from '../../components/map/filters'
import { useMapFilterOptions } from '../../components/map/queries'
import { useMapFilters } from '../../components/map/useMapFilters'
import { useSchoolList } from '../../components/schools/queries'
import { SchoolTable } from '../../components/schools/SchoolTable'
import { useSchoolListView } from '../../components/schools/useSchoolListView'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { PROVIDER_SCOPE_HINTS, SECTION_LABELS } from '../../lib/labels'

/** List of schools (ТЗ п. 4): averages for the last 24 hours, the last measurement and the status. */
export function SchoolsPage() {
  const [filters, setFilters] = useMapFilters()
  const [view, setView] = useSchoolListView()
  const [, setParams] = useSearchParams()
  const options = useMapFilterOptions()
  const schools = useSchoolList(filters, view)
  const providerHint = useProviderHint(PROVIDER_SCOPE_HINTS.schools)

  const empty = isFiltered(filters) ? (
    <EmptyState
      icon={SearchX}
      title="Школ по фильтрам нет"
      description="Измените или сбросьте фильтры."
      action={<Button onClick={() => setFilters(NO_FILTERS)}>Сбросить фильтры</Button>}
    />
  ) : (
    <EmptyState title="Школ пока нет" description="В вашей области видимости нет ни одной школы." />
  )

  return (
    <>
      <PageHeader title={SECTION_LABELS.schools} subtitle={providerHint} />
      <MapFilterBar
        filters={filters}
        options={options.data}
        onChange={(next) =>
          setParams(
            (current) => {
              const updated = writeFilters(next, current)
              updated.delete('page')
              return updated
            },
            { replace: true },
          )
        }
      />
      {schools.isError ? (
        <ErrorState error={schools.error} onRetry={() => void schools.refetch()} />
      ) : schools.isPending ? (
        <ContentSkeleton />
      ) : (
        <SchoolTable
          items={schools.data.items}
          total={schools.data.total}
          view={view}
          loading={schools.isFetching && schools.isPlaceholderData}
          empty={empty}
          onChange={setView}
        />
      )}
    </>
  )
}
