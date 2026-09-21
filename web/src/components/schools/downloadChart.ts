// Series of the cabinet chart «Скорость загрузки за 7 дней» (T-61, DESIGN.md §3.27): one line, the
// download alone. `speedChart` of the school card always draws three series on two axes, which the
// director does not need, so the cabinet has its own builder next to it.
import type { AnalyticsReport, LineDetail } from '../../api/types'
import { formatSpeed, SPEED_UNIT } from '../../lib/format'
import { CABINET_LABELS, CABINET_TERM_LABELS } from '../../lib/labels'
import type { ChartMark, TimeChartData } from '../ui/chartOption'

const SPEED_AXIS = 0

export function downloadChart(report: AnalyticsReport, mainLine: LineDetail | undefined): TimeChartData {
  const points = report.series
  const marks: ChartMark[] = [
    {
      axis: SPEED_AXIS,
      value: report.thresholds.downloadMinMbps,
      label: `${CABINET_LABELS.norm} ${formatSpeed(report.thresholds.downloadMinMbps)}`,
    },
  ]
  const contract = mainLine?.contractDownMbps
  if (contract != null) {
    marks.push({ axis: SPEED_AXIS, value: contract, label: `${CABINET_LABELS.contractMark} ${formatSpeed(contract)}` })
  }
  return {
    moments: points.map((point) => point.bucketStart),
    step: report.granularity,
    axes: [{ unit: SPEED_UNIT, digits: 1 }],
    series: [{ name: CABINET_TERM_LABELS.download, axis: SPEED_AXIS, values: points.map((point) => point.avgDownloadMbps) }],
    marks,
  }
}
