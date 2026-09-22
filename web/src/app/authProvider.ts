// Refine auth and access control over /api/auth (ADR-008, ADR-009). Permissions from
// GET /api/auth/me only hide what a role cannot use; the API checks them again (ТЗ п. 16).
import type { AccessControlProvider, AuthProvider } from '@refinedev/core'

import { getCurrentUser, login, logout, restoreSession } from '../api/auth'
import { ApiError, hasAccessToken } from '../api/client'
import { adoptProfileLocale } from '../lib/locale'
import { SECTIONS, canOpenSection } from './sections'

export const authProvider: AuthProvider = {
  async login({ email, password }: { email: string; password: string }) {
    try {
      await login(email, password)
      return { success: true, redirectTo: '/' }
    } catch (error) {
      return { success: false, error: error instanceof Error ? error : new Error(String(error)) }
    }
  },

  async logout() {
    await logout().catch(() => undefined)
    return { success: true, redirectTo: '/login' }
  },

  async check() {
    if (hasAccessToken() || (await restoreSession())) return { authenticated: true }
    return { authenticated: false, redirectTo: '/login', logout: true }
  },

  async onError(error: unknown) {
    // 401 left after the client tried the refresh cookie: the session is over.
    if (error instanceof ApiError && error.status === 401) {
      return { logout: true, redirectTo: '/login', error }
    }
    return {}
  },

  async getIdentity() {
    const user = await getCurrentUser()
    // A browser that never chose a language takes the one of the profile (T-66).
    adoptProfileLocale(user.locale)
    return user
  },

  getPermissions: async () => (await getCurrentUser()).permissions,
}

export const accessControlProvider: AccessControlProvider = {
  async can({ resource }) {
    const section = SECTIONS.find((item) => item.key === resource)
    if (!section) return { can: true }
    const { permissions } = await getCurrentUser()
    return { can: canOpenSection(section, permissions) }
  },
}
