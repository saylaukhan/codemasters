// Panel-side names for the generated OpenAPI types (ADR-009): payloads in camelCase, enum codes as is.
import type { Camelize } from './case'
import type { components, operations } from './generated/schema'

type Schemas = components['schemas']

/** A schema of the contract with camelCase keys, e.g. `Schema<'CurrentUser'>`. */
export type Schema<K extends keyof Schemas> = Camelize<Schemas[K]>

export type CurrentUser = Schema<'CurrentUser'>
export type FieldError = Schema<'FieldError'>

export type SchoolStatus = Schemas['SchoolStatus']
export type QualityStatus = Schemas['QualityStatus']
export type IncidentStatus = Schemas['IncidentStatus']
export type IncidentMetric = Schemas['IncidentMetric']
export type UserRole = Schemas['UserRole']
export type Locale = Schemas['Locale']
export type LineStatus = Schemas['LineStatus']
export type DeviceStatus = Schemas['DeviceStatus']
export type IfaceType = Schemas['IfaceType']
export type AnalyticsPeriod = Schemas['AnalyticsPeriod']
export type AnalyticsLevel = Schemas['AnalyticsLevel']
export type Weekday = Schemas['Weekday']
export type ExportMode = Schemas['ExportMode']
export type ExportFormat = Schemas['ExportFormat']
export type ExportColumn = Schemas['ExportColumn']
export type ExportStatus = Schemas['ExportStatus']
/** Column of an aggregates file (T-31): fixed, not chosen, so not in the contract. */
export type ExportAggregateColumn =
  | 'school_code'
  | 'school_name'
  | 'measurements_count'
  | 'avg_download_mbps'
  | 'min_download_mbps'
  | 'avg_upload_mbps'
  | 'avg_ping_ms'
  | 'problem_count'
  | 'problem_pct'

export type DashboardSummary = Schema<'DashboardSummary'>
/** The period-dependent half of the KPIs: the same six numbers describe the previous period (T-60). */
export type DashboardPeriodKpis = Schema<'DashboardPeriodKpis'>
/** Schools per status at `period_to`, counted before the status filter narrows them (T-60). */
export type SchoolStatusCounts = Schema<'SchoolStatusCounts'>
export type SchoolMapCollection = Schema<'SchoolMapFeatureCollection'>
export type SchoolMapFeature = Schema<'SchoolMapFeature'>
export type RegionMapCollection = Schema<'RegionMapFeatureCollection'>
export type MapFilterOptions = Schema<'MapFilterOptions'>

// «Требуют внимания» of the main screen (T-60): what is wrong, where, and since when.
export type AttentionPage = Schema<'AttentionPage'>
export type AttentionItem = Schema<'AttentionItem'>
export type AttentionKind = Schemas['AttentionKind']
export type AttentionReason = Schemas['AttentionReason']

export type SchoolListItem = Schema<'SchoolListItem'>
export type SchoolSort = Schemas['SchoolSort']

export type SchoolDetail = Schema<'SchoolDetail'>
/** Day strip of the school cabinet (T-61): one entry per local day, oldest first. */
export type SchoolDays = Schema<'SchoolDays'>
export type SchoolDay = Schema<'SchoolDay'>
export type SchoolCreate = Schema<'SchoolCreate'>
export type SchoolUpdate = Schema<'SchoolUpdate'>
export type WorkingHours = Schema<'WorkingHours'>
export type GeoPoint = Schema<'GeoPoint'>
export type LatestMeasurement = Schema<'LatestMeasurement'>
export type DeviceListItem = Schema<'DeviceListItem'>
export type DeviceDetail = Schema<'DeviceDetail'>
export type MeasurementListItem = Schema<'MeasurementListItem'>
export type LineDetail = Schema<'LineDetail'>
export type SchoolContactDetail = Schema<'SchoolContactDetail'>
export type MonitoringPointDetail = Schema<'MonitoringPointDetail'>
export type AnalyticsReport = Schema<'AnalyticsReport'>
export type AnalyticsRow = Schema<'AnalyticsRow'>
export type IncidentAnalyticsReport = Schema<'IncidentAnalyticsReport'>
export type IncidentAnalyticsRow = Schema<'IncidentAnalyticsRow'>

/** Body of POST /api/exports: `columns` has a default and is raw only, so it may be left out. */
export type ExportCreate = Omit<Schema<'ExportCreate'>, 'columns'> & Partial<Pick<Schema<'ExportCreate'>, 'columns'>>
export type ExportJob = Schema<'ExportJob'>
export type ExportJobPage = Schema<'ExportJobPage'>
/** Filters of GET /api/exports/estimate: the selection of an export without its format and columns (T-64). */
export type ExportEstimateQuery = Camelize<operations['estimate_export']['parameters']['query']>
export type ExportEstimate = Schema<'ExportEstimate'>

// References of the administration (T-34): districts and cities, providers, connection types.
export type RegionListItem = Schema<'RegionListItem'>
export type RegionDetail = Schema<'RegionDetail'>
/** The boundary is loaded from GeoJSON by the seed, not edited in the panel. */
export type RegionCreate = Omit<Schema<'RegionCreate'>, 'boundary'>
export type RegionUpdate = Omit<Schema<'RegionUpdate'>, 'boundary'>
export type ProviderDetail = Schema<'ProviderDetail'>
export type ProviderCreate = Schema<'ProviderCreate'>
export type ProviderUpdate = Schema<'ProviderUpdate'>
export type ConnectionTypeDetail = Schema<'ConnectionTypeDetail'>
export type ConnectionTypeCreate = Schema<'ConnectionTypeCreate'>
export type ConnectionTypeUpdate = Schema<'ConnectionTypeUpdate'>

// Lines, monitoring points and contacts of a school (T-35), edited from its card.
/** The start of operation is not edited in the panel yet. */
export type LineCreate = Omit<Schema<'LineCreate'>, 'startedAt'>
export type LineUpdate = Omit<Schema<'LineUpdate'>, 'startedAt'>
export type MonitoringPointCreate = Schema<'MonitoringPointCreate'>
export type MonitoringPointUpdate = Schema<'MonitoringPointUpdate'>
export type SchoolContactCreate = Schema<'SchoolContactCreate'>
export type SchoolContactUpdate = Schema<'SchoolContactUpdate'>

// Devices of the administration (T-36): rebinding to a point, installation codes.
export type DeviceUpdate = Schema<'DeviceUpdate'>
export type EnrollmentCodeCreate = Schema<'EnrollmentCodeCreate'>
export type EnrollmentCodeIssued = Schema<'EnrollmentCodeIssued'>

// Thresholds, schedules and settings of the administration (T-37): nothing of it is in the code.
export type ThresholdProfileScope = Schemas['ThresholdProfileScope']
export type ThresholdValues = Schema<'ThresholdValues'>
export type ThresholdProfileDetail = Schema<'ThresholdProfileDetail'>
export type ThresholdProfileCreate = Schema<'ThresholdProfileCreate'>
export type ThresholdProfileUpdate = Schema<'ThresholdProfileUpdate'>
export type ScheduleScope = Schemas['ScheduleScope']
export type ScheduleSlot = Schema<'ScheduleSlot'>
export type ScheduleDetail = Schema<'ScheduleDetail'>
export type ScheduleCreate = Schema<'ScheduleCreate'>
export type ScheduleUpdate = Schema<'ScheduleUpdate'>
export type SettingsDetail = Schema<'SettingsDetail'>
export type SettingsUpdate = Schema<'SettingsUpdate'>

// Incident rules of the administration (T-40): N in a row or T minutes open an incident, M normal restore it.
export type IncidentRuleDetail = Schema<'IncidentRuleDetail'>
export type IncidentRuleCreate = Schema<'IncidentRuleCreate'>
export type IncidentRuleUpdate = Schema<'IncidentRuleUpdate'>

// Incidents (T-41): the list, the card with its history, manual creation from the school card, status changes.
export type IncidentListItem = Schema<'IncidentListItem'>
export type IncidentDetail = Schema<'IncidentDetail'>
export type IncidentBasisMetric = Schema<'IncidentBasisMetric'>
export type IncidentEventDetail = Schema<'IncidentEventDetail'>
export type IncidentEventKind = Schemas['IncidentEventKind']
export type IncidentCreate = Schema<'IncidentCreate'>
export type IncidentUpdate = Schema<'IncidentUpdate'>
export type IncidentStatusChange = Schema<'IncidentStatusChange'>
export type IncidentCommentCreate = Schema<'IncidentCommentCreate'>

// Appeals (T-47, ТЗ п. 17, ADR-011): the AI draft of a letter to the provider.
export type AppealDraftRequest = Schema<'AppealDraftRequest'>
export type AppealDraft = Schema<'AppealDraft'>
export type AppealContext = Schema<'AppealContext'>
export type MetricStats = Schema<'MetricStats'>

// Sent appeals (T-48): the number, the letter, the PDF, the same six statuses as an incident and their history.
export type AppealListItem = Schema<'AppealListItem'>
export type AppealListItemPage = Schema<'AppealListItemPage'>
export type AppealDetail = Schema<'AppealDetail'>
export type AppealEventDetail = Schema<'AppealEventDetail'>
export type AppealCreate = Schema<'AppealCreate'>
export type AppealUpdate = Schema<'AppealUpdate'>
export type AppealDeliveryStatus = Schemas['AppealDeliveryStatus']

// Users of the administration (T-38): a role with its scope, blocked instead of deleted.
export type UserDetail = Schema<'UserDetail'>
export type UserCreate = Schema<'UserCreate'>
export type UserUpdate = Schema<'UserUpdate'>

// Notifications (T-42): the bell of the header and its panel; every row is about an incident.
export type NotificationKind = Schemas['NotificationKind']
export type NotificationListItem = Schema<'NotificationListItem'>
export type NotificationChannel = Schemas['NotificationChannel']
export type NotificationResult = Schemas['NotificationResult']

// Audit log of the administration (T-39): sign-ins, changes, rejected agent requests; read-only.
export type AuditLogListItem = Schema<'AuditLogListItem'>
export type AuditAction = Schemas['AuditAction']
export type AuditEntityType = Schemas['AuditEntityType']

// Рассылки сводки для руководителя (T-67): охват, расписание, каналы и итог отправки.
export type DigestScope = Schemas['DigestScope']
export type DigestSettingsDetail = Schema<'DigestSettingsDetail'>
export type DigestSettingsCreate = Schema<'DigestSettingsCreate'>
export type DigestSettingsUpdate = Schema<'DigestSettingsUpdate'>
export type DigestSendResult = Schema<'DigestSendResult'>

// Календарь каникул, праздников и плановых работ (T-70): тип события, его цель и импорт.
export type CalendarKind = Schemas['CalendarKind']
export type CalendarScope = Schemas['CalendarScope']
export type CalendarEventDetail = Schema<'CalendarEventDetail'>
export type CalendarEventCreate = Schema<'CalendarEventCreate'>
export type CalendarEventUpdate = Schema<'CalendarEventUpdate'>
export type CalendarImportResult = Schema<'CalendarImportResult'>
