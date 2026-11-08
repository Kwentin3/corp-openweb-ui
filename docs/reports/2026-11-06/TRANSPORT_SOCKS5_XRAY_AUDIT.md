# Аудит транспорта перед переходом SOCKS5 → Xray

Дата: 2026-11-06, наблюдения около 14:05–14:10 МСК.

Исторический аудит до изменений. После него завершены [переход на Xray](TRANSPORT_XRAY_GOAL.md) и [добавление AmneziaWG](TRANSPORT_AMNEZIAWG_GOAL.md); актуальная эксплуатационная схема — в [provider runbook](../../ops/PROVIDER_SETUP_RUNBOOK.md).

## Результат и границы

Собран контекст исходников, работающего сервера приложения и существующего Xray Amnezia. Пользователь подтвердил, что целевой узел — существующий Xray в Amnezia. Конфигурации и сервисы на серверах не менялись, перезапусков, установки ПО, генераций модели и запросов с API-ключами не было. Проверки включали короткие TCP-соединения и GET `/v1/models` без авторизации.

Аудит источника завершён. Текущее состояние целевого Xray и готовность миграции не подтверждены: доступ к целевому серверу ограничен таймаутами. Это не доказательство неисправности самого сервера или конкретной причины сетевого сбоя.

## Подтверждённая текущая схема

```text
OpenWebUI 0122 ─────────────┐
STT 0122 ──────────────────┼─ HTTP proxy на Docker gateway:8118
Google/OpenAI/Anthropic    │       → host Privoxy
gateway 0122 ──────────────┘       → удалённый SOCKS5 Amnezia
```

- DNS публичного портала совпадает с проверенным SSH-узлом приложения; проверка host key оставалась включённой.
- Production-маршрут Traefik указывает на `openwebui-0122-openwebui-0122-1`, а не на исторический `0114`.
- Работающие OpenWebUI, STT и gateway `0122` имеют статус healthy и одинаковый HTTP proxy в верхнем и нижнем регистре переменных окружения. Это состояние healthcheck, не доказательство работы провайдера.
- Privoxy active/running, слушает loopback и Docker gateway на `8118`, публичного wildcard listener на этом порту нет. UFW содержит разрешения от Docker-сетей. Полный аудит nftables/Docker firewall в эту работу не входил.
- Активная директива — `forward-socks5t / <authenticated upstream> .`. Адрес, порт и декодированные credentials совпадают с `OPENWEBUI_SOCKS5_UPSTREAM` в старом `/opt/openwebui-prd0/.env`; секреты не экспортировались. Комментарии в action files исключены: активных `forward-override` не обнаружено.
- Само приложение получает HTTP proxy; `OPENWEBUI_SOCKS5_UPSTREAM` не передаётся как используемый proxy в исследованном Compose. Одной правки этой переменной недостаточно для переключения Privoxy.
- Локальный Xray не обнаружен среди контейнеров, systemd units с соответствующим именем и исполняемых файлов в PATH. Это не полный поиск всех файлов на диске.
- OfficeCLI и Terminal `0122` не имеют proxy env. У SearXNG также нет proxy env; его собственные настройки outbound в этом аудите не исследовались. Поэтому утверждение «весь исходящий трафик сервера идёт через Privoxy» не подтверждено.

## Наблюдаемый разрыв

| Проверка | Результат |
| --- | --- |
| OpenWebUI, STT, gateway → локальный HTTP bridge | TCP connect успешен у всех трёх |
| OpenWebUI → OpenAI через env, aiohttp/httpx | TimeoutError / ReadTimeout |
| STT → OpenAI через env, httpx | ReadTimeout |
| gateway → OpenAI через env, aiohttp/httpx | TimeoutError / ReadTimeout |
| Сервер приложения → Amnezia TCP 22, 443, SOCKS5 port | Все три — TimeoutError, предел 5 с на соединение |
| Локальная машина → Amnezia SSH | ConnectTimeout, предел 8 с |
| SSH через исторический Hermes jump | Таймаут banner exchange; конкретный отказавший участок не установлен |

`aiohttp` в STT отсутствует; это ограничение диагностического клиента, а не найденная неисправность STT. Текущие HTTP-пробы не получили ожидаемого 401 и не подтвердили TLS/доступность OpenAI. Они не проверяют работоспособность API-ключей, моделей, Google/Anthropic или пользовательского чата.

Доказан доступ контейнеров до локального bridge и отсутствие успешного TCP connect от узла приложения до проверенных портов Amnezia в момент аудита. Причины за этой границей — маршрутизация, фильтрация, состояние целевого узла и другие варианты — остаются гипотезами.

## Источники конфигурации и риск устаревшего контекста

Работающий релиз использует `/opt/openwebui-upgrade-0122/compose/openwebui.release-0122.compose.yml`, дополнения `google` и `route`. Proxy env приходит из защищённых release env files через `RELEASE_WEBUI_ENV_FILE`, `RELEASE_STT_ENV_FILE`, `RELEASE_GOOGLE_ENV_FILE`. Gateway монтирует конфигурацию из каталога `final-01/google-gateway`.

Старый `/opt/openwebui-prd0/.env` и локальная `.env` подтверждают историю и совпадение текущего upstream, но не являются единственными владельцами окружения работающего релиза. Если при миграции понадобится менять env контейнеров, необходимо разрешить фактические пути release env files; в этом аудите они не установлены. При сохранении HTTP endpoint приложения env менять не требуется.

Локальные источники:

- [Compose HTTP proxy](../../../compose/openwebui.compose.yml), [release 0122](../../../compose/openwebui.release-0122.compose.yml), [gateway](../../../compose/openwebui.release-0122.google.compose.yml).
- [Preflight](../../../scripts/preflight.sh) принимает HTTP/HTTPS proxy и отклоняет прямой SOCKS URL в `OPENWEBUI_OUTBOUND_PROXY`.
- [Первоначальный bridge](../2026-06-09/OPENWEBUI_PRD_0_SOCKS5_BRIDGE_DEPLOYMENT.report.md), [provider plan](../../infra/PROVIDER_CONNECTIONS_PLAN.md).
- Точные container/image IDs, endpoints и конфигурационный hash сохранены в игнорируемом `local/transport-audit-20261106/inventory.private.json`; результаты ограниченных HTTP-проб — в `probe.private.json`. Пароли, UUID и private keys в них отсутствуют.

## Контекст существующего Xray

В соседнем проекте Amnezia сохранён receipt `docs/reports/2026-11-01/goal-xray-after-reboot.json`: VLESS / REALITY / `xtls-rprx-vision` через публичный TCP443, успешные TLS, remote DNS, HTTP200 и проверка egress; временный клиент остановлен. Исторический клиент был Xray 26.10.31. Скрипт `goal_xray_check.py` показывает прежний путь конфигурации `/opt/amnezia/xray/server.json` внутри `amnezia-xray`.

Это evidence от 1 ноября, а не текущее подтверждение версии, конфигурации или доступности. Сегодня серверная конфигурация Amnezia не прочитана. Не извлекались и не переиспользовались private keys или пользовательские профили.

## Минимальное направление миграции

Сохранить HTTP endpoint приложений и существующий Privoxy; добавить на узле приложения Xray client с локальным SOCKS inbound и VLESS/REALITY outbound к Amnezia, затем переключить только upstream Privoxy на этот локальный inbound. Локальный SOCKS при этом остаётся внутренним адаптером, а внешний транспорт меняется на Xray. Такой вариант сохраняет существующих владельцев HTTP listener, firewall и env контейнеров.

Xray также имеет штатный HTTP inbound: это возможная последующая замена Privoxy, но она требует отдельно проверить переход владения listener, совместимость и доступ из Docker. Для первого переключения удаление работающего HTTP bridge не требуется. Штатные возможности проверены по [HTTP inbound](https://xtls.github.io/en/config/inbounds/http.html) и [SOCKS inbound](https://xtls.github.io/en/config/inbounds/socks.html); совместимость конкретной установленной версии ещё предстоит проверить.

## Обязательные условия будущего переключения

1. Подтвердить свежую доступность Amnezia TCP443 именно с узла приложения; при сохраняющемся таймауте сначала выяснить сетевой разрыв. Смена протокола на том же недоступном IP сама по себе его не устраняет.
2. Прочитать текущий native Xray runtime/config и получить предназначенный для сервера приложения клиентский профиль. Проверить serverName, public key, shortId, flow, server port и версию; сохранить серверные private keys у их владельца.
3. Подготовить ограниченный клиентский кандидат вне рабочего HTTP endpoint. Проверить конфигурацию, TLS, remote DNS, egress и отсутствие нежелательного direct fallback, затем те же запросы через будущую цепочку из всех трёх контейнеров.
4. Перед изменением сохранить rollback Privoxy и клиентского сервиса. Согласовать само переключение отдельно: текущая авторизация относится к аудиту.
5. После переключения принять обычный чат/streaming, функции gateway и STT, доступ внутренних сервисов через NO_PROXY и восстановление после переподключения. Ни healthcheck, ни HTTP401 не заменяют продуктовую приёмку. Не удалять старый маршрут до её завершения.

Следующий шаг: восстановить или независимо подтвердить маршрут от приложения к существующему Amnezia и актуализировать целевой профиль. Сам переезд не выполнялся.
