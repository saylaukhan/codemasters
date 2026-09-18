import { describe, expect, it } from 'vitest'

import type { AnalyticsReport } from '../../api/types'
import { heatmapCsv, mixColors } from '../ui/heatmapOption'
import { heatmapMatrix, problemHeatmap } from './heatmap'

type Cell = AnalyticsReport['heatmap'][number]

const CELLS: Cell[] = [
  { weekday: 'mon', hour: 9, measurementsCount: 4, problemCount: 1, problemPct: 25 },
  { weekday: 'sun', hour: 23, measurementsCount: 21, problemCount: 0, problemPct: 0 },
  { weekday: 'wed', hour: 0, measurementsCount: 12, problemCount: 12, problemPct: 100 },
]

const REPORT = { heatmap: CELLS } as AnalyticsReport

describe('heatmapMatrix', () => {
  it('lays the cells of m_hourly into 7 days Monday first by 24 hours, gaps are null', () => {
    const matrix = heatmapMatrix(CELLS)

    expect(matrix).toHaveLength(7)
    expect(matrix.every((row) => row.length === 24)).toBe(true)
    expect(matrix[0][9]).toBe(CELLS[0])
    expect(matrix[6][23]).toBe(CELLS[1])
    expect(matrix[2][0]).toBe(CELLS[2])
    expect(matrix.flat().filter(Boolean)).toHaveLength(3)
  })

  it('is all empty without measurements', () => {
    expect(heatmapMatrix([]).flat().every((cell) => cell === null)).toBe(true)
  })
})

describe('problemHeatmap', () => {
  it('captions the rows by weekday and the cells by hour, with the number of measurements', () => {
    const data = problemHeatmap(REPORT)

    expect(data.rows).toEqual(['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'])
    expect(data.columns[0]).toBe('00')
    expect(data.columns[23]).toBe('23')
    expect(data.cells[0][9]).toEqual({ value: 25, title: 'Пн, 09:00–10:00', note: '1 из 4 замеров' })
    expect(data.cells[6][23]).toEqual({ value: 0, title: 'Вс, 23:00–24:00', note: '0 из 21 замера' })
    expect(data.cells[0][10]).toBeNull()
  })

  it('exports the same matrix as CSV with empty cells for hours without measurements', () => {
    const lines = heatmapCsv(problemHeatmap(REPORT)).split('\r\n')

    expect(lines).toHaveLength(8)
    expect(lines[0]).toBe(`\uFEFFПроблемные замеры, %;${Array.from({ length: 24 }, (_, h) => String(h).padStart(2, '0')).join(';')}`)
    expect(lines[1].split(';')).toHaveLength(25)
    expect(lines[1].split(';')[10]).toBe('25')
    expect(lines[3].split(';')[1]).toBe('100')
    expect(lines[4]).toBe(`Чт${';'.repeat(24)}`)
  })
})

describe('mixColors', () => {
  it('takes the middle of two hex colors for the intermediate steps', () => {
    expect(mixColors('#e6f7ee', '#fff4db')).toBe('#f3f6e5')
    expect(mixColors('#000000', '#ffffff')).toBe('#808080')
    expect(mixColors('', '#ffffff')).toBe('')
  })
})
