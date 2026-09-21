#!/usr/bin/env bash
# Ежедневный полный бэкап БД (T-53). Запускается как команда контейнера pgbackrest.
#
# Обычный запуск: бесконечный цикл — ждёт времени PGBACKREST_BACKUP_AT по часовому поясу TZ
# и делает полный бэкап, затем expire по сроку хранения из конфигурации.
# Разовый запуск руками:  docker compose run --rm pgbackrest once
#
# Стендж (stanza) создаётся при первом старте: команда идемпотентна, повтор на уже
# созданном хранилище ничего не меняет.

set -euo pipefail

STANZA="${PGBACKREST_STANZA:-vko}"
BACKUP_AT="${PGBACKREST_BACKUP_AT:-02:30}"

log() { printf '%s pgbackrest: %s\n' "$(date --iso-8601=seconds)" "$*"; }

run_backup() {
	log "полный бэкап, стендж ${STANZA}"
	pgbackrest --stanza="${STANZA}" --type=full backup
	log "удаление просроченных бэкапов"
	pgbackrest --stanza="${STANZA}" expire
	log "готово; последние бэкапы:"
	pgbackrest --stanza="${STANZA}" info
}

prepare() {
	# Ждём, пока база примет соединение: depends_on healthy уже это проверил, но
	# контейнер может пережить перезапуск базы.
	until pg_isready --host=/var/run/postgresql --port=5432 --quiet; do
		log "база не отвечает, ждём 5 с"
		sleep 5
	done
	log "создание стенджа ${STANZA}, если его ещё нет"
	pgbackrest --stanza="${STANZA}" stanza-create
	# check убеждается, что archive_command сервера доходит до этого же хранилища:
	# без него бэкап снимется, а восстановиться на точку во времени будет нечем.
	pgbackrest --stanza="${STANZA}" check
}

seconds_until() {
	# Секунды до ближайшего наступления времени HH:MM; если оно уже прошло — до завтра.
	local target_today target
	target_today=$(date -d "today ${1}" +%s)
	target=${target_today}
	if [ "${target}" -le "$(date +%s)" ]; then
		target=$(date -d "tomorrow ${1}" +%s)
	fi
	echo $((target - $(date +%s)))
}

prepare

if [ "${1:-}" = "once" ]; then
	run_backup
	exit 0
fi

log "расписание: каждый день в ${BACKUP_AT} (${TZ:-UTC})"
while true; do
	pause=$(seconds_until "${BACKUP_AT}")
	log "следующий бэкап через ${pause} с"
	sleep "${pause}"
	# Сбой одного бэкапа не должен убивать расписание: контейнер бы перезапустился и
	# начал ждать заново, а запись в журнале осталась бы только в логе Docker.
	if ! run_backup; then
		log "БЭКАП НЕ УДАЛСЯ — смотрите /var/log/pgbackrest"
	fi
done
