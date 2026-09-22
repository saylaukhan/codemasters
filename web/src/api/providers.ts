// Providers of the claim work (T-68, ТЗ п. 14, docs/design/README.md §6.3): the score of every provider the user
// may see, the card of one of them and the act of non-compliance as a PDF. The scope is the server's (ADR-008).
import { apiDownload, apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'
import type { Schema } from './types'

type Schemas = components['schemas']

// Panel-side names of the contract types of this section; the answers are camelCase (ADR-009).
export type ProviderScoreReport = Schema<'ProviderScoreReport'>
export type ProviderScoreRow = Schema<'ProviderScoreRow'>
export type ProviderScoreDetail = Schema<'ProviderScoreDetail'>
export type ProviderSchoolRow = Schema<'ProviderSchoolRow'>
export type ProviderLineBelowNorm = Schema<'ProviderLineBelowNorm'>

export const getProviderScore = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ProviderScoreReport']>('/providers/score', { query, signal })

/** Card of one provider: the same numbers plus its schools and the lines whose contract is below the norm. */
export const getProviderCard = (providerId: number, query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ProviderScoreDetail']>(`/providers/${providerId}/score`, { query, signal })

/** The act as a file: it is fetched with the token, not by a link, like the PDF of an appeal (T-48). */
export const downloadProviderAct = (providerId: number, period: string) =>
  apiDownload(`/providers/${providerId}/act?period=${encodeURIComponent(period)}`)
