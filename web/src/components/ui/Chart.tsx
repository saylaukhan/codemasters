// ECharts wrapper of DESIGN.md §2.4 / §3.16: the base configuration lives once in chartOption.ts,
// screens pass only the moments, the series and the threshold marks; the heatmap «час × день
// недели» — its matrix (heatmapOption.ts). Colors come from tokens.css, so the chart follows the
// light and the dark theme.
import { Dropdown } from 'antd'
import { BarChart, HeatmapChart, LineChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapPiecewiseComponent,
} from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { Download } from 'lucide-react'
import { useEffect, useRef, type ReactNode } from 'react'

import { useThemeMode } from '../../app/themeMode'
import { Button } from './Button'
import styles from './Chart.module.css'
import { buildOption, chartCsv, token, type TimeChartData } from './chartOption'
import { buildHeatmapOption, heatmapCsv, type HeatmapChartData } from './heatmapOption'

echarts.use([
  BarChart,
  HeatmapChart,
  LineChart,
  GridComponent,
  LegendComponent,
  MarkLineComponent,
  TooltipComponent,
  VisualMapPiecewiseComponent,
  CanvasRenderer,
])

export type ChartData = TimeChartData | HeatmapChartData

const isHeatmap = (data: ChartData): data is HeatmapChartData => 'kind' in data && data.kind === 'heatmap'
const optionOf = (data: ChartData) => (isHeatmap(data) ? buildHeatmapOption(data) : buildOption(data))
const csvOf = (data: ChartData) => (isHeatmap(data) ? heatmapCsv(data) : chartCsv(data))

function save(href: string, fileName: string): void {
  const link = document.createElement('a')
  link.href = href
  link.download = fileName
  link.click()
}

interface ChartCardProps {
  title: string
  /** Period control of the header (segmented, DESIGN.md §3.16). */
  controls?: ReactNode
  /** Name of the exported files without an extension. */
  fileName: string
  data: ChartData | undefined
  /** Loading, empty or error state shown instead of the chart. */
  placeholder?: ReactNode
  height?: number
}

/** Card with a line, bar or heatmap chart: title, period control and «Экспорт» (PNG, CSV) in the header. */
export function ChartCard({ title, controls, fileName, data, placeholder, height = 320 }: ChartCardProps) {
  const element = useRef<HTMLDivElement>(null)
  const chart = useRef<echarts.ECharts | null>(null)
  const { mode } = useThemeMode()
  const showChart = data !== undefined && !placeholder

  useEffect(() => {
    if (!showChart || !element.current) return
    const instance = echarts.init(element.current)
    chart.current = instance
    const observer = new ResizeObserver(() => instance.resize())
    observer.observe(element.current)
    return () => {
      observer.disconnect()
      instance.dispose()
      chart.current = null
    }
  }, [showChart])

  useEffect(() => {
    if (showChart && chart.current) chart.current.setOption(optionOf(data), true)
  }, [showChart, data, mode])

  const exportAs = (kind: string) => {
    if (!data) return
    if (kind === 'png' && chart.current) {
      save(chart.current.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: token('--bg-surface') }), `${fileName}.png`)
    }
    if (kind === 'csv') {
      const url = URL.createObjectURL(new Blob([csvOf(data)], { type: 'text/csv;charset=utf-8' }))
      save(url, `${fileName}.csv`)
      URL.revokeObjectURL(url)
    }
  }

  return (
    <section className={styles.card} aria-label={title}>
      <header className={styles.header}>
        <h2 className={styles.title}>{title}</h2>
        <div className={styles.controls}>
          {controls}
          <Dropdown
            disabled={!showChart}
            menu={{
              items: [
                { key: 'png', label: 'Картинка PNG' },
                { key: 'csv', label: 'Таблица CSV' },
              ],
              onClick: ({ key }) => exportAs(key),
            }}
          >
            <Button kind="flat" icon={<Download size={16} aria-hidden />}>
              Экспорт
            </Button>
          </Dropdown>
        </div>
      </header>
      {showChart ? <div ref={element} style={{ height }} /> : placeholder}
    </section>
  )
}
