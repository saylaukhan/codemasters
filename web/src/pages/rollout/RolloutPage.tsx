import { useNotification, usePermissions } from '@refinedev/core'
import { Popconfirm } from 'antd'
import { useState } from 'react'
import { Link } from 'react-router'

import { ApiError } from '../../api/client'
import type { RolloutFilter, RolloutRegionRow, RolloutSchoolItem } from '../../api/rollout'
import { schoolCardPath } from '../../app/sections'
import { EnrollmentCodeButton } from '../../components/admin/EnrollmentCodeButton'
import { OverviewSection } from '../../components/overview/OverviewSection'
import { useAssignAgentUpdate, useRolloutSchools, useRolloutSummary } from '../../components/rollout/queries'
import {
  listCount,
  rolloutDescription,
  rolloutKpiItems,
  rolloutReason,
  rolloutVerdict,
  ROLLOUT_FILTERS,
} from '../../components/rollout/rollout'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { FilterBar, FilterChip } from '../../components/ui/FilterBar'
import { KpiStrip } from '../../components/ui/KpiStrip'
import { PageHeader } from '../../components/ui/PageHeader'
import { ResponsiveTable, type ResponsiveColumn } from '../../components/ui/ResponsiveTable'
import { formatNumber, formatPercent, formatTime, plural } from '../../lib/format'
import {
  ROLLOUT_COLUMN_LABELS,
  ROLLOUT_FILTER_LABELS,
  ROLLOUT_LABELS,
  SCHOOL_COUNT_FORMS,
  WHOLE_OBLAST_SCOPE_LABEL,
} from '../../lib/labels'
import styles from './RolloutPage.module.css'

const REGION_COLUMNS: ResponsiveColumn<RolloutRegionRow>[] = [
  { key: 'region', title: ROLLOUT_COLUMN_LABELS.region, priority: 'primary', render: (_, row) => row.regionName },
  {
    key: 'schools',
    title: ROLLOUT_COLUMN_LABELS.schools,
    align: 'right',
    render: (_, row) => <span className={styles.number}>{formatNumber(row.schoolsCount, 0)}</span>,
  },
  {
    key: 'connected',
    title: ROLLOUT_COLUMN_LABELS.connected,
    align: 'right',
    render: (_, row) => <span className={styles.number}>{formatNumber(row.schoolsConnectedCount, 0)}</span>,
  },
  {
    key: 'alive',
    title: ROLLOUT_COLUMN_LABELS.alive,
    align: 'right',
    priority: 'minor',
    render: (_, row) => <span className={styles.number}>{formatNumber(row.devicesAliveCount, 0)}</span>,
  },
  {
    key: 'share',
    title: ROLLOUT_COLUMN_LABELS.share,
    align: 'right',
    priority: 'primary',
    render: (_, row) => <span className={styles.number}>{formatPercent(row.connectedPct, 0)}</span>,
  },
]

/** Columns of a list: the school, why it is here and what to do with it (docs/design/README.md §6.4). */
const schoolColumns = (filter: RolloutFilter): ResponsiveColumn<RolloutSchoolItem>[] => [
  {
    key: 'school',
    title: ROLLOUT_COLUMN_LABELS.school,
    priority: 'primary',
    render: (_, item) => (
      <span className={styles.stack}>
        <Link to={schoolCardPath(item.schoolId)}>{item.schoolName}</Link>
        <span className={styles.muted}>{item.regionName}</span>
      </span>
    ),
  },
  {
    key: 'reason',
    title: ROLLOUT_COLUMN_LABELS.reason,
    priority: 'primary',
    render: (_, item) => rolloutReason(item, filter),
  },
  {
    key: 'devices',
    title: ROLLOUT_COLUMN_LABELS.devices,
    align: 'right',
    priority: 'minor',
    render: (_, item) => (
      <span className={styles.number}>{`${formatNumber(item.devicesAliveCount, 0)} / ${formatNumber(item.devicesCount, 0)}`}</span>
    ),
  },
  {
    key: 'action',
    title: '',
    align: 'right',
    render: (_, item) => (filter === 'old_version' ? null : <EnrollmentCodeButton schoolId={item.schoolId} />),
  },
]

/**
 * Section «Внедрение» (T-69, DESIGN.md §3.30, docs/design/README.md §6.4): the verdict «350 из 366 школ
 * подключены», the strip of the progress, the four lists of schools that wait for a person and the table of
 * districts with their share. «Выдать код» opens the installation code of T-36; «Назначить обновление» hands the
 * current release to the computers of the scope through the channel of T-50.
 */
export function RolloutPage() {
  const [filter, setFilter] = useState<RolloutFilter>('not_connected')
  const summary = useRolloutSummary()
  const schools = useRolloutSchools(filter)
  const assign = useAssignAgentUpdate()
  const { data: permissions } = usePermissions<string[]>({})
  const { open: notify } = useNotification()

  const data = summary.data
  const version = data?.targetVersion ?? null
  const mayAssign = permissions?.includes('devices:manage') === true

  const assignAction = mayAssign && (
    <Popconfirm
      title={ROLLOUT_LABELS.assignConfirmTitle(version ?? '')}
      description={ROLLOUT_LABELS.assignConfirmText}
      okText={ROLLOUT_LABELS.assignConfirmOk}
      cancelText={ROLLOUT_LABELS.assignConfirmCancel}
      disabled={version === null}
      onConfirm={() =>
        version !== null &&
        assign.mutate(
          { version, deviceIds: null, regionId: null },
          {
            onSuccess: (result) =>
              notify?.({
                type: 'success',
                message: ROLLOUT_LABELS.assigned(
                  formatNumber(result.devicesChangedCount, 0),
                  plural(result.devicesChangedCount, ROLLOUT_LABELS.deviceForms),
                ),
                description: ROLLOUT_LABELS.release(result.version),
              }),
            onError: (error) =>
              notify?.({
                type: 'error',
                message: ROLLOUT_LABELS.assignFailed,
                description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
              }),
          },
        )
      }
    >
      <Button
        kind="action"
        loading={assign.isPending}
        disabled={version === null}
        tooltip={version === null ? ROLLOUT_LABELS.assignNoRelease : undefined}
      >
        {version === null ? ROLLOUT_LABELS.assign : `${ROLLOUT_LABELS.assign} ${version}`}
      </Button>
    </Popconfirm>
  )

  return (
    <>
      <PageHeader
        context={ROLLOUT_LABELS.context(WHOLE_OBLAST_SCOPE_LABEL)}
        title={rolloutVerdict(data)}
        subtitle={
          data &&
          ROLLOUT_LABELS.subtitle(formatNumber(data.devicesAliveCount, 0), formatTime(data.asOf))
        }
        stickyAction={assignAction}
      />
      <div className={styles.page}>
        <OverviewSection
          title={ROLLOUT_LABELS.progress}
          note={version === null ? ROLLOUT_LABELS.noRelease : ROLLOUT_LABELS.release(version)}
          card={false}
        >
          {summary.isError ? (
            <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
          ) : data ? (
            <KpiStrip items={rolloutKpiItems(data)} label={ROLLOUT_LABELS.progress} />
          ) : (
            <ContentSkeleton rows={4} />
          )}
        </OverviewSection>
        <OverviewSection title={ROLLOUT_LABELS.lists} count={schools.data?.total}>
          <FilterBar label={ROLLOUT_LABELS.lists}>
            {ROLLOUT_FILTERS.map((key) => (
              <FilterChip
                key={key}
                label={ROLLOUT_FILTER_LABELS[key]}
                value={key === filter ? formatNumber(listCount(data, key) ?? 0, 0) : undefined}
                onClick={() => setFilter(key)}
              />
            ))}
          </FilterBar>
          {schools.isError ? (
            <ErrorState error={schools.error} onRetry={() => void schools.refetch()} />
          ) : schools.isPending ? (
            <ContentSkeleton rows={5} />
          ) : (
            <ResponsiveTable<RolloutSchoolItem>
              rowKey="schoolId"
              size="middle"
              columns={schoolColumns(filter)}
              dataSource={schools.data.items}
              loading={schools.isFetching && schools.isPlaceholderData}
              scroll={{ x: 'max-content' }}
              pagination={false}
              locale={{
                emptyText: (
                  <EmptyState
                    title={ROLLOUT_LABELS.emptyTitle}
                    description={ROLLOUT_LABELS.emptyDescription}
                  />
                ),
              }}
              card={{
                title: (item) => <Link to={schoolCardPath(item.schoolId)}>{item.schoolName}</Link>,
                description: (item) => rolloutDescription(item, filter),
                action: (item) =>
                  filter === 'old_version' ? null : <EnrollmentCodeButton schoolId={item.schoolId} />,
              }}
            />
          )}
        </OverviewSection>
        <OverviewSection
          title={ROLLOUT_LABELS.regions}
          note={
            data &&
            `${formatNumber(data.schoolsCount, 0)} ${plural(data.schoolsCount, SCHOOL_COUNT_FORMS)}`
          }
        >
          {data ? (
            <ResponsiveTable<RolloutRegionRow>
              rowKey="regionId"
              size="middle"
              columns={REGION_COLUMNS}
              dataSource={data.regions}
              scroll={{ x: 'max-content' }}
              pagination={false}
              card={{
                title: (row) => row.regionName,
                description: (row) =>
                  `${formatPercent(row.connectedPct, 0)} · ${formatNumber(row.schoolsConnectedCount, 0)} / ${formatNumber(row.schoolsCount, 0)}`,
              }}
            />
          ) : (
            <ContentSkeleton rows={5} />
          )}
        </OverviewSection>
      </div>
    </>
  )
}
