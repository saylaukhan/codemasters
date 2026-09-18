import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'

import { PAGE_SIZES } from '../schools/useSchoolListView'

export interface AdminListView {
  /** Search as typed; the query trims it. */
  q: string
  /** Schools only: true — active, false — disabled, undefined — all. */
  isActive?: boolean
  page: number
  pageSize: number
}

const readPositive = (value: string | null, fallback: number): number => {
  const number = Number(value ?? undefined)
  return Number.isInteger(number) && number > 0 ? number : fallback
}

const readActive = (value: string | null): boolean | undefined =>
  value === 'true' ? true : value === 'false' ? false : undefined

/** Search, filter and page of a list of the administration, kept in the URL (DESIGN.md §2.6). */
export function useAdminListView(): [AdminListView, (view: AdminListView) => void] {
  const [params, setParams] = useSearchParams()
  const view = useMemo<AdminListView>(() => {
    const pageSize = readPositive(params.get('page_size'), PAGE_SIZES[0])
    return {
      q: params.get('q') ?? '',
      isActive: readActive(params.get('is_active')),
      page: readPositive(params.get('page'), 1),
      pageSize: (PAGE_SIZES as readonly number[]).includes(pageSize) ? pageSize : PAGE_SIZES[0],
    }
  }, [params])
  const setView = useCallback(
    (next: AdminListView) =>
      setParams(
        (current) => {
          const updated = new URLSearchParams(current)
          if (next.q) updated.set('q', next.q)
          else updated.delete('q')
          if (next.isActive === undefined) updated.delete('is_active')
          else updated.set('is_active', String(next.isActive))
          updated.set('page', String(next.page))
          updated.set('page_size', String(next.pageSize))
          return updated
        },
        { replace: true },
      ),
    [setParams],
  )
  return [view, setView]
}
