import { Route, Routes } from 'react-router'

import { NotFoundPage } from '../section/NotFoundPage'
import { IncidentCardPage } from './IncidentCardPage'
import { IncidentsPage } from './IncidentsPage'

/** Section «Инциденты»: the list and the kanban at /incidents (T-41, T-43), the card at /incidents/:incidentId. */
export function IncidentsSection() {
  return (
    <Routes>
      <Route index element={<IncidentsPage />} />
      <Route path=":incidentId" element={<IncidentCardPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
