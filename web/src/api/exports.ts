// Exports of the panel (T-30, T-33): build a file of measurements, list them, download one with the token.
import { apiDownload, apiRequest } from './client'
import type { components } from './generated/schema'
import type { ExportCreate, ExportEstimateQuery } from './types'

type Schemas = components['schemas']

export const createExport = (body: ExportCreate) =>
  apiRequest<Schemas['ExportJob']>('/exports', { method: 'POST', body })

export const getExports = (params: { page: number; pageSize: number }, signal?: AbortSignal) =>
  apiRequest<Schemas['ExportJobPage']>('/exports', { query: params, signal })

/** «Будет выгружено ≈ N строк» before the file is built (T-64): the same filters as the export itself. */
export const getExportEstimate = (query: ExportEstimateQuery, signal?: AbortSignal) =>
  apiRequest<Schemas['ExportEstimate']>('/exports/estimate', { query, signal })

export const downloadExport = (exportId: number) => apiDownload(`/exports/${exportId}`)
