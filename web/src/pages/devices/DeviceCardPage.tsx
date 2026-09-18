import { Alert, Segmented } from 'antd'
import { SearchX } from 'lucide-react'
import { useParams, useSearchParams } from 'react-router'

import { ApiError } from '../../api/client'
import { schoolCardPath } from '../../app/sections'
import deviceStyles from '../../components/devices/DeviceCard.module.css'
import { MeasurementTable } from '../../components/devices/MeasurementTable'
import { HISTORY_DAYS, useDevice, useDeviceMeasurements, type HistoryPeriod } from '../../components/devices/queries'
import styles from '../../components/schools/SchoolCard.module.css'
import { SchoolKpis } from '../../components/schools/SchoolKpis'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { ConnectionStatusBadge } from '../../components/ui/StatusBadge'
import { NO_VALUE, formatDateTime, formatRelative } from '../../lib/format'
import { DEVICE_STATUS_LABELS, IFACE_LABELS, LINE_STATUS_LABELS, PERIOD_LABELS, SECTION_LABELS } from '../../lib/labels'

const PERIODS = Object.keys(HISTORY_DAYS) as HistoryPeriod[]
const DEFAULT_PAGE_SIZE = 20

const positive = (value: string | null, fallback: number): number => {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

/** Card of a computer (ТЗ п. 4): identity, place, last contact, current values and the history. */
export function DeviceCardPage() {
  const deviceId = Number(useParams().deviceId)
  const [params, setParams] = useSearchParams()
  const period = PERIODS.includes(params.get('period') as HistoryPeriod) ? (params.get('period') as HistoryPeriod) : 'week'
  const page = positive(params.get('page'), 1)
  const pageSize = positive(params.get('pageSize'), DEFAULT_PAGE_SIZE)
  const setView = (values: Record<string, string | number>) =>
    setParams(
      (current) => {
        const updated = new URLSearchParams(current)
        for (const [name, value] of Object.entries(values)) updated.set(name, String(value))
        return updated
      },
      { replace: true },
    )

  const device = useDevice(deviceId)
  const history = useDeviceMeasurements(deviceId, { period, page, pageSize })

  if (device.isError) {
    if (device.error instanceof ApiError && device.error.status === 404) {
      return (
        <EmptyState
          icon={SearchX}
          title="Компьютер не найден"
          description="Его нет или он вне вашей области видимости."
        />
      )
    }
    return <ErrorState error={device.error} onRetry={() => void device.refetch()} />
  }
  if (device.isPending) return <ContentSkeleton rows={8} />

  const card = device.data
  const name = card.hostname ?? card.deviceUid
  const latest = card.latestMeasurement
  const pairs: [string, string][] = [
    ['Device ID', String(card.id)],
    ['Идентификатор агента', card.deviceUid],
    ['Название', card.hostname ?? NO_VALUE],
    ['Кабинет', card.room ?? NO_VALUE],
    ['Точка мониторинга', card.monitoringPointName],
    ['Линия', LINE_STATUS_LABELS[card.lineStatus]],
    ['Последняя связь', card.lastSeenAt ? `${formatRelative(card.lastSeenAt)} · ${formatDateTime(card.lastSeenAt)}` : NO_VALUE],
    ['Версия агента', card.agentVersion ?? NO_VALUE],
    ['ОС', card.os ?? NO_VALUE],
    ['Зарегистрирован', formatDateTime(card.registeredAt)],
  ]

  return (
    <>
      <PageHeader
        title={name}
        breadcrumbs={[
          { title: SECTION_LABELS.schools, path: '/schools' },
          { title: card.schoolName, path: `${schoolCardPath(card.schoolId)}?tab=devices` },
          { title: name },
        ]}
        subtitle={
          <span className={styles.meta}>
            <span className={styles.code}>{card.deviceUid}</span>
            <span>·</span>
            <span className={styles.code}>{card.schoolCode}</span>
            <span>·</span>
            <span>{card.room ?? card.monitoringPointName}</span>
          </span>
        }
        actions={<ConnectionStatusBadge status={card.currentStatus} />}
      />
      {card.status === 'blocked' && (
        <Alert
          className={styles.alert}
          type="info"
          showIcon
          message={`${DEVICE_STATUS_LABELS.blocked}: запросы агента отклоняются, история сохранена`}
        />
      )}
      <p className={styles.caption}>
        {latest
          ? `Последний замер · ${formatDateTime(latest.measuredAt)}${
              latest.ifaceType ? ` · ${IFACE_LABELS[latest.ifaceType]}` : ''
            }`
          : 'Последний замер · замеров ещё нет'}
      </p>
      <SchoolKpis latest={latest} loading={false} />
      <dl className={deviceStyles.details}>
        {pairs.map(([label, value]) => (
          <div key={label} className={deviceStyles.pair}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
      <div className={deviceStyles.historyHeader}>
        <h2 className={deviceStyles.historyTitle}>История замеров</h2>
        <Segmented<HistoryPeriod>
          size="small"
          value={period}
          options={PERIODS.map((value) => ({ value, label: PERIOD_LABELS[value] }))}
          onChange={(value) => setView({ period: value, page: 1 })}
        />
      </div>
      {history.isError ? (
        <ErrorState error={history.error} onRetry={() => void history.refetch()} />
      ) : history.isPending ? (
        <ContentSkeleton rows={6} />
      ) : history.data.total === 0 ? (
        <EmptyState title="Замеров за период нет" description="Выберите другой период или проверьте агент на этом ПК." />
      ) : (
        <MeasurementTable
          items={history.data.items}
          total={history.data.total}
          page={page}
          pageSize={pageSize}
          loading={history.isFetching}
          onPageChange={(next, size) => setView({ page: size === pageSize ? next : 1, pageSize: size })}
        />
      )}
    </>
  )
}
