import { Suspense, lazy } from 'react'
import { Route, Routes } from 'react-router'

import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { NotFoundPage } from '../section/NotFoundPage'
import { SchoolsPage } from './SchoolsPage'

// The card carries ECharts: loaded only when a card is opened.
const SchoolCardPage = lazy(() => import('./SchoolCardPage').then((page) => ({ default: page.SchoolCardPage })))

/** Section «Школы»: the list (T-24) and the card of a school at /schools/:schoolId (T-25). */
export function SchoolsSection() {
  return (
    <Routes>
      <Route index element={<SchoolsPage />} />
      <Route
        path=":schoolId"
        element={
          <Suspense fallback={<ContentSkeleton rows={8} />}>
            <SchoolCardPage />
          </Suspense>
        }
      />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
