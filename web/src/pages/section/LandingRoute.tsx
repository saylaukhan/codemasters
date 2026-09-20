import { useGetIdentity } from '@refinedev/core'
import { Navigate } from 'react-router'

import type { CurrentUser } from '../../api/types'
import { landingPath } from '../../app/sections'
import { ContentSkeleton } from '../../components/ui/ContentSkeleton'

/** Root of the panel: the first section of the user's navigation — «Обзор» for most roles, «Школы» in the cabinet
 * of a provider (T-44). A role must not land on a section its navigation does not hold. */
export function LandingRoute() {
  const { data: user, isLoading } = useGetIdentity<CurrentUser>()
  if (isLoading) return <ContentSkeleton />
  return <Navigate to={landingPath(user)} replace />
}
