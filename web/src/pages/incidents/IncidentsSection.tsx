import { Route, Routes } from 'react-router'

import { NotFoundPage } from '../section/NotFoundPage'
import { IncidentCardPage } from './IncidentCardPage'
import { IncidentsPage } from './IncidentsPage'

/** Section «Инциденты»: the list and the card of an incident at /incidents/:incidentId (T-41); the kanban is T-43. */
export function IncidentsSection() {
  return (
    <Routes>
      <Route index element={<IncidentsPage />} />
      <Route path=":incidentId" element={<IncidentCardPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
