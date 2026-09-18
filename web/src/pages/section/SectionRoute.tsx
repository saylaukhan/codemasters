import { usePermissions } from '@refinedev/core'
import { ShieldX } from 'lucide-react'
import { Suspense, lazy, type ComponentType } from 'react'

import { canOpenSection, type Section } from '../../app/sections'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import type { SectionKey } from '../../lib/labels'
import { SectionPage } from './SectionPage'

// Screens already built; the other sections show the placeholder until their task lands. Loaded on
// demand: the map library alone outweighs the rest of the panel.
const PAGES: Partial<Record<SectionKey, ComponentType>> = {
  overview: lazy(() => import('../overview/OverviewPage').then((page) => ({ default: page.OverviewPage }))),
  map: lazy(() => import('../map/MapPage').then((page) => ({ default: page.MapPage }))),
  schools: lazy(() => import('../schools/SchoolsPage').then((page) => ({ default: page.SchoolsPage }))),
}

/** A section opened by URL is checked like the navigation: no permission — no screen (ТЗ п. 16). */
export function SectionRoute({ section }: { section: Section }) {
  const { data: permissions, isLoading, error, refetch } = usePermissions<string[]>({})
  if (isLoading) return <ContentSkeleton />
  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (!canOpenSection(section, permissions)) {
    return <EmptyState icon={ShieldX} title="Нет доступа" description="Этот раздел недоступен для вашей роли." />
  }
  const Page = PAGES[section.key]
  if (!Page) return <SectionPage section={section} />
  return (
    <Suspense fallback={<ContentSkeleton />}>
      <Page />
    </Suspense>
  )
}
