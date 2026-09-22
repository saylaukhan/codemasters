// Rollout of the monitoring (T-69): the progress of the oblast and its districts, the four lists of
// docs/design/README.md §6.4 and «Назначить обновление» through the update channel of T-50.
import { apiRequest, type QueryValue } from './client'
import type { Camelize } from './case'
import type { components } from './generated/schema'

type Schemas = components['schemas']

export type RolloutSummary = Camelize<Schemas['RolloutSummary']>
export type RolloutRegionRow = Camelize<Schemas['RolloutRegionRow']>
export type RolloutSchoolPage = Camelize<Schemas['RolloutSchoolPage']>
export type RolloutSchoolItem = Camelize<Schemas['RolloutSchoolItem']>
export type RolloutFilter = Schemas['RolloutFilter']
export type AgentUpdateAssign = Camelize<Schemas['AgentUpdateAssign']>
export type AgentUpdateAssigned = Camelize<Schemas['AgentUpdateAssigned']>

export const getRolloutSummary = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['RolloutSummary']>('/rollout/summary', { query, signal })

/** One of the four lists; `total` counts the schools before `limit`, for «Ещё N школ». */
export const getRolloutSchools = (query: Record<string, QueryValue>, signal?: AbortSignal) =>
  apiRequest<Schemas['RolloutSchoolPage']>('/rollout/schools', { query, signal })

/** Target version of the chosen computers, or of a whole district: the channel that delivers it (T-50). */
export const assignAgentUpdate = (body: AgentUpdateAssign) =>
  apiRequest<Schemas['AgentUpdateAssigned']>('/rollout/devices/agent-update', { method: 'POST', body })
