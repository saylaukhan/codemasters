import { MonitorSmartphone } from 'lucide-react'
import type { ReactNode } from 'react'

import type { DeviceListItem } from '../../api/types'
import { formatRelative, NO_VALUE } from '../../lib/format'
import { CABINET_LABELS } from '../../lib/labels'
import { SIZES } from '../../styles/theme'
import { ConnectionStatusBadge } from '../ui/StatusBadge'
import styles from './SchoolCabinet.module.css'

interface CabinetAgentProps {
  device: DeviceListItem | undefined
  placeholder?: ReactNode
}

/**
 * Card «Компьютер с агентом» (DESIGN.md §3.27): where the agent stands, when it last called in and
 * the reminder that a switched-off computer is «Нет данных», not a problem of the internet (T-16).
 */
export function CabinetAgent({ device, placeholder }: CabinetAgentProps) {
  return (
    <section className={styles.card} aria-label={CABINET_LABELS.agent}>
      <div className={styles.head}>
        <h2 className={styles.title}>{CABINET_LABELS.agent}</h2>
        {device && <ConnectionStatusBadge status={device.currentStatus} />}
      </div>
      {placeholder ?? (
        <>
          <div className={styles.agent}>
            <span className={styles.agentIcon}>
              <MonitorSmartphone size={SIZES.iconMd} strokeWidth={SIZES.iconStroke} aria-hidden />
            </span>
            <span className={styles.stack}>
              <span className={styles.agentName}>
                {device?.monitoringPointName ?? NO_VALUE}
                {device?.hostname ? ' · ' : ''}
                {device?.hostname && <span className={styles.code}>{device.hostname}</span>}
              </span>
              <span className={styles.note}>
                {CABINET_LABELS.agentSignal} {formatRelative(device?.lastSeenAt)}
                {device?.agentVersion ? ` · ${CABINET_LABELS.agentVersion} ${device.agentVersion}` : ''}
              </span>
            </span>
          </div>
          <p className={styles.note}>{CABINET_LABELS.agentNote}</p>
        </>
      )}
    </section>
  )
}
