import { usePermissions } from '@refinedev/core'
import { ShieldX } from 'lucide-react'

import { canOpenSection, type Section } from '../../app/sections'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'
import { EmptyState } from '../../components/ui/EmptyState'
import { ErrorState } from '../../components/ui/ErrorState'
import { SectionPage } from './SectionPage'

/** A section opened by URL is checked like the navigation: no permission — no screen (ТЗ п. 16). */
export function SectionRoute({ section }: { section: Section }) {
  const { data: permissions, isLoading, error, refetch } = usePermissions<string[]>({})
  if (isLoading) return <ContentSkeleton />
  if (error) return <ErrorState error={error} onRetry={() => void refetch()} />
  if (!canOpenSection(section, permissions)) {
    return <EmptyState icon={ShieldX} title="Нет доступа" description="Этот раздел недоступен для вашей роли." />
  }
  return <SectionPage section={section} />
}
