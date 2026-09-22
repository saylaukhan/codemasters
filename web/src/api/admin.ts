// References of the administration (T-34): districts and cities, providers, connection types; threshold
// profiles, schedules and settings (T-37); users (T-38); incident rules (T-40); letter templates (T-60). Nothing is
// deleted: schools and lines refer to the references, a profile, a schedule, a rule or a template is switched off, a
// user is blocked; a PATCH changes only the fields present.
// The audit log is read-only (T-39).
import { apiRequest, type QueryValue } from './client'
import type { components } from './generated/schema'
import type {
  AppealTemplateCreate,
  AppealTemplateUpdate,
  ConnectionTypeCreate,
  ConnectionTypeUpdate,
  ContractImportRequest,
  IncidentRuleCreate,
  IncidentRuleUpdate,
  ProviderCreate,
  ProviderUpdate,
  RegionCreate,
  RegionUpdate,
  ScheduleCreate,
  ScheduleUpdate,
  SettingsUpdate,
  ThresholdProfileCreate,
  ThresholdProfileUpdate,
  UserCreate,
  UserUpdate,
} from './types'

type Schemas = components['schemas']

export const getRegions = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['RegionListItemPage']>('/admin/regions', { query, signal })

export const createRegion = (body: RegionCreate) =>
  apiRequest<Schemas['RegionDetail']>('/admin/regions', { method: 'POST', body })

export const updateRegion = (regionId: number, body: RegionUpdate) =>
  apiRequest<Schemas['RegionDetail']>(`/admin/regions/${regionId}`, { method: 'PATCH', body })

export const getProviders = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ProviderDetailPage']>('/admin/providers', { query, signal })

export const createProvider = (body: ProviderCreate) =>
  apiRequest<Schemas['ProviderDetail']>('/admin/providers', { method: 'POST', body })

export const updateProvider = (providerId: number, body: ProviderUpdate) =>
  apiRequest<Schemas['ProviderDetail']>(`/admin/providers/${providerId}`, { method: 'PATCH', body })

export const getConnectionTypes = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ConnectionTypeDetailPage']>('/admin/connection-types', { query, signal })

export const createConnectionType = (body: ConnectionTypeCreate) =>
  apiRequest<Schemas['ConnectionTypeDetail']>('/admin/connection-types', { method: 'POST', body })

export const updateConnectionType = (connectionTypeId: number, body: ConnectionTypeUpdate) =>
  apiRequest<Schemas['ConnectionTypeDetail']>(`/admin/connection-types/${connectionTypeId}`, {
    method: 'PATCH',
    body,
  })

export const getThresholdProfiles = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ThresholdProfileDetailPage']>('/admin/thresholds', { query, signal })

export const createThresholdProfile = (body: ThresholdProfileCreate) =>
  apiRequest<Schemas['ThresholdProfileDetail']>('/admin/thresholds', { method: 'POST', body })

export const updateThresholdProfile = (profileId: number, body: ThresholdProfileUpdate) =>
  apiRequest<Schemas['ThresholdProfileDetail']>(`/admin/thresholds/${profileId}`, { method: 'PATCH', body })

export const getSchedules = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['ScheduleDetailPage']>('/admin/schedules', { query, signal })

export const createSchedule = (body: ScheduleCreate) =>
  apiRequest<Schemas['ScheduleDetail']>('/admin/schedules', { method: 'POST', body })

export const updateSchedule = (scheduleId: number, body: ScheduleUpdate) =>
  apiRequest<Schemas['ScheduleDetail']>(`/admin/schedules/${scheduleId}`, { method: 'PATCH', body })

export const getIncidentRules = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['IncidentRuleDetailPage']>('/admin/incident-rules', { query, signal })

export const createIncidentRule = (body: IncidentRuleCreate) =>
  apiRequest<Schemas['IncidentRuleDetail']>('/admin/incident-rules', { method: 'POST', body })

export const updateIncidentRule = (ruleId: number, body: IncidentRuleUpdate) =>
  apiRequest<Schemas['IncidentRuleDetail']>(`/admin/incident-rules/${ruleId}`, { method: 'PATCH', body })

export const getAppealTemplates = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['AppealTemplateDetailPage']>('/admin/appeal-templates', { query, signal })

/** What the server puts in place of `{{name}}` in a template: shown next to its editor. */
export const getAppealPlaceholders = (signal?: AbortSignal) =>
  apiRequest<Schemas['AppealPlaceholderList']>('/admin/appeal-templates/placeholders', { signal })

export const createAppealTemplate = (body: AppealTemplateCreate) =>
  apiRequest<Schemas['AppealTemplateDetail']>('/admin/appeal-templates', { method: 'POST', body })

/** The default template cannot be switched off or demoted: the API answers 409. */
export const updateAppealTemplate = (templateId: number, body: AppealTemplateUpdate) =>
  apiRequest<Schemas['AppealTemplateDetail']>(`/admin/appeal-templates/${templateId}`, { method: 'PATCH', body })

/** What the registry would change, without writing (T-61): the same report the import returns. */
export const previewContractImport = (body: ContractImportRequest) =>
  apiRequest<Schemas['ContractImportReport']>('/admin/contracts/import/preview', { method: 'POST', body })

/** The registry into the lines: rows with an error are skipped, the others applied together. */
export const importContracts = (body: ContractImportRequest) =>
  apiRequest<Schemas['ContractImportReport']>('/admin/contracts/import', { method: 'POST', body })

export const getSettings = (signal?: AbortSignal) =>
  apiRequest<Schemas['SettingsDetail']>('/admin/settings', { signal })

export const updateSettings = (body: SettingsUpdate) =>
  apiRequest<Schemas['SettingsDetail']>('/admin/settings', { method: 'PATCH', body })

export const getUsers = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['UserDetailPage']>('/admin/users', { query, signal })

export const createUser = (body: UserCreate) =>
  apiRequest<Schemas['UserDetail']>('/admin/users', { method: 'POST', body })

export const updateUser = (userId: number, body: UserUpdate) =>
  apiRequest<Schemas['UserDetail']>(`/admin/users/${userId}`, { method: 'PATCH', body })

export const getAuditLog = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['AuditLogListItemPage']>('/admin/audit-log', { query, signal })
