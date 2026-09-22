import { Steps, Timeline as AntTimeline, type StepsProps, type TimelineProps } from 'antd'

import styles from './Stepper.module.css'

/**
 * Status stepper over AntD `Steps` (DESIGN.md §2.3, §3.17): the fixed order of statuses with the
 * current one in 600. Thin on purpose — the card of an incident keeps its own layout, the wrapper
 * only holds the type scale so every stepper of the panel matches.
 */
export function Stepper({ className, size = 'small', ...props }: StepsProps) {
  return <Steps {...props} size={size} className={className ? `${styles.stepper} ${className}` : styles.stepper} />
}

/**
 * Event timeline over AntD `Timeline` (DESIGN.md §2.3, §3.17): the history of an incident or an
 * appeal. Same idea as `Stepper` — tokens only, no new markup.
 */
export function Timeline({ className, ...props }: TimelineProps) {
  return <AntTimeline {...props} className={className ? `${styles.timeline} ${className}` : styles.timeline} />
}
