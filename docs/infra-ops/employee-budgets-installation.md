# Установка бюджетов сотрудников и откат

Статус10.11.2026: инструкция подготовки, **не разрешение на deployment**.
Текущее состояние и незакрытые пункты — в [единственной записи GOAL584](employee-budgets-goal584.md).
Streaming unknown-Usage ещё не квалифицирован. До закрытия этого пункта нельзя
объявлять комплект готовым для всех рабочих моделей и инструментов Office.

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
Builder проверяет base digest, native3/SDK8 source hashes и сохраняет immutable IID.
Разрешение на этот патч ограничено стендом; production activation согласуется отдельно.

## Подключение и проверка

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
| Service tasks | `employee_budget_service` / [service_pipe.py](../../deploy/openwebui-budgets/service_pipe.py) для согласованных задач |

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
