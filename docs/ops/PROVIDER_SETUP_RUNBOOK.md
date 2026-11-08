# Provider Setup Runbook

## Назначение

Runbook описывает подключение OpenAI и Gemini штатными средствами OpenWebUI.

## Preconditions

- OpenWebUI доступен по `https://gpt.alpha-soft.ru`.
- Администратор может войти в Admin UI.
- Primary provider через `.env`: OpenAI.
- Secondary provider через Admin UI: Gemini.
- Есть OpenAI API key и Gemini API key.
- Проверены billing, quota и region/project restrictions для обоих провайдеров.
- OpenAI model id: `gpt-5.4-mini`.
- Gemini model id: `gemini-3.5-flash`.

## 1. Primary provider через `.env`

Открыть server-local `.env` на сервере.

OpenAI primary:

```env
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=<openai-api-key>
DEFAULT_MODELS=gpt-5.4-mini
```

Gemini primary является допустимым fallback-вариантом, но не выбран для текущего PRD-0 `.env.example`:

```env
OPENAI_API_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
OPENAI_API_KEY=<gemini-api-key>
DEFAULT_MODELS=gemini-3.5-flash
```

Не коммитить `.env`. После изменения:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml up -d
```

Если OpenWebUI уже запускался, часть настроек могла сохраниться в persistent config. В таком случае проверить Connections в Admin UI и исправить provider там.

Важно: OpenAI и Gemini уже выбраны как provider set. Admin UI не является blocker по выбору provider; это штатное место для ввода second provider connection и Gemini API key без multi-value env.

Если OpenAI API блокирует регион исходящего IP, можно задать outbound proxy для OpenWebUI без fork/frontend changes:

```env
OPENWEBUI_OUTBOUND_PROXY=http://172.18.0.1:8118
OPENWEBUI_SOCKS5_UPSTREAM=socks5h://user:password@proxy-host:1080
OPENWEBUI_NO_PROXY=localhost,127.0.0.1,::1,openwebui,traefik,openwebui-traefik,gpt.alpha-soft.ru
```

OpenWebUI OpenAI route uses an HTTP client path that expects an HTTP proxy. Для SOCKS5 нужен local HTTP-to-SOCKS bridge, например Privoxy. `socks5h://` остается upstream-схемой bridge, чтобы DNS provider API тоже шел через proxy. Реальные proxy credentials хранить только в server-local `.env`/password manager.

Bridge должен слушать только loopback и Docker gateway address. Если UFW настроен как `deny incoming`, добавить узкое правило только от Docker subnet к bridge port, например `172.18.0.0/16 -> 172.18.0.1:8118/tcp`. Не открывать proxy port публично.

<a id="текущий-транспорт-amnezia-xray-6-ноября-2026"></a>

Текущее состояние на 6 ноября 2026: активен **AmneziaWG3.1**, Xray сохранён для ручного переключения. Основной HTTP endpoint приложений прежний. Проверка выбора: `sudo openwebui-transport status`; [приёмка второго транспорта](../reports/2026-11-06/TRANSPORT_AMNEZIAWG_GOAL.md).

### Backend Xray, 6 ноября 2026

Внешний SOCKS5 заменён клиентским VLESS/TCP/REALITY/vision-туннелем. Схема:

`OpenWebUI / STT / gateway → прежний HTTP endpoint Privoxy → 127.0.0.1:10808 SOCKS → Xray → Amnezia`.

Локальный SOCKS — адаптер между двумя существующими компонентами. Внешний транспорт этой ветки — Xray; старый удалённый SOCKS5 не является рабочим резервом. Второй протокол AmneziaWG добавлен ниже; актуальный выбор всегда читается из `openwebui-transport status`.

Владельцы конфигурации:

- Штатный `xray.service`, пользователь `xray`, бинарный файл `/usr/local/bin/xray`.
- Клиентский JSON `/usr/local/etc/xray/config.json`: `root:xray`, `0640`, каталог `0750`. Единственный outbound — предоставленный VLESS; direct fallback, TUN и изменение системных маршрутов не добавлены.
- Локальный authenticated SOCKS inbound слушает только `127.0.0.1:10808`. При выборе Xray его credentials используются в единственной `forward-socks5t / … .` в `/etc/privoxy/config`; при выборе AWG эту директиву заменяет `forward / 10.203.0.2:8119`.
- `OPENWEBUI_SOCKS5_UPSTREAM` в локальной и исторической серверной `.env` обновлён как операторская запись upstream. Compose не генерирует из неё Privoxy config; одной правки `.env` недостаточно.
- HTTP proxy и NO_PROXY работающих контейнеров не менялись. В релизе `0122` их источники — защищённые release env files, не только старый `/opt/openwebui-prd0/.env`.

Для воспроизведения использовать официальный Linux amd64 release **26.10.31** и installer commit **04e6f3bd9534811ed901a48c47b2c042dd64eb3a**. SHA256 архива `Xray-linux-64.zip`:

```text
e4bd9119f50ae7c41658b1abd0679ae06f98bd864a2907ff33f2f2cf7081b214
```

До установки подготовить защищённый клиентский JSON из предоставленного Amnezia client profile, сохранив VLESS outbound и заменив только inbound на локальный SOCKS. Создать штатного пользователя `xray` через systemd-sysusers и выставить указанные выше owner/mode. Проверить JSON бинарным файлом из проверенного архива командой `xray run -test -config <protected-config>`. Серверные SSH/private keys для этого не нужны.

Официальный installer автоматически стартует и включает сервис при первой установке: готовый конфиг должен существовать заранее. Рядом с архивом сохранить официальный `.dgst`; затем выполнить:

```bash
bash install-release.sh install --local ./Xray-linux-64.zip --without-geodata --without-logfiles
runuser -u xray -- /usr/local/bin/xray run -test -config /usr/local/etc/xray/config.json
systemctl is-active xray
systemctl is-enabled xray
```

`--local` не сочетать с `--version`. Установка использует штатный systemd unit и `Restart=on-failure`; вывод Xray идёт в journal. Исходники: [Xray release](https://github.com/XTLS/Xray-core/releases/tag/v26.10.31), [зафиксированный installer](https://github.com/XTLS/Xray-install/blob/04e6f3bd9534811ed901a48c47b2c042dd64eb3a/install-release.sh).

При замене самого Xray profile сначала проверить отдельный туннель, TLS/DNS/egress и целевые API; сохранить защищённый rollback config. Для выбора между уже установленными AWG и Xray использовать `openwebui-transport use …` ниже: selector проверяет backend и выполняет native auto-reload без restart основного Privoxy. Контейнеры не требуется пересоздавать при сохранении HTTP endpoint.

Защищённые исходные конфигурации, installer и receipts перехода SOCKS5 → Xray оставлены на узле приложения в `/root/transport-xray-20261106` (`0700`); исходная Privoxy — `privoxy.config.before`, историческая `.env` — `prd0.env.before`. Это исторический rollback, а не рабочий резерв через прежний SOCKS5. Остановка выбранного backend лишает новые запросы внешней связи; сначала переключить на проверенный рабочий backend. Xray сохраняется как второй доступный протокол.

Приёмка и её ограничения: [GOAL транспорта](../reports/2026-11-06/TRANSPORT_XRAY_GOAL.md). HTTP401 без API-ключа доказывает доступность API, но не работу чата; нужны штатный streaming и реальное STT на коротком синтетическом аудио.

### Второй backend AmneziaWG3.1 и ручное переключение

Основной HTTP endpoint остаётся прежним. Выбор хранится **только** в forwarding directive `/etc/privoxy/config`; дополнительного файла активного состояния и автоматического failover нет.

```text
Xray: Privoxy → authenticated loopback SOCKS → native Xray/TCP → VPN server
AWG:  Privoxy → namespace HTTP adapter → native AmneziaWG3.1/UDP → тот же VPN server
```

Операторские команды на узле приложения:

```bash
sudo openwebui-transport status
sudo openwebui-transport use awg
sudo openwebui-transport use xray
```

Selector проверяет доступность выбранного backend до изменения, валидирует native Privoxy config и атомарно заменяет файл с сохранением прав/owner и новым mtime. Используется штатный auto-reload Privoxy3.0.34, без restart: для обнаружения изменения нужны свежие соединения. При ошибке после записи возвращается прежний конфиг с новым mtime. Существующие CONNECT streams продолжают свой прежний маршрут до закрытия; выбор действует на новые соединения. Снимки конфигурации сохраняются в защищённом `/root/transport-awg-20261106`.

Native owners и source files:

- [amneziawg-egress.service](../../deploy/transport/amneziawg-egress.service) запускает foreground userspace daemon в root network namespace; UDP использует обычный маршрут хоста.
- [awg-egress-netns.sh](../../deploy/transport/awg-egress-netns.sh) создаёт `awg-egress`, переносит TUN `awge0`, настраивает только namespace default route. Veth `awge-host/awge-peer`, сеть `10.203.0.0/30`, служит локальному доступу к proxy. Host default route, policy rules, глобальный DNS, NAT и forwarding не меняются.
- [privoxy-awg-egress.service](../../deploy/transport/privoxy-awg-egress.service) использует уже установленный Privoxy через native `ip netns exec`, с [ограниченным adapter config](../../deploy/transport/privoxy-awg-egress.conf). Слушает `10.203.0.2:8119`, принимает только root-side адрес veth; наружу этот port не опубликован.
- [openwebui-transport.py](../../deploy/transport/openwebui-transport.py) устанавливается как `/usr/local/sbin/openwebui-transport`; это ограниченный coordinator native операций, а не новый proxy/harness.

Профиль хранится в `/etc/amnezia/egress/profile.conf`, native Interface/Peer после `awg-quick strip` — в `interface.conf`, адрес/MTU — в `interface.env`. Каталог0700 и secret files0600. DNS placeholders экспорта буквально разрешаются из валидных dns1/dns2; resolver file — `/etc/netns/awg-egress/resolv.conf`. Непроверенные hooks из профиля не исполняются. Если профиль не задаёт MTU, используется **1376**, штатный Amnezia Linux AWG default; перед перемещением TUN daemon получает время обработать изменение. В namespace нет default через veth, IPv6 default unreachable: потеря AWG не включает direct egress.

Воспроизводимые готовые artifacts, без сборки/DKMS на production:

- Static `/usr/local/bin/amneziawg-go` извлечён без запуска контейнера из официального `amneziavpn/amneziawg-go@sha256:c68009d33df3aef4654db72bf1a7880cfa0a631fe866c50d9ae3dd34ddd7c13a`, tag3.1.20260828, source commit `b5928efb6ca19f0153958460c3d141f04abc5c2e`. Binary SHA256 `6177066f0e35b1cb44945136d9a10841dd3ce30fdf16009c9a815cd943a982fe`.
- Только `amneziawg-tools` Noble/amd64 из официального PPA: `1.0.20210914-0~202608130144+ee0f0a9~ubuntu24.04.1`; deb SHA256 `2c924076be2ba217eea04f9693291f01c5307a9be5aeee60d04525a50ff2804f`. Пакет `amneziawg`, тянущий DKMS, не устанавливался.
- Не принимать identity go binary только по `--version`: в официальном tag строка отстаёт. Использовать image/source digest, binary hash и реальный handshake. Источники: [официальный workflow](https://github.com/amnezia-vpn/amneziawg-go/blob/v3.1.20260828/.github/workflows/build-if-tag.yml), [tools3.1](https://github.com/amnezia-vpn/amneziawg-tools/releases/tag/v3.1.20260812), [Amnezia defaults](https://github.com/amnezia-vpn/amnezia-client/blob/ac175c8a8147cfe56f98c8372ec17ea2ba00bb02/client/core/utils/constants/protocolConstants.h).

Units устанавливаются в `/etc/systemd/system`, helper — в `/usr/local/libexec`; перед стартом подготовить защищённые config/env и DNS file, проверить свободные namespace/link names/control subnet. После `systemd-analyze verify` и `daemon-reload` включить `amneziawg-egress`; второй Privoxy запускается его native dependencies/Upholds. Остановка выполняется в обратном порядке, helper не удаляет занятые посторонние interfaces.

При восстановлении операторской административной пробы `ip link down/up` нужно восстановить и namespace default route: ядро удаляет его при down. При аварии daemon полный systemd lifecycle пересоздаёт route сам. Если один peer/key используется на другом устройстве, roaming endpoint может нарушить оба подключения: использовать выделенный клиентский профиль.

Приёмка и реальные скорости: [GOAL второго транспорта](../reports/2026-11-06/TRANSPORT_AMNEZIAWG_GOAL.md). Оба протокола используют **один VPN-узел**; резервирования его отказа и гарантированной скорости эта схема не даёт. `OPENWEBUI_SOCKS5_UPSTREAM` теперь описывает Xray backend; активный выбор смотрится в основной конфигурации, а не в `.env`.

## 2. Secondary provider через Admin UI

1. Войти администратором.
2. Открыть Admin Settings.
3. Открыть Connections.
4. В секции OpenAI/OpenAI-compatible connection выбрать manage/add connection.
5. Ввести base URL:
   - OpenAI: `https://api.openai.com/v1`;
   - Gemini: `https://generativelanguage.googleapis.com/v1beta/openai`.
6. Ввести API key.
7. Для Gemini secondary указать Model IDs: `gemini-3.5-flash`.
8. Сохранить connection.
9. Запустить проверку connection в UI или открыть список моделей.

Для Gemini не использовать trailing slash в этом runbook. Google SDK examples показывают slash в base URL, но OpenWebUI connection URL в PRD-0 нормализован без slash.

Если оператор намеренно тестирует Gemini 3 Flash Preview, использовать точный model id `gemini-3-flash-preview`. Строка `gemini-3-flash` без `preview` не является выбранным exact model id в PRD-0.

## 3. Проверить OpenAI

Проверить:

- connection сохраняется;
- список моделей загружается или `gpt-5.4-mini` доступен;
- тестовый чат получает ответ от OpenAI;
- пользователю не виден API key.

Если список моделей не загружается:

- проверить API key;
- проверить billing/quota;
- проверить доступ к `gpt-5.4-mini`;
- проверить, что base URL указан как `https://api.openai.com/v1`;
- посмотреть логи OpenWebUI:

```bash
docker compose --env-file .env -f compose/openwebui.compose.yml logs --tail=100 openwebui
```

## 4. Проверить Gemini

Проверить:

- connection сохраняется;
- список моделей загружается или `gemini-3.5-flash` доступен;
- тестовый чат получает ответ от Gemini;
- пользователю не виден API key.

Если список моделей не загружается:

- проверить Gemini API key;
- проверить Google Cloud/project billing, quota и региональные ограничения;
- проверить доступ к `gemini-3.5-flash`;
- проверить, что base URL указан как `https://generativelanguage.googleapis.com/v1beta/openai`;
- посмотреть логи OpenWebUI.

## 5. Acceptance evidence

В приватном deployment note зафиксировать без секретов:

- какой provider выбран primary;
- какой provider добавлен secondary;
- model ids: OpenAI `gpt-5.4-mini`, Gemini `gemini-3.5-flash`;
- дата и результат тестового ответа OpenAI;
- дата и результат тестового ответа Gemini;
- если один provider не проверен, почему он pending и кто владеет решением.

## Non-goals

Не настраивать в PRD-0:

- LiteLLM;
- model gateway;
- routing/fallback;
- per-user limits;
- budgets;
- provider-specific proxy.

## Sources

- OpenWebUI OpenAI-compatible connection docs: https://docs.openwebui.com/getting-started/quick-start/connect-a-provider/starting-with-openai-compatible/
- OpenWebUI Starting with OpenAI: https://docs.openwebui.com/getting-started/quick-start/starting-with-openai/
- Gemini OpenAI compatibility: https://ai.google.dev/gemini-api/docs/openai
- Gemini 3.5 Flash model page: https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash
- OpenAI model catalog: https://developers.openai.com/api/docs/models/gpt
