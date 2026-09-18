import { useState } from 'react'

import { PAGE_SIZES } from '../schools/useSchoolListView'
import { ContentSkeleton } from '../ui/ContentSkeleton'
import { EmptyState } from '../ui/EmptyState'
import { ErrorState } from '../ui/ErrorState'
import { IncidentTable } from './IncidentTable'
import { useSchoolIncidents } from './queries'

/** Tab «Инциденты» of the school card (ТЗ п. 19): the incidents of its lines, newest first. */
export function SchoolIncidents({ schoolId }: { schoolId: number }) {
  const [view, setView] = useState<{ page: number; pageSize: number }>({ page: 1, pageSize: PAGE_SIZES[0] })
  const incidents = useSchoolIncidents(schoolId, view.page, view.pageSize)

  if (incidents.isError) return <ErrorState error={incidents.error} onRetry={() => void incidents.refetch()} />
  if (incidents.isPending) return <ContentSkeleton />
  return (
    <IncidentTable
      items={incidents.data.items}
      total={incidents.data.total}
      page={view.page}
      pageSize={view.pageSize}
      loading={incidents.isFetching && incidents.isPlaceholderData}
      empty={
        <EmptyState
          title="Инцидентов нет"
          description="Инцидент открывается по правилу детекции или вручную, если проблему заметили люди."
        />
      }
      onPageChange={(page, pageSize) => setView({ page, pageSize })}
      showSchool={false}
    />
  )
}
