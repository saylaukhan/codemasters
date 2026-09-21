#!/bin/sh
# После удаления пакета (T-52).
#
# Папка данных /var/lib/vko-agent, файл конфигурации /etc/vko-agent/agent.yaml и учётная
# запись vko-agent остаются намеренно — так же, как %ProgramData%\VKO Monitor после удаления
# MSI: в папке лежат неотправленные замеры и токен устройства (ADR-006, ADR-005).
# Чтобы поставить компьютер заново «с нуля», папку удаляют руками, а прежнее устройство
# блокируют в админке (ТЗ п. 20).
set -e

SERVICE=vko-agent.service
SYSCTL_FILE=/etc/sysctl.d/90-vko-agent.conf

case "${1:-}" in
    remove|purge|0)
        rm -f "$SYSCTL_FILE"
        if [ -d /run/systemd/system ]; then
            systemctl daemon-reload >/dev/null 2>&1 || true
            systemctl reset-failed "$SERVICE" >/dev/null 2>&1 || true
        fi
        ;;
esac

exit 0
