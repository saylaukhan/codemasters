# Пакет агента для Linux (systemd)

`vko-agent` ставит агент «Мониторинг интернета ВКО» на компьютер или стенд с systemd: службу
`vko-agent.service` с автозапуском при загрузке, папку данных и файл конфигурации. GUI и
значка в трее нет — после установки участие пользователя не требуется (ТЗ п. 2, ADR-010).

Собираются оба формата — `.deb` (Debian, Ubuntu, Astra) и `.rpm` (RED OS, ALT, RHEL): в
plan.md §15 указан просто «Linux-пакет», формат — решение лида, и выбор не должен
блокировать поставку. Сборка только в CI: `.github/workflows/agent-linux.yml`.
`make check-agent` пакет не собирает, но проверяет, что unit не разошёлся с кодом агента
(`agent/internal/service/systemd_unit_test.go`).

## Что делает установка

1. Кладёт `vko-agent` в `/usr/bin/`.
2. Заводит системную учётную запись `vko-agent` без входа — служба работает не от root
   (plan.md §4.1, «минимум прав»).
3. Создаёт `/etc/vko-agent/` (0750 `root:vko-agent`) и `/var/lib/vko-agent/` (0750
   `vko-agent:vko-agent`): очередь замеров `queue.db`, журнал, `device.json` и токен
   устройства (файл 600, ADR-005).
4. Вызывает `vko-agent configure` — тот пишет `/etc/vko-agent/agent.yaml` (0640
   `root:vko-agent`) из переменных окружения команды установки.
5. Разрешает группе `vko-agent` unprivileged ICMP через `/etc/sysctl.d/90-vko-agent.conf`:
   без этого серия ping уходит в запасной метод TCP-connect.
6. Включает и запускает `vko-agent.service`.

При первом старте агент регистрируется на сервере кодом установки и получает `device_id` и
токен (T-07); дальше замеряет по расписанию с сервера (ADR-004, ADR-012). Пороги, расписание
и адрес сервера замеров в пакет не попадают.

## Параметры установки

Задаются переменными окружения команды установки — это аналог свойств MSI.

| Переменная | Обязательная | Что это |
|---|---|---|
| `VKO_ENROLL_CODE` | нет | одноразовый код установки из панели, привязывает ПК к школе (T-07) |
| `VKO_ROOM` | нет | кабинет, в котором стоит компьютер |
| `VKO_SERVER_URL` | нет | адрес API сервера мониторинга; по умолчанию — значение, зашитое при сборке |
| `VKO_LOG_LEVEL` | нет | `debug`, `info` (по умолчанию), `warn`, `error` |

```bash
# Debian / Ubuntu / Astra
sudo env VKO_ENROLL_CODE=VKO-7F3K-92QD VKO_ROOM="Кабинет 12" \
     apt install ./vko-agent_1.0.0_amd64.deb

# RED OS / ALT / RHEL
sudo env VKO_ENROLL_CODE=VKO-7F3K-92QD VKO_ROOM="Кабинет 12" \
     dnf install ./vko-agent-1.0.0.x86_64.rpm
```

Без `VKO_ENROLL_CODE` установка проходит, но устройство не регистрируется: агент пишет об
этом в журнал и ждёт. Код дописывается в `/etc/vko-agent/agent.yaml`, дальше
`systemctl restart vko-agent`.

## Проверка после установки

```bash
systemctl status vko-agent
sudo -u vko-agent /usr/bin/vko-agent status
journalctl -u vko-agent -n 50
```

`status` печатает состояние службы, зарегистрировано ли устройство, последний замер и размер
очереди. Запускать его лучше от `vko-agent`, а не от root: root открыл бы `queue.db` и
оставил рядом `queue.db-wal` от root, которые служба потом не перезапишет.

## Удаление

```bash
sudo apt purge vko-agent      # или: sudo dnf remove vko-agent
```

Служба останавливается, снимается с автозапуска, unit и `/etc/sysctl.d/90-vko-agent.conf`
убираются.

Папка `/var/lib/vko-agent/`, файл `/etc/vko-agent/agent.yaml` и учётная запись `vko-agent`
остаются намеренно — так же, как `%ProgramData%\VKO Monitor` после удаления MSI: в папке
лежат неотправленные замеры (ADR-006) и токен устройства. Повторная установка подхватит их и
не потребует нового кода. Чтобы поставить компьютер заново «с нуля», папку удаляют руками, а
прежнее устройство блокируют в админке (ТЗ п. 20).

## Обновление версии

Версия пакета — из тега (`v1.2.3` → `1.2.3`) или `0.1.<номер прогона>` без тега. Установка
поверх не трогает папку данных и сохраняет код установки, кабинет и адрес сервера из
`agent.yaml`. Службу при обновлении перезапускает `try-restart` — если администратор её
выключил, она останется выключенной.

Самообновления на Linux нет: `vko-agent update-apply` умеет только `msiexec` (T-50). Новая
версия ставится пакетом.

## Файлы

| Файл | Что в нём |
|---|---|
| `nfpm.yaml` | состав пакета для обоих форматов: файлы, права, зависимости, сценарии |
| `systemd/vko-agent.service` | unit: `User=vko-agent`, `Restart=on-failure`, ограничения systemd |
| `scripts/postinstall.sh` | учётная запись, папки, `vko-agent configure`, sysctl, запуск службы |
| `scripts/preremove.sh` | остановка и снятие с автозапуска при удалении |
| `scripts/postremove.sh` | уборка sysctl и `daemon-reload` после удаления |

Сценарии общие для `.deb` и `.rpm`, поэтому разбирают оба набора аргументов: `dpkg` передаёт
`configure` / `remove` / `purge`, `rpm` — `1` / `2` / `0`.

Переменные `VKO_VERSION` и `VKO_ARCH` подставляет workflow; `nfpm` запускается из папки
`agent/`, все пути `src` отсчитываются от неё.
