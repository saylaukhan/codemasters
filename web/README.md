# Панель «Мониторинг интернета ВКО»

React 18 + TypeScript + Vite, Refine поверх Ant Design 5 (ADR-013), дизайн — по `DESIGN.md`.
Типы API (`src/api/generated/schema.ts`) генерирует `make openapi` из `docs/reference/openapi.json`
через openapi-typescript (`npm run api:generate`); руками не правятся (ADR-009).

| Путь | Что там |
|---|---|
| `src/app/` | `App.tsx` (Refine, маршруты), провайдеры auth / data / прав, каркас (шапка, сайдбар), тема, `sections.ts` — разделы и нужные им права |
| `src/api/` | `client.ts` — запросы к `/api`, access-токен в памяти, refresh через cookie, ошибки problem+json; `case.ts` — snake_case ↔ camelCase; `types.ts` — имена для сгенерированных типов |
| `src/styles/` | `tokens.css` (CSS-переменные светлой и тёмной темы) и `theme.ts` (тема AntD) — единственные места с hex |
| `src/lib/` | `labels.ts` — статусы, роли, разделы по-русски; `format.ts` — числа и даты в Asia/Almaty |
| `src/components/ui/` | обёртки над AntD: `Button`, статус-бейджи, `PageHeader`, `EmptyState`, `ContentSkeleton`, `ErrorState` |
| `src/pages/` | `login/` — вход; `section/` — заглушка раздела, «Нет доступа», 404 |

В режиме разработки Vite проксирует `/api` на `http://localhost:8000` (`make api`), поэтому
refresh-cookie живёт на том же адресе, что и панель.

Команды (из корня репозитория — через `Makefile`):

```bash
make web-install   # npm ci
make web           # vite dev server на http://localhost:5173
make check-web     # api:check, lint, typecheck, test, build
```

Локально то же самое: `npm run dev`, `npm run api:check` (типы API совпадают с контрактом),
`npm run lint`, `npm run typecheck`, `npm run test`, `npm run build`. Docker-образ (`Dockerfile`)
собирает бандл и отдаёт его через nginx на порту 80; `/api/*` перед ним маршрутизирует Caddy
(`deploy/Caddyfile`).
