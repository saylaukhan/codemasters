// The single dictionary of statuses and captions (ADR-013, DESIGN.md §3.11): the API returns
// codes, Russian strings live only here. A status string inside a component is a bug.
import type {
  AnalyticsLevel,
  AuditAction,
  AuditEntityType,
  AnalyticsPeriod,
  DeviceStatus,
  ExportAggregateColumn,
  ExportColumn,
  ExportFormat,
  ExportMode,
  ExportStatus,
  IfaceType,
  IncidentEventKind,
  IncidentMetric,
  IncidentStatus,
  LineStatus,
  NotificationKind,
  QualityStatus,
  ScheduleScope,
  SchoolStatus,
  ThresholdProfileScope,
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

/** Switch of the incidents section (DESIGN.md §3.18): the table of T-41 or the kanban of T-43. */
export const INCIDENT_VIEW_LABELS = {
  list: 'Список',
  board: 'Доска',
} as const

export type IncidentViewKey = keyof typeof INCIDENT_VIEW_LABELS

/** Entry of the incident history (`incident_events`, ADR-007); a status change is written «Статус: A → B». */
export const INCIDENT_EVENT_LABELS: Record<IncidentEventKind, string> = {
  created: 'Инцидент создан',
  status_change: 'Статус',
  comment: 'Комментарий',
  restored: 'Показатели восстановлены',
}

/** Author of an entry without a person: the detection of T-40 or the automatic closing after 24 h. */
export const SYSTEM_AUTHOR_LABEL = 'Система'

/** Appeals go through the same six statuses as incidents (ADR-011). */
export const APPEAL_STATUS_LABELS: Record<IncidentStatus, string> = INCIDENT_STATUS_LABELS

/** What the notification is about (T-42, ТЗ п. 18): every one of them follows an incident. */
export const NOTIFICATION_KIND_LABELS: Record<NotificationKind, string> = {
  incident_opened: 'Новый инцидент',
  incident_status_changed: 'Смена статуса инцидента',
  incident_restored: INCIDENT_EVENT_LABELS.restored,
}

/** Tabs of the notification panel (DESIGN.md §3.23). */
export const NOTIFICATION_TAB_LABELS = {
  all: 'Все',
  unread: 'Непрочитанные',
} as const

export type NotificationTabKey = keyof typeof NOTIFICATION_TAB_LABELS

/** Bell of the header (DESIGN.md §3.5) and the captions of its panel (§3.23). */
export const NOTIFICATIONS_TITLE = 'Уведомления'
export const NOTIFICATIONS_READ_ALL_LABEL = 'Отметить все как прочитанные'
export const NOTIFICATIONS_EMPTY_LABEL = 'Уведомлений пока нет'
export const NOTIFICATIONS_UNREAD_EMPTY_LABEL = 'Непрочитанных уведомлений нет'

/** More unread than the counter of the bell can show: «99+». */
export const NOTIFICATIONS_OVERFLOW_LABEL = '99+'

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

/** A user is blocked, never deleted: his actions stay in the audit log (ТЗ п. 16, T-38). */
export const USER_STATUS_LABELS = {
  active: 'Активен',
  blocked: 'Заблокирован',
} as const

export type UserStatus = keyof typeof USER_STATUS_LABELS

/** Scope of Область and Администратор: no district, provider or school of their own (ADR-008). */
export const WHOLE_OBLAST_SCOPE_LABEL = 'Вся область'

/** Filter of the devices and of the users in the administration by status (T-36, T-38). */
export const DEVICE_STATUS_FILTER_LABELS = {
  all: 'Все',
  active: 'Активные',
  blocked: 'Заблокированные',
} as const

/** A new token of a device is requested and its agent has not taken it yet (T-36, ADR-005). */
export const TOKEN_ROTATION_PENDING_LABEL = 'Ждёт замены токена'

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

/** One entity of a level: title of the first column of a table of the analytics. */
export const ANALYTICS_ENTITY_LABELS: Record<AnalyticsLevel, string> = {
  school: 'Школа',
  district: 'Район/город',
  provider: 'Провайдер',
  region: 'Область',
}

/** Tabs of «Аналитика» (DESIGN.md §3.8): the metrics of T-27 and the incidents of T-45. */
export const ANALYTICS_TAB_LABELS = {
  quality: 'Показатели',
  incidents: 'Инциденты',
} as const

export type AnalyticsTabKey = keyof typeof ANALYTICS_TAB_LABELS

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

/** Caption of a screen in the provider cabinet (T-44, ТЗ п. 16): his lists hold only his own lines. */
export const PROVIDER_SCOPE_HINTS = {
  schools: 'Показаны только школы с вашими линиями',
  incidents: 'Показаны только инциденты ваших линий',
} as const

/** Tabs of «Администрирование» (T-34): the key is the path under /admin. */
export const ADMIN_TAB_LABELS = {
  schools: 'Школы',
  devices: 'Устройства',
  users: 'Пользователи',
  regions: 'Районы и города',
  providers: 'Поставщики',
  'connection-types': 'Типы подключения',
  thresholds: 'Пороги',
  schedules: 'Расписания',
  'incident-rules': 'Правила инцидентов',
  settings: 'Настройки',
  audit: 'Аудит',
  events: 'События',
} as const

export type AdminTabKey = keyof typeof ADMIN_TAB_LABELS

/** Target of a threshold profile (ADR-004): the most specific active one judges a measurement. */
export const PROFILE_SCOPE_LABELS: Record<ThresholdProfileScope, string> = {
  global: 'Вся область',
  district: 'Район или город',
  line: 'Линия',
}

/** Target of a measurement schedule (T-17): the most specific active one reaches the agent. */
export const SCHEDULE_SCOPE_LABELS: Record<ScheduleScope, string> = {
  global: 'Вся область',
  district: 'Район или город',
  school: 'Школа',
}

/** Metric an incident rule watches on every line (ТЗ п. 18, ADR-007): the names of the thresholds page. */
export const INCIDENT_METRIC_LABELS: Record<IncidentMetric, string> = {
  download_mbps: 'Download',
  upload_mbps: 'Upload',
  ping_ms: 'Ping',
  jitter_ms: 'Jitter',
  packet_loss_pct: 'Packet Loss',
  no_connection: SCHOOL_STATUS_LABELS.offline,
}

/** A profile or a schedule is switched off, never deleted: the next one of its chain applies (T-37). */
export const CONFIG_ACTIVITY_LABELS = {
  active: 'Действует',
  disabled: 'Отключено',
} as const

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

/** What happened, in the audit log (T-39, ТЗ п. 12, п. 16). */
export const AUDIT_ACTION_LABELS: Record<AuditAction, string> = {
  login_success: 'Вход',
  login_failure: 'Неудачный вход',
  create: 'Создание',
  update: 'Изменение',
  block: 'Блокировка',
  unblock: 'Разблокировка',
  password_reset: 'Сброс пароля',
  status_change: 'Смена статуса',
  export: 'Экспорт',
  transfer_error: 'Ошибка передачи',
}

/** Kind of record an action of the audit log touched. */
export const AUDIT_ENTITY_LABELS: Record<AuditEntityType, string> = {
  user: 'Пользователь',
  school: 'Школа',
  line: 'Линия',
  monitoring_point: 'Точка мониторинга',
  school_contact: 'Ответственный',
  device: 'Устройство',
  enrollment_code: 'Код установки',
  region: 'Район или город',
  provider: 'Поставщик',
  connection_type: 'Тип подключения',
  threshold_profile: 'Профиль порогов',
  schedule: 'Расписание',
  setting: 'Настройки',
  incident_rule: 'Правило инцидентов',
  agent_release: 'Релиз агента',
  incident: 'Инцидент',
  appeal: 'Обращение',
  export: 'Выгрузка',
}

/** Why a sign-in or an agent request was refused: `type` of the problem (ADR-009); another code is shown as is. */
export const AUDIT_ERROR_LABELS: Record<string, string> = {
  invalid_credentials: 'Неверный e-mail или пароль',
  account_blocked: 'Учётная запись заблокирована',
  unauthorized: 'Токен устройства отсутствует или недействителен',
  device_blocked: 'Устройство заблокировано',
  validation_error: 'Невалидные данные',
  bad_request: 'Некорректный запрос',
  payload_too_large: 'Слишком большой запрос',
  unsupported_media_type: 'Неподдерживаемый формат запроса',
}

/** Changed fields in the audit log, by their camelCase key; another field is shown by its key. */
export const AUDIT_FIELD_LABELS: Record<string, string> = {
  name: 'Название',
  fullName: 'ФИО',
  email: 'E-mail',
  phone: 'Телефон',
  position: 'Должность',
  role: 'Роль',
  isActive: 'Активен',
  status: 'Статус',
  address: 'Адрес',
  schoolCode: 'Код школы',
  schoolId: 'Школа',
  regionId: 'Район или город',
  providerId: 'Поставщик',
  connectionTypeId: 'Тип подключения',
  lineId: 'Линия',
  room: 'Кабинет',
  contractNumber: 'Номер договора',
  contractDownMbps: 'Download по договору',
  contractUpMbps: 'Upload по договору',
  thresholds: 'Пороги',
  slots: 'Слоты',
  workingHours: 'Рабочие часы',
  speedtest: 'Сервер замеров',
}

/** Empty value of a changed field in the audit log. */
export const AUDIT_EMPTY_VALUE_LABEL = 'пусто'

/** Yes-or-no value of a changed field in the audit log. */
export const AUDIT_BOOLEAN_LABELS = { true: 'да', false: 'нет' } as const
