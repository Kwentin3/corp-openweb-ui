# Постоянная конфигурация OfficeCLI DOCX

## Назначение

Это штатная конфигурация OpenWebUI для двухходового редактирования DOCX.
Пользователь выбирает одну готовую модель в списке, прикладывает Word-файл и
общается с ней обычными репликами. OpenWebUI продолжает владеть чатами,
вложениями, доступом и sharing; OfficeCLI — командами и официальной справкой.

## Единственная офисная конфигурация

Создать через **Admin Settings → Models** один Workspace Model:

| Поле | Значение |
| --- | --- |
| Отображаемое имя | `Office Documents` |
| Model ID | `office-documents` |
| Base model ID | `claude-opus-5` |
| Function calling | `native` |
| System prompt | Текст из раздела «Инструкция интеграции» |
| Tool IDs | `server:officecli` |
| Access | Все авторизованные пользователи, которым уже доступна базовая модель |

Не изменять `claude-opus-5` и другие модели. Если базовая модель недоступна
пользователю, Workspace Model не должен обходить это ограничение.

## Инструмент

В **Admin Settings → Integrations → Tool Servers** сохранить существующее
OpenAPI-подключение с неизменяемым ID `officecli`:

- тип: OpenAPI;
- URL: `http://officecli-openapi-proof:8080` только во внутренней Docker-сети;
- auth type: `Session`;
- подключение включено;
- native access grants выданы всем авторизованным пользователям в рамках
  обычных прав OpenWebUI.

Использование `server:officecli`, а не индексного `server:0`, исключает
зависимость модели от порядка подключений. Не добавлять ключи, отдельную ACL,
реестр файлов или browser-side маршрутизацию.

## Инструкция интеграции

Это системная инструкция модели, а не собственная Word-методика:

> Для интеграции OfficeCLI в этом чате Shell и ручная передача бинарника не
> нужны. Skill/help/inspect только читают. `apply_office_batch` сам применяет
> правку, сохраняет DOCX и прикрепляет его к текущему ответу. О выполнении
> сообщай только после успешного результата с `result_file_id`.

Официальный Word skill и `help` OfficeCLI остаются источником синтаксиса и
офисных операций.

## Запуск и выключение

Sidecar описан в
`compose/officecli-openapi-proof.compose.yml` и запускается с
`restart: unless-stopped`. Он не имеет host port или Traefik router, работает
в `openwebui_web` и использует закреплённый OfficeCLI `1.0.148` с
`OFFICECLI_SKIP_UPDATE=1` и `OFFICECLI_NO_AUTO_RESIDENT=1`.

Уже действующий `NO_PROXY` основного OpenWebUI содержит имена sidecar. Не
пересоздавать, не перезапускать и не обновлять основной OpenWebUI для этой
интеграции.

Чтобы отключить Office-функцию без затрагивания чатов, файлов или OpenWebUI:

1. В Admin UI выключить Tool Server `officecli` и убрать доступ к Workspace
   Model `office-documents`.
2. Остановить только sidecar его Compose-проектом.

Обратное включение — вернуть доступ и поднять только этот sidecar. Основной
OpenWebUI, его volume и другие сервисы не входят ни в запуск, ни в rollback.
