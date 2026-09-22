import { describe, expect, it } from 'vitest'

import { edgeLabels } from './chartOption'
import { compactColumns } from './heatmapOption'

describe('compact charts of a phone (DESIGN.md §9.3)', () => {
  it('labels only the extreme moments of the axis', () => {
    const shown = ['01.09', '02.09', '03.09', '04.09'].map((_, index) => edgeLabels(4)(index))

    expect(shown).toEqual([true, false, false, true])
  })

  it('keeps the range of columns the data names and all of them without one', () => {
    const hours = Array.from({ length: 24 }, (_, hour) => String(hour).padStart(2, '0'))

    expect(compactColumns(hours, [8, 17])).toEqual(['08', '09', '10', '11', '12', '13', '14', '15', '16', '17'])
    expect(compactColumns(hours, undefined)).toHaveLength(24)
    expect(compactColumns(hours, [20, 40])).toEqual(['20', '21', '22', '23'])
  })
})
