import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import {
  getNotifications,
  getUnreadCount,
  readAllNotifications,
  streamNotifications,
} from '../../api/notifications'
import type { NotificationTabKey } from '../../lib/labels'
import { REFRESH_MS } from '../map/queries'
import { notificationListQuery } from './notifications'

const NOTIFICATIONS_KEY = ['notifications']
const LIST_KEY = [...NOTIFICATIONS_KEY, 'list']
const UNREAD_KEY = [...NOTIFICATIONS_KEY, 'unread']

// Pause before the stream is opened again: a proxy or a restart of the API ends it from time to time.
const RECONNECT_MS = 10_000

/** A page of the chosen tab; the panel is mounted only once the bell has been unfolded. */
export const useNotifications = (tab: NotificationTabKey) =>
  useQuery({
    queryKey: [...LIST_KEY, tab],
    queryFn: ({ signal }) => getNotifications(notificationListQuery(tab), signal),
    placeholderData: keepPreviousData,
  })

/** Counter of the bell: the stream keeps it exact, the interval covers a stream that was cut. */
export const useUnreadCount = () =>
  useQuery({
    queryKey: UNREAD_KEY,
    queryFn: ({ signal }) => getUnreadCount(signal),
    refetchInterval: REFRESH_MS,
  })

export const useReadAllNotifications = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: readAllNotifications,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: NOTIFICATIONS_KEY }),
  })
}

/**
 * Subscribes the bell to GET /api/notifications/stream: a new notification bumps the counter and
 * shows up in the panel without a page reload (T-42). A stream that ended is opened again after a
 * pause; while it is down the interval of `useUnreadCount` still keeps the bell honest.
 */
export function useNotificationStream(enabled: boolean): void {
  const queryClient = useQueryClient()
  useEffect(() => {
    if (!enabled) return
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout> | undefined
    const listen = async (): Promise<void> => {
      try {
        await streamNotifications((event) => {
          queryClient.setQueryData(UNREAD_KEY, { unread: event.unread })
          void queryClient.invalidateQueries({ queryKey: LIST_KEY })
        }, controller.signal)
      } catch {
        // Losing the stream is not an error of the panel: the counter is asked for again anyway.
      }
      if (!controller.signal.aborted) timer = setTimeout(() => void listen(), RECONNECT_MS)
    }
    void listen()
    return () => {
      controller.abort()
      clearTimeout(timer)
    }
  }, [enabled, queryClient])
}
