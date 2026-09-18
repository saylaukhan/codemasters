// Light or dark theme of the panel (DESIGN.md §2.1): the start value follows the system
// `prefers-color-scheme`, a choice made with the switch in the header is remembered in the browser.
import { createContext, useContext } from 'react'

export type ThemeMode = 'light' | 'dark'

export interface ThemeModeValue {
  mode: ThemeMode
  toggle: () => void
}

export const ThemeModeContext = createContext<ThemeModeValue | null>(null)

const STORAGE_KEY = 'vko-monitor.theme'

export function initialThemeMode(): ThemeMode {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    if (stored === 'light' || stored === 'dark') return stored
  } catch {
    // Storage may be blocked by the browser: fall back to the system preference.
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function rememberThemeMode(mode: ThemeMode): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, mode)
  } catch {
    // Not remembered: the next visit starts from the system preference again.
  }
}

export function useThemeMode(): ThemeModeValue {
  const value = useContext(ThemeModeContext)
  if (!value) throw new Error('useThemeMode is used outside ThemeModeProvider')
  return value
}
