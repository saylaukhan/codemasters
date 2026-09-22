import { useMutation, useQuery } from '@tanstack/react-query'

import { ApiError } from '../../api/client'
import { downloadProviderAct, getProviderCard, getProviderScore } from '../../api/providers'
import { saveFile } from '../exports/queries'
import { REFRESH_MS } from '../map/queries'

// A provider outside the scope answers 404: asking again will not change that (ADR-008).
const retryUnlessMissing = (count: number, error: Error) =>
  !(error instanceof ApiError && error.status === 404) && count < 3

export const useProviderScore = (period: string) =>
  useQuery({
    queryKey: ['providers', 'score', period],
    queryFn: ({ signal }) => getProviderScore({ period }, signal),
    refetchInterval: REFRESH_MS,
  })

export const useProviderCard = (providerId: number | null, period: string) =>
  useQuery({
    queryKey: ['providers', 'card', providerId, period],
    queryFn: ({ signal }) => getProviderCard(providerId as number, { period }, signal),
    enabled: providerId !== null,
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })

/** «Скачать акт»: the PDF is built on the server by the generator of T-48 and saved under the provider's name. */
export const useDownloadProviderAct = (period: string) =>
  useMutation({
    mutationFn: async (provider: { id: number; name: string }) => {
      const file = await downloadProviderAct(provider.id, period)
      if (file !== null) saveFile(file.blob, `Акт — ${provider.name}.pdf`)
    },
  })
