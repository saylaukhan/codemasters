// Рассылки сводки для руководителя (T-67): список, сохранение, удаление, отправка и предпросмотр.
// Раздел администрирования, поэтому ключ запроса общий с админкой: сохранение в админке и здесь
// обновляет один и тот же список.
import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createDigest,
  deleteDigest,
  downloadDigestPreview,
  getDigests,
  getRegions,
  sendDigestNow,
  updateDigest,
} from '../../api/admin'
import type { DigestSettingsCreate, DigestSettingsDetail, DigestSettingsUpdate } from '../../api/types'
import type { AdminListView } from '../admin/useAdminListView'
import { saveFile } from './queries'

const DIGESTS_KEY = ['admin', 'digests']
// Районов и городов ВКО меньше двадцати: выбор охвата не листается.
const REGION_OPTIONS = 100

/** Рассылки сводки страницами (GET /api/admin/digests). */
export const useDigests = (view: AdminListView) =>
  useQuery({
    queryKey: [...DIGESTS_KEY, view.page, view.pageSize],
    queryFn: ({ signal }) => getDigests({ page: view.page, pageSize: view.pageSize }, signal),
    placeholderData: keepPreviousData,
  })

/** Районы и города для выбора охвата рассылки. */
export const useRegionOptions = () =>
  useQuery({
    queryKey: ['admin', 'regions', 'options'],
    queryFn: ({ signal }) => getRegions({ pageSize: REGION_OPTIONS }, signal),
    select: (page) => page.items.map((region) => ({ value: region.id, label: region.name })),
  })

interface SaveDigest {
  /** Без id — новая рассылка. */
  id?: number
  body: DigestSettingsCreate | DigestSettingsUpdate
}

/** Новая рассылка или изменение существующей: POST или PATCH. */
export const useSaveDigest = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (save: SaveDigest): Promise<DigestSettingsDetail> =>
      save.id === undefined
        ? createDigest(save.body as DigestSettingsCreate)
        : updateDigest(save.id, save.body as DigestSettingsUpdate),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DIGESTS_KEY }),
  })
}

/** Удаление рассылки: настройка, а не история — ушедшие выпуски остаются в журнале. */
export const useDeleteDigest = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteDigest,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DIGESTS_KEY }),
  })
}

/** «Отправить сейчас»: тот же выпуск вне расписания, с той же записью в журнал. */
export const useSendDigest = () => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: sendDigestNow,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: DIGESTS_KEY }),
  })
}

/** «Предпросмотр»: PDF выпуска скачивается с токеном, как отчёт по школе (T-32). */
export const useDigestPreview = () =>
  useMutation({
    mutationFn: async (digestId: number) => {
      const file = await downloadDigestPreview(digestId)
      if (file === null) throw new Error('Предпросмотр не сформирован')
      saveFile(file.blob, file.fileName ?? `svodka-${digestId}.pdf`)
    },
  })
