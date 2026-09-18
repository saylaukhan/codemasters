// Users of the administration (T-38): the scope a role needs, the password rules and the bodies of the user form.
import type { FormRule } from 'antd'

import type { UserCreate, UserDetail, UserRole, UserUpdate } from '../../api/types'
import { maxLength } from './form'

// The shortest password the API takes (backend/app/schemas/users.py) and the longest one.
const PASSWORD_MIN_LENGTH = 8
const PASSWORD_MAX_LENGTH = 128

/** Rules of a password set by the administrator: a new user's first one or a reset. */
export const PASSWORD_RULES: FormRule[] = [
  { required: true, message: 'Введите пароль' },
  { min: PASSWORD_MIN_LENGTH, message: `Не короче ${PASSWORD_MIN_LENGTH} символов` },
  maxLength(PASSWORD_MAX_LENGTH),
]

type ScopeField = 'regionId' | 'providerId' | 'schoolId'

/** The one scope id of a role (ADR-008); null — the role sees the whole oblast. */
export const ROLE_SCOPE_FIELD: Record<UserRole, ScopeField | null> = {
  school: 'schoolId',
  district: 'regionId',
  provider: 'providerId',
  oblast: null,
  admin: null,
}

export interface UserFormValues {
  fullName: string
  email: string
  role?: UserRole
  regionId?: number
  providerId?: number
  /** With its label: a school picked from one search stays named when the search changes. */
  schoolId?: { value: number; label: string }
  /** Only of a new user; an existing one gets a new password from «Сбросить пароль». */
  password?: string
}

export const userFormValues = (user?: UserDetail): UserFormValues => ({
  fullName: user?.fullName ?? '',
  email: user?.email ?? '',
  role: user?.role,
  regionId: user?.scope.regionId ?? undefined,
  providerId: user?.scope.providerId ?? undefined,
  schoolId:
    user?.scope.schoolId != null
      ? { value: user.scope.schoolId, label: user.scopeName ?? String(user.scope.schoolId) }
      : undefined,
})

type RoleWithScope = Pick<UserCreate, 'role' | 'regionId' | 'providerId' | 'schoolId'>

/** The role with its own scope id only: the API takes them together and clears the ids of other roles. */
function roleWithScope({ role, regionId, providerId, schoolId }: UserFormValues): RoleWithScope {
  const field = ROLE_SCOPE_FIELD[role as UserRole]
  const ids: Record<ScopeField, number | undefined> = { regionId, providerId, schoolId: schoolId?.value }
  return field ? { role: role as UserRole, [field]: ids[field] } : { role: role as UserRole }
}

export const userCreateBody = (values: UserFormValues): UserCreate => ({
  email: values.email.trim(),
  fullName: values.fullName.trim(),
  ...roleWithScope(values),
  password: values.password ?? '',
})

/** PATCH of the changed fields; the role travels with its scope when either of them changed. */
export function userUpdateBody(initial: UserFormValues, values: UserFormValues): UserUpdate {
  const body: UserUpdate = {}
  if (values.email.trim() !== initial.email) body.email = values.email.trim()
  if (values.fullName.trim() !== initial.fullName) body.fullName = values.fullName.trim()
  const scope = roleWithScope(values)
  if (JSON.stringify(scope) !== JSON.stringify(roleWithScope(initial))) Object.assign(body, scope)
  return body
}
