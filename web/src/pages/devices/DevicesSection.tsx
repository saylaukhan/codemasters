import { Monitor } from 'lucide-react'
import { Route, Routes } from 'react-router'

import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { SECTION_LABELS } from '../../lib/labels'
import { NotFoundPage } from '../section/NotFoundPage'
import { DeviceCardPage } from './DeviceCardPage'

/** Section «Устройства»: the card of a computer at /devices/:deviceId (T-26); the list is T-36. */
export function DevicesSection() {
  return (
    <Routes>
      <Route
        index
        element={
          <>
            <PageHeader title={SECTION_LABELS.devices} />
            <EmptyState
              icon={Monitor}
              title="Выберите компьютер в карточке школы"
              description="Список компьютеров школы — на вкладке «Устройства» карточки школы."
            />
          </>
        }
      />
      <Route path=":deviceId" element={<DeviceCardPage />} />
      <Route path="*" element={<NotFoundPage />} />
    </Routes>
  )
}
