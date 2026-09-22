// Heatmap «час × день недели» of the school card (T-28, ТЗ п. 5): the heatmap cells of the report —
// hours of `m_hourly` summed over the period, Asia/Almaty — as a matrix of 7 days by 24 hours.
import type { AnalyticsReport } from '../../api/types'
import { WEEKDAY_LABELS, WEEKDAY_ORDER } from '../../lib/labels'
import type { HeatmapChartData } from '../ui/heatmapOption'

type Cell = AnalyticsReport['heatmap'][number]

const HOURS = 24

/** Rows Monday → Sunday, columns 0 → 23 hours; null — nothing measured in that hour of that day. */
export function heatmapMatrix(cells: readonly Cell[]): (Cell | null)[][] {
  const matrix = WEEKDAY_ORDER.map(() => new Array<Cell | null>(HOURS).fill(null))
  for (const cell of cells) {
    const row = WEEKDAY_ORDER.indexOf(cell.weekday)
    if (row >= 0 && cell.hour >= 0 && cell.hour < HOURS) matrix[row][cell.hour] = cell
  }
  return matrix
}

const hour = (value: number) => `${String(value).padStart(2, '0')}:00`

/** «из 1 замера», «из 21 замера», but «из 11 замеров», «из 12 замеров». */
const measurements = (count: number) =>
  `${count} ${count % 10 === 1 && count % 100 !== 11 ? 'замера' : 'замеров'}`

/** Share of problem measurements per hour of a weekday over the period of the report. */
export function problemHeatmap(report: AnalyticsReport): HeatmapChartData {
  return {
    kind: 'heatmap',
    name: 'Проблемные замеры',
    columns: Array.from({ length: HOURS }, (_, column) => String(column).padStart(2, '0')),
    rows: WEEKDAY_ORDER.map((day) => WEEKDAY_LABELS[day]),
    // Hours a phone keeps (DESIGN.md §9.3, row «Тепловая карта»): the school day, 08:00–17:00.
    compactRange: [8, 17],
    cells: heatmapMatrix(report.heatmap).map((cells, row) =>
      cells.map(
        (cell, column) =>
          cell && {
            value: cell.problemPct,
            title: `${WEEKDAY_LABELS[WEEKDAY_ORDER[row]]}, ${hour(column)}–${hour(column + 1)}`,
            note: `${cell.problemCount} из ${measurements(cell.measurementsCount)}`,
          },
      ),
    ),
  }
}
