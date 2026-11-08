# GOAL: второй исходящий транспорт AmneziaWG

Статус: завершён, независимая приёмка PASS (6 ноября 2026). Авторизация: «добавляем новый транспорт Amnesia WG и давайте тестанем его»; максимально KISS/native.

Результат: второй проверенный исходящий маршрут OpenWebUI/STT/gateway через предоставленный AmneziaWG3.1/UDP, сохранённые Xray и основной HTTP endpoint Privoxy, проверяемое ручное переключение без пересоздания приложений. Автоматический failover и третий транспорт не входят в объём.

## Владельцы и границы

| Смысл | Владелец / контракт | Потребитель и классификация |
| --- | --- | --- |
| Ключ и параметры AWG | Предоставленный Amnezia export → native Interface/Peer | Локальная подготовка файлов — representation-only adapter; ключи/параметры не переизобретаются. |
| Handshake, шифрование, UDP | Native amneziawg-go3.1 + awg tools | Изолированный туннель; серверный профиль и peers не меняются. |
| Изоляция маршрутов/DNS | Linux network namespace, iproute2, /etc/netns resolv.conf | Второй native Privoxy как HTTP adapter; отсутствует default route через veth. |
| Выбор исходящего транспорта | Единственная forwarding directive основного Privoxy | Приложения сохраняют HTTP endpoint и NO_PROXY; второго владельца выбора нет. |
| Жизненный цикл | Native systemd units | Небольшой helper только упорядочивает native команды настройки/уборки namespace и links. |

Два экземпляра Privoxy нужны по доказанному разрыву: native AWG предоставляет L3-interface, а приложения уже используют HTTP proxy. Второй экземпляр использует установленный binary и изолированный direct egress; основной остаётся владельцем выбора. Host default route, глобальный DNS, NAT/forwarding и код приложений не меняются.

## Проверено

- Профиль protocol_version3.1, UDP, тот же сервер; IP/endpoint и форматы ключей валидны. Native S1–S4 удовлетворяют требованию header protection. Серверный peer присутствует, ранее не имел handshake/endpoint: активный чужой клиент этим ключом не обнаружен.
- Сервер приложения Ubuntu24.04, kernel6.8, /dev/net/tun присутствует; новых tools пока нет. Native systemd255 поддерживает нужный lifecycle. Перед работой нет network namespaces, host route rules стандартные.
- Официальные готовые amneziawg-go image и tools Noble найдены; сборка/DKMS на production не требуется. Независимое исследование подтвердило ожидаемую поддержку переноса TUN при сохранении daemon/UDP sockets в root namespace; необходимо проверить на фактическом binary.

## Ход реализации и принятые уточнения

- Установлены официальный static go binary из image digest `c68009d33df3aef4654db72bf1a7880cfa0a631fe866c50d9ae3dd34ddd7c13a` и Noble tools3.1.20260812 (deb SHA256 `2c924076be2ba217eea04f9693291f01c5307a9be5aeee60d04525a50ff2804f`). Временный контейнер/образ извлечения удалены.
- Root daemon, moved TUN и отдельный Privoxy работают: handshake, DNS, TLS, ожидаемый egress и OpenAI/Lemonfox401 подтверждены; общий default route и ip rules не менялись.
- Native DNS placeholders `$PRIMARY_DNS`/`$SECONDARY_DNS` разрешены из валидных top-level dns1/dns2 по штатному configurator contract, без shell expansion. Секреты — только в root0600 native files.
- Первая проба использовала общий awg-quick fallbackMTU1420. На 25МБ upload с ним запрос не завершился за40с. Уточнён официальный Amnezia Linux AWG default1376 (в ключе MTU отсутствует); с1376 тот же25МБ завершился HTTP200 за35,712с. Причинность улучшения одним тестом не доказана; файл и неуспех сохранены в evidence. Доставленный рабочий env будет1376.
- При административном link-down default route namespace удаляется ядром. Первое восстановление диагностического fault не восстановило этот route и дало500; fault cleanup исправлен. С восстановлением route link-up/API прошли. Реальная авария daemon SIGKILL восстановила оба сервиса автоматически; на финальном MTU1376 — за4,423с с новым успешным API-запросом. Прямого выхода при link-down нет.
- Независимое source review нашло ошибку shell guards под set-e: `! ip link show` не останавливает helper. Исправлено явными if/exit до ownership marker; native regression подтвердил сохранение постороннего dummy-link без создания namespace/marker.
- Официальный Privoxy3.0.34 поддерживает auto-reload forwarding config. Selector использует атомарную замену с новым whole-secondmtime, два свежих native запросa и проверку; сохраняет прежний конфиг для rollback с новымmtime. Restart основного Privoxy не требуется. Выбор читается только из действующей forwarding directive; отдельного statefile нет.

Сейчас: активен AWG; Xray сохранён и работает. Проверено переключение Xray → AWG → Xray → AWG без перезапуска основного Privoxy. Непригодный AWG backend отклоняется до изменения конфигурации. После завершённой загрузки через основной HTTP endpoint счётчики AWG выросли на соответствующий объём. Подробности в игнорируемом `local/transport-awg-20261106/`; единственная текущая запись GOAL — этот файл.

## Итог проверки

1. Официальные готовые artifacts установлены; финальные hashes всех пяти исходных файлов совпадают с deployment. MTU интерфейса и env — 1376, секретные файлы root/0600, каталог root/0700. Native service dependencies закреплены; основной PID Privoxy и Xray прежние. Приложения имеют прежние IDs/images, healthy, без restart; host default route и policy rules прежние.
2. Handshake, DNS, TLS и ожидаемый egress подтверждены. В namespace IPv4 default только через AWG, IPv6 default unreachable. Failclosed и восстановление после SIGKILL проверены. Административный link-down не равен падению daemon: Linux удаляет route, поэтому диагностический cleanup восстанавливал его явно.
3. Native chat `/api/chat/completions`: OpenAI и Google gateway вернули HTTP200, завершённый SSE и ожидаемый текст без error events. Native audio transcription и Stage2 job на русском WAV завершились, текст прочитан обратно и совпал. Внутренние STT/OfficeCLI/gateway/terminal endpoints вернули200.
4. Обычный пользователь через интерфейс OpenWebUI получил точный `TRANSPORT_OK`, генерация завершилась, POST `/api/chat/completions`200. Использован встроенный Playwright MCP с отдельным контекстом. Первые cold-load попытки упёрлись в долгую загрузку статических файлов; до запроса модели они не дошли и не доказывают проблему VPN. После загрузки UI проверка прошла.
5. Временный пользователь удалён через native API; два файла synthetic audio удалены; synthetic Stage2 scope удалён штатным owner, active artifacts=0. Локальные временные токены/WAV удалены, тестовая вкладка закрыта. Extraction image/container удалены. Защищённый rollback archive и игнорируемые диагностические receipts оставлены намеренно; Stage2 tombstones живут по native retention.

Скорость: в последовательном снимке на исходном MTU1420 загрузка10МБ дала AWG22,016 против Xray12,340Мбит/с, отправка5МБ —12,870 против12,306Мбит/с. Отправка25МБ при1420 не закончилась за40с; на финальном штатном Linux MTU1376 закончилась за35,712с (5,600Мбит/с, HTTP200). Один такой опыт не доказывает причинность MTU и не гарантирует скорость; проблема канала не объявлена полностью устранённой.

Ограничения: оба протокола на одном VPN-сервере; переключение ручное; существующие CONNECT-сессии сохраняют прежний маршрут. Проверен crash/recovery daemon, но не перезагрузка хоста и не полная потеря WAN. STT проверен файлом через реальные endpoints, физический захват микрофона не выполнялся.

Evidence: [safe acceptance receipt](TRANSPORT_AMNEZIAWG_ACCEPTANCE.receipt.safe.json); эксплуатация: [runbook](../../ops/PROVIDER_SETUP_RUNBOOK.md).

Независимая итоговая приёмка `contract-outcome-review`: PASS по R1–R6. Сверены 12 разделов публичного receipt с исходными evidence, пять source hashes с deployment, ordinary-user UI snapshot и native cleanup. Блокирующих дефектов и обязательных оставшихся шагов нет. Дополнительные замеры не являются условием закрытия согласованного объёма.
