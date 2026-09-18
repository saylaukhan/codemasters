import type { SchoolContactDetail } from '../../api/types'
import { NO_VALUE, formatDate } from '../../lib/format'
import { Button } from '../ui/Button'
import styles from './SchoolCard.module.css'

interface ContactListProps {
  items: SchoolContactDetail[]
  /** The role has the right to see phones (`contacts:phone`); otherwise the API leaves them empty. */
  canSeePhone: boolean
  /** «Изменить» of a card, for a role that sets up the monitoring (T-35). */
  onEdit?: (contact: SchoolContactDetail) => void
}

/** Responsible people of the school (ТЗ п. 15, DESIGN.md §3.15). */
export function ContactList({ items, canSeePhone, onEdit }: ContactListProps) {
  return (
    <div className={styles.contacts}>
      {items.map((contact) => (
        <section key={contact.id} className={styles.contact} aria-label={contact.fullName}>
          <div className={styles.contactHead}>
            <h3 className={styles.contactName}>{contact.fullName}</h3>
            {onEdit && (
              <Button kind="flat" size="small" onClick={() => onEdit(contact)}>
                Изменить
              </Button>
            )}
          </div>
          {contact.position && <p className={styles.muted}>{contact.position}</p>}
          <dl className={styles.pairs}>
            <dt>Телефон</dt>
            <dd>
              {!canSeePhone ? (
                <span className={styles.muted}>Скрыт для вашей роли</span>
              ) : contact.phone ? (
                <a href={`tel:${contact.phone.replace(/[^+\d]/g, '')}`}>{contact.phone}</a>
              ) : (
                NO_VALUE
              )}
            </dd>
            <dt>Email</dt>
            <dd>{contact.email ? <a href={`mailto:${contact.email}`}>{contact.email}</a> : NO_VALUE}</dd>
            <dt>Техподдержка поставщика</dt>
            <dd>{contact.providerSupportContact ?? NO_VALUE}</dd>
          </dl>
          <p className={styles.updated}>Обновлено {formatDate(contact.updatedAt)}</p>
        </section>
      ))}
    </div>
  )
}
