import { keepPreviousData, useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query'

import {
  createAppeal,
  createAppealDraft,
  downloadAppealPdf,
  getAppeal,
  getAppeals,
  updateAppeal,
} from '../../api/appeals'
import { ApiError } from '../../api/client'
import type { AppealDetail, AppealDraftRequest, AppealUpdate } from '../../api/types'
import { saveFile } from '../exports/queries'
import { REFRESH_MS } from '../map/queries'
import { appealListQuery, type AppealListView } from './appeals'

// An appeal outside the scope answers 404: asking again will not change that.
const retryUnlessMissing = (count: number, error: Error) =>
  !(error instanceof ApiError && error.status === 404) && count < 3

/**
 * Every list and card of appeals lives under ['appeals']; a sent one changes the incident it is about too. The
 * draft is left alone: asking the model again would rewrite the letter the person has just sent (ADR-011).
 */
const invalidateAppeals = (queryClient: QueryClient) =>
  Promise.all([
    queryClient.invalidateQueries({ queryKey: ['appeals'], predicate: (query) => query.queryKey[1] !== 'draft' }),
    queryClient.invalidateQueries({ queryKey: ['incidents'] }),
  ])

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

export const useAppeals = (view: AppealListView) =>
  useQuery({
    queryKey: ['appeals', 'list', view],
    queryFn: ({ signal }) => getAppeals(appealListQuery(view), signal),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
  })

export const useAppeal = (appealId: number) =>
  useQuery({
    queryKey: ['appeals', appealId],
    queryFn: ({ signal }) => getAppeal(appealId, signal),
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })

/** «Отправить обращение»: the number comes back with the card the editor then opens. */
export const useCreateAppeal = () => {
  const queryClient = useQueryClient()
  return useMutation({ mutationFn: createAppeal, onSuccess: () => invalidateAppeals(queryClient) })
}

export const useUpdateAppeal = (appealId: number) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (body: AppealUpdate) => updateAppeal(appealId, body),
    onSuccess: () => invalidateAppeals(queryClient),
  })
}

/**
 * «Скачать PDF» of the card: the file is fetched with the token and saved under the number of the appeal — the
 * header names it in latin-1 for old clients, the number itself is Cyrillic.
 */
export const useDownloadAppealPdf = () =>
  useMutation({
    mutationFn: async (appeal: Pick<AppealDetail, 'id' | 'number'>) => {
      const file = await downloadAppealPdf(appeal.id)
      if (file !== null) saveFile(file.blob, `${appeal.number}.pdf`)
    },
  })
