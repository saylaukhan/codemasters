// Kanban of incidents (T-43, ТЗ п. 19, DESIGN.md §3.18): the six columns in the fixed order, the grouping of the
// loaded incidents into them and the chosen view of the section remembered in the browser.
import type { IncidentListItem, IncidentStatus } from '../../api/types'
import { INCIDENT_STATUS_ORDER, type IncidentViewKey } from '../../lib/labels'

/** The board shows one page of GET /api/incidents; 100 is the largest the API gives at once (MAX_PAGE_SIZE). */
export const BOARD_PAGE_SIZE = 100

export interface IncidentColumn {
  status: IncidentStatus
  items: IncidentListItem[]
}

/**
 * Incidents by their status, always six columns in the order of ТЗ п. 19: an empty column stays on the board, the
 * order inside a column is the order of the list (newest first).
 */
export function groupByStatus(items: readonly IncidentListItem[]): IncidentColumn[] {
  const columns: IncidentColumn[] = INCIDENT_STATUS_ORDER.map((status) => ({ status, items: [] }))
  const byStatus = new Map(columns.map((column) => [column.status, column.items]))
  for (const item of items) byStatus.get(item.status)?.push(item)
  return columns
}

const STORAGE_KEY = 'vko-monitor.incidents.view'

/** The view chosen last time in this browser; the list is the start value (T-41). */
export function initialIncidentView(): IncidentViewKey {
  try {
    return window.localStorage.getItem(STORAGE_KEY) === 'board' ? 'board' : 'list'
  } catch {
    // Storage may be blocked by the browser: the section opens as a list.
    return 'list'
  }
}

export function rememberIncidentView(view: IncidentViewKey): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, view)
  } catch {
    // Not remembered: the next visit starts from the list again.
  }
}
