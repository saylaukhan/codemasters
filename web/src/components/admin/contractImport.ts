// Contract import of the administration (T-61, ТЗ п. 14): the file read for the request, the summary of a report
// and the rows of it as the table shows them.
import type { ContractImportReport, ContractImportRequest, ContractImportRow } from '../../api/types'
import { CONTRACT_IMPORT_LABELS } from '../../lib/labels'
import { changeLines, type ChangeLine } from './auditLog'

/** Limit of backend/app/schemas/contracts.py, checked before the file is read. */
export const MAX_FILE_SIZE = 2 * 1024 * 1024

export const ACCEPTED_EXTENSIONS = ['.csv', '.xlsx'] as const

export const isAcceptedFile = (name: string): boolean =>
  ACCEPTED_EXTENSIONS.some((extension) => name.toLowerCase().endsWith(extension))

/** Body of the two calls: the name says the format, the content goes as base64. */
export const importRequest = (fileName: string, contentBase64: string): ContractImportRequest => ({
  fileName,
  content: contentBase64,
})

/** Base64 of a data URL, as `FileReader.readAsDataURL` gives it: everything after the comma. */
export const base64OfDataUrl = (dataUrl: string): string => dataUrl.slice(dataUrl.indexOf(',') + 1)

/** «120 строк · 3 новых линий · 40 изменений · 75 без изменений · 2 с ошибкой». */
export function importSummary(report: ContractImportReport): string {
  return [
    `${report.rowsTotal} ${CONTRACT_IMPORT_LABELS.rowsTotal}`,
    `${report.created} ${CONTRACT_IMPORT_LABELS.created}`,
    `${report.updated} ${CONTRACT_IMPORT_LABELS.updated}`,
    `${report.unchanged} ${CONTRACT_IMPORT_LABELS.unchanged}`,
    `${report.failed} ${CONTRACT_IMPORT_LABELS.failed}`,
  ].join(' · ')
}

/** Whether the file has something to write: a preview with only unchanged and failed rows is not applied. */
export const canApply = (report: ContractImportReport | undefined): boolean =>
  report !== undefined && report.dryRun && report.created + report.updated > 0

/** Changed fields of a row as «поле: старое → новое» lines, the words of the audit log (T-39). */
export const rowChangeLines = (row: ContractImportRow): ChangeLine[] => changeLines(row.changes)
