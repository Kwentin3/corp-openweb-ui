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

2. Импортировать `deploy/openwebui-functions/officecli_auto_attach_filter.py` как Filter, но до проверки оставить valves пустыми. Файл в Git является source of truth; его LF-нормализованный SHA-256 для версии `0.9.0-multi-xlsx-native` — `b4ea612001ffabd3c9a130816d671427c5df09974a37a3c0a015878525238d1d`. Это единственный автоподключающий слой: он добавляет существующий `server:officecli` до штатного разрешения tools и не вызывает OfficeCLI сам. В списке **Functions** включить оба независимых флага этой функции: основной switch строки (**Active**) и switch **Global** через меню `…`. Без Global inlet не участвует в обычных чатах; без Active функция не исполняется вообще.

3. Для каждого прямого профиля модели в **Advanced Parameters** явно выбрать **Function Calling: Native** и нажать **Save & Update**; не полагаться на значение `Default`. В valves Filter оставить проверенный список прямых моделей текущего каталога:
   `claude-opus-5,claude-sonnet-4-6,gpt-5.4-mini,models/gemini-3.5-flash,models/gemini-3.6-flash,gpt-5.6-luna,models/gemini-3.1-flash-lite,models/gemini-3.5-flash-lite,office-documents`.
   Это восемь прямых моделей и существующий профиль `office-documents`. У последнего включить `meta.capabilities.file_upload`, сохранив его базовую модель и Tool IDs. Пустое `target_model_ids` выключает Filter. Broker/NDFL/STT/Mistral и task models не добавлять.

4. Filter дописывает одну короткую идемпотентную инструкцию, общую для всех девяти профилей, не заменяя существующий system prompt. В ней есть только маршрутизация трёх create-операций, три минимальные формы команд, граница help для сложной структуры/правки и требование `result_file_id`. Отдельной Gemini-инструкции нет. Штатное разрешение `tool_ids` затем сохраняет проверку доступа к global Tool Server; Filter не открывает чужие файлы и не обходит отключённый сервер.

Не подключать инструмент вслепую к специализированным моделям Broker/NDFL/STT/Mistral. Список фактически проверенных моделей фиксируется в сдаче. Модель без native tool calling не объявлять поддержанной только потому, что Tool Server виден пользователю.

`Office Documents` может оставаться переходной конфигурацией для обратной совместимости, но сотрудник не должен выбирать её как обязательную точку входа.

При квалификации новой версии подтвердить затронутые сценарии в обычном пользовательском чате: создание и правку файлов, последовательные операции, A → B model switch и обновление страницы. При несовместимом native tool-calling пути отключить затронутую конфигурацию и сохранить точный failure receipt. Предыдущая DOCX-матрица находится в `docs/reports/2026-09-21/OFFICECLI_COMPACT_CONTEXT_MODEL_MATRIX.report.md`; актуальная квалификация нескольких XLSX на девяти профилях — в `docs/reports/2026-09-26/OFFICECLI_ALL_PUBLISHED_MODELS.report.md`. XLSX-проверка не означает новую квалификацию всех DOCX/PPTX-сценариев.

## Clean VPS: порядок восстановления

1. Поднять основной OpenWebUI и внутреннюю сеть `openwebui_web` по `docs/ops/DEPLOYMENT_RUNBOOK.md`.
2. Собрать и поднять только sidecar:

   ```bash
   docker compose -p officecli451e7cede5 -f compose/officecli-openapi-proof.compose.yml build
   docker compose -p officecli451e7cede5 -f compose/officecli-openapi-proof.compose.yml up -d
   ```

3. Создать глобальный Tool Server `officecli` с внутренним URL из шага 1 раздела «Нативная конфигурация»; секреты и session state в Git не переносить.
4. Для Gemini использовать квалифицированный основной образ с overlay V2 из раздела ниже. Импортировать Filter строго из `deploy/openwebui-functions/officecli_auto_attach_filter.py`, проверить версию и SHA-256, затем настроить оба модельных valve на девять ID из раздела «Нативная конфигурация». Для `office-documents` включить загрузку файлов; исключение reasoning настроить только на Luna.
5. Включить **Active** и **Global** только после read-only проверки карточки Function и одного успешного файла на тестовой модели. После включения выполнить полную матрицу из отчёта.

Импорт Function и настройка Tool Server остаются нативной административной конфигурацией OpenWebUI. Репозиторий хранит воспроизводимый source и порядок действий, но не копию базы OpenWebUI, токены, cookies или credentials.

## Инструкция интеграции

Source of truth инструкции — строка `OFFICECLI_INSTRUCTION` в Filter. Её смысл:

- простой новый DOCX/XLSX/PPTX сразу идёт в соответствующую create-операцию по минимальной форме команды;
- skill/help загружается только для существующей сложной структуры либо новой таблицы, диаграммы или картинки;
- существующий файл сначала инспектируется и меняется подходящим apply batch;
- успех подтверждается `result_file_id` и штатным вложением, после чего лишние inspect/help/recreate в том же ответе запрещены.

Пользователь не вводит эту инструкцию, не включает function calling и не называет инструмент. Не копировать парафраз из этого runbook в Admin UI: импортировать точный Python source. При нескольких офисных файлах в ближайшем сообщении адаптер не выбирает первый молча: модель должна использовать однозначный `file_id` из штатного контекста.

### Несколько XLSX в обычном чате

Для OpenWebUI 0.9.6 отдельно настроить `multi_xlsx_native_model_ids`:
Установить тот же список девяти ID, что и в `target_model_ids` выше.
По умолчанию этот valve пуст; Gemini требует квалифицированного overlay V2.
При двух различных XLSX в штатном `body.files` Filter выбирает native tool loop
через общий `metadata.params.function_calling`; ручная настройка Native пользователю
не требуется. Именно OpenWebUI добавляет `<attached_files>` с ID источников,
проверяет права, выполняет последовательные tools и прикрепляет выходной файл.
Filter не создаёт собственный реестр файлов. На последующих сообщениях исходные
ссылки восстанавливаются из штатной истории чата; повторная загрузка не нужна.
Полный извлечённый контекст также предоставляет штатная обработка файлов OpenWebUI.

Для текущего OpenAI Chat Completions установить
`multi_xlsx_no_reasoning_model_ids=gpt-5.6-luna`: отсутствие явного effort
переводится в `none` только для этого многофайлового пути. Явно выбранный другой
effort вызывает объяснимую ошибку, а не скрытое снижение. Для reasoning вместе
с tools нужна отдельно квалифицированная Responses-конфигурация.

Для прежнего runtime без квалифицированного overlay Gemini не включать в этот valve: streamed tool calls
без `index` отбрасываются OpenWebUI; дополнительно требуется сохранение Google
thought signature. Старый `target_model_ids` и остальные Office-сценарии этим
valve не изменяются. Это ограничение протокола, а не потеря загруженных файлов.
Проверка данных, формул, отсутствия лишних листов и ролей описана в
`docs/reports/2026-09-26/OFFICECLI_MULTI_XLSX_PRODUCT.report.md`.

Для отключения только автоматического многофайлового пути очистить
`multi_xlsx_native_model_ids`. Остальные valves и чаты остаются у своих владельцев.

### Полный опубликованный каталог: квалифицированный release Gemini

2026-09-26 после отдельного согласования и успешного CI установлен
`corp-openwebui/openwebui:officecli-all-models-release-20260926`, image ID
`sha256:095f1a356b38d2461265b58a8b9fbc6d97063b41d68712193a5c08c94bb04097`,
implementation `7176d602422adca2c6f3ea5014507b5d203a3755`, overlay V2.
Все девять профилей прошли обычный пользовательский чат с двумя XLSX,
скачивание результата и строгую проверку исходных ячеек, формул и итогов.
Оба модельных valve теперь содержат девять ID из итоговой acceptance matrix;
исключение reasoning содержит только Luna. Сохранены volume и все mounts;
sidecar не перезапускался. Итоговые доказательства находятся в
`docs/reports/2026-09-26/artifacts/officecli-all-models/acceptance.json`.

После первоначальной квалификации трёх моделей проверены также Claude Opus 5
и уже опубликованный Workspace-профиль `office-documents` (базовая модель
`claude-opus-5`). У профиля необходимо включить `meta.capabilities.file_upload`:
старый false приводил к отправке сообщения без XLSX. Добавить именно этот
существующий профиль в оба модельных valve, сохранив его текущие Tool IDs.
Остальные специализированные Workspace/Pipe-модели остаются вне области.

Для четырёх Gemini в опубликованном каталоге подготовлен image overlay
`deploy/openwebui-patches/apply_google_openai_tool_protocol_patch.py`.
Он допускает только точные исходные SHA OpenWebUI 0.9.6, задаёт отсутствующий
index полным Gemini-вызовам и переносит исходный `extra_content.google` через
штатный output и восстановление истории. Подписи не подменяются и не хранятся
во внешнем кеше. Исполнение tools, авторизация и файлы остаются штатными.
Dockerfile содержит модуль и проверку реальных функций установленного runtime;
source-sync allowlist содержит все три необходимых файла адаптации.

Overlay V2 уже активирован и квалифицирован на девяти профилях. При будущей
смене runtime согласовать перезапуск отдельно, проверить точные исходные SHA
и повторить затронутую продуктовую матрицу. Доказательства текущего результата:
`docs/reports/2026-09-26/OFFICECLI_ALL_PUBLISHED_MODELS.report.md`.
Rollback: вернуть `corp-openwebui/openwebui:media-intake-audio-release-20260925`
с ID `sha256:114f20df22d1e4f33e9381a5e75492db92310b98f61694e6f7e5f1c1c5336a6b`
и восстановить в `multi_xlsx_native_model_ids` прежние пять профилей:
`claude-opus-5,claude-sonnet-4-6,gpt-5.4-mini,gpt-5.6-luna,office-documents`.
Отдельно проверенную загрузку файлов Office Documents сохранить.
Резервные конфигурации находятся вне Git, с root-only доступом, в
`/root/.local/state/openwebui-releases/officecli-all-models-20260926`.
Удалять адаптацию после подтверждённой штатной поддержки протокола провайдером
или runtime; неизвестные новые SHA должны остановить сборку, а не продолжить
патчирование предположительно похожего источника.

## Пользовательский результат

Пользователь видит короткие статусы и штатное вложение с новым или изменённым офисным файлом DOCX/XLSX/PPTX. JSON payload, внутренние ID, команды OfficeCLI и диагностический протокол не должны быть основным ответом.

Карточка файла — штатный владелец скачивания и прав доступа. Встроенный preview OpenWebUI не является WYSIWYG: для DOCX допустимы упрощения отображения, а для PPTX отдельно зафиксирован неблокирующий backlog #473 по встроенному изображению. Источником истины является скачанный OOXML-файл, открытый в соответствующем Office-приложении. Улучшение preview и интерфейсная косметика — отдельный backlog, не DOM-хак этой интеграции.

## Запуск и отключение

Sidecar описан в `compose/officecli-openapi-proof.compose.yml` и запускается с `restart: unless-stopped`. У него нет host port и Traefik router; он работает в `openwebui_web` с закреплённым OfficeCLI `1.0.148`, `OFFICECLI_SKIP_UPDATE=1` и `OFFICECLI_NO_AUTO_RESIDENT=1`.

Уже действующий `NO_PROXY` основного OpenWebUI содержит имя sidecar. Не пересоздавать, не перезапускать и не обновлять основной OpenWebUI для этой интеграции без отдельного согласования.

Чтобы отключить Office-capability без изменения чатов или файлов:

1. Для немедленного отключения в Admin UI выключить основной switch (**Active**) у `OfficeCLI Auto Attach`. Это не меняет чаты и файлы.
2. Для отключения области применения очистить `target_model_ids` у Filter; при необходимости также выключить switch **Global** через меню `…`.
3. Не заменять это ручным назначением `officecli` на профили моделей; Tool Server `officecli` выключать только если нужно остановить capability для всех разрешённых пользователей.
4. Остановить только sidecar его Compose-проектом.

Обратное включение capability — вернуть проверенные модельные valves и поднять только sidecar. Это не требует изменения основного OpenWebUI или его volume. Откат основного образа с Gemini overlay — отдельная операция по процедуре выше и требует согласования перезапуска.
