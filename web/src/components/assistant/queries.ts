import { useMutation, useQuery } from '@tanstack/react-query'

import { askAssistant, getAssistantStatus } from '../../api/assistant'
import type { AssistantQuestion } from '../../api/types'

const STATUS_KEY = ['assistant', 'status']

/**
 * Whether the button is in the header (T-84): asked once per sign-in and kept — the switch of
 * the environment and the key of the model do not change under an open panel.
 */
export const useAssistantStatus = (enabled: boolean) =>
  useQuery({
    queryKey: STATUS_KEY,
    queryFn: ({ signal }) => getAssistantStatus(signal),
    enabled,
    staleTime: Infinity,
  })

/** One question with the dialog so far; the answer is appended by the drawer. */
export const useAskAssistant = () =>
  useMutation({ mutationFn: (body: AssistantQuestion) => askAssistant(body) })
