// Interface assistant (T-84, ADR-017): whether it is on, and one question with the whole dialog.
// The server gives the model the description of the panel, the role and the open screen and
// nothing of the data; nothing is stored, so the dialog travels with every question.
import { apiRequest } from './client'
import type { components } from './generated/schema'
import type { AssistantQuestion } from './types'

type Schemas = components['schemas']

/** `available: false` — switched off or the model has no key: the header shows no button. */
export const getAssistantStatus = (signal?: AbortSignal) =>
  apiRequest<Schemas['AssistantStatus']>('/assistant', { signal })

/** The open screen and the dialog so far, the question last; the answer is text with paragraphs, lists and bold. */
export const askAssistant = (body: AssistantQuestion, signal?: AbortSignal) =>
  apiRequest<Schemas['AssistantAnswer']>('/assistant/ask', { method: 'POST', body, signal })
