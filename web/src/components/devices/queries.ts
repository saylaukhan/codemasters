import { keepPreviousData, useQuery } from '@tanstack/react-query'

import { ApiError } from '../../api/client'
import { getDevice, getDeviceMeasurements } from '../../api/devices'
import { REFRESH_MS } from '../map/queries'

/** Periods of the history: the last 7 or 30 days back from the moment of the request. */
export const HISTORY_DAYS = { week: 7, month: 30 } as const
export type HistoryPeriod = keyof typeof HISTORY_DAYS

export interface HistoryView {
  period: HistoryPeriod
  page: number
  pageSize: number
}

const DAY_MS = 24 * 60 * 60 * 1000

// A device outside the scope answers 404: asking again will not change that.
const retryUnlessMissing = (count: number, error: Error) =>
  !(error instanceof ApiError && error.status === 404) && count < 3

export const useDevice = (deviceId: number) =>
  useQuery({
    queryKey: ['devices', deviceId],
    queryFn: ({ signal }) => getDevice(deviceId, signal),
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })

export const useDeviceMeasurements = (deviceId: number, { period, page, pageSize }: HistoryView) =>
  useQuery({
    queryKey: ['devices', deviceId, 'measurements', period, page, pageSize],
    // The start is taken at request time, not in the key: the key stays stable between refreshes.
    queryFn: ({ signal }) =>
      getDeviceMeasurements(
        deviceId,
        { periodFrom: new Date(Date.now() - HISTORY_DAYS[period] * DAY_MS).toISOString(), page, pageSize },
        signal,
      ),
    placeholderData: keepPreviousData,
    refetchInterval: REFRESH_MS,
    retry: retryUnlessMissing,
  })
