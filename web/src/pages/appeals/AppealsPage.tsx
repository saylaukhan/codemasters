import { Select } from 'antd'
import { SearchX } from 'lucide-react'
import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'

import type { IncidentStatus } from '../../api/types'
import { useProviderHint } from '../../app/useProviderHint'
import styles from '../../components/appeals/Appeal.module.css'
import {
  isAppealFiltered,
  readAppealListView,
  writeAppealListView,
  type AppealListView,
} from '../../components/appeals/appeals'
import { AppealTable } from '../../components/appeals/AppealTable'
import { useAppeals } from '../../components/appeals/queries'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { SearchInput } from '../../components/ui/SearchInput'
import {
  APPEAL_COLUMN_LABELS,
  APPEAL_LABELS,
  APPEAL_STATUS_LABELS,
  INCIDENT_STATUS_ORDER,
  PROVIDER_SCOPE_HINTS,
  SECTION_LABELS,
} from '../../lib/labels'

const STATUS_OPTIONS = INCIDENT_STATUS_ORDER.map((status) => ({ value: status, label: APPEAL_STATUS_LABELS[status] }))

function useAppealListView(): [AppealListView, (view: AppealListView) => void] {
  const [params, setParams] = useSearchParams()
  const view = useMemo(() => readAppealListView(params), [params])
  const setView = useCallback(
    (next: AppealListView) => setParams((current) => writeAppealListView(current, next), { replace: true }),
    [setParams],
  )
  return [view, setView]
}

/**
 * Sent appeals of the scope (ТЗ п. 17): filters by status and number in the URL, newest first. The provider sees
 * only the appeals of his own lines — that is the scope of the API, the screen only says so (T-44, ADR-008).
 */
export function AppealsPage() {
  const [view, setView] = useAppealListView()
  const appeals = useAppeals(view)
  const providerHint = useProviderHint(PROVIDER_SCOPE_HINTS.appeals)

  const reset = () => setView({ statuses: [], q: '', page: 1, pageSize: view.pageSize })

  const empty = isAppealFiltered(view) ? (
    <EmptyState
      icon={SearchX}
      title={APPEAL_LABELS.filteredEmpty}
      description={APPEAL_LABELS.filteredEmptyHint}
      action={<Button onClick={reset}>Сбросить фильтры</Button>}
    />
  ) : (
    <EmptyState title={APPEAL_LABELS.empty} description={APPEAL_LABELS.emptyHint} />
  )

  return (
    <>
      <PageHeader title={SECTION_LABELS.appeals} subtitle={providerHint} />
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder={APPEAL_LABELS.search}
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
        <Select<IncidentStatus[]>
          className={styles.statusFilter}
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          aria-label={APPEAL_COLUMN_LABELS.status}
          placeholder="Все статусы"
          options={STATUS_OPTIONS}
          value={view.statuses}
          onChange={(statuses) =>
            setView({ ...view, statuses: INCIDENT_STATUS_ORDER.filter((status) => statuses.includes(status)), page: 1 })
          }
        />
        {isAppealFiltered(view) && (
          <Button kind="link" onClick={reset}>
            Сбросить
          </Button>
        )}
      </div>
      {appeals.isError ? (
        <ErrorState error={appeals.error} onRetry={() => void appeals.refetch()} />
      ) : appeals.isPending ? (
        <ContentSkeleton />
      ) : (
        <AppealTable
          items={appeals.data.items}
          total={appeals.data.total}
          page={view.page}
          pageSize={view.pageSize}
          loading={appeals.isFetching && appeals.isPlaceholderData}
          empty={empty}
          onPageChange={(page, pageSize) => setView({ ...view, page, pageSize })}
        />
      )}
    </>
  )
}
