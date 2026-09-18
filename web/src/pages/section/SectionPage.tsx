import { Construction } from 'lucide-react'

import type { Section } from '../../app/sections'
import { EmptyState } from '../../components/ui/EmptyState'
import { PageHeader } from '../../components/ui/PageHeader'
import { SECTION_LABELS } from '../../lib/labels'

/** Placeholder of a section until its task (`section.task`) builds the real screen. */
export function SectionPage({ section }: { section: Section }) {
  return (
    <>
      <PageHeader title={SECTION_LABELS[section.key]} />
      <EmptyState
        icon={Construction}
        title="Раздел в разработке"
        description="Экран появится в ближайшем обновлении панели."
      />
    </>
  )
}
