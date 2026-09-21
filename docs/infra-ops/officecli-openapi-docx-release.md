# Постоянная OfficeCLI capability для DOCX, XLSX и PPTX

## Назначение

OfficeCLI дополняет обычный рабочий чат OpenWebUI: сотрудник выбирает модель и создаёт или правит DOCX, XLSX и PPTX со штатным вложением результата. Это не отдельная модель и не второй файловый контур.

OpenWebUI остаётся владельцем чатов, пользователей, штатных прав и sharing, файлов и выдачи вложений. OfficeCLI владеет офисными командами и официальными skill/help. Тонкий OpenAPI-адаптер связывает только эти два владельца.

## Нативная конфигурация

1. В **Admin Settings → Integrations → Tool Servers** оставить глобальный OpenAPI Tool Server с неизменяемым ID `officecli`:

   - URL: `http://officecli-openapi-proof:8080` только во внутренней Docker-сети;
   - auth type: `Session`;
   - соединение включено;
   - access grant — штатный доступ авторизованных пользователей OpenWebUI.

2. Импортировать `deploy/openwebui-functions/officecli_auto_attach_filter.py` как Filter, но до проверки оставить valves пустыми. Файл в Git является source of truth; его LF-нормализованный SHA-256 для версии `0.8.4-compact-context-experiment` — `f348a3e20f3bd2cd42785b461d029a505c7e39a61b15b0c6bc683a5f6c3fca93`. Это единственный разрешённый автоподключающий слой: он добавляет существующий `server:officecli` до штатного разрешения tools и не вызывает OfficeCLI сам. В списке **Functions** включить оба независимых флага этой функции: основной switch строки (**Active**) и switch **Global** через меню `…`. Без Global inlet не участвует в обычных чатах; без Active функция не исполняется вообще.

3. Для каждого прямого профиля модели в **Advanced Parameters** явно выбрать **Function Calling: Native** и нажать **Save & Update**; не полагаться на значение `Default`. В valves Filter оставить проверенный список прямых моделей текущего каталога:
   `claude-opus-5,claude-sonnet-4-6,gpt-5.4-mini,models/gemini-3.5-flash,models/gemini-3.6-flash,gpt-5.6-luna,models/gemini-3.1-flash-lite,models/gemini-3.5-flash-lite`.
   Это расширяет native OfficeCLI на OpenAI, Claude и Gemini. Пустое `target_model_ids` выключает Filter. Не добавлять `Office Documents`, Broker/NDFL/STT/Mistral или task models.

4. Filter дописывает одну короткую идемпотентную инструкцию, общую для всех восьми моделей, не заменяя существующий system prompt. В ней есть только маршрутизация трёх create-операций, три минимальные формы команд, граница help для сложной структуры/правки и требование `result_file_id`. Отдельной Gemini-инструкции нет. Штатное разрешение `tool_ids` затем сохраняет проверку доступа к global Tool Server; Filter не открывает чужие файлы и не обходит отключённый сервер.

Не подключать инструмент вслепую к специализированным моделям Broker/NDFL/STT/Mistral. Список фактически проверенных моделей фиксируется в сдаче. Модель без native tool calling не объявлять поддержанной только потому, что Tool Server виден пользователю.

`Office Documents` может оставаться переходной конфигурацией для обратной совместимости, но сотрудник не должен выбирать её как обязательную точку входа.

До постоянного включения подтвердить в браузере: по одному новому DOCX, XLSX и PPTX на каждой модели, обычную фразу с приложенным файлом, две последовательные правки, A → B model switch, новую учётную запись и обновление страницы. При первом несовместимом native tool-calling пути очистить `target_model_ids` и сохранить точный failure receipt. Матрица последней квалификации записана в `docs/reports/2026-09-21/OFFICECLI_COMPACT_CONTEXT_MODEL_MATRIX.report.md`.

## Clean VPS: порядок восстановления

1. Поднять основной OpenWebUI и внутреннюю сеть `openwebui_web` по `docs/ops/DEPLOYMENT_RUNBOOK.md`.
2. Собрать и поднять только sidecar:

   ```bash
   docker compose -p officecli451e7cede5 -f compose/officecli-openapi-proof.compose.yml build
   docker compose -p officecli451e7cede5 -f compose/officecli-openapi-proof.compose.yml up -d
   ```

3. Создать глобальный Tool Server `officecli` с внутренним URL из шага 1 раздела «Нативная конфигурация»; секреты и session state в Git не переносить.
4. Импортировать Filter строго из `deploy/openwebui-functions/officecli_auto_attach_filter.py`, проверить версию и SHA-256, затем настроить восемь model IDs.
5. Включить **Active** и **Global** только после read-only проверки карточки Function и одного успешного файла на тестовой модели. После включения выполнить полную матрицу из отчёта.

Импорт Function и настройка Tool Server остаются нативной административной конфигурацией OpenWebUI. Репозиторий хранит воспроизводимый source и порядок действий, но не копию базы OpenWebUI, токены, cookies или credentials.

## Инструкция интеграции

Source of truth инструкции — строка `OFFICECLI_INSTRUCTION` в Filter. Её смысл:

- простой новый DOCX/XLSX/PPTX сразу идёт в соответствующую create-операцию по минимальной форме команды;
- skill/help загружается только для существующей сложной структуры либо новой таблицы, диаграммы или картинки;
- существующий файл сначала инспектируется и меняется подходящим apply batch;
- успех подтверждается `result_file_id` и штатным вложением, после чего лишние inspect/help/recreate в том же ответе запрещены.

Пользователь не вводит эту инструкцию, не включает function calling и не называет инструмент. Не копировать парафраз из этого runbook в Admin UI: импортировать точный Python source. При нескольких офисных файлах в ближайшем сообщении адаптер не выбирает первый молча: модель должна использовать однозначный `file_id` из штатного контекста.

## Пользовательский результат

Пользователь видит короткие статусы и штатное вложение с новой версией DOCX. JSON payload, внутренние ID, команды OfficeCLI и диагностический протокол не должны быть основным ответом.

Карточка файла — штатный владелец скачивания и прав доступа. Текущий встроенный preview DOCX может упрощать вёрстку и цвета; источником истины является скачанный файл, открытый в Word. Перенос карточки файла, Word-кнопка в toolbar и точный preview — отдельный backlog, не DOM-хак этой интеграции.

## Запуск и отключение

Sidecar описан в `compose/officecli-openapi-proof.compose.yml` и запускается с `restart: unless-stopped`. У него нет host port и Traefik router; он работает в `openwebui_web` с закреплённым OfficeCLI `1.0.148`, `OFFICECLI_SKIP_UPDATE=1` и `OFFICECLI_NO_AUTO_RESIDENT=1`.

Уже действующий `NO_PROXY` основного OpenWebUI содержит имя sidecar. Не пересоздавать, не перезапускать и не обновлять основной OpenWebUI для этой интеграции без отдельного согласования.

Чтобы отключить Office-capability без изменения чатов или файлов:

1. Для немедленного отключения в Admin UI выключить основной switch (**Active**) у `OfficeCLI Auto Attach`. Это не меняет чаты и файлы.
2. Для отключения области применения очистить `target_model_ids` у Filter; при необходимости также выключить switch **Global** через меню `…`.
3. Не заменять это ручным назначением `officecli` на профили моделей; Tool Server `officecli` выключать только если нужно остановить capability для всех разрешённых пользователей.
4. Остановить только sidecar его Compose-проектом.

Обратное включение — вернуть проверенный список `target_model_ids` и поднять только sidecar. Основной OpenWebUI, его volume и другие сервисы не входят ни в запуск, ни в rollback.
