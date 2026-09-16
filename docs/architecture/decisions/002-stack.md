# ADR-002 · Стек

**Статус:** принято · **Дата:** 2026-09-16 · **Источник:** ТЗ п. 8, plan.md §2 и §1

## Контекст
ТЗ п. 8 оставляет выбор стека команде; обоснование нужно только для технологий вне перечисленных в нём,
а Go, FastAPI, React и PostgreSQL названы там явно. Ограничения задают другие пункты:
агент — фоновая служба без GUI (п. 2), интерактивная карта ВКО (п. 13), история и агрегаты за
длинные периоды (п. 5, п. 9), масштабирование (п. 3). Ближайший аналог Giga Meter (plan.md §1) —
оконное Electron-приложение, поэтому его клиент как образец не подходит; берём только идеи.

## Решение
- Агент: Go 1.23, служба Windows и systemd через `kardianos/service`, SQLite (`modernc.org/sqlite`,
  без CGO), установщик MSI (WiX v4). Служба — `VKOMonitorAgent`, файл — `VKO-Agent.msi`.
- Backend: Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2; фоновые задачи —
  Celery + Celery Beat на Redis.
- БД: PostgreSQL 16 + TimescaleDB (временные ряды, агрегаты) + PostGIS (геометрия районов и школ).
- Панель: React 18 + TypeScript + Vite, Refine + Ant Design 5, TanStack Query, ECharts, MapLibre GL JS.
- Замеры: свой LibreSpeed-сервер (основной) и ndt7 (резерв), оба в Казахстане — ADR-012.
- Инфраструктура: Docker Compose (`caddy`, `api`, `worker`, `beat`, `db`, `redis`, `web`,
  `speedtest`), Caddy для TLS, GitHub Actions (`ci.yml`, `agent-msi.yml`).
- Экспорт, уведомления, наблюдаемость — по таблице plan.md §2; обоснование каждой строки — там же.

## Последствия
- Три языка — три набора проверок: `make check-agent`, `make check-backend`, `make check-web`;
  `make check` запускает всё и обязателен перед слиянием (ADR-001).
- На машине разработчика нужны Go 1.23+, Python 3.12+, Node.js 24, Docker Desktop.
- Свой speedtest-движок, свои UI-компоненты и код Giga Meter (AGPL) не используем — ADR-010.
- Замена любого слоя (например, Refine на «голый» React) — новым ADR, а не внутри задачи.
- Кода пока нет: каркас с этими зависимостями появится в T-01.
