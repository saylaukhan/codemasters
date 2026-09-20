import { keepPreviousData, useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createExport, downloadExport, getExports } from '../../api/exports'
import { getSchoolDevices, getSchools } from '../../api/schools'
import type { ExportCreate, ExportJob } from '../../api/types'

// Schools offered at a time: the choice narrows by typing, the list is not paged.
const SCHOOL_OPTIONS = 20

/** Schools of the scope matching `search` by name or School ID (GET /api/schools). */
export const useSchoolOptions = (search: string) =>
  useQuery({
    queryKey: ['schools', 'options', search],
    queryFn: ({ signal }) => getSchools({ q: search || undefined, pageSize: SCHOOL_OPTIONS }, signal),
    placeholderData: keepPreviousData,
  })

/** Computers of the chosen school; nothing to ask without one. */
export const useDeviceOptions = (schoolId: number | undefined) =>
  useQuery({
    queryKey: ['schools', schoolId, 'devices'],
    queryFn: ({ signal }) => getSchoolDevices(schoolId as number, signal),
    enabled: schoolId !== undefined,
  })

/** A blob fetched with the token, saved by the browser; the appeal card saves its PDF the same way (T-48). */
export function saveFile(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

const EXPORTS_KEY = ['exports']
// How often a file built in the background is asked for: a PDF of a school takes seconds.
const POLL_MS = 2000

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms))

/** The file of a ready export is fetched with the token and saved; false while it is still being built. */
async function saveExport(job: Pick<ExportJob, 'id' | 'format'>): Promise<boolean> {
  const file = await downloadExport(job.id)
  if (file === null) return false
  saveFile(file.blob, file.fileName ?? `export-${job.id}.${job.format}`)
  return true
}

/**
 * POST /api/exports; a ready file is saved at once. A PDF or an export of more rows than the settings allow is
 * built in the background (T-33): it is asked for every two seconds for `waitMs`, then it waits in the list of
 * exports. `saved` tells which of the two happened; a failed export is an error with its reason.
 */
export const useBuildExport = (waitMs = 0) => {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (body: ExportCreate) => {
      const job = await createExport(body)
      if (job.status === 'failed') throw new Error(job.error ?? 'Файл выгрузки не сформирован')
      const deadline = Date.now() + waitMs
      let saved = await saveExport(job)
      while (!saved && Date.now() < deadline) {
        await sleep(POLL_MS)
        saved = await saveExport(job)
      }
      return { job, saved }
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: EXPORTS_KEY }),
  })
}

/** Exports of the user, newest first; asked again every two seconds while one of them is being built. */
export const useExports = (page: number, pageSize: number) =>
  useQuery({
    queryKey: [...EXPORTS_KEY, page, pageSize],
    queryFn: ({ signal }) => getExports({ page, pageSize }, signal),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => (query.state.data?.items.some((job) => job.status === 'pending') ? POLL_MS : false),
  })

/** «Скачать» in the list of exports: the file of a ready export. */
export const useDownloadExport = () => useMutation({ mutationFn: saveExport })
