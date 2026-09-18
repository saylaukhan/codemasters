// Series of the school chart (T-25): Download and Upload on the left axis, Ping on the right one,
// with the thresholds of the report and the contract speed of the main line as dashed marks.
import type { AnalyticsReport, LineDetail } from '../../api/types'
import { MS_UNIT, SPEED_UNIT, formatMs, formatSpeed } from '../../lib/format'
import type { ChartMark, TimeChartData } from '../ui/chartOption'

const SPEED_AXIS = 0
const PING_AXIS = 1

export function speedChart(report: AnalyticsReport, mainLine: LineDetail | undefined): TimeChartData {
  const points = report.series
  const marks: ChartMark[] = [
    {
      axis: SPEED_AXIS,
      value: report.thresholds.downloadMinMbps,
      label: `Порог ${formatSpeed(report.thresholds.downloadMinMbps)}`,
    },
    { axis: PING_AXIS, value: report.thresholds.pingMaxMs, label: `Порог ${formatMs(report.thresholds.pingMaxMs)}` },
  ]
  const contract = mainLine?.contractDownMbps
  if (contract != null) {
    marks.push({ axis: SPEED_AXIS, value: contract, label: `Договор ${formatSpeed(contract)}` })
  }
  return {
    moments: points.map((point) => point.bucketStart),
    step: report.granularity,
    axes: [
      { unit: SPEED_UNIT, digits: 1 },
      { unit: MS_UNIT, digits: 0 },
    ],
    series: [
      { name: 'Download', axis: SPEED_AXIS, values: points.map((point) => point.avgDownloadMbps) },
      { name: 'Upload', axis: SPEED_AXIS, values: points.map((point) => point.avgUploadMbps) },
      { name: 'Ping', axis: PING_AXIS, values: points.map((point) => point.avgPingMs) },
    ],
    marks,
  }
}
