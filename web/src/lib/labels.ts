// The single dictionary of statuses and captions (ADR-013, DESIGN.md §3.11): the API returns
// codes, Russian strings live only here. A status string inside a component is a bug.
import type { IncidentStatus, QualityStatus, SchoolStatus, UserRole } from '../api/types'

/** Status of a school on the map and in lists (ТЗ п. 13); «Нет данных» is display-only (ADR-004). */
export const SCHOOL_STATUS_LABELS: Record<SchoolStatus, string> = {
  normal: 'Норма',
  unstable: 'Нестабильно',
  critical: 'Критично',
  offline: 'Нет соединения',
  no_data: 'Нет данных',
}

/** Quality of a measurement or a line, evaluated on the server (ADR-004). */
export const QUALITY_STATUS_LABELS: Record<QualityStatus, string> = {
  normal: SCHOOL_STATUS_LABELS.normal,
  unstable: SCHOOL_STATUS_LABELS.unstable,
  critical: SCHOOL_STATUS_LABELS.critical,
  offline: SCHOOL_STATUS_LABELS.offline,
}

/** Status of an incident (ТЗ п. 19, ADR-007). */
export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  new: 'Новый',
  sent_to_provider: 'Передан поставщику',
  in_progress: 'В работе',
  awaiting_info: 'Ожидает информации',
  resolved: 'Устранён',
  closed: 'Закрыт',
}

/** Fixed order of ТЗ п. 19: status stepper, kanban columns, filters. */
export const INCIDENT_STATUS_ORDER: readonly IncidentStatus[] = [
  'new',
  'sent_to_provider',
  'in_progress',
  'awaiting_info',
  'resolved',
  'closed',
]

/** Appeals go through the same six statuses as incidents (ADR-011). */
export const APPEAL_STATUS_LABELS: Record<IncidentStatus, string> = INCIDENT_STATUS_LABELS

/** Five roles of ТЗ п. 16 (ADR-008). */
export const ROLE_LABELS: Record<UserRole, string> = {
  school: 'Школа',
  district: 'Район/город',
  oblast: 'Область',
  provider: 'Провайдер',
  admin: 'Администратор',
}

/** Sections of the side navigation (DESIGN.md §3.6). */
export const SECTION_LABELS = {
  overview: 'Обзор',
  map: 'Карта',
  schools: 'Школы',
  devices: 'Устройства',
  analytics: 'Аналитика',
  incidents: 'Инциденты',
  appeals: 'Обращения',
  exports: 'Экспорт',
  admin: 'Администрирование',
} as const

export type SectionKey = keyof typeof SECTION_LABELS
