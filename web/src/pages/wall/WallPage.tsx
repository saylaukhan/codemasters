import { ConfigProvider } from 'antd'
import { Activity } from 'lucide-react'
import { useEffect, useLayoutEffect, useMemo, useState } from 'react'
import { Navigate, useNavigate } from 'react-router'

import { useMediaQuery } from '../../app/useMediaQuery'
import { ThemeModeContext, useThemeMode } from '../../app/themeMode'
import { NOTIFICATION_STATUS } from '../../components/notifications/notifications'
import { useNotifications } from '../../components/notifications/queries'
import { NO_FILTERS } from '../../components/map/filters'
import { REFRESH_MS, useRegionBoundaries, useSchoolMap } from '../../components/map/queries'
import { SchoolMapView } from '../../components/map/SchoolMapView'
import { AttentionCard } from '../../components/overview/AttentionCard'
import { useDashboardAttention, useDashboardSummary } from '../../components/overview/queries'
import { kpiStripItems, noDataFootnote, statusStripItems } from '../../components/overview/strips'
import { overviewVerdict, selectedSchools } from '../../components/overview/verdict'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { ErrorState } from '../../components/ui/ErrorState'
import { KpiStrip } from '../../components/ui/KpiStrip'
import { StatusStrip } from '../../components/ui/StatusStrip'
import { APP_NAME } from '../../lib/app-info'
import { formatDate, formatNumber, formatTime, plural } from '../../lib/format'
import {
  OVERVIEW_LABELS,
  SCHOOL_COUNT_FORMS,
  WALL_LABELS,
  WHOLE_OBLAST_SCOPE_LABEL,
} from '../../lib/labels'
import { COMPACT_SCREEN, darkTheme, SIZES } from '../../styles/theme'
import { tickerEvents, WALL_CLOCK_MS, wallKpiItems } from './wall'
import styles from './WallPage.module.css'

/** Where Esc and a screen narrower than the wall both lead: the landing of the role (T-44). */
const PANEL_PATH = '/'

/** The wall has no theme switch of its own: the subtree is dark and stays dark. */
const WALL_THEME = { mode: 'dark' as const, toggle: () => {} }

/** The map of the wall is shown whole: there is nothing to reset, because there are no filters. */
const NO_RESET = () => {}

/**
 * Dark theme for the wall only (DESIGN.md §3.33). The map and the charts read the tokens off
 * `<html>` (`components/map/mapStyle.ts`), so the attribute has to move there; the choice the user
 * made for the panel lives in the browser storage and is never touched — leaving the wall puts the
 * mode of the panel back on the attribute.
 */
function useDarkWall(): void {
  const { mode } = useThemeMode()
  useLayoutEffect(() => {
    const root = document.documentElement
    root.dataset.theme = 'dark'
    return () => {
      root.dataset.theme = mode
    }
  }, [mode])
}

/** Esc returns to the panel: the only control of the screen (docs/design/README.md §6.6). */
function useEscapeToPanel(): void {
  const navigate = useNavigate()
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') navigate(PANEL_PATH)
    }
    window.addEventListener('keydown', onKeyDown)
    return () => window.removeEventListener('keydown', onKeyDown)
  }, [navigate])
}

/** Clock of the header: the wall shows no seconds, so it is redrawn twice a minute. */
function useClock(): Date {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), WALL_CLOCK_MS)
    return () => clearInterval(timer)
  }, [])
  return now
}

/**
 * The wall itself: the verdict and the status strip of the main screen, the map of the oblast,
 * «Требуют внимания», four KPIs and the line of the latest events of the stream of T-42. Every
 * query is the one the panel asks and refreshes itself every 60 seconds (`REFRESH_MS`).
 */
function WallScreen() {
  useDarkWall()
  useEscapeToPanel()
  const now = useClock()
  const summary = useDashboardSummary(NO_FILTERS)
  const attention = useDashboardAttention(NO_FILTERS)
  const schools = useSchoolMap(NO_FILTERS)
  const regions = useRegionBoundaries()
  // The bell of the panel waits for the stream; the wall has no bell, so it asks for the page again.
  const notifications = useNotifications('all', REFRESH_MS)

  const data = summary.data
  const events = useMemo(() => tickerEvents(notifications.data?.items ?? []), [notifications.data])
  const judged = data ? selectedSchools(data) : 0
  const context = data
    ? OVERVIEW_LABELS.context(WHOLE_OBLAST_SCOPE_LABEL, formatNumber(judged, 0), plural(judged, SCHOOL_COUNT_FORMS))
    : WHOLE_OBLAST_SCOPE_LABEL

  return (
    <ThemeModeContext.Provider value={WALL_THEME}>
      <ConfigProvider theme={darkTheme}>
        <div className={styles.wall}>
          <header className={styles.header}>
            <div className={styles.brand}>
              <span className={styles.mark} aria-hidden>
                <Activity size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} />
              </span>
              <span className={styles.brandText}>
                <span className={styles.brandName}>{APP_NAME}</span>
                <span className={styles.caption}>{context}</span>
              </span>
            </div>
            <h1 className={styles.verdict}>{overviewVerdict(data)}</h1>
            <div className={styles.clock}>
              <span className={styles.time}>{formatTime(now)}</span>
              <span className={styles.caption}>
                {data ? `${formatDate(now)} · ${WALL_LABELS.updated(formatTime(data.periodTo))}` : formatDate(now)}
              </span>
            </div>
          </header>

          {summary.isError ? (
            <ErrorState error={summary.error} onRetry={() => void summary.refetch()} />
          ) : data ? (
            <StatusStrip
              items={statusStripItems(data, NO_FILTERS)}
              label={OVERVIEW_LABELS.statusStrip}
              footnote={noDataFootnote(data)}
            />
          ) : (
            <ContentSkeleton rows={2} />
          )}

          <div className={styles.main}>
            <div className={styles.mapCard} aria-label={OVERVIEW_LABELS.map}>
              <SchoolMapView
                schools={schools}
                regions={regions.data}
                filters={NO_FILTERS}
                onReset={NO_RESET}
                className={styles.map}
              />
            </div>
            <AttentionCard attention={attention} className={styles.aside} />
          </div>

          {data && <KpiStrip items={wallKpiItems(kpiStripItems(data))} label={OVERVIEW_LABELS.kpi} />}

          <div className={styles.ticker}>
            <span className={styles.tickerLabel}>{WALL_LABELS.ticker}</span>
            {events.length === 0 ? (
              <span className={styles.caption}>{WALL_LABELS.tickerEmpty}</span>
            ) : (
              events.map((event) => (
                <span key={event.id} className={styles.event}>
                  <span className={styles.eventTime}>{formatTime(event.createdAt)}</span>
                  <span className={styles.dot} data-status={NOTIFICATION_STATUS[event.kind]} aria-hidden />
                  {`${event.schoolName} · ${event.title}`}
                </span>
              ))
            )}
            <span className={styles.hint}>{WALL_LABELS.hint}</span>
          </div>
        </div>
      </ConfigProvider>
    </ThemeModeContext.Provider>
  )
}

/**
 * Wall for the situation room (T-71, DESIGN.md §3.33, docs/design/README.md §6.6): a route outside
 * the shell of the panel. The composition is laid out for 1920 × 1080; below 1280px there is no
 * wall to show, so the route sends the browser back to the panel.
 */
export function WallPage() {
  const compact = useMediaQuery(COMPACT_SCREEN)
  if (compact) return <Navigate to={PANEL_PATH} replace />
  return <WallScreen />
}
