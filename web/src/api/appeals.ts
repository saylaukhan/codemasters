// Appeals to a provider (T-47, T-48, ТЗ п. 17, ADR-011): the draft of the letter, its sending and what is kept
// afterwards. The server collects the facts of the period without personal data and asks the model; nothing is
// stored until «Отправить» — that call assigns the number, mails the letter and saves the PDF.
import { apiDownload, apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'
import type { AppealCreate, AppealDraftRequest, AppealUpdate } from './types'

type Schemas = components['schemas']

/**
 * Draft about one incident, or about a line of a school over a period. `ai_generated: false` — the model is off or
 * unavailable and the answer is an empty template the user fills in himself (ADR-011).
 */
export const createAppealDraft = (body: AppealDraftRequest, signal?: AbortSignal) =>
  apiRequest<Schemas['AppealDraft']>('/appeals/draft', { method: 'POST', body, signal })

/** Active templates the editor may write the letter by, the default first (T-60). */
export const getAppealTemplateOptions = (signal?: AbortSignal) =>
  apiRequest<Schemas['AppealTemplateOptionPage']>('/appeals/templates', { query: { page: 1, pageSize: 100 }, signal })

export const getAppeals = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['AppealListItemPage']>('/appeals', { query, signal })

export const getAppeal = (appealId: number, signal?: AbortSignal) =>
  apiRequest<Schemas['AppealDetail']>(`/appeals/${appealId}`, { signal })

/** «Отправить»: the number is assigned here, not by the draft; a letter that did not go leaves `not_sent`. */
export const createAppeal = (body: AppealCreate) =>
  apiRequest<Schemas['AppealDetail']>('/appeals', { method: 'POST', body })

/** The status or a comment of the history; a transition the table of T-41 has no room for answers 409. */
export const updateAppeal = (appealId: number, body: AppealUpdate) =>
  apiRequest<Schemas['AppealDetail']>(`/appeals/${appealId}`, { method: 'PATCH', body })

/** The saved PDF of a sent appeal; it is fetched with the token, not by a link. */
export const downloadAppealPdf = (appealId: number) => apiDownload(`/appeals/${appealId}/pdf`)
