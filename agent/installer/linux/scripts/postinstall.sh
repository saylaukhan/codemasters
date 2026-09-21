#!/bin/sh
# Пост-установочный сценарий пакета агента «Мониторинг интернета ВКО» (T-52).
#
# Один сценарий на .deb и .rpm: аргументы у них разные (dpkg — configure [прежняя версия],
# rpm — 1 при установке и 2 при обновлении), поэтому обновление определяется разбором $1/$2.
#
# Делает то же, что MSI на Windows (installer/wix): учётная запись службы, папки, файл
# конфигурации через `vko-agent configure`, регистрация и запуск службы.
set -e

SERVICE=vko-agent.service
USER_NAME=vko-agent
CONFIG_DIR=/etc/vko-agent
CONFIG=/etc/vko-agent/agent.yaml
DATA_DIR=/var/lib/vko-agent
SERVER_URL_FILE=/usr/share/vko-agent/server-url
SYSCTL_FILE=/etc/sysctl.d/90-vko-agent.conf

is_upgrade=no
case "${1:-}" in
    configure)
        if [ -n "${2:-}" ]; then is_upgrade=yes; fi
        ;;
    2)
        is_upgrade=yes
        ;;
esac

# 1. Системная учётная запись без входа: служба работает не от root (plan.md §4.1).
if ! getent group "$USER_NAME" >/dev/null 2>&1; then
    groupadd --system "$USER_NAME"
fi
if ! getent passwd "$USER_NAME" >/dev/null 2>&1; then
    nologin=/usr/sbin/nologin
    [ -x "$nologin" ] || nologin=/sbin/nologin
    [ -x "$nologin" ] || nologin=/bin/false
    useradd --system --gid "$USER_NAME" --home-dir "$DATA_DIR" --no-create-home \
        --shell "$nologin" --comment "Мониторинг интернета ВКО" "$USER_NAME"
fi

# 2. Папки. Конфигурацию служба только читает, папку данных — читает и пишет: там очередь
# замеров, журнал, device.json и токен устройства (ADR-005, ADR-006).
mkdir -p "$CONFIG_DIR" "$DATA_DIR"
chown root:"$USER_NAME" "$CONFIG_DIR"
chmod 0750 "$CONFIG_DIR"
chown -R "$USER_NAME":"$USER_NAME" "$DATA_DIR"
chmod 0750 "$DATA_DIR"

# 3. Конфигурация. `vko-agent configure` сохраняет значения, которых в этот раз не передали,
# поэтому обновление пакета не теряет код установки и кабинет, правленные вручную.
# Значения приходят переменными окружения команды установки:
#   VKO_ENROLL_CODE=VKO-7F3K-92QD VKO_ROOM="Кабинет 12" apt install ./vko-agent_*.deb
set -- --config "$CONFIG" --data-dir "$DATA_DIR"
if [ -n "${VKO_ENROLL_CODE:-}" ]; then set -- "$@" --enroll-code "$VKO_ENROLL_CODE"; fi
if [ -n "${VKO_ROOM:-}" ]; then set -- "$@" --room "$VKO_ROOM"; fi
if [ -n "${VKO_LOG_LEVEL:-}" ]; then set -- "$@" --log-level "$VKO_LOG_LEVEL"; fi

# Адрес сервера: из окружения, иначе — значение сборки, и только когда конфигурации ещё нет.
# Иначе обновление пакета затёрло бы адрес, исправленный администратором.
server_url="${VKO_SERVER_URL:-}"
if [ -z "$server_url" ] && [ ! -f "$CONFIG" ] && [ -r "$SERVER_URL_FILE" ]; then
    server_url="$(cat "$SERVER_URL_FILE")"
fi
if [ -n "$server_url" ]; then set -- "$@" --server-url "$server_url"; fi

if /usr/bin/vko-agent configure "$@"; then
    # 0640 root:vko-agent — в файле код установки, служба его только читает.
    chown root:"$USER_NAME" "$CONFIG"
    chmod 0640 "$CONFIG"
else
    echo "vko-agent: конфигурация не записана. Задайте server_url в $CONFIG и выполните:" >&2
    echo "           systemctl restart $SERVICE" >&2
fi

# 4. Серия ping без прав root. probe (agent/internal/probe) шлёт unprivileged ICMP
# (SOCK_DGRAM) — ядро разрешает это только группам из net.ipv4.ping_group_range.
# Без этого замер не падает, а уходит в запасной метод TCP-connect.
gid="$(getent group "$USER_NAME" | cut -d: -f3)"
if [ -n "$gid" ]; then
    {
        echo "# Разрешает группе $USER_NAME unprivileged ICMP (SOCK_DGRAM): серия ping агента"
        echo "# без прав root (T-52, agent/internal/probe). Удаляется вместе с пакетом."
        echo "net.ipv4.ping_group_range = $gid $gid"
    } > "$SYSCTL_FILE"
    sysctl -q -w "net.ipv4.ping_group_range=$gid $gid" >/dev/null 2>&1 || true
fi

# 5. Служба. Автозапуск при загрузке — enable; при обновлении уважаем решение
# администратора, который мог службу выключить, поэтому try-restart, а не start.
if [ -d /run/systemd/system ]; then
    systemctl daemon-reload >/dev/null 2>&1 || true
    if [ "$is_upgrade" = yes ]; then
        systemctl try-restart "$SERVICE" >/dev/null 2>&1 || true
    elif ! systemctl enable --now "$SERVICE" >/dev/null 2>&1; then
        echo "vko-agent: служба не запустилась, смотрите: systemctl status $SERVICE" >&2
    fi
fi

exit 0
