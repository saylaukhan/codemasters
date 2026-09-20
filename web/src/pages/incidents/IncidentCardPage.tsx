import { useGetIdentity, useNotification } from '@refinedev/core'
import { Steps, Table, type TableProps } from 'antd'
import { Mail, SearchX } from 'lucide-react'
import { Fragment, type ReactNode } from 'react'
import { Link, useNavigate, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { CurrentUser, IncidentBasisMetric } from '../../api/types'
import { appealDraftPath, schoolCardPath } from '../../app/sections'
import { appealTargetQuery, canCreateAppeal, incidentAppealTarget } from '../../components/appeals/appeals'
import styles from '../../components/incidents/Incident.module.css'
import { IncidentActivity } from '../../components/incidents/IncidentActivity'
import { durationCaption, formatMetricValue } from '../../components/incidents/incidents'
import { IncidentStatusForm } from '../../components/incidents/IncidentStatusForm'
import { useIncident, useUpdateIncident } from '../../components/incidents/queries'
import { allowedTargets, canUpdate } from '../../components/incidents/transitions'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { IncidentStatusBadge } from '../../components/ui/StatusBadge'
import { formatDateTime, formatDuration, NO_VALUE } from '../../lib/format'
import {
  APPEAL_LABELS,
  INCIDENT_METRIC_LABELS,
  INCIDENT_STATUS_LABELS,
  INCIDENT_STATUS_ORDER,
  LINE_STATUS_LABELS,
  SECTION_LABELS,
} from '../../lib/labels'
import { SIZES } from '../../styles/theme'

// Values and thresholds come from the measurement that opened the incident; a manual one has none (ADR-004).
const BASIS_COLUMNS: TableProps<IncidentBasisMetric>['columns'] = [
  { key: 'metric', title: 'Показатель', render: (_, row) => INCIDENT_METRIC_LABELS[row.metric] },
  {
    key: 'value',
    title: 'Значение',
    align: 'right',
    render: (_, row) => <span className={styles.number}>{formatMetricValue(row.metric, row.value)}</span>,
  },
  {
    key: 'threshold',
    title: 'Порог',
    align: 'right',
    render: (_, row) => <span className={styles.number}>{formatMetricValue(row.metric, row.threshold)}</span>,
  },
]

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.panel} aria-label={title}>
      <h2 className={styles.panelTitle}>{title}</h2>
      {children}
    </section>
  )
}

/**
 * Card of an incident (ТЗ п. 19, DESIGN.md §3.17): the number, the status and the duration, the stepper of the six
 * statuses, the basis metrics, the status change, the history with comments; the school, the line and the time marks
 * on the right.
 */
export function IncidentCardPage() {
  const incidentId = Number(useParams().incidentId)
  const incident = useIncident(incidentId)
  const update = useUpdateIncident(incidentId)
  const { data: user } = useGetIdentity<CurrentUser>()
  const { open: notify } = useNotification()
  const navigate = useNavigate()

  if (incident.isError) {
    if (incident.error instanceof ApiError && incident.error.status === 404) {
      return (
        <EmptyState
          icon={SearchX}
          title="Инцидент не найден"
          description="Его нет или он вне вашей области видимости."
        />
      )
    }
    return <ErrorState error={incident.error} onRetry={() => void incident.refetch()} />
  }
  if (incident.isPending) return <ContentSkeleton rows={8} />

  const card = incident.data
  const current = INCIDENT_STATUS_ORDER.indexOf(card.status)
  const targets = allowedTargets(card.status, user)
  const editable = canUpdate(user)
  const duration = durationCaption(card)

  const assignMe = () =>
    user &&
    update.mutate(
      { responsibleUserId: user.id },
      {
        onSuccess: (saved) =>
          notify?.({ type: 'success', message: 'Вы назначены ответственным', description: saved.number }),
        onError: (error) =>
          notify?.({
            type: 'error',
            message: 'Ответственный не назначен',
            description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
          }),
      },
    )

  const pairs: [string, ReactNode][] = [
    [
      'Школа',
      <span className={styles.stack}>
        <Link to={`${schoolCardPath(card.schoolId)}?tab=incidents`}>{card.schoolName}</Link>
        <span className={`${styles.code} ${styles.muted}`}>{card.schoolCode}</span>
      </span>,
    ],
    ['Линия', LINE_STATUS_LABELS[card.lineStatus]],
    ['Поставщик', card.providerName],
    [
      'Ответственный',
      <span className={styles.responsible}>
        <span>{card.responsibleUserName ?? NO_VALUE}</span>
        {editable && user && user.id !== card.responsibleUserId && card.status !== 'closed' && (
          <Button kind="outlined" size="small" loading={update.isPending} onClick={assignMe}>
            Назначить меня
          </Button>
        )}
      </span>,
    ],
    ['Открыт', card.ruleId === null ? 'Вручную' : 'По правилу детекции'],
    ['Начало', formatDateTime(card.startedAt)],
    ['Последнее нарушение', formatDateTime(card.lastViolationAt)],
    ['Передан поставщику', formatDateTime(card.sentToProviderAt)],
    ['Восстановлено', formatDateTime(card.restoredAt)],
    ['Закрыт', formatDateTime(card.closedAt)],
    ['Длительность', duration],
    ['Реакция поставщика', formatDuration(card.providerReactionS)],
  ]

  return (
    <>
      <PageHeader
        mono
        title={card.number}
        breadcrumbs={[{ title: SECTION_LABELS.incidents, path: '/incidents' }, { title: card.number }]}
        subtitle={
          <span className={styles.meta}>
            <IncidentStatusBadge status={card.status} />
            <span className={styles.number}>{duration}</span>
            <span>·</span>
            <span>{card.schoolName}</span>
          </span>
        }
        actions={
          // The Action of this screen is «Сохранить» of the status form (DESIGN.md §1, rule 2).
          canCreateAppeal(user) && (
            <Button
              icon={<Mail size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
              onClick={() => navigate(appealDraftPath(appealTargetQuery(incidentAppealTarget(card))))}
            >
              {APPEAL_LABELS.create}
            </Button>
          )
        }
      />
      <Steps
        className={styles.steps}
        size="small"
        current={current}
        status={card.status === 'closed' ? 'finish' : 'process'}
        items={INCIDENT_STATUS_ORDER.map((status, index) => ({
          title: (
            <span className={index === current ? styles.current : undefined}>{INCIDENT_STATUS_LABELS[status]}</span>
          ),
        }))}
      />
      <div className={styles.layout}>
        <div className={styles.column}>
          <Panel title="Описание">
            <p className={card.description ? styles.text : `${styles.text} ${styles.muted}`}>
              {card.description ?? 'Описание не указано'}
            </p>
          </Panel>
          <Panel title="Показатели-основания">
            <Table<IncidentBasisMetric>
              rowKey="metric"
              size="small"
              columns={BASIS_COLUMNS}
              dataSource={card.basisMetrics}
              pagination={false}
            />
          </Panel>
          {targets.length > 0 && (
            <Panel title="Смена статуса">
              {/* A new status starts the form over: the chosen target may be gone from the table. */}
              <IncidentStatusForm key={card.status} incidentId={card.id} targets={targets} />
            </Panel>
          )}
          <Panel title="История">
            <IncidentActivity incidentId={card.id} events={card.events} canComment={editable} />
          </Panel>
        </div>
        <div className={styles.column}>
          <Panel title="Сведения">
            <dl className={styles.pairs}>
              {pairs.map(([label, value]) => (
                <Fragment key={label}>
                  <dt>{label}</dt>
                  <dd>{value}</dd>
                </Fragment>
              ))}
            </dl>
          </Panel>
        </div>
      </div>
    </>
  )
}
