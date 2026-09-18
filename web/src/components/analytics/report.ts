// Pure functions over the analytics report (T-27): totals of the selection, the rating of the rows
// and the chart data of «Часы ухудшения» and «Сравнение школ».
import type { AnalyticsReport, AnalyticsRow } from '../../api/types'
import { MS_UNIT, SPEED_UNIT } from '../../lib/format'
import type { TimeChartData } from '../ui/chartOption'

type Point = AnalyticsReport['series'][number]

export interface ReportTotals {
  measurementsCount: number
  problemPct: number | null
  avgDownloadMbps: number | null
  avgUploadMbps: number | null
  avgPingMs: number | null
}

/** Average of the points weighted by their number of measurements; null when nothing has a value. */
function weighted(points: readonly Point[], value: (point: Point) => number | null): number | null {
  let sum = 0
  let weight = 0
  for (const point of points) {
    const metric = value(point)
    if (metric === null) continue
    sum += metric * point.measurementsCount
    weight += point.measurementsCount
  }
  return weight ? sum / weight : null
}

/** Totals over the whole selection of the filters, from the series of the report. */
export function reportTotals(report: AnalyticsReport): ReportTotals {
  const measurementsCount = report.series.reduce((sum, point) => sum + point.measurementsCount, 0)
  const problemCount = report.series.reduce((sum, point) => sum + point.problemCount, 0)
  return {
    measurementsCount,
    problemPct: measurementsCount ? (problemCount / measurementsCount) * 100 : null,
    avgDownloadMbps: weighted(report.series, (point) => point.avgDownloadMbps),
    avgUploadMbps: weighted(report.series, (point) => point.avgUploadMbps),
    avgPingMs: weighted(report.series, (point) => point.avgPingMs),
  }
}

export interface RankedRow extends AnalyticsRow {
  /** Place in the rating: 1 — the fewest problem measurements; null — no measurements in the period. */
  rank: number | null
}

/**
 * Rating of the rows (ТЗ п. 5): by the share of problem measurements, then by availability and
 * by the number of measurements; rows without measurements have no place and go last.
 */
export function rankRows(rows: readonly AnalyticsRow[]): RankedRow[] {
  const rated = rows
    .filter((row) => row.problemPct !== null)
    .sort(
      (a, b) =>
        (a.problemPct ?? 0) - (b.problemPct ?? 0) ||
        (b.availabilityPct ?? -1) - (a.availabilityPct ?? -1) ||
        b.measurementsCount - a.measurementsCount,
    )
  const places = new Map(rated.map((row, index) => [row, index + 1]))
  return rows
    .map((row) => ({ ...row, rank: places.get(row) ?? null }))
    .sort((a, b) => (a.rank ?? Infinity) - (b.rank ?? Infinity))
}

const HOURS = Array.from({ length: 24 }, (_, hour) => hour)
const hourCaption = (hour: number) => `${String(hour).padStart(2, '0')}:00`

/** «Часы ухудшения»: share of problem measurements per hour of the day over all days of the period. */
export function hoursChart(report: AnalyticsReport): TimeChartData {
  const measured = new Array<number>(24).fill(0)
  const problems = new Array<number>(24).fill(0)
  for (const cell of report.heatmap) {
    measured[cell.hour] += cell.measurementsCount
    problems[cell.hour] += cell.problemCount
  }
  return {
    moments: HOURS.map(hourCaption),
    step: 'category',
    axes: [{ unit: '%', digits: 1 }],
    series: [
      {
        name: 'Проблемные замеры',
        axis: 0,
        kind: 'bar',
        values: HOURS.map((hour) => (measured[hour] ? (problems[hour] / measured[hour]) * 100 : null)),
      },
    ],
    marks: [],
  }
}

export interface ComparedSchool {
  name: string
  report: AnalyticsReport
}

/** Download and Ping of two schools on one time axis: buckets of either school, in order. */
export function compareChart(schools: readonly ComparedSchool[]): TimeChartData {
  const moments = [...new Set(schools.flatMap((school) => school.report.series.map((point) => point.bucketStart)))].sort(
    (a, b) => Date.parse(a) - Date.parse(b),
  )
  const values = (school: ComparedSchool, metric: (point: Point) => number | null) => {
    const byMoment = new Map(school.report.series.map((point) => [point.bucketStart, metric(point)]))
    return moments.map((moment) => byMoment.get(moment) ?? null)
  }
  return {
    moments,
    step: schools[0]?.report.granularity ?? 'day',
    axes: [
      { unit: SPEED_UNIT, digits: 1 },
      { unit: MS_UNIT, digits: 0 },
    ],
    series: [
      ...schools.map((school) => ({
        name: `Download · ${school.name}`,
        axis: 0,
        values: values(school, (point) => point.avgDownloadMbps),
      })),
      ...schools.map((school) => ({
        name: `Ping · ${school.name}`,
        axis: 1,
        values: values(school, (point) => point.avgPingMs),
      })),
    ],
    marks: [],
  }
}
