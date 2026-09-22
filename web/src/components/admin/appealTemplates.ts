// Letter templates of the administration (T-86, ТЗ п. 17, ADR-011): the values of the form and the bodies of
// POST and PATCH. The server fills `{{name}}` with the facts of the appeal and the model writes by the result.
import type { AppealKind, AppealTemplateCreate, AppealTemplateDetail, AppealTemplateUpdate } from '../../api/types'
import { changedFields, optionalText } from './form'

/** Length limits of backend/app/schemas/appeal_templates.py, checked before sending. */
export const SUBJECT_MAX_LENGTH = 255
export const BODY_MAX_LENGTH = 20000
export const INSTRUCTIONS_MAX_LENGTH = 2000

/** `{{name}}` as it is typed into a template. */
export const placeholderMark = (name: string): string => `{{${name}}}`

export interface AppealTemplateFormValues {
  name: string
  kind: AppealKind
  subject: string
  body: string
  aiInstructions: string | null
  isDefault: boolean
  isActive: boolean
}

export const appealTemplateFormValues = (template?: AppealTemplateDetail): AppealTemplateFormValues => ({
  name: template?.name ?? '',
  kind: template?.kind ?? 'appeal',
  subject: template?.subject ?? '',
  body: template?.body ?? '',
  aiInstructions: template?.aiInstructions ?? null,
  isDefault: template?.isDefault ?? false,
  isActive: template?.isActive ?? true,
})

/** Body of POST /api/admin/appeal-templates; a new template is active. */
export const appealTemplateCreateBody = (values: AppealTemplateFormValues): AppealTemplateCreate => ({
  name: values.name.trim(),
  kind: values.kind,
  subject: values.subject.trim(),
  body: values.body.trim(),
  aiInstructions: optionalText(values.aiInstructions),
  isDefault: values.isDefault,
})

const updatableOf = (values: AppealTemplateFormValues): AppealTemplateUpdate => ({
  ...appealTemplateCreateBody(values),
  isActive: values.isActive,
})

/** Body of PATCH /api/admin/appeal-templates/{id}: the changed fields only; cleared instructions are `null`. */
export const appealTemplateUpdateBody = (
  initial: AppealTemplateFormValues,
  values: AppealTemplateFormValues,
): AppealTemplateUpdate => changedFields<AppealTemplateUpdate>(updatableOf(initial), updatableOf(values))
