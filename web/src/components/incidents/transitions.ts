// Transitions of an incident's status (T-41, ADR-007): the table the API checks in POST /api/incidents/{id}/status,
// repeated here only to offer what will be accepted. The card and the kanban of T-43 both read it.
import type { CurrentUser, IncidentStatus, UserRole } from '../../api/types'

/**
 * Forward in the order of ТЗ п. 19, «Передан поставщику», «В работе» and «Ожидает информации» may be skipped;
 * «Закрыт» only from «Устранён»; back only «Ожидает информации» → «В работе» and «Устранён» → «В работе» (the
 * problem came back before closing); nothing out of «Закрыт». The same status is not a transition.
 */
export const INCIDENT_TRANSITIONS: Record<IncidentStatus, readonly IncidentStatus[]> = {
  new: ['sent_to_provider', 'in_progress', 'awaiting_info', 'resolved'],
  sent_to_provider: ['in_progress', 'awaiting_info', 'resolved'],
  in_progress: ['awaiting_info', 'resolved'],
  awaiting_info: ['in_progress', 'resolved'],
  resolved: ['in_progress', 'closed'],
  closed: [],
}

/** Roles that close an incident (ADR-007): Район/город, Область, Администратор; the provider does not. */
export const CLOSING_ROLES: readonly UserRole[] = ['district', 'oblast', 'admin']

/** Permission of backend/app/auth/permissions.py to change the status, the responsible and to comment. */
export const UPDATE_PERMISSION = 'incidents:update'

/** Permission to create an incident by hand from the school card. */
export const CREATE_PERMISSION = 'incidents:create'

export const isTransition = (from: IncidentStatus, to: IncidentStatus): boolean =>
  INCIDENT_TRANSITIONS[from].includes(to)

export const canClose = (role: UserRole | undefined): boolean => role !== undefined && CLOSING_ROLES.includes(role)

export const canUpdate = (user: Pick<CurrentUser, 'permissions'> | undefined): boolean =>
  user?.permissions.includes(UPDATE_PERMISSION) ?? false

/**
 * Statuses the user may move an incident to from `from`, in the order of ТЗ п. 19: none without `incidents:update`,
 * «Закрыт» only for a closing role.
 */
export function allowedTargets(
  from: IncidentStatus,
  user: Pick<CurrentUser, 'role' | 'permissions'> | undefined,
): IncidentStatus[] {
  if (!canUpdate(user)) return []
  return INCIDENT_TRANSITIONS[from].filter((to) => to !== 'closed' || canClose(user?.role))
}

/** A move the user may make: the kanban of T-43 accepts a drop only here. */
export const canMove = (
  from: IncidentStatus,
  to: IncidentStatus,
  user: Pick<CurrentUser, 'role' | 'permissions'> | undefined,
): boolean => allowedTargets(from, user).includes(to)

/** A comment is required to close an incident (DESIGN.md §3.17); the API answers 422 without it. */
export const commentRequired = (to: IncidentStatus | undefined): boolean => to === 'closed'
