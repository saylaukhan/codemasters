// Exports of the panel (T-30, T-33): build a file of measurements, list them, download one with the token.
import { apiDownload, apiRequest } from './client'
import type { components } from './generated/schema'
import type { ExportCreate } from './types'

type Schemas = components['schemas']

export const createExport = (body: ExportCreate) =>
  apiRequest<Schemas['ExportJob']>('/exports', { method: 'POST', body })

export const getExports = (params: { page: number; pageSize: number }, signal?: AbortSignal) =>
  apiRequest<Schemas['ExportJobPage']>('/exports', { query: params, signal })

export const downloadExport = (exportId: number) => apiDownload(`/exports/${exportId}`)
