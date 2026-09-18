// Panel-side names for the generated OpenAPI types (ADR-009): payloads in camelCase, enum codes as is.
import type { Camelize } from './case'
import type { components } from './generated/schema'

type Schemas = components['schemas']

/** A schema of the contract with camelCase keys, e.g. `Schema<'CurrentUser'>`. */
export type Schema<K extends keyof Schemas> = Camelize<Schemas[K]>

export type CurrentUser = Schema<'CurrentUser'>
export type FieldError = Schema<'FieldError'>

export type SchoolStatus = Schemas['SchoolStatus']
export type QualityStatus = Schemas['QualityStatus']
export type IncidentStatus = Schemas['IncidentStatus']
export type UserRole = Schemas['UserRole']

export type DashboardSummary = Schema<'DashboardSummary'>
export type SchoolMapCollection = Schema<'SchoolMapFeatureCollection'>
export type SchoolMapFeature = Schema<'SchoolMapFeature'>
export type RegionMapCollection = Schema<'RegionMapFeatureCollection'>
export type MapFilterOptions = Schema<'MapFilterOptions'>

export type SchoolListItem = Schema<'SchoolListItem'>
export type SchoolSort = Schemas['SchoolSort']
