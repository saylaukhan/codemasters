import { useNotificationProvider } from '@refinedev/antd'
import { Authenticated, Refine, type ResourceProps } from '@refinedev/core'
import routerProvider, { CatchAllNavigate, DocumentTitleHandler } from '@refinedev/react-router'
import { BrowserRouter, Outlet, Route, Routes } from 'react-router'

import { APP_NAME } from '../lib/app-info'
import { SECTION_LABELS } from '../lib/labels'
import { LoginPage } from '../pages/login/LoginPage'
import { PasswordResetPage } from '../pages/login/PasswordResetPage'
import { LandingRoute } from '../pages/section/LandingRoute'
import { NotFoundPage } from '../pages/section/NotFoundPage'
import { SectionRoute } from '../pages/section/SectionRoute'
import { AppLayout } from './AppLayout'
import { accessControlProvider, authProvider } from './authProvider'
import { dataProvider } from './dataProvider'
import { SECTIONS } from './sections'
import { ThemeModeProvider } from './ThemeModeProvider'

const resources: ResourceProps[] = SECTIONS.map((section) => ({
  name: section.key,
  list: section.path,
  meta: { label: SECTION_LABELS[section.key] },
}))

const documentTitle = ({ resource }: { resource?: ResourceProps }): string =>
  resource?.meta?.label ? `${resource.meta.label} · ${APP_NAME}` : APP_NAME

/** Providers, Refine and routes of the panel (ADR-013). */
export function App() {
  return (
    <BrowserRouter>
      <ThemeModeProvider>
        <Refine
          authProvider={authProvider}
          dataProvider={dataProvider}
          accessControlProvider={accessControlProvider}
          routerProvider={routerProvider}
          notificationProvider={useNotificationProvider}
          resources={resources}
          options={{ syncWithLocation: true, disableTelemetry: true }}
        >
          <Routes>
            <Route
              element={
                <Authenticated key="panel" fallback={<CatchAllNavigate to="/login" />}>
                  <AppLayout>
                    <Outlet />
                  </AppLayout>
                </Authenticated>
              }
            >
              <Route index element={<LandingRoute />} />
              {SECTIONS.map((section) => (
                <Route key={section.key} path={`${section.path}/*`} element={<SectionRoute section={section} />} />
              ))}
              <Route path="*" element={<NotFoundPage />} />
            </Route>
            <Route
              element={
                <Authenticated key="login" fallback={<Outlet />}>
                  <LandingRoute />
                </Authenticated>
              }
            >
              <Route path="/login" element={<LoginPage />} />
            </Route>
            {/* Ссылка из письма открывается и в браузере, где ещё жива старая сессия. */}
            <Route path="/password-reset" element={<PasswordResetPage />} />
          </Routes>
          <DocumentTitleHandler handler={documentTitle} />
        </Refine>
      </ThemeModeProvider>
    </BrowserRouter>
  )
}
