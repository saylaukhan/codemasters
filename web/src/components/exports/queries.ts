import { keepPreviousData, useMutation, useQuery } from '@tanstack/react-query'

import { createExport, downloadExport } from '../../api/exports'
import { getSchoolDevices, getSchools } from '../../api/schools'
import type { ExportCreate } from '../../api/types'

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

function saveFile(blob: Blob, fileName: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}

/** POST /api/exports, then the file is fetched with the token and saved (T-30: built in the request). */
export const useBuildExport = () =>
  useMutation({
    mutationFn: async (body: ExportCreate) => {
      const job = await createExport(body)
      const file = await downloadExport(job.id)
      saveFile(file.blob, file.fileName ?? `export-${job.id}.${job.format}`)
      return job
    },
  })
