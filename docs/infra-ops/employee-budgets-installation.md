# Установка бюджетов сотрудников и откат

Статус10.11.2026: инструкция подготовки, **не разрешение на deployment**.
Текущее состояние и незакрытые пункты — в [единственной записи GOAL584](employee-budgets-goal584.md).
Streaming CC Usage и native регистрация проверены на LiteLLM1.105.1/OpenAI SDK2.33.0.
Actual42825996133 подтвердил отмену → native failure row → reader unknown → адресную
блокировку и отказ без повторного dispatch; native Compose merge также проверен.
Это подготовленный стендовый комплект. Установка, DB/Redis/права и каталог на
целевом сервере остаются отдельной приёмкой; production не менялся.

## Что устанавливается

Существующий LiteLLM получает native budget DB/Redis, auth и callbacks;
существующий WebUI — backend-модули и native Functions/Tool. Нового сервера
учёта или отдельного хранилища денег нет. PostgreSQL, users, virtual keys и
SpendLogs остаются штатными владельцами финансового состояния LiteLLM.

Отдельный [Compose overlay](../../compose/openwebui.employee-budgets.compose.yml)
добавляется к существующим release Compose только при установке бюджетов.
Он использует сервисы `google-gateway-0122` и `openwebui-0122`; базовые файлы,
data volumes, сети и обычный release-путь не заменяются.

## Подготовка до включения

1. Сохранить текущие image IDs, protected config/env, native connection settings,
   источники Functions/Tools/Models, Valves и ACL. Сделать штатную согласованную
   резервную копию WebUI DB и бюджетной DB. Секреты остаются в protected файлах,
   отдельно от Git и публичных отчётов.
2. Подготовить существующие native PostgreSQL/Redis и проверить доступ из
   контейнера LiteLLM. Наличие этих ресурсов на production пока не проверено.
   Не использовать disposable volumes, аккаунты или цены из proof-стенда.
3. Выбрать точный проверенный image ID/digest LiteLLM и WebUI0.12.2.
   Stock1.105.1 сам по себе не подтверждает наличие проверенной calendar-floor
   поправки. Сохранить её manifest и точную идентичность выбранного артефакта.
4. До включения custom auth создать и прочитать обратно native control-plane
   identities через stock management API. Master, shared gateway bearer, native
   management key и viewer key различны. Management — `proxy_admin` с явно
   разрешёнными маршрутами из существующего [bootstrap owner](../../scripts/goal584-budget-proof/prove_gateway_auth.py);
   сам proof-скрипт на production не устанавливается и не запускается.
   Viewer — `proxy_admin_viewer`, только `/spend/logs/session/ui`.
   Проверить роли и `allowed_routes` через `/user/info` и `/key/info`.
5. Согласовать конкретный каталог deployment IDs, маршрутов и реальных native
   цен. Wildcard gateway-конфигурация без проверки цен не является бюджетной
   конфигурацией. Native0 требует protected explicit input/output rates;
   дополнительный audit descriptor для этого не обязателен.

Protected budget env содержит `DATABASE_URL`, native Redis connection values,
`LITELLM_MASTER_KEY`, отдельный `OWUI_BUDGET_GATEWAY_SECRET` и native
`OWUI_BUDGET_OPERATOR_KEY`. Последний использует existing Usage guard;
его отсутствие/некорректный формат запрещает регистрацию callback. Проверка
формата не заменяет проверку настоящих прав ключа.

В protected LiteLLM config сохранить согласованный `model_list` и параметры
провайдеров. Добавить штатные настройки, заполнив Redis из реального подключения:

```yaml
general_settings:
  master_key: os.environ/LITELLM_MASTER_KEY
  database_url: os.environ/DATABASE_URL
  custom_auth: litellm_auth.gateway_auth
  custom_auth_run_common_checks: true
  missing_session_id: omit
  coordination_redis:
    host: os.environ/REDIS_HOST
    port: 6379
    password: os.environ/REDIS_PASSWORD
  fail_closed_budget_enforcement: true
  disable_spend_logs: false
  store_prompts_in_spend_logs: false
  proxy_batch_write_at: 1
litellm_settings:
  callbacks: [budget_errors.handler, pricing_snapshot.handler, budget_runtime.handler]
  block_requests_for_models_without_pricing: true
```

Это фрагмент, не самостоятельный runnable config: model/protocol profiles
должны быть квалифицированы отдельно. Не переносить отсюда Redis password/port,
если реальное подключение использует иной native вариант.

Для согласованного **стендового** streaming-кандидата `stream-usage-v1.105.1`
список callbacks имеет следующий вид:

```yaml
callbacks: [budget_errors.handler, pricing_snapshot.handler, budget_runtime.responses_handler, budget_runtime.cc_stream_handler]
```

Эти два Usage callbacks экспортирует тот же `budget_runtime.py`, с тем же
protected operator key. Responses peer сохраняет существующий buffered-upstream
профиль и native WebUI SSE/Tools; CC peer читает исходный признак Usage из
проверенного патча. Точный образ собирается существующим
`scripts/goal584-budget-proof/build_native_floor_image.py --variant stream-usage-v1.105.1`
с отдельными абсолютными `--context` и `--receipt` на подготовленном стенде.
Builder проверяет base digest, native4/SDK8 source hashes и сохраняет immutable IID.
Составной proxy source включает прежний floor patch и передачу отмены из фактического
CC generator в общий cleanup; исходный floor patch проверяется отдельно без изменений.
Разрешение на этот патч ограничено стендом; production activation согласуется отдельно.

## Подключение и проверка

Для подготовки единого маршрута используется существующий
`deploy/openwebui-upgrade-0122/prepare_google_gateway.py` с обоими параметрами:

```text
--root /opt/openwebui-upgrade-0122/<phase>
--managed-config /opt/openwebui-upgrade-0122/<phase>/private/approved-litellm.json
--managed-env /opt/openwebui-upgrade-0122/<phase>/private/approved-litellm.env
```

Это подготовка новой защищённой фазы, без применения native config или запуска
контейнеров; существующий gateway она не перезаписывает. Входной JSON является
штатным конфигом LiteLLM в YAML-совместимом формате и копируется точно, без
построения второго каталога тарифов. Значения цен и подключения задаёт оператор.
Env содержит разные master/operator/shared inference keys и native DATABASE_URL.
Обязателен профиль обоих `budget_runtime.responses_handler` и
`budget_runtime.cc_stream_handler`; legacy handler к этому списку не добавляется.
Для managed Responses alias требуется уже квалифицированный native профиль:
`model_info.mode=responses`, `supports_native_streaming=false` и
`litellm_params.model=openai/<wire model>` без другого custom provider override.
LiteLLM получает полный upstream HTTP response; WebUI сохраняет SSE/Tools.
Подготовка отклоняет иной профиль, поскольку наличие callbacks само по себе
не включает проверку Usage в неподдерживаемой streaming-ветке.

Managed-подготовка читает native `/openai/models`, сохраняет API type Responses/CC,
prefix и разрешённые metadata headers, направляет все enabled connection slots
в тот же LiteLLM и помещает в WebUI только shared inference bearer. Disabled
connection slots очищаются от URL, ключей и скрытых credential headers; исходная
конфигурация сохраняется в protected source snapshot. Неоднозначные активные
подключения, конфликтующие headers, отсутствующие aliases/цены и fallback вызывают
отказ подготовки. Ошибка managed-профиля не переключает её на legacy-режим.
Default CC bootstrap остаётся исторической транспортной подготовкой; для включения
бюджетов применяется только managed-режим и бюджетный overlay.

Перед включением подтвердить `direct.enable=false`, `ollama.enable=false`,
native attachment/активность бюджетных Functions и service task binding.
Низкоуровневый native model helper сам request Filters не запускает. OCR внешнего
загрузчика подписывает отдельную служебную операцию `document_ocr` с настоящими
actor/File IDs через общие модули; chat/answer root для неё не создаётся. Плательщик —
служебный бюджет платформы из common `service_payer_id`, не сотрудник. Нужны native
назначение этого плательщика на OCR model alias и его лимит. Отсутствие конфигурации,
неподходящий gateway/model или неподписанный вызов останавливают запрос до провайдера;
прямого fallback нет. При неизвестной Usage блокируется соответствующий служебный
ключ модели, личные ключи сотрудника сохраняются. Raw Responses и native File ACL
сохраняются; новая обвязка не меняет содержимое PDF и инструкцию распознавания.
Неактивные broker direct adapters требуют отдельного включения в общий путь
перед активацией; наличие их файлов не означает работающий обход.

В существующем protected Compose env задать `EMPLOYEE_BUDGET_LITELLM_IMAGE`,
`EMPLOYEE_BUDGET_CONFIG_FILE`, `EMPLOYEE_BUDGET_ENV_FILE` и
`EMPLOYEE_BUDGET_MODULES_DIR`. Последний — каталог исходников
`deploy/openwebui-budgets` выбранной поставки. Overlay монтирует отдельные файлы
под точными runtime names; каталог целиком и стендовые модули не монтируются.
Проверить итоговый Compose командой `docker compose ... config --quiet`, затем
перечень mounts/image IDs. Обычный вывод `config` может раскрыть protected env.
Проверка Compose не доказывает import/runtime или продуктовую приёмку.

После отдельного разрешения установки подключить модули и установить через
native Workspace/API ресурсы из выбранной поставки:

| Ресурс | Native ID / источник |
|---|---|
| Cost Filter | `employee_budget_cost` / [cost_filter.py](../../deploy/openwebui-budgets/cost_filter.py) |
| Details Action | `employee_budget_cost_details` / [cost_action.py](../../deploy/openwebui-budgets/cost_action.py) |
| Admin Tool | admin-only Tool / [admin_tools.py](../../deploy/openwebui-budgets/admin_tools.py) |
| Monthly budget Event | `employee_budget_monthly_view` / [monthly_view.py](../../deploy/openwebui-budgets/monthly_view.py) |
| Service tasks | `employee_budget_service` / [service_pipe.py](../../deploy/openwebui-budgets/service_pipe.py) для согласованных задач |
| OCR Event | существующий OCR Function / [luna_pdf_ocr.py](../../deploy/openwebui-functions/luna_pdf_ocr.py), с общими budget modules |

Проверить source/ACL readback, включить Filter/Action и, если используется,
service Pipe; прочитать `is_active` обратно. Filter/Action прикрепить к согласованным
Models и проверить сохранённые `filterIds`/`actionIds`.
В admin-only Valves `employee_budget_cost` задать `ledger_base_url` (корень LiteLLM
без `/v1`), `ledger_read_key` (viewer), `ledger_admin_key` (management).
Tool Valves `managed_model_ids` содержат выбранные native Model IDs без ключей.
Для согласованных service tasks явно задать common `service_payer_id`, Pipe Valves
`target_model_id` и native `TASK_MODEL`/`TASK_MODEL_EXTERNAL=employee_budget_service`;
проверить разрешения на исходную и целевую модель. Месячный шаблон задавать явно,
не сбрасывая существующие назначения. Лимиты сотрудников задаются готовой формой
с native подтверждением.

Для просмотра месячного бюджета установить и включить Event `employee_budget_monthly_view`
через native Functions API, прочитать сохранённые source/type=`event`/`is_active=true`.
Новых module mounts и отдельного credential не требуется: Event использует уже
подключённые budget modules и common `ledger_base_url`/`ledger_admin_key`.

`GET /api/v1/employee-budgets/monthly` возвращает бюджет текущего native authenticated
user. Параметр `?user_id=<UUID>` другого сотрудника доступен только действующему
администратору. Роль и целевой пользователь повторно проверяются перед выдачей;
ответ `Cache-Control: no-store`. Клиенту не выдаются native key hashes, aliases и
management credentials. GET не создаёт назначений и не меняет финансовые данные.
Отсутствующая/противоречивая native конфигурация даёт безопасный отказ, не нулевой бюджет.

Суммы — строковые десятичные native counters и проекция cap-minus-spend; это не
гарантия допуска следующего запроса с учётом резервов. Период/следующий reset передаются
из native user/model полей без пересчёта календаря. `expense_status=unknown` означает
подтверждённый witness неизвестного расхода; `unavailable` не доказывает отсутствие
такого расхода. `expense_observation_scope=assignment_history` явно отделяет этот
ограниченный поиск истории текущего назначения от месячных counters.

Личный GUI использует уже установленное действие **«Стоимость: детали»** у
собственного ответа. Оно показывает расходы ответа/чата и раздел **«Мой бюджет»**:
личный лимит, учтённый расход, остаток, native период/следующее обновление, данные
и блокировку по моделям. Повторное открытие читает свежий снимок. Для этого нужен
активный Event `employee_budget_monthly_view`; Action вызывает его серверный reader
с native пользователем, не передаёт ключи в iframe и не вызывает модель. Если
месячный reader недоступен, этот раздел явно недоступен; расходы ответа/чата
сохраняют самостоятельный результат. Ноль не подставляется вместо ошибки.

Это штатный снимок внутри сообщения: действие доступно у существующего собственного
ответа, отдельной страницы до первого ответа нет. При явной публикации/экспорте чата
пользователь публикует и сохранённый снимок; карточка сообщает об этом и не содержит
email/UUID сотрудника. Fresh self/admin read остаётся защищённым серверными правами.

OCR использует тот же common `service_payer_id` без зависимости от `target_model_id`
служебного Pipe; выбранная OCR-модель остаётся прежней. Это отдельная операция над
файлом, поэтому её расходы не добавляются к личной стоимости ответа/чата. В native
Responses 0.12.2 `TASK` может быть пустым: служебного плательщика разрешает только
проверенная подпись `document_ocr`, связанная с actor, File и точным model alias.
Произвольные body metadata, старый chat-service token без TASK и неподписанный вызов
такого разрешения не дают.

Все согласованные LLM connections, включая Responses, должны использовать общий
gateway bearer и native headers `X-OpenWebUI-User-Id: {{USER_ID}}`,
`X-OpenWebUI-Task: {{TASK}}`. Сохранить тип API, wire model IDs, полный контекст,
Tools и reasoning; изменение URL само по себе не доказывает совместимость.
После установки сверить один согласованный сквозной сценарий с native ledger:
форма → запрос/помощник → две суммы → отказ → изменение лимита → восстановление;
known0/unknown, Details/reload и чужой доступ — в объёме принятой приёмки GOAL.

## Откат с сохранением данных

Остановить поступление новых managed model calls на время отката. Вернуть
сохранённые image/config/env и native Functions/Tools/Models/Valves/ACL, сверить
их точную идентичность. Native бюджеты, key assignments и SpendLogs сохранить;
не выполнять `down -v`, очистку Redis, прямую правку spend или импорт stand DB.
Восстанавливать DB из backup только отдельной согласованной процедурой, поскольку
обычный откат кода не должен стирать новые финансовые записи.

Возобновить трафик после проверки management доступа, учёта и enforcement на
согласованной конфигурации. Прежний прямой маршрут к провайдеру автоматически
не включать: режим работы при откате согласуется как часть deployment.
