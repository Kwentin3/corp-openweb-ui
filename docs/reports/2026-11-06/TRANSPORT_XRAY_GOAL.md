# GOAL: исходящий транспорт через Amnezia Xray

Статус: выполнен. Установка, переключение, функциональная приёмка и уборка подтверждены; независимое ревью по `contract-outcome-review` — PASS по R1–R6. Авторизация пользователя: «бери в работу. Максимально kiss, максимально нативно».

Последующее состояние 6 ноября: [AmneziaWG добавлен и принят как второй транспорт](TRANSPORT_AMNEZIAWG_GOAL.md), сейчас выбран AWG; Xray сохранён. Ниже зафиксирован исторический этап перехода SOCKS5 → Xray.

## Результат и границы

Перевести OpenWebUI, STT и gateway с недоступного удалённого SOCKS5 на предоставленный клиентский профиль Amnezia Xray. Сохранить текущий HTTP endpoint Privoxy, код приложений и конфигурацию удалённого сервера. Один native Xray client под systemd; без дополнительного gateway, TUN и изменения системных маршрутов. Второй независимый транспорт — отдельный backlog. Старый SOCKS5 не считать рабочим резервом.

## Принятые решения

- Новый профиль указывает на другой узел, чем в первоначальном аудите; его TCP endpoint доступен с сервера приложения.
- Из `vpn://` используется предоставленный `last_config` VLESS/TCP/REALITY/vision. Не извлекать серверные ключи и не менять Amnezia.
- Приложения сохраняют HTTP proxy и NO_PROXY. Privoxy переключается на локальный SOCKS inbound Xray после отдельной проверки кандидата.
- Установка: официальный стабильный Xray 26.10.31, Linux amd64, официальный installer, зафиксированные артефакты и SHA256; без geodata и отдельных log files.
- Секреты остаются в игнорируемой локальной `.env` и защищённой серверной конфигурации. В отчёт выводятся результаты и агрегаты.

## Проверенное состояние

- Production: OpenWebUI/STT/gateway `0122`; их текущие контейнеры healthy. Privoxy active.
- Узел приложения Ubuntu 24.04 x86_64, достаточно свободных RAM и диска для бинарной установки без сборки.
- Предоставленный профиль декодируется, IP совпадает с полем `.env`, UUID/port корректны, обязательные REALITY поля присутствуют.
- Независимая проверка официального systemd installer выполняется субагентом; установка, переключение и приёмка принадлежат основному агенту.

## Выполнено и подтверждено

Итоговая проверка: 6 ноября 2026, около 14:40 МСК. Машинный receipt: [TRANSPORT_XRAY.receipt.safe.json](TRANSPORT_XRAY.receipt.safe.json). Операционная процедура: [provider runbook](../../ops/PROVIDER_SETUP_RUNBOOK.md#текущий-транспорт-amnezia-xray-6-ноября-2026).

| Требование согласованного GOAL | Наблюдаемый результат |
| --- | --- |
| Native client и точный artifact | Официальный 26.10.31, archive SHA256 проверен; установленный binary `cc4b84d3069569f297a61f04b914f2bb37e9d202fd7b84cb50def1fc30fd40e1`. Официальный installer зафиксирован commit `04e6f3bd9534811ed901a48c47b2c042dd64eb3a`; установленный config-test успешен от пользователя xray. |
| Туннель до переключения | Через временный loopback Privoxy: HTTPS example body, remote DNS, точный egress IP; OpenAI401, Google403 и Anthropic405 без ключей. Единственный outbound VLESS, direct fallback отсутствует. |
| Переключение | В 14:28 МСК изменена одна `forward-socks5t` directive, config-test успешен, перезапущен только Privoxy. HTTP endpoint и NO_PROXY контейнеров сохранены. |
| Цепочка из всех consumers | OpenWebUI, STT и gateway получили OpenAI401 через свои native HTTP clients; каждый отдельно подтвердил новый egress по HTTPS. У STT нет aiohttp, проверен установленный httpx. |
| Чат и gateway | Native `/api/chat/completions`: gpt-5.4-mini (Responses) и models/gemini-3.5-flash-lite (существующий gateway) вернули TRANSPORT_OK; SSE завершены, error events отсутствуют. |
| Обычный пользователь | В браузере native UI под временной ролью user: введён запрос, виден TRANSPORT_OK, POST /api/chat/completions200, генерация завершилась. Использован временный чат. |
| STT | Синтетическая русская фраза «Проверка связи. Новый транспорт работает.» целиком распознана через native audio API и отдельный Stage2 job. Job completed, stub отсутствует; GET result вернул тот же текст. |
| Внутренние соединения | Из OpenWebUI с trust_env=True получены HTTP200 от Stage2 capabilities, OfficeCLI healthz, Terminal health и gateway liveliness. |
| Автозапуск и восстановление | xray.service enabled/active, User/Group=xray, Restart=on-failure. До переключения main process завершён SIGKILL, systemd поднял новый PID; после готовности listener свежий запрос через туннель успешен. |
| Нет лишних изменений | IDs/images/start times трёх контейнеров сохранены, restart counts0, health healthy. Код приложений, удалённая Amnezia и системные маршруты не менялись. |
| Секреты и воспроизводимость | Client config root:xray0640 в каталоге0750, Privoxy config0600, recovery directory0700. Официальные zip/dgst/installer и исходные конфиги сохранены; локальная и старая серверная `.env` согласованы с действующим upstream. |
| Уборка | Временный Privoxy остановлен, listener/config отсутствуют. Временная учётная запись удалена, прежняя браузерная сессия восстановлена. Синтетические WAV/JSON native audio cache удалены; синтетический Stage2 scope удалён штатным store owner (active artifacts0). Локальные временные JWT/password/WAV-файлы удалены. |

Итоговый SHA256 клиентского JSON: `f46734f00cb023adb8120e973afdb9e0ffa748fedc2e2236d09025d9520383f2`; Privoxy после переключения: `cc43915906a7fb59c902f23cc9b2a8d6705a96a16463934edb4fdb9812182d0c`. Точные локальные проверки и private receipts находятся в игнорируемом `local/transport-audit-20261106/`. На сервере сохраняется `/root/transport-xray-20261106` для воспроизведения/восстановления; это намеренно оставленный защищённый операционный архив.

## Ограничения проверки

- Production reboot и реальный WAN outage не провоцировались. Проверены enablement и автоматическое восстановление после аварии процесса, затем новое соединение. Первый диагностический запрос после рестарта опередил готовность SOCKS listener и получил Privoxy500; проверка после готовности listener прошла. Это не было ошибкой рабочего переключения.
- Физический микрофон/MediaRecorder повторно не проверялись: использован настоящий синтетический WAV через оба штатных серверных STT-пути.
- Generation acceptance покрывает текущие активные OpenAI Responses и Google gateway модели. Anthropic проверен до TLS/HTTP endpoint без авторизации; отдельная Anthropic generation не выполнялась. Каталоги/настройки моделей не менялись.
- Stage2 scope удалён штатным logical delete; tombstones и in-memory запись job остаются под native lifecycle/retention. Ради физической очистки не перезапускался production STT и не выполнялись прямые SQL удаления.
- Сохраняется один рабочий внешний транспорт. Второй независимый транспорт и его переключение — следующий backlog, не условие этого GOAL.

## Обязательные оставшиеся шаги

Нет. Независимый reviewer прочитал receipts, точные выполнявшиеся скрипты, runbook и извлечённый из native MCP event браузерный snapshot `local/transport-audit-20261106/browser-final.native.json`. Подтверждены R1–R6: artifact/permissions, туннель/egress, сохранение owners, функции, восстановление и уборка. Новые provider calls и изменения при ревью не выполнялись; обязательных замечаний нет.

Последующий backlog второго протокола закрыт [отдельным GOAL AmneziaWG](TRANSPORT_AMNEZIAWG_GOAL.md). Оба протокола используют один VPN-узел; резервирования самого узла по-прежнему нет.
