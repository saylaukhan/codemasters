import { useCallback, useMemo } from 'react'
import { useSearchParams } from 'react-router'

import type { SchoolSort } from '../../api/types'
import type { SchoolListView } from './queries'

export const PAGE_SIZES = [25, 50, 100] as const

const readPositive = (value: string | null, fallback: number): number => {
  const number = Number(value ?? undefined)
  return Number.isInteger(number) && number > 0 ? number : fallback
}

/** Sort and page of the list, kept in the URL next to the filters (DESIGN.md §2.6). */
export function useSchoolListView(): [SchoolListView, (view: SchoolListView) => void] {
  const [params, setParams] = useSearchParams()
  const view = useMemo<SchoolListView>(() => {
    const pageSize = readPositive(params.get('page_size'), PAGE_SIZES[0])
    return {
      sort: (params.get('sort') as SchoolSort | null) ?? undefined,
      page: readPositive(params.get('page'), 1),
      pageSize: (PAGE_SIZES as readonly number[]).includes(pageSize) ? pageSize : PAGE_SIZES[0],
    }
  }, [params])
  const setView = useCallback(
    (next: SchoolListView) =>
      setParams(
        (current) => {
          const updated = new URLSearchParams(current)
          if (next.sort) updated.set('sort', next.sort)
          else updated.delete('sort')
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
