import { Phone } from 'lucide-react'
import type { ReactNode } from 'react'

import type { SchoolContactDetail } from '../../api/types'
import { CABINET_CONTACT_LABELS, CABINET_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { telHref } from './cabinet'
import styles from './SchoolCabinet.module.css'

interface CabinetContactsProps {
  items: readonly SchoolContactDetail[]
  /** Support of the provider: its name for the caption, its phone from the contacts of the school. */
  providerName: string | undefined
  supportPhone: string | null
  placeholder?: ReactNode
}

interface CabinetContact {
  key: string
  role: string
  name: string
  /** Second line next to the phone: the position of the person or the hours of the support. */
  note: string | null
  phone: string | null
}

/**
 * Block «Кому звонить» (DESIGN.md §3.27, ТЗ п. 15): the responsible people of the school and the
 * support of its provider, the phone always a `tel:` link. Three free-standing cards in a row on a
 * wide screen, where the heading of the block is only its `aria-label` (School.html); a phone wraps
 * the same people in one card with a visible heading and turns them into call rows (SchoolPhone.html,
 * §9.3). The card of the district office waits for a source of its data.
 */
export function CabinetContacts({ items, providerName, supportPhone, placeholder }: CabinetContactsProps) {
  const contacts: CabinetContact[] = items.map((contact) => ({
    key: `contact-${contact.id}`,
    role: CABINET_CONTACT_LABELS.school,
    name: contact.fullName,
    note: contact.position,
    phone: contact.phone,
  }))
  if (providerName) {
    contacts.push({
      key: 'support',
      role: `${CABINET_CONTACT_LABELS.support} ${providerName}`,
      name: CABINET_CONTACT_LABELS.supportName,
      note: CABINET_LABELS.roundClock,
      phone: supportPhone,
    })
  }

  return (
    <section className={styles.contactsCard} aria-label={CABINET_LABELS.contacts}>
      <div className={`${styles.head} ${styles.contactsHead}`}>
        <h2 className={styles.title}>{CABINET_LABELS.contacts}</h2>
      </div>
      {placeholder ?? (
        <div className={styles.contacts}>
          {contacts.map((contact) => {
            const body = (
              <>
                <span className={styles.contactText}>
                  <span className={styles.contactRole}>{contact.role}</span>
                  <span className={styles.contactName}>{contact.name}</span>
                </span>
                {contact.phone && (
                  <>
                    <span className={styles.contactPhone}>
                      {contact.note ? `${contact.note} · ${contact.phone}` : contact.phone}
                    </span>
                    <span className={styles.callIcon} aria-hidden>
                      <Phone size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} />
                    </span>
                  </>
                )}
              </>
            )
            return contact.phone ? (
              <a
                key={contact.key}
                className={styles.contact}
                href={telHref(contact.phone)}
                aria-label={`${CABINET_CONTACT_LABELS.call} ${contact.name}`}
              >
                {body}
              </a>
            ) : (
              <div key={contact.key} className={styles.contact}>
                {body}
              </div>
            )
          })}
        </div>
      )}
    </section>
  )
}
