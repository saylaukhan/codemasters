import { useGetIdentity } from '@refinedev/core'
import { Suspense, lazy } from 'react'
import { Navigate, Route, Routes } from 'react-router'

import type { CurrentUser } from '../../api/types'
import { schoolCardPath } from '../../app/sections'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { NotFoundPage } from '../section/NotFoundPage'
import { SchoolsPage } from './SchoolsPage'

// Both cards carry ECharts: loaded only when a card is opened.
const SchoolCardPage = lazy(() => import('./SchoolCardPage').then((page) => ({ default: page.SchoolCardPage })))
const SchoolCabinetPage = lazy(() =>
  import('./SchoolCabinetPage').then((page) => ({ default: page.SchoolCabinetPage })),
)

/**
 * Section «Школы»: the list (T-24) and the card of a school at /schools/:schoolId (T-25). The
 * school role sees the cabinet of T-61 at the same address and is sent to its own school from the
 * index, so no second route exists; a foreign school answers 404 inside the cabinet as it does in
 * the card (ТЗ п. 16).
 */
export function SchoolsSection() {
  const { data: user, isLoading } = useGetIdentity<CurrentUser>()
  // Until the role is known nothing is drawn: a school user must not see one frame of the oblast
  // list or of the card of T-25 before the cabinet replaces it (LandingRoute does the same).
  if (isLoading) return <ContentSkeleton rows={8} />
  const cabinet = user?.role === 'school'
  const ownSchoolId = cabinet ? user.scope.schoolId : null

  return (
    <Routes>
      <Route
        index
        element={ownSchoolId == null ? <SchoolsPage /> : <Navigate to={schoolCardPath(ownSchoolId)} replace />}
      />
      <Route
        path=":schoolId"
        element={
          <Suspense fallback={<ContentSkeleton rows={8} />}>
            {cabinet ? <SchoolCabinetPage /> : <SchoolCardPage />}
          </Suspense>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
