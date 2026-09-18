import { Button as AntButton, Tooltip, type ButtonProps as AntButtonProps } from 'antd'

// Button variants of DESIGN.md §3.1 on top of AntD 5.21+ `color` / `variant` (§2.3).
const VARIANTS = {
  action: { color: 'primary', variant: 'solid' },
  normal: { color: 'default', variant: 'filled' },
  outlined: { color: 'default', variant: 'outlined' },
  flat: { color: 'default', variant: 'text' },
  danger: { color: 'danger', variant: 'solid' },
  link: { type: 'link' },
} as const satisfies Record<string, AntButtonProps>

export type ButtonKind = keyof typeof VARIANTS

export interface ButtonProps extends Omit<AntButtonProps, 'type' | 'color' | 'variant' | 'danger' | 'ghost'> {
  /** Only one `action` per screen (DESIGN.md §1, rule 2). */
  kind?: ButtonKind
  /** Required for an icon-only button: shown on hover and read as its aria-label. */
  tooltip?: string
}

export function Button({ kind = 'normal', tooltip, ...props }: ButtonProps) {
  const button = <AntButton {...VARIANTS[kind]} aria-label={props['aria-label'] ?? tooltip} {...props} />
  return tooltip ? <Tooltip title={tooltip}>{button}</Tooltip> : button
}
