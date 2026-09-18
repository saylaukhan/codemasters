// Exports of the panel (T-30): build a file of measurements, then download it with the token.
import { apiDownload, apiRequest } from './client'
import type { components } from './generated/schema'
import type { ExportCreate } from './types'

type Schemas = components['schemas']

export const createExport = (body: ExportCreate) =>
  apiRequest<Schemas['ExportJob']>('/exports', { method: 'POST', body })

export const downloadExport = (exportId: number) => apiDownload(`/exports/${exportId}`)
