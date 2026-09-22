// Pure helpers of the wall of the situation room (T-71, DESIGN.md §3.33): what the ticker at the
// bottom shows and which of the eight KPIs of the main screen stay readable from six metres. The
// numbers themselves are built by the main screen (`components/overview`) and never here.
import type { NotificationListItem } from '../../api/types'
import type { KpiStripItem } from '../../components/ui/KpiStrip'

/** Events the line at the bottom holds; the rest of the page of the T-42 stream is dropped. */
export const WALL_TICKER_LIMIT = 6

/** The clock of the header carries no seconds, so twice a minute is often enough. */
export const WALL_CLOCK_MS = 30_000

/**
 * Four of the eight KPIs of ТЗ п. 4 (`kpiStripItems` of T-60): the room watches the speeds, the
 * response and how many computers answer — the rest of the strip belongs to the main screen.
 */
const WALL_KPI_KEYS: readonly string[] = ['activeDevices', 'avgDownload', 'avgUpload', 'avgPing']

/** Newest first, everything past the limit dropped; the page of the API may come in any order. */
export function tickerEvents(
  items: readonly NotificationListItem[],
  limit: number = WALL_TICKER_LIMIT,
): NotificationListItem[] {
  if (limit <= 0) return []
  return [...items].sort((left, right) => Date.parse(right.createdAt) - Date.parse(left.createdAt)).slice(0, limit)
}

/** The four cells of the wall in the order of `WALL_KPI_KEYS`; a cell the strip lacks is skipped. */
export const wallKpiItems = (items: readonly KpiStripItem[]): KpiStripItem[] =>
  WALL_KPI_KEYS.map((key) => items.find((item) => item.key === key)).filter(
    (item): item is KpiStripItem => item !== undefined,
  )
