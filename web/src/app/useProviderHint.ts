import { useGetIdentity } from '@refinedev/core'

import type { CurrentUser } from '../api/types'
import { isProviderCabinet } from './sections'

/**
 * Subtitle of a screen of the provider cabinet (T-44, ТЗ п. 16): the lists of a provider hold only the schools and
 * the incidents of his own lines, and the screen says so instead of looking like an oblast that lost its schools.
 * Another role gets no subtitle.
 */
export function useProviderHint(hint: string): string | undefined {
  const { data: user } = useGetIdentity<CurrentUser>()
  return isProviderCabinet(user?.role) ? hint : undefined
}
