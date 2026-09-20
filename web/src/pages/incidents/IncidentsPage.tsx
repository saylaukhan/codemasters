import { DatePicker, Segmented, Select } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { SearchX } from 'lucide-react'
import { useCallback, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router'

import type { IncidentStatus } from '../../api/types'
import styles from '../../components/incidents/Incident.module.css'
import {
  isFiltered,
  readIncidentListView,
  writeIncidentListView,
  type IncidentListView,
} from '../../components/incidents/incidents'
import { IncidentBoard } from '../../components/incidents/IncidentBoard'
import { IncidentTable } from '../../components/incidents/IncidentTable'
import {
  BOARD_PAGE_SIZE,
  initialIncidentView,
  rememberIncidentView,
} from '../../components/incidents/kanban'
import { useIncidents } from '../../components/incidents/queries'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { SearchInput } from '../../components/ui/SearchInput'
import {
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_ORDER,
  INCIDENT_VIEW_LABELS,
  SECTION_LABELS,
  type IncidentViewKey,
} from '../../lib/labels'

const DAY_FORMAT = 'YYYY-MM-DD'

const STATUS_OPTIONS = INCIDENT_STATUS_ORDER.map((status) => ({ value: status, label: INCIDENT_STATUS_LABELS[status] }))

const VIEW_OPTIONS = Object.entries(INCIDENT_VIEW_LABELS).map(([value, label]) => ({
  value: value as IncidentViewKey,
  label,
}))

function useIncidentListView(): [IncidentListView, (view: IncidentListView) => void] {
  const [params, setParams] = useSearchParams()
  const view = useMemo(() => readIncidentListView(params), [params])
  const setView = useCallback(
    (next: IncidentListView) => setParams((current) => writeIncidentListView(current, next), { replace: true }),
    [setParams],
  )
  return [view, setView]
}

/**
 * Incidents of the scope (ТЗ п. 19): filters by status, number and start in the URL, newest first. The list of T-41
 * or the kanban of T-43 (DESIGN.md §3.18); the chosen view is remembered in the browser, the board takes one page of
 * the same filter.
 */
export function IncidentsPage() {
  const [view, setView] = useIncidentListView()
  const [mode, setMode] = useState<IncidentViewKey>(initialIncidentView)
  const incidents = useIncidents(mode === 'board' ? { ...view, page: 1, pageSize: BOARD_PAGE_SIZE } : view)

  const chooseMode = (next: IncidentViewKey) => {
    setMode(next)
    rememberIncidentView(next)
  }

  const period: [Dayjs, Dayjs] | null = view.days ? [dayjs(view.days[0]), dayjs(view.days[1])] : null
  const reset = () => setView({ statuses: [], q: '', days: undefined, page: 1, pageSize: view.pageSize })

  const empty = isFiltered(view) ? (
    <EmptyState
      icon={SearchX}
      title="По заданным фильтрам ничего не найдено"
      description="Измените или сбросьте фильтры."
      action={<Button onClick={reset}>Сбросить фильтры</Button>}
    />
  ) : (
    <EmptyState
      title="Инцидентов нет"
      description="Инцидент открывается, когда показатели линии нарушают правило подряд или дольше заданного."
    />
  )

  return (
    <>
      <PageHeader title={SECTION_LABELS.incidents} />
      <div className={styles.toolbar}>
        <SearchInput
          className={styles.search}
          value={view.q}
          placeholder="Поиск по номеру инцидента"
          onSearch={(q) => setView({ ...view, q, page: 1 })}
        />
        <Select<IncidentStatus[]>
          className={styles.statusFilter}
          mode="multiple"
          allowClear
          maxTagCount="responsive"
          aria-label="Статус"
          placeholder="Все статусы"
          options={STATUS_OPTIONS}
          value={view.statuses}
          onChange={(statuses) =>
            setView({ ...view, statuses: INCIDENT_STATUS_ORDER.filter((status) => statuses.includes(status)), page: 1 })
          }
        />
        <DatePicker.RangePicker
          aria-label="Начало инцидента"
          placeholder={['Начало с', 'по']}
          format="DD.MM.YYYY"
          value={period}
          disabledDate={(day) => day.isAfter(dayjs(), 'day')}
          onChange={(range) =>
            setView({
              ...view,
              days: range?.[0] && range[1] ? [range[0].format(DAY_FORMAT), range[1].format(DAY_FORMAT)] : undefined,
              page: 1,
            })
          }
        />
        {isFiltered(view) && (
          <Button kind="link" onClick={reset}>
            Сбросить
          </Button>
        )}
        <Segmented<IncidentViewKey>
          className={styles.viewSwitch}
          aria-label="Вид списка"
          options={VIEW_OPTIONS}
          value={mode}
          onChange={chooseMode}
        />
      </div>
      {incidents.isError ? (
        <ErrorState error={incidents.error} onRetry={() => void incidents.refetch()} />
      ) : incidents.isPending ? (
        <ContentSkeleton />
      ) : mode === 'board' ? (
        <IncidentBoard items={incidents.data.items} total={incidents.data.total} empty={empty} />
      ) : (
        <IncidentTable
          items={incidents.data.items}
          total={incidents.data.total}
          page={view.page}
          pageSize={view.pageSize}
          loading={incidents.isFetching && incidents.isPlaceholderData}
          empty={empty}
          onPageChange={(page, pageSize) => setView({ ...view, page, pageSize })}
        />
      )}
    </>
  )
}
