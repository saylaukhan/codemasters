import { Route, Routes } from 'react-router'

import { NotFoundPage } from '../section/NotFoundPage'
import { AppealCardPage } from './AppealCardPage'
import { AppealDraftPage } from './AppealDraftPage'
import { AppealsPage } from './AppealsPage'

/**
 * Section «Обращения»: the list of sent ones at /appeals, the editor of a draft at /appeals/new (T-47), the card
 * of one appeal with its history at /appeals/:appealId (T-48). «new» is not a number, so it comes first.
 */
export function AppealsSection() {
  return (
    <Routes>
      <Route index element={<AppealsPage />} />
      <Route path="new" element={<AppealDraftPage />} />
      <Route path=":appealId" element={<AppealCardPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
