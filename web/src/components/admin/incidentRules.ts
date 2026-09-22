// Incident rules of the administration (T-40, T-59, ADR-007): the conditions of a rule in words, whose lines it
// watches, and the bodies of its form.
import type { IncidentMetric, IncidentRuleCreate, IncidentRuleDetail, IncidentRuleScope, IncidentRuleUpdate } from '../../api/types'
import { INCIDENT_RULE_GLOBAL_TARGET_LABEL } from '../../lib/labels'
import { changedFields } from './form'

type Conditions = Pick<IncidentRuleDetail, 'consecutiveViolations' | 'durationMin'>

/** What opens an incident: «3 подряд или 30 мин», «3 подряд» or «30 мин»; whichever comes first. */
export function formatOpening({ consecutiveViolations, durationMin }: Conditions): string {
  const conditions = [
    consecutiveViolations != null && `${consecutiveViolations} подряд`,
    durationMin != null && `${durationMin} мин`,
  ].filter(Boolean)
  return conditions.join(' или ')
}

/** When `restored_at` is set: «после 2 нормальных подряд». */
export const formatRecovery = (count: number): string =>
  `после ${count} ${count % 10 === 1 && count % 100 !== 11 ? 'нормального' : 'нормальных'} подряд`

/** Whose lines the rule watches: the school by its name and School ID, or every school without a rule of its own. */
export const formatTarget = (rule: Pick<IncidentRuleDetail, 'scope' | 'schoolCode' | 'schoolName'>): string =>
  rule.scope === 'school' ? `${rule.schoolName} · ${rule.schoolCode}` : INCIDENT_RULE_GLOBAL_TARGET_LABEL

export interface IncidentRuleFormValues {
  name: string
  /** Only of a new rule: another metric is another rule. */
  metric?: IncidentMetric
  /** Only of a new rule: the oblast, or one school in place of the oblast for its lines (T-59). */
  scope: IncidentRuleScope
  /** With its label: a school picked from one search stays named when the search changes. */
  school?: { value: number; label: string }
  /** A cleared number is `null`, as InputNumber gives it; at least one of the two, the form checks it. */
  consecutiveViolations: number | null
  durationMin: number | null
  recoveryNormalCount: number | null
  isActive: boolean
}

export const incidentRuleFormValues = (rule?: IncidentRuleDetail): IncidentRuleFormValues => ({
  name: rule?.name ?? '',
  metric: rule?.metric,
  scope: rule?.scope ?? 'global',
  school:
    rule?.schoolId != null ? { value: rule.schoolId, label: `${rule.schoolCode} · ${rule.schoolName}` } : undefined,
  consecutiveViolations: rule?.consecutiveViolations ?? null,
  durationMin: rule?.durationMin ?? null,
  recoveryNormalCount: rule?.recoveryNormalCount ?? null,
  isActive: rule?.isActive ?? true,
})

/** Body of POST /api/admin/incident-rules; the metric, M and the school of a school rule are required by the form. */
export const incidentRuleCreateBody = (values: IncidentRuleFormValues): IncidentRuleCreate => ({
  name: values.name.trim(),
  metric: values.metric as IncidentMetric,
  scope: values.scope,
  schoolId: values.scope === 'school' ? (values.school?.value ?? null) : null,
  consecutiveViolations: values.consecutiveViolations,
  durationMin: values.durationMin,
  recoveryNormalCount: values.recoveryNormalCount as number,
})

const updatableOf = (values: IncidentRuleFormValues): IncidentRuleUpdate => ({
  name: values.name.trim(),
  consecutiveViolations: values.consecutiveViolations,
  durationMin: values.durationMin,
  recoveryNormalCount: values.recoveryNormalCount as number,
  isActive: values.isActive,
})

/** Body of PATCH /api/admin/incident-rules/{id}: the changed fields only; a cleared N or T is `null`. */
export const incidentRuleUpdateBody = (
  initial: IncidentRuleFormValues,
  values: IncidentRuleFormValues,
): IncidentRuleUpdate => changedFields(updatableOf(initial), updatableOf(values))
