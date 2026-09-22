import type { AssistantAuthor, AssistantQuestion, AssistantScreen } from '../../api/types'

/** One line of the dialog as the drawer keeps it; the API takes the same two fields. */
export interface AssistantTurn {
  author: AssistantAuthor
  text: string
}

/** Lines sent with a question, the limit of `POST /api/assistant/ask` (backend/app/schemas/assistant.py). */
export const DIALOG_MAX_MESSAGES = 20

/** Length of one line the API takes; the field of the drawer stops there. */
export const QUESTION_MAX_LENGTH = 2000

export const withQuestion = (turns: readonly AssistantTurn[], text: string): AssistantTurn[] => [
  ...turns,
  { author: 'user', text },
]

export const withAnswer = (turns: readonly AssistantTurn[], text: string): AssistantTurn[] => [
  ...turns,
  { author: 'assistant', text },
]

/** A question is sent trimmed and only when something is typed. */
export const cleanQuestion = (draft: string): string | null => {
  const text = draft.trim()
  return text === '' ? null : text
}

/**
 * Body of one question: the open screen and the last lines of the dialog, the question last.
 * Nothing is stored on the server (ADR-017), so the dialog goes whole — up to the limit of the
 * API, the oldest lines staying in the browser.
 */
export const questionBody = (screen: AssistantScreen, turns: readonly AssistantTurn[]): AssistantQuestion => ({
  screen,
  messages: turns.slice(-DIALOG_MAX_MESSAGES).map(({ author, text }) => ({ author, text })),
})
