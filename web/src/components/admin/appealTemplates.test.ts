import { describe, expect, it } from 'vitest'

import type { AppealTemplateDetail } from '../../api/types'
import {
  appealTemplateCreateBody,
  appealTemplateFormValues,
  appealTemplateUpdateBody,
  placeholderMark,
} from './appealTemplates'

const claim: AppealTemplateDetail = {
  id: 2,
  name: 'Претензионное письмо',
  kind: 'claim',
  subject: 'Претензия по договору {{contract_number}}: {{school_code}}',
  body: '**{{provider_name}}**\n\n{{facts}}',
  aiInstructions: 'Официальный стиль.',
  isDefault: false,
  isActive: true,
  updatedAt: '2026-09-22T05:00:00Z',
}

describe('letter templates of the administration', () => {
  it('writes a placeholder as it is typed', () => {
    expect(placeholderMark('school_name')).toBe('{{school_name}}')
  })

  it('sends a new template trimmed, blank instructions as null', () => {
    expect(
      appealTemplateCreateBody({
        name: ' Претензия ',
        kind: 'claim',
        subject: ' {{topic}} ',
        body: '{{facts}}\n',
        aiInstructions: '   ',
        isDefault: true,
        isActive: true,
      }),
    ).toEqual({
      name: 'Претензия',
      kind: 'claim',
      subject: '{{topic}}',
      body: '{{facts}}',
      aiInstructions: null,
      isDefault: true,
    })
  })

  it('patches only what changed', () => {
    const initial = appealTemplateFormValues(claim)
    expect(appealTemplateUpdateBody(initial, { ...initial, isDefault: true })).toEqual({ isDefault: true })
    expect(appealTemplateUpdateBody(initial, { ...initial, aiInstructions: null, isActive: false })).toEqual({
      aiInstructions: null,
      isActive: false,
    })
    expect(appealTemplateUpdateBody(initial, { ...initial, name: 'Претензионное письмо ' })).toEqual({})
  })

  it('starts a new template as an active appeal', () => {
    expect(appealTemplateFormValues()).toMatchObject({ kind: 'appeal', isDefault: false, isActive: true })
  })
})
