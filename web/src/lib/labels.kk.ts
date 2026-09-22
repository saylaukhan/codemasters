// The Kazakh dictionary of the panel (T-66, DESIGN.md §5.1): the same exports and the same keys
// as labels.ru.ts, so labels.ts can put one module in place of the other for a whole page load.
// GENERATED FROM labels.ru.ts, values included: every string below is still the Russian one and
// is replaced by the translation of T-66; labels.test.ts fails the moment the keys of the two
// files, the length of an array or the type of a value stop matching.
import type {
  AnalyticsLevel,
  AnalyticsPeriod,
  AppealDeliveryStatus,
  AttentionReason,
  AuditAction,
  AuditEntityType,
  CalendarKind,
  CalendarScope,
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
  normal: 'Қалыпты',
  unstable: 'Тұрақсыз',
  critical: 'Сыни',
  offline: 'Байланыс жоқ',
  no_data: 'Деректер жоқ',
}

/**
 * «Нет данных» is display-only and never stands without a reason (DESIGN.md §4.1): the agent is
 * silent, so there is nothing to judge the connection by.
 */
export const NO_DATA_HINT = 'Компьютер өшірулі немесе жұмыс уақыты емес'

/** The same for a blocked computer: the server declines its measurements, the history stays (ADR-005). */
export const NO_DATA_BLOCKED_HINT = 'Компьютер бұғатталған, тарих сақталды'

/** Quality of a measurement or a line, evaluated on the server (ADR-004). */
export const QUALITY_STATUS_LABELS: Record<QualityStatus, string> = {
  normal: SCHOOL_STATUS_LABELS.normal,
  unstable: SCHOOL_STATUS_LABELS.unstable,
  critical: SCHOOL_STATUS_LABELS.critical,
  offline: SCHOOL_STATUS_LABELS.offline,
}

/** Status of an incident (ТЗ п. 19, ADR-007). */
export const INCIDENT_STATUS_LABELS: Record<IncidentStatus, string> = {
  new: 'Жаңа',
  sent_to_provider: 'Жеткізушіге берілді',
  in_progress: 'Жұмыста',
  awaiting_info: 'Ақпарат күтілуде',
  resolved: 'Жойылды',
  closed: 'Жабылды',
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
  available: 'Қолжетімді',
  none: 'Бұл мәртебеден өтуге болатын мәртебе жоқ',
} as const

/** Switch of the incidents section (DESIGN.md §3.18): the table of T-41 or the kanban of T-43. */
export const INCIDENT_VIEW_LABELS = {
  list: 'Тізім',
  board: 'Тақта',
} as const

export type IncidentViewKey = keyof typeof INCIDENT_VIEW_LABELS

/** Entry of the incident history (`incident_events`, ADR-007); a status change is written «Статус: A → B». */
export const INCIDENT_EVENT_LABELS: Record<IncidentEventKind, string> = {
  created: 'Инцидент құрылды',
  status_change: 'Мәртебе',
  comment: 'Пікір',
  restored: 'Көрсеткіштер қалпына келді',
}

/** Author of an entry without a person: the detection of T-40 or the automatic closing after 24 h. */
export const SYSTEM_AUTHOR_LABEL = 'Жүйе'

/** Appeals go through the same six statuses as incidents (ADR-011). */
export const APPEAL_STATUS_LABELS: Record<IncidentStatus, string> = INCIDENT_STATUS_LABELS

/**
 * Captions of an appeal to the provider (ТЗ п. 17, DESIGN.md §3.19): the draft opens from the card of an incident
 * or of a school (T-47), the number is assigned by the sending (T-48) and the letter stays in the list with it.
 */
export const APPEAL_LABELS = {
  create: 'Өтініш құру',
  draft: 'Өтініш жобасы',
  send: 'Өтінішті жіберу',
  sent: 'Өтініш жіберілді',
  sendFailed: 'Өтініш жіберілмеді',
  regenerate: 'Қайта жасау',
  regenerateHint: 'Модель хатты қайтадан жазады: редактордағы мәтін ауыстырылады',
  aiNote: 'Жоба автоматты түрде құрылды. Жіберу алдында тексеріңіз.',
  letter: 'Хат',
  facts: 'Мәліметтер',
  history: 'Тарих',
  statusChange: 'Мәртебенің өзгеруі',
  userComment: 'Жіберушінің пікірі',
  noUserComment: 'Пікір қалдырылмаған',
  pdf: 'PDF жүктеп алу',
  pdfFailed: 'PDF жүктелмеді',
  search: 'Өтініш нөмірі бойынша іздеу',
  empty: 'Өтініштер жоқ',
  emptyHint: 'Өтініш жеткізушіге хат жіберілгеннен кейін осында шығады.',
  filteredEmpty: 'Берілген сүзгілер бойынша ештеңе табылмады',
  filteredEmptyHint: 'Сүзгілерді өзгертіңіз немесе тазалаңыз.',
  notFound: 'Өтініш табылмады',
  notFoundHint: 'Ол жоқ немесе сіздің көру аймағыңыздан тыс.',
  /** Under «Отправить» of a draft about an incident: the sending hands the incident over itself (T-63, ADR-007). */
  incidentHandover: 'Жіберілгеннен кейін «Жаңа» мәртебесіндегі инцидент «Жеткізушіге берілді» мәртебесіне өтеді',
  noTarget: 'Өтініш жазуға негіз жоқ',
  noTargetHint: 'Инцидент немесе мектеп картасындағы «Өтініш құру» түймесімен жобаны ашыңыз.',
} as const

/** Columns of the incident list (T-41), header of `IncidentTable`. */
export const INCIDENT_COLUMN_LABELS = {
  number: 'Нөмір',
  school: 'Мектеп',
  status: 'Мәртебе',
  line: 'Желі және жеткізуші',
  basis: 'Негіздер',
  startedAt: 'Басталуы',
  duration: 'Ұзақтығы',
  responsible: 'Жауапты',
} as const

/** Footer of a paged table: «1–25 из 143». */
export const TABLE_PAGINATION_LABELS = {
  total: (from: number, to: number, count: number) => `${from}–${to} / ${count}`,
} as const

/** Columns of the appeal list (T-48). */
export const APPEAL_COLUMN_LABELS = {
  number: 'Нөмір',
  status: 'Мәртебе',
  school: 'Мектеп',
  provider: 'Жеткізуші',
  subject: 'Тақырып',
  sentAt: 'Жіберілді',
  delivery: 'Хаттың жеткізілуі',
} as const

/** Captions of the appeal card, left of the values (DESIGN.md §3.17). */
export const APPEAL_FIELD_LABELS = {
  school: 'Мектеп',
  schoolCode: 'School ID',
  provider: 'Жеткізуші',
  line: 'Желі',
  incident: 'Инцидент',
  period: 'Кезең',
  sentAt: 'Жіберілді',
  recipient: 'Алушы',
  delivery: 'Хаттың жеткізілуі',
  contract: 'Шарт',
  contractDown: 'Шарт бойынша Download',
  contractUp: 'Шарт бойынша Upload',
  measurements: 'Өлшем саны',
  problems: 'Проблемалы өлшемдер',
  outages: 'Іркілістер',
  outagesDuration: 'Іркілістердің ұзақтығы',
  /** Next to the average of a metric: the threshold it was judged by (ТЗ п. 11, ADR-004). */
  threshold: 'шек',
} as const

/** Captions of the fields a person fills in: the editor of the draft (T-47) and the status form of the card (T-48). */
export const APPEAL_FORM_LABELS = {
  subject: 'Тақырып',
  text: 'Хат мәтіні',
  comment: 'Пікір',
  requiredComment: 'Пікір, міндетті',
  status: 'Жаңа мәртебе',
} as const

/**
 * Did the letter go (T-48): without SMTP or without an address of the provider the appeal is kept anyway, with
 * its number and its PDF, and says so (ADR-011, «Решения по умолчанию»).
 */
export const APPEAL_DELIVERY_LABELS: Record<AppealDeliveryStatus, string> = {
  sent: 'Жіберілді',
  not_sent: 'Жіберілмеді',
}

/** Next to «Не отправлено»: the appeal itself is kept, only the mail did not go. */
export const APPEAL_NOT_SENT_HINT = 'Хат жеткізілмеді, өтініш пен PDF сақталды'

/** The provider has no `appeals_email`: the appeal is kept with its PDF, the letter goes nowhere (ADR-011). */
export const APPEAL_NO_RECIPIENT_HINT = 'Мекенжай көрсетілмеген, хат жіберілмейді'

/** What the notification is about (T-42, ТЗ п. 18): every one of them follows an incident. */
export const NOTIFICATION_KIND_LABELS: Record<NotificationKind, string> = {
  incident_opened: 'Жаңа инцидент',
  incident_status_changed: 'Инцидент мәртебесінің өзгеруі',
  incident_restored: INCIDENT_EVENT_LABELS.restored,
}

/** Tabs of the notification panel (DESIGN.md §3.23). */
export const NOTIFICATION_TAB_LABELS = {
  all: 'Барлығы',
  unread: 'Оқылмағандар',
} as const

export type NotificationTabKey = keyof typeof NOTIFICATION_TAB_LABELS

/** Bell of the header (DESIGN.md §3.5) and the captions of its panel (§3.23). */
export const NOTIFICATIONS_TITLE = 'Хабарламалар'
export const NOTIFICATIONS_READ_ALL_LABEL = 'Барлығын оқылған деп белгілеу'
export const NOTIFICATIONS_EMPTY_LABEL = 'Әзірге хабарлама жоқ'
export const NOTIFICATIONS_UNREAD_EMPTY_LABEL = 'Оқылмаған хабарлама жоқ'

/** More unread than the counter of the bell can show: «99+». */
export const NOTIFICATIONS_OVERFLOW_LABEL = '99+'

/** Role of a line at a school (ТЗ п. 10, ADR-003). */
export const LINE_STATUS_LABELS: Record<LineStatus, string> = {
  main: 'Негізгі',
  reserve: 'Қосалқы',
  disabled: 'Өшірілген',
}

/** Blocking of a device keeps its history (ADR-005). */
export const DEVICE_STATUS_LABELS: Record<DeviceStatus, string> = {
  active: 'Белсенді',
  blocked: 'Бұғатталған',
}

/** A user is blocked, never deleted: his actions stay in the audit log (ТЗ п. 16, T-38). */
export const USER_STATUS_LABELS = {
  active: 'Белсенді',
  blocked: 'Бұғатталған',
} as const

export type UserStatus = keyof typeof USER_STATUS_LABELS

/** Scope of Область and Администратор: no district, provider or school of their own (ADR-008). */
export const WHOLE_OBLAST_SCOPE_LABEL = 'Бүкіл облыс'

/** Filter of the devices and of the users in the administration by status (T-36, T-38). */
export const DEVICE_STATUS_FILTER_LABELS = {
  all: 'Барлығы',
  active: 'Белсенділер',
  blocked: 'Бұғатталғандар',
} as const

/** A new token of a device is requested and its agent has not taken it yet (T-36, ADR-005). */
export const TOKEN_ROTATION_PENDING_LABEL = 'Токен ауысуын күтіп тұр'

/** A measurement is asked for in the panel and its agent has not taken it yet (T-79). */
export const MEASURE_PENDING_LABEL = 'Өлшеуді күтіп тұр'

/** Network interface of a measurement; Wi-Fi does not rate the line (ADR-012). */
export const IFACE_LABELS: Record<IfaceType, string> = {
  ethernet: 'Ethernet',
  wifi: 'Wi‑Fi',
  other: 'Басқа',
}

/** Monitoring point of a school: one of them is the point the school is judged by (ТЗ п. 10). */
export const MONITORING_POINT_LABELS = {
  primary: 'Мектептің басты нүктесі',
} as const

/** Note next to the interface of a measurement: Wi-Fi is not read as the quality of the line. */
export const IFACE_NOTE_LABELS = {
  wifi: 'Желіні бағаламайды',
} as const

/** Period presets of charts and analytics (ТЗ п. 5); «Свой период» is a separate control. */
export const PERIOD_LABELS: Record<Exclude<AnalyticsPeriod, 'custom'>, string> = {
  today: 'Бүгін',
  week: '7 күн',
  month: '30 күн',
}

/** Period with explicit bounds, next to the presets. */
export const CUSTOM_PERIOD_LABEL = 'Өз кезеңі'

/** Grouping of the analytics rows (ТЗ п. 13): per school, district or city, provider, the oblast. */
export const ANALYTICS_LEVEL_LABELS: Record<AnalyticsLevel, string> = {
  school: 'Мектептер',
  district: 'Аудандар',
  provider: 'Провайдерлер',
  region: 'Бүкіл облыс',
}

/** One entity of a level: title of the first column of a table of the analytics. */
export const ANALYTICS_ENTITY_LABELS: Record<AnalyticsLevel, string> = {
  school: 'Мектеп',
  district: 'Аудан/қала',
  provider: 'Провайдер',
  region: 'Облыс',
}

/** Tabs of «Аналитика» (DESIGN.md §3.8): the metrics of T-27 and the incidents of T-45. */
export const ANALYTICS_TAB_LABELS = {
  quality: 'Көрсеткіштер',
  incidents: 'Инциденттер',
} as const

export type AnalyticsTabKey = keyof typeof ANALYTICS_TAB_LABELS

/** Days of the week in Asia/Almaty (ADR-014): rows of the heatmap «час × день недели». */
export const WEEKDAY_LABELS: Record<Weekday, string> = {
  mon: 'Дс',
  tue: 'Сс',
  wed: 'Ср',
  thu: 'Бс',
  fri: 'Жм',
  sat: 'Сн',
  sun: 'Жс',
}

/** Monday first, as the week is read in Kazakhstan. */
export const WEEKDAY_ORDER: readonly Weekday[] = ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun']

/** Five roles of ТЗ п. 16 (ADR-008). */
export const ROLE_LABELS: Record<UserRole, string> = {
  school: 'Мектеп',
  district: 'Аудан/қала',
  oblast: 'Облыс',
  provider: 'Провайдер',
  admin: 'Әкімші',
}

/** What an export contains (DESIGN.md §3.24): measurements, one row per school, PDF of a school. */
export const EXPORT_MODE_LABELS: Record<ExportMode, string> = {
  raw: 'Өңделмеген деректер',
  aggregates: 'Мектеп бойынша жиынтық',
  school_report: 'PDF-есеп',
}

/** State of an export's file (T-33): PDF and big exports are built in the background. */
export const EXPORT_STATUS_LABELS: Record<ExportStatus, string> = {
  pending: 'Дайындалуда',
  ready: 'Дайын',
  failed: 'Қате',
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
  school_name: 'Мектеп',
  hostname: 'Компьютер',
  room: 'Кабинет',
  date: 'Күні',
  time: 'Уақыты',
  download_mbps: 'Download, Мбит/с',
  upload_mbps: 'Upload, Мбит/с',
  ping_ms: 'Ping, мс',
  jitter_ms: 'Jitter, мс',
  packet_loss_pct: 'Packet Loss, %',
  quality_status: 'Күйі',
  school_code: 'School ID',
  device_id: 'Компьютер ID',
  line_status: 'Желі',
  connection_status: 'Байланыс',
  iface_type: 'Интерфейс',
  duration_s: 'Өлшеу ұзақтығы, с',
  external_ip: 'Сыртқы IP',
  server: 'Өлшеу сервері',
  agent_version: 'Агент нұсқасы',
}

/**
 * Columns of the aggregates in the order of the file: one row per school (ТЗ п. 9, T-31).
 * The headers of XLSX and CSV repeat them: backend/app/services/exports/columns.py.
 */
export const EXPORT_AGGREGATE_COLUMN_LABELS: Record<ExportAggregateColumn, string> = {
  school_code: 'School ID',
  school_name: 'Мектеп',
  measurements_count: 'Өлшеу саны',
  avg_download_mbps: 'Орташа Download, Мбит/с',
  min_download_mbps: 'Ең төмен Download, Мбит/с',
  avg_upload_mbps: 'Орташа Upload, Мбит/с',
  avg_ping_ms: 'Орташа Ping, мс',
  problem_count: 'Проблемалы өлшеулер',
  problem_pct: 'Проблемалы өлшеу үлесі, %',
}

/** Summary of the export constructor (DESIGN.md §3.24, T-64): «Будет выгружено ≈ 12 480 строк». */
export const EXPORT_ESTIMATE_LABELS = {
  title: 'Жүктеледі',
  /** Sign of an estimate: m_daily counts a touched day whole and holds no Wi-Fi. */
  approximate: '≈',
  rows: 'жол',
  loading: 'есептеп жатырмыз…',
  error: 'бағалау мүмкін болмады',
} as const

/** Sections of the side navigation (DESIGN.md §3.6). */
export const SECTION_LABELS = {
  overview: 'Шолу',
  map: 'Карта',
  schools: 'Мектептер',
  devices: 'Құрылғылар',
  analytics: 'Аналитика',
  incidents: 'Инциденттер',
  appeals: 'Өтініштер',
  providers: 'Жеткізушілер',
  rollout: 'Енгізу',
  exports: 'Есептер және экспорт',
  admin: 'Әкімшілендіру',
} as const

export type SectionKey = keyof typeof SECTION_LABELS

/** Caption of a screen in the provider cabinet (T-44, ТЗ п. 16): his lists hold only his own lines. */
export const PROVIDER_SCOPE_HINTS = {
  schools: 'Тек сіздің желілеріңіз бар мектептер көрсетілген',
  incidents: 'Тек сіздің желілеріңіздің инциденттері көрсетілген',
  appeals: 'Тек сіздің желілеріңіз бойынша өтініштер көрсетілген',
} as const

/** Tabs of «Администрирование» (T-34): the key is the path under /admin. */
export const ADMIN_TAB_LABELS = {
  schools: 'Мектептер',
  devices: 'Құрылғылар',
  users: 'Пайдаланушылар',
  regions: 'Аудандар мен қалалар',
  providers: 'Жеткізушілер',
  'connection-types': 'Қосылу түрлері',
  thresholds: 'Шектік мәндер',
  schedules: 'Кестелер',
  'incident-rules': 'Инцидент ережелері',
  settings: 'Параметрлер',
  audit: 'Аудит',
  events: 'Оқиғалар',
  calendar: 'Күнтізбе',
} as const

export type AdminTabKey = keyof typeof ADMIN_TAB_LABELS

/** Target of a threshold profile (ADR-004): the most specific active one judges a measurement. */
export const PROFILE_SCOPE_LABELS: Record<ThresholdProfileScope, string> = {
  global: 'Бүкіл облыс',
  district: 'Аудан немесе қала',
  line: 'Желі',
}

/** Target of a measurement schedule (T-17): the most specific active one reaches the agent. */
export const SCHEDULE_SCOPE_LABELS: Record<ScheduleScope, string> = {
  global: 'Бүкіл облыс',
  district: 'Аудан немесе қала',
  school: 'Мектеп',
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
  active: 'Қолданыста',
  disabled: 'Өшірілген',
} as const

/** A school is deactivated, never deleted: its measurements and incidents stay (ТЗ п. 20). */
export const SCHOOL_ACTIVITY_LABELS = {
  active: 'Белсенді',
  disabled: 'Өшірілген',
} as const

export type SchoolActivity = keyof typeof SCHOOL_ACTIVITY_LABELS

/** Filter of the schools in the administration by activity. */
export const SCHOOL_ACTIVITY_FILTER_LABELS = {
  all: 'Барлығы',
  active: 'Белсенділер',
  disabled: 'Өшірілгендер',
} as const

/** Boundary of a district or city: loaded from GeoJSON by the seed, drawn on the map. */
export const REGION_BOUNDARY_LABELS = {
  loaded: 'Жүктелген',
  missing: 'Жоқ',
} as const

/** What happened, in the audit log (T-39, ТЗ п. 12, п. 16). */
export const AUDIT_ACTION_LABELS: Record<AuditAction, string> = {
  login_success: 'Кіру',
  login_failure: 'Сәтсіз кіру',
  create: 'Құру',
  update: 'Өзгерту',
  block: 'Бұғаттау',
  unblock: 'Бұғаттан шығару',
  password_reset: 'Құпия сөзді қалпына келтіру',
  status_change: 'Күйін өзгерту',
  export: 'Экспорт',
  transfer_error: 'Деректерді жіберу қатесі',
}

/** Kind of record an action of the audit log touched. */
export const AUDIT_ENTITY_LABELS: Record<AuditEntityType, string> = {
  user: 'Пайдаланушы',
  school: 'Мектеп',
  line: 'Желі',
  monitoring_point: 'Мониторинг нүктесі',
  school_contact: 'Жауапты адам',
  device: 'Құрылғы',
  enrollment_code: 'Орнату коды',
  region: 'Аудан немесе қала',
  provider: 'Жеткізуші',
  connection_type: 'Қосылу түрі',
  threshold_profile: 'Шектік мәндер профилі',
  schedule: 'Кесте',
  setting: 'Параметрлер',
  incident_rule: 'Инцидент ережесі',
  agent_release: 'Агент релизі',
  incident: 'Инцидент',
  appeal: 'Өтініш',
  export: 'Экспорт файлы',
}

/** Why a sign-in or an agent request was refused: `type` of the problem (ADR-009); another code is shown as is. */
export const AUDIT_ERROR_LABELS: Record<string, string> = {
  invalid_credentials: 'E-mail немесе құпия сөз дұрыс емес',
  account_blocked: 'Тіркелгі бұғатталған',
  unauthorized: 'Құрылғы токені жоқ немесе жарамсыз',
  device_blocked: 'Құрылғы бұғатталған',
  validation_error: 'Деректер жарамсыз',
  bad_request: 'Сұрау дұрыс емес',
  payload_too_large: 'Сұрау тым үлкен',
  unsupported_media_type: 'Қолдау көрсетілмейтін сұрау форматы',
}

/** Changed fields in the audit log, by their camelCase key; another field is shown by its key. */
export const AUDIT_FIELD_LABELS: Record<string, string> = {
  name: 'Атауы',
  fullName: 'Аты-жөні',
  email: 'E-mail',
  phone: 'Телефон',
  position: 'Лауазымы',
  role: 'Рөлі',
  isActive: 'Белсенді',
  status: 'Күйі',
  address: 'Мекенжайы',
  schoolCode: 'Мектеп коды',
  schoolId: 'Мектеп',
  regionId: 'Аудан немесе қала',
  providerId: 'Жеткізуші',
  connectionTypeId: 'Қосылу түрі',
  lineId: 'Желі',
  room: 'Кабинет',
  contractNumber: 'Шарт нөмірі',
  resetLink: 'Құпия сөзді өзгерту сілтемесі',
  contractDownMbps: 'Шарт бойынша Download',
  contractUpMbps: 'Шарт бойынша Upload',
  thresholds: 'Шектік мәндер',
  slots: 'Слоттар',
  workingHours: 'Жұмыс уақыты',
  speedtest: 'Өлшеу сервері',
}

/** Empty value of a changed field in the audit log. */
export const AUDIT_EMPTY_VALUE_LABEL = 'бос'

/** Yes-or-no value of a changed field in the audit log. */
export const AUDIT_BOOLEAN_LABELS = { true: 'да', false: 'нет' } as const

/** Forms of «школа» for a counted number: the status strip prints «312 школ», «21 школа» (§3.10). */
export const SCHOOL_COUNT_FORMS = ['мектеп', 'мектеп', 'мектеп'] as const

/** Change of a status column over the last day (DESIGN.md §3.10): «▲ 3 за сутки», «без изменений». */
export const DAY_DELTA_LABELS = {
  up: '▲',
  down: '▼',
  period: 'тәулік ішінде',
  none: 'өзгеріссіз',
} as const

/** Filter bar, DESIGN.md §3.9: the chip clears its own value, the link clears the whole bar. */
export const FILTER_BAR_LABELS = {
  reset: 'Ысыру',
  clear: 'Сүзгіні тазалау',
} as const

/** Dimensions of the filter bar of the map, the overview and the analytics (DESIGN.md §3.9). */
export const MAP_FILTER_LABELS = {
  level: 'Деңгей',
  region: 'Аудан',
  provider: 'Провайдер',
  connectionType: 'Қосылым түрі',
  status: 'Мәртебе',
  period: 'Кезең',
} as const

/** Bottom sheet the filters fold into on a phone (DESIGN.md §9.3, row «Панель фильтров»). */
export const FILTER_SHEET_LABELS = {
  open: 'Сүзгілер',
  title: 'Сүзгілер',
} as const

/** Legend of the map (DESIGN.md §3.13); on a narrow screen it folds into one button (§9.3). */
export const MAP_LEGEND_LABELS = {
  title: 'Шартты белгілер',
  show: 'Шартты белгілерді көрсету',
  hide: 'Шартты белгілерді жасыру',
} as const

/** Bar «fact against the threshold» under a metric tile (DESIGN.md §3.10, §3.27). */
export const FACT_BAR_LABELS = {
  normFrom: 'қалыпты мәні кемінде',
  normTo: 'қалыпты мәні ең көп',
  contract: 'шарт бойынша',
  lowerIsBetter: 'аз болғаны жақсы',
} as const

/** Controls of `ResponsiveTable` (DESIGN.md §3.12): the phone sorts with a select above the list. */
export const RESPONSIVE_TABLE_LABELS = {
  sort: 'Сұрыптау',
  defaultOrder: 'Әдепкі бойынша',
} as const

/** Rating of «Аналитика»: a phone card carries the place in place of the status pill (§3.12). */
export const RATING_LABELS = {
  place: 'Орны',
  placeOf: (rank: string) => `${rank}-орын`,
  wholeRegion: 'Бүкіл ШҚО',
} as const

/** Controls of the side navigation and of its drawer (DESIGN.md §3.5, §3.6, §9.3). */
export const NAVIGATION_LABELS = {
  open: 'Мәзірді ашу',
  title: 'Бөлімдер',
  expand: 'Мәзірді жаю',
  fold: 'Мәзірді жию',
} as const

/** Blocks of the main screen of the oblast and of a district (DESIGN.md §3.28, `Main.html`). */
export const OVERVIEW_LABELS = {
  statusStrip: 'Мектептер мәртебесі бойынша',
  map: 'Облыс картасы',
  mapOpen: 'Картаны ашу',
  attention: 'Назар қажет',
  kpi: 'Кезең көрсеткіштері',
  kpiCompare: 'алдыңғы кезеңмен салыстырғанда',
  incidents: 'Соңғы инциденттер',
  incidentsAll: 'Барлық инциденттер',
  incidentsEmpty: 'Ашық инцидент жоқ',
  incidentsEmptyHint: 'Инцидент желі көрсеткіштері ережені қатарынан немесе белгіленген уақыттан ұзақ бұзғанда ашылады.',
  /** No previous period to compare with, so the delta line says so instead (docs/design/README.md §4.1). */
  firstData: 'алғашқы деректер',
  /** Caption of the context above the title: «Вся область · 350 школ» (DESIGN.md §3.7). */
  context: (scope: string, count: string, noun: string) => `${scope} · ${count} ${noun}`,
  subtitle: (time: string) => `Деректер ${time} жағдайына · негізгі арналар`,
  /** «Нет данных» is display-only (ADR-004): a footnote under the strip, not a fifth column. */
  noData: (count: string, noun: string) => `${SCHOOL_STATUS_LABELS.no_data}: ${count} ${noun}`,
} as const

/** Verdict of the main screen (DESIGN.md §3.28): the title is a sentence about the whole selection. */
export const OVERVIEW_VERDICT_LABELS = {
  loading: 'Деректер жиналуда',
  empty: 'Берілген сүзгілер бойынша мектеп жоқ',
  all: (count: string, noun: string) => `Барлық ${count} ${noun} бүгін қалыпты`,
  part: (normal: string, noun: string, total: string) => `${total} ${noun} ішінен ${normal} бүгін қалыпты`,
} as const

/** The eight KPIs of ТЗ п. 4 on the main screen; the captions are those of `Main.html`. */
export const OVERVIEW_KPI_LABELS = {
  schools: 'Қосылған мектептер',
  devices: 'Агент орнатылған компьютерлер',
  activeDevices: 'Қазір байланыста',
  measurements: 'Кезеңдегі өлшемдер',
  avgDownload: 'Орташа жүктеп алу',
  avgUpload: 'Орташа жүктеп жіберу',
  avgPing: 'Орташа жауап уақыты',
  problemDevices: 'Проблемалы құрылғылар',
  registry: (total: string) => `тізілімдегі ${total} ішінен`,
  of: (total: string) => `${total} ішінен`,
} as const

/** Why a row of «Требуют внимания» is there; an incident says its metric instead (§4.1). */
export const ATTENTION_REASON_LABELS: Record<AttentionReason, string> = {
  offline: 'Байланыс жоқ',
  critical: SCHOOL_STATUS_LABELS.critical,
  incident_unassigned: 'Инцидент',
  appeal_unanswered: 'Жауапсыз өтініш',
}

/**
 * Metric of an incident row of «Требуют внимания», in the words of `Main.html`: the English terms
 * of `INCIDENT_METRIC_LABELS` belong to the incident card, not to this list (docs/design §4.1).
 */
export const ATTENTION_METRIC_LABELS: Record<IncidentMetric, string> = {
  download_mbps: 'Жүктеп алу',
  upload_mbps: 'Жүктеп жіберу',
  ping_ms: 'Жауап уақыты',
  jitter_ms: 'Діріл',
  packet_loss_pct: 'Жоғалулар',
  no_connection: ATTENTION_REASON_LABELS.offline,
}

/** Second line of a row of «Требуют внимания»: since when it has been so. */
export const ATTENTION_LABELS = {
  since: (moment: string) => `${moment} бастап`,
  unassignedSince: (moment: string) => `${moment} бастап жауапты тағайындалмаған`,
  more: (count: string, noun: string) => `Тағы ${count} ${noun}`,
  empty: 'Назар қажет ететін ештеңе жоқ',
  emptyHint: 'Байланысы жоқ мектептер, жауаптысы жоқ инциденттер және жауапсыз өтініштер осында шығады.',
} as const
/**
 * Words of the school cabinet (T-61, DESIGN.md §3.27, docs/design/README.md §4.2): the director
 * reads the same data in plainer words than the panel. Taken from `docs/design/mockups/School.html`
 * and `SchoolPhone.html` verbatim.
 */
export const CABINET_LABELS = {
  report: 'Айлық есеп',
  reportProblem: 'Ақаулық туралы хабарлау',
  checked: 'Тексерілді',
  checkedToday: 'Бүгін тексерілді',
  neverChecked: 'Әзірге өлшем болмаған',
  tiles: 'Ағымдағы көрсеткіштер',
  download: 'Жүктеп алу жылдамдығы',
  upload: 'Жүктеп жіберу жылдамдығы',
  ping: 'Жауап уақыты',
  jitter: 'Діріл',
  jitterLow: 'діріл',
  packetLoss: 'пакеттердің жоғалуы',
  packetLossShort: 'жоғалулар',
  availability: '7 күндегі қолжетімділік',
  availabilityCap: '7 күндегі қолжетімділік',
  allMeasurements: 'Барлық өлшемдер',
  days: 'Соңғы 30 күн',
  week: '7 күндегі жүктеп алу жылдамдығы',
  norm: 'қалыпты',
  contractMark: 'шарт',
  contract: 'Провайдер және шарт',
  support: 'Жеткізушінің қолдау қызметі',
  callSupport: 'Қолдау қызметіне қоңырау шалу',
  roundClock: 'тәулік бойы',
  from: 'бастап',
  agent: 'Агент орнатылған компьютер',
  agentSignal: 'Сигнал',
  agentVersion: 'агент',
  agentNote: 'Өшірулі = «Деректер жоқ», интернет ақаулығы емес',
  problems: 'Ақаулықтар мен өтініштер',
  problem: 'Байланыс ақаулығы',
  history: 'Бүкіл тарих',
  all: 'Барлығы',
  since: 'бастап',
  goesOn: 'жалғасуда',
  contacts: 'Кімге қоңырау шалу керек',
  today: 'бүгін',
} as const

/** English term next to the caption of a tile: «Скорость загрузки · Download» (DESIGN.md §3.27). */
export const CABINET_TERM_LABELS = {
  download: 'Download',
  upload: 'Upload',
  ping: 'Ping',
} as const

/** How the last measurement reached the network, in the words of the cabinet, not of the panel. */
export const CABINET_IFACE_LABELS: Record<IfaceType, string> = {
  ethernet: 'кабель арқылы',
  wifi: 'Wi‑Fi арқылы',
  other: 'басқа желі арқылы',
}

/**
 * Verdict of the cabinet, chosen by `components/schools/cabinet.ts` from the status of the school
 * and from what exactly is broken (docs/design/README.md §4.2). «Интернета нет с» takes the time
 * of the last measurement next to it; without that moment the shorter «Интернета нет» is printed.
 */
export const CABINET_VERDICT_LABELS = {
  normal: 'Интернет қалыпты',
  slowContract: 'Интернет шартта көрсетілгеннен баяу',
  slowNorm: 'Интернет тиісті деңгейден баяу',
  unstable: 'Интернет үзіліп жұмыс істейді',
  offline: 'Интернет жоқ',
  offlineSince: 'Интернет жоқ, басталған уақыты',
  noData: 'Агент орнатылған компьютер өшірулі',
} as const

export type CabinetVerdictKey = keyof typeof CABINET_VERDICT_LABELS

/** Summary over the day strip: «28 в норме · 1 перебои · 1 без связи» (DESIGN.md §3.27). */
export const CABINET_DAY_LABELS = {
  normal: 'қалыпты',
  problem: 'үзілістер',
  offline: 'байланыссыз',
  noData: 'деректер жоқ',
} as const

/** Captions of «Провайдер и договор», left of the values. */
export const CABINET_FIELD_LABELS = {
  provider: 'Жеткізуші',
  connection: 'Қосылым',
  contract: 'Шарт бойынша',
  contractNumber: 'Шарт',
} as const

/** Role of a line in the words of the cabinet: the panel writes the same three with a capital. */
export const CABINET_LINE_LABELS: Record<LineStatus, string> = {
  main: 'негізгі желі',
  reserve: 'қосалқы желі',
  disabled: 'желі өшірілген',
}

/** Cards of «Кому звонить»: the school's own responsible and the support of its provider (ТЗ п. 15). */
export const CABINET_CONTACT_LABELS = {
  school: 'Мектептегі жауапты',
  support: 'Қолдау қызметі',
  supportName: 'Техникалық қолдау',
  call: 'Қоңырау шалу',
} as const

/**
 * The same six statuses of ТЗ п. 19 in the words of the cabinet (docs/design/README.md §4.2):
 * «У поставщика» instead of «Передан поставщику». `IncidentStatusBadge` takes this dictionary
 * instead of the default one, so no Russian string enters a component (ADR-013).
 */
export const CABINET_APPEAL_STATUS_LABELS: Record<IncidentStatus, string> = {
  new: 'Тіркелді',
  sent_to_provider: 'Жеткізушіде',
  in_progress: 'Жұмыста',
  awaiting_info: 'Жауап күтіп отырмыз',
  resolved: 'Шешілді',
  closed: 'Жабылды',
}

/** Empty states and notices of the cabinet: what the director sees instead of a block that has no data. */
export const CABINET_NOTICE_LABELS = {
  notFound: 'Мектеп табылмады',
  notFoundHint: 'Ол жоқ немесе сіздің көру аймағыңыздан тыс.',
  noDays: 'Өлшем жүргізілген күндер әзірге жоқ',
  noWeek: 'Апта ішінде өлшем жоқ',
  noWeekHint: 'Агент орнатылған компьютер қосулы ма, тексеріңіз.',
  noLine: 'Желі тіркелмеген',
  noDevice: 'Агент орнатылған компьютер жоқ',
  noDeviceHint: 'Агент мектептің бірде-бір компьютеріне орнатылмаған.',
  noProblems: 'Ақаулық болмаған',
  noProblemsHint: 'Осында байланыс үзілістері мен жеткізушіге жазылған хаттар шығады.',
  noContacts: 'Байланыс деректері жоқ',
  noAppealLine: 'Мектепте жұмыс істеп тұрған желі жоқ',
  reportPending: 'Есеп әзірге дайындалып жатыр',
  reportPendingHint: 'Дайын болғанда «Есептер және экспорт» бөлімінен жүктеп алыңыз.',
  reportFailed: 'Есеп қалыптастырылмады',
} as const

/** What broke, in the words of the cabinet: the panel calls the same metrics by their English terms. */
export const CABINET_METRIC_LABELS: Record<IncidentMetric, string> = {
  download_mbps: 'Жүктеп алу жылдамдығы қалыптыдан төмен',
  upload_mbps: 'Жүктеп жіберу жылдамдығы қалыптыдан төмен',
  ping_ms: 'Жауап уақыты ұзақ',
  jitter_ms: 'Сигнал біркелкі емес',
  packet_loss_pct: 'Пакеттер жоғалуда',
  no_connection: 'Байланыс болмады',
}


/**
 * «Забыли пароль?» of the sign-in screen and the page of the link from the letter (T-65,
 * docs/design/README.md §4.6). The answer of the API says nothing about the address, so the
 * notice after a request is the same for every e-mail.
 */
export const PASSWORD_RESET_LABELS = {
  link: 'Құпиясөзді ұмыттыңыз ба?',
  requestTitle: 'Құпиясөзді өзгерту',
  requestHint: 'Тіркелгінің e-mail мекенжайына құпиясөзді өзгерту сілтемесін жібереміз.',
  email: 'E-mail',
  emailRequired: 'E-mail енгізіңіз',
  send: 'Сілтемені жіберу',
  cancel: 'Болдырмау',
  sent: 'Мұндай мекенжай бар болса, оған сілтеме жібердік',
  requestFailed: 'Сілтемені жіберу мүмкін болмады, қайталап көріңіз',
  supportTitle: 'Құпиясөзді әкімші өзгертеді',
  confirmTitle: 'Жаңа құпиясөз',
  confirmHint: 'Сілтеме бір рет жарамды. Құпиясөзді өзгерткеннен кейін жаңа құпиясөзбен кіріңіз.',
  password: 'Жаңа құпиясөз',
  repeat: 'Құпиясөзді қайталаңыз',
  repeatRequired: 'Құпиясөзді қайталаңыз',
  mismatch: 'Құпиясөздер сәйкес келмейді',
  save: 'Құпиясөзді сақтау',
  invalid: 'Сілтеме жарамсыз немесе ескірген — жаңасын сұратыңыз',
  done: 'Құпиясөз өзгертілді, жаңа құпиясөзбен кіріңіз',
  toLogin: 'Кіру бетіне қайту',
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
  title: 'Жүйеге кіру',
  email: 'E-mail',
  password: 'Құпиясөз',
  emailRequired: 'E-mail енгізіңіз',
  passwordRequired: 'Құпиясөз енгізіңіз',
  submit: 'Кіру',
  failed: 'Кіру мүмкін болмады, қайталап көріңіз',
} as const

/** Действия шапки: переключатель темы и меню профиля (DESIGN.md §3.5). */
export const HEADER_LABELS = {
  lightTheme: 'Ашық тақырып',
  darkTheme: 'Қараңғы тақырып',
  logout: 'Шығу',
  profileMenu: 'Профиль мәзірі',
} as const

/** Вкладки экрана «Отчёты и экспорт» (T-67): конструктор выгрузок и рассылка сводки. */
export const EXPORT_TAB_LABELS = {
  builder: 'Жүктеп алулар',
  digests: 'Жиынтықтар',
} as const


/** День недели рассылки: 1 — понедельник, как хранит digest_settings (ADR-014). */
export const DIGEST_WEEKDAY_LABELS: Record<number, string> = {
  1: 'Дүйсенбі',
  2: 'Сейсенбі',
  3: 'Сәрсенбі',
  4: 'Бейсенбі',
  5: 'Жұма',
  6: 'Сенбі',
  7: 'Жексенбі',
}

/** Охват выпуска сводки (T-67, §6.2 дизайна). */
export const DIGEST_SCOPE_LABELS: Record<DigestScope, string> = {
  oblast: 'Бүкіл облыс',
  region: 'Аудан немесе қала',
}

/** Канал доставки сводки и что из него вышло: те же коды, что notification_log (ТЗ п. 18). */
export const DIGEST_CHANNEL_LABELS: Record<NotificationChannel, string> = {
  panel: 'Панель',
  telegram: 'Telegram',
  email: 'Пошта',
}

export const DIGEST_RESULT_LABELS: Record<NotificationResult, string> = {
  sent: 'жіберілді',
  failed: 'жіберілмеді',
  skipped: 'арна бапталмаған',
}

/**
 * Рассылка сводки для руководителя (T-67, §6.2 дизайна, DESIGN.md §3.32): список, drawer,
 * «Отправить сейчас» с подтверждением и «Предпросмотр», который скачивает тот же PDF.
 */
export const DIGEST_LABELS = {
  title: 'Басшыға арналған жиынтық',
  subtitle: 'Аптасына бір бет: пошта және Telegram',
  lead:
    'Шығарылым апта бойғы панель деректері бойынша жиналады және кесте бойынша PDF қоса ' +
    'берілген хатпен және Telegram хабарымен кетеді. Әрбір жіберілім хабарлама журналына түседі.',
  add: 'Жаңа жіберілім',
  addAction: 'Жіберілім қосу',
  edit: 'Жіберілімді өзгерту',
  emptyTitle: 'Әзірге жіберілім жоқ',
  emptyDescription: 'Жіберілім қосыңыз: қамту, апта күні, сағат және алушылар.',
  scope: 'Қамту',
  region: 'Аудан немесе қала',
  regionPlaceholder: 'Тізімнен таңдаңыз',
  regionRequired: 'Аудан немесе қала таңдаңыз',
  when: 'Қашан',
  weekday: 'Апта күні',
  hour: 'Сағат',
  hourHint: 'Алматы уақыты; кесте жіберілім баптауында сақталады.',
  recipients: 'Алушылар',
  recipientsPlaceholder: 'Мекенжайды енгізіп, Enter басыңыз',
  recipientsHint: 'Басшылардың электрондық пошта мекенжайлары.',
  recipientsInvalid: 'name@example.kz түріндегі мекенжайды енгізіңіз',
  channels: 'Арналар',
  telegram: 'Telegram чаты',
  telegramPlaceholder: 'Чат идентификаторы',
  active: 'Жіберілім қолданыста',
  activeHint: 'Өшірілген жіберілім кесте бойынша кетпейді, «Қазір жіберу» жұмыс істейді.',
  lastSent: 'Соңғы жіберілім',
  neverSent: 'Әлі кеткен жоқ',
  sendNow: 'Қазір жіберу',
  sendConfirmTitle: 'Жиынтықты қазір жіберу керек пе?',
  sendConfirmText: 'PDF қоса берілген хат пен Telegram хабары алушыларға кестеден тыс кетеді.',
  sendConfirmOk: 'Жіберу',
  sendConfirmCancel: 'Болдырмау',
  sent: 'Жиынтық жіберілді',
  preview: 'Алдын ала қарау',
  previewFailed: 'Алдын ала қарау жасалмады',
  remove: 'Жою',
  removeConfirmTitle: 'Жіберілімді жою керек пе?',
  removeConfirmText: 'Бұрын кеткен шығарылымдар хабарлама журналында қалады.',
  removed: 'Жіберілім жойылды',
  created: 'Жіберілім қосылды',
  changed: 'Жіберілім өзгертілді',
} as const

/** Column of the provider score table (T-68, DESIGN.md §3.29, docs/design/README.md §6.3). */
export const PROVIDER_COLUMN_LABELS = {
  name: 'Жеткізуші',
  schools: 'Мектеп',
  belowContract: 'Шарттан төмен',
  incidents: 'Инцидент',
  reaction: 'Жауап беру',
  restore: 'Қалпына келтіру',
  school: 'Мектеп',
  region: 'Аудан',
  status: 'Мәртебе',
  belowNorm: 'Шарт нормадан төмен',
  score: 'Баға',
} as const

/** Verdict on the score: at the passing threshold of the settings or below it. */
export const PROVIDER_VERDICT_LABELS = {
  pass: 'Қалыпты',
  below_norm: 'Шектен төмен',
} as const

/** Strip of the provider card, in the order of `Providers.html`. */
export const PROVIDER_KPI_LABELS = {
  belowContract: 'Шарттан төмен уақыт',
  incidents: 'Инцидент',
  reaction: 'Орташа жауап беру',
  restore: 'Орташа қалпына келтіру',
  availability: 'Қолжетімділік',
} as const

/** Section «Поставщики» (T-68): claim work — score, escalation, act, contract below the norm. */
export const PROVIDER_LABELS = {
  context: 'Талап-шағым жұмысы',
  subtitle: 'Негізгі арналар · кезеңдегі баға',
  scoreTable: 'Кезеңдегі жеткізушілер бағасы',
  scoreOf: (score: string, threshold: string) => `баға ${score} · шек ${threshold}`,
  reactionNorm: (norm: string) => `норма ${norm}`,
  availabilityNorm: (norm: string) => `норма ${norm}`,
  incidentsClosed: (closed: string) => `қалпына келтірілді ${closed}`,
  worst: (value: string) => `ең жаманы ${value}`,
  belowNormFilter: 'Шарт нормадан төмен',
  belowNorm: 'Шарт нормадан төмен',
  notAClaim: 'талап емес',
  belowNormHint: 'Шарттық жылдамдық профиль шегінен төмен: жаңа шарт керек, өтініш емес.',
  belowNormEmpty: 'Жеткізушінің барлық шарты профиль шегінен төмен емес.',
  contractOf: (down: string, up: string) => `шарт ${down} / ${up}`,
  schools: 'Жеткізушінің мектептері',
  schoolsBelowContract: 'Шарттан төмен',
  sustained: 'тұрақты шарттан төмен',
  escalation: 'Эскалация',
  escalationHint:
    'Баға шектен төмен — талап-шағым жұмысының негізі: сәйкессіздік актісі және жеткізушіге өтініш.',
  act: 'Актіні жүктеу',
  actTitle: 'Сәйкессіздік актісі',
  actHint: 'Шарттан төмен замерлер, әрбір замердің шектері мен шарттық мәндерімен.',
  actFailed: 'Акт жасалмады',
  selectHint: 'Карточканы ашу үшін кестеден жеткізушіні таңдаңыз.',
  empty: 'Жеткізушілер әзірге жоқ',
  emptyHint: 'Кезеңде жеткізуші арналарында замерлер өткенде баға шығады.',
  filteredEmpty: 'Шарты нормадан төмен жеткізуші жоқ',
  reset: 'Сүзгіні тазалау',
  open: 'Карточканы ашу',
  noScore: 'кезеңде замер жоқ',
  plannedWorks: 'Жоспарлы жұмыс терезелері бағадан әзірге шығарылмайды: күнтізбе кейін шығады.',
} as const

/** Lists of «Внедрение» (T-69, docs/design/README.md §6.4); the key is the `filter` of the endpoint. */
export const ROLLOUT_FILTER_LABELS = {
  not_connected: 'Қосылмаған',
  silent: 'Үнсіз',
  code_unused: 'Код қолданылмаған',
  old_version: 'Агенттің ескі нұсқасы',
} as const

/** Columns of the two tables of the rollout: the districts and the schools of a list (DESIGN.md §3.30). */
export const ROLLOUT_COLUMN_LABELS = {
  region: 'Аудан немесе қала',
  schools: 'Мектеп',
  connected: 'Қосылған',
  alive: 'Байланыста',
  share: 'Қосылғандар үлесі',
  school: 'Мектеп',
  reason: 'Не дұрыс емес',
  devices: 'Компьютер',
  version: 'Агент нұсқасы',
} as const

/** Cells of the «Ход внедрения» strip of Rollout.html: the three colours and the agent versions. */
export const ROLLOUT_KPI_LABELS = {
  connected: 'Қосылған',
  alive: 'Байланыста',
  silent: 'Орнатылған, бірақ үнсіз',
  notConnected: 'Қосылмаған',
  oldVersion: 'Ескі нұсқаларда',
} as const

/** Captions of the rollout screen (T-69, DESIGN.md §3.30). */
export const ROLLOUT_LABELS = {
  progress: 'Енгізу барысы',
  regions: 'Аудандар мен қалалар бойынша',
  lists: 'Кім әрекет күтеді',
  registry: (total: string) => `тізілімдегі ${total} ішінен`,
  context: (scope: string) => `Енгізу · ${scope}`,
  verdict: (connected: string, total: string, noun: string) =>
    `${total} ${noun} ішінен ${connected} қосылған`,
  subtitle: (alive: string, time: string) => `Байланыста ${alive} · деректер ${time}`,
  release: (version: string) => `Агенттің қазіргі релизі ${version}`,
  noRelease: 'Агент релизі жарияланбаған',
  silentWindow: (days: string, noun: string) => `${days} ${noun} артық үнсіз`,
  dayForms: ['күн', 'күн', 'күн'] as [string, string, string],
  deviceForms: ['компьютер', 'компьютер', 'компьютер'] as [string, string, string],
  silentSince: (days: string, noun: string) => `соңғы сигнал ${days} ${noun} бұрын`,
  neverSeen: 'бірде-бір рет байланысқа шықпаған',
  codeAge: (days: string, noun: string) => `код ${days} ${noun} қолданылмаған`,
  noDevices: 'бірде-бір компьютер жоқ',
  noContact: 'жауапты адам жоқ',
  emptyTitle: 'Бұл тізімде ешкім жоқ',
  emptyDescription: 'Мектептер тізім критерийіне сәйкес келген бойда осында шығады.',
  assign: 'Жаңарту тағайындау',
  assignConfirmTitle: (version: string) => `${version} жаңартуын тағайындау керек пе?`,
  assignConfirmText:
    'Таңдалған компьютерлер осы нұсқаның арнасына өтеді және агент конфигурациясы келесі ' +
    'жаңартылғанда оны орнатады. Тарих пен өлшемдер өзгермейді.',
  assignConfirmOk: 'Тағайындау',
  assignConfirmCancel: 'Болдырмау',
  assigned: (count: string, noun: string) => `Жаңарту тағайындалды: ${count} ${noun}`,
  assignFailed: 'Жаңарту тағайындалмады',
  assignNoRelease: 'Агенттің қолданыстағы релизі жоқ: оны әкімшілендіруде жариялаңыз',
} as const

/** Тип события календаря (T-70, docs/design/README.md §6.5). */
export const CALENDAR_KIND_LABELS: Record<CalendarKind, string> = {
  vacation: 'Демалыс',
  holiday: 'Мереке',
  planned_works: 'Жоспарлы жұмыстар',
}

/** Чьи данные закрывает событие календаря. */
export const CALENDAR_SCOPE_LABELS: Record<CalendarScope, string> = {
  oblast: 'Бүкіл облыс',
  district: 'Аудан немесе қала',
  school: 'Мектеп',
}

/** Почему нет данных: школа не работает по календарю (DESIGN.md §4.1, T-70). */
export const CALENDAR_NO_DATA_HINTS: Record<CalendarKind, string> = {
  vacation: 'Күнтізбе бойынша демалыс',
  holiday: 'Мереке күні',
  planned_works: 'Жеткізушінің жоспарлы жұмыстары',
}

/** Подписи вкладки «Календарь» администрирования (T-70). */
export const CALENDAR_LABELS = {
  lead:
    'Демалыс пен мерекеде қолжетімділік есептелмейді және инциденттер ашылмайды, агенттің үнсіздігі ' +
    '«Дерек жоқ» болып көрсетіледі. Жоспарлы жұмыстар терезесі жеткізуші бағасына кірмейді.',
  add: 'Оқиға қосу',
  import: 'Кестеден импорттау',
  importHint: 'kind, title, start, end бағандары бар CSV файлы; school_code және region_code — қалауыңызша.',
  imported: (created: string) => `Жүктелген оқиға: ${created}`,
  importFailed: 'Файл жүктелмеді',
  importErrors: (count: string) => `Қателі жолдар: ${count}`,
  columnKind: 'Түрі',
  columnTitle: 'Оқиға',
  columnPeriod: 'Кезең',
  columnTarget: 'Кім үшін',
  wholeOblast: 'Облыстың барлық мектебі',
  emptyTitle: 'Әзірге оқиға жоқ',
  emptyDescription: 'Демалысты, мерекені немесе жұмыс терезесін қосыңыз не кестені жүктеңіз.',
  newTitle: 'Жаңа оқиға',
  editTitle: 'Оқиғаны өзгерту',
  kindField: 'Оқиға түрі',
  scopeField: 'Оқиға кім үшін',
  regionField: 'Аудан немесе қала',
  schoolField: 'Мектеп',
  providerField: 'Жеткізуші',
  providerHint: 'Тек жоспарлы жұмыстар үшін: терезе осы жеткізушінің желілеріне қатысты.',
  titleField: 'Атауы',
  periodField: 'Кезең',
  periodHint: 'Демалыс пен мереке Asia/Almaty жергілікті тәулігімен беріледі.',
  commentField: 'Түсініктеме',
  requiredTitle: 'Атауын көрсетіңіз',
  requiredPeriod: 'Кезеңді көрсетіңіз',
  requiredRegion: 'Ауданды немесе қаланы таңдаңыз',
  requiredSchool: 'Мектепті таңдаңыз',
  created: 'Оқиға қосылды',
  changed: 'Оқиға өзгертілді',
  deleted: 'Оқиға жойылды',
  edit: 'Өзгерту',
  delete: 'Жою',
  deleteTitle: 'Күнтізбе оқиғасын жою керек пе?',
  deleteText: 'Есептеулер бұл күндерді қайта ескереді. Өлшемдер мен тарих өзгермейді.',
  deleteOk: 'Жою',
  deleteCancel: 'Болдырмау',
} as const

/** Captions of the wall of the situation room (T-71, DESIGN.md §3.33). */
export const WALL_LABELS = {
  ticker: 'Таспа',
  tickerEmpty: 'Оқиғалар әзірге жоқ',
  hint: 'Автожаңарту 60 с · Esc панельге қайтарады',
  updated: (time: string) => `Деректер ${time} жағдайына`,
} as const
