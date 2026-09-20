import { useQuery } from '@tanstack/react-query'

import { createAppealDraft } from '../../api/appeals'
import type { AppealDraftRequest } from '../../api/types'

/**
 * Draft of the editor (POST /api/appeals/draft, T-47): asked once when the editor opens and kept as it came. The
 * model answers slowly and never twice the same, so nothing refetches it by itself and a failure is not retried —
 * «Повторить» of the editor does that, and until then the letter is written by hand (ADR-011).
 */
export const useAppealDraft = (target: AppealDraftRequest | null) =>
  useQuery({
    queryKey: ['appeals', 'draft', target],
    queryFn: ({ signal }) => createAppealDraft(target as AppealDraftRequest, signal),
    enabled: target !== null,
    staleTime: Infinity,
    retry: false,
    refetchOnWindowFocus: false,
  })
