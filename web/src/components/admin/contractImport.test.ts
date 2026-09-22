import { describe, expect, it } from 'vitest'

import type { ContractImportReport } from '../../api/types'
import { base64OfDataUrl, canApply, importRequest, importSummary, isAcceptedFile, rowChangeLines } from './contractImport'

const report: ContractImportReport = {
  fileName: 'contracts.csv',
  dryRun: true,
  rowsTotal: 4,
  created: 1,
  updated: 1,
  unchanged: 0,
  failed: 2,
  items: [
    {
      row: 2,
      schoolCode: 'VKO-UK-001',
      schoolId: 1,
      schoolName: 'Школа № 1',
      providerName: 'Провайдер',
      lineId: 7,
      action: 'update',
      changes: { contractDownMbps: { old: null, new: 100 }, contractDate: { old: null, new: '2026-01-15' } },
      error: null,
    },
    {
      row: 3,
      schoolCode: 'VKO-UK-999',
      schoolId: null,
      schoolName: null,
      providerName: 'Провайдер',
      lineId: null,
      action: 'error',
      changes: null,
      error: 'школа не найдена',
    },
  ],
}

describe('contract import', () => {
  it('accepts only csv and xlsx files whatever the case', () => {
    expect(isAcceptedFile('Реестр.XLSX')).toBe(true)
    expect(isAcceptedFile('contracts.csv')).toBe(true)
    expect(isAcceptedFile('contracts.xls')).toBe(false)
  })

  it('takes the base64 of a data url and builds the request', () => {
    expect(base64OfDataUrl('data:text/csv;base64,U2Nob29s')).toBe('U2Nob29s')
    expect(importRequest('contracts.csv', 'U2Nob29s')).toEqual({ fileName: 'contracts.csv', content: 'U2Nob29s' })
  })

  it('sums the report up and knows when there is something to apply', () => {
    expect(importSummary(report)).toBe('4 строк · 1 новых линий · 1 изменений · 0 без изменений · 2 с ошибкой')
    expect(canApply(report)).toBe(true)
    expect(canApply({ ...report, created: 0, updated: 0 })).toBe(false)
    expect(canApply({ ...report, dryRun: false })).toBe(false)
    expect(canApply(undefined)).toBe(false)
  })

  it('writes the changes of a row with the words of the audit log', () => {
    expect(rowChangeLines(report.items[0])).toEqual([
      { field: 'Download по договору', old: 'пусто', new: '100' },
      { field: 'Дата договора', old: 'пусто', new: '2026-01-15' },
    ])
    expect(rowChangeLines(report.items[1])).toEqual([])
  })
})
