# ADR-003 · Модель данных: школа → линия → точка мониторинга → устройство → замер

**Статус:** принято · **Дата:** 2026-09-16 · **Источник:** ТЗ п. 7, п. 10, п. 14, п. 15, plan.md §5

## Контекст
ТЗ п. 7 даёт плоскую схему Schools → Devices → Measurements, но п. 10 требует различать основную и
резервную линии и привязывать замер к линии, п. 14 — хранить договорные параметры, п. 15 — контакты
ответственных. Плоская схема не отвечает на главный вопрос панели: какая именно линия деградирует.

## Решение
- Иерархия: `schools` → `lines` → `monitoring_points` → `devices` → `measurements`. Замер хранит `device_id`
  и `line_id`; статус считается вверх по цепочке. Справочники `regions` (PostGIS), `providers`, `connection_types`; поля таблиц — plan.md §5.
- `lines.status` — `main | reserve | disabled`, `ip_ranges` — для сверки внешнего IP. Договор — поля
  `contract_down_mbps`, `contract_up_mbps`, `contract_number`, `contract_date` в `lines`, не в порогах (п. 11, п. 14).
- `monitoring_points.is_primary` — главная точка школы; `devices.status` — `active | blocked`, `devices.token_hash` — `sha256$…`, алгоритм назван в самой строке (ADR-005).
- `school_contacts` — единственная таблица с персональными данными: ФИО, должность, телефон, e-mail,
  контакт поддержки провайдера, `updated_at` (п. 15).
- `measurements` и `heartbeats` — hypertables TimescaleDB. `measurement_uuid` — уникальный индекс (ADR-006);
  в замере — `thresholds_snapshot`, `quality_status`, `contract_ok`, `iface_type`, `server` (ADR-004, ADR-012).
- Continuous aggregates `m_hourly`, `m_daily` по линии и устройству (avg/min/max, число замеров, число
  проблемных): аналитика, рейтинг школ и тепловая карта читают их, а не сырые замеры.

## Последствия
- School ID выводится из привязки устройства, а не из запроса (ADR-005). Несколько устройств на линии:
  статус линии — по всем её Ethernet-устройствам; Wi‑Fi-замеры хранятся, но линию не оценивают.
- Хранение: сырые замеры 24 месяца, агрегаты бессрочно. Имена — snake_case во множественном числе, время —
  `timestamptz` в UTC (ADR-014). Новая таблица обязана иметь индексы на FK, `created_at` / `updated_at` где уместно,
  RLS при области видимости (ADR-008), hypertable для временного ряда и тест в `backend/tests/`.
- Кода нет: схема появится в T-02 миграциями Alembic (forward-only), агрегаты — в T-19. Формат School ID:
  `schools.school_code` — строка от заказчика; пока её нет — `VKO-<код района>-<номер>`.
