import { useNotification, usePermissions } from '@refinedev/core'
import { FileDown, Mail, SearchX } from 'lucide-react'
import type { ReactNode } from 'react'
import { useNavigate, useParams } from 'react-router'

import { ApiError } from '../../api/client'
import { appealDraftPath, deviceCardPath } from '../../app/sections'
import { useMediaQuery } from '../../app/useMediaQuery'
import { APPEAL_CREATE_PERMISSION, appealTargetQuery, schoolAppealTarget } from '../../components/appeals/appeals'
import { useSchoolAppeals } from '../../components/appeals/queries'
import { useBuildExport } from '../../components/exports/queries'
import { useSchoolIncidents } from '../../components/incidents/queries'
import { CabinetAgent } from '../../components/schools/CabinetAgent'
import { CabinetContacts } from '../../components/schools/CabinetContacts'
import { CabinetContract } from '../../components/schools/CabinetContract'
import { CabinetDays } from '../../components/schools/CabinetDays'
import { CabinetProblems } from '../../components/schools/CabinetProblems'
import { CabinetTiles } from '../../components/schools/CabinetTiles'
import {
  CABINET_DAYS,
  cabinetProblems,
  cabinetTiles,
  cabinetVerdict,
  isToday,
} from '../../components/schools/cabinet'
import { downloadChart } from '../../components/schools/downloadChart'
import { schoolReportBody } from '../../components/schools/report'
import styles from '../../components/schools/SchoolCabinet.module.css'
import { Button } from '../../components/ui/Button'
import { ChartCard } from '../../components/ui/Chart'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { PageHeader } from '../../components/ui/PageHeader'
import {
  useSchool,
  useSchoolAnalytics,
  useSchoolContacts,
  useSchoolDays,
  useSchoolDevices,
  useSchoolLines,
} from '../../components/schools/queries'
import { formatDateTime, formatTime } from '../../lib/format'
import { CABINET_IFACE_LABELS, CABINET_LABELS, CABINET_NOTICE_LABELS, CABINET_VERDICT_LABELS } from '../../lib/labels'
import { PHONE_SCREEN, SIZES } from '../../styles/theme'

/** Every appeal and incident of the school fits on one page of the cabinet. */
const PROBLEMS_PAGE = { page: 1, pageSize: 20 }

interface QueryState {
  isPending: boolean
  isError: boolean
  error: unknown
  refetch: () => unknown
}

/** Three states of one query inside a card (DESIGN.md §2.7); nothing means «draw the data». */
function cardState(query: QueryState, empty: ReactNode, rows = 3): ReactNode | undefined {
  if (query.isError) return <ErrorState error={query.error} onRetry={() => void query.refetch()} />
  if (query.isPending) return <ContentSkeleton rows={rows} />
  return empty ?? undefined
}

/**
 * Cabinet of the school (T-61, ТЗ п. 16, DESIGN.md §3.27): the verdict in words, the three tiles,
 * the month of days, the week of the download, the provider, the computer with the agent, the
 * problems and whom to call. The same address `/schools/:schoolId` shows the card of T-25 to every
 * other role; a school outside the scope answers 404 here as it does there.
 */
export function SchoolCabinetPage() {
  const schoolId = Number(useParams().schoolId)
  const phone = useMediaQuery(PHONE_SCREEN)
  const school = useSchool(schoolId)
  const days = useSchoolDays(schoolId, CABINET_DAYS)
  const analytics = useSchoolAnalytics(schoolId, 'week')
  const lines = useSchoolLines(schoolId)
  const devices = useSchoolDevices(schoolId)
  const contacts = useSchoolContacts(schoolId)
  const incidents = useSchoolIncidents(schoolId, PROBLEMS_PAGE.page, PROBLEMS_PAGE.pageSize)
  const appeals = useSchoolAppeals(schoolId)
  const { data: permissions } = usePermissions<string[]>({})
  const canCreateAppeal = permissions?.includes(APPEAL_CREATE_PERMISSION) ?? false
  const canSeePhone = permissions?.includes('contacts:phone') ?? false
  // The PDF is built by the worker (T-33): the cabinet waits for it for a minute, then it is in «Экспорт».
  const report = useBuildExport(60_000)
  const { open } = useNotification()
  const navigate = useNavigate()

  if (school.isError) {
    if (school.error instanceof ApiError && school.error.status === 404) {
      return (
        <EmptyState
          icon={SearchX}
          title={CABINET_NOTICE_LABELS.notFound}
          description={CABINET_NOTICE_LABELS.notFoundHint}
        />
      )
    }
    return <ErrorState error={school.error} onRetry={() => void school.refetch()} />
  }
  if (school.isPending) return <ContentSkeleton rows={8} />

  const card = school.data
  const latest = card.latestMeasurement
  const mainLine = lines.data?.items.find((line) => line.status === 'main')
  // A letter goes to the provider of one line: the main one, or the first that is not switched off (ТЗ п. 10).
  const appealLine = mainLine ?? lines.data?.items.find((line) => line.status !== 'disabled')
  const device = devices.data?.items.find((item) => item.lineId === mainLine?.id) ?? devices.data?.items[0]
  const support = contacts.data?.items.find((contact) => contact.providerSupportContact)
  const verdict = cabinetVerdict(card.status, latest, mainLine?.contractDownMbps)

  const checked = latest
    ? `${isToday(latest.measuredAt) ? `${CABINET_LABELS.checkedToday} ${formatTime(latest.measuredAt)}` : `${CABINET_LABELS.checked} ${formatDateTime(latest.measuredAt)}`}${
        latest.ifaceType ? ` · ${CABINET_IFACE_LABELS[latest.ifaceType]}` : ''
      }`
    : CABINET_LABELS.neverChecked

  const daysCard = (
    <CabinetDays
      days={days.data?.days ?? []}
      placeholder={cardState(
        days,
        days.data?.days.length === 0 ? <EmptyState title={CABINET_NOTICE_LABELS.noDays} /> : null,
      )}
    />
  )
  const weekCard = (
    <ChartCard
      title={CABINET_LABELS.week}
      fileName={`${card.schoolCode}-week`}
      data={analytics.data ? downloadChart(analytics.data, mainLine) : undefined}
      height={200}
      placeholder={cardState(
        analytics,
        analytics.data?.series.length === 0 ? (
          <EmptyState title={CABINET_NOTICE_LABELS.noWeek} description={CABINET_NOTICE_LABELS.noWeekHint} />
        ) : null,
        6,
      )}
    />
  )
  const contractCard = (
    <CabinetContract
      line={mainLine}
      supportPhone={(canSeePhone && support?.providerSupportContact) || null}
      placeholder={cardState(lines, mainLine ? null : <EmptyState title={CABINET_NOTICE_LABELS.noLine} />)}
    />
  )
  const agentCard = (
    <CabinetAgent
      device={device}
      placeholder={cardState(
        devices,
        device ? null : (
          <EmptyState title={CABINET_NOTICE_LABELS.noDevice} description={CABINET_NOTICE_LABELS.noDeviceHint} />
        ),
      )}
    />
  )
  const problemsCard = (
    <CabinetProblems
      problems={cabinetProblems(incidents.data?.items ?? [], appeals.data?.items ?? [])}
      historyHref="/appeals"
      placeholder={
        cardState(incidents, null) ??
        cardState(appeals, null) ??
        (incidents.data?.items.length === 0 && appeals.data?.items.length === 0 ? (
          <EmptyState title={CABINET_NOTICE_LABELS.noProblems} description={CABINET_NOTICE_LABELS.noProblemsHint} />
        ) : undefined)
      }
    />
  )
  const contactsCard = (
    <CabinetContacts
      items={contacts.data?.items ?? []}
      providerName={mainLine?.providerName}
      supportPhone={(canSeePhone && support?.providerSupportContact) || null}
      placeholder={cardState(
        contacts,
        contacts.data?.items.length === 0 ? <EmptyState title={CABINET_NOTICE_LABELS.noContacts} /> : null,
      )}
    />
  )

  return (
    <div className={styles.page}>
      <p className={styles.context}>
        {card.fullName} · {card.regionName}
        <span className={styles.contextCode}>
          {' · '}
          <span className={styles.code}>{card.schoolCode}</span>
        </span>
      </p>
      <PageHeader
        title={
          <span className={styles.verdict}>
            <span className={styles.dot} data-status={card.status} aria-hidden />
            {verdict.since
              ? `${CABINET_VERDICT_LABELS[verdict.key]} ${formatTime(verdict.since)}`
              : CABINET_VERDICT_LABELS[verdict.key]}
          </span>
        }
        subtitle={checked}
        actions={
          <Button
            kind="outlined"
            icon={<FileDown size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
            loading={report.isPending}
            onClick={() =>
              report.mutate(schoolReportBody(schoolId, 'month'), {
                onSuccess: ({ saved }) =>
                  !saved &&
                  open?.({
                    type: 'success',
                    message: CABINET_NOTICE_LABELS.reportPending,
                    description: CABINET_NOTICE_LABELS.reportPendingHint,
                  }),
                onError: (error) =>
                  open?.({
                    type: 'error',
                    message: CABINET_NOTICE_LABELS.reportFailed,
                    description: error instanceof ApiError ? (error.detail ?? error.title) : error.message,
                  }),
              })
            }
          >
            {CABINET_LABELS.report}
          </Button>
        }
        stickyAction={
          canCreateAppeal && (
            <Button
              kind="action"
              icon={<Mail size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
              disabled={appealLine === undefined}
              tooltip={appealLine === undefined ? CABINET_NOTICE_LABELS.noAppealLine : undefined}
              aria-label={CABINET_LABELS.reportProblem}
              onClick={() =>
                appealLine && navigate(appealDraftPath(appealTargetQuery(schoolAppealTarget(schoolId, appealLine.id))))
              }
            >
              {CABINET_LABELS.reportProblem}
            </Button>
          )
        }
      />
      <CabinetTiles
        tiles={cabinetTiles(latest, mainLine)}
        latest={latest}
        availabilityPct={analytics.isPending ? undefined : analytics.data?.rows[0]?.availabilityPct}
        measurementsHref={device ? deviceCardPath(device.id) : undefined}
      />
      {phone ? (
        <>
          {daysCard}
          {problemsCard}
          {contractCard}
          {agentCard}
        </>
      ) : (
        <>
          <div className={styles.pair}>
            {daysCard}
            {weekCard}
          </div>
          <div className={styles.pair}>
            {contractCard}
            {agentCard}
          </div>
          {problemsCard}
        </>
      )}
      {contactsCard}
    </div>
  )
}
