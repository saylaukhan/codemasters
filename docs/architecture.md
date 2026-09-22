# Архитектура

Как система устроена **по факту кода** на ветке `developing` (задачи T-01…T-54 влиты). Где
код и план расходятся, здесь написан код; план — `docs/product/plan.md`, решения —
`docs/architecture/decisions/`.

Смежные документы: инструкция администратора — `docs/product/admin-guide.md`, установка
агента — `docs/product/agent-install.md`, контракт API — `docs/reference/openapi.json`
(в PDF — `make api-pdf`).

---

## 1. Из чего состоит система

| Часть | Где | Что делает |
|---|---|---|
| Агент | `agent/` (Go 1.23, без CGO) | служба на компьютере школы: замеряет по расписанию с сервера, копит в SQLite, досылает |
| Сервер | `backend/` (FastAPI, SQLAlchemy 2, Celery) | принимает замеры, считает статусы, ведёт инциденты, отдаёт API панели |
| Панель | `web/` (React 18, Ant Design 5, Refine, MapLibre, ECharts) | карта, карточки школ, аналитика, инциденты, обращения, админка |
| Инфраструктура | `docker-compose.yml`, `deploy/` | PostgreSQL 16 + TimescaleDB + PostGIS, Redis, серверы замеров, Caddy, Prometheus, Grafana |

Границы: агент не знает ни порогов, ни расписания, ни адреса сервера замеров — всё приходит
с сервера (`GET /api/agent/config`, ADR-012). Панель не считает статусы — она их показывает
(ADR-004). Считает сервер.

## 2. Процессы в проде

`docker compose up -d` поднимает 11 сервисов (`docker-compose.yml`). Для разработки нужны не
все: `make up` — только `db`, `redis`, `speedtest`, `ndt7`, остальное на хосте.

| Сервис | Образ | Порт | За что отвечает |
|---|---|---|---|
| `db` | `timescale/timescaledb-ha:pg16` | `127.0.0.1:5432` | PostgreSQL 16 + TimescaleDB + PostGIS; том `pgdata` |
| `redis` | `redis:7-alpine` | `127.0.0.1:6379` | брокер и backend Celery, счётчик лимита запросов агентов |
| `speedtest` | `ghcr.io/librespeed/speedtest:6.3.0` | `8080` | LibreSpeed — основной сервер замера скорости |
| `ndt7` | `measurementlab/ndt-server:v0.25.3` | `8081` | ndt7 — резерв, когда LibreSpeed не ответил |
| `api` | сборка `./backend` | `8000` | uvicorn `app.main:app` |
| `worker` | тот же образ | — | `celery -A app.workers.celery_app worker` |
| `beat` | тот же образ | — | `celery -A app.workers.celery_app beat` — расписание фоновых задач |
| `web` | сборка `./web` | `5173:80` | собранный SPA под nginx (`web/nginx.conf`) |
| `caddy` | `caddy:2-alpine` | `80`, `443` | TLS и реверс-прокси перед API и панелью |
| `prometheus` | `prom/prometheus:v3.1.0` | не публикуется | метрики самого сервера, хранение 30 дней |
| `grafana` | `grafana/grafana:11.4.0` | `127.0.0.1:3000` | дашборд «Сервер мониторинга ВКО» |

`api`, `worker` и `beat` — один образ `vko-monitor-backend` и один якорь `x-backend` в compose:
общий `.env`, `DATABASE_URL` и `REDIS_URL` переопределены на хосты `db` и `redis`, старт по
healthcheck базы и Redis.

Caddy наружу отдаёт только два маршрута (`deploy/Caddyfile`): `/api/*` → `api:8000`, всё
остальное → `web:80`. `GET /metrics` за Caddy не публикуется. Сертификат автоматический:
реальный домен в `CADDY_DOMAIN` — Let's Encrypt, `localhost` — самоподписанный.

Замеры — исключение: `speedtest` и `ndt7` слушают снаружи напрямую, по `http://` и `ws://`,
без TLS и не через Caddy. Это зафиксированное ограничение, а не забытая настройка —
`docs/known-limitations.md`.

## 3. Путь замера: от компьютера школы до карты

1. **Расписание.** `agent/internal/scheduler` выбирает слот и случайное смещение внутри него.
   После старта службы или выхода компьютера из сна догоняющий замер откладывается на
   случайные 1–15 минут (`catchUpMin`, `catchUpMax`): сеть могла ещё не подняться, а
   включённые вместе компьютеры школы не должны замерять одновременно.
2. **Замер.** `probe` — связь, ping, jitter, packet loss; `speed` — Download и Upload через
   LibreSpeed, при отказе через ndt7; `netinfo` — тип адаптера (ethernet, wifi, other).
3. **Очередь.** Результат пишется в SQLite `queue.db` **до** отправки. Запись удаляется только
   после ответа сервера `201` или `409` по `measurement_uuid`, поэтому обрыв связи и
   перезагрузка не теряют ничего (`agent/internal/queue`, ADR-006). Пределов очереди два:
   число записей — 10 000 (`MaxRecords`), а срок хранения приходит с сервера в
   `queue_retention_days` конфигурации (`Queue.SetMaxAge`); `queue.DefaultMaxAge` — 30 суток —
   работает только до первой конфигурации. Тот же срок задаёт, насколько старый замер примет
   сервер: настройка «Срок очереди агента, дней» в админке (ТЗ п. 11, п. 20; ADR-004).
4. **Отправка.** `POST /api/measurements` или `POST /api/measurements/batch` с заголовком
   `Authorization: Device <token>`. Токен — `<device_id>.<32 случайных байта>`
   (`backend/app/core/security.py`). Перед маршрутизацией запрос проходит
   `RateLimitMiddleware` (`app/core/ratelimit.py`).
5. **Приём.** `backend/app/api/agent.py` достаёт устройство из токена: нет токена — 401,
   заблокировано — 403. **School ID и линия берутся из привязки устройства, а не из тела
   запроса, никогда** (ТЗ п. 12, ADR-005).
6. **Статус замера.** `backend/app/services/status.py` сравнивает значения с порогами линии и
   кладёт применённые пороги в `thresholds_snapshot` самой записи. Поэтому поздняя правка
   профиля не переписывает историю, и спор с поставщиком решается одной строкой замера
   (ТЗ п. 11, ADR-004).
7. **Статус школы.** Тот же сервис сворачивает последние N замеров основной линии (по
   умолчанию 3, Wi‑Fi не в счёт) в статус школы. Молчание heartbeat дольше `offline_after_s`
   в рабочие часы — «Нет соединения», вне рабочих часов — «Нет данных»: выключенный на ночь
   компьютер не поломка линии (ADR-014).
8. **Инциденты.** API ставит в очередь `incidents.detect_line`; beat каждые 5 минут гоняет
   `incidents.detect_all`. Инцидент не заводится по единичному отклонению — только по N
   подряд или по длительности (ADR-007). Каждый переход статуса пишется в `incident_events`,
   каждая попытка уведомления — в `notification_log`.
9. **Панель.** Читает `GET /api/map/schools`, `GET /api/dashboard/summary` и остальное через
   JWT → `require(permission)` → RLS.

Нет связи — факт фиксируется локально (`POST /api/outages` после восстановления), очередь
досылается сама; дыра в данных закрывается без ручных действий.

## 4. База данных

35 моделей, одна таблица — один файл (`backend/app/models/`). Крупными блоками:

| Блок | Таблицы |
|---|---|
| Справочники и объекты | `regions`, `providers`, `connection_types`, `schools`, `school_contacts`, `lines`, `monitoring_points` |
| Устройства | `devices`, `enrollment_codes`, `agent_releases` |
| Временные ряды | `measurements`, `heartbeats`, `outages`, `m_hourly`, `m_daily` |
| Настройки мониторинга | `settings`, `threshold_profiles`, `schedules`, `incident_rules` |
| Инциденты и уведомления | `incidents`, `incident_events`, `notifications`, `notification_log` |
| Обращения и выгрузки | `appeals`, `appeal_events`, `appeal_templates`, `exports` |
| Доступ и журнал | `users`, `roles`, `user_scopes`, `audit_log` |

TimescaleDB по факту: гипертаблицы — `measurements` (по `measured_at`) и `heartbeats` (по
`ts`); непрерывные агрегаты — `m_hourly` (час) и `m_daily` (сутки) с политиками обновления;
границы часов и суток считаются в `Asia/Almaty`, хранение всегда UTC (ADR-014). Плюс
агрегаты «ниже договора» (`20260918_0330_aggregates_below_contract.py`).

Миграции — 34 ревизии в `backend/alembic/versions/`, **forward-only**: `downgrade()` кидает
`NotImplementedError`, ошибка исправляется новой ревизией (ADR-003). Порядок задаёт цепочка
`down_revision`, а не имя файла.

Договорные значения линии хранятся отдельно от порогов и сравниваются с фактом наравне с
ними (ТЗ п. 11, п. 14); устойчивое несоответствие считает фоновая задача. Заносятся они руками в
карточке школы или импортом реестра договоров (CSV/XLSX → `POST /api/admin/contracts/import`,
`app/services/contract_import.py`); импорт пишет в те же поля `lines` и оставляет одну запись
`audit_log` с действием `import`.

Правила инцидентов и шаблоны писем поставщику — тоже данные, а не код (ADR-018): правило
`incident_rules` бывает для всей области или одной школы (правило школы заменяет глобальное по тому же
показателю для её линий), а письмо обращения или претензии пишется моделью по шаблону
`appeal_templates`, который сервер заполняет фактами (`app/services/appeals/template.py`).

## 5. Права: JWT → require → RLS

Три разных слоя, и ни один не заменяет другой.

1. **Кто пришёл.** `app/auth/deps.py`: `current_user` разбирает `Authorization: Bearer <jwt>`
   и **читает строку пользователя на каждом запросе** — поэтому блокировка и выход
   действуют сразу, а не когда истекут 15 минут токена.
2. **Что ему можно.** `require("<permission>")` сверяет право с матрицей
   `app/auth/permissions.py`. Роли: `school`, `district`, `provider`, `oblast`, `admin`.
   Провайдер не получает `contacts:phone` — телефон ответственного ему не виден (ТЗ п. 15).
   Панель получает список прав из `GET /api/auth/me` только чтобы прятать недоступное;
   решает всё равно сервер.
3. **Какие строки он увидит.** `app/auth/rls.py` на каждой транзакции запроса делает
   `SET LOCAL ROLE vko_panel`, `SET LOCAL app.user_scope` и `SET LOCAL app.user_id`. Область
   видимости: `all` для области и администратора, `region:<id>`, `provider:<id>`,
   `school:<id>`; пустая строка — не видно ничего. RLS включён на девяти таблицах
   (`schools`, `school_contacts`, `enrollment_codes`, `lines`, `monitoring_points`,
   `outages`, `measurements`, `devices`, `heartbeats`), политики — в миграции
   `20260918_1510_row_level_security.py`.

Запросы агента, логин и middleware аудита идут от владельца таблиц, вне области видимости —
им RLS не нужен и мешал бы. Celery тоже работает вне области (ADR-008).

`AuditMiddleware` (`app/auth/audit.py`) пишет в `audit_log` изменяющие действия и отказы
агентам. Блокировка учётной записи и устройства историю не удаляет (ТЗ п. 16, п. 20).

## 6. Фоновые задачи

`backend/app/workers/celery_app.py`: брокер и backend — Redis, `enable_utc=True`, пояс из
`TZ`. Расписание beat по факту — четыре записи:

| Задача | Как часто | Зачем |
|---|---|---|
| `contracts.recompute_compliance` | 15 мин | устойчивое несоответствие договору за окно (ТЗ п. 14) |
| `incidents.detect_all` | 5 мин | молчание heartbeat меряется против 15 минут `offline_after_s` |
| `incidents.close_resolved` | 15 мин | «Устранён» → «Закрыт» через 24 часа |
| `exports.purge_expired` | 1 час | файлы выгрузок живут 7 дней |

Кроме них по событию ставятся `incidents.detect_line` (после замера) и `exports.build`
(выгрузка больше 10 000 строк или PDF). Уведомления пишет одна функция —
`notify_incident` в `app/services/notifications.py`: и строку в `notifications` для панели, и
строку в `notification_log` на каждую попытку канала (ТЗ п. 18; ADR-007). Вызывают её два
воркера: `tasks/incidents.py` — на открытие, восстановление и авто-закрытие инцидента, и
`tasks/notifications.py` (задача `notify_incident_task`) — на смену статуса руками, которую
ставит в очередь `app/api/incidents.py`.

Каждая задача открывает свой async-engine с `NullPool`: `asyncio.run` — это новый цикл
событий, переиспользовать пул между ними нельзя.

## 7. Контракт API

Один источник — схема приложения. `make openapi` экспортирует её в
`docs/reference/openapi.json` (`app/openapi_export.py`) и тут же генерирует типы панели
`web/src/api/generated` (`npm run api:generate`). Руками ни то, ни другое не правится
(ADR-009); свежесть проверяет `npm run api:check` внутри `make check-web`, поэтому
разойтись контракт и клиент не могут — сборка панели упадёт.

Живая справка — Swagger на `/api/docs`, схема — `/api/openapi.json`. Для поставки тот же
контракт собирается в PDF: `make api-pdf` → `docs/reference/api.pdf`
(`backend/app/openapi_pdf.py`).

Сейчас в контракте 98 путей, 124 операции, 236 схем, 16 тегов. Ошибки у всех операций
одинаковые — `application/problem+json` (RFC 9457, ADR-009), схемы `Problem` и
`ValidationProblem`; формат собирает `app/core/openapi.py`.

Важное про контракт: право, которое проверяет `require(...)`, **в OpenAPI не попадает** — оно
живёт только в `app/auth/permissions.py`. В контракте видно схему доступа (`DeviceToken`,
`BearerAuth`, `RefreshCookie`), но не код права.

## 8. Наблюдаемость и бэкапы

`backend/app/core/observability.py` (T-54):

- **Sentry** стартует только при непустом `SENTRY_DSN`, `send_default_pii=False`, тег
  `component` = `api` или `worker`. Пустой DSN — нормальный режим, приложение работает молча.
- **Метрики**: `vko_http_requests_total`, `vko_http_request_duration_seconds`,
  `vko_celery_tasks_total`, `vko_celery_task_duration_seconds`. Путь помечается **шаблоном**
  маршрута (`/api/schools/{school_id}`), а не адресом — иначе на 350 школах взорвалась бы
  кардинальность.
- Воркер отдаёт метрики на `WORKER_METRICS_PORT` (9808) внутри сети compose; Prometheus
  собирает их каждые 30 с (`deploy/prometheus/prometheus.yml`), дашборд —
  `deploy/grafana/dashboards/server-health.json`.

Это метрики **сервера**, а не качества интернета школ: качество живёт в `measurements`.

Бэкапы — pgBackRest, отдельной надстройкой `docker-compose.backup.yml`: полный бэкап раз в
сутки плюс непрерывный архив WAL, значит восстановление на любую минуту. Отдельным файлом
потому, что `archive_mode=on` без забирающего WAL контейнера молча забьёт диск. Включение,
проверка и пошаговое восстановление — `deploy/pgbackrest/README.md`.

## 9. Развёртывание

Разработка: `cp .env.example .env` → `make install` → `make up` → `make migrate` → `make seed`;
дальше `make api`, `make worker`, `make web` на хосте. Полный стек за Caddy:
`docker compose up -d`. Пошагово с ожидаемым выводом — `docs/product/admin-guide.md`.

Агент ставится отдельно: Windows — `VKO-Agent.msi` (WiX v4, служба `VKOMonitorAgent`),
Linux — `.deb` и `.rpm` (systemd, `vko-agent.service`). Обе сборки только в CI
(`.github/workflows/agent-msi.yml`, `agent-linux.yml`). Инструкция —
`docs/product/agent-install.md`.

Всё, что настраивается без пересборки, настраивается в админке: пороги, расписания, правила
инцидентов, адреса серверов замеров, справочники (ТЗ п. 11, п. 20; ADR-004, ADR-012). В код
эти значения не зашиты нигде — ни в агенте, ни в панели.
