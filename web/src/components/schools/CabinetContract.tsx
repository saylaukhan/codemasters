import { Phone } from 'lucide-react'
import type { ReactNode } from 'react'

import type { LineDetail } from '../../api/types'
import { formatDate, formatSpeedPair, NO_VALUE } from '../../lib/format'
import { CABINET_FIELD_LABELS, CABINET_LABELS, CABINET_LINE_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { Button } from '../ui/Button'
import { telHref } from './cabinet'
import styles from './SchoolCabinet.module.css'

interface CabinetContractProps {
  line: LineDetail | undefined
  /** Support of the provider, from the contacts of the school (ТЗ п. 15); empty — no button. */
  supportPhone: string | null
  /** SchoolPhone.html drops the row «Подключение» and widens the support button (DESIGN.md §9.3). */
  phone?: boolean
  placeholder?: ReactNode
}

/** Card «Провайдер и договор»: who gives the internet and what he promised (ТЗ п. 10, п. 14). */
export function CabinetContract({ line, supportPhone, phone = false, placeholder }: CabinetContractProps) {
  const connection = line && [line.connectionTypeName, CABINET_LINE_LABELS[line.status]].filter(Boolean)
  return (
    <section className={styles.card} aria-label={CABINET_LABELS.contract}>
      <h2 className={styles.title}>{CABINET_LABELS.contract}</h2>
      {placeholder ?? (
        <>
          <dl className={styles.fields}>
            <dt>{CABINET_FIELD_LABELS.provider}</dt>
            <dd>{line?.providerName ?? NO_VALUE}</dd>
            {!phone && (
              <>
                <dt>{CABINET_FIELD_LABELS.connection}</dt>
                <dd>{connection?.length ? connection.join(' · ') : NO_VALUE}</dd>
              </>
            )}
            <dt>{CABINET_FIELD_LABELS.contract}</dt>
            <dd>{formatSpeedPair(line?.contractDownMbps, line?.contractUpMbps)}</dd>
            <dt>{CABINET_FIELD_LABELS.contractNumber}</dt>
            <dd>
              {line?.contractNumber ?? NO_VALUE}
              {line?.contractDate ? ` ${CABINET_LABELS.from} ${formatDate(line.contractDate)}` : ''}
            </dd>
          </dl>
          {supportPhone && (
            <p className={styles.support}>
              <Button
                block={phone}
                href={telHref(supportPhone)}
                icon={<Phone size={SIZES.iconSm} strokeWidth={SIZES.iconStroke} aria-hidden />}
              >
                {phone ? CABINET_LABELS.callSupport : CABINET_LABELS.support}
              </Button>
              {!phone && <span className={styles.contactRole}>{CABINET_LABELS.roundClock}</span>}
            </p>
          )}
        </>
      )}
    </section>
  )
}
