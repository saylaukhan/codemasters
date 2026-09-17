# Сервер замеров: LibreSpeed + ndt7

Два сервиса `docker-compose.yml` (ADR-012): `speedtest` — LibreSpeed, основной сервер, и
`ndt7` — ndt-server M-Lab, резерв на случай, когда LibreSpeed не ответил. Оба поднимает
`make up`. Настраиваются переменными окружения и аргументами в `docker-compose.yml`, своих
файлов конфигурации у них нет. Версии образов закреплены там же; обновление — правкой тега.

| Сервис | Образ | Порт | Что использует агент (T-10) |
|---|---|---|---|
| `speedtest` | `ghcr.io/librespeed/speedtest:6.3.0` | 8080 | `GET /backend/garbage.php?ckSize=N` — download, `POST /backend/empty.php` — upload, `GET /backend/getIP.php` — IP |
| `ndt7` | `measurementlab/ndt-server:v0.25.3` | 8081 | WebSocket `ws://…/ndt/v7/download` и `/ndt/v7/upload`, подпротокол `net.measurementlab.ndt.v7` |

Адреса серверов в агент и панель не зашиваются. Начальные значения — `SPEEDTEST_URL` и
`NDT7_URL` из `.env`: `make seed` записывает их в `settings`, только если записи ещё нет.
Дальше адрес меняется в админке (T-37), а агент получает его из `GET /api/agent/config` (T-17).

## Ручная проверка

```bash
make up
# LibreSpeed: откройте http://localhost:8080 и нажмите «Start» — покажет Download и Upload
curl -s http://localhost:8080/backend/getIP.php
# ndt7: ответ 101 Switching Protocols — сервер принимает тест
curl -s -m 3 -o /dev/null -w '%{http_code}\n' \
  -H 'Connection: Upgrade' -H 'Upgrade: websocket' -H 'Sec-WebSocket-Version: 13' \
  -H 'Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==' \
  -H 'Sec-WebSocket-Protocol: net.measurementlab.ndt.v7' \
  http://localhost:8081/ndt/v7/download
# Замер агентом (T-10): LibreSpeed, а при его отказе — ndt7; метод и сервер — в выводе
cd agent && go run ./cmd/vko-agent speed --librespeed http://localhost:8080 --ndt7 ws://localhost:8081
```

## Ограничения

- Оба сервера работают без TLS (`http://`, `ws://`): сертификат не настроен, TLS-порты ndt7
  выключены. Как закрыть их TLS в бою, решает лид (строка в `docs/known-limitations.md`).
- Образ ndt-server собран только для amd64: на Apple Silicon он работает в эмуляции и медленнее,
  поэтому локальные цифры ndt7 не показательны.
