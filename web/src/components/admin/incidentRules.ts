// Incident rules of the administration (T-40, ADR-007): the conditions of a rule in words and the bodies of its form.
import type { IncidentMetric, IncidentRuleCreate, IncidentRuleDetail, IncidentRuleUpdate } from '../../api/types'
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

export interface IncidentRuleFormValues {
  name: string
  /** Only of a new rule: another metric is another rule. */
  metric?: IncidentMetric
  /** A cleared number is `null`, as InputNumber gives it; at least one of the two, the form checks it. */
  consecutiveViolations: number | null
  durationMin: number | null
  recoveryNormalCount: number | null
  isActive: boolean
}

export const incidentRuleFormValues = (rule?: IncidentRuleDetail): IncidentRuleFormValues => ({
  name: rule?.name ?? '',
  metric: rule?.metric,
  consecutiveViolations: rule?.consecutiveViolations ?? null,
  durationMin: rule?.durationMin ?? null,
  recoveryNormalCount: rule?.recoveryNormalCount ?? null,
  isActive: rule?.isActive ?? true,
})

/** Body of POST /api/admin/incident-rules; the metric and M are required by the form before it submits. */
export const incidentRuleCreateBody = (values: IncidentRuleFormValues): IncidentRuleCreate => ({
  name: values.name.trim(),
  metric: values.metric as IncidentMetric,
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
