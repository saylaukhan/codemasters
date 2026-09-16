# Панель «Мониторинг интернета ВКО»

React 18 + TypeScript + Vite. Refine, Ant Design 5, тема из токенов и `labels.ts` появятся в T-21;
клиент к API (`src/api/generated/*`) генерирует `make openapi` — T-03.

Команды (из корня репозитория — через `Makefile`):

```bash
make web-install   # npm ci
make web           # vite dev server на http://localhost:5173
make check-web     # npm run lint && npm run typecheck && npm run test && npm run build
```

Локально то же самое: `npm run dev`, `npm run lint`, `npm run typecheck`, `npm run test`,
`npm run build`. Docker-образ (`Dockerfile`) собирает бандл и отдаёт его через nginx на порту 80;
`/api/*` перед ним маршрутизирует Caddy (`deploy/Caddyfile`).
