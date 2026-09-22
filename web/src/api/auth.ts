// Panel authentication (plan.md §10, ADR-009): /api/auth/login, /refresh, /logout, /me and the
// password reset of the sign-in screen (T-65): /login-info, /password-reset, /password-reset/confirm.
import { apiRequest, refreshAccessToken, setAccessToken } from './client'
import type { components } from './generated/schema'
import type { CurrentUser } from './types'

type Schemas = components['schemas']

// The current user is asked once per session: identity, permissions and access checks share it.
let currentUser: Promise<CurrentUser> | null = null

export async function login(email: string, password: string): Promise<void> {
  const tokens = await apiRequest<Schemas['AccessTokenResponse']>('/auth/login', {
    method: 'POST',
    body: { email, password },
    auth: false,
  })
  currentUser = null
  setAccessToken(tokens.accessToken)
}

export async function logout(): Promise<void> {
  try {
    await apiRequest<null>('/auth/logout', { method: 'POST', auth: false })
  } finally {
    currentUser = null
    setAccessToken(null)
  }
}

/** After a page reload the access token is gone: get a new one from the refresh cookie. */
export const restoreSession = (): Promise<boolean> => refreshAccessToken()

export function getCurrentUser(): Promise<CurrentUser> {
  currentUser ??= apiRequest<Schemas['CurrentUser']>('/auth/me').catch((error: unknown) => {
    currentUser = null
    throw error
  })
  return currentUser
}

/** What the sign-in screen shows: the «Забыли пароль?» link, or the contact of the administrator. */
export const getLoginInfo = (signal?: AbortSignal) =>
  apiRequest<Schemas['LoginInfo']>('/auth/login-info', { auth: false, signal })

/** Ask for a reset link; the answer is the same for every address, so it tells nothing (T-65). */
export const requestPasswordReset = (email: string) =>
  apiRequest<null>('/auth/password-reset', { method: 'POST', body: { email }, auth: false })

/** Set the new password by the token of the link from the letter. */
export const confirmPasswordReset = (token: string, password: string) =>
  apiRequest<null>('/auth/password-reset/confirm', {
    method: 'POST',
    body: { token, password },
    auth: false,
  })
