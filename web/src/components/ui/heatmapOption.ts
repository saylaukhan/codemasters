// Option of the ECharts heatmap (DESIGN.md §2.4, §4.4) and its CSV: pure functions of the heatmap
// data, apart from reading the colors of tokens.css at the moment the option is built. Values are
// shares of something bad, 0–100 %: 0 is painted with the good color, 100 with the bad one.
import type { EChartsCoreOption } from 'echarts/core'

import { formatNumber, formatPercent } from '../../lib/format'
import { token, tooltipFrame } from './chartOption'

const BOM = '\uFEFF'
const STEPS = 5
const STEP = 100 / STEPS
// Value of a cell without measurements: its own piece of the visual map, the color of the empty cell.
const EMPTY = -1
const EMPTY_LABEL = 'Нет замеров'

export interface HeatmapCell {
  /** Share, 0–100 %. */
  value: number
  /** First line of the tooltip, e.g. «Пн, 09:00–10:00». */
  title: string
  /** Last line of the tooltip, e.g. «3 из 12 замеров». */
  note: string
}

export interface HeatmapChartData {
  kind: 'heatmap'
  /** Name of the value in the tooltip: «Проблемные замеры». */
  name: string
  /** Captions of the columns, left to right. */
  columns: readonly string[]
  /** Captions of the rows, top to bottom. */
  rows: readonly string[]
  /** cells[row][column]; null — nothing measured there. */
  cells: readonly (readonly (HeatmapCell | null)[])[]
}

/** Middle of two #rrggbb colors: the intermediate steps of DESIGN.md §4.4; anything else — the first. */
export function mixColors(a: string, b: string): string {
  const hex = /^#[0-9a-f]{6}$/i
  if (!hex.test(a) || !hex.test(b)) return a
  const channels = (color: string) => [1, 3, 5].map((index) => parseInt(color.slice(index, index + 2), 16))
  const [left, right] = [channels(a), channels(b)]
  return `#${left.map((channel, index) => Math.round((channel + right[index]) / 2).toString(16).padStart(2, '0')).join('')}`
}

interface TooltipItem {
  value: [number, number, number]
}

export function buildHeatmapOption(data: HeatmapChartData): EChartsCoreOption {
  const textStyle = { color: token('--text-muted'), fontSize: 12 }
  const [bad, mid, good] = ['--chart-heatmap-bad', '--chart-heatmap-mid', '--chart-heatmap-good'].map(token)
  const colors = [good, mixColors(good, mid), mid, mixColors(mid, bad), bad]
  const axis = { type: 'category', axisTick: { show: false }, axisLine: { show: false }, axisLabel: textStyle }
  return {
    backgroundColor: 'transparent',
    animation: false,
    textStyle: { fontFamily: token('--font-sans') },
    grid: { left: 32, right: 8, top: 8, bottom: 40 },
    tooltip: {
      ...tooltipFrame(),
      trigger: 'item',
      formatter: ({ value: [column, row] }: TooltipItem) => {
        const cell = data.cells[row]?.[column]
        if (!cell) return `<div>${data.rows[row]}, ${data.columns[column]}</div><div>${EMPTY_LABEL}</div>`
        const muted = `color:${token('--text-secondary')}`
        return `<div style="margin-bottom:4px">${cell.title}</div><div>${data.name}: <b>${formatPercent(cell.value)}</b></div><div style="${muted}">${cell.note}</div>`
      },
    },
    xAxis: { ...axis, data: data.columns },
    yAxis: { ...axis, data: data.rows, inverse: true },
    visualMap: {
      type: 'piecewise',
      dimension: 2,
      orient: 'horizontal',
      left: 0,
      bottom: 0,
      itemWidth: 12,
      itemHeight: 12,
      itemGap: 12,
      itemSymbol: 'roundRect',
      textStyle: { color: token('--text-secondary'), fontSize: 12 },
      pieces: [
        ...colors.map((color, step) => ({
          gte: step * STEP,
          ...(step === STEPS - 1 ? { lte: 100 } : { lt: (step + 1) * STEP }),
          color,
          label: `${formatNumber(step * STEP, 0)}–${formatPercent((step + 1) * STEP, 0)}`,
        })),
        { value: EMPTY, color: token('--chart-heatmap-empty'), label: EMPTY_LABEL },
      ],
    },
    series: [
      {
        type: 'heatmap',
        name: data.name,
        data: data.cells.flatMap((cells, row) =>
          cells.map((cell, column) => [column, row, cell ? cell.value : EMPTY]),
        ),
        itemStyle: { borderColor: token('--bg-surface'), borderWidth: 2, borderRadius: 4 },
        emphasis: { itemStyle: { borderColor: token('--border-strong'), borderWidth: 1 } },
      },
    ],
  }
}

/** CSV of the heatmap for Excel: the same matrix, «;» between fields, empty cells without measurements. */
export function heatmapCsv(data: HeatmapChartData): string {
  const header = [`${data.name}, %`, ...data.columns]
  const rows = data.rows.map((caption, row) => [
    caption,
    ...data.columns.map((_, column) => data.cells[row]?.[column]?.value.toString() ?? ''),
  ])
  return `${BOM}${[header, ...rows].map((line) => line.join(';')).join('\r\n')}`
}
