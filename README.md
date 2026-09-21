# Мониторинг интернета ВКО

> `main` — стабильная, обновляет только лид перед демо или поставкой; `developing` — интеграционная, в неё вливаются задачи (ADR-001).
> Как включиться в работу — [CONTRIBUTING.md](CONTRIBUTING.md); задачи — [docs/tasks/README.md](docs/tasks/README.md).
> Архитектурные решения — [docs/architecture/decisions/README.md](docs/architecture/decisions/README.md); правила для ИИ-агентов — [AGENTS.md](AGENTS.md).
> Интерфейс панели — [DESIGN.md](DESIGN.md).

## Что это

Система автономного мониторинга качества интернет-соединения в организациях образования
Восточно-Казахстанской области (ТЗ п. 1, plan.md §3). Фоновый агент на школьном ПК — служба
без окон — сам замеряет Download, Upload, Ping, Jitter и Packet Loss 3–5 раз в день и по
HTTPS/TLS отправляет результаты в API, а тот сохраняет их в БД. Веб-панель показывает карту ВКО
со статусами школ, аналитику по школам, районам и провайдерам, инциденты, обращения провайдеру
с AI-черновиком письма и экспорт в XLSX, CSV и PDF.

Для кого: областной уровень, районный или городской отдел образования, школа, провайдер
(видит только свои линии) и администратор системы (ТЗ п. 16, plan.md §9).

## С чего начать

| Документ | Что там |
|---|---|
| [CONTRIBUTING.md](CONTRIBUTING.md) | как включиться: установка, ветки, коммиты, путь задачи до слияния |
| [docs/tasks/README.md](docs/tasks/README.md) | задачи T-01…T-58 со статусами, порядок внутри MVP, решения по умолчанию |
| [docs/architecture/decisions/README.md](docs/architecture/decisions/README.md) | ADR-001…014 — принятые решения и как добавить новое |
| [AGENTS.md](AGENTS.md) | правила для ИИ-агентов: что можно, что нельзя, инварианты из ТЗ |
| [DESIGN.md](DESIGN.md) | дизайн-код панели: токены, компоненты, состояния экранов |
| [docs/checklist.md](docs/checklist.md) | чек-лист — гейт перед слиянием в `developing` |
| [docs/worklog.md](docs/worklog.md) | отчёт по каждой слитой задаче |
| [docs/known-limitations.md](docs/known-limitations.md) | что заведомо не доделано — это не баг |
| [docs/architecture.md](docs/architecture.md) | как устроено приложение; пока заглушка — наполняет T-57 |
| [docs/product/tz.md](docs/product/tz.md) | ТЗ заказчика, 20 разделов — источник: из него выводятся задачи и ADR |
| [docs/product/plan.md](docs/product/plan.md) | план реализации §1–§16: стек, схема БД, API, статусы, инциденты, этапы |
| [docs/product/overview-slides.md](docs/product/overview-slides.md) | слайды: декомпозиция ТЗ и обзор системы |

## Стек

Кратко; полная таблица с обоснованием — plan.md §2, решение — ADR-002.

| Слой | Технология |
|---|---|
| Агент | Go 1.23, служба Windows (`kardianos/service`) и systemd на Linux, SQLite-очередь, установщики MSI (WiX v4) и `.deb` / `.rpm` (nfpm) |
| Замеры | свой LibreSpeed-сервер (основной) + ndt7 (резерв), оба в Казахстане |
| Backend | Python 3.12, FastAPI, SQLAlchemy 2 (async), Alembic, Pydantic v2 |
| Фоновые задачи | Redis + Celery (+ Celery Beat) |
| БД | PostgreSQL 16 + TimescaleDB + PostGIS |
| Панель | React 18 + TypeScript + Vite, Refine + Ant Design, TanStack Query |
| Карта и графики | MapLibre GL JS + GeoJSON районов ВКО; Apache ECharts |
| Экспорт и AI | openpyxl (XLSX), csv, WeasyPrint + Jinja2 (PDF); LLM через адаптер `LLMProvider` |
| Инфраструктура | Docker Compose, Caddy (TLS), GitHub Actions |
| Эксплуатация | pgBackRest (бэкап БД), Sentry, Prometheus + Grafana |

## Структура репозитория

Функции разложены по задачам `docs/tasks/README.md`; что в какой папке:

```text
agent/               Go — агент: служба Windows / systemd, замеры, очередь, MSI и пакет Linux
backend/             Python — FastAPI, модели, миграции Alembic, Celery, тесты
web/                 React + TypeScript + Vite — веб-панель
simulator/           симулятор агентов: 350 школ, 1000 ПК, 3 месяца истории
deploy/              Caddyfile, LibreSpeed (+ ndt7), pgBackRest, Prometheus, Grafana
docker-compose.yml   caddy, api, worker, beat, db, redis, web, speedtest, ndt7, prometheus, grafana
docker-compose.backup.yml  надстройка: архив WAL и ежедневный бэкап БД (deploy/pgbackrest/README.md)
Makefile             единая точка входа для команд
.github/workflows/   ci.yml (make check), agent-msi.yml (сборка MSI)
docs/                документация: задачи, ADR, чек-лист, worklog, ТЗ и план
```

Подпапки агента — plan.md §4.7; таблицы БД — plan.md §5; роутеры API — plan.md §10.

## Команды

Полный список — `make help`.

```bash
make up            # docker compose up -d db redis speedtest ndt7 — инфраструктура для разработки
make migrate       # alembic upgrade head
make seed          # справочники, GeoJSON районов ВКО, тестовые школы, dev-пользователи
make api           # uvicorn app.main:app --reload на http://localhost:8000 (Swagger: /api/docs)
make worker        # celery worker + beat
make web           # vite dev server на http://localhost:5173
make agent-run     # go run ./cmd/vko-agent run --config ./agent/dev.yaml (без установки службы)
make check         # ВСЁ: check-agent + check-backend + check-web — перед каждым слиянием
make backup        # разовый полный бэкап БД; восстановление — deploy/pgbackrest/README.md
```

Установка с нуля: `git clone git@github.com:saylaukhan/codemasters.git && cd codemasters && cp .env.example .env && make install && make up && make migrate && make seed`.
Нужны Go 1.23+, Python 3.12+ (uv или venv), Node.js 24, Docker Desktop, git. Полный список
целей — в AGENTS.md §7 (блок команд `make …`); dev-пользователи — в CONTRIBUTING.md §1.

## Ветки

- `main` — стабильная, всегда собирается; обновляет только лид слиянием из `developing` перед демо или поставкой.
- `developing` — интеграционная; в неё вливаются задачи.
- Рабочие ветки — от `developing`, латиницей, с номером задачи: `feature/t-08-scheduler-slots`.

Pull Request'ов нет. Гейт перед слиянием — [docs/checklist.md](docs/checklist.md) (включая
`make check`), отчёт — [docs/worklog.md](docs/worklog.md); в `developing` сливает человек
командой `git merge --no-ff` (ADR-001).

## Статус

Сентябрь 2026. Реализовано 55 задач из 58; все задачи волны MVP закрыты, кроме поставочных
(T-55, T-57, T-58). Работает сквозной путь данных: агент — служба Windows и systemd —
регистрируется по коду установки, замеряет по расписанию со случайным смещением, копит
результаты в SQLite-очереди при обрыве связи и дошлёт их сам; API принимает замеры, считает
статусы, ведёт инциденты с гистерезисом, уведомления, обращения провайдеру с AI-черновиком и
выгрузки; панель показывает карту ВКО, карточки школы и ПК, аналитику, инциденты, кабинет
провайдера и админку. Есть MSI-установщик, пакеты `.deb` и `.rpm`, самообновление агента,
ролевая модель с RLS и аудитом, экспорт в XLSX, CSV, JSON и PDF, резервное копирование БД и
наблюдаемость сервера.

Осталось: T-55 (симулятор агентов), T-56 (нагрузочный тест), T-57 (документация поставки)
и T-58 (сценарий демонстрации и контрольный прогон). До T-55 история замеров наполняется
только реальными агентами: `simulator/simulate.py` — заглушка из T-01.

Что заведомо не доделано — [docs/known-limitations.md](docs/known-limitations.md); статусы
задач (`todo | in-progress | done (дата)`) — в [docs/tasks/README.md](docs/tasks/README.md);
отчёт по каждой слитой задаче — [docs/worklog.md](docs/worklog.md).
