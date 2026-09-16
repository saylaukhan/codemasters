# Панель «Мониторинг интернета ВКО»

React 18 + TypeScript + Vite. Refine, Ant Design 5, тема из токенов и `labels.ts` появятся в T-21.
Типы API (`src/api/generated/schema.ts`) генерирует `make openapi` из `docs/reference/openapi.json`
через openapi-typescript (`npm run api:generate`); руками не правятся (ADR-009). HTTP-клиент и
перевод snake_case → camelCase поверх этих типов — `src/api/`, T-21.

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
