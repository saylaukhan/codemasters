#!/bin/sh
# Перед удалением пакета: остановить и снять службу с автозапуска (T-52).
# Аргумент удаления: dpkg — remove / purge, rpm — 0. При обновлении (upgrade / 1)
# служба не трогается: её перезапустит postinstall.
set -e

SERVICE=vko-agent.service

case "${1:-}" in
    remove|purge|0)
        if [ -d /run/systemd/system ]; then
            systemctl --no-reload disable --now "$SERVICE" >/dev/null 2>&1 || true
        fi
        ;;
esac

exit 0
