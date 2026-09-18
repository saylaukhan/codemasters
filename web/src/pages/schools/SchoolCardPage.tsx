import { usePermissions } from '@refinedev/core'
import { Alert, Segmented, Tabs } from 'antd'
import { Construction, SearchX } from 'lucide-react'
import type { ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { AnalyticsPeriod } from '../../api/types'
import { ContactList } from '../../components/schools/ContactList'
import { ContractFact } from '../../components/schools/ContractFact'
import { DeviceTable } from '../../components/schools/DeviceTable'
import { problemHeatmap } from '../../components/schools/heatmap'
import { LineTable } from '../../components/schools/LineTable'
import {
  useSchool,
  useSchoolAnalytics,
  useSchoolContacts,
  useSchoolDevices,
  useSchoolLines,
} from '../../components/schools/queries'
import styles from '../../components/schools/SchoolCard.module.css'
import { SchoolKpis } from '../../components/schools/SchoolKpis'
import { speedChart } from '../../components/schools/speedChart'
import { ChartCard } from '../../components/ui/Chart'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { ConnectionStatusBadge } from '../../components/ui/StatusBadge'
import { formatDateTime } from '../../lib/format'
import { IFACE_LABELS, PERIOD_LABELS, SECTION_LABELS } from '../../lib/labels'

type Period = keyof typeof PERIOD_LABELS

const PERIODS = Object.keys(PERIOD_LABELS) as Period[]
const DEFAULT_PERIOD: Period = 'week'
const TABS = ['overview', 'lines', 'devices', 'incidents', 'appeals', 'contacts'] as const
type Tab = (typeof TABS)[number]

/** One query of a tab in its three states (DESIGN.md §3.21). */
function TabState<T>({
  query,
  empty,
  children,
}: {
  query: { isPending: boolean; isError: boolean; error: unknown; data: T | undefined; refetch: () => unknown }
  empty: (data: T) => ReactNode | null
  children: (data: T) => ReactNode
}) {
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  if (query.isPending || query.data === undefined) return <ContentSkeleton />
  return empty(query.data) ?? children(query.data)
}

const upcoming = (title: string) => (
  <EmptyState
    icon={Construction}
    title={title}
    description="Раздел карточки появится в ближайшем обновлении панели."
  />
)

/** Card of a school (ТЗ п. 4, п. 13–15; DESIGN.md §3.15): state, chart, lines, computers, contacts. */
export function SchoolCardPage() {
  const schoolId = Number(useParams().schoolId)
  const [params, setParams] = useSearchParams()
  const period = PERIODS.includes(params.get('period') as Period) ? (params.get('period') as Period) : DEFAULT_PERIOD
  const tab = TABS.includes(params.get('tab') as Tab) ? (params.get('tab') as Tab) : 'overview'
  const setParam = (name: string, value: string) =>
    setParams(
      (current) => {
        const updated = new URLSearchParams(current)
        updated.set(name, value)
        return updated
      },
      { replace: true },
    )

  const school = useSchool(schoolId)
  const analytics = useSchoolAnalytics(schoolId, period satisfies Exclude<AnalyticsPeriod, 'custom'>)
  const lines = useSchoolLines(schoolId)
  const devices = useSchoolDevices(schoolId)
  const contacts = useSchoolContacts(schoolId)
  const { data: permissions } = usePermissions<string[]>({})

  if (school.isError) {
    if (school.error instanceof ApiError && school.error.status === 404) {
      return (
        <EmptyState icon={SearchX} title="Школа не найдена" description="Её нет или она вне вашей области видимости." />
      )
    }
    return <ErrorState error={school.error} onRetry={() => void school.refetch()} />
  }
  if (school.isPending) return <ContentSkeleton rows={8} />

  const card = school.data
  const latest = card.latestMeasurement
  const row = analytics.data?.rows[0]
  const mainLine = lines.data?.items.find((line) => line.status === 'main')
  const chart = analytics.data ? speedChart(analytics.data, mainLine) : undefined
  const heatmap = analytics.data ? problemHeatmap(analytics.data) : undefined

  const chartPlaceholder = (empty: boolean) =>
    analytics.isError ? (
      <ErrorState error={analytics.error} onRetry={() => void analytics.refetch()} />
    ) : analytics.isPending ? (
      <ContentSkeleton rows={6} />
    ) : empty ? (
      <EmptyState title="Замеров за период нет" description="Выберите другой период или проверьте агент на ПК школы." />
    ) : undefined
  // Both charts follow one period: the KPI of availability and the contract block use it too.
  const periodControl = (
    <Segmented<Period>
      size="small"
      value={period}
      options={PERIODS.map((value) => ({ value, label: PERIOD_LABELS[value] }))}
      onChange={(value) => setParam('period', value)}
    />
  )

  const overview = (
    <>
      <ChartCard
        title="Скорость и задержка"
        fileName={`${card.schoolCode}-${period}`}
        data={chart}
        placeholder={chartPlaceholder(analytics.data?.series.length === 0)}
        controls={periodControl}
      />
      <div className={styles.charts}>
        <ChartCard
          title="Проблемные замеры по часам"
          fileName={`${card.schoolCode}-${period}-hours`}
          data={heatmap}
          placeholder={chartPlaceholder(analytics.data?.heatmap.length === 0)}
          controls={periodControl}
          height={280}
        />
        {lines.isError || analytics.isError ? (
          <ErrorState
            error={lines.error ?? analytics.error}
            onRetry={() => {
              void lines.refetch()
              void analytics.refetch()
            }}
          />
        ) : lines.isPending || analytics.isPending ? (
          <ContentSkeleton rows={4} />
        ) : (
          <ContractFact line={mainLine} row={row} periodLabel={PERIOD_LABELS[period]} />
        )}
      </div>
    </>
  )

  return (
    <>
      <PageHeader
        title={card.fullName}
        breadcrumbs={[{ title: SECTION_LABELS.schools, path: '/schools' }, { title: card.fullName }]}
        subtitle={
          <span className={styles.meta}>
            <span className={styles.code}>{card.schoolCode}</span>
            <span>·</span>
            <span>{card.regionName}</span>
            {card.address && (
              <>
                <span>·</span>
                <span>{card.address}</span>
              </>
            )}
          </span>
        }
        actions={<ConnectionStatusBadge status={card.status} />}
      />
      {!card.isActive && (
        <Alert className={styles.alert} type="info" showIcon message="Школа отключена от мониторинга, история сохранена" />
      )}
      {card.onReserveLine && (
        <Alert
          className={styles.alert}
          type="warning"
          showIcon
          message="Замеры идут через резервную линию: основная недоступна"
        />
      )}
      <p className={styles.caption}>
        {latest
          ? `Текущие показатели · замер ${formatDateTime(latest.measuredAt)}${
              latest.ifaceType ? ` · ${IFACE_LABELS[latest.ifaceType]}` : ''
            }`
          : 'Текущие показатели · замеров основной линии ещё нет'}
      </p>
      <SchoolKpis
        latest={latest}
        availabilityPct={row?.availabilityPct}
        availabilityMinPct={analytics.data?.availabilityMinPct}
        periodLabel={PERIOD_LABELS[period]}
        loading={false}
      />
      <Tabs
        activeKey={tab}
        onChange={(key) => setParam('tab', key)}
        items={[
          { key: 'overview', label: 'Обзор', children: overview },
          {
            key: 'lines',
            label: 'Линии и договор',
            children: (
              <TabState
                query={lines}
                empty={(data) =>
                  data.items.length ? null : <EmptyState title="Линий нет" description="Линии заводятся в админке." />
                }
              >
                {(data) => <LineTable items={data.items} />}
              </TabState>
            ),
          },
          {
            key: 'devices',
            label: 'Устройства',
            children: (
              <TabState
                query={devices}
                empty={(data) =>
                  data.items.length ? null : (
                    <EmptyState title="Компьютеров нет" description="Агент ещё не установлен ни на один ПК школы." />
                  )
                }
              >
                {(data) => <DeviceTable items={data.items} />}
              </TabState>
            ),
          },
          { key: 'incidents', label: 'Инциденты', children: upcoming('Инциденты школы') },
          { key: 'appeals', label: 'Обращения', children: upcoming('Обращения школы') },
          {
            key: 'contacts',
            label: 'Контакты',
            children: (
              <TabState
                query={contacts}
                empty={(data) =>
                  data.items.length ? null : (
                    <EmptyState title="Контактов нет" description="Ответственный за связь ещё не указан." />
                  )
                }
              >
                {(data) => (
                  <ContactList items={data.items} canSeePhone={permissions?.includes('contacts:phone') ?? false} />
                )}
              </TabState>
            ),
          },
        ]}
      />
    </>
  )
}
