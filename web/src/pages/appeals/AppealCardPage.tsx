import { useGetIdentity, useNotification } from '@refinedev/core'
import { Steps } from 'antd'
import { Download, SearchX } from 'lucide-react'
import { Fragment, type ReactNode } from 'react'
import { Link, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import type { CurrentUser } from '../../api/types'
import { incidentCardPath, schoolCardPath } from '../../app/sections'
import styles from '../../components/appeals/Appeal.module.css'
import { appealTargets, periodCaption } from '../../components/appeals/appeals'
import { AppealActivity } from '../../components/appeals/AppealActivity'
import { AppealStatusForm } from '../../components/appeals/AppealStatusForm'
import { useAppeal, useDownloadAppealPdf } from '../../components/appeals/queries'
import { Button } from '../../components/ui/Button'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import { IncidentStatusBadge } from '../../components/ui/StatusBadge'
import { formatDateTime, NO_VALUE } from '../../lib/format'
import {
  APPEAL_DELIVERY_LABELS,
  APPEAL_FIELD_LABELS,
  APPEAL_LABELS,
  APPEAL_NOT_SENT_HINT,
  APPEAL_STATUS_LABELS,
  INCIDENT_STATUS_ORDER,
  SECTION_LABELS,
} from '../../lib/labels'
import { SIZES } from '../../styles/theme'

function Panel({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className={styles.panel} aria-label={title}>
      <h2 className={styles.panelTitle}>{title}</h2>
      {children}
    </section>
  )
}

/**
 * Card of a sent appeal (ТЗ п. 17, DESIGN.md §3.17): the number assigned at sending, the stepper of the six
 * statuses, the letter as it went out with its PDF, the status form and the history; the school, the line and the
 * delivery of the letter on the right. The provider opens the same card from his cabinet (T-44).
 */
export function AppealCardPage() {
  const appealId = Number(useParams().appealId)
  const appeal = useAppeal(appealId)
  const download = useDownloadAppealPdf()
  const { data: user } = useGetIdentity<CurrentUser>()
  const { open: notify } = useNotification()

  if (appeal.isError) {
    if (appeal.error instanceof ApiError && appeal.error.status === 404) {
      return <EmptyState icon={SearchX} title={APPEAL_LABELS.notFound} description={APPEAL_LABELS.notFoundHint} />
    }
    return <ErrorState error={appeal.error} onRetry={() => void appeal.refetch()} />
  }
  if (appeal.isPending) return <ContentSkeleton rows={8} />

  const card = appeal.data
  const context = card.context
  const current = INCIDENT_STATUS_ORDER.indexOf(card.status)
  const targets = appealTargets(card.status, user)
  const delivered = card.deliveryStatus === 'sent'

  const savePdf = () =>
    download.mutate(card, {
      onError: (error) =>
        notify?.({
          type: 'error',
          message: APPEAL_LABELS.pdfFailed,
          description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
        }),
    })

  const pairs: [string, ReactNode][] = [
    [
      APPEAL_FIELD_LABELS.school,
      <span className={styles.stack}>
        <Link to={schoolCardPath(context.schoolId)}>{context.schoolName}</Link>
        <span className={`${styles.code} ${styles.muted}`}>{context.schoolCode}</span>
      </span>,
    ],
    [APPEAL_FIELD_LABELS.provider, context.providerName],
    [
      APPEAL_FIELD_LABELS.line,
      context.lineIdentifier ? <span className={styles.code}>{context.lineIdentifier}</span> : NO_VALUE,
    ],
    [
      APPEAL_FIELD_LABELS.period,
      <span className={styles.number}>{periodCaption(context.periodFrom, context.periodTo)}</span>,
    ],
    [APPEAL_FIELD_LABELS.sentAt, <span className={styles.number}>{formatDateTime(card.sentAt)}</span>],
    [APPEAL_FIELD_LABELS.recipient, card.recipientEmail ?? NO_VALUE],
    [
      APPEAL_FIELD_LABELS.delivery,
      <span className={styles.stack}>
        <span>{APPEAL_DELIVERY_LABELS[card.deliveryStatus]}</span>
        {!delivered && <span className={styles.muted}>{APPEAL_NOT_SENT_HINT}</span>}
      </span>,
    ],
  ]
  if (context.incidentId !== null && context.incidentNumber !== null) {
    pairs.splice(2, 0, [
      APPEAL_FIELD_LABELS.incident,
      <Link className={styles.code} to={incidentCardPath(context.incidentId)}>
        {context.incidentNumber}
      </Link>,
    ])
  }

  return (
    <>
      {/* The Action of this screen is «Сохранить» of the status form (DESIGN.md §1, rule 2). */}
      <PageHeader
        mono
        title={card.number}
        breadcrumbs={[{ title: SECTION_LABELS.appeals, path: '/appeals' }, { title: card.number }]}
        subtitle={
          <span className={styles.meta}>
            <IncidentStatusBadge status={card.status} />
            <span className={styles.number}>{formatDateTime(card.sentAt)}</span>
            <span>·</span>
            <span>{context.schoolName}</span>
          </span>
        }
      />
      <Steps
        className={styles.steps}
        size="small"
        current={current}
        status={card.status === 'closed' ? 'finish' : 'process'}
        items={INCIDENT_STATUS_ORDER.map((status, index) => ({
          title: <span className={index === current ? styles.current : undefined}>{APPEAL_STATUS_LABELS[status]}</span>,
        }))}
      />
      <div className={styles.layout}>
        <div className={styles.column}>
          <Panel title={APPEAL_LABELS.letter}>
            <p className={styles.note}>{card.subject}</p>
            {/* Markdown as the person left it: the line breaks of the letter are kept, nothing renders it (T-48). */}
            <p className={styles.text}>{card.text}</p>
            <div className={styles.panelActions}>
              <Button
                kind="link"
                size="small"
                loading={download.isPending}
                icon={<Download size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
                onClick={savePdf}
              >
                {APPEAL_LABELS.pdf}
              </Button>
            </div>
          </Panel>
          <Panel title={APPEAL_LABELS.userComment}>
            <p className={card.userComment ? styles.text : `${styles.text} ${styles.muted}`}>
              {card.userComment ?? APPEAL_LABELS.noUserComment}
            </p>
          </Panel>
          {targets.length > 0 && (
            <Panel title={APPEAL_LABELS.statusChange}>
              {/* A new status starts the form over: the chosen target may be gone from the table. */}
              <AppealStatusForm key={card.status} appealId={card.id} targets={targets} />
            </Panel>
          )}
          <Panel title={APPEAL_LABELS.history}>
            <AppealActivity events={card.events} />
          </Panel>
        </div>
        <div className={styles.column}>
          <Panel title={APPEAL_LABELS.facts}>
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
