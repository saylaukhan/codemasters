// Appeals to a provider (T-47, ТЗ п. 17, ADR-011): the draft of the letter. The server collects the facts of the
// period without personal data and asks the model; nothing is stored until «Отправить» (T-48).
import { apiRequest } from './client'
import type { components } from './generated/schema'
import type { AppealDraftRequest } from './types'

type Schemas = components['schemas']

/**
 * Draft about one incident, or about a line of a school over a period. `ai_generated: false` — the model is off or
 * unavailable and the answer is an empty template the user fills in himself (ADR-011).
 */
export const createAppealDraft = (body: AppealDraftRequest, signal?: AbortSignal) =>
  apiRequest<Schemas['AppealDraft']>('/appeals/draft', { method: 'POST', body, signal })
