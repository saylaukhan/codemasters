"""Columns of a raw export: Russian headers and values of XLSX and CSV (ТЗ п. 9, ADR-013).

A file is a document for a person, not an API answer, so it carries the Russian words the panel
shows. They repeat ``web/src/lib/labels.ts`` (``QUALITY_STATUS_LABELS``, ``LINE_STATUS_LABELS``,
``IFACE_LABELS``, ``EXPORT_COLUMN_LABELS``): a change there is made here too. JSON keeps the
codes and the column codes as keys.
"""

from app.schemas.exports import ExportColumn

COLUMN_TITLES: dict[ExportColumn, str] = {
    "school_name": "Школа",
    "hostname": "Компьютер",
    "room": "Кабинет",
    "date": "Дата",
    "time": "Время",
    "download_mbps": "Download, Мбит/с",
    "upload_mbps": "Upload, Мбит/с",
    "ping_ms": "Ping, мс",
    "jitter_ms": "Jitter, мс",
    "packet_loss_pct": "Packet Loss, %",
    "quality_status": "Статус",
    "school_code": "School ID",
    "device_id": "ID компьютера",
    "line_status": "Линия",
    "connection_status": "Связь",
    "iface_type": "Интерфейс",
    "duration_s": "Длительность замера, с",
    "external_ip": "Внешний IP",
    "server": "Сервер замера",
    "agent_version": "Версия агента",
}

# Codes of a column turned into words; other values are written as they are.
VALUE_LABELS: dict[ExportColumn, dict[str, str]] = {
    "quality_status": {
        "normal": "Норма",
        "unstable": "Нестабильно",
        "critical": "Критично",
        "offline": "Нет соединения",
    },
    "line_status": {"main": "Основная", "reserve": "Резервная", "disabled": "Отключена"},
    "connection_status": {"online": "Есть", "offline": "Нет"},
    "iface_type": {"ethernet": "Ethernet", "wifi": "Wi‑Fi", "other": "Другое"},
}
