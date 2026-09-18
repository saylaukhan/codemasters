import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import type { SchoolContactDetail } from '../../api/types'
import { ContactList } from './ContactList'

const CONTACT: SchoolContactDetail = {
  id: 1,
  schoolId: 42,
  fullName: 'Иванова Анна Борисовна',
  position: 'Заместитель директора',
  phone: '+7 700 000 00 00',
  email: 'school@example.kz',
  providerSupportContact: null,
  // 19:30 UTC on the 11th is the 12th in Almaty.
  updatedAt: '2026-09-11T19:30:00Z',
}

describe('ContactList', () => {
  it('shows the phone as a link to call and the date of the last update', () => {
    const html = renderToStaticMarkup(<ContactList items={[CONTACT]} canSeePhone />)

    expect(html).toContain('href="tel:+77000000000"')
    expect(html).toContain('href="mailto:school@example.kz"')
    expect(html).toContain('Обновлено 12.09.2026')
    expect(html).not.toContain('undefined')
  })

  it('says the phone is hidden for a role without the right', () => {
    const html = renderToStaticMarkup(<ContactList items={[{ ...CONTACT, phone: null }]} canSeePhone={false} />)

    expect(html).toContain('Скрыт для вашей роли')
    expect(html).not.toContain('tel:')
  })
})
