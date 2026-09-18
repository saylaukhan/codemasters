// The single dictionary of statuses and captions (ADR-013, DESIGN.md §3.11): the API returns
// codes, Russian strings live only here. A status string inside a component is a bug.
import type {
  AnalyticsLevel,
  AnalyticsPeriod,
  DeviceStatus,
  ExportAggregateColumn,
  ExportColumn,
  ExportFormat,
  ExportMode,
  ExportStatus,
  IfaceType,
  IncidentStatus,
  LineStatus,
  QualityStatus,
  SchoolStatus,
  UserRole,
  Weekday,
} from '../api/types'

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

/** Role of a line at a school (ТЗ п. 10, ADR-003). */
export const LINE_STATUS_LABELS: Record<LineStatus, string> = {
  main: 'Основная',
  reserve: 'Резервная',
  disabled: 'Отключена',
}

/** Blocking of a device keeps its history (ADR-005). */
export const DEVICE_STATUS_LABELS: Record<DeviceStatus, string> = {
  active: 'Активно',
  blocked: 'Заблокировано',
}

/** Network interface of a measurement; Wi-Fi does not rate the line (ADR-012). */
export const IFACE_LABELS: Record<IfaceType, string> = {
  ethernet: 'Ethernet',
  wifi: 'Wi‑Fi',
  other: 'Другое',
}

/** Period presets of charts and analytics (ТЗ п. 5); «Свой период» is a separate control. */
export const PERIOD_LABELS: Record<Exclude<AnalyticsPeriod, 'custom'>, string> = {
  today: 'Сегодня',
  week: '7 дней',
  month: '30 дней',
}

/** Period with explicit bounds, next to the presets. */
export const CUSTOM_PERIOD_LABEL = 'Свой период'

/** Grouping of the analytics rows (ТЗ п. 13): per school, district or city, provider, the oblast. */
export const ANALYTICS_LEVEL_LABELS: Record<AnalyticsLevel, string> = {
  school: 'Школы',
  district: 'Районы',
  provider: 'Провайдеры',
  region: 'Вся область',
}

/** Days of the week in Asia/Almaty (ADR-014): rows of the heatmap «час × день недели». */
export const WEEKDAY_LABELS: Record<Weekday, string> = {
  mon: 'Пн',
  tue: 'Вт',
  wed: 'Ср',
  thu: 'Чт',
  fri: 'Пт',
  sat: 'Сб',
  sun: 'Вс',
}

/** Monday first, as the week is read in Kazakhstan. */
export const WEEKDAY_ORDER: readonly Weekday[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

/** Five roles of ТЗ п. 16 (ADR-008). */
export const ROLE_LABELS: Record<UserRole, string> = {
  school: 'Школа',
  district: 'Район/город',
  oblast: 'Область',
  provider: 'Провайдер',
  admin: 'Администратор',
}

/** What an export contains (DESIGN.md §3.24): measurements, one row per school, PDF of a school. */
export const EXPORT_MODE_LABELS: Record<ExportMode, string> = {
  raw: 'Сырые данные',
  aggregates: 'Агрегаты по школе',
  school_report: 'PDF-отчёт',
}

/** State of an export's file (T-33): PDF and big exports are built in the background. */
export const EXPORT_STATUS_LABELS: Record<ExportStatus, string> = {
  pending: 'Готовится',
  ready: 'Готова',
  failed: 'Ошибка',
}

export const EXPORT_FORMAT_LABELS: Record<ExportFormat, string> = {
  xlsx: 'XLSX',
  csv: 'CSV',
  json: 'JSON',
  pdf: 'PDF',
}

/**
 * Columns of a raw export in the order of the file; the first eleven are the minimum of ТЗ п. 9.
 * The headers of XLSX and CSV repeat them: backend/app/services/exports/columns.py.
 */
export const EXPORT_COLUMN_LABELS: Record<ExportColumn, string> = {
  school_name: 'Школа',
  hostname: 'Компьютер',
  room: 'Кабинет',
  date: 'Дата',
  time: 'Время',
  download_mbps: 'Download, Мбит/с',
  upload_mbps: 'Upload, Мбит/с',
  ping_ms: 'Ping, мс',
  jitter_ms: 'Jitter, мс',
  packet_loss_pct: 'Packet Loss, %',
  quality_status: 'Статус',
  school_code: 'School ID',
  device_id: 'ID компьютера',
  line_status: 'Линия',
  connection_status: 'Связь',
  iface_type: 'Интерфейс',
  duration_s: 'Длительность замера, с',
  external_ip: 'Внешний IP',
  server: 'Сервер замера',
  agent_version: 'Версия агента',
}

/**
 * Columns of the aggregates in the order of the file: one row per school (ТЗ п. 9, T-31).
 * The headers of XLSX and CSV repeat them: backend/app/services/exports/columns.py.
 */
export const EXPORT_AGGREGATE_COLUMN_LABELS: Record<ExportAggregateColumn, string> = {
  school_code: 'School ID',
  school_name: 'Школа',
  measurements_count: 'Замеров',
  avg_download_mbps: 'Средний Download, Мбит/с',
  min_download_mbps: 'Минимальный Download, Мбит/с',
  avg_upload_mbps: 'Средний Upload, Мбит/с',
  avg_ping_ms: 'Средний Ping, мс',
  problem_count: 'Проблемных замеров',
  problem_pct: 'Доля проблемных, %',
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

/** Tabs of «Администрирование» (T-34): the key is the path under /admin. */
export const ADMIN_TAB_LABELS = {
  schools: 'Школы',
  regions: 'Районы и города',
  providers: 'Поставщики',
  'connection-types': 'Типы подключения',
} as const

export type AdminTabKey = keyof typeof ADMIN_TAB_LABELS

/** A school is deactivated, never deleted: its measurements and incidents stay (ТЗ п. 20). */
export const SCHOOL_ACTIVITY_LABELS = {
  active: 'Активна',
  disabled: 'Отключена',
} as const

export type SchoolActivity = keyof typeof SCHOOL_ACTIVITY_LABELS

/** Filter of the schools in the administration by activity. */
export const SCHOOL_ACTIVITY_FILTER_LABELS = {
  all: 'Все',
  active: 'Активные',
  disabled: 'Отключённые',
} as const

/** Boundary of a district or city: loaded from GeoJSON by the seed, drawn on the map. */
export const REGION_BOUNDARY_LABELS = {
  loaded: 'Загружена',
  missing: 'Нет',
} as const
