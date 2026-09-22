// The single dictionary of statuses and captions (ADR-013, DESIGN.md §3.11): the API returns
// codes, Russian strings live only here. A status string inside a component is a bug.
import type {
  AnalyticsLevel,
  AnalyticsPeriod,
  AppealDeliveryStatus,
  AttentionReason,
  AuditAction,
  AuditEntityType,
  DeviceStatus,
  DigestScope,
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
  NotificationChannel,
  NotificationKind,
  NotificationResult,
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

/**
 * «Нет данных» is display-only and never stands without a reason (DESIGN.md §4.1): the agent is
 * silent, so there is nothing to judge the connection by.
 */
export const NO_DATA_HINT = 'Компьютер выключен или нерабочее время'

/** The same for a blocked computer: the server declines its measurements, the history stays (ADR-005). */
export const NO_DATA_BLOCKED_HINT = 'Компьютер заблокирован, история сохранена'

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

/**
 * Hint under «Новый статус» of the card (DESIGN.md §3.17, T-63): the whole row of the table of transitions,
 * «Доступно: В работе, Ожидает информации, Устранён». A status with nothing left says so instead.
 */
export const INCIDENT_TARGETS_LABELS = {
  available: 'Доступно',
  none: 'Из этого статуса переходов нет',
} as const

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

/**
 * Captions of an appeal to the provider (ТЗ п. 17, DESIGN.md §3.19): the draft opens from the card of an incident
 * or of a school (T-47), the number is assigned by the sending (T-48) and the letter stays in the list with it.
 */
export const APPEAL_LABELS = {
  create: 'Создать обращение',
  draft: 'Черновик обращения',
  send: 'Отправить обращение',
  sent: 'Обращение отправлено',
  sendFailed: 'Обращение не отправлено',
  regenerate: 'Перегенерировать',
  regenerateHint: 'Модель напишет письмо заново: текст в редакторе будет заменён',
  aiNote: 'Черновик создан автоматически. Проверьте перед отправкой.',
  letter: 'Письмо',
  facts: 'Сведения',
  history: 'История',
  statusChange: 'Смена статуса',
  userComment: 'Комментарий отправителя',
  noUserComment: 'Комментарий не оставлен',
  pdf: 'Скачать PDF',
  pdfFailed: 'PDF не скачан',
  search: 'Поиск по номеру обращения',
  empty: 'Обращений нет',
  emptyHint: 'Обращение появляется здесь после отправки письма поставщику.',
  filteredEmpty: 'По заданным фильтрам ничего не найдено',
  filteredEmptyHint: 'Измените или сбросьте фильтры.',
  notFound: 'Обращение не найдено',
  notFoundHint: 'Его нет или оно вне вашей области видимости.',
  /** Under «Отправить» of a draft about an incident: the sending hands the incident over itself (T-63, ADR-007). */
  incidentHandover: 'После отправки инцидент в статусе «Новый» перейдёт в «Передан поставщику»',
  noTarget: 'Обращение не о чем',
  noTargetHint: 'Откройте черновик кнопкой «Создать обращение» в карточке инцидента или школы.',
} as const

/** Columns of the incident list (T-41), header of `IncidentTable`. */
export const INCIDENT_COLUMN_LABELS = {
  number: 'Номер',
  school: 'Школа',
  status: 'Статус',
  line: 'Линия и поставщик',
  basis: 'Основания',
  startedAt: 'Начало',
  duration: 'Длительность',
  responsible: 'Ответственный',
} as const

/** Footer of a paged table: «1–25 из 143». */
export const TABLE_PAGINATION_LABELS = {
  total: (from: number, to: number, count: number) => `${from}–${to} из ${count}`,
} as const

/** Columns of the appeal list (T-48). */
export const APPEAL_COLUMN_LABELS = {
  number: 'Номер',
  status: 'Статус',
  school: 'Школа',
  provider: 'Поставщик',
  subject: 'Тема',
  sentAt: 'Отправлено',
  delivery: 'Доставка письма',
} as const

/** Captions of the appeal card, left of the values (DESIGN.md §3.17). */
export const APPEAL_FIELD_LABELS = {
  school: 'Школа',
  schoolCode: 'School ID',
  provider: 'Поставщик',
  line: 'Линия',
  incident: 'Инцидент',
  period: 'Период',
  sentAt: 'Отправлено',
  recipient: 'Получатель',
  delivery: 'Доставка письма',
  contract: 'Договор',
  contractDown: 'Договор Download',
  contractUp: 'Договор Upload',
  measurements: 'Замеров',
  problems: 'Проблемных замеров',
  outages: 'Простоев',
  outagesDuration: 'Длительность простоев',
  /** Next to the average of a metric: the threshold it was judged by (ТЗ п. 11, ADR-004). */
  threshold: 'порог',
} as const

/** Captions of the fields a person fills in: the editor of the draft (T-47) and the status form of the card (T-48). */
export const APPEAL_FORM_LABELS = {
  subject: 'Тема',
  text: 'Текст письма',
  comment: 'Комментарий',
  requiredComment: 'Комментарий, обязателен',
  status: 'Новый статус',
} as const

/**
 * Did the letter go (T-48): without SMTP or without an address of the provider the appeal is kept anyway, with
 * its number and its PDF, and says so (ADR-011, «Решения по умолчанию»).
 */
export const APPEAL_DELIVERY_LABELS: Record<AppealDeliveryStatus, string> = {
  sent: 'Отправлено',
  not_sent: 'Не отправлено',
}

/** Next to «Не отправлено»: the appeal itself is kept, only the mail did not go. */
export const APPEAL_NOT_SENT_HINT = 'Письмо не ушло, обращение и PDF сохранены'

/** The provider has no `appeals_email`: the appeal is kept with its PDF, the letter goes nowhere (ADR-011). */
export const APPEAL_NO_RECIPIENT_HINT = 'Адрес не задан, письмо не уйдёт'

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

/** Monitoring point of a school: one of them is the point the school is judged by (ТЗ п. 10). */
export const MONITORING_POINT_LABELS = {
  primary: 'Главная точка школы',
} as const

/** Note next to the interface of a measurement: Wi-Fi is not read as the quality of the line. */
export const IFACE_NOTE_LABELS = {
  wifi: 'Не оценивает линию',
} as const

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

/** Summary of the export constructor (DESIGN.md §3.24, T-64): «Будет выгружено ≈ 12 480 строк». */
export const EXPORT_ESTIMATE_LABELS = {
  title: 'Будет выгружено',
  /** Sign of an estimate: m_daily counts a touched day whole and holds no Wi-Fi. */
  approximate: '≈',
  rows: 'строк',
  loading: 'считаем…',
  error: 'не удалось оценить',
} as const

/** Sections of the side navigation (DESIGN.md §3.6). */
export const SECTION_LABELS = {
  overview: 'Обзор',
  map: 'Карта',
  schools: 'Школы',
  devices: 'Устройства',
  analytics: 'Аналитика',
  incidents: 'Инциденты',
  appeals: 'Обращения',
  providers: 'Поставщики',
  rollout: 'Внедрение',
  exports: 'Отчёты и экспорт',
  admin: 'Администрирование',
} as const

export type SectionKey = keyof typeof SECTION_LABELS

/** Caption of a screen in the provider cabinet (T-44, ТЗ п. 16): his lists hold only his own lines. */
export const PROVIDER_SCOPE_HINTS = {
  schools: 'Показаны только школы с вашими линиями',
  incidents: 'Показаны только инциденты ваших линий',
  appeals: 'Показаны только обращения по вашим линиям',
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
  resetLink: 'Ссылка на смену пароля',
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

/** Forms of «школа» for a counted number: the status strip prints «312 школ», «21 школа» (§3.10). */
export const SCHOOL_COUNT_FORMS = ['школа', 'школы', 'школ'] as const

/** Change of a status column over the last day (DESIGN.md §3.10): «▲ 3 за сутки», «без изменений». */
export const DAY_DELTA_LABELS = {
  up: '▲',
  down: '▼',
  period: 'за сутки',
  none: 'без изменений',
} as const

/** Filter bar, DESIGN.md §3.9: the chip clears its own value, the link clears the whole bar. */
export const FILTER_BAR_LABELS = {
  reset: 'Сбросить',
  clear: 'Очистить фильтр',
} as const

/** Dimensions of the filter bar of the map, the overview and the analytics (DESIGN.md §3.9). */
export const MAP_FILTER_LABELS = {
  level: 'Уровень',
  region: 'Район',
  provider: 'Провайдер',
  connectionType: 'Тип подключения',
  status: 'Статус',
  period: 'Период',
} as const

/** Bottom sheet the filters fold into on a phone (DESIGN.md §9.3, row «Панель фильтров»). */
export const FILTER_SHEET_LABELS = {
  open: 'Фильтры',
  title: 'Фильтры',
} as const

/** Legend of the map (DESIGN.md §3.13); on a narrow screen it folds into one button (§9.3). */
export const MAP_LEGEND_LABELS = {
  title: 'Легенда',
  show: 'Показать легенду',
  hide: 'Скрыть легенду',
} as const

/** Bar «fact against the threshold» under a metric tile (DESIGN.md §3.10, §3.27). */
export const FACT_BAR_LABELS = {
  normFrom: 'норма от',
  normTo: 'норма до',
  contract: 'по договору',
  lowerIsBetter: 'чем меньше, тем лучше',
} as const

/** Controls of `ResponsiveTable` (DESIGN.md §3.12): the phone sorts with a select above the list. */
export const RESPONSIVE_TABLE_LABELS = {
  sort: 'Сортировка',
  defaultOrder: 'По умолчанию',
} as const

/** Rating of «Аналитика»: a phone card carries the place in place of the status pill (§3.12). */
export const RATING_LABELS = {
  place: 'Место',
  placeOf: (rank: string) => `Место ${rank}`,
  wholeRegion: 'Вся ВКО',
} as const

/** Controls of the side navigation and of its drawer (DESIGN.md §3.5, §3.6, §9.3). */
export const NAVIGATION_LABELS = {
  open: 'Открыть меню',
  title: 'Разделы',
  expand: 'Развернуть меню',
  fold: 'Свернуть меню',
} as const

/** Blocks of the main screen of the oblast and of a district (DESIGN.md §3.28, `Main.html`). */
export const OVERVIEW_LABELS = {
  statusStrip: 'Школы по статусу',
  map: 'Карта области',
  mapOpen: 'Открыть карту',
  attention: 'Требуют внимания',
  kpi: 'Показатели за период',
  kpiCompare: 'к предыдущему периоду',
  incidents: 'Последние инциденты',
  incidentsAll: 'Все инциденты',
  incidentsEmpty: 'Открытых инцидентов нет',
  incidentsEmptyHint: 'Инцидент открывается, когда показатели линии нарушают правило подряд или дольше заданного.',
  /** No previous period to compare with, so the delta line says so instead (docs/design/README.md §4.1). */
  firstData: 'первые данные',
  /** Caption of the context above the title: «Вся область · 350 школ» (DESIGN.md §3.7). */
  context: (scope: string, count: string, noun: string) => `${scope} · ${count} ${noun}`,
  subtitle: (time: string) => `Данные на ${time} · основные линии`,
  /** «Нет данных» is display-only (ADR-004): a footnote under the strip, not a fifth column. */
  noData: (count: string, noun: string) => `${SCHOOL_STATUS_LABELS.no_data}: ${count} ${noun}`,
} as const

/** Verdict of the main screen (DESIGN.md §3.28): the title is a sentence about the whole selection. */
export const OVERVIEW_VERDICT_LABELS = {
  loading: 'Собираем данные',
  empty: 'Школ по заданным фильтрам нет',
  all: (count: string, noun: string) => `Все ${count} ${noun} сегодня в норме`,
  part: (normal: string, noun: string, total: string) => `${normal} ${noun} из ${total} сегодня в норме`,
} as const

/** The eight KPIs of ТЗ п. 4 on the main screen; the captions are those of `Main.html`. */
export const OVERVIEW_KPI_LABELS = {
  schools: 'Подключённые школы',
  devices: 'Компьютеры с агентом',
  activeDevices: 'На связи сейчас',
  measurements: 'Замеров за период',
  avgDownload: 'Средняя загрузка',
  avgUpload: 'Средняя отдача',
  avgPing: 'Средний отклик',
  problemDevices: 'Проблемные устройства',
  registry: (total: string) => `из ${total} в реестре`,
  of: (total: string) => `из ${total}`,
} as const

/** Why a row of «Требуют внимания» is there; an incident says its metric instead (§4.1). */
export const ATTENTION_REASON_LABELS: Record<AttentionReason, string> = {
  offline: 'Нет связи',
  critical: SCHOOL_STATUS_LABELS.critical,
  incident_unassigned: 'Инцидент',
  appeal_unanswered: 'Обращение без ответа',
}

/**
 * Metric of an incident row of «Требуют внимания», in the words of `Main.html`: the English terms
 * of `INCIDENT_METRIC_LABELS` belong to the incident card, not to this list (docs/design §4.1).
 */
export const ATTENTION_METRIC_LABELS: Record<IncidentMetric, string> = {
  download_mbps: 'Загрузка',
  upload_mbps: 'Отдача',
  ping_ms: 'Отклик',
  jitter_ms: 'Дрожание',
  packet_loss_pct: 'Потери',
  no_connection: ATTENTION_REASON_LABELS.offline,
}

/** Second line of a row of «Требуют внимания»: since when it has been so. */
export const ATTENTION_LABELS = {
  since: (moment: string) => `с ${moment}`,
  unassignedSince: (moment: string) => `без ответственного с ${moment}`,
  more: (count: string, noun: string) => `Ещё ${count} ${noun}`,
  empty: 'Ничего не требует внимания',
  emptyHint: 'Школы без связи, инциденты без ответственного и обращения без ответа появятся здесь.',
} as const
/**
 * Words of the school cabinet (T-61, DESIGN.md §3.27, docs/design/README.md §4.2): the director
 * reads the same data in plainer words than the panel. Taken from `docs/design/mockups/School.html`
 * and `SchoolPhone.html` verbatim.
 */
export const CABINET_LABELS = {
  report: 'Отчёт за месяц',
  reportProblem: 'Сообщить о проблеме',
  checked: 'Проверено',
  checkedToday: 'Проверено сегодня в',
  neverChecked: 'Замеров ещё не было',
  tiles: 'Текущие показатели',
  download: 'Скорость загрузки',
  upload: 'Скорость отдачи',
  ping: 'Отклик',
  jitter: 'Дрожание',
  jitterLow: 'дрожание',
  packetLoss: 'потери пакетов',
  packetLossShort: 'потери',
  availability: 'доступность за 7 дней',
  availabilityCap: 'Доступность за 7 дней',
  allMeasurements: 'Все замеры',
  days: 'Последние 30 дней',
  week: 'Скорость загрузки за 7 дней',
  norm: 'норма',
  contractMark: 'договор',
  contract: 'Провайдер и договор',
  support: 'Поддержка поставщика',
  callSupport: 'Позвонить в поддержку',
  roundClock: 'круглосуточно',
  from: 'от',
  agent: 'Компьютер с агентом',
  agentSignal: 'Сигнал',
  agentVersion: 'агент',
  agentNote: 'Выключен = «Нет данных», не проблема интернета',
  problems: 'Проблемы и обращения',
  problem: 'Проблема со связью',
  history: 'Вся история',
  all: 'Все',
  since: 'с',
  goesOn: 'продолжается',
  contacts: 'Кому звонить',
  today: 'сегодня',
} as const

/** English term next to the caption of a tile: «Скорость загрузки · Download» (DESIGN.md §3.27). */
export const CABINET_TERM_LABELS = {
  download: 'Download',
  upload: 'Upload',
  ping: 'Ping',
} as const

/** How the last measurement reached the network, in the words of the cabinet, not of the panel. */
export const CABINET_IFACE_LABELS: Record<IfaceType, string> = {
  ethernet: 'по кабелю',
  wifi: 'по Wi‑Fi',
  other: 'по другой сети',
}

/**
 * Verdict of the cabinet, chosen by `components/schools/cabinet.ts` from the status of the school
 * and from what exactly is broken (docs/design/README.md §4.2). «Интернета нет с» takes the time
 * of the last measurement next to it; without that moment the shorter «Интернета нет» is printed.
 */
export const CABINET_VERDICT_LABELS = {
  normal: 'Интернет в норме',
  slowContract: 'Интернет медленнее, чем по договору',
  slowNorm: 'Интернет медленнее, чем положено',
  unstable: 'Интернет работает с перебоями',
  offline: 'Интернета нет',
  offlineSince: 'Интернета нет с',
  noData: 'Компьютер с агентом выключен',
} as const

export type CabinetVerdictKey = keyof typeof CABINET_VERDICT_LABELS

/** Summary over the day strip: «28 в норме · 1 перебои · 1 без связи» (DESIGN.md §3.27). */
export const CABINET_DAY_LABELS = {
  normal: 'в норме',
  problem: 'перебои',
  offline: 'без связи',
  noData: 'без данных',
} as const

/** Captions of «Провайдер и договор», left of the values. */
export const CABINET_FIELD_LABELS = {
  provider: 'Поставщик',
  connection: 'Подключение',
  contract: 'По договору',
  contractNumber: 'Договор',
} as const

/** Role of a line in the words of the cabinet: the panel writes the same three with a capital. */
export const CABINET_LINE_LABELS: Record<LineStatus, string> = {
  main: 'основная линия',
  reserve: 'резервная линия',
  disabled: 'линия отключена',
}

/** Cards of «Кому звонить»: the school's own responsible and the support of its provider (ТЗ п. 15). */
export const CABINET_CONTACT_LABELS = {
  school: 'Ответственный в школе',
  support: 'Поддержка',
  supportName: 'Техническая поддержка',
  call: 'Позвонить',
} as const

/**
 * The same six statuses of ТЗ п. 19 in the words of the cabinet (docs/design/README.md §4.2):
 * «У поставщика» instead of «Передан поставщику». `IncidentStatusBadge` takes this dictionary
 * instead of the default one, so no Russian string enters a component (ADR-013).
 */
export const CABINET_APPEAL_STATUS_LABELS: Record<IncidentStatus, string> = {
  new: 'Зарегистрировано',
  sent_to_provider: 'У поставщика',
  in_progress: 'В работе',
  awaiting_info: 'Ждём ответа',
  resolved: 'Решено',
  closed: 'Закрыто',
}

/** Empty states and notices of the cabinet: what the director sees instead of a block that has no data. */
export const CABINET_NOTICE_LABELS = {
  notFound: 'Школа не найдена',
  notFoundHint: 'Её нет или она вне вашей области видимости.',
  noDays: 'Дней с замерами ещё нет',
  noWeek: 'Замеров за неделю нет',
  noWeekHint: 'Проверьте, включён ли компьютер с агентом.',
  noLine: 'Линия не заведена',
  noDevice: 'Компьютера с агентом нет',
  noDeviceHint: 'Агент ещё не установлен ни на один ПК школы.',
  noProblems: 'Проблем не было',
  noProblemsHint: 'Здесь появятся перебои со связью и письма поставщику.',
  noContacts: 'Контактов нет',
  noAppealLine: 'У школы нет действующей линии',
  reportPending: 'Отчёт ещё готовится',
  reportPendingHint: 'Скачайте его в разделе «Отчёты и экспорт», когда он будет готов.',
  reportFailed: 'Отчёт не сформирован',
} as const

/** What broke, in the words of the cabinet: the panel calls the same metrics by their English terms. */
export const CABINET_METRIC_LABELS: Record<IncidentMetric, string> = {
  download_mbps: 'Скорость загрузки ниже нормы',
  upload_mbps: 'Скорость отдачи ниже нормы',
  ping_ms: 'Долгий отклик',
  jitter_ms: 'Неровный сигнал',
  packet_loss_pct: 'Теряются пакеты',
  no_connection: 'Не было связи',
}


/**
 * «Забыли пароль?» of the sign-in screen and the page of the link from the letter (T-65,
 * docs/design/README.md §4.6). The answer of the API says nothing about the address, so the
 * notice after a request is the same for every e-mail.
 */
export const PASSWORD_RESET_LABELS = {
  link: 'Забыли пароль?',
  requestTitle: 'Смена пароля',
  requestHint: 'Пришлём ссылку на смену пароля на e-mail учётной записи.',
  email: 'E-mail',
  emailRequired: 'Введите e-mail',
  send: 'Отправить ссылку',
  cancel: 'Отмена',
  sent: 'Если такой адрес есть, мы отправили на него ссылку',
  requestFailed: 'Не удалось отправить ссылку, попробуйте ещё раз',
  supportTitle: 'Пароль меняет администратор',
  confirmTitle: 'Новый пароль',
  confirmHint: 'Ссылка действует один раз. После смены пароля войдите с новым паролем.',
  password: 'Новый пароль',
  repeat: 'Повторите пароль',
  repeatRequired: 'Повторите пароль',
  mismatch: 'Пароли не совпадают',
  save: 'Сохранить пароль',
  invalid: 'Ссылка недействительна или устарела — запросите новую',
  done: 'Пароль изменён, войдите с новым паролем',
  toLogin: 'Вернуться к входу',
} as const

/**
 * Language switch of the header and of the sign-in screen (DESIGN.md §3.5, §3.26, T-66): every
 * language is named in its own language, so the pill reads «Қаз · Рус» in both dictionaries.
 */
export const LOCALE_LABELS = {
  title: 'Язык интерфейса',
  ru: 'Рус',
  kk: 'Қаз',
} as const

/** Экран входа (DESIGN.md §3.26) и профиль в шапке (§3.5): строки, которые раньше жили в компонентах. */
export const SIGN_IN_LABELS = {
  title: 'Вход в систему',
  email: 'E-mail',
  password: 'Пароль',
  emailRequired: 'Введите e-mail',
  passwordRequired: 'Введите пароль',
  submit: 'Войти',
  failed: 'Не удалось войти, попробуйте ещё раз',
} as const

/** Действия шапки: переключатель темы и меню профиля (DESIGN.md §3.5). */
export const HEADER_LABELS = {
  lightTheme: 'Светлая тема',
  darkTheme: 'Тёмная тема',
  logout: 'Выйти',
  profileMenu: 'Меню профиля',
} as const

/** Вкладки экрана «Отчёты и экспорт» (T-67): конструктор выгрузок и рассылка сводки. */
export const EXPORT_TAB_LABELS = {
  builder: 'Выгрузки',
  digests: 'Сводки',
} as const


/** День недели рассылки: 1 — понедельник, как хранит digest_settings (ADR-014). */
export const DIGEST_WEEKDAY_LABELS: Record<number, string> = {
  1: 'Понедельник',
  2: 'Вторник',
  3: 'Среда',
  4: 'Четверг',
  5: 'Пятница',
  6: 'Суббота',
  7: 'Воскресенье',
}

/** Охват выпуска сводки (T-67, §6.2 дизайна). */
export const DIGEST_SCOPE_LABELS: Record<DigestScope, string> = {
  oblast: 'Вся область',
  region: 'Район или город',
}

/** Канал доставки сводки и что из него вышло: те же коды, что notification_log (ТЗ п. 18). */
export const DIGEST_CHANNEL_LABELS: Record<NotificationChannel, string> = {
  panel: 'Панель',
  telegram: 'Telegram',
  email: 'Почта',
}

export const DIGEST_RESULT_LABELS: Record<NotificationResult, string> = {
  sent: 'отправлено',
  failed: 'не отправлено',
  skipped: 'канал не настроен',
}

/**
 * Рассылка сводки для руководителя (T-67, §6.2 дизайна, DESIGN.md §3.32): список, drawer,
 * «Отправить сейчас» с подтверждением и «Предпросмотр», который скачивает тот же PDF.
 */
export const DIGEST_LABELS = {
  title: 'Сводка для руководителя',
  subtitle: 'Одна страница раз в неделю: почта и Telegram',
  lead:
    'Выпуск собирается по данным панели за неделю и уходит по расписанию письмом с PDF и ' +
    'сообщением в Telegram. Каждая отправка попадает в журнал уведомлений.',
  add: 'Новая рассылка',
  addAction: 'Добавить рассылку',
  edit: 'Изменить рассылку',
  emptyTitle: 'Рассылок пока нет',
  emptyDescription: 'Добавьте рассылку: охват, день недели, час и получателей.',
  scope: 'Охват',
  region: 'Район или город',
  regionPlaceholder: 'Выберите из списка',
  regionRequired: 'Выберите район или город',
  when: 'Когда',
  weekday: 'День недели',
  hour: 'Час',
  hourHint: 'Местное время Алматы; расписание хранится в настройке рассылки.',
  recipients: 'Получатели',
  recipientsPlaceholder: 'Введите адрес и нажмите Enter',
  recipientsHint: 'Адреса электронной почты руководителей.',
  recipientsInvalid: 'Введите адрес вида name@example.kz',
  channels: 'Каналы',
  telegram: 'Чат Telegram',
  telegramPlaceholder: 'Идентификатор чата',
  active: 'Рассылка действует',
  activeHint: 'Отключённая рассылка не уходит по расписанию, «Отправить сейчас» работает.',
  lastSent: 'Последняя отправка',
  neverSent: 'Ещё не уходила',
  sendNow: 'Отправить сейчас',
  sendConfirmTitle: 'Отправить сводку сейчас?',
  sendConfirmText: 'Письмо с PDF и сообщение в Telegram уйдут получателям рассылки вне расписания.',
  sendConfirmOk: 'Отправить',
  sendConfirmCancel: 'Отмена',
  sent: 'Сводка отправлена',
  preview: 'Предпросмотр',
  previewFailed: 'Предпросмотр не сформирован',
  remove: 'Удалить',
  removeConfirmTitle: 'Удалить рассылку?',
  removeConfirmText: 'Выпуски, которые уже ушли, останутся в журнале уведомлений.',
  removed: 'Рассылка удалена',
  created: 'Рассылка добавлена',
  changed: 'Рассылка изменена',
} as const

/** Column of the provider score table (T-68, DESIGN.md §3.29, docs/design/README.md §6.3). */
export const PROVIDER_COLUMN_LABELS = {
  name: 'Поставщик',
  schools: 'Школ',
  belowContract: 'Ниже договора',
  incidents: 'Инцидентов',
  reaction: 'Реакция',
  restore: 'Устранение',
  school: 'Школа',
  region: 'Район',
  status: 'Статус',
  belowNorm: 'Договор ниже нормы',
  score: 'Оценка',
} as const

/** Verdict on the score: at the passing threshold of the settings or below it. */
export const PROVIDER_VERDICT_LABELS = {
  pass: 'Норма',
  below_norm: 'Ниже порога',
} as const

/** Strip of the provider card, in the order of `Providers.html`. */
export const PROVIDER_KPI_LABELS = {
  belowContract: 'Время ниже договора',
  incidents: 'Инцидентов',
  reaction: 'Средняя реакция',
  restore: 'Среднее устранение',
  availability: 'Доступность',
} as const

/** Section «Поставщики» (T-68): claim work — score, escalation, act, contract below the norm. */
export const PROVIDER_LABELS = {
  context: 'Претензионная работа',
  subtitle: 'Основные линии · оценка за период',
  scoreTable: 'Оценка поставщиков за период',
  scoreOf: (score: string, threshold: string) => `оценка ${score} · порог ${threshold}`,
  reactionNorm: (norm: string) => `норма ${norm}`,
  availabilityNorm: (norm: string) => `норма ${norm}`,
  incidentsClosed: (closed: string) => `восстановлено ${closed}`,
  worst: (value: string) => `худшее ${value}`,
  belowNormFilter: 'Договор ниже норматива',
  belowNorm: 'Договор ниже норматива',
  notAClaim: 'не претензия',
  belowNormHint: 'Договорная скорость ниже порога профиля: нужен новый договор, а не обращение.',
  belowNormEmpty: 'Все договоры поставщика не ниже порогов профиля.',
  contractOf: (down: string, up: string) => `договор ${down} / ${up}`,
  schools: 'Школы поставщика',
  schoolsBelowContract: 'Ниже договора',
  sustained: 'устойчиво ниже договора',
  escalation: 'Эскалация',
  escalationHint:
    'Оценка ниже порога — основание для претензионной работы: акт о несоответствии и обращение поставщику.',
  act: 'Скачать акт',
  actTitle: 'Акт о несоответствии',
  actHint: 'Замеры ниже договора с порогами и договорными значениями каждого замера.',
  actFailed: 'Акт не сформирован',
  selectHint: 'Выберите поставщика в таблице, чтобы открыть карточку.',
  empty: 'Поставщиков пока нет',
  emptyHint: 'Оценка появится, когда по линиям поставщиков пройдут замеры за период.',
  filteredEmpty: 'Нет поставщиков с договором ниже норматива',
  reset: 'Сбросить фильтр',
  open: 'Открыть карточку',
  noScore: 'нет замеров за период',
  plannedWorks: 'Окна плановых работ из оценки пока не исключаются: календарь появится позже.',
} as const

/** Lists of «Внедрение» (T-69, docs/design/README.md §6.4); the key is the `filter` of the endpoint. */
export const ROLLOUT_FILTER_LABELS = {
  not_connected: 'Не подключены',
  silent: 'Молчат',
  code_unused: 'Код не использован',
  old_version: 'Старая версия агента',
} as const

/** Columns of the two tables of the rollout: the districts and the schools of a list (DESIGN.md §3.30). */
export const ROLLOUT_COLUMN_LABELS = {
  region: 'Район или город',
  schools: 'Школ',
  connected: 'Подключено',
  alive: 'На связи',
  share: 'Доля подключённых',
  school: 'Школа',
  reason: 'Что не так',
  devices: 'Компьютеров',
  version: 'Версия агента',
} as const

/** Cells of the «Ход внедрения» strip of Rollout.html: the three colours and the agent versions. */
export const ROLLOUT_KPI_LABELS = {
  connected: 'Подключены',
  alive: 'На связи',
  silent: 'Установлен, но молчит',
  notConnected: 'Не подключены',
  oldVersion: 'На старых версиях',
} as const

/** Captions of the rollout screen (T-69, DESIGN.md §3.30). */
export const ROLLOUT_LABELS = {
  progress: 'Ход внедрения',
  regions: 'По районам и городам',
  lists: 'Кто ждёт действий',
  registry: (total: string) => `из ${total} в реестре`,
  context: (scope: string) => `Внедрение · ${scope}`,
  verdict: (connected: string, total: string, noun: string) =>
    `${connected} из ${total} ${noun} подключены`,
  subtitle: (alive: string, time: string) => `На связи ${alive} · данные на ${time}`,
  release: (version: string) => `Текущий релиз агента ${version}`,
  noRelease: 'Релиз агента не опубликован',
  silentWindow: (days: string, noun: string) => `Молчат дольше ${days} ${noun}`,
  dayForms: ['день', 'дня', 'дней'] as [string, string, string],
  deviceForms: ['компьютер', 'компьютера', 'компьютеров'] as [string, string, string],
  silentSince: (days: string, noun: string) => `последний сигнал ${days} ${noun} назад`,
  neverSeen: 'ни разу не выходил на связь',
  codeAge: (days: string, noun: string) => `код не использован ${days} ${noun}`,
  noDevices: 'нет ни одного компьютера',
  noContact: 'нет ответственного',
  emptyTitle: 'В этом списке никого нет',
  emptyDescription: 'Школы появятся здесь, как только подойдут под критерий списка.',
  assign: 'Назначить обновление',
  assignConfirmTitle: (version: string) => `Назначить обновление ${version}?`,
  assignConfirmText:
    'Выбранные компьютеры перейдут в канал этой версии и поставят её при следующем обновлении ' +
    'конфигурации агента. История и замеры не меняются.',
  assignConfirmOk: 'Назначить',
  assignConfirmCancel: 'Отмена',
  assigned: (count: string, noun: string) => `Обновление назначено: ${count} ${noun}`,
  assignFailed: 'Обновление не назначено',
  assignNoRelease: 'Нет действующего релиза агента: опубликуйте его в администрировании',
} as const
