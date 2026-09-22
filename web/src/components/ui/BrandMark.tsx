import styles from './BrandMark.module.css'

interface BrandMarkProps {
  /** `md` is the 28px mark of the header and the sign-in card, `lg` the 40px mark of the wall. */
  size?: 'md' | 'lg'
}

/**
 * The Jyldam mark (DESIGN.md §1): a rounded square in the brand navy with a white school under
 * two arcs of signal. Decorative only, so it is hidden from assistive technology; the product
 * name is written next to it by the caller.
 */
export function BrandMark({ size = 'md' }: BrandMarkProps) {
  return (
    <span className={`${styles.mark} ${styles[size]}`} aria-hidden>
      <svg
        className={styles.icon}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth={1.75}
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        {/* Signal: two arcs around the source on the roof. */}
        <path d="M6.25 7.18a7.5 7.5 0 0 1 11.5 0" />
        <path d="M8.78 9.3a4.2 4.2 0 0 1 6.44 0" />
        <circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none" />
        {/* School: roof, walls, ground and door. */}
        <path d="M4.5 17.5 12 12l7.5 5.5" />
        <path d="M6 16.4V21" />
        <path d="M18 16.4V21" />
        <path d="M3 21h18" />
        <path d="M10.4 21v-3.2a1.6 1.6 0 0 1 3.2 0V21" />
      </svg>
    </span>
  )
}
