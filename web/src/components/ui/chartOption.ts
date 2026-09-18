// Option of the ECharts line chart (DESIGN.md §2.4 / §3.16) and its CSV: pure functions of the
// chart data, apart from reading the colors of tokens.css at the moment the option is built.
import type { EChartsCoreOption } from 'echarts/core'

import { formatDate, formatDateTime, formatDayMonth, formatNumber, formatTime } from '../../lib/format'

// Byte order mark: Excel reads a CSV with it as UTF-8, so Cyrillic survives.
const BOM = '\uFEFF'

const SERIES_TOKENS = [
  '--chart-series-1',
  '--chart-series-2',
  '--chart-series-3',
  '--chart-series-4',
  '--chart-series-5',
  '--chart-series-6',
]

export const token = (name: string): string => getComputedStyle(document.documentElement).getPropertyValue(name).trim()

export interface ChartAxis {
  unit: string
  /** Digits after the comma in labels and the tooltip. */
  digits: number
}

export interface ChartSeries {
  name: string
  /** Index in `axes`: 0 — left, 1 — right. */
  axis: number
  /** One value per moment; `null` — nothing measured then. */
  values: readonly (number | null)[]
}

/** Dashed line of a threshold or a contract value, captioned at the right edge («Порог 20 Мбит/с»). */
export interface ChartMark {
  axis: number
  value: number
  label: string
}

export interface TimeChartData {
  /** Start of every bucket, RFC 3339. */
  moments: readonly string[]
  /** Bucket width: the axis shows «14:00» for hours and «12.09» for days. */
  step: 'hour' | 'day'
  axes: readonly ChartAxis[]
  series: readonly ChartSeries[]
  marks: readonly ChartMark[]
}

const axisLabel = (data: TimeChartData, moment: string) =>
  data.step === 'hour' ? formatTime(moment) : formatDayMonth(moment)
const tooltipTitle = (data: TimeChartData, moment: string) =>
  data.step === 'hour' ? formatDateTime(moment) : formatDate(moment)

interface TooltipItem {
  dataIndex: number
  seriesIndex: number
  color: string
}

export function buildOption(data: TimeChartData): EChartsCoreOption {
  const muted = token('--text-muted')
  const textStyle = { color: muted, fontSize: 12 }
  const markStyle = {
    silent: true,
    symbol: 'none',
    lineStyle: { type: 'dashed', width: 1, color: token('--chart-threshold') },
  }
  const format = (value: number | null, axis: number) => {
    const { unit, digits } = data.axes[axis]
    return value === null ? '—' : `${formatNumber(value, digits)} ${unit}`
  }
  return {
    color: SERIES_TOKENS.map(token),
    backgroundColor: 'transparent',
    animation: false,
    textStyle: { fontFamily: token('--font-sans') },
    grid: { left: 8, right: 8, top: 48, bottom: 8, containLabel: true },
    legend: {
      left: 0,
      top: 0,
      icon: 'circle',
      itemWidth: 8,
      itemHeight: 8,
      textStyle: { color: token('--text-secondary'), fontSize: 13 },
    },
    tooltip: {
      trigger: 'axis',
      backgroundColor: token('--bg-surface'),
      borderColor: token('--border'),
      borderWidth: 1,
      padding: [8, 12],
      textStyle: { color: token('--text-primary'), fontSize: 13 },
      extraCssText: 'border-radius: 12px; box-shadow: 0 4px 16px rgba(31, 35, 40, 0.12);',
      formatter: (items: TooltipItem[]) => {
        if (items.length === 0) return ''
        const rows = items.map((item) => {
          const series = data.series[item.seriesIndex]
          const dot = `<span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${item.color};margin-right:8px"></span>`
          return `<div>${dot}${series.name}: <b>${format(series.values[item.dataIndex], series.axis)}</b></div>`
        })
        return `<div style="margin-bottom:4px">${tooltipTitle(data, data.moments[items[0].dataIndex])}</div>${rows.join('')}`
      },
    },
    xAxis: {
      type: 'category',
      data: data.moments.map((moment) => axisLabel(data, moment)),
      boundaryGap: false,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: token('--border') } },
      axisLabel: textStyle,
      splitLine: { show: false },
    },
    yAxis: data.axes.map((axis, index) => ({
      type: 'value',
      name: axis.unit,
      position: index === 0 ? 'left' : 'right',
      nameTextStyle: { ...textStyle, align: index === 0 ? 'left' : 'right' },
      axisLabel: { ...textStyle, formatter: (value: number) => formatNumber(value, axis.digits) },
      splitLine: { show: index === 0, lineStyle: { color: token('--chart-grid') } },
    })),
    series: data.series.map((series, index) => {
      // Marks of an axis hang on its first series: ECharts draws them per series.
      const first = data.series.findIndex((other) => other.axis === series.axis) === index
      const marks = first ? data.marks.filter((mark) => mark.axis === series.axis) : []
      return {
        type: 'line',
        name: series.name,
        yAxisIndex: series.axis,
        data: series.values,
        showSymbol: false,
        lineStyle: { width: 2 },
        markLine: marks.length
          ? {
              ...markStyle,
              label: { position: 'insideEndTop', color: muted, fontSize: 12 },
              data: marks.map((mark) => ({ yAxis: mark.value, label: { formatter: mark.label } })),
            }
          : undefined,
      }
    }),
  }
}

/** CSV of the chart for Excel: «;» between fields, a BOM so that Cyrillic survives. */
export function chartCsv(data: TimeChartData): string {
  const header = ['Время', ...data.series.map((series) => `${series.name}, ${data.axes[series.axis].unit}`)]
  const rows = data.moments.map((moment, index) => [
    tooltipTitle(data, moment),
    ...data.series.map((series) => series.values[index]?.toString() ?? ''),
  ])
  return `${BOM}${[header, ...rows].map((row) => row.join(';')).join('\r\n')}`
}
