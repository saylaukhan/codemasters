import { LOCALE_LABELS } from '../../lib/labels'
import { activeLocale, setLocale, type Locale } from '../../lib/locale'
import styles from './LocaleSwitch.module.css'

// DESIGN.md §3.5 prints the pill as «Қаз · Рус», so Kazakh is the first segment of the two.
const ORDER: readonly Locale[] = ['kk', 'ru']

/**
 * Language switch (DESIGN.md §3.5, §3.26): a 34px pill of two segments, in the header next to
 * the theme switch and in the top right corner of the sign-in screen. The panel picks its
 * dictionary once per page load (`lib/locale.ts`), so a segment reloads the page.
 */
export function LocaleSwitch() {
  const active = activeLocale()

  return (
    <div className={styles.pill} role="group" aria-label={LOCALE_LABELS.title}>
      {ORDER.map((locale) => (
        <button
          key={locale}
          type="button"
          className={styles.option}
          aria-pressed={locale === active}
          data-active={locale === active || undefined}
          onClick={() => {
            if (locale !== active) setLocale(locale)
          }}
        >
          {LOCALE_LABELS[locale]}
        </button>
      ))}
    </div>
  )
}
