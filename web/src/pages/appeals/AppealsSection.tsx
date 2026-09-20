import { Construction } from 'lucide-react'
import { Route, Routes } from 'react-router'

import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { SECTION_LABELS } from '../../lib/labels'
import { NotFoundPage } from '../section/NotFoundPage'
import { AppealDraftPage } from './AppealDraftPage'

/** Sent appeals with their numbers and statuses arrive with the sending of T-48. */
function AppealsPage() {
  return (
    <>
      <PageHeader title={SECTION_LABELS.appeals} />
      <EmptyState
        icon={Construction}
        title="Список обращений в разработке"
        description="Отправленные обращения появятся здесь в ближайшем обновлении панели."
      />
    </>
  )
}

/** Section «Обращения»: the list of sent ones at /appeals (T-48), the editor of a draft at /appeals/new (T-47). */
export function AppealsSection() {
  return (
    <Routes>
      <Route index element={<AppealsPage />} />
      <Route path="new" element={<AppealDraftPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
