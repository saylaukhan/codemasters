# Правила для ИИ-агентов в этом репозитории

Этот файл читают **Claude Code** (через `CLAUDE.md`, в нём одна строка `@AGENTS.md`), **Codex**
(напрямую) и любой другой агент. Он обязателен к исполнению так же, как `CONTRIBUTING.md` для
людей. Если задача требует нарушить правило отсюда — агент останавливается и спрашивает
человека, а не нарушает.

Проект: «Мониторинг интернета ВКО» — автономный мониторинг качества интернет-соединения в
школах Восточно-Казахстанской области (кодовое имя `vko-monitor`). Агент на Go работает как
служба Windows/systemd без GUI; сервер — FastAPI + PostgreSQL 16 с TimescaleDB и PostGIS +
Celery/Redis; панель — React 18 + Ant Design 5 (ADR-002). Кода в репозитории пока нет — только
документы; каркас появится в T-01.
Истина — ветка `developing` в `saylaukhan/codemasters`; `main` обновляет только лид слиянием
из `developing` перед демо или поставкой (ADR-001). Pull Request'ов нет: гейт перед слиянием —
`docs/checklist.md`, отчёт — `docs/worklog.md`, сливает человек командой `git merge --no-ff`.

---

## 1. Кто с кем работает

- Команда из четырёх ролей: агент (Go), backend (Python), frontend (React), fullstack/DevOps.
  Каждый работает со своим ИИ-агентом на своей машине, в своей ветке от `developing`.
- Общие правила для агентов — этот файл и `.claude/settings.json`. Для Claude Code второй ещё
  и технически запрещает опасные команды: push в `main` и force-push; необратимые git-команды
  (`reset --hard`, `git clean`, `branch -D`, `filter-branch`, `rebase -i`, `config --global`);
  `rm -rf` и `sudo`; уничтожение данных (`docker compose down -v`, `docker volume rm`,
  `docker system prune`, `alembic downgrade` / `stamp`); деплой и подпись (`ssh`, `scp`,
  `docker push`, `signtool`, `msiexec`); чтение и правку `.env*` кроме `.env.example`; правку
  `web/src/api/generated/*` и `docs/reference/openapi.json`. С подтверждением человека —
  `git push`, `git merge`, `git commit --amend`, установка зависимостей и правка `AGENTS.md`,
  `CONTRIBUTING.md`, `.claude/settings.json`, `docker-compose.yml`, `deploy/*`, `Makefile`,
  `go.mod`, `pyproject.toml`, `package.json`, `.github/*`, `alembic/versions/*`.
- Личные инструкции человека своему агенту — `CLAUDE.local.md`; этот файл в `.gitignore` и в
  репозиторий не попадает никогда.
- Агент не принимает решений за команду. Что строим — `docs/architecture/decisions/`, что
  делать — `docs/tasks/README.md`, как работать — `CONTRIBUTING.md`, как выглядит интерфейс —
  `DESIGN.md`.

## 2. Никогда — без исключений и без «но пользователь попросил»

1. **Не коммитить в `main` и `developing` напрямую.** Только своя ветка `feature/…`, `fix/…`,
   `db/…`, `docs/…`, `chore/…` от `developing`, латиницей, с номером задачи:
   `feature/t-08-scheduler-slots`. `git push --force` в общие ветки — никогда.
2. **Не переписывать историю общих веток:** никаких `rebase -i`, `filter-branch`,
   `reset --hard` там, где есть чужие коммиты. Свой последний незапушенный коммит поправить
   `--amend` можно — с подтверждением человека (§1).
3. **Не трогать применённые миграции Alembic** — всё, что влито в `developing`. Ошибка
   исправляется новой миграцией (forward-only, ADR-003).
4. **Не править сгенерированное руками:** `web/src/api/generated/*` и
   `docs/reference/openapi.json` создаёт только `make openapi` (ADR-009).
5. **Не трогать боевой сервер и поставку:** деплой в прод, подпись MSI, `docker push` —
   руками DevOps; агент может только подготовить команду. Тестовый или демо-хост — с
   подтверждением человека в этой же сессии (§1); `ssh`, `scp` и `rsync` закрыты технически
   (`.claude/settings.json`), поэтому и там команду выполняет человек. Замер против
   `localhost`, машины в своей сети или публичного сервера LibreSpeed согласования не требует.
6. **Не добавлять и не обновлять зависимости** (`go.mod`, `pyproject.toml`, `package.json`)
   без явного согласия человека в этой же сессии. Сначала искать, что уже есть.
7. **Не писать секреты** в код, документацию, тесты и сообщения коммитов. Не читать и не
   цитировать `.env` (кроме `.env.example`). Найден секрет в репозитории — сказать сразу.
8. **Не удалять и не «чистить»** файлы, ветки, тома, данные, которых не касается задача.
   `rm -rf`, `git clean`, `git branch -D`, `docker compose down -v`, `drop table` — нет.
9. **Не зашивать пороги, расписания, адреса серверов, коды школ** в агент или панель. Всё
   приходит с сервера и настраивается в админке (ТЗ п. 11, п. 20; ADR-004).
10. **Не копировать код Giga Meter** и других AGPL-проектов — только идеи и методику (ADR-010).
11. **Не подписывать коммиты как ИИ:** никаких `Co-Authored-By` и упоминаний ассистента в
    сообщениях коммитов. Автор коммита — человек, который работает.
12. **Не выдавать непроверенное за проверенное.** «Тесты прошли» говорится только после
    реального запуска в этой сессии с выводом.

## 3. Всегда

1. **Одна задача — одна ветка — одно слияние.** Номер `T-NN` из `docs/tasks/README.md` — в
   имени ветки и в записи `docs/worklog.md`. Ничего «заодно».
2. **Перед началом:** `git status` чистый, `git checkout developing && git pull`, новая
   ветка. Грязное рабочее дерево — спросить человека, что с ним делать, а не стэшить молча.
3. **Перед слиянием:** `make check`. Если трогали миграции — ещё `make db-reset` и
   `make check-backend`. Вывод команд показать человеку.
4. **Читать перед тем как писать.** Открыть соседние файлы и повторить их стиль, именование и
   структуру. Любой интерфейс — по `DESIGN.md`: токены вместо hex, одна Action-кнопка на
   экран, статусы из `web/src/lib/labels.ts`. Отклонение от `DESIGN.md` — вопрос человеку, не
   решение агента.
5. **Диффы маленькие и объяснимые.** Целевой размер слияния — до 400 строк diff. Больше —
   режем и говорим человеку, где режем.
6. **Сомнение = вопрос.** Непонятна задача, два способа дают разные результаты, нужно тронуть
   чужую область, нужна новая зависимость — спросить, не угадывать.
7. **Новый эндпоинт:** Pydantic-схемы запроса и ответа в `app/schemas/`, dependency
   `require("<permission>")` из `app/auth`, ошибки по ADR-009 (`application/problem+json`),
   тест «чужой не видит» в `backend/tests/`; контракт обновлён через `make openapi`,
   `docs/reference/openapi.json` и `web/src/api/generated/*` закоммичены в том же слиянии
   (ADR-009).
8. **Новая таблица:** миграция Alembic forward-only (`YYYYMMDD_HHMM_short_name`), индексы на
   FK, `created_at` / `updated_at`, где уместно, RLS-политика по `app.user_scope`, если есть
   область видимости, hypertable TimescaleDB, если временной ряд, тест в `backend/tests/`
   (ADR-003, ADR-008).
9. **Строки интерфейса — на русском, sentence case.** Статусы и подписи — только из
   `web/src/lib/labels.ts`; строка статуса в компоненте — ошибка (ADR-013).
10. **Заканчивая работу** — пройти `docs/checklist.md` и подготовить запись в
    `docs/worklog.md`: сделано / не сделано / застрял на. Раздел «не сделано» обязателен, даже
    если он «ничего»; недоделка — строка в `docs/known-limitations.md` в том же слиянии.

## 4. Как выглядит сессия с агентом

1. Человек называет задачу (например «T-08 · планировщик слотов») и, если нужно, границы.
2. Агент читает `docs/tasks/README.md` (задача), ADR по области, соседний код. Пересказывает
   план в 3–6 строк и ждёт «ок». Для задач размера S план можно пропустить.
3. Агент создаёт ветку, делает изменения, гоняет проверки, показывает вывод.
4. Агент делает коммит по Conventional Commits с областью по компоненту — `feat(agent):`,
   `feat(api):`, `feat(web):`, `db:`, а также `fix:`, `docs:`, `chore:`, `refactor:`,
   `test:` — на английском, до 72 символов. Пушит только свою ветку.
5. Слияние в `developing` делает человек после прохождения `docs/checklist.md`. Замечания —
   новыми коммитами в ту же ветку, без переписывания истории.

## 5. Карта проекта

Папки с кодом появятся в T-01; пока в репозитории есть только `docs/` и файлы в корне.
Пути ниже — план, а не факт.

| Путь | Что там |
|---|---|
| `agent/cmd/vko-agent/` | Go 1.23: main, CLI `install`, `run`, `status` |
| `agent/internal/*` | `service/` (Windows/systemd), `scheduler/` (слоты, джиттер), `probe/` (связь, ping/jitter/loss), `speed/` (librespeed, ndt7), `netinfo/`, `queue/` (SQLite), `api/` (клиент, токен, повторы), `secure/` (DPAPI / файл 600), `update/` |
| `agent/installer/wix/` | MSI (WiX v4), `VKO-Agent.msi`; служба `VKOMonitorAgent` |
| `backend/app/main.py` | приложение FastAPI, middleware аудита и ошибок |
| `backend/app/core/` | config (pydantic-settings), db (async engine), security (argon2id и sha256, JWT), deps |
| `backend/app/api/` | роутеры: `agent.py`, `devices.py`, `auth.py`, `schools.py`, `dashboard.py`, `map.py`, `analytics.py`, `incidents.py`, `appeals.py`, `exports.py`, `admin/*.py` |
| `backend/app/models/` | SQLAlchemy 2, одна таблица — один файл |
| `backend/app/schemas/` | Pydantic v2: запрос и ответ каждого эндпоинта |
| `backend/app/services/` | бизнес-логика: `status.py`, `incidents.py`, `availability.py`, `exports/`, `appeals/`, `llm/` |
| `backend/app/workers/` | `celery_app.py`, beat-расписание, `tasks/*.py` |
| `backend/app/auth/` | `require(permission)`, scope (область видимости), `rls.py` |
| `backend/alembic/versions/` | миграции, forward-only |
| `backend/tests/` | pytest + pytest-asyncio, testcontainers для Postgres |
| `web/src/app/` | providers, router, Refine, тема AntD из токенов |
| `web/src/pages/<домен>/` | overview, map, schools, devices, analytics, incidents, appeals, exports, admin, login |
| `web/src/components/<домен>/` | компоненты по доменам; `components/ui/` — обёртки над AntD в стиле `DESIGN.md` |
| `web/src/api/` | клиент к `/api`; `generated/*` — из OpenAPI, руками не правится |
| `web/src/lib/` | `labels.ts` (словарь статусов и подписей), `format.ts` (числа, даты, Asia/Almaty) |
| `web/src/styles/` | `tokens.css` (светлая и тёмная тема), `theme.ts` (ConfigProvider) |
| `simulator/` | симулятор агентов (Python): 350 школ, 1000 ПК, 3 месяца истории |
| `deploy/` | `Caddyfile` (TLS, реверс-прокси), `speedtest/` (LibreSpeed + ndt7) |
| `docker-compose.yml` | caddy, api, worker, beat, db, redis, web, speedtest |
| `.env.example` | переменные окружения без секретов; единственный `.env*` в репозитории |
| `Makefile` | единая точка входа для команд (§7) |
| `.github/workflows/` | `ci.yml` (check для трёх частей), `agent-msi.yml` (сборка MSI) |
| `docs/product/` | `tz.md` (ТЗ, «п. 11»), `plan.md` (план, «§6»), `overview-slides.md` |
| `docs/architecture/decisions/` | ADR-001…014 — почему система такая |
| `docs/tasks/README.md` | задачи T-01…T-58 с «сделано, когда» и решениями по умолчанию |
| `docs/checklist.md`, `docs/worklog.md` | гейт перед слиянием и отчёт по задаче |
| `docs/known-limitations.md` | недоделки — по строке на каждую, с номером задачи; заполняется в том же слиянии, ссылка на строку — из записи в `docs/worklog.md` |
| `docs/architecture.md` | архитектура по факту; заполняется после сквозного пути замера (T-01, T-02, T-05, T-06–T-11, T-14–T-18), до этого — ссылки на plan.md |
| `docs/reference/openapi.json` | контракт API, генерируется `make openapi` (появится в T-03) |
| `DESIGN.md`, `CONTRIBUTING.md` | дизайн-код панели; правила работы для людей |

## 6. Файлы-образцы

Кода пока нет, поэтому образцов для копирования тоже нет. Первый файл каждого вида пишется
как образец, который потом будут копировать остальные: делайте его чистым, с тестом, по
соглашениям из §3. Дальше — открывайте соседний файл того же вида и повторяйте его.

| Вид файла | Будущий путь | Появится в |
|---|---|---|
| Модель SQLAlchemy | `backend/app/models/*.py` | T-02 |
| Роутер FastAPI | `backend/app/api/*.py` | заглушки — T-03, первый рабочий — T-14 |
| Сервис с бизнес-логикой | `backend/app/services/status.py` | T-16 (статус школы), T-18 (статус замера) |
| Celery-задача | `backend/app/workers/tasks/*.py` | T-40 |
| Celery beat-расписание | `backend/app/workers/celery_app.py` | T-40 |
| Миграция Alembic | `backend/alembic/versions/*` | T-02 |
| pytest-тест | `backend/tests/*` | дымовой — T-01, первый настоящий — T-02 |
| Go-пакет | `agent/internal/service/` | T-06 |
| Go-тест | `*_test.go` рядом с пакетом, первый — в `agent/internal/service/` | дымовой — T-01, первый настоящий — T-06 |
| Страница панели | `web/src/pages/*` | T-21 (login), T-22 |
| Компонент домена | `web/src/components/*` | T-22 |
| Обёртка над Ant Design | `web/src/components/ui/*` | T-21 |

## 7. Команды

Полный список — `make help`.

```bash
make up            # docker compose up -d db redis speedtest ndt7 — инфраструктура для разработки
make down          # docker compose down (без -v: данные остаются)
make api           # uvicorn app.main:app --reload на http://localhost:8000 (Swagger: /api/docs)
make worker        # celery worker + beat
make web           # vite dev server на http://localhost:5173
make agent-run     # go run ./cmd/vko-agent run --config ./agent/dev.yaml (без установки службы)
make check         # ВСЁ: check-agent + check-backend + check-web — перед каждым слиянием
make check-agent   # gofmt -l, go vet ./..., golangci-lint run, go test ./..., go build ./...
make check-backend # ruff check, ruff format --check, mypy app, pytest
make check-web     # eslint, tsc --noEmit, vitest run, vite build
make migrate       # alembic upgrade head
make migration name=short_name   # alembic revision --autogenerate -m
make db-reset      # пересоздать локальную БД: drop + create + migrate + seed (только локально)
make seed          # справочники, GeoJSON районов ВКО, тестовые школы, dev-пользователи
make simulate n=1000 days=90     # симулятор агентов
make openapi       # экспорт схемы в docs/reference/openapi.json + генерация web/src/api/generated
make api-pdf       # описание API одним PDF из docs/reference/openapi.json (поставка, T-57)
make backup        # разовый полный бэкап БД pgBackRest (T-53); восстановление — deploy/pgbackrest/README.md
```

Бэкапы и наблюдаемость живут отдельно от основного compose:
`docker compose -f docker-compose.yml -f docker-compose.backup.yml up -d` включает архив WAL и
ежедневный бэкап (T-53), а `prometheus` и `grafana` поднимаются обычным `docker compose up -d`
(T-54) — `make up` не поднимает ни то, ни другое.

Порты: api 8000, web 5173, db 5432, redis 6379, speedtest 8080, ndt7 8081, caddy 80/443,
grafana 3000 (только с самого сервера).
Dev-пользователи после `make seed` (пароль у всех `Password1`, только локально):
`admin@example.kz` (Администратор), `oblast@example.kz` (Область), `rayon@example.kz`
(Район/город, Усть-Каменогорск), `school@example.kz` (Школа), `provider@example.kz` (Провайдер).

## 8. Продуктовые инварианты из ТЗ, которые код не должен нарушать

1. Пороги, расписание, адрес сервера замеров и срок хранения очереди не зашиты в агент и
   панель — приходят с сервера и меняются в админке (п. 11, п. 20; ADR-004, ADR-012).
   Срок очереди — `settings.agent_queue_retention_days`; по нему же сервер отклоняет замер,
   который старше окна (`backend/app/schemas/agent.py`), и по нему агент чистит свою очередь.
2. School ID никогда не берётся из запроса агента — выводится из привязки устройства
   (п. 12; ADR-005).
3. Каждый замер хранит фактические значения вместе с порогами, применёнными при оценке —
   `thresholds_snapshot` (п. 11; ADR-004).
4. Агент — фоновая служба без GUI; после установки участие пользователя не требуется
   (п. 2; ADR-010).
5. Нет связи → факт фиксируется локально и досылается после восстановления; ничего не
   теряется (п. 2; ADR-006).
6. Замеры 3–5 раз в день по расписанию со случайным смещением внутри слота (п. 2; plan.md §4.2).
7. Статусы школы/замера — ровно «Норма», «Нестабильно», «Критично», «Нет соединения»
   (п. 13; ADR-004); «Нет данных» — только отображение, не статус качества.
8. Статусы инцидента — ровно шесть, в порядке п. 19; каждый переход — в `incident_events`
   (ADR-007).
9. Инцидент не создаётся по единичному отклонению — только по N подряд или длительности
   (п. 18; ADR-007).
10. Каждое уведомление фиксируется в `notification_log` (п. 18; ADR-007).
11. Права применяются и в панели, и в API; провайдер видит только свои линии (п. 16; ADR-008).
12. Блокировка учётной записи и устройства — без удаления истории (п. 16, п. 20; ADR-005, ADR-008).
13. Персональные данные — только контакты ответственных (п. 15); ученики и учителя — никогда
    (п. 12); в LLM ПД не передаются (ADR-011).
14. Пароли и коды установки — argon2id, токен устройства — sha256 со сравнением за постоянное
    время (секрет 256 бит, `backend/app/core/security.py`); сам секрет не хранится нигде.
    Секреты — в окружении (п. 12; ADR-005).
15. AI-текст обращения редактируется человеком до отправки; номер присваивается после
    отправки (п. 17; ADR-011).
16. Экспорт XLSX и CSV обязателен с минимальным набором колонок: школа, компьютер, кабинет,
    дата, время, Download, Upload, Ping, Jitter, Packet Loss, статус (п. 9).
17. Основная и резервная линии различаются; замер привязан к линии (п. 10; ADR-003).
18. Договорные значения хранятся отдельно и сравниваются с фактом наравне с порогами
    (п. 11, п. 14; ADR-003, ADR-004).
19. Административные действия, входы и ошибки передачи — в журнале (п. 12, п. 16; ADR-008).

## 9. Если что-то пошло не так

- Проверка красная — не «чинить» отключением теста, `# type: ignore` или `@ts-ignore`.
  Показать вывод человеку.
- Случайно закоммитил в `developing` локально — не пушить; перенести коммит в ветку и сказать.
- Нашёл секрет, чужой баг, странность вне задачи — сказать, не чинить молча.
- Конфликт в `web/src/api/generated/*` или `docs/reference/openapi.json` — не решать руками:
  после rebase запустить `make openapi` и закоммитить результат.
- Конфликт миграций (две ревизии от одной родительской — `alembic upgrade head` падает с
  «Multiple head revisions») — порядок задаёт цепочка `down_revision`, а не имя файла: после
  rebase поставить в своей ревизии `down_revision` на последнюю влитую, при необходимости
  переименовать файл на более позднее время и проверить `make db-reset`; влитую в `developing`
  ревизию не трогать (`CONTRIBUTING.md` §6, §9).
