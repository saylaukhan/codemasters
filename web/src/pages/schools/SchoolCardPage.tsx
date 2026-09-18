import { useNotification, usePermissions } from '@refinedev/core'
import { Alert, Segmented, Tabs } from 'antd'
import { Construction, FileDown, Plus, SearchX } from 'lucide-react'
import type { ReactNode } from 'react'
import { useParams, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { AnalyticsPeriod, LineDetail, MonitoringPointDetail, SchoolContactDetail } from '../../api/types'
import { ContactDrawer } from '../../components/admin/ContactDrawer'
import { EnrollmentCodeButton } from '../../components/admin/EnrollmentCodeButton'
import { LineDrawer } from '../../components/admin/LineDrawer'
import { PointDrawer } from '../../components/admin/PointDrawer'
import { useDrawer } from '../../components/admin/useDrawer'
import { useBuildExport } from '../../components/exports/queries'
import { IncidentCreateDrawer } from '../../components/incidents/IncidentCreateDrawer'
import { SchoolIncidents } from '../../components/incidents/SchoolIncidents'
import { CREATE_PERMISSION } from '../../components/incidents/transitions'
import { ContactList } from '../../components/schools/ContactList'
import { ContractFact } from '../../components/schools/ContractFact'
import { DeviceTable } from '../../components/schools/DeviceTable'
import { problemHeatmap } from '../../components/schools/heatmap'
import { LineTable } from '../../components/schools/LineTable'
import { PointTable } from '../../components/schools/PointTable'
import {
  useSchool,
  useSchoolAnalytics,
  useSchoolContacts,
  useSchoolDevices,
  useSchoolLines,
  useSchoolPoints,
} from '../../components/schools/queries'
import { schoolReportBody } from '../../components/schools/report'
import styles from '../../components/schools/SchoolCard.module.css'
import { SchoolKpis } from '../../components/schools/SchoolKpis'
import { speedChart } from '../../components/schools/speedChart'
import { Button } from '../../components/ui/Button'
import { ChartCard } from '../../components/ui/Chart'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { ConnectionStatusBadge } from '../../components/ui/StatusBadge'
import { formatDateTime } from '../../lib/format'
import { IFACE_LABELS, PERIOD_LABELS, SECTION_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'

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

/** Outlined «Добавить …» of a tab (DESIGN.md §1, rule 2): the Action of the card is in its header. */
const addButton = (label: string, onClick: () => void, disabled = false) => (
  <Button
    kind="outlined"
    icon={<Plus size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
    disabled={disabled}
    onClick={onClick}
  >
    {label}
  </Button>
)

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
  const points = useSchoolPoints(schoolId)
  const { data: permissions } = usePermissions<string[]>({})
  // Область and Администратор set up the lines, points and contacts right in the card (T-35).
  const canEdit = permissions?.includes('schools:write') ?? false
  // Администратор issues installation codes of the agent (T-36, plan.md §4.1).
  const canManageDevices = permissions?.includes('devices:manage') ?? false
  // Район/город, Область and Администратор open an incident by hand when people notice a problem (T-41).
  const canCreateIncident = permissions?.includes(CREATE_PERMISSION) ?? false
  const lineDrawer = useDrawer<LineDetail>()
  const pointDrawer = useDrawer<MonitoringPointDetail>()
  const contactDrawer = useDrawer<SchoolContactDetail>()
  const incidentDrawer = useDrawer()
  // The PDF is built by the worker (T-33): the card waits for it for a minute, then it is in «Экспорт».
  const report = useBuildExport(60_000)
  const { open } = useNotification()

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
        actions={
          <>
            <ConnectionStatusBadge status={card.status} />
            {/* «Создать обращение» becomes the Action of the card with appeals (T-45…T-48). */}
            <Button
              icon={<FileDown size={16} />}
              loading={report.isPending}
              onClick={() =>
                report.mutate(schoolReportBody(schoolId, period), {
                  onSuccess: ({ saved }) =>
                    !saved &&
                    open?.({
                      type: 'success',
                      message: 'Отчёт ещё готовится',
                      description: 'Скачайте его в разделе «Экспорт», когда он будет готов.',
                    }),
                  onError: (error) =>
                    open?.({
                      type: 'error',
                      message: 'Отчёт не сформирован',
                      description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
                    }),
                })
              }
            >
              Отчёт PDF
            </Button>
          </>
        }
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
              <>
                {canEdit && <div className={styles.toolbar}>{addButton('Добавить линию', () => lineDrawer.show())}</div>}
                <TabState
                  query={lines}
                  empty={(data) =>
                    data.items.length ? null : (
                      <EmptyState
                        title="Линий нет"
                        description={canEdit ? 'Добавьте основную линию школы.' : 'Линии заводит администратор.'}
                      />
                    )
                  }
                >
                  {(data) => <LineTable items={data.items} onEdit={canEdit ? lineDrawer.show : undefined} />}
                </TabState>
                <div className={styles.section}>
                  <h3 className={styles.sectionTitle}>Точки мониторинга</h3>
                  {canEdit && addButton('Добавить точку', () => pointDrawer.show(), !lines.data?.items.length)}
                </div>
                <TabState
                  query={points}
                  empty={(data) =>
                    data.items.length ? null : (
                      <EmptyState
                        title="Точек мониторинга нет"
                        description="Без точки агент не сможет зарегистрироваться на ПК школы."
                      />
                    )
                  }
                >
                  {(data) => <PointTable items={data.items} onEdit={canEdit ? pointDrawer.show : undefined} />}
                </TabState>
              </>
            ),
          },
          {
            key: 'devices',
            label: 'Устройства',
            children: (
              <>
                {canManageDevices && (
                  <div className={styles.toolbar}>
                    <EnrollmentCodeButton schoolId={schoolId} />
                  </div>
                )}
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
              </>
            ),
          },
          {
            key: 'incidents',
            label: 'Инциденты',
            children: (
              <>
                {canCreateIncident && (
                  <div className={styles.toolbar}>
                    {addButton(
                      'Создать инцидент',
                      () => incidentDrawer.show(),
                      !lines.data?.items.some((line) => line.status !== 'disabled'),
                    )}
                  </div>
                )}
                <SchoolIncidents schoolId={schoolId} />
              </>
            ),
          },
          { key: 'appeals', label: 'Обращения', children: upcoming('Обращения школы') },
          {
            key: 'contacts',
            label: 'Контакты',
            children: (
              <>
                {canEdit && (
                  <div className={styles.toolbar}>{addButton('Добавить контакт', () => contactDrawer.show())}</div>
                )}
                <TabState
                  query={contacts}
                  empty={(data) =>
                    data.items.length ? null : (
                      <EmptyState title="Контактов нет" description="Ответственный за связь ещё не указан." />
                    )
                  }
                >
                  {(data) => (
                    <ContactList
                      items={data.items}
                      canSeePhone={permissions?.includes('contacts:phone') ?? false}
                      onEdit={canEdit ? contactDrawer.show : undefined}
                    />
                  )}
                </TabState>
              </>
            ),
          },
        ]}
      />
      {canCreateIncident && (
        <IncidentCreateDrawer
          key={`incident-${incidentDrawer.key}`}
          open={incidentDrawer.open}
          lines={lines.data?.items ?? []}
          onClose={incidentDrawer.close}
        />
      )}
      {canEdit && (
        <>
          <LineDrawer
            key={`line-${lineDrawer.key}`}
            schoolId={schoolId}
            open={lineDrawer.open}
            line={lineDrawer.item}
            newStatus={mainLine ? 'reserve' : 'main'}
            onClose={lineDrawer.close}
          />
          <PointDrawer
            key={`point-${pointDrawer.key}`}
            schoolId={schoolId}
            open={pointDrawer.open}
            point={pointDrawer.item}
            lines={lines.data?.items ?? []}
            onClose={pointDrawer.close}
          />
          <ContactDrawer
            key={`contact-${contactDrawer.key}`}
            schoolId={schoolId}
            open={contactDrawer.open}
            contact={contactDrawer.item}
            onClose={contactDrawer.close}
          />
        </>
      )}
    </>
  )
}
