import { App as AntdApp, ConfigProvider } from 'antd'
import ruRU from 'antd/locale/ru_RU'
import dayjs from 'dayjs'
import 'dayjs/locale/ru'
import { useCallback, useLayoutEffect, useMemo, useState, type PropsWithChildren } from 'react'

import { PHONE_SCREEN, darkTheme, lightTheme } from '../styles/theme'
import { ThemeModeContext, initialThemeMode, rememberThemeMode, type ThemeMode } from './themeMode'
import { useMediaQuery } from './useMediaQuery'

dayjs.locale('ru')

/** AntD theme and `data-theme` on <html> switch together, so tokens.css follows the same mode. */
export function ThemeModeProvider({ children }: PropsWithChildren) {
  const [mode, setMode] = useState<ThemeMode>(initialThemeMode)
  // DESIGN.md §9.3: at 768px and narrower every AntD control is 44px tall — one size here instead
  // of a `size` prop on every call site.
  const phone = useMediaQuery(PHONE_SCREEN)

  // Before paint: the page never flashes the other theme.
  useLayoutEffect(() => {
    document.documentElement.dataset.theme = mode
  }, [mode])

  const toggle = useCallback(() => {
    setMode((current) => {
      const next = current === 'dark' ? 'light' : 'dark'
      rememberThemeMode(next)
      return next
    })
  }, [])

  const value = useMemo(() => ({ mode, toggle }), [mode, toggle])

  return (
    <ThemeModeContext.Provider value={value}>
      <ConfigProvider
        theme={mode === 'dark' ? darkTheme : lightTheme}
        locale={ruRU}
        componentSize={phone ? 'large' : 'middle'}
      >
        <AntdApp>{children}</AntdApp>
      </ConfigProvider>
    </ThemeModeContext.Provider>
  )
}
