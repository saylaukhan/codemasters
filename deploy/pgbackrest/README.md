# Резервное копирование и восстановление БД

pgBackRest (T-53, plan.md §13). Полный бэкап раз в сутки, непрерывный архив WAL — значит
восстановиться можно не только на момент бэкапа, но и на любую минуту после него.

Что где лежит:

| Файл | Зачем |
|---|---|
| `pgbackrest.conf` | конфигурация; монтируется в контейнеры `db` и `pgbackrest` |
| `backup.sh` | команда контейнера `pgbackrest`: стендж, расписание, `backup` + `expire` |
| `../../docker-compose.backup.yml` | надстройка над основным compose: архив WAL у базы и сам контейнер |

Сроки и время задаются в `.env` (`PGBACKREST_BACKUP_AT`, `PGBACKREST_RETENTION_FULL`,
`PGBACKREST_REPO1_PATH`) — см. `.env.example`. Секретов ни здесь, ни в конфигурации нет:
pgBackRest ходит к базе по unix-сокету от имени `postgres`.

## Включение

Бэкапы — отдельный файл compose, а не часть основного. Как только включён `archive_mode`,
PostgreSQL держит сегменты WAL, пока их не заберёт pgBackRest; на машине разработчика
`make up` поднимает базу без этого контейнера, и диск заполнился бы молча.

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml up -d
```

Первый старт контейнера `pgbackrest` создаёт стендж (`stanza-create`) и проверяет, что
`archive_command` базы доходит до того же хранилища (`check`). Обе команды идемпотентны.

Разовый бэкап руками — `make backup`.

## Проверка, что всё работает

```bash
# Список бэкапов: должен быть хотя бы один full, и archive — min/max сегментов.
docker compose -f docker-compose.yml -f docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=vko info

# Архив WAL доходит до хранилища.
docker compose -f docker-compose.yml -f docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=vko check
```

Признаки беды: `info` показывает бэкап старше суток; в `docker compose logs pgbackrest`
строка «БЭКАП НЕ УДАЛСЯ»; в журнале PostgreSQL — ошибки `archive_command`. Подробности —
`/var/log/pgbackrest` (том `pgbackrest_log`).

## Восстановление

Восстановление затирает текущий каталог базы. Сначала убедитесь, что восстанавливаете
именно то, что нужно, и что API остановлен — иначе он будет писать в базу во время
восстановления.

### 1. Остановить всё, что пишет в базу

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml stop api worker beat db
```

Контейнер `pgbackrest` остаётся запущенным: восстановление делает он.

### 2. Выбрать, на какой момент восстанавливаться

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=vko info
```

В выводе — список полных бэкапов с временем начала и окончания, и диапазон архива WAL.
Восстановиться можно на конец любого бэкапа или на любой момент внутри диапазона архива.

### 3. Восстановить

На момент последнего бэкапа — всё, что записано после него, теряется:

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=vko --delta restore
```

На точку во времени — например, за минуту до ошибочного удаления данных:

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml exec pgbackrest \
  pgbackrest --stanza=vko --delta \
  --type=time --target="2026-09-21 14:25:00+06" \
  --target-action=promote restore
```

`--delta` переписывает только отличающиеся файлы — так быстрее, чем выкладывать базу
целиком. Время указывается с часовым поясом; в системе он `Asia/Almaty` (+06), хранение —
UTC (ADR-014).

### 4. Поднять базу и убедиться, что данные на месте

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml start db
docker compose -f docker-compose.yml -f docker-compose.backup.yml logs -f db
```

В журнале должны пройти строки восстановления архива и «database system is ready to accept
connections». После этого:

```bash
# Последний замер в базе — его время должно быть не позже целевого момента.
docker compose -f docker-compose.yml -f docker-compose.backup.yml exec db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select max(measured_at) from measurements"

# Миграции на месте: версия схемы совпадает с head репозитория.
docker compose -f docker-compose.yml -f docker-compose.backup.yml exec db \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "select version_num from alembic_version"
```

### 5. Вернуть сервисы

```bash
docker compose -f docker-compose.yml -f docker-compose.backup.yml start api worker beat
```

Проверьте панель: карта, карточка школы, список инцидентов. Агенты в это время копили
замеры в своей очереди и дошлют их сами (ADR-006), поэтому дыра в данных за время простоя
закроется без ручных действий — кроме той, что осталась за целевым моментом.

### После восстановления на точку во времени

База стала новой линией времени, и старые бэкапы к ней больше не относятся. Снимите полный
бэкап сразу:

```bash
make backup
```

## Куда класть хранилище на боевом сервере

Том `pgbackrest_repo` по умолчанию лежит там же, где данные Docker, то есть на том же диске,
что и сама база. Это защищает от ошибочного удаления данных, но не от отказа диска. На
боевом сервере смонтируйте в каталог тома отдельный диск или сетевое хранилище — путь
внутри контейнера задаёт `PGBACKREST_REPO1_PATH`.
