# OfficeCLI в обычном чате OpenWebUI

Единственный пользовательский вход — обычный чат с выбранной прямой моделью.
Отдельный Office Documents, его промпт и маршруты обратной совместимости удалены
из целевой конфигурации. Историю чатов и пользовательские файлы не удалять и не
переписывать. Для продолжения старого чата пользователь выбирает доступную модель;
скрытая подмена удалённого профиля запрещена.

Этот runbook описывает выпущенный native-workflow. Текущее состояние установки и
приёмки Open Terminal зафиксировано в
[производственном отчёте](../reports/2026-09-28/open-terminal-production-acceptance.report.md).
История квалификации OfficeCLI приведена в
[отчёте кандидата](../reports/2026-09-28/officecli-native-kiss.report.md).
[Дополнение для заказчика](../commercial/COMPLETED_WORK_2026-09-28_OPEN_TERMINAL_OFFICE_WORKFLOW.md)
описывает тот же выпуск без операционных деталей.
Наличие более нового кода в Git само по себе не означает его выкладку: при
сопровождении сверять установленный release-state и фактические образы.

## Владельцы и конфигурация

- OpenWebUI владеет пользователями, чатами, правами, файлами и вложениями.
- Установленный OfficeCLI владеет командами, синтаксисом, проверками и справкой.
- Существующий OpenAPI-адаптер переводит только транспорт файлов и ограничивает
  ресурсы. Он не выбирает содержание документа или бизнес-сценарий.

В **Admin Settings → Integrations → Tool Servers** используется один сервер:

- ID `officecli`, URL `http://officecli-openapi-proof:8080` во внутренней сети;
- авторизация `Session`, штатные access grants авторизованных пользователей;
- соединение включено, отдельные назначения инструмента офисным профилям не нужны.

Единственный автоподключающий слой — Function из
`deploy/openwebui-functions/officecli_auto_attach_filter.py`. Импортировать точный
source выбранного коммита, сверить LF SHA-256 и версию. Используются штатные
независимые переключатели **Active** и **Global**. Вторых копий и резервных
Functions в реестре приложения не держать.

`target_model_ids` содержит разрешённые прямые модели. Исходный список берётся из
`DEFAULT_TARGET_MODEL_IDS` этого же файла; не вести его дубликат в runbook.
При выпуске сверять с фактическим каталогом и сохранять действующие права доступа.
Пустой список выключает автоподключение. Удалённые профили не добавлять.
NDFL/Broker/STT, task models и провайдеры без native tool calling не включать.
Публичный каталог после удаления Office Documents содержит восемь прямых моделей;
административная видимость других моделей не означает публичную квалификацию.

Filter выбирает native function calling до штатного разрешения `tool_ids`.
Вспомогательные tasks и запросы с явно переданными `tools` остаются у своего
владельца. Права сервера и файлов проверяются OpenWebUI, Filter их не обходит.

`no_reasoning_model_ids` отражает проверенное ограничение текущего провайдера
Chat Completions. Явно выбранный несовместимый reasoning приводит к ошибке,
а не скрытому снижению. Смена провайдера или протокола не выполняется автоматически.

## Контекст и выполнение

Описание `get_officecli_help` содержит неизменённый workflow из `tools/list`
установленного OfficeCLI. Подробные skills и адресный help загружаются по запросу.
Источник общего транспортного контекста — `OFFICECLI_INSTRUCTION` в Filter;
не копировать его в промпты моделей и не добавлять инструкции по отдельным заданиям.

Штатный файловый контекст передаёт ID вложений и восстанавливает их из истории.
При нескольких источниках агент передаёт явный `file_id`; неоднозначность должна
возвращаться ошибкой. Текстовые цитаты RAG не заменяют исследование структуры.
Настройка File Context остаётся у OpenWebUI; её глобальное отключение не входит
в этот выпуск. Результаты сравнительных прогонов приведены в отчёте.

Чтение не публикует файлы. Create/apply работают с копией и возвращают штатные
`result_file_id` и `download_url`. Nonresident CLI сохраняет результат до ответа;
отдельные open/save/close не нужны. Частичный результат после ошибки не публикуется.
Ответ должен показывать реальное вложение, а не вымышленную sandbox-ссылку.

Большие чтения имеют продолжение `next_offset` / `next_text_offset`. Ограничения
пакетов и рендеринга опубликованы в OpenAPI; автоматического дробления, best-effort
или замены команды другим движком нет. Сценарный сборщик Excel и автоматическая
нормализация Word удалены. Нативный `merge` — подстановка шаблона, не обещание
произвольного переноса книг без потерь.

### Завершение многоэтапной работы

Универсальная инструкция находится в
[`deploy/openwebui-skills/artifact-workflow.md`](../../deploy/openwebui-skills/artifact-workflow.md).
Она установлена как штатный Skill и использует native Tasks для перечня частей,
прогресса и проверки. Не дублировать её в системных промптах моделей. Один план
не обеспечивает перенос большого массива данных: полный Excel-прогон завершился
после подключения штатного Open Terminal с серверным Linux-выполнением.

Open Terminal подключён через штатный раздел Integrations. На проверенной 0.9.6
Tool `terminal_file_transfer` передаёт явно выбранное и разрешённое вложение чата
в новую рабочую папку и публикует проверенный результат обратно в OpenWebUI Files.
Файл, оставшийся только в рабочей папке Terminal, не является вложением чата.
Права Tool, Skill и Terminal выданы всем пользователям после отдельного принятия
границы доверенной команды. Два обычных пользователя получили разные домашние
каталоги; общий контейнер не считается изоляцией взаимно недоверенных арендаторов.

Кандидат операции `render_office_file` принимает `grid` для обзора всех страниц
DOCX или слайдов PPTX. Для проверки пагинации Word использовать этот штатный
режим: в закреплённом OfficeCLI одиночная первая страница пропускает пагинацию и
может показывать ложный перенос/наложение. Отдельные страницы остаются для деталей.
Не повторять изменения документа ради дефекта, который исчезает при проверке
того же файла другим штатным режимом просмотра.

Кандидат Filter исправляет только добавленный моделью префикс `sandbox:` у
Markdown-ссылки, если её адрес и ID подтверждены успешным результатом публикации
OfficeCLI в текущем ответе. Неизвестные адреса не восстанавливаются по имени файла.
Это не универсальная защита от вымышленных ссылок. Границы проверки и внедрения
описаны в [отчёте кандидата](../reports/2026-09-28/office-workflow-completion.report.md).

### Передача файлов в Linux

Для установленной OpenWebUI 0.9.6
`deploy/openwebui-tools/terminal_file_transfer.py` связывает существующие Files API,
выбранный Terminal и события вложений. `stage_chat_file` копирует доступное
вложение в новую папку; `publish_terminal_file` сохраняет новый результат в Files
и прикрепляет его к ответу. Исходники сохраняются. Содержимое файлов и секреты
не передаются через контекст модели. Временное чтение повторяется один раз;
операция записи автоматически не повторяется.

До выпуска обычный чат с двумя исходными книгами прошёл полный путь на Linux:
23 листа, все значения и изображения, публикация самим агентом. После выпуска
отдельный обычный пользователь прошёл XLSX, DOCX и PPTX через передачу, Linux-
обработку и штатную публикацию; исходные хэши сохранились. Tool, Skill и Terminal
включены для всех пользователей только на разрешённых прямых моделях и только при
наличии Office-вложения. Обновление всей платформы ради более нового Filesystem
upload требует своей проверки существующих расширений. Подробности — в
[отчёте передачи файлов](../reports/2026-09-28/terminal-file-handoff.report.md) и
[производственной приёмке](../reports/2026-09-28/open-terminal-production-acceptance.report.md).

Общий OpenWebUI-слой устанавливается скриптом
`deploy/openwebui-tools/office_workflow_release.py`. Он принимает два файла с
правами `0600`: короткоживущий admin token и полное описание уже выбранного
Terminal-соединения. При `apply` порядок фиксирован: Terminal → Tool → Skill →
глобальный Filter. До последнего шага пользовательский маршрут не переключается.
Скрипт создаёт новый файл отката через exclusive create с правами `0600`; там
находится прежняя конфигурация, включая прежний секрет соединения, поэтому этот
файл нельзя класть в Git или выводить в журнал.

```bash
python deploy/openwebui-tools/office_workflow_release.py apply \
  --base-url http://openwebui:8080 \
  --token-file /run/secrets/openwebui-admin-token \
  --terminal-connection-file /run/secrets/office-terminal-connection.json \
  --backup-file /release-state/office-linux-before.json
```

Откат использует тот же base URL и token, но не принимает новое соединение:

```bash
python deploy/openwebui-tools/office_workflow_release.py rollback \
  --base-url http://openwebui:8080 \
  --token-file /run/secrets/openwebui-admin-token \
  --backup-file /release-state/office-linux-before.json
```

### Trusted-team Open Terminal runtime

`compose/open-terminal-office.compose.yml` is the accepted runtime after explicit
confirmation that every current OpenWebUI user is trusted at the same level. It
enables upstream multi-user mode and separate homes, keeps the service off host
ports, pins the qualified full image, and joins only `openwebui_web`. The shared
kernel, process list, network, root-capable system state and 2 GiB resource pool
are not per-user isolation.

Keep `OPEN_TERMINAL_API_KEY` in a server-local mode-0600 environment file. Build
the release connection file with ID `office-linux`, URL
`http://open-terminal-office:8000`, `auth_type` `bearer`, the same key,
`config.enable=true`, and the `user:*:read` grant. Keep that JSON mode 0600 and
pass it to `office_workflow_release.py apply`; do not print either file.

Apply in this order:

1. Start the pinned Compose service and wait for its Docker health status.
2. Add `open-terminal-office` and `open-terminal-office:8000` to both `NO_PROXY`
   and `no_proxy` for OpenWebUI. Without this entry the outbound proxy can return
   HTTP 502 for the internal Terminal route.
3. Run the common release installer. It switches the global Filter last.
4. Run an ordinary-user Office chat, then a second synthetic-user separation
   check without private files.
5. Verify OpenWebUI health, public HTTP, container restart counts, result
   attachment download and unchanged source hashes.

Rollback starts with `office_workflow_release.py rollback`, then stops the
Compose service. Do not pass `--volumes` to `docker compose down`; the named home
volume is preserved for a reviewed recovery or later deletion.

For users who must be protected from one another, do not use this Compose file.
Deploy licensed Terminals and pass its already qualified connection JSON to the
same common installer. The Kubernetes backend plus NetworkPolicy is the upstream
path when network isolation is required.

Откат возвращает старый Filter первым, затем восстанавливает или удаляет только
ресурсы с ID `terminal_file_transfer`, `artifact-workflow` и `office-linux`.
Другие Terminal-соединения, включая добавленные после выпуска, сохраняются.

## Установка и выпуск

1. Использовать существующий OpenWebUI и сеть `openwebui_web`. Ядро, volume и
   пользовательские данные не пересоздавать. Подтверждённая адаптация протокола
   Google находится в `deploy/openwebui-patches`; это не альтернативный tool loop.
   Удалять её после квалификации штатной поддержки на выбранном runtime.
2. Собрать sidecar из `services/officecli-openapi-proof/Dockerfile` и Compose
   `compose/officecli-openapi-proof.compose.yml`. Закрепить точный image ID, сверить
   source, отсутствие host ports, read-only root, tmpfs и внутреннюю сеть.
3. Проверить CI, реальный установленный CLI и обычный пользовательский чат.
   Сверить структуру и содержимое скачанных XLSX/DOCX/PPTX, формулы, сохранность
   исходников, read-only запрос, follow-up, reload и смену модели. Отсутствие доступа
   к провайдеру записывать как непроверенный пункт, не как успешный тест.
4. Удалить Workspace Model `office-documents` штатным Models API, убрать его ID из
   valves. Удалить отключённые резервные OfficeCLI Functions. Не создавать алиас,
   перенаправление или fallback для старого ID. Перед и после сверить сохранность
   истории и файлов; не вызывать маршруты удаления чатов или файлов.
5. После согласованного выпуска обновить единственный sidecar и единственную
   Function. Обновить кеш схемы штатным сохранением существующего Tool Server:
   `GET /api/v1/configs/tool_servers`, затем `POST` неизменённой конфигурации.
   Сохранить ID, Session auth и права. Не добавлять второй публичный сервер.
6. Повторить обычный пользовательский путь на установленной версии. Удалить
   временные QA-профили, Functions и соединения после завершения их назначения.

При сбое выключить **Active** у общей Function и при необходимости остановить
только sidecar. Не переключать пользователей на старую модель, промпт или сборщик.
Исправленный кандидат проходит те же проверки перед повторным включением.
Архивные образы и отчёты являются forensic evidence, а не активным fallback.

Для инцидентов использовать существующий [самописец](openwebui-flight-recorder.md),
сопоставляя container ID, UTC и фактическую ошибку. Не выводить причину OOM только
из совпадения по времени с вызовом инструмента.

## История

Прежние процедуры и результаты доступны в Git и датированных отчётах. Они не
должны использоваться для восстановления удалённых маршрутов. Актуальное
состояние и непроверенные ограничения приведены в отчёте текущего кандидата.
