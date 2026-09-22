// Language of the panel (DESIGN.md §5.1, T-66): Russian or Kazakh, without an i18n framework
// (ADR-010). The dictionaries of labels.ts are plain module constants in 92 files, so the
// language cannot change under a rendered tree: it is decided once per page load, the switch
// remembers the choice and reloads the page. Remembered next to the theme of themeMode.ts;
// the profile keeps the same value, so a new browser opens the panel in the chosen language.
import { updateProfileLocale } from '../api/auth'
import { hasAccessToken } from '../api/client'
import type { Locale as ContractLocale } from '../api/types'
import * as kk from './labels.kk'
import * as ru from './labels.ru'

/** The two languages of the panel; `satisfies` keeps them the two codes of the contract. */
export const LOCALES = ['ru', 'kk'] as const satisfies readonly ContractLocale[]

export type Locale = (typeof LOCALES)[number]

/** Language of an account that never chose one (migration 20260922_1400_user_locale). */
export const DEFAULT_LOCALE: Locale = 'ru'

// One namespace with 'vko-monitor.theme' of themeMode.ts: the choices of this browser.
const STORAGE_KEY = 'vko-monitor.locale'

const known = (value: string | null | undefined): Locale | null =>
  LOCALES.find((locale) => locale === value) ?? null

function storedLocale(): Locale | null {
  try {
    return known(window.localStorage.getItem(STORAGE_KEY))
  } catch {
    // Storage may be blocked by the browser: the language of the browser decides instead.
    return null
  }
}

function browserLocale(): Locale | null {
  try {
    return known(window.navigator.language.slice(0, 2).toLowerCase())
  } catch {
    return null
  }
}

/** Language of this page load: the remembered choice, then the browser, then Russian. */
export function activeLocale(): Locale {
  return storedLocale() ?? browserLocale() ?? DEFAULT_LOCALE
}

export function rememberLocale(locale: Locale): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, locale)
  } catch {
    // Not remembered: the next visit starts from the language of the browser again.
  }
}

/** `lang` of the document follows the language (DESIGN.md §9.4); index.html ships with `ru`. */
export function applyDocumentLanguage(locale: Locale = activeLocale()): void {
  document.documentElement.lang = locale
}

/**
 * Switch the language: remember it, tell the server when someone is signed in, and load the
 * page again — the dictionaries are read at module load, so only a new load speaks the new
 * language. A profile that could not be saved does not hold the switch back: the browser
 * keeps the choice anyway, and the next sign-in of this user writes it again.
 */
export function setLocale(locale: Locale): void {
  rememberLocale(locale)
  applyDocumentLanguage(locale)
  const saved = hasAccessToken()
    ? updateProfileLocale(locale).catch(() => undefined)
    : Promise.resolve()
  void saved.then(() => {
    window.location.reload()
  })
}

/**
 * Language of the profile on a browser that has no choice of its own: the account chose it on
 * another computer, so the panel adopts it and loads again in that language. The choice is
 * remembered before the reload, so this happens once.
 */
export function adoptProfileLocale(locale: Locale): void {
  if (storedLocale() !== null || locale === activeLocale()) return
  rememberLocale(locale)
  applyDocumentLanguage(locale)
  window.location.reload()
}

/**
 * The Kazakh dictionary repeats the Russian one key for key and only its strings differ, so
 * `Localized<T>` is the Russian shape with the strings widened — and nothing else widened.
 */
export type Localized<T> = T extends string
  ? string
  : T extends number | boolean
    ? T
    : { [K in keyof T]: Localized<T[K]> }

const KAZAKH = activeLocale() === 'kk'

/**
 * The dictionary of the active language under the type of the Russian one. Consumers read
 * `keyof typeof` and unions off these constants (ADR-013), so the public type has to stay
 * `typeof ru.X`: the `Localized` parameter proves the Kazakh value has the same keys and the
 * same shape, and the cast then puts back the literal types the panel is typed with today.
 */
export function localized<T>(russian: T, kazakh: Localized<T>): T {
  return KAZAKH ? (kazakh as T) : russian
}

/** Dictionaries of the active language for a component that wants the whole module. */
export function useLabels(): typeof ru {
  return localized(ru, kk)
}
